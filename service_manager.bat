@echo off
REM ===============================================================
REM  مدير التشغيل الدائم - BatteryGuardAI (ويندوز)
REM
REM  غلاف رفيع فوق service_installer.py. المنطق كله هناك، وهذا الملف
REM  اختصار لمن يفضل النقر المزدوج على قائمة تفاعلية.
REM
REM  ملاحظة: النسخة السابقة كانت تكتب سكريبت VBS بنفسها ثم تسجل مهمة
REM  تشير إليه. صار المثبت هو من يبني سطر التشغيل، فلا يبقى ملف وسيط
REM  قد يُحذف أو تتغير مساراته فتفشل المهمة بلا رسالة مفهومة.
REM
REM  الاستخدام:
REM    service_manager.bat            قائمة تفاعلية
REM    service_manager.bat install    تثبيت وتشغيل
REM    service_manager.bat status     الحالة
REM    service_manager.bat uninstall  إزالة
REM ===============================================================

chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM اختيار مفسر بايثون: py أدق من python على ويندوز لأنه يقرأ المسجل
where py >nul 2>&1 && (set PY=py) || (set PY=python)

if not "%~1"=="" (
    call :RUN %*
    exit /b %errorlevel%
)

:MENU
cls
echo ----------------------------------------------------------
echo   مدير التشغيل الدائم - BatteryGuardAI
echo ----------------------------------------------------------
echo.
echo   1. تثبيت التشغيل الدائم
echo   2. عرض الحالة
echo   3. بدء
echo   4. ايقاف
echo   5. اعادة تشغيل
echo   6. عرض السجل
echo   7. ازالة التشغيل الدائم
echo   8. خروج
echo.

set /p choice="  اختيارك (1-8): "
echo.

if "%choice%"=="1" call :RUN install & goto PAUSE_MENU
if "%choice%"=="2" call :RUN status & goto PAUSE_MENU
if "%choice%"=="3" call :RUN start & goto PAUSE_MENU
if "%choice%"=="4" call :RUN stop & goto PAUSE_MENU
if "%choice%"=="5" call :RUN restart & goto PAUSE_MENU
if "%choice%"=="6" call :RUN logs & goto PAUSE_MENU
if "%choice%"=="7" call :RUN uninstall & goto PAUSE_MENU
if "%choice%"=="8" goto EXIT

echo   اختيار غير صحيح
goto PAUSE_MENU

:PAUSE_MENU
echo.
pause
goto MENU

:RUN
%PY% service_installer.py %*
exit /b %errorlevel%

:EXIT
echo   الى اللقاء
timeout /t 1 >nul
exit /b 0
