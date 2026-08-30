#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
وضع الخلفية الحقيقي - BatteryGuardAI

يشغّل التطبيق بأيقونة صينية وبلا نافذة على الإطلاق: لا نافذة تُبنى ثم تُخفى،
بل لا تُبنى حتى يطلبها المستخدم من الأيقونة. الفرق ملموس، فبناء لوحة القياس
يعني خمسة مجالات وعشرات العناصر ومؤقّتات لا يراها أحد في الخلفية.

    main.py --service ─► BackgroundController ─► BatteryTrayIcon
                                │
                                ├─ BatteryMonitor / BatteryAI
                                ├─ GuardService  (نسب الطاقة + الاستدلال + الحارس)
                                ├─ MonitorThread (خيط القياس)
                                └─ ModernUI      عند أول طلب إظهار فقط

المتحكّم `QObject` لا `QWidget`: لا رسم ولا تخطيط ولا نافذة مخفيّة. يوفّر
للأيقونة نفس الواجهة التي توفّرها لوحة القياس (`show_window`،
`run_optimization`، `quit_application`، وإجراءات الحارس) فلا تعرف الأيقونة
أيّهما يعمل تحتها.
"""

import logging
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from battery_ai import BatteryAI
from battery_monitor import BatteryMonitor
from default_settings import get_default_settings
from guard_service import GuardService
from i18n import t
from monitor_thread import MonitorThread
from notification_manager import SmartNotificationManager
from tray_icon import BatteryTrayIcon

logger = logging.getLogger('BatteryGuard')

#: كل كم مللي ثانية تُحفظ بيانات التعلّم في وضع الخلفية
AUTOSAVE_INTERVAL_MS = 300_000


class BackgroundController(QObject):
    """
    متحكّم الخلفية: يملك القياس والاستدلال والحماية والأيقونة، ولا يملك نافذة.

    النافذة تُبنى تأخيرياً في `show_window`، ويُنقل إليها كل ما تعلّمه
    المتحكّم (نفس كائنات `monitor` و`ai` و`guard_service`) حتى لا يبدأ التعلّم
    من الصفر ولا تعمل نسختان من خيط المراقبة.
    """

    #: تُطلقها نسخة ثانية من التطبيق لطلب إظهار النافذة (آمنة بين الخيوط)
    show_requested = pyqtSignal()

    def __init__(self, settings_provider=None):
        super().__init__()
        self._settings_provider = settings_provider
        self.window = None
        self._quitting = False

        self.monitor = BatteryMonitor()
        self.ai = BatteryAI()
        self.notification_manager = SmartNotificationManager()
        self.guard_service = GuardService(
            self.monitor, self.ai, self._settings(),
            on_action=self._on_guard_action)
        self._last_intelligence = None

        self.tray = BatteryTrayIcon(self)
        if not self.tray.available:
            logger.warning(t('service.tray_missing'))

        self.monitor_thread = MonitorThread(
            self.monitor, self.ai, self._settings(),
            guard_service=self.guard_service)
        self.monitor_thread.battery_updated.connect(self._on_battery)
        self.monitor_thread.notification_requested.connect(self.send_notification)
        self.monitor_thread.intelligence_updated.connect(self._on_intelligence)
        self.monitor_thread.start()

        self._autosave = QTimer(self)
        self._autosave.timeout.connect(self._save)
        self._autosave.start(AUTOSAVE_INTERVAL_MS)

        self.show_requested.connect(self.show_window)
        logger.info("BatteryGuardAI يعمل في الخلفية بلا نافذة")

    # ══════════════════════════════════════════════════════
    # الإعدادات
    # ══════════════════════════════════════════════════════

    def _settings(self) -> Dict:
        """
        الإعدادات الفعّالة. في الخلفية لا توجد عناصر واجهة تُقرأ منها، فتُقرأ
        من المزوّد (QSettings) وإلا من الافتراضات المركزية.
        """
        if self._settings_provider is not None:
            try:
                return self._settings_provider()
            except Exception as e:
                logger.error(f"تعذّرت قراءة الإعدادات: {e}")
        return get_default_settings()

    def reload_settings(self) -> None:
        """إعادة تطبيق الإعدادات على خيط المراقبة والحارس"""
        settings = self._settings()
        self.monitor_thread.update_settings(settings)

    # ══════════════════════════════════════════════════════
    # القياس والاستدلال
    # ══════════════════════════════════════════════════════

    def _on_battery(self, status: Dict) -> None:
        """تحديث الأيقونة من كل قراءة، وتمرير القراءة للنافذة إن كانت مفتوحة"""
        try:
            health = self.monitor.get_battery_health()
            soh = health.get('health_percentage')
            self.tray.update_icon(
                status['percent'], status['is_charging'],
                int(soh) if soh is not None else None,
                status.get('reporting', True))
            if status.get('reporting', True):
                prediction = self.ai.predict_time_remaining(
                    status['percent'], status['is_charging'])
                self.tray.update_time_remaining(prediction or t('status.time_unknown'))
            else:
                self.tray.update_time_remaining(t('status.not_reporting'))
        except Exception as e:
            logger.debug(f"تعذّر تحديث الأيقونة: {e}")

        if self.window is not None:
            try:
                self.window.update_battery_display(status)
            except Exception as e:
                logger.debug(f"تعذّر تحديث النافذة: {e}")

    def _on_intelligence(self, report) -> None:
        """تقرير استدلال جديد: يُعرض في الأيقونة، وفي النافذة إن كانت مفتوحة"""
        self._last_intelligence = report
        try:
            self.tray.update_offenders(report)
        except Exception as e:
            logger.debug(f"تعذّر تحديث مخالفي الأيقونة: {e}")
        if self.window is not None:
            try:
                self.window.on_intelligence_report(report)
            except Exception as e:
                logger.debug(f"تعذّر تمرير التقرير للنافذة: {e}")

    def send_notification(self, title: str, message: str, urgency: str) -> None:
        """إشعار من الخلفية عبر مدير الإشعارات، ثم الأيقونة كبديل"""
        settings = self._settings()
        if not settings.get('notifications_enabled', True):
            return
        try:
            self.notification_manager.send_notification(title, message, urgency)
            return
        except Exception as e:
            logger.debug(f"مدير الإشعارات أخفق، سنستخدم الصينية: {e}")
        try:
            self.tray.show_message(title, message)
        except Exception as e:
            logger.error(f"تعذّر إرسال الإشعار: {e}")

    def _on_guard_action(self, outcome, offender) -> None:
        """بلاغ الحارس في الخلفية: سجل دائماً، وإشعار عند إجراء فعلي"""
        logger.info(f"الحارس: {outcome.kind} {outcome.name} "
                    f"({'نُفّذ' if outcome.applied else outcome.reason})")
        if offender is None or not outcome.applied:
            return
        self.send_notification(
            t('guard.title'),
            t('guard.notify.offender', name=offender.name,
              watts=round(offender.watts, 1),
              loss=round(offender.annual_capacity_loss, 2)),
            'normal')

    # ══════════════════════════════════════════════════════
    # واجهة الأيقونة
    # ══════════════════════════════════════════════════════

    def window_visible(self) -> bool:
        """هل النافذة مبنيّة وظاهرة (في الخلفية: لا نافذة أصلاً)"""
        return self.window is not None and self.window.isVisible()

    def hide(self) -> None:
        """إخفاء النافذة إن وُجدت. الخلفية تستمر بلا انقطاع."""
        if self.window is not None:
            self.window.hide()

    def show_window(self) -> None:
        """
        بناء لوحة القياس عند أول طلب، ثم إظهارها.

        النافذة تتشارك نفس `monitor` و`ai` و`guard_service`، ولا يُشغَّل خيط
        مراقبة ثانٍ: خيطان يقرآن نفس العتاد ويكتبان نفس ملفات التعلّم يعني
        بيانات متضاربة واستهلاكاً مضاعفاً.
        """
        if self.window is None:
            logger.info("بناء لوحة القياس بناءً على طلب المستخدم")
            try:
                self.window = self._build_window()
            except Exception as e:
                logger.error(f"تعذّر بناء النافذة: {e}", exc_info=True)
                self.tray.show_message(t('app.name'), t('diag.unreadable'))
                return
        self.window.show()
        self.window.activateWindow()
        self.window.raise_()
        if self._last_intelligence is not None:
            try:
                self.window.on_intelligence_report(self._last_intelligence)
            except Exception as e:
                logger.debug(f"تعذّر تمرير آخر تقرير: {e}")

    def _build_window(self):
        """
        بناء `ModernUI` وإعادة توجيهها إلى كائنات المتحكّم.

        الاستيراد داخل الدالة عن قصد: في وضع الخلفية الدائم لا تُحمَّل وحدة
        الواجهة ولا تبعيّاتها إطلاقاً، وهذا أهمّ ما يوفّره هذا الوضع.
        """
        from main_window import ModernUI

        window = ModernUI.__new__(ModernUI)
        window._shared_context = {
            'monitor': self.monitor,
            'ai': self.ai,
            'notification_manager': self.notification_manager,
            'guard_service': self.guard_service,
            'monitor_thread': self.monitor_thread,
            'tray': self.tray,
        }
        window.__init__()
        # الأيقونة تعود لتشير إلى النافذة حتى تعمل قوائمها على لوحة القياس
        self.tray.parent = window
        return window

    def run_optimization(self) -> None:
        """
        التحسين اليدوي يحتاج لوحة القياس لعرض نتائجه وطلب الصلاحيات.
        فتحها هنا أصدق من تشغيل عملية ثقيلة بلا أن يرى المستخدم نتيجتها.
        """
        self.show_window()
        if self.window is not None:
            QTimer.singleShot(400, self.window.run_optimization)

    # ── إجراءات الحارس من الأيقونة ──────────────────────────

    def guard_suspend(self, name: str) -> None:
        self._guard_action(self.guard_service.suspend, name)

    def guard_resume(self, name: str) -> None:
        self._guard_action(self.guard_service.resume, name)

    def guard_throttle(self, name: str) -> None:
        self._guard_action(self.guard_service.throttle, name)

    def guard_restore(self, name: str) -> None:
        self._guard_action(self.guard_service.restore, name)

    def guard_ignore(self, name: str) -> None:
        self.guard_service.ignore(name)
        logger.info(f"لن يُلمس {name} بعد الآن")

    def guard_terminate(self, name: str) -> None:
        """
        الإيقاف النهائي يحتاج تأكيداً صريحاً، والتأكيد يحتاج نافذة.
        لا إيقاف من قائمة الصينية بنقرة واحدة بلا سؤال.
        """
        self.show_window()
        if self.window is not None:
            QTimer.singleShot(400, lambda: self.window.guard_terminate(name))

    def _guard_action(self, action, name: str) -> None:
        try:
            outcome = action(name)
        except Exception as e:
            logger.error(f"فشل إجراء الحارس على {name}: {e}")
            return
        if not outcome.applied:
            self.tray.show_message(
                t('guard.title'),
                t('guard.refused', name=name,
                  reason=t(f'guard.reason.{outcome.reason}')))

    # ══════════════════════════════════════════════════════
    # الخروج
    # ══════════════════════════════════════════════════════

    def _save(self) -> None:
        """حفظ دوري لبيانات التعلّم في الخلفية"""
        try:
            self.ai.save_learning_data()
            self.guard_service.save()
        except Exception as e:
            logger.error(f"تعذّر الحفظ التلقائي: {e}")

    def quit_application(self, interactive: bool = True) -> None:
        """
        إغلاق نظيف بلا واجهة: إفراج عن كل تدخّل، إيقاف الخيط، حفظ، ثم خروج.
        ترتيب الخطوات مهمّ: الإفراج قبل الخروج، والحفظ بعد توقّف الكتابة.

        `interactive` موجود لتطابق واجهة لوحة القياس فقط: هذا المسار بلا نافذة
        أصلاً، فلا فرق بين الحالتين هنا.
        """
        from PyQt6.QtWidgets import QApplication

        if self._quitting:
            return
        self._quitting = True
        logger.info("إيقاف وضع الخلفية...")

        self._autosave.stop()
        try:
            self.guard_service.shutdown()
        except Exception as e:
            logger.error(f"إيقاف الحارس: {e}")
        try:
            self.notification_manager.stop_all_reminders()
        except Exception as e:
            logger.debug(f"إيقاف التذكيرات: {e}")
        try:
            self.monitor_thread.stop(timeout_ms=4000)
        except Exception as e:
            logger.error(f"إيقاف خيط المراقبة: {e}")
        try:
            # `force`: الحفظ الدوري محدود بمهلة، والخروج آخر فرصة للكتابة
            self.ai.save_learning_data(force=True)
        except Exception as e:
            logger.error(f"حفظ بيانات التعلّم: {e}")
        try:
            self.tray.hide()
        except Exception as e:
            logger.debug(f"إخفاء الأيقونة: {e}")
        if self.window is not None:
            try:
                self.window._quitting = True
                self.window.close()
            except Exception as e:
                logger.debug(f"إغلاق النافذة: {e}")

        logger.info("تم الإغلاق النظيف")
        QApplication.quit()
