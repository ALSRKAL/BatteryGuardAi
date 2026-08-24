#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مدير التشغيل التلقائي"""

import sys
import os
import subprocess
import logging
from pathlib import Path
from typing import Tuple

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')
logger = logging.getLogger('BatteryGuard')


class AutostartManager:
    def __init__(self):
        # التحقق من وضع التشغيل (مبني أو تطوير)
        if getattr(sys, 'frozen', False):
            # التطبيق مبني بـ PyInstaller
            self.executable_path = Path(sys.executable)
            self.is_frozen = True
        else:
            # وضع التطوير
            self.current_dir = Path(__file__).parent.absolute()
            self.python_path = sys.executable
            self.main_script = self.current_dir / "main.py"
            self.is_frozen = False
        
        self.method = 'task_scheduler' if IS_WINDOWS else 'autostart'
    
    def is_enabled(self) -> bool:
        try:
            if IS_LINUX:
                desktop_file = Path.home() / ".config" / "autostart" / "batteryguard.desktop"
                if not desktop_file.exists():
                    return False
                # احترام حالة التعطيل داخل الملف نفسه
                content = desktop_file.read_text(encoding='utf-8')
                if 'X-GNOME-Autostart-enabled=false' in content:
                    return False
                return True
            elif IS_WINDOWS:
                result = subprocess.run(['schtasks', '/Query', '/TN', 'BatteryGuardPro'],
                                      capture_output=True, timeout=5)
                return result.returncode == 0
        except Exception:
            return False
        return False
    
    def enable(self) -> Tuple[bool, str]:
        try:
            if IS_LINUX:
                return self._enable_linux()
            elif IS_WINDOWS:
                return self._enable_windows()
        except Exception as e:
            return False, str(e)
        return False, "نظام غير مدعوم"
    
    def disable(self) -> Tuple[bool, str]:
        try:
            if IS_LINUX:
                return self._disable_linux()
            elif IS_WINDOWS:
                return self._disable_windows()
        except Exception as e:
            return False, str(e)
        return False, "نظام غير مدعوم"
    
    def _enable_linux(self) -> Tuple[bool, str]:
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = autostart_dir / "batteryguard.desktop"
        
        # تحديد الأمر المناسب حسب وضع التشغيل
        # مهم: اقتباس المسارات - مسار هذا المشروع يحتوي فراغات وحروفاً عربية
        if self.is_frozen:
            exec_command = f'"{self.executable_path}" --background'
        else:
            exec_command = f'"{self.python_path}" "{self.main_script}" --background'
        
        content = f"""[Desktop Entry]
Type=Application
Name=BatteryGuard Pro
Exec={exec_command}
Terminal=false
X-GNOME-Autostart-enabled=true
"""
        with open(desktop_file, 'w', encoding='utf-8') as f:
            f.write(content)
        os.chmod(desktop_file, 0o755)
        return True, "تم التفعيل بنجاح"
    
    def _disable_linux(self) -> Tuple[bool, str]:
        desktop_file = Path.home() / ".config" / "autostart" / "batteryguard.desktop"
        if desktop_file.exists():
            desktop_file.unlink()
        return True, "تم الإلغاء بنجاح"
    
    def _enable_windows(self) -> Tuple[bool, str]:
        # حذف المهمة القديمة إن وجدت
        subprocess.run(['schtasks', '/Delete', '/TN', 'BatteryGuardPro', '/F'],
                      capture_output=True, check=False)
        
        if self.is_frozen:
            # استخدام الملف المبني مباشرة (اقتباس المسار للفراغات)
            exec_path = str(self.executable_path)
            result = subprocess.run([
                'schtasks', '/Create', '/TN', 'BatteryGuardPro',
                '/TR', f'"{exec_path}" --background', '/SC', 'ONLOGON', '/F'
            ], capture_output=True, timeout=10)
        else:
            # وضع التطوير - استخدام VBS
            vbs_file = self.current_dir / "run_background.vbs"
            vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{self.python_path}" & chr(34) & " " & chr(34) & "{self.main_script}" & chr(34) & " --background", 0
'''
            with open(vbs_file, 'w', encoding='utf-8') as f:
                f.write(vbs_content)
            
            result = subprocess.run([
                'schtasks', '/Create', '/TN', 'BatteryGuardPro',
                '/TR', f'"{vbs_file}"', '/SC', 'ONLOGON', '/F'
            ], capture_output=True, timeout=10)
        
        if result.returncode == 0:
            return True, "تم التفعيل بنجاح"
        stderr = result.stderr.decode(errors='replace').strip() if result.stderr else ''
        return False, f"فشل التفعيل: {stderr or 'خطأ غير معروف'}"
    
    def _disable_windows(self) -> Tuple[bool, str]:
        subprocess.run(['schtasks', '/Delete', '/TN', 'BatteryGuardPro', '/F'],
                      capture_output=True, check=False)
        vbs_file = self.current_dir / "run_background.vbs"
        if vbs_file.exists():
            vbs_file.unlink()
        return True, "تم الإلغاء بنجاح"


autostart_manager = AutostartManager()
