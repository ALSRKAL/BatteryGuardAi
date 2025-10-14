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

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batteryguard.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('BatteryGuard')

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
    
    # إنشاء النافذة الرئيسية
    window = ModernUI()
    
    # بدء الاستماع للإشارات من نسخ أخرى
    def show_window_callback():
        """إظهار النافذة عند استقبال إشارة"""
        window.show()
        window.activateWindow()
        window.raise_()
    
    instance.start_listening(callback=show_window_callback)
    
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
