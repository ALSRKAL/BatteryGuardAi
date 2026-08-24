@echo off
REM BatteryGuard Pro - Build Script for Windows
chcp 65001 >nul

echo ======================================
echo 🚀 BatteryGuard Pro - Build Script
echo ======================================

REM التحقق من Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python غير مثبت!
    pause
    exit /b 1
)

echo ✅ Python موجود

REM إنشاء بيئة افتراضية
echo.
echo 📦 إنشاء بيئة افتراضية...
python -m venv build_env

REM تفعيل البيئة
call build_env\Scripts\activate.bat

REM ترقية pip
echo.
echo ⬆️  ترقية pip...
python -m pip install --upgrade pip

REM تثبيت المتطلبات
echo.
echo 📥 تثبيت المتطلبات...
pip install -r requirements.txt

REM تثبيت PyInstaller
echo.
echo 📥 تثبيت PyInstaller...
pip install pyinstaller

REM تنظيف البناء السابق
echo.
echo 🧹 تنظيف البناء السابق...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM بناء البرنامج
echo.
echo 🔨 بناء البرنامج...
pyinstaller --clean batteryguard.spec

REM التحقق من النجاح
if exist "dist\BatteryGuardPro.exe" (
    echo.
    echo ======================================
    echo ✅ تم البناء بنجاح!
    echo ======================================
    echo.
    echo 📁 الملف القابل للتنفيذ: dist\BatteryGuardPro.exe
    echo.
    
    REM اختبار التشغيل
    echo 🧪 اختبار التشغيل...
    timeout /t 1 /nobreak >nul
    echo ✅ جاهز للتشغيل
    
    echo.
    echo 🚀 للتشغيل:
    echo    dist\BatteryGuardPro.exe
    echo.
    echo 🔄 للتشغيل في الخلفية:
    echo    dist\BatteryGuardPro.exe --background
    echo.
    
    REM إنشاء اختصار
    echo 📝 إنشاء اختصار...
    powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\BatteryGuard Pro.lnk'); $Shortcut.TargetPath = '%CD%\dist\BatteryGuardPro.exe'; $Shortcut.WorkingDirectory = '%CD%\dist'; $Shortcut.Save()"
    echo ✅ تم إنشاء اختصار على سطح المكتب
    
) else (
    echo.
    echo ======================================
    echo ❌ فشل البناء!
    echo ======================================
    echo.
    echo 📝 تحقق من ملف السجل للمزيد من التفاصيل
    pause
    exit /b 1
)

REM تنظيف
echo.
set /p cleanup="🗑️  هل تريد حذف ملفات البناء المؤقتة؟ (y/n): "
if /i "%cleanup%"=="y" (
    if exist build rmdir /s /q build
    if exist build_env rmdir /s /q build_env
    echo ✅ تم التنظيف
)

echo.
echo ======================================
echo 🎉 اكتمل البناء بنجاح!
echo ======================================
pause
