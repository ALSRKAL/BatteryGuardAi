#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BatteryGuard Pro - نظام إدارة بطارية احترافي مع ذكاء اصطناعي
نظام متقدم لتحسين عمر البطارية وإدارتها بذكاء عبر المنصات
"""

import sys
import logging
import json
from PyQt6.QtWidgets import QApplication, QMessageBox

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

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('BatteryGuard')

# تسجيل معلومات التشغيل
logger.info(f"🚀 بدء BatteryGuard Pro - وضع: {'مبني' if is_frozen() else 'تطوير'}")
logger.info(f"📝 ملف السجل: {log_file}")

from main_window import ModernUI
from single_instance import SingleInstance


def main():
    """نقطة الدخول الرئيسية"""
    
    # التحقق من نسخة واحدة فقط
    instance = SingleInstance('BatteryGuardPro')
    
    if instance.is_already_running():
        logger.warning("⚠️ BatteryGuard Pro يعمل بالفعل!")
        
        # محاولة إظهار النافذة الموجودة
        if instance.show_existing_instance():
            logger.info("✅ تم إرسال إشارة لإظهار النافذة الموجودة")
            print("\n" + "="*60)
            print("⚠️  BatteryGuard Pro يعمل بالفعل!")
            print("✅ تم إظهار النافذة الموجودة")
            print("💡 تحقق من أيقونة شريط المهام")
            print("="*60 + "\n")
        else:
            print("\n" + "="*60)
            print("⚠️  BatteryGuard Pro يعمل بالفعل!")
            print("💡 تحقق من أيقونة شريط المهام")
            print("="*60 + "\n")
        
        sys.exit(0)
    
    logger.info("🚀 بدء تشغيل BatteryGuard Pro...")
    
    # التحقق من وضع الخلفية
    background_mode = '--background' in sys.argv or '--minimized' in sys.argv
    
    app = QApplication(sys.argv)
    app.setApplicationName("BatteryGuard Pro")
    app.setOrganizationName("BatteryGuard")
    app.setApplicationVersion("2.0")
    
    # منع إغلاق التطبيق عند إغلاق آخر نافذة (للعمل في الخلفية)
    app.setQuitOnLastWindowClosed(False)
    
    if not (IS_WINDOWS or IS_LINUX):
        logger.error("هذا البرنامج يدعم Windows و Linux فقط")
        sys.exit(1)
    
    # التحقق من التشغيل الأول وتطبيق الإعدادات الافتراضية
    is_first_run = False
    show_welcome = False
    
    try:
        from resource_path import get_data_path
        from default_settings import get_default_settings
        import json
        
        settings_file = get_data_path('battery_settings.json')
        
        # التحقق من التشغيل الأول
        if not settings_file.exists():
            is_first_run = True
            show_welcome = True
            logger.info("🎉 التشغيل الأول - تطبيق الإعدادات الافتراضية")
            
            # إنشاء مجلد البيانات إذا لم يكن موجوداً
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            # حفظ الإعدادات الافتراضية
            default_settings = get_default_settings()
            # تأكد من أن show_welcome_dialog = True في التشغيل الأول
            default_settings['show_welcome_dialog'] = True
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=2, ensure_ascii=False)
            
            logger.info("✅ تم حفظ الإعدادات الافتراضية")
        else:
            # قراءة الإعدادات الموجودة
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    # إذا لم يكن الخيار موجود، اعتبره True (للتوافق مع الإصدارات القديمة)
                    show_welcome = settings.get('show_welcome_dialog', True)
                    logger.info(f"📖 تم قراءة الإعدادات الموجودة - show_welcome={show_welcome}")
            except Exception as e:
                logger.warning(f"⚠️ خطأ في قراءة الإعدادات: {e}")
                show_welcome = False
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من التشغيل الأول: {e}")
        import traceback
        logger.error(traceback.format_exc())
        is_first_run = False
        show_welcome = False
    
    # إنشاء النافذة الرئيسية
    window = ModernUI()
    
    # بدء الاستماع للإشارات من نسخ أخرى
    # مهم: خيط الاستماع لا يستطيع لمس الواجهة مباشرة، لذا نستخدم
    # إشارة Qt (آمنة عبر الخيوط) لتنفيذ الإظهار على الخيط الرئيسي.
    from PyQt6.QtCore import QObject, pyqtSignal
    
    class _ShowRequestBridge(QObject):
        show_requested = pyqtSignal()
    
    bridge = _ShowRequestBridge()
    instance.on_show_request = bridge.show_requested.emit
    bridge.show_requested.connect(
        lambda: (window.show(), window.activateWindow(), window.raise_())
    )
    
    instance.start_listening()
    
    # إظهار نافذة الترحيب في التشغيل الأول
    if show_welcome and not background_mode:
        try:
            from welcome_dialog import WelcomeDialog
            import json
            
            logger.info("📋 عرض نافذة الترحيب...")
            
            welcome = WelcomeDialog(window)
            result = welcome.exec()
            
            logger.info(f"✅ نافذة الترحيب: نتيجة={result}")
            
            # حفظ خيار عدم الإظهار مرة أخرى
            if not welcome.should_show_again():
                try:
                    settings_file = get_data_path('battery_settings.json')
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                    settings['show_welcome_dialog'] = False
                    with open(settings_file, 'w', encoding='utf-8') as f:
                        json.dump(settings, f, indent=2, ensure_ascii=False)
                    logger.info("✅ تم حفظ خيار عدم إظهار الترحيب")
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في حفظ خيار الترحيب: {e}")
            
            # إذا اختار المستخدم فتح الإعدادات
            if result == 2:
                logger.info("📋 المستخدم اختار فتح الإعدادات")
                # يمكن إضافة كود لفتح نافذة الإعدادات هنا
        except Exception as e:
            logger.error(f"❌ خطأ في عرض نافذة الترحيب: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # إذا كان في وضع الخلفية، لا تظهر النافذة
    if not background_mode:
        window.show()
        logger.info("✅ تم تشغيل BatteryGuard Pro بنجاح")
    else:
        logger.info("🔄 BatteryGuard Pro يعمل في وضع الخلفية")
        logger.info("💡 انقر على أيقونة شريط المهام لإظهار النافذة")
    
    # تشغيل التطبيق
    exit_code = app.exec()
    
    # تحرير القفل عند الخروج
    instance.release()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
