#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
 مثبت خدمة BatteryGuardAI
يقوم بتثبيت الخدمة للتشغيل التلقائي عند الإقلاع
"""

import sys
import os
import subprocess
import platform
from pathlib import Path
import shutil

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

def print_header():
    """طباعة رأس المثبت"""
    print("━" * 70)
    print("مثبت خدمة BatteryGuardAI")
    print("━" * 70)
    print()

def check_admin():
    """التحقق من صلاحيات المسؤول"""
    if IS_WINDOWS:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    else:
        return os.geteuid() == 0

def install_linux_systemd():
    """تثبيت خدمة systemd على Linux"""
    print("تثبيت خدمة systemd...")
    print()
    
    # الحصول على المسار الحالي
    current_dir = Path.cwd()
    python_path = sys.executable
    main_script = current_dir / "main.py"
    
    # الحصول على اسم المستخدم
    username = os.environ.get('SUDO_USER') or os.environ.get('USER')
    
    # إنشاء ملف الخدمة
    service_content = f"""[Unit]
Description=BatteryGuardAI - Smart Battery Management System
Documentation=https://github.com/your-repo/batteryguard-pro
After=network.target graphical.target
Wants=graphical.target

[Service]
Type=simple
User={username}
Group={username}
WorkingDirectory={current_dir}
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/{username}/.Xauthority"
Environment="XDG_RUNTIME_DIR=/run/user/$(id -u {username})"
ExecStart={python_path} {main_script} --background
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={current_dir}

[Install]
WantedBy=graphical.target
"""
    
    service_file = Path("/etc/systemd/system/batteryguard.service")
    
    try:
        # كتابة ملف الخدمة
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        print(f"تم إنشاء ملف الخدمة: {service_file}")
        
        # إعادة تحميل systemd
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        print("تم إعادة تحميل systemd")
        
        # تفعيل الخدمة
        subprocess.run(['systemctl', 'enable', 'batteryguard.service'], check=True)
        print("تم تفعيل الخدمة للتشغيل التلقائي")
        
        # بدء الخدمة
        subprocess.run(['systemctl', 'start', 'batteryguard.service'], check=True)
        print("تم بدء الخدمة")
        
        print()
        print("━" * 70)
        print("تم تثبيت الخدمة بنجاح!")
        print("━" * 70)
        print()
        print("الأوامر المفيدة:")
        print("   • حالة الخدمة:    sudo systemctl status batteryguard")
        print("   • إيقاف الخدمة:    sudo systemctl stop batteryguard")
        print("   • بدء الخدمة:      sudo systemctl start batteryguard")
        print("   • إعادة التشغيل:   sudo systemctl restart batteryguard")
        print("   • عرض السجل:       sudo journalctl -u batteryguard -f")
        print("   • إلغاء التثبيت:   sudo systemctl disable batteryguard")
        print()
        
        return True
    
    except Exception as e:
        print(f"خطأ في التثبيت: {e}")
        return False

def install_linux_autostart():
    """تثبيت التشغيل التلقائي عبر autostart (بديل لـ systemd)"""
    print("تثبيت التشغيل التلقائي (autostart)...")
    print()
    
    username = os.environ.get('SUDO_USER') or os.environ.get('USER')
    home_dir = Path.home() if os.geteuid() != 0 else Path(f"/home/{username}")
    autostart_dir = home_dir / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    
    current_dir = Path.cwd()
    python_path = sys.executable
    main_script = current_dir / "main.py"
    
    # إنشاء ملف .desktop
    desktop_content = f"""[Desktop Entry]
