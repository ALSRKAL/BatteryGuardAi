#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مدير التشغيل التلقائي"""

import logging
import sys
from pathlib import Path
from typing import Tuple

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')
logger = logging.getLogger('BatteryGuard')


class AutostartManager:
    """
    مفتاح «ابدأ مع النظام» في الإعدادات.

    غلاف رفيع فوق `service_installer`: هو من يعرف أي طريقة تصلح على هذا
    الجهاز (خدمة مستخدم أم ملف تشغيل تلقائي)، وهذه الطبقة لا تكرّر قراره.
    الطريقة القديمة (كتابة `.desktop` مباشرة) كانت تُعيد التشغيل بعد الإقلاع
    ولا تُعيده إن توقّف التطبيق، والخدمة تفعل الاثنين.
    """

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.executable_path = Path(sys.executable)
            self.is_frozen = True
        else:
            self.current_dir = Path(__file__).parent.absolute()
            self.python_path = sys.executable
            self.main_script = self.current_dir / "main.py"
            self.is_frozen = False

        self.method = 'task_scheduler' if IS_WINDOWS else 'autostart'

    # ── الحالة ──────────────────────────────────────────────

    def status(self):
        """الحالة الكاملة من المثبّت (طريقة، تفعيل، تشغيل، linger)"""
        import service_installer
        return service_installer.status()

    def is_enabled(self) -> bool:
        """هل يبدأ التطبيق تلقائياً بأي طريقة متاحة"""
        try:
            state = self.status()
            return bool(state.installed and state.enabled)
        except Exception as e:
            logger.debug(f"تعذّرت قراءة حالة التشغيل التلقائي: {e}")
            return False

    def active_method(self) -> str:
        """أي طريقة مستخدمة فعلاً الآن"""
        try:
            return self.status().method
        except Exception:
            return 'none'

    # ── التبديل ─────────────────────────────────────────────

    def enable(self) -> Tuple[bool, str]:
        """تفعيل التشغيل الدائم بأفضل طريقة متوفّرة"""
        try:
            import service_installer
            result = service_installer.install(start_now=False)
            if not result.success:
                return False, result.error or "فشل التثبيت"
            message = "تم التفعيل بنجاح"
            if result.method == service_installer.METHOD_SYSTEMD:
                message += " (خدمة مستخدم: تبقى بعد إغلاق الطرفية وتعود بعد الإقلاع)"
            else:
                message += " (تشغيل تلقائي للجلسة)"
            if result.follow_up:
                message += " · " + result.follow_up[0]
            return True, message
        except Exception as e:
            logger.error(f"تعذّر تفعيل التشغيل التلقائي: {e}")
            return False, str(e)

    def disable(self) -> Tuple[bool, str]:
        """إزالة كل صور التشغيل الدائم"""
        try:
            import service_installer
            result = service_installer.uninstall()
            if not result.success:
                return False, result.error or "فشل الإلغاء"
            return True, "تم الإلغاء بنجاح"
        except Exception as e:
            logger.error(f"تعذّر إلغاء التشغيل التلقائي: {e}")
            return False, str(e)


autostart_manager = AutostartManager()
