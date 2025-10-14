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
        self.current_dir = Path(__file__).parent.absolute()
        self.python_path = sys.executable
        self.main_script = self.current_dir / "main.py"
        self.method = 'task_scheduler' if IS_WINDOWS else 'autostart'
    
    def is_enabled(self) -> bool:
        try:
            if IS_LINUX:
                desktop_file = Path.home() / ".config" / "autostart" / "batteryguard.desktop"
                return desktop_file.exists()
            elif IS_WINDOWS:
                result = subprocess.run(['schtasks', '/Query', '/TN', 'BatteryGuardPro'],
                                      capture_output=True, timeout=5)
                return result.returncode == 0
        except:
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
        
        content = f"""[Desktop Entry]
Type=Application
Name=BatteryGuard Pro
Exec={self.python_path} {self.main_script} --background
Terminal=false
X-GNOME-Autostart-enabled=true
"""
        with open(desktop_file, 'w') as f:
            f.write(content)
        os.chmod(desktop_file, 0o755)
        return True, "تم التفعيل بنجاح"
    
    def _disable_linux(self) -> Tuple[bool, str]:
        desktop_file = Path.home() / ".config" / "autostart" / "batteryguard.desktop"
        if desktop_file.exists():
            desktop_file.unlink()
        return True, "تم الإلغاء بنجاح"
    
    def _enable_windows(self) -> Tuple[bool, str]:
        vbs_file = self.current_dir / "run_background.vbs"
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{self.python_path}" & chr(34) & " " & chr(34) & "{self.main_script}" & chr(34) & " --background", 0
'''
        with open(vbs_file, 'w') as f:
            f.write(vbs_content)
        
        subprocess.run(['schtasks', '/Delete', '/TN', 'BatteryGuardPro', '/F'],
                      capture_output=True, check=False)
        
        result = subprocess.run([
            'schtasks', '/Create', '/TN', 'BatteryGuardPro',
            '/TR', str(vbs_file), '/SC', 'ONLOGON', '/RL', 'HIGHEST', '/F'
        ], capture_output=True, timeout=10)
        
        return (True, "تم التفعيل بنجاح") if result.returncode == 0 else (False, "فشل التفعيل")
    
    def _disable_windows(self) -> Tuple[bool, str]:
        subprocess.run(['schtasks', '/Delete', '/TN', 'BatteryGuardPro', '/F'],
                      capture_output=True, check=False)
        vbs_file = self.current_dir / "run_background.vbs"
        if vbs_file.exists():
            vbs_file.unlink()
        return True, "تم الإلغاء بنجاح"


autostart_manager = AutostartManager()
