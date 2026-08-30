#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
منسّق الحارس - BatteryGuardAI

يربط الطبقات الأربع في خطّ واحد، ويملك التخزين والوتيرة والسياسة:

    battery_monitor  ─┐
                      ├─► power_attribution ─► battery_intelligence ─► guard_actions
    battery_ai       ─┘        (واط/عملية)        (من يُتلف وبكم)       (ماذا نفعل)

لا Qt هنا بقصد: الخطّ كله قابل للتشغيل والاختبار بلا واجهة، وهو نفسه الذي
يعمل في وضع الخلفية بلا نافذة. `monitor_thread` يستدعي `step()` فقط.

الوتيرة
───────
قراءة البطارية رخيصة (ملف أو اثنان) فتجري كل ثانيتين، أما جولة العمليات
فتقرأ عدّادات مئات العمليات، فتجري كل `ATTRIBUTION_INTERVAL` ثانية. خلط
الوتيرتين في حلقة واحدة كان سيجعل الحارس نفسه مستنزفاً للبطارية.
"""

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

import psutil

from battery_intelligence import (ACTION_ALERT, BatteryIntelligence,
                                  IntelligenceReport, Offender)
from guard_actions import (ACTION_SUSPEND, ACTION_THROTTLE, BatteryGuard,
                           GuardOutcome, GuardPolicy)
from power_attribution import PowerAttribution
from storage import JsonStore

logger = logging.getLogger('BatteryGuard')

#: ملف حالة التعلّم الخاص بهذا الخطّ (منفصل عن battery_ai_data.json حتى لا
#: يتضخّم ملف واحد ولا يفسد تلف أحدهما الآخر)
STATE_FILE = 'battery_guard_state.json'

#: كم ثانية بين جولتي نسب طاقة كاملتين
ATTRIBUTION_INTERVAL = 25.0

#: كل كم ثانية تُحفظ الحالة على القرص
SAVE_INTERVAL = 180.0

#: أقصى عدد عمليات تُطابق باسم واحد عند إعادة استخراج الأرقام
MAX_PIDS_PER_NAME = 24


class GuardService:
    """
    خطّ الاستدلال والحماية كاملاً، بحالة محفوظة وسياسة قابلة للتحديث.

    الاستخدام من خيط المراقبة:
        report = service.step(battery_status, health)
        if report is not None:      # جولة كاملة جرت
            ...اعرضها...
    """

    def __init__(self, monitor, ai, settings: Optional[Dict] = None,
                 dry_run: bool = False,
                 on_report: Optional[Callable[[IntelligenceReport], None]] = None,
                 on_action: Optional[Callable[[GuardOutcome, Optional[Offender]], None]] = None):
        self.monitor = monitor
        self.ai = ai
        self._lock = threading.RLock()
        self.on_report = on_report

        self.store = JsonStore(STATE_FILE, defaults={})
        state = self.store.data if isinstance(self.store.data, dict) else {}

        self.attribution = PowerAttribution(model_state=state.get('power_model'))
        self.intelligence = BatteryIntelligence(state.get('intelligence'))
        self.policy = self._policy_from_settings(settings or {})
        self.guard = BatteryGuard(self.policy, dry_run=dry_run,
                                  notifier=on_action)

        self.enabled = self._attribution_enabled(settings or {})
        self.interval = self._attribution_interval(settings or {})

        self._last_attribution = 0.0
        self._last_save = time.monotonic()
        self.last_report: Optional[IntelligenceReport] = None
        self.rounds = 0

        logger.info(
            f"منسّق الحارس جاهز - عيّنات النموذج: {self.attribution.model.samples}, "
            f"عيّنات الاستدلال: {self.intelligence.samples}, "
            f"سياسة: مفعّل={self.policy.enabled} تلقائي={self.policy.automatic} "
            f"سقف={self.policy.max_action}")

    # ══════════════════════════════════════════════════════
    # الإعدادات
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _policy_from_settings(settings: Dict) -> GuardPolicy:
        """
        بناء السياسة من الإعدادات المسطّحة التي تستخدمها الواجهة.
        المفاتيح كلها ببادئة `guard_` حتى تبقى مجمّعة في ملف واحد.
        """
        return GuardPolicy.from_dict({
            'enabled': settings.get('guard_enabled', True),
            'automatic': settings.get('guard_automatic', False),
            'max_action': settings.get('guard_max_action', ACTION_ALERT),
            'only_on_battery': settings.get('guard_only_on_battery', True),
            'act_below_percent': settings.get('guard_act_below_percent', 100),
            'allowlist': settings.get('guard_allowlist', []),
            'blocklist': settings.get('guard_blocklist', []),
            'allow_irreversible_nice': settings.get(
                'guard_allow_irreversible_nice', False),
            'min_damage_score': settings.get('guard_min_damage_score', 45),
            'min_confidence': settings.get('guard_min_confidence', 55),
        })

    @staticmethod
    def _attribution_enabled(settings: Dict) -> bool:
        return bool(settings.get('attribution_enabled', True))

    @staticmethod
    def _attribution_interval(settings: Dict) -> float:
        try:
            value = float(settings.get('attribution_interval',
                                       ATTRIBUTION_INTERVAL))
        except (TypeError, ValueError):
            return ATTRIBUTION_INTERVAL
        # حدّ أدنى صلب: أقل من عشر ثوانٍ يجعل الحارس نفسه حِملاً محسوساً
        return max(10.0, min(300.0, value))

    def apply_settings(self, settings: Dict) -> None:
        """تحديث السياسة والوتيرة أثناء التشغيل"""
        with self._lock:
            self.policy = self._policy_from_settings(settings)
            self.enabled = self._attribution_enabled(settings)
            self.interval = self._attribution_interval(settings)
        self.guard.update_policy(self.policy)

    # ══════════════════════════════════════════════════════
    # الدورة
    # ══════════════════════════════════════════════════════

    def step(self, battery_status: Dict,
             health: Optional[Dict] = None) -> Optional[IntelligenceReport]:
        """
        جولة واحدة. يعيد التقرير إن جرت جولة نسب كاملة، وإلا `None`.
        يُستدعى من خيط المراقبة على وتيرته السريعة، ويقرّر هو متى يعمل.
        """
        if not self.enabled:
            return None

        now = time.monotonic()
        with self._lock:
            due = (now - self._last_attribution) >= self.interval
            if not due:
                return None
            self._last_attribution = now

        try:
            return self._run_round(battery_status, health or {})
        except Exception as e:  # جولة فاشلة لا يجوز أن تُسقط خيط المراقبة
            logger.error(f"فشلت جولة الحارس: {e}", exc_info=True)
            return None

    def _run_round(self, battery_status: Dict,
                   health: Dict) -> Optional[IntelligenceReport]:
        measured = battery_status.get('power_draw') or None
        charging = bool(battery_status.get('is_charging'))

        result = self.attribution.sample(measured_watts=measured,
                                         is_charging=charging)
        if result is None:
            # أول عيّنة: العدّادات سُجّلت وسيصير الفرق متاحاً في الجولة القادمة
            return None

        drain_rate, hours_on_battery, typical_dod = self._usage_context()
        report = self.intelligence.update(
            result, battery_status, health,
            drain_rate=drain_rate,
            hours_on_battery_per_day=hours_on_battery,
            typical_dod=typical_dod)

        self.rounds += 1
        self.last_report = report

        outcomes = self.guard.enforce(report, battery_status)
        if outcomes:
            logger.info("إجراءات الحارس: " + ", ".join(
                f"{item.kind}:{item.name}" for item in outcomes))

        if self.rounds == 1:
            # أول جولة تُحفظ فوراً: تثبت أن الخطّ يعمل فعلاً، وتُنشئ ملف
            # الحالة فلا يُظنّ أن التعلّم متوقّف بينما هو ينتظر مهلة الحفظ.
            logger.info(
                f"أول جولة نسب طاقة اكتملت: {len(report.offenders)} مستهلك، "
                f"قدرة مقيسة={report.measured_watts}، "
                f"ثقة النموذج={report.model_confidence}٪")
            self.save()
        elif (time.monotonic() - self._last_save) >= SAVE_INTERVAL:
            self.save()

        if self.on_report is not None:
            try:
                self.on_report(report)
            except Exception as e:
                logger.debug(f"مستقبل تقرير الحارس أخفق: {e}")
        return report

    def _usage_context(self) -> tuple:
        """
        معدل الاستنزاف وساعات العمل على البطارية وعمق التفريغ المعتاد، مقروءة
        من `battery_ai` بدل تقديرها هنا: مصدر واحد لكل رقم.
        """
        drain = 0.0
        hours = 4.0
        dod = 30.0
        try:
            drain = float(getattr(self.ai, '_ewma_drain_rate', 0.0) or 0.0)
            if drain <= 0:
                drain = float(self.ai.learning_data.get('average_drain_rate', 0) or 0)
        except (AttributeError, TypeError, ValueError):
            pass
        try:
            projection = self.ai.wear_projection()
            hours = float(projection.get('hours_on_battery_per_day') or 0.0) or 4.0
            dod = float(projection.get('typical_dod') or 0.0) or 30.0
        except Exception as e:
            logger.debug(f"تعذّرت قراءة ملف الاستخدام: {e}")
        return drain, hours, dod

    # ══════════════════════════════════════════════════════
    # إجراءات المستخدم الصريحة
    # ══════════════════════════════════════════════════════

    def resolve_pids(self, name: str) -> List[int]:
        """
        أرقام العمليات الحاملة لهذا الاسم **الآن**.

        لا تُستخدم الأرقام المحفوظة في التقرير: بين لحظة الاستدلال ولحظة نقر
        المستخدم قد تنتهي العملية ويُعاد استخدام رقمها، فيقع الإجراء على
        عملية بريئة. بوابة السلامة تفحص الاسم مرة أخرى أيضاً.
        """
        pids: List[int] = []
        for process in psutil.process_iter(['pid', 'name']):
            try:
                if process.info['name'] == name:
                    pids.append(int(process.info['pid']))
                    if len(pids) >= MAX_PIDS_PER_NAME:
                        break
            except (psutil.Error, TypeError, ValueError):
                continue
        return pids

    def suspend(self, name: str) -> GuardOutcome:
        """تعليق كل عمليات هذا الاسم (قابل للتراجع بـ `resume`)"""
        return self.guard.suspend(name, self.resolve_pids(name))

    def resume(self, name: str) -> GuardOutcome:
        return self.guard.resume(name)

    def throttle(self, name: str) -> GuardOutcome:
        return self.guard.throttle(name, self.resolve_pids(name))

    def restore(self, name: str) -> GuardOutcome:
        return self.guard.restore(name)

    def terminate(self, name: str) -> GuardOutcome:
        """
        إيقاف نهائي بطلب صريح من المستخدم. لا مسار تلقائي يصل إلى هنا.
        """
        logger.warning(f"طلب المستخدم إيقاف {name}")
        return self.guard.terminate(name, self.resolve_pids(name))

    def allow(self, name: str) -> None:
        """إضافة اسم إلى قائمة السماح بالتصرّف تجاهه"""
        with self._lock:
            if name not in self.policy.allowlist:
                self.policy.allowlist.append(name)
        self.guard.update_policy(self.policy)

    def ignore(self, name: str) -> None:
        """منع الحارس من لمس هذا الاسم نهائياً"""
        with self._lock:
            if name not in self.policy.blocklist:
                self.policy.blocklist.append(name)
            if name in self.policy.allowlist:
                self.policy.allowlist.remove(name)
        self.guard.update_policy(self.policy)

    # ══════════════════════════════════════════════════════
    # العرض والتخزين
    # ══════════════════════════════════════════════════════

    def statistics(self) -> Dict[str, object]:
        """ملخّص للعرض في لوحة التحليل"""
        report = self.last_report
        model = self.attribution.model
        return {
            'rounds': self.rounds,
            'enabled': self.enabled,
            'interval': self.interval,
            'model_samples': model.samples,
            'model_calibrated': model.calibrated,
            'model_confidence': model.confidence(),
            'model_r_squared': model.r_squared,
            'model_coefficients': model.coefficients,
            'baseline_watts': round(model.baseline_watts, 2),
            'intelligence_samples': self.intelligence.samples,
            'offenders': 0 if report is None else len(report.offenders),
            'actionable': 0 if report is None else len(report.actionable()),
            'worst': None if report is None or report.worst is None
                     else report.worst.as_dict(),
            'degradation': None if report is None or report.degradation is None
                           else report.degradation.as_dict(),
            'rhythm': None if report is None or report.rhythm is None
                      else report.rhythm.as_dict(),
            'active_interventions': self.guard.active_interventions(),
            'policy': self.policy.as_dict(),
            'history': self.guard.recent_history(10),
        }

    def save(self) -> bool:
        """حفظ حالة النموذج والاستدلال (كتابة ذرية عبر `storage`)"""
        with self._lock:
            self.store.data['power_model'] = self.attribution.model_state()
            self.store.data['intelligence'] = self.intelligence.dump()
            self.store.data['rounds'] = self.rounds
            self._last_save = time.monotonic()
        saved = self.store.save()
        if saved:
            logger.debug(f"حُفظت حالة الحارس ({self.rounds} جولة)")
        return saved

    def reset(self) -> None:
        """تصفير كل ما تعلّمه هذا الخطّ، مع الإفراج عن أي تدخّل نشط"""
        self.guard.release_all()
        with self._lock:
            self.attribution.reset()
            self.intelligence.reset()
            self.rounds = 0
            self.last_report = None
            self._last_attribution = 0.0
            self.store.data.clear()
        self.save()
        logger.info("أُعيد تعيين تعلّم الحارس")

    def shutdown(self) -> None:
        """
        إغلاق نظيف: يُفرج عن كل عملية معلّقة ثم يحفظ. تُستدعى في مسار الخروج،
        وتركها يعني احتمال بقاء عملية معلّقة بعد اختفاء من علّقها.
        """
        try:
            self.guard.stop()
        except Exception as e:
            logger.error(f"تعذّر إيقاف الحارس: {e}")
        try:
            self.save()
        except Exception as e:
            logger.error(f"تعذّر حفظ حالة الحارس: {e}")
