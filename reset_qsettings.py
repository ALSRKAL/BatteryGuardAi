#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إعادة تعيين QSettings إلى القيم الافتراضية
"""

import sys
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication


def show_current_qsettings():
    """عرض إعدادات QSettings الحالية"""
    print("\n" + "=" * 70)
    print("  📊 إعدادات QSettings الحالية")
    print("=" * 70)
    
    app = QApplication(sys.argv)
    settings = QSettings('BatteryGuard', 'Pro')
    
    print(f"\n📁 الموقع: {settings.fileName()}")
    print(f"📊 عدد الإعدادات: {len(settings.allKeys())}")
    
    if len(settings.allKeys()) == 0:
        print("\n⚠️ لا توجد إعدادات محفوظة")
        return
    
    print("\n📋 جميع الإعدادات:")
    for key in sorted(settings.allKeys()):
        value = settings.value(key)
        print(f"  • {key}: {value}")


def reset_qsettings():
    """إعادة تعيين QSettings إلى القيم الافتراضية"""
    print("\n" + "=" * 70)
    print("  🔄 إعادة تعيين QSettings إلى القيم الافتراضية")
    print("=" * 70)
    
    app = QApplication(sys.argv)
    settings = QSettings('BatteryGuard', 'Pro')
    
    print(f"\n📁 الموقع: {settings.fileName()}")
    
    # عرض الإعدادات القديمة
    old_keys = settings.allKeys()
    if old_keys:
        print(f"\n🗑️  حذف {len(old_keys)} إعداد قديم...")
        settings.clear()
        print("✅ تم حذف جميع الإعدادات القديمة")
    else:
        print("\n✅ لا توجد إعدادات قديمة")
    
    # تعيين القيم الافتراضية الصحيحة
    print("\n📝 تعيين القيم الافتراضية...")
    
    # ═══════════════════════════════════════════════════════════
    # الإعدادات العامة
    # ═══════════════════════════════════════════════════════════
    
    # ❌ معطّل افتراضياً
    settings.setValue('minimize_to_tray', False)
    settings.setValue('show_battery_in_tray', True)
    settings.setValue('start_on_boot', False)
    
    # ═══════════════════════════════════════════════════════════
    # إعدادات الإشعارات
    # ═══════════════════════════════════════════════════════════
    
    # ✅ مفعّل افتراضياً
    settings.setValue('enable_notifications', True)
    settings.setValue('enable_sounds', True)
    settings.setValue('enable_reminders', True)
    
    # حدود البطارية
    settings.setValue('low_battery_threshold', 20)
    settings.setValue('critical_battery_threshold', 10)
    settings.setValue('charge_threshold', 40)
    settings.setValue('unplug_threshold', 80)
    settings.setValue('optimal_min_threshold', 40)
    settings.setValue('optimal_max_threshold', 80)
    settings.setValue('high_battery_threshold', 90)
    settings.setValue('full_battery_threshold', 95)
    
    # ═══════════════════════════════════════════════════════════
    # التنبيهات الذكية
    # ═══════════════════════════════════════════════════════════
    
    # ✅ مفعّل افتراضياً
    settings.setValue('charger_disconnect_reminder', True)
    settings.setValue('optimal_charge_reminder', True)
    settings.setValue('health_warnings', True)
    settings.setValue('usage_pattern_alerts', True)
    settings.setValue('temperature_warnings', True)
    settings.setValue('ai_recommendations', True)
    
    # ═══════════════════════════════════════════════════════════
    # فترات التذكير (بالدقائق)
    # ═══════════════════════════════════════════════════════════
    
    settings.setValue('battery_critical_interval', 1)   # دقيقة
    settings.setValue('battery_low_interval', 5)        # 5 دقائق
    settings.setValue('charge_complete_interval', 10)   # 10 دقائق
    settings.setValue('unplug_charger_interval', 5)     # 5 دقائق
    
    # ═══════════════════════════════════════════════════════════
    # التحكم في الشحن
    # ═══════════════════════════════════════════════════════════
    
    # ❌ معطّل افتراضياً
    settings.setValue('auto_charge_control', False)
    settings.setValue('max_charge_limit', 80)
    settings.setValue('min_charge_limit', 40)
    
    # ═══════════════════════════════════════════════════════════
    # التحسين التلقائي
    # ═══════════════════════════════════════════════════════════
    
    # ❌ معطّل افتراضياً
    settings.setValue('auto_optimization_enabled', False)
    settings.setValue('auto_optimization_mode', 'on_demand')
    settings.setValue('auto_optimization_interval', 5)
    settings.setValue('opt_cpu_threshold', 70)
    settings.setValue('opt_memory_threshold', 75)
    
    # حفظ التغييرات
    settings.sync()
    
    print("✅ تم تعيين جميع القيم الافتراضية")
    
    # عرض الإعدادات الجديدة
    print("\n📋 الإعدادات الجديدة:")
    
    print("\n✅ مفعّل افتراضياً:")
    enabled_settings = [
        'enable_notifications',
        'enable_sounds',
        'enable_reminders',
        'show_battery_in_tray',
        'charger_disconnect_reminder',
        'optimal_charge_reminder',
        'health_warnings',
        'usage_pattern_alerts',
        'temperature_warnings',
        'ai_recommendations'
    ]
    for key in enabled_settings:
        value = settings.value(key, type=bool)
        print(f"  • {key}: {value}")
    
    print("\n❌ معطّل افتراضياً:")
    disabled_settings = [
        'minimize_to_tray',
        'start_on_boot',
        'auto_charge_control',
        'auto_optimization_enabled'
    ]
    for key in disabled_settings:
        value = settings.value(key, type=bool)
        print(f"  • {key}: {value}")
    
    print("\n" + "=" * 70)
    print("  ✅ تم إعادة التعيين بنجاح!")
    print("=" * 70)
    print("\n💡 الآن يمكنك تشغيل التطبيق:")
    print("   python3 main.py")
    print("\n   جميع الإعدادات ستكون كما هو معروض في شاشة الترحيب")
    print("=" * 70)


def compare_with_defaults():
    """مقارنة الإعدادات الحالية مع الافتراضية"""
    print("\n" + "=" * 70)
    print("  🔍 مقارنة الإعدادات الحالية مع الافتراضية")
    print("=" * 70)
    
    app = QApplication(sys.argv)
    settings = QSettings('BatteryGuard', 'Pro')
    
    # القيم الافتراضية المتوقعة
    defaults = {
        'enable_notifications': True,
        'enable_sounds': True,
        'enable_reminders': True,
        'minimize_to_tray': False,
        'start_on_boot': False,
        'auto_charge_control': False,
        'auto_optimization_enabled': False,
        'show_battery_in_tray': True,
    }
    
    print("\n📊 المقارنة:")
    
    differences = []
    
    for key, expected_value in defaults.items():
        current_value = settings.value(key, type=bool)
        
        if current_value != expected_value:
            differences.append({
                'key': key,
                'current': current_value,
                'expected': expected_value
            })
    
    if differences:
        print(f"\n⚠️ وجدت {len(differences)} اختلاف:")
        for diff in differences:
            print(f"\n  • {diff['key']}:")
            print(f"    الحالي: {diff['current']}")
            print(f"    المتوقع: {diff['expected']}")
    else:
        print("\n✅ جميع الإعدادات تطابق القيم الافتراضية")


def main():
    """الدالة الرئيسية"""
    print("\n" + "=" * 70)
    print("  ⚙️ إدارة QSettings - BatteryGuard Pro")
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
        reset_qsettings()
    elif choice == '2' or choice.lower() == 'show':
        show_current_qsettings()
    elif choice == '3' or choice.lower() == 'compare':
        compare_with_defaults()
    elif choice == '4' or choice.lower() == 'exit':
        print("\n👋 إلى اللقاء!")
    else:
        print("\n❌ خيار غير صحيح!")
        print("\nالاستخدام:")
        print("  python3 reset_qsettings.py reset    # إعادة تعيين")
        print("  python3 reset_qsettings.py show     # عرض الحالية")
        print("  python3 reset_qsettings.py compare  # مقارنة")


if __name__ == '__main__':
    main()
