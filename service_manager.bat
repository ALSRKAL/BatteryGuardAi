@echo off
REM ═══════════════════════════════════════════════════════════════
REM 🔧 مدير خدمة BatteryGuard Pro - Windows
REM ═══════════════════════════════════════════════════════════════

chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set TASK_NAME=BatteryGuardPro
set SCRIPT_DIR=%~dp0
set PYTHON_EXE=python
set VBS_FILE=%SCRIPT_DIR%run_background.vbs

:MENU
cls
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 🔧 مدير خدمة BatteryGuard Pro
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo 1. تثبيت الخدمة (Task Scheduler)
echo 2. بدء الخدمة
echo 3. إيقاف الخدمة
echo 4. حالة الخدمة
echo 5. تفعيل التشغيل التلقائي
echo 6. تعطيل التشغيل التلقائي
echo 7. إلغاء تثبيت الخدمة
echo 8. خروج
echo.

set /p choice="اختيارك (1-8): "
echo.

if "%choice%"=="1" goto INSTALL
if "%choice%"=="2" goto START
if "%choice%"=="3" goto STOP
if "%choice%"=="4" goto STATUS
if "%choice%"=="5" goto ENABLE
if "%choice%"=="6" goto DISABLE
if "%choice%"=="7" goto UNINSTALL
if "%choice%"=="8" goto EXIT

echo ❌ اختيار غير صحيح!
pause
goto MENU

:INSTALL
echo 📦 تثبيت الخدمة...
echo.

REM التحقق من الصلاحيات
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠️  يتطلب صلاحيات مسؤول!
    echo    قم بتشغيل هذا الملف كمسؤول
    pause
    goto MENU
)

REM إنشاء سكريبت VBS
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_FILE%"
echo WshShell.Run chr(34) ^& "%PYTHON_EXE%" ^& chr(34) ^& " " ^& chr(34) ^& "%SCRIPT_DIR%main.py" ^& chr(34) ^& " --background", 0 >> "%VBS_FILE%"
echo Set WshShell = Nothing >> "%VBS_FILE%"

echo ✅ تم إنشاء سكريبت التشغيل
echo.

REM حذف المهمة القديمة
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM إنشاء مهمة جديدة
schtasks /Create /TN "%TASK_NAME%" /TR "\"%VBS_FILE%\"" /SC ONLOGON /RL HIGHEST /F >nul 2>&1

if %errorLevel% equ 0 (
    echo ✅ تم تثبيت الخدمة بنجاح
    echo 💡 استخدم الخيار 5 لتفعيل التشغيل التلقائي
) else (
    echo ❌ فشل تثبيت الخدمة
)

pause
goto MENU

:START
echo ▶️  بدء الخدمة...
schtasks /Run /TN "%TASK_NAME%" >nul 2>&1

if %errorLevel% equ 0 (
    echo ✅ تم بدء الخدمة
) else (
    echo ❌ فشل بدء الخدمة
    echo    تأكد من تثبيت الخدمة أولاً
)

pause
goto MENU

:STOP
echo ⏸️  إيقاف الخدمة...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq BatteryGuard*" >nul 2>&1

if %errorLevel% equ 0 (
    echo ✅ تم إيقاف الخدمة
) else (
    echo ⚠️  لم يتم العثور على عملية قيد التشغيل
)

pause
goto MENU

:STATUS
echo 📊 حالة الخدمة:
echo.
schtasks /Query /TN "%TASK_NAME%" /FO LIST /V

if %errorLevel% neq 0 (
    echo ❌ الخدمة غير مثبتة
)

echo.
echo 📋 العمليات قيد التشغيل:
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE

pause
goto MENU

:ENABLE
echo ✅ تفعيل التشغيل التلقائي...
schtasks /Change /TN "%TASK_NAME%" /ENABLE >nul 2>&1

if %errorLevel% equ 0 (
    echo ✅ تم تفعيل التشغيل التلقائي
    echo 💡 سيتم تشغيل الخدمة تلقائياً عند تسجيل الدخول
) else (
    echo ❌ فشل التفعيل
    echo    تأكد من تثبيت الخدمة أولاً
)

pause
goto MENU

:DISABLE
echo ❌ تعطيل التشغيل التلقائي...
schtasks /Change /TN "%TASK_NAME%" /DISABLE >nul 2>&1

if %errorLevel% equ 0 (
    echo ✅ تم تعطيل التشغيل التلقائي
) else (
    echo ❌ فشل التعطيل
)

pause
goto MENU

:UNINSTALL
echo 🗑️  إلغاء تثبيت الخدمة...
echo.

REM إيقاف الخدمة
taskkill /F /IM python.exe /FI "WINDOWTITLE eq BatteryGuard*" >nul 2>&1

REM حذف المهمة
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

if %errorLevel% equ 0 (
    echo ✅ تم حذف المهمة
) else (
    echo ⚠️  المهمة غير موجودة
)

REM حذف سكريبت VBS
if exist "%VBS_FILE%" (
    del "%VBS_FILE%"
    echo ✅ تم حذف سكريبت التشغيل
)

echo ✅ تم إلغاء التثبيت بنجاح

pause
goto MENU

:EXIT
echo 👋 إلى اللقاء!
timeout /t 2 >nul
exit /b 0
