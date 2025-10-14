@echo off
REM ═══════════════════════════════════════════════════════════════
REM 🚀 BatteryGuard Pro - ملف التشغيل السريع (Windows)
REM ═══════════════════════════════════════════════════════════════

chcp 65001 >nul
title BatteryGuard Pro - نظام إدارة البطارية الذكي

echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 🔋 BatteryGuard Pro - نظام إدارة البطارية الذكي
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM التحقق من Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python غير مثبت!
    echo 📦 قم بتحميله من: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo ✅ تم العثور على Python
python --version
echo.

REM التحقق من البيئة الافتراضية
if not exist "venv" (
    echo 📦 إنشاء البيئة الافتراضية...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ فشل إنشاء البيئة الافتراضية
        pause
        exit /b 1
    )
)

REM تفعيل البيئة الافتراضية
echo 🔄 تفعيل البيئة الافتراضية...
call venv\Scripts\activate.bat

REM تثبيت المتطلبات
echo 📦 تثبيت المتطلبات...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

if errorlevel 1 (
    echo ⚠️ فشل تثبيت بعض المكتبات، محاولة التثبيت اليدوي...
    python -m pip install PyQt6 psutil pywin32 wmi win10toast -q
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 🚀 تشغيل BatteryGuard Pro...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo 💡 نصيحة: قم بتشغيل هذا الملف كمسؤول للحصول على كامل الصلاحيات
echo.

REM تشغيل التطبيق
python main.py

REM إلغاء تفعيل البيئة الافتراضية
call venv\Scripts\deactivate.bat

pause
