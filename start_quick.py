#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 BatteryGuard Pro - مشغل سريع متعدد المنصات
يقوم بتثبيت المتطلبات وتشغيل التطبيق تلقائياً
"""

import sys
import os
import subprocess
import platform
from pathlib import Path

def print_header():
    """طباعة رأس التطبيق"""
    print("━" * 60)
    print("🔋 BatteryGuard Pro - نظام إدارة البطارية الذكي")
    print("━" * 60)
    print()

def check_python():
    """التحقق من إصدار Python"""
    version = sys.version_info
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ يتطلب Python 3.8 أو أحدث")
        return False
    
    return True

def install_requirements():
    """تثبيت المتطلبات"""
    print("\n📦 تثبيت المتطلبات...")
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("⚠️ ملف requirements.txt غير موجود")
        return False
    
    try:
        # ترقية pip
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            check=False
        )
        
        # تثبيت المتطلبات
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ تم تثبيت جميع المتطلبات")
            return True
        else:
            print("⚠️ بعض المكتبات فشلت، محاولة التثبيت الأساسي...")
            
            # تثبيت المكتبات الأساسية فقط
            basic_packages = ["PyQt6", "psutil"]
            
            if platform.system() == "Windows":
                basic_packages.extend(["pywin32", "wmi", "win10toast"])
            
            for package in basic_packages:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True,
                    check=False
                )
            
            print("✅ تم تثبيت المكتبات الأساسية")
            return True
    
    except Exception as e:
        print(f"❌ خطأ في التثبيت: {e}")
        return False

def check_charge_control_tools():
    """التحقق من أدوات التحكم في الشحن"""
    print("\n🔧 التحقق من أدوات التحكم في الشحن...")
    
    system = platform.system()
    
    if system == "Linux":
        # التحقق من TLP
        try:
            result = subprocess.run(["which", "tlp"], capture_output=True)
            if result.returncode == 0:
                print("✅ TLP مثبت")
            else:
                print("⚠️ TLP غير مثبت (اختياري)")
                print("   لتثبيته: sudo apt install tlp tlp-rdw")
        except:
            pass
        
        # التحقق من kernel threshold
        threshold_path = Path("/sys/class/power_supply/BAT0/charge_control_end_threshold")
        if threshold_path.exists():
            print("✅ دعم kernel threshold متاح")
        else:
            print("⚠️ kernel threshold غير متاح")
    
    elif system == "Windows":
        print("💡 سيتم اكتشاف أدوات التحكم تلقائياً (ASUS/Lenovo/Dell)")
        print("   للحصول على أفضل أداء، قم بتشغيل التطبيق كمسؤول")

def run_application():
    """تشغيل التطبيق"""
    print("\n━" * 60)
    print("🚀 تشغيل BatteryGuard Pro...")
    print("━" * 60)
    print()
    
    main_file = Path("main.py")
    if not main_file.exists():
        print("❌ ملف main.py غير موجود")
        return False
    
    try:
        # تشغيل التطبيق
        subprocess.run([sys.executable, "main.py"])
        return True
    
    except KeyboardInterrupt:
        print("\n\n⚠️ تم إيقاف التطبيق بواسطة المستخدم")
        return True
    
    except Exception as e:
        print(f"❌ خطأ في تشغيل التطبيق: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    print_header()
    
    # التحقق من Python
    if not check_python():
        input("\nاضغط Enter للخروج...")
        return 1
    
    # تثبيت المتطلبات
    if not install_requirements():
        print("\n⚠️ فشل تثبيت المتطلبات، لكن سنحاول التشغيل...")
    
    # التحقق من أدوات التحكم
    check_charge_control_tools()
    
    # تشغيل التطبيق
    success = run_application()
    
    if not success:
        input("\nاضغط Enter للخروج...")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
