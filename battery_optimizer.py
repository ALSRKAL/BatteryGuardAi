#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
محسّن الطاقة - BatteryGuardAI

الإصدار السابق من هذا الملف أعطب أجهزة مستخدمين: كان يرفع السطوع إلى قيمة
يختارها بنفسه بعد أن ينزله المستخدم، ويعلّق كل أجهزة USB فتسقط محطة الإرساء
والشاشة الموصولة بها، ويكتب على `card0` الذي لا وجود له على كثير من الأجهزة،
ويترك البلوتوث محجوباً و`swappiness` مغيّراً بلا طريق رجوع، ثم يعلن «توفير
15٪» وهو رقم ثابت مكتوب في الشيفرة لا قياس.

هذا الإصدار مبني على عقد مختلف:

| المبدأ | التطبيق |
|---|---|
| لا تغيير بلا طريق رجوع | كل إجراء يلتقط الأصل في لقطة دائمة (`system_tuning`) |
| لا رقم بلا قياس | التوفير يُقرأ من العتاد قبل وبعد، أو يُعلَن «غير مقيس» |
| الامتناع نتيجة معلنة | ما لم يُنفَّذ يظهر بسببه، لا يُخفى ولا يُزعم نجاحه |
| لا صلاحيات لما لا يحتاجها | السطوع عبر مسار الجلسة المصرّح به، بلا كلمة مرور |
| الشاشة الخارجية خط أحمر | إجراءات الرسوم تُلغى كلها عند وجود شاشة موصولة |

