#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مدير المسارات للتطبيق - يعمل في وضع التطوير والبناء
"""

import sys
import os
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """
    الحصول على المسار الصحيح للملف سواء في وضع التطوير أو البناء
    
    Args:
        relative_path: المسار النسبي للملف (مثل: 'sounds/alert.mp3')
    
    Returns:
        Path: المسار الكامل للملف
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Running in normal Python environment
        base_path = Path(__file__).parent.absolute()
    
    resource = base_path / relative_path
    
    # إذا لم يوجد الملف في المسار المبني، جرب المسار الأصلي
    if not resource.exists():
        original_path = Path(__file__).parent.absolute() / relative_path
        if original_path.exists():
            return original_path
    
    return resource


def get_data_path(filename: str) -> Path:
    """
    الحصول على مسار ملف البيانات (JSON, LOG, etc.)
    يحفظ في مجلد المستخدم للبيانات الدائمة
    
    Args:
        filename: اسم الملف
    
    Returns:
        Path: المسار الكامل للملف
    """
    # استخدام مجلد المستخدم للبيانات
    if sys.platform == 'win32':
        data_dir = Path(os.environ.get('APPDATA', Path.home())) / 'BatteryGuardPro'
    else:
        data_dir = Path.home() / '.config' / 'batteryguard'
    
    # إنشاء المجلد إذا لم يكن موجوداً
    data_dir.mkdir(parents=True, exist_ok=True)
    
    return data_dir / filename


def ensure_data_files():
    """
    التأكد من وجود ملفات البيانات الأساسية
    ينسخها من الموارد إذا لم تكن موجودة
    """
    default_files = [
        'battery_settings.json',
        'battery_ai_data.json',
        'auto_optimizer_settings.json'
    ]
    
    for filename in default_files:
        data_file = get_data_path(filename)
        
        # إذا لم يكن الملف موجوداً، انسخه من الموارد
        if not data_file.exists():
            resource_file = get_resource_path(filename)
            if resource_file.exists():
                import shutil
                shutil.copy2(resource_file, data_file)


def get_log_path() -> Path:
    """
    الحصول على مسار ملف السجل
    
    Returns:
        Path: المسار الكامل لملف السجل
    """
    return get_data_path('batteryguard.log')


def is_frozen() -> bool:
    """
    التحقق من أن التطبيق يعمل كملف مبني (frozen)
    
    Returns:
        bool: True إذا كان التطبيق مبني
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


# اختبار سريع
if __name__ == '__main__':
    print("🔍 اختبار مدير المسارات")
    print(f"وضع التشغيل: {'مبني (Frozen)' if is_frozen() else 'تطوير (Development)'}")
    print(f"\nمسار الموارد: {get_resource_path('.')}")
    print(f"مسار البيانات: {get_data_path('test.json')}")
    print(f"مسار السجل: {get_log_path()}")
    
    # اختبار الأصوات
    print("\n🔊 اختبار ملفات الأصوات:")
    sounds = [
        'sounds/new-notification-010-352755.mp3',
        'sounds/new-notification-05-352453.mp3',
        'sounds/new-notification-021-370045.mp3',
        'sounds/new-notification-022-370046.mp3',
        'sounds/new-notification-024-370048.mp3'
    ]
    
    for sound in sounds:
        path = get_resource_path(sound)
        status = "✅" if path.exists() else "❌"
        print(f"{status} {sound}: {path}")
