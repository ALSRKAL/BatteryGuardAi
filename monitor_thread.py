#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خيط المراقبة الخلفي

- فاصل مراقبة قابل للتخصيص مع وضع تكيفي (سريع أثناء التفريغ/قرب الحدود،
  بطيء أثناء الشحن المستقر) لتقليل الاستهلاك.
- إيقاف تعاوني عبر threading.Event بدلاً من QThread.terminate() غير الآمن.
- لا يكرر منطق تنبيهات العتبات: مدير الإشعارات هو المصدر الوحيد لقرار
  الإشعارات، وهذا الخيط يبث البيانات الخام فقط.
- يشغّل خطّ الحارس (`guard_service`) على وتيرته الخاصة الأبطأ: جولة نسب
  الطاقة تقرأ عدّادات مئات العمليات، وتشغيلها كل ثانيتين يجعل التطبيق نفسه
  من أكبر مستنزفي البطارية.
"""

import logging
import threading
import time
from typing import Dict, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from i18n import t

logger = logging.getLogger('BatteryGuard')

# فواصل المراقبة بالثواني
INTERVAL_ACTIVE = 2      # أثناء التفريغ أو قرب حدود التنبيه
INTERVAL_IDLE = 10       # شحن مستقر بعيداً عن الحدود
IDLE_MARGIN = 15         # هامش النسبة حول حدود التنبيه ليبقى الوضع نشطاً


class MonitorThread(QThread):
    """خيط مراقبة حالة البطارية"""

    battery_updated = pyqtSignal(dict)
    notification_requested = pyqtSignal(str, str, str)
    #: تقرير استدلال جديد (IntelligenceReport) - يُبَث حين تكتمل جولة نسب
    intelligence_updated = pyqtSignal(object)

    def __init__(self, monitor, ai, settings: Dict, guard_service=None):
        super().__init__()
        self.monitor = monitor
        self.ai = ai
        self.settings = dict(settings)
        #: خطّ الاستدلال والحماية؛ `None` يعني تشغيلاً بلا حارس
        self.guard_service = guard_service
        self._stop_event = threading.Event()
        self.interval_override: Optional[int] = None  # فرض فاصل ثابت عند الحاجة

    # ── التحكم بالدورة الحياتية ─────────────────────────────────

    def stop(self, timeout_ms: int = 5000) -> bool:
        """إيقاف تعاوني نظيف وانتظار انتهاء الخيط"""
        self._stop_event.set()
        if self.isRunning():
            return self.wait(timeout_ms)
        return True

    @property
    def running(self) -> bool:
        """توافق مع الكود القديم الذي كان يضبط running=False"""
        return not self._stop_event.is_set()

    @running.setter
    def running(self, value: bool):
        if not value:
            self._stop_event.set()

    def update_settings(self, settings: Dict):
        """تحديث الإعدادات مباشرة من خيط الواجهة"""
        self.settings = dict(settings)
        if self.guard_service is not None:
            try:
                self.guard_service.apply_settings(self.settings)
            except Exception as e:
                logger.error(f"تعذّر تحديث سياسة الحارس: {e}")

    # ── حلقة المراقبة ────────────────────────────────────────────

    def run(self):
        logger.info("بدأ خيط المراقبة")
        error_streak = 0
        while not self._stop_event.is_set():
            try:
                battery_status = self.monitor.get_battery_status()

                if battery_status['available']:
                    # تغذية محرك التحليل وصحة العتاد
                    self.ai.analyze_usage_pattern(battery_status)
                    health_info = self.monitor.get_battery_health()
                    if health_info.get('health_percentage') is not None:
                        self.ai.update_hardware_health(health_info['health_percentage'])

                    # خطّ الحارس يقرّر بنفسه متى تحين جولته (وتيرة أبطأ)
                    self._run_guard(battery_status, health_info)

                    # بطارية لا تُبلّغ: لا قرارات حدود مبنية على قياس غير صالح
                    if battery_status.get('reporting', True):
                        charge_action = self.monitor.check_charge_limits(
                            battery_status['percent'],
                            battery_status['is_charging']
                        )
                        if charge_action['action'] != 'none' and charge_action.get('should_notify'):
                            self.notification_requested.emit(
                                t('control.title'),
                                t(charge_action.get('message_key', 'control.title'),
                                  **charge_action.get('params', {})),
                                'normal'
                            )

                    self.battery_updated.emit(battery_status)
                    error_streak = 0
                    sleep_s = self._compute_interval(battery_status)
                else:
                    sleep_s = INTERVAL_IDLE

                self._sleep(sleep_s)

            except Exception as e:
                error_streak += 1
                backoff = min(60, INTERVAL_IDLE * error_streak)
                logger.error(f"خطأ في خيط المراقبة ({error_streak} متتالية): {e}")
                self._sleep(backoff)
        logger.info("انتهى خيط المراقبة")

    def _run_guard(self, battery_status: Dict, health_info: Dict):
        """
        جولة الحارس. فشلها يُسجَّل ولا يُوقف المراقبة: قراءة البطارية والتنبيه
        عند انخفاضها أهمّ من تحليل العمليات، فلا يجوز أن يُسقطها خطأ فيه.
        """
        if self.guard_service is None:
            return
        try:
            report = self.guard_service.step(battery_status, health_info)
            if report is not None:
                self.intelligence_updated.emit(report)
        except Exception as e:
            logger.error(f"خطأ في جولة الحارس: {e}")

    def _compute_interval(self, status: Dict) -> float:
        """اختيار الفاصل: ثابت إن فُرض، وإلا تكيفي حسب الحالة"""
        if self.interval_override:
            return max(1, int(self.interval_override))
        percent = status['percent']
        charging = status['is_charging']

        # كانت هذه القراءة تستخدم getattr على قاموس، فتعيد الافتراضي دائماً
        # وتُفقد الحدود المخصّصة أثرها على وتيرة المراقبة.
        limits = self.settings.get('battery_thresholds') or {}
        thresholds = [
            self.settings.get('low_battery_threshold', 20),
            limits.get('critical_low', 10),
            limits.get('optimal_max', self.settings.get('max_charge_limit', 80)),
        ]
        near_boundary = any(abs(percent - limit) <= IDLE_MARGIN for limit in thresholds)

        if not charging or near_boundary or percent <= 20:
            return INTERVAL_ACTIVE
        return INTERVAL_IDLE

    def _sleep(self, seconds: float):
        """انتظار قابل للمقاطعة الفورية عند طلب الإيقاف"""
        self._stop_event.wait(timeout=max(0.1, seconds))
