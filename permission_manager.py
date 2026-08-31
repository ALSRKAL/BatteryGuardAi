#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مدير الصلاحيات - BatteryGuardAI

يُطلب رفع الصلاحيات لغرض واحد فقط: كتابة عتبات الشحن في
`/sys/class/power_supply/*/charge_control_*` حيث تكون محجوزة للجذر. كل ما
عدا ذلك (السطوع، أولوية القرص، القياس) يجري بصلاحيات المستخدم العادية، ولا
يجوز أن يطلب كلمة مرور.

النافذة السابقة كانت تُرسم بتدرّجات لونية وألوان مكتوبة داخل الملف ونصوص بلا
مفتاح ترجمة، وتطلب كلمة المرور بلا ذكر ما سيُفعل بها. أصبحت الآن من
`dialogs.PasswordDialog`: نفس عالم اللوحة، وسبب الطلب مكتوب في النافذة.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

import dialogs
from i18n import t

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

logger = logging.getLogger('BatteryGuard')

#: مهلة اختبار كلمة المرور (ثانية)
SUDO_TEST_TIMEOUT = 5


class PermissionManager:
    """
    يفحص الصلاحيات الحالية، ويطلب الرفع مرة واحدة عند الحاجة إليه فعلاً.
    """

    def __init__(self):
        self.has_admin_rights = False
        self.sudo_password = None
        #: يُطلب مرة واحدة لكل جلسة: نافذة كلمة مرور متكررة تدرّب المستخدم
        #: على إدخالها بلا تفكير، وذلك ضرر أمني لا إلحاح مفيد.
        self.permission_requested = False
        self._check_current_permissions()

    # ── الفحص ───────────────────────────────────────────────

    def _check_current_permissions(self) -> None:
        if IS_WINDOWS:
            try:
                import ctypes
                self.has_admin_rights = ctypes.windll.shell32.IsUserAnAdmin() != 0
                if self.has_admin_rights:
                    logger.info("يعمل بصلاحيات المسؤول (Windows)")
            except Exception:
                self.has_admin_rights = False
            return

        if not IS_LINUX:
            return

        if os.environ.get('BATTERYGUARD_SUDO_VERIFIED') == '1':
            self.has_admin_rights = True
            logger.info("صلاحيات sudo محفوظة في الجلسة")
            return

        # الفحص بإعادة كتابة القيمة نفسها: يثبت إمكانية الكتابة بلا تغيير حدّ
        threshold = Path('/sys/class/power_supply/BAT0/'
                         'charge_control_end_threshold')
        if not threshold.exists():
            return
        try:
            current = threshold.read_text().strip()
            threshold.write_text(current)
            self.has_admin_rights = True
            logger.info("صلاحيات كتابة عتبات الشحن متاحة مباشرة")
        except (PermissionError, OSError):
            self.has_admin_rights = False

    # ── الطلب ───────────────────────────────────────────────

    def request_permissions(self, parent_widget=None) -> bool:
        """طلب الصلاحيات مرة واحدة لكل جلسة"""
        if self.permission_requested:
            return self.has_admin_rights
        self.permission_requested = True

        if self.has_admin_rights:
            return True
        if IS_WINDOWS:
            return self._request_windows_admin(parent_widget)
        if IS_LINUX:
            return self._request_linux_sudo(parent_widget)
        return False

    def _request_windows_admin(self, parent_widget) -> bool:
        """إعادة التشغيل كمسؤول بعد تأكيد صريح"""
        if not dialogs.confirm(parent_widget, t('perm.title'),
                               t('perm.windows_admin'),
                               detail=t('perm.reason_charge')):
            return False
        try:
            import ctypes
            script = os.path.abspath(sys.argv[0])
            params = ' '.join(sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1)
            sys.exit(0)
        except Exception as e:
            logger.error(f"فشل طلب صلاحيات المسؤول: {e}")
            dialogs.error(parent_widget, t('dialog.error_title'),
                          t('perm.windows_failed'))
            return False

    def _request_linux_sudo(self, parent_widget) -> bool:
        """طلب كلمة مرور sudo مع ذكر سبب الطلب في النافذة نفسها"""
        password = dialogs.ask_password(parent_widget, t('perm.reason_charge'))
        if not password:
            self.permission_requested = False
            return False

        if not self._test_sudo_password(password):
            dialogs.error(parent_widget, t('dialog.error_title'), t('perm.denied'))
            self.permission_requested = False
            return False

        self.sudo_password = password
        self.has_admin_rights = True
        os.environ['BATTERYGUARD_SUDO_VERIFIED'] = '1'
        logger.info("تم الحصول على صلاحيات sudo")
        return True

    @staticmethod
    def _test_sudo_password(password: str) -> bool:
        """
        اختبار كلمة المرور بأمر لا أثر له (`echo`).

        `SUDO_ASKPASS=/bin/false` يمنع sudo من فتح نافذة رسومية خاصة به،
        و`-p ''` يخفي مطالبته النصية: بلاهما يتعلّق الاختبار في انتظار مدخل
        لا أحد يراه.
        """
        try:
            process = subprocess.Popen(
                ['sudo', '-S', '-p', '', 'echo', 'ok'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                env={**os.environ, 'SUDO_ASKPASS': '/bin/false'})
            _, stderr = process.communicate(input=f"{password}\n",
                                            timeout=SUDO_TEST_TIMEOUT)
            if process.returncode != 0:
                logger.debug(f"فشل اختبار sudo: {stderr.strip()[:120]}")
            return process.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("انتهت مهلة اختبار sudo")
            return False
        except Exception as e:
            logger.error(f"خطأ في اختبار sudo: {e}")
            return False

    def get_sudo_password(self):
        return self.sudo_password