Type=Application
Name=BatteryGuardAI
Comment=Smart Battery Management System
Exec={python_path} {main_script} --background
Icon={current_dir}/icon.png
Terminal=false
Categories=Utility;System;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
    
    desktop_file = autostart_dir / "batteryguard.desktop"
    
    try:
        with open(desktop_file, 'w') as f:
            f.write(desktop_content)
        
        # تعيين الصلاحيات
        os.chmod(desktop_file, 0o755)
        
        # تغيير المالك إذا كنا root
        if os.geteuid() == 0:
            import pwd
            uid = pwd.getpwnam(username).pw_uid
            gid = pwd.getpwnam(username).pw_gid
            os.chown(desktop_file, uid, gid)
        
        print(f"تم إنشاء ملف التشغيل التلقائي: {desktop_file}")
        print()
        print("━" * 70)
        print("تم تثبيت التشغيل التلقائي بنجاح!")
        print("━" * 70)
        print()
        print("سيتم تشغيل التطبيق تلقائياً عند تسجيل الدخول")
        print()
        
        return True
    
    except Exception as e:
        print(f"خطأ في التثبيت: {e}")
        return False

def install_windows_service():
    """تثبيت خدمة Windows"""
    print("تثبيت خدمة Windows...")
    print()
    
    current_dir = Path.cwd()
    python_path = sys.executable
    
    # إنشاء سكريبت VBS للتشغيل في الخلفية
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{python_path}" & chr(34) & " " & chr(34) & "{current_dir}\\main.py" & chr(34) & " --background", 0
Set WshShell = Nothing
'''
    
    vbs_file = current_dir / "run_background.vbs"
    
    try:
        with open(vbs_file, 'w') as f:
            f.write(vbs_content)
        
        print(f"تم إنشاء سكريبت التشغيل: {vbs_file}")
        
        # إضافة إلى Task Scheduler
        task_name = "BatteryGuardPro"
        
        # حذف المهمة القديمة إن وجدت
        subprocess.run(['schtasks', '/Delete', '/TN', task_name, '/F'], 
                      capture_output=True, check=False)
        
        # إنشاء مهمة جديدة
        create_task_cmd = [
            'schtasks', '/Create',
            '/TN', task_name,
            '/TR', str(vbs_file),
            '/SC', 'ONLOGON',
            '/RL', 'HIGHEST',
            '/F'
        ]
        
        result = subprocess.run(create_task_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("تم إنشاء مهمة Task Scheduler")
            
            # تشغيل المهمة الآن
            subprocess.run(['schtasks', '/Run', '/TN', task_name], 
                         capture_output=True, check=False)
            
            print()
            print("━" * 70)
            print("تم تثبيت الخدمة بنجاح!")
            print("━" * 70)
            print()
            print("الأوامر المفيدة:")
            print("   • عرض المهمة:      schtasks /Query /TN BatteryGuardPro")
            print("   • تشغيل المهمة:    schtasks /Run /TN BatteryGuardPro")
            print("   • إيقاف المهمة:    taskkill /F /IM python.exe")
            print("   • حذف المهمة:      schtasks /Delete /TN BatteryGuardPro /F")
            print()
            
            return True
        else:
            print(f"خطأ في إنشاء المهمة: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"خطأ في التثبيت: {e}")
        return False

def install_windows_startup():
    """تثبيت التشغيل التلقائي في مجلد Startup (بديل)"""
    print("تثبيت التشغيل التلقائي (Startup)...")
    print()
    
    current_dir = Path.cwd()
    python_path = sys.executable
    
    # الحصول على مجلد Startup
    startup_folder = Path(os.environ['APPDATA']) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    
    # إنشاء سكريبت VBS
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{python_path}" & chr(34) & " " & chr(34) & "{current_dir}\\main.py" & chr(34) & " --background", 0
Set WshShell = Nothing
'''
    
    vbs_file = startup_folder / "BatteryGuardPro.vbs"
    
    try:
        with open(vbs_file, 'w') as f:
            f.write(vbs_content)
        
        print(f"تم إنشاء ملف التشغيل التلقائي: {vbs_file}")
        print()
        print("━" * 70)
        print("تم تثبيت التشغيل التلقائي بنجاح!")
        print("━" * 70)
        print()
        print("سيتم تشغيل التطبيق تلقائياً عند تسجيل الدخول")
        print()
        
        return True
    
    except Exception as e:
        print(f"خطأ في التثبيت: {e}")
        return False

