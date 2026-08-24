#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إعادة تعيين الإعدادات إلى القيم الافتراضية
"""

import sys
import json
from pathlib import Path


def reset_settings():
    """إعادة تعيين الإعدادات"""
    print("\n" + "=" * 70)
    print("  🔄 إعادة تعيين الإعدادات إلى القيم الافتراضية")
    print("=" * 70)
    
    try:
        from resource_path import get_data_path
        from default_settings import get_default_settings
        
        settings_file = get_data_path('battery_settings.json')
        
        # حذف الملف القديم إذا كان موجوداً
        if settings_file.exists():
            print(f"\n📁 ملف الإعدادات الحالي: {settings_file}")
            
            # قراءة الإعدادات القديمة
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    old_settings = json.load(f)
                
                print("\n📋 الإعدادات الحالية:")
                print(f"  • autostart_enabled: {old_settings.get('autostart_enabled', 'غير موجود')}")
                print(f"  • start_in_background: {old_settings.get('start_in_background', 'غير موجود')}")
                print(f"  • charge_control_enabled: {old_settings.get('charge_control_enabled', 'غير موجود')}")
                print(f"  • auto_optimization_enabled: {old_settings.get('auto_optimization_enabled', 'غير موجود')}")
                print(f"  • minimize_to_tray: {old_settings.get('minimize_to_tray', 'غير موجود')}")
                print(f"  • notifications_enabled: {old_settings.get('notifications_enabled', 'غير موجود')}")
                print(f"  • sounds_enabled: {old_settings.get('sounds_enabled', 'غير موجود')}")
            except Exception as e:
                print(f"⚠️ خطأ في قراءة الإعدادات القديمة: {e}")
            
            # حذف الملف
            settings_file.unlink()
            print("\n🗑️  تم حذف الملف القديم")
        else:
            print(f"\n✅ لا يوجد ملف إعدادات (تشغيل أول)")
        
        # إنشاء الإعدادات الافتراضية
        print("\n📝 إنشاء الإعدادات الافتراضية...")
        
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        
        default_settings = get_default_settings()
        
        # التأكد من القيم الصحيحة
        default_settings['autostart_enabled'] = False
        default_settings['start_in_background'] = False
        default_settings['charge_control_enabled'] = False
        default_settings['auto_optimization_enabled'] = False
        default_settings['minimize_to_tray'] = False
        default_settings['show_welcome_dialog'] = True
        
        # حفظ الإعدادات
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=2, ensure_ascii=False)
        
        print(f"✅ تم حفظ الإعدادات في: {settings_file}")
        
        # عرض الإعدادات الجديدة
        print("\n📋 الإعدادات الافتراضية الجديدة:")
        print("\n✅ مفعّل افتراضياً:")
        for key, value in default_settings.items():
            if value is True:
                print(f"  • {key}")
        
        print("\n❌ معطّل افتراضياً:")
        for key, value in default_settings.items():
            if value is False:
                print(f"  • {key}")
        
        print("\n" + "=" * 70)
        print("  ✅ تم إعادة التعيين بنجاح!")
        print("=" * 70)
        print("\n💡 الآن يمكنك تشغيل التطبيق:")
        print("   python3 main.py")
        print("\n   سيظهر شاشة الترحيب وجميع الإعدادات ستكون كما هو معروض")
        print("=" * 70)
        
        return True
    
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_current_settings():
    """عرض الإعدادات الحالية"""
    print("\n" + "=" * 70)
    print("  📊 الإعدادات الحالية")
    print("=" * 70)
    
    try:
        from resource_path import get_data_path
        
        settings_file = get_data_path('battery_settings.json')
        
        if not settings_file.exists():
            print("\n⚠️ لا يوجد ملف إعدادات")
            print("💡 قم بتشغيل التطبيق أولاً أو استخدم: reset")
            return False
        
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        print(f"\n📁 الملف: {settings_file}")
        print(f"\n📊 عدد الإعدادات: {len(settings)}")
        
        print("\n✅ مفعّل:")
        for key, value in sorted(settings.items()):
            if value is True:
                print(f"  • {key}")
        
        print("\n❌ معطّل:")
        for key, value in sorted(settings.items()):
            if value is False:
                print(f"  • {key}")
        
        print("\n🔢 قيم أخرى:")
        for key, value in sorted(settings.items()):
            if value is not True and value is not False:
                print(f"  • {key}: {value}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        return False


def compare_with_defaults():
    """مقارنة الإعدادات الحالية مع الافتراضية"""
    print("\n" + "=" * 70)
    print("  🔍 مقارنة الإعدادات الحالية مع الافتراضية")
    print("=" * 70)
    
    try:
        from resource_path import get_data_path
        from default_settings import get_default_settings
        
        settings_file = get_data_path('battery_settings.json')
        
        if not settings_file.exists():
            print("\n⚠️ لا يوجد ملف إعدادات")
            return False
        
        with open(settings_file, 'r', encoding='utf-8') as f:
            current_settings = json.load(f)
        
        default_settings = get_default_settings()
        
        print("\n📊 المقارنة:")
        
        differences = []
        
        for key in default_settings:
            current_value = current_settings.get(key, 'غير موجود')
            default_value = default_settings[key]
            
            if current_value != default_value:
                differences.append({
                    'key': key,
                    'current': current_value,
                    'default': default_value
                })
        
        if differences:
            print(f"\n⚠️ وجدت {len(differences)} اختلاف:")
            for diff in differences:
                print(f"\n  • {diff['key']}:")
                print(f"    الحالي: {diff['current']}")
                print(f"    الافتراضي: {diff['default']}")
        else:
            print("\n✅ جميع الإعدادات تطابق القيم الافتراضية")
        
        return True
    
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        return False


def main():
    """الدالة الرئيسية"""
    print("\n" + "=" * 70)
    print("  ⚙️ إدارة الإعدادات - BatteryGuard Pro")
    print("=" * 70)
    print("\nالخيارات:")
    print("  1. إعادة تعيين إلى القيم الافتراضية")
    print("  2. عرض الإعدادات الحالية")
    print("  3. مقارنة مع الافتراضية")
    print("  4. الخروج")
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("\nاختر (1-4): ").strip()
    
    if choice == '1' or choice.lower() == 'reset':
        reset_settings()
    elif choice == '2' or choice.lower() == 'show':
        show_current_settings()
    elif choice == '3' or choice.lower() == 'compare':
        compare_with_defaults()
    elif choice == '4' or choice.lower() == 'exit':
        print("\n👋 إلى اللقاء!")
    else:
        print("\n❌ خيار غير صحيح!")
        print("\nالاستخدام:")
        print("  python3 reset_to_defaults.py reset    # إعادة تعيين")
        print("  python3 reset_to_defaults.py show     # عرض الحالية")
        print("  python3 reset_to_defaults.py compare  # مقارنة")


if __name__ == '__main__':
    main()
