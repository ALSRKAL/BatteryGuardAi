#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BatteryGuardAI - نقطة الدخول

ثلاثة أوضاع تشغيل:

    python main.py              لوحة القياس كاملة
    python main.py --background أيقونة صينية فقط، بلا نافذة حتى تطلبها
    python main.py --window     لوحة القياس مبنيّة ومخفيّة (توافق مع القديم)

وضع `--background` هو الذي تستخدمه خدمة systemd: لا نافذة تُبنى إطلاقاً، بل
متحكّم خفيف يملك القياس والاستدلال والحماية والأيقونة، ويبني لوحة القياس عند
أول نقرة إظهار فقط. هذا ما يجعل التشغيل الدائم في الخلفية رخيصاً فعلاً.
"""

import json
import logging
import logging.handlers
import sys

from PyQt6.QtWidgets import QApplication

# استيراد مدير المسارات
try:
    from resource_path import get_log_path, ensure_data_files, is_frozen
    log_file = get_log_path()
    # التأكد من وجود ملفات البيانات
    ensure_data_files()
except ImportError:
    from pathlib import Path
    log_file = Path('batteryguard.log')

    def is_frozen():
        return False

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

#: سقف حجم ملف السجل وعدد النسخ المحفوظة.
#: تطبيق يعمل في الخلفية دائماً يكتب سجلاً بلا نهاية: بلا تدوير يبلغ الملف
#: مئات الميغابايتات ويملأ قرص المستخدم. السقف هنا هو الإعداد `max_log_size`
#: نفسه المعلن في `default_settings`، وصار مُنفَّذاً لا مجرّد رقم مكتوب.
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 3


def _configure_logging() -> None:
    """
    سجل مُدوَّر بحجم محدود، مع مخرَج إلى الطرفية أو إلى journal.

    `delay=True` يؤجّل فتح الملف حتى أول كتابة، فلا يُنشئ ملفاً فارغاً حين
    يخرج التطبيق فوراً (مثل نسخة ثانية تجد نسخة تعمل).
    """
    handlers = [logging.StreamHandler()]
    try:
        handlers.insert(0, logging.handlers.RotatingFileHandler(
            log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8', delay=True))
    except OSError as e:
        print(f"تحذير: تعذّر فتح ملف السجل ({e}) - سيُكتب إلى الطرفية فقط")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers)


_configure_logging()
logger = logging.getLogger('BatteryGuard')

logger.info(f"بدء BatteryGuardAI - وضع: {'مبني' if is_frozen() else 'تطوير'}")
logger.info(f"ملف السجل: {log_file} (سقف "
            f"{LOG_MAX_BYTES // (1024 * 1024)} ميغابايت × {LOG_BACKUP_COUNT + 1})")

from PyQt6.QtCore import QObject, Qt, pyqtSignal

from default_settings import (APP_NAME, APP_ORG, APP_VERSION,
                              get_default_settings)
from i18n import is_rtl, set_language
from lifecycle import install_shutdown_handler
from single_instance import SingleInstance


class _ShowRequestBridge(QObject):
    """
    ناقل إشارة الإظهار من خيط الاستماع إلى الخيط الرئيسي.

    خيط الاستماع لا يجوز أن يلمس الواجهة، وإشارات Qt هي الطريق الآمن الوحيد
    لعبور حدود الخيوط هنا.
    """
    show_requested = pyqtSignal()


def _saved_language() -> str:
    """
    اللغة المحفوظة في إعدادات المستخدم، وإلا الافتراضية.
    تُقرأ قبل بناء الواجهة لأن اتجاه التخطيط يُضبط مرة واحدة على التطبيق.
    """
    try:
        from resource_path import get_data_path
        settings_file = get_data_path('battery_settings.json')
        if settings_file.exists():
            with open(settings_file, 'r', encoding='utf-8') as handle:
                return str(json.load(handle).get('language', 'ar'))
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.debug(f"تعذّرت قراءة اللغة المحفوظة: {e}")
    return get_default_settings().get('language', 'ar')


def _parse_mode(argv) -> str:
    """
    وضع التشغيل من سطر الأوامر: `background` أو `window` أو `full`.

    `--minimized` يبقى مقبولاً لأن ملفات التشغيل التلقائي القديمة تستخدمه،
    ويُعامل معاملة `--background` لأن ذلك ما كان يقصده المستخدم منه.
    """
    flags = set(argv[1:])
    if {'--background', '--service', '--minimized', '--tray'} & flags:
        return 'background'
    if '--window' in flags:
        return 'window'
    return 'full'


def _first_run_state() -> bool:
    """
    هل هذا تشغيل أول يستحق نافذة ترحيب؟ يكتب الإعدادات الافتراضية عند الحاجة.
    """
    try:
        from resource_path import get_data_path

        settings_file = get_data_path('battery_settings.json')
        if not settings_file.exists():
            logger.info("التشغيل الأول - تطبيق الإعدادات الافتراضية")
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            defaults = get_default_settings()
            defaults['show_welcome_dialog'] = True
            with open(settings_file, 'w', encoding='utf-8') as handle:
                json.dump(defaults, handle, indent=2, ensure_ascii=False)
            return True

        with open(settings_file, 'r', encoding='utf-8') as handle:
            return bool(json.load(handle).get('show_welcome_dialog', True))
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.warning(f"تعذّرت قراءة حالة التشغيل الأول: {e}")
        return False


def _show_welcome(window) -> None:
    """نافذة الترحيب مرة واحدة، وحفظ رغبة المستخدم بعدم تكرارها"""
    try:
        from resource_path import get_data_path
        from welcome_dialog import WelcomeDialog

        welcome = WelcomeDialog(window)
        welcome.exec()
        if welcome.should_show_again():
            return

        settings_file = get_data_path('battery_settings.json')
        with open(settings_file, 'r', encoding='utf-8') as handle:
            settings = json.load(handle)
        settings['show_welcome_dialog'] = False
        with open(settings_file, 'w', encoding='utf-8') as handle:
            json.dump(settings, handle, indent=2, ensure_ascii=False)
        logger.info("تم حفظ خيار عدم إظهار الترحيب")
    except Exception as e:
        logger.error(f"خطأ في نافذة الترحيب: {e}")


def main():
    """نقطة الدخول الرئيسية"""
    if not (IS_WINDOWS or IS_LINUX):
        logger.error("هذا البرنامج يدعم Windows و Linux فقط")
        return 1

    mode = _parse_mode(sys.argv)

    # نسخة واحدة فقط: النسخة الثانية تطلب إظهار الأولى ثم تخرج
    instance = SingleInstance('BatteryGuardPro')
    if instance.is_already_running():
        logger.warning("BatteryGuardAI يعمل بالفعل")
        shown = instance.show_existing_instance()
        print("\n" + "=" * 60)
        print("BatteryGuardAI يعمل بالفعل.")
        print("تم إظهار النافذة الموجودة." if shown
              else "تحقق من أيقونة شريط المهام.")
        print("=" * 60 + "\n")
        return 0

    logger.info(f"بدء التشغيل - الوضع: {mode}")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setApplicationVersion(APP_VERSION)

    # اللغة واتجاه القراءة قبل بناء أي واجهة
    language = set_language(_saved_language())
    if is_rtl(language):
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    logger.info(f"لغة الواجهة: {language}")

    # إغلاق آخر نافذة لا يُنهي التطبيق: الأيقونة تبقى والمراقبة تستمر
    app.setQuitOnLastWindowClosed(False)

    bridge = _ShowRequestBridge()
    instance.on_show_request = bridge.show_requested.emit

    if mode == 'background':
        controller = _start_background(app, bridge)
        if controller is None:
            instance.release()
            return 1
    else:
        controller = _start_window(app, bridge, hidden=(mode == 'window'))

    # الإغلاق النظيف عند SIGTERM: هذا ما ترسله systemd وتسجيل الخروج وإعادة
    # التشغيل. بلا هذا المعالِج يموت التطبيق فوراً فتبقى أي عملية علّقها
    # الحارس معلّقة، ويُفقد كل ما تعلّمه بعد آخر حفظ.
    # `interactive=False`: لا نافذة تقدّم أثناء إغلاق الجلسة، فلا أحد يراها
    # ورسمها قد يتعلّق حتى تنتهي مهلة systemd فتُقتل العملية قبل التنظيف.
    # يُحتفظ بالمرجع: جامع النفايات يُبطل مراقب المقبس بلا أي رسالة.
    shutdown = install_shutdown_handler(
        lambda: controller.quit_application(interactive=False))

    instance.start_listening()
    exit_code = app.exec()
    shutdown.uninstall()
    instance.release()
    logger.info(f"انتهى التطبيق برمز {exit_code}")
    return exit_code


def _start_background(app, bridge):
    """
    وضع الخلفية: متحكّم خفيف وأيقونة، بلا نافذة.

    إن لم تتوفّر صينية النظام لا نخرج: التطبيق يواصل القياس والحماية والإشعار،
    ويُسجّل أن الأيقونة غائبة. الخروج هنا كان سيُفقد المستخدم الحماية كلها
    بسبب أيقونة.
    """
    from service_runner import BackgroundController
    from settings_bridge import effective_settings

    try:
        controller = BackgroundController(settings_provider=effective_settings)
    except Exception as e:
        logger.critical(f"تعذّر بدء وضع الخلفية: {e}", exc_info=True)
        return None

    bridge.show_requested.connect(controller.show_window)
    logger.info("يعمل في الخلفية. انقر أيقونة شريط المهام لإظهار اللوحة.")
    return controller


def _start_window(app, bridge, hidden: bool):
    """وضع النافذة: لوحة القياس كاملة، ظاهرة أو مخفيّة"""
    from main_window import ModernUI

    show_welcome = _first_run_state()
    window = ModernUI()
    bridge.show_requested.connect(
        lambda: (window.show(), window.activateWindow(), window.raise_()))

    if show_welcome and not hidden:
        _show_welcome(window)

    if hidden:
        logger.info("اللوحة مبنيّة ومخفيّة - انقر أيقونة شريط المهام لإظهارها")
    else:
        window.show()
        logger.info("تم تشغيل BatteryGuardAI بنجاح")
    return window


if __name__ == "__main__":
    sys.exit(main())