ما حُذف نهائياً ولا يعود، لأن ضرره مثبت ومكسبه غير مثبت:
`for i in /sys/bus/usb/devices/*/power/control; do echo auto` (يفصل الإرساء
ولوحة المفاتيح)، `rfkill block bluetooth` (يقطع الفأرة ولا يُستعاد)،
`echo low > power_dpm_force_performance_level` و`echo auto > card0/device/
power/control` (يسقطان الشاشة الخارجية)، `echo 3 > drop_caches` (يُجبر
النظام على إعادة القراءة من القرص فيستهلك أكثر)، `echo 10 > swappiness`
و`echo noop > /sys/block/sda/queue/scheduler` (تغيير دائم في النواة على قرص
مفترض بمجدول لم يعد موجوداً في النوى الحديثة).
"""

from __future__ import annotations

import gc
import logging
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import psutil

from i18n import t
from system_tuning import SafeTuner, graphics_tuning_allowed, usb_tuning_allowed

logger = logging.getLogger('BatteryGuard')

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

# ═══════════════════════════════════════════════════════════
# ثوابت معلنة
# ═══════════════════════════════════════════════════════════

#: أدنى نسبة معالج تجعل عملية مرشحة لخفض أولوية الإدخال/الإخراج.
#: القيمة عالية عن قصد: خفض أولوية عملية تعمل قليلاً لا يوفّر شيئاً ويضرّ.
THROTTLE_CPU_PERCENT = 25.0

#: أقصى عدد عمليات تُخفض أولويتها في جولة واحدة
THROTTLE_MAX_PROCESSES = 5

#: مهلة قياس السحب قبل/بعد (ثانية): أقصر من هذا يقرأ ضجيجاً لا فرقاً
MEASURE_SETTLE_SECONDS = 2.0

#: أوضاع التحسين المقبولة. `basic` و`intelligent` تبقى للتوافق مع النداءات
#: القديمة وتُخطَّط إلى نفس السلوك الآمن: الوضع لم يكن يوماً سبباً كافياً
#: لإجراء أخطر.
KNOWN_MODES = frozenset({'basic', 'advanced', 'intelligent', 'balanced', 'saver'})


# ═══════════════════════════════════════════════════════════
# نتيجة إجراء واحد
# ═══════════════════════════════════════════════════════════

@dataclass
class ActionReport:
    """
    نتيجة إجراء واحد بصيغة تفهمها الواجهة.

    `success` تعني «نُفّذ فعلاً»، و`declined` تعني «امتنعنا وهذا سببه».
    لا حالة ثالثة تُعرض كنجاح وهي ليست كذلك.
    """

    key: str
    success: bool = False
    declined: bool = False
    reason: str = ''
    detail: str = ''
    reversible: bool = True
    measured_watts: Optional[float] = None

    @property
    def name(self) -> str:
        return t(f'opt.action.{self.key}')

    def as_dict(self) -> Dict:
        return {
            'key': self.key,
            'name': self.name,
            'success': self.success,
            'declined': self.declined,
            'reason': self.reason,
            'details': self.detail,
            'reversible': self.reversible,
            'measured_watts': self.measured_watts,
            # التوافق مع القارئ القديم: لا رقم مختلَق، صفر حتى يُقاس
            'power_saved': self.measured_watts or 0.0,
        }


# ═══════════════════════════════════════════════════════════
# المحسّن
# ═══════════════════════════════════════════════════════════

class BatteryOptimizer:
    """
    يقلّل السحب بإجراءات قابلة للتراجع، ويقيس أثرها من العتاد، ويقول ما
    امتنع عنه ولماذا.
    """

    def __init__(self, ai_engine=None, monitor=None,
                 tuner: Optional[SafeTuner] = None):
        self.ai_engine = ai_engine
        #: مصدر قراءة القدرة لقياس الأثر (اختياري: بلا قياس نقول ذلك)
        self.monitor = monitor
        self.tuner = tuner or SafeTuner()

        self.is_optimizing = False
        self._optimizing_lock = threading.Lock()

        #: يبقى للتوافق مع `_sync_permissions`. لا إجراء في هذا الملف
        #: يستخدمه: كل ما نفعله متاح لمالك الجلسة بلا رفع صلاحيات.
        self.sudo_password: Optional[str] = None

        self.optimization_history: List[Dict] = []
        self.total_optimizations = 0
        self.power_saved_total = 0.0
        self.success_rate = 100

        #: العمليات التي خُفضت أولويتها في هذه الجلسة، لاستعادتها
        self._throttled: Dict[int, Tuple[int, int]] = {}
        self._safety_gate = None

    # ── التوافق مع الطبقات الأعلى ───────────────────────────

    def set_sudo_password(self, password: Optional[str]) -> None:
        """
        يُستدعى من مزامنة الصلاحيات. نحفظه ولا نستخدمه: أي إجراء يحتاج
        كلمة مرور المستخدم لضبط سطوع شاشته إجراء مصمَّم خطأً.
        """
        self.sudo_password = password

    @property
    def safety_gate(self):
        """بوابة سلامة العمليات نفسها التي يستخدمها الحارس، لا نسخة ثانية"""
        if self._safety_gate is None:
            from guard_actions import SafetyGate
            self._safety_gate = SafetyGate()
        return self._safety_gate

    # ── القياس ──────────────────────────────────────────────

    def _read_draw_watts(self) -> Optional[float]:
        """سحب القدرة الآن بالواط، أو None إذا لم يوفّره العتاد"""
        if self.monitor is None:
            return None
        try:
            status = self.monitor.get_battery_status()
        except Exception as e:  # pragma: no cover - عتاد لا يستجيب
            logger.debug(f"محسّن: تعذّرت قراءة القدرة: {e}")
            return None
        if not isinstance(status, dict):
            return None
        for key in ('power_draw', 'power_now', 'draw_watts'):
            value = status.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        return None

    def get_system_status(self) -> Dict:
        """حالة النظام الآن: قياسات فقط، بلا درجات مركّبة"""
        status: Dict = {}
        try:
            status['cpu_percent'] = psutil.cpu_percent(interval=None)
            status['memory_percent'] = psutil.virtual_memory().percent
            status['process_count'] = len(psutil.pids())
        except Exception as e:
            logger.debug(f"محسّن: تعذّرت قراءة حالة النظام: {e}")

        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                status['battery_percent'] = int(battery.percent)
                status['is_charging'] = bool(battery.power_plugged)
        except Exception:
            pass

        draw = self._read_draw_watts()
        if draw is not None:
            status['power_draw'] = draw
        status['displays'] = self.tuner.displays().as_dict()
        return status

    def capabilities(self) -> Dict:
        """ما يمكن فعله على هذا الجهاز فعلاً (تعرضه الواجهة قبل أي زر)"""
        return self.tuner.capabilities()

    # ── الإجراءات ───────────────────────────────────────────

    #: أسباب الامتناع المعروفة التي تملك مفتاح ترجمة. ما عداها يُعرض بنصّه
    #: الخام داخل رسالة عامة: مفتاح مفقود أسوأ من سبب غير مترجم.
    KNOWN_REASONS = frozenset({
        'no_internal_panel', 'already_at_floor', 'no_headroom',
        'no_greedy_process', 'all_denied', 'scan_failed',
        'external_display_connected', 'displays_unreadable',
    })

    @classmethod
    def _reason_text(cls, reason: str) -> str:
        """نص سبب الامتناع: مترجم إن كان معروفاً، وصادق إن لم يكن"""
        if not reason:
            return ''
        if reason in cls.KNOWN_REASONS:
            return t(f'opt.reason.{reason}')
        return t('opt.reason.blocked_by_system', detail=reason)

    def _dim_panel(self) -> ActionReport:
        """خفض سطوع اللوحة الداخلية درجة واحدة، بلقطة قابلة للاستعادة"""
        panels_before = self.tuner.internal_backlights()
        before = panels_before[0].percent if panels_before else None

        result = self.tuner.dim_internal_panel()

        if not result.applied:
            return ActionReport('dim_panel', declined=True, reason=result.reason,
                                detail=self._reason_text(result.reason))

        panels_after = self.tuner.internal_backlights()
        after = panels_after[0].percent if panels_after else None
        return ActionReport(
            'dim_panel', success=True, reversible=True,
            detail=t('opt.detail.dimmed', before=before, after=after))

    def _throttle_greedy_processes(self) -> ActionReport:
        """
        خفض أولوية الإدخال/الإخراج للعمليات الشرِهة إلى الصنف الخامل.

        قابل للتراجع تماماً، ولا يلمس أولوية المعالج: `renice` لا يُستعاد بلا
        صلاحيات على معظم التوزيعات، فخفضه من مسار تلقائي تغيير دائم بلا إذن.
        كل عملية تمرّ من بوابة سلامة الحارس: لا نظام، لا خيوط نواة، لا
        مستخدم آخر، لا أسلاف التطبيق ولا ذرّيته.
        """
        candidates: List[Tuple[float, psutil.Process]] = []
        try:
            for process in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                cpu = process.info.get('cpu_percent') or 0.0
                if cpu < THROTTLE_CPU_PERCENT:
                    continue
                verdict = self.safety_gate.check(process.info['pid'],
                                                 process.info.get('name') or '')
                if not verdict.allowed:
                    continue
                candidates.append((cpu, process))
        except Exception as e:
            return ActionReport('throttle', declined=True, reason='scan_failed',
                                detail=str(e))

        if not candidates:
            return ActionReport('throttle', declined=True, reason='no_greedy_process',
                                detail=t('opt.reason.no_greedy_process'))

        candidates.sort(key=lambda item: item[0], reverse=True)
        names: List[str] = []
        for _, process in candidates[:THROTTLE_MAX_PROCESSES]:
            try:
                if not hasattr(process, 'ionice'):
                    continue
                current = process.ionice()
                if process.pid not in self._throttled:
                    self._throttled[process.pid] = (
                        int(getattr(current, 'ioclass', current)),
                        int(getattr(current, 'value', 0)))
                process.ionice(psutil.IOPRIO_CLASS_IDLE)
                names.append(process.name())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except (OSError, ValueError) as e:
                logger.debug(f"محسّن: تعذّر خفض أولوية {process.pid}: {e}")

        if not names:
            return ActionReport('throttle', declined=True, reason='all_denied',
                                detail=t('opt.reason.all_denied'))
        return ActionReport('throttle', success=True, reversible=True,
                            detail=t('opt.detail.throttled',
                                     count=len(names), names=t('unit.list_separator').join(names[:3])))

    def _release_own_memory(self) -> ActionReport:
        """
        تحرير ذاكرة التطبيق نفسه.

        الإصدار السابق كان يكتب `3` في `drop_caches` ويسمّيه «تنظيف الذاكرة
        بالكامل». إفراغ ذاكرة القرص المخبّأة يُجبر النظام على إعادة القراءة
        من القرص، والقرص من أكبر مستهلكي الطاقة: كان يزيد السحب لا يقلّله.
        ما يبقى صحيحاً هو تحرير ذاكرة هذه العملية فقط، وهذا حجمه المعلن.
        """
        before = 0.0
        try:
            before = psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            pass
        collected = gc.collect()
        after = before
        try:
            after = psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            pass
        freed = max(0.0, before - after)
        return ActionReport('own_memory', success=True, reversible=True,
                            detail=t('opt.detail.own_memory',
                                     objects=collected, freed=f'{freed:.1f}'))

    def _declared_refusals(self) -> List[ActionReport]:
        """
        ما امتنع عنه التطبيق صراحةً. يُعرض للمستخدم دائماً: تطبيق يخفي
        امتناعه يبدو أقوى مما هو، وذلك أسوأ من أن يبدو أضعف.
        """
        displays = self.tuner.displays()
        refusals: List[ActionReport] = []

        graphics_ok, graphics_reason = graphics_tuning_allowed(displays)
        if not graphics_ok:
            refusals.append(ActionReport(
                'graphics', declined=True, reason=graphics_reason,
                detail=t(f'opt.reason.{graphics_reason}')))

        _, usb_reason = usb_tuning_allowed(displays)
        refusals.append(ActionReport('usb', declined=True, reason=usb_reason,
                                     detail=t('opt.reason.usb_unsafe')))
        refusals.append(ActionReport('radio', declined=True, reason='needs_consent',
                                     detail=t('opt.reason.radio_needs_consent')))
        refusals.append(ActionReport('kernel', declined=True, reason='not_reversible',
                                     detail=t('opt.reason.kernel_not_reversible')))
        return refusals

    # ── الجولة الكاملة ──────────────────────────────────────

    def optimize_battery(self, use_cached_password: bool = True,
                         optimization_mode: str = 'balanced') -> Dict:
        """
        جولة تحسين واحدة.

        `use_cached_password` و`optimization_mode` يبقيان في التوقيع للتوافق
        مع النداءات القائمة. الأول لا أثر له لأن لا إجراء يحتاج صلاحيات،
        والثاني لا يغيّر خطورة ما يُنفَّذ: كل الأوضاع تُنفّذ الإجراءات الآمنة
        نفسها. الوضع الخطر لم يكن ميزة بل عطلاً.
        """
        with self._optimizing_lock:
            if self.is_optimizing:
                return {'success': False, 'actions': [], 'errors': [],
                        'power_saved': 0.0,
                        'message': t('opt.already_running')}
            self.is_optimizing = True

        if optimization_mode not in KNOWN_MODES:
            optimization_mode = 'balanced'

        started = time.time()
        draw_before = self._read_draw_watts()
        reports: List[ActionReport] = []
        errors: List[str] = []

        try:
            for step in (self._dim_panel, self._throttle_greedy_processes,
                         self._release_own_memory):
                try:
                    reports.append(step())
                except Exception as e:
                    logger.error(f"محسّن: فشل {step.__name__}: {e}")
                    errors.append(f'{step.__name__}: {e}')

            reports.extend(self._declared_refusals())

            applied = [report for report in reports if report.success]
            measured_saving = None
            if applied and draw_before is not None:
                time.sleep(MEASURE_SETTLE_SECONDS)
                draw_after = self._read_draw_watts()
                if draw_after is not None:
                    measured_saving = round(max(0.0, draw_before - draw_after), 2)

            self.total_optimizations += 1
            if measured_saving:
                self.power_saved_total += measured_saving
            self.success_rate = 100 if applied or not errors else max(
                0, self.success_rate - 5)

            record = {
                'timestamp': datetime.now().isoformat(timespec='seconds'),
                'mode': optimization_mode,
                'applied': [report.key for report in applied],
                'declined': {report.key: report.reason
                             for report in reports if report.declined},
                'draw_before': draw_before,
                'measured_saving': measured_saving,
                'duration': round(time.time() - started, 2),
            }
            self.optimization_history.append(record)
            if len(self.optimization_history) > 100:
                self.optimization_history = self.optimization_history[-100:]

            return {
                'success': bool(applied) or not errors,
                'actions': [report.as_dict() for report in reports],
                'errors': errors,
                # التوفير المقيس بالواط، أو None إذا لم يوفّره العتاد
                'power_saved': measured_saving or 0.0,
                'power_saved_measured': measured_saving is not None,
                'draw_before': draw_before,
                'applied_count': len(applied),
                'declined_count': sum(1 for r in reports if r.declined),
                'reversible': all(report.reversible for report in applied),
                'optimization_level': optimization_mode,
                'ai_recommendations': self._ai_recommendations(),
                'personalized_actions': [],
                'can_restore': self.tuner.has_pending_restore() or bool(self._throttled),
            }
        finally:
            self.is_optimizing = False

    def _ai_recommendations(self) -> List[str]:
        """توصيات المحرك المتعلّم إن وُجد، بلا اختلاق عند غيابه"""
        if self.ai_engine is None:
            return []
        try:
            status = self.get_system_status()
            if hasattr(self.ai_engine, 'get_optimization_recommendations'):
                items = self.ai_engine.get_optimization_recommendations(
                    status.get('battery_percent', 50),
                    status.get('is_charging', False))
                return [str(item) for item in list(items)[:3]]
        except Exception as e:
            logger.debug(f"محسّن: تعذّرت قراءة التوصيات: {e}")
        return []

    # ── التراجع ─────────────────────────────────────────────

    def restore(self) -> Dict:
        """
        إرجاع كل ما غيّرته الجولات السابقة: السطوع وأولويات الإدخال/الإخراج.
        تُستدعى بزر صريح وعند الإغلاق النظيف.
        """
        results = [result.as_dict() for result in self.tuner.restore_all()]

        restored_processes = 0
        for pid, (ioclass, value) in list(self._throttled.items()):
            try:
                psutil.Process(pid).ionice(ioclass, value)
                restored_processes += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, OSError):
                pass
            finally:
                self._throttled.pop(pid, None)

        if restored_processes:
            results.append({'action': 'restore_throttle', 'applied': True,
                            'reversible': True, 'reason': '',
                            'detail': {'processes': restored_processes}})

        return {'success': bool(results), 'results': results,
                'message': t('opt.restore_done') if results
                else t('opt.nothing_to_restore')}

    def get_statistics(self) -> Dict:
        """إحصاءات الجولات: أرقام مقيسة أو غائبة، لا مقدّرة بصمت"""
        measured = [record['measured_saving'] for record in self.optimization_history
                    if record.get('measured_saving')]
        return {
            'runs': self.total_optimizations,
            'measured_runs': len(measured),
            'watts_saved_total': round(self.power_saved_total, 2),
            'watts_saved_average': round(sum(measured) / len(measured), 2)
            if measured else None,
            'pending_restore': self.tuner.has_pending_restore() or bool(self._throttled),
            'recent': self.optimization_history[-10:],
        }


#: أسماء متوافقة مع الاستيرادات القديمة
__all__ = ['BatteryOptimizer', 'ActionReport', 'THROTTLE_CPU_PERCENT']
