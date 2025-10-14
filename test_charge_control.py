#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار نظام التحكم في الشحن
يختبر جميع الطرق المتاحة ويعرض النتائج
"""

import sys
import logging
from pathlib import Path

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("━" * 70)
print("🧪 اختبار نظام التحكم في الشحن - BatteryGuard Pro")
print("━" * 70)
print()

# استيراد النظام المتقدم
try:
    from charge_control_advanced import AdvancedChargeController
    print("✅ تم استيراد نظام التحكم المتقدم")
    USE_ADVANCED = True
except ImportError as e:
    print(f"❌ فشل استيراد النظام المتقدم: {e}")
    USE_ADVANCED = False

# استيراد النظام الأساسي
try:
    from charge_controller import ChargeController
    print("✅ تم استيراد نظام التحكم الأساسي")
    USE_BASIC = True
except ImportError as e:
    print(f"❌ فشل استيراد النظام الأساسي: {e}")
    USE_BASIC = False

print()
print("━" * 70)
print("📊 معلومات النظام")
print("━" * 70)

# معلومات النظام
import platform
print(f"🖥️  نظام التشغيل: {platform.system()} {platform.release()}")
print(f"🐍 Python: {sys.version.split()[0]}")
print(f"📁 المسار: {Path.cwd()}")
print()

# معلومات البطارية
try:
    import psutil
    battery = psutil.sensors_battery()
    if battery:
        print("🔋 معلومات البطارية:")
        print(f"   📊 المستوى: {battery.percent}%")
        print(f"   🔌 الشحن: {'نعم' if battery.power_plugged else 'لا'}")
        if battery.secsleft > 0:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            print(f"   ⏱️  الوقت المتبقي: {hours}س {minutes}د")
    else:
        print("⚠️  لم يتم العثور على بطارية")
except Exception as e:
    print(f"❌ خطأ في قراءة معلومات البطارية: {e}")

print()
print("━" * 70)
print("🔍 اكتشاف طرق التحكم المتاحة")
print("━" * 70)
print()

if USE_ADVANCED:
    print("🚀 اختبار النظام المتقدم...")
    try:
        controller = AdvancedChargeController()
        
        print(f"📱 الجهاز: {controller.device_info.get('manufacturer', 'Unknown')} "
              f"{controller.device_info.get('model', 'Unknown')}")
        print()
        
        print("✅ الطرق المتاحة:")
        for i, method in enumerate(controller.available_methods, 1):
            print(f"   {i}. {method}")
        
        print()
        print("━" * 70)
        print("🧪 اختبار التفعيل")
        print("━" * 70)
        print()
        
        # اختبار التفعيل
        print("⚙️  محاولة تفعيل التحكم (40%-80%)...")
        success, message = controller.enable_control(40, 80)
        
        if success:
            print(f"✅ نجح التفعيل: {message}")
        else:
            print(f"⚠️  فشل التفعيل: {message}")
        
        print()
        print("📊 حالة التحكم:")
        status = controller.get_status()
        print(f"   🔄 نشط: {status['is_active']}")
        print(f"   📉 الحد الأدنى: {status['min_limit']}%")
        print(f"   📈 الحد الأقصى: {status['max_limit']}%")
        print(f"   🎯 آخر إجراء: {status['last_action'] or 'لا يوجد'}")
        
        print()
        print("━" * 70)
        print("🧪 اختبار الطرق الفردية")
        print("━" * 70)
        print()
        
        # اختبار كل طريقة
        for method in controller.available_methods:
            if method == 'notification_only':
                print(f"⏭️  تخطي: {method}")
                continue
            
            print(f"🔧 اختبار: {method}")
            success, msg = controller._apply_method(method, 'set_limit', 80)
            
            if success:
                print(f"   ✅ نجح")
            else:
                print(f"   ❌ فشل: {msg}")
        
        print()
        print("━" * 70)
        print("🛑 إيقاف التحكم")
        print("━" * 70)
        print()
        
        success, message = controller.disable_control()
        if success:
            print(f"✅ تم إيقاف التحكم: {message}")
        else:
            print(f"⚠️  فشل الإيقاف: {message}")
    
    except Exception as e:
        print(f"❌ خطأ في النظام المتقدم: {e}")
        import traceback
        traceback.print_exc()

elif USE_BASIC:
    print("📦 اختبار النظام الأساسي...")
    try:
        controller = ChargeController()
        
        print(f"🔧 طريقة التحكم: {controller.control_method}")
        print()
        
        print("━" * 70)
        print("🧪 اختبار التفعيل")
        print("━" * 70)
        print()
        
        success, message = controller.enable_control(40, 80)
        
        if success:
            print(f"✅ نجح التفعيل: {message}")
        else:
            print(f"⚠️  فشل التفعيل: {message}")
        
        print()
        print("🛑 إيقاف التحكم...")
        success, message = controller.disable_control()
        
        if success:
            print(f"✅ تم الإيقاف: {message}")
        else:
            print(f"⚠️  فشل الإيقاف: {message}")
    
    except Exception as e:
        print(f"❌ خطأ في النظام الأساسي: {e}")
        import traceback
        traceback.print_exc()

else:
    print("❌ لم يتم العثور على أي نظام تحكم!")

print()
print("━" * 70)
print("🔍 فحص ملفات النظام (Linux)")
print("━" * 70)
print()

if sys.platform.startswith('linux'):
    # فحص ملفات التحكم
    paths_to_check = [
        '/sys/class/power_supply/BAT0/charge_control_end_threshold',
        '/sys/class/power_supply/BAT0/charge_control_start_threshold',
        '/sys/class/power_supply/BAT0/charge_start_threshold',
        '/sys/class/power_supply/BAT0/charge_stop_threshold',
        '/proc/acpi/call',
        '/sys/class/dmi/id/sys_vendor',
        '/sys/class/dmi/id/product_name',
    ]
    
    for path_str in paths_to_check:
        path = Path(path_str)
        if path.exists():
            print(f"✅ {path_str}")
            try:
                if path.is_file() and path.stat().st_size < 1000:
                    with open(path, 'r') as f:
                        content = f.read().strip()
                        if content:
                            print(f"   📄 المحتوى: {content}")
            except:
                pass
        else:
            print(f"❌ {path_str}")
    
    print()
    print("🔧 الأدوات المثبتة:")
    
    import subprocess
    tools = ['tlp', 'laptop_mode', 'upower', 'acpi']
    
    for tool in tools:
        try:
            result = subprocess.run(['which', tool], capture_output=True, timeout=2)
            if result.returncode == 0:
                print(f"   ✅ {tool}: {result.stdout.decode().strip()}")
            else:
                print(f"   ❌ {tool}: غير مثبت")
        except:
            print(f"   ❌ {tool}: خطأ في الفحص")

elif sys.platform == 'win32':
    print("🪟 Windows - فحص الأدوات...")
    
    # فحص أدوات Windows
    tools_paths = {
        'ASUS': [
            'C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe',
            'C:/Program Files/ASUS/ATK Package/ATK Hotkey/HControl.exe',
        ],
        'Dell': [
            'C:/Program Files/Dell/CommandConfigure/X86_64/cctk.exe',
        ],
        'HP': [
            'C:/Program Files/HP/HP Battery Health Manager/HPBatteryHealthManager.exe',
        ],
    }
    
    for vendor, paths in tools_paths.items():
        found = False
        for path_str in paths:
            if Path(path_str).exists():
                print(f"   ✅ {vendor}: {path_str}")
                found = True
                break
        if not found:
            print(f"   ❌ {vendor}: غير مثبت")
    
    # فحص Registry (Lenovo)
    try:
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r'SOFTWARE\Lenovo\SmartBattery', 0, winreg.KEY_READ)
            print(f"   ✅ Lenovo: Registry key موجود")
            winreg.CloseKey(key)
        except:
            print(f"   ❌ Lenovo: Registry key غير موجود")
    except:
        pass

print()
print("━" * 70)
print("📋 التوصيات")
print("━" * 70)
print()

if sys.platform.startswith('linux'):
    print("🐧 Linux:")
    print("   1. قم بتثبيت TLP للحصول على أفضل تحكم:")
    print("      sudo apt install tlp tlp-rdw")
    print("      sudo tlp start")
    print()
    print("   2. تأكد من الصلاحيات:")
    print("      sudo usermod -aG sudo $USER")
    print()
    print("   3. للأجهزة ThinkPad، قم بتثبيت acpi-call:")
    print("      sudo apt install acpi-call-dkms")
    print("      sudo modprobe acpi_call")

elif sys.platform == 'win32':
    print("🪟 Windows:")
    print("   1. قم بتشغيل التطبيق كمسؤول")
    print("   2. قم بتثبيت أدوات الشركة المصنعة:")
    print("      - ASUS: ASUS Battery Health Charging")
    print("      - Lenovo: Lenovo Vantage")
    print("      - Dell: Dell Power Manager")
    print("      - HP: HP Battery Health Manager")
    print()
    print("   3. تحديث تعريفات البطارية من موقع الشركة المصنعة")

print()
print("━" * 70)
print("✅ انتهى الاختبار")
print("━" * 70)
print()
print("💡 نصيحة: إذا فشلت جميع الطرق، سيستخدم التطبيق الإشعارات الذكية")
print("   لتذكيرك بفصل/توصيل الشاحن في الوقت المناسب.")
print()