def uninstall_service():
    """إلغاء تثبيت الخدمة"""
    print("إلغاء تثبيت الخدمة...")
    print()
    
    if IS_LINUX:
        # إلغاء systemd
        try:
            subprocess.run(['systemctl', 'stop', 'batteryguard.service'], 
                         capture_output=True, check=False)
            subprocess.run(['systemctl', 'disable', 'batteryguard.service'], 
                         capture_output=True, check=False)
            
            service_file = Path("/etc/systemd/system/batteryguard.service")
            if service_file.exists():
                service_file.unlink()
                print("تم حذف خدمة systemd")
            
            subprocess.run(['systemctl', 'daemon-reload'], 
                         capture_output=True, check=False)
        except:
            pass
        
        # إلغاء autostart
        username = os.environ.get('SUDO_USER') or os.environ.get('USER')
        home_dir = Path.home() if os.geteuid() != 0 else Path(f"/home/{username}")
        desktop_file = home_dir / ".config" / "autostart" / "batteryguard.desktop"
        
        if desktop_file.exists():
            desktop_file.unlink()
            print("تم حذف ملف التشغيل التلقائي")
    
    elif IS_WINDOWS:
        # إلغاء Task Scheduler
        try:
            subprocess.run(['schtasks', '/Delete', '/TN', 'BatteryGuardPro', '/F'], 
                         capture_output=True, check=False)
            print("تم حذف مهمة Task Scheduler")
        except:
            pass
        
        # إلغاء Startup
        startup_folder = Path(os.environ['APPDATA']) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        vbs_file = startup_folder / "BatteryGuardPro.vbs"
        
        if vbs_file.exists():
            vbs_file.unlink()
            print("تم حذف ملف التشغيل التلقائي")
        
        # حذف سكريبت VBS
        current_dir = Path.cwd()
        vbs_file = current_dir / "run_background.vbs"
        if vbs_file.exists():
            vbs_file.unlink()
    
    print()
    print("تم إلغاء التثبيت بنجاح!")

def main():
    """الدالة الرئيسية"""
    print_header()
    
    # عرض القائمة
    print("اختر نوع التثبيت:")
    print()
    
    if IS_LINUX:
        print("1. تثبيت خدمة systemd (موصى به - يتطلب sudo)")
        print("2. تثبيت التشغيل التلقائي (autostart)")
        print("3. إلغاء التثبيت")
        print("4. خروج")
    elif IS_WINDOWS:
        print("1. تثبيت خدمة Task Scheduler (موصى به - يتطلب صلاحيات مسؤول)")
        print("2. تثبيت التشغيل التلقائي (Startup)")
        print("3. إلغاء التثبيت")
        print("4. خروج")
    
    print()
    choice = input("اختيارك (1-4): ").strip()
    print()
    
    if choice == '1':
        if IS_LINUX:
            if not check_admin():
                print("يتطلب صلاحيات sudo!")
                print("   قم بتشغيل: sudo python3 install_service.py")
                return 1
            install_linux_systemd()
        elif IS_WINDOWS:
            if not check_admin():
                print("يتطلب صلاحيات مسؤول!")
                print("   قم بتشغيل Command Prompt كمسؤول")
                return 1
            install_windows_service()
    
    elif choice == '2':
        if IS_LINUX:
            install_linux_autostart()
        elif IS_WINDOWS:
            install_windows_startup()
    
    elif choice == '3':
        if IS_LINUX and not check_admin():
            print("قد تحتاج صلاحيات sudo لإلغاء بعض الخدمات")
        uninstall_service()
    
    elif choice == '4':
        print("إلى اللقاء!")
        return 0
    
    else:
        print("اختيار غير صحيح!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
