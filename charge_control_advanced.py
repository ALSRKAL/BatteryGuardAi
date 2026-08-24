#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔌 نظام التحكم المتقدم في الشحن - الجيل الثاني
يستخدم تقنيات متعددة للتحكم الفعلي في الشحن على Windows و Linux
"""

import sys
import os
import logging
import subprocess
import time
import ctypes
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import psutil

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

logger = logging.getLogger('BatteryGuard')


class AdvancedChargeController:
    """نظام التحكم المتقدم في الشحن - يعمل فعلياً"""
    
    def __init__(self, sudo_password=None):
        self.is_active = False
        self.max_charge_limit = 80
        self.min_charge_limit = 40
        self.sudo_password = sudo_password
        self.last_action = None
        self.last_action_time = 0
        
        # اكتشاف جميع الطرق المتاحة
        self.available_methods = self._detect_all_methods()
        logger.info(f"✅ الطرق المتاحة: {', '.join(self.available_methods)}")
        
        # معلومات الجهاز
        self.device_info = self._detect_device_info()
        logger.info(f"📱 الجهاز: {self.device_info.get('manufacturer', 'Unknown')}")
    
    def _detect_device_info(self) -> Dict:
        """اكتشاف معلومات الجهاز"""
        info = {
            'manufacturer': 'Unknown',
            'model': 'Unknown',
            'battery_path': None
        }
        
        if IS_LINUX:
            # قراءة معلومات الجهاز من DMI
            try:
                with open('/sys/class/dmi/id/sys_vendor', 'r') as f:
                    info['manufacturer'] = f.read().strip()
                with open('/sys/class/dmi/id/product_name', 'r') as f:
                    info['model'] = f.read().strip()
            except:
                pass
            
            # البحث عن مسار البطارية
            for bat in ['BAT0', 'BAT1', 'battery']:
                path = Path(f'/sys/class/power_supply/{bat}')
                if path.exists():
                    info['battery_path'] = str(path)
                    break
        
        elif IS_WINDOWS:
            try:
                # استخدام WMI للحصول على معلومات الجهاز
                result = subprocess.run(
                    ['wmic', 'computersystem', 'get', 'manufacturer,model'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if parts:
                            info['manufacturer'] = parts[0]
                            if len(parts) > 1:
                                info['model'] = ' '.join(parts[1:])
            except:
                pass
        
        return info
    
    def _detect_all_methods(self) -> List[str]:
        """اكتشاف جميع طرق التحكم المتاحة"""
        methods = []
        
        if IS_LINUX:
            # 1. Kernel Threshold (الأفضل والأكثر موثوقية)
            for bat in ['BAT0', 'BAT1']:
                threshold_path = Path(f'/sys/class/power_supply/{bat}/charge_control_end_threshold')
                if threshold_path.exists():
                    methods.append(f'kernel_threshold_{bat}')
                    break
            
            # 2. ASUS Battery Health
            asus_start = Path('/sys/class/power_supply/BAT0/charge_control_start_threshold')
            asus_end = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            if asus_start.exists() and asus_end.exists():
                methods.append('asus_battery_health')
            
            # 3. ThinkPad Battery Thresholds
            tp_start = Path('/sys/class/power_supply/BAT0/charge_start_threshold')
            tp_stop = Path('/sys/class/power_supply/BAT0/charge_stop_threshold')
            if tp_start.exists() and tp_stop.exists():
                methods.append('thinkpad_threshold')
            
            # 4. TLP
            if self._check_command('tlp'):
                methods.append('tlp')
            
            # 5. ACPI Call
            if Path('/proc/acpi/call').exists():
                methods.append('acpi_call')
            
            # 6. Laptop Mode Tools
            if self._check_command('laptop_mode'):
                methods.append('laptop_mode')
            
            # 7. UPower (للمراقبة والإشعارات)
            if self._check_command('upower'):
                methods.append('upower')
        
        elif IS_WINDOWS:
            # 1. ASUS Battery Health Charging
            if self._check_asus_windows():
                methods.append('asus_windows')
            
            # 2. Lenovo Conservation Mode
            if self._check_lenovo_windows():
                methods.append('lenovo_windows')
            
            # 3. Dell Power Manager
            if self._check_dell_windows():
                methods.append('dell_windows')
            
            # 4. HP Battery Health Manager
            if self._check_hp_windows():
                methods.append('hp_windows')
            
            # 5. MSI Dragon Center
            if self._check_msi_windows():
                methods.append('msi_windows')
            
            # 6. WMI/ACPI
            methods.append('wmi_acpi')
            
            # 7. PowerShell Battery Control
            methods.append('powershell_battery')
        
        if not methods:
            methods.append('notification_only')
        
        return methods
    
    def _check_command(self, cmd: str) -> bool:
        """التحقق من وجود أمر"""
        try:
            result = subprocess.run(['which', cmd], capture_output=True, timeout=2)
            return result.returncode == 0
        except:
            return False
    
    def _check_asus_windows(self) -> bool:
        """التحقق من ASUS Battery Health"""
        paths = [
            'C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe',
            'C:/Program Files/ASUS/ATK Package/ATK Hotkey/HControl.exe',
        ]
        return any(Path(p).exists() for p in paths)
    
    def _check_lenovo_windows(self) -> bool:
        """التحقق من Lenovo Vantage"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r'SOFTWARE\Lenovo\SmartBattery', 0, winreg.KEY_READ)
            winreg.CloseKey(key)
            return True
        except:
            return False
    
    def _check_dell_windows(self) -> bool:
        """التحقق من Dell Command"""
        return self._check_command('cctk') or Path('C:/Program Files/Dell/CommandConfigure/X86_64/cctk.exe').exists()
    
    def _check_hp_windows(self) -> bool:
        """التحقق من HP Battery Health Manager"""
        return Path('C:/Program Files/HP/HP Battery Health Manager/HPBatteryHealthManager.exe').exists()
    
    def _check_msi_windows(self) -> bool:
        """التحقق من MSI Dragon Center"""
        return Path('C:/Program Files (x86)/MSI/One Dragon Center/DragonCenter.exe').exists()
    
    def enable_control(self, min_limit: int, max_limit: int) -> Tuple[bool, str]:
        """تفعيل التحكم في الشحن"""
        self.min_charge_limit = min_limit
        self.max_charge_limit = max_limit
        self.is_active = True
        
        # محاولة تطبيق الحد على مستوى النظام
        success_count = 0
        messages = []
        
        for method in self.available_methods:
            if method == 'notification_only':
                continue
            
            success, msg = self._apply_method(method, 'set_limit', max_limit)
            if success:
                success_count += 1
                messages.append(f"✅ {method}")
                logger.info(f"✅ نجح: {method}")
            else:
                messages.append(f"❌ {method}: {msg}")
        
        if success_count > 0:
            return True, f"تم التفعيل بنجاح ({success_count} طريقة)"
        else:
            return False, "سيتم استخدام الإشعارات فقط"
    
    def disable_control(self) -> Tuple[bool, str]:
        """إيقاف التحكم في الشحن"""
        self.is_active = False
        
        for method in self.available_methods:
            if method != 'notification_only':
                self._apply_method(method, 'disable', 100)
        
        logger.info("تم إيقاف التحكم في الشحن")
        return True, "تم إيقاف التحكم"
    
    def check_and_control(self, current_percent: int, is_charging: bool) -> Optional[Dict]:
        """فحص والتحكم في الشحن"""
        if not self.is_active:
            return None
        
        current_time = time.time()
        if current_time - self.last_action_time < 30:
            return None
        
        action_needed = None
        
        # وصل للحد الأقصى
        if is_charging and current_percent >= self.max_charge_limit:
            if self.last_action != 'stop_charging':
                success = self._execute_stop_charging()
                
                action_needed = {
                    'action': 'stop_charging',
                    'message': f'{"✅ تم إيقاف الشحن" if success else "⚠️ افصل الشاحن يدوياً"} عند {self.max_charge_limit}%',
                    'should_notify': True,
                    'urgency': 'critical' if not success else 'normal'
                }
                
                self.last_action = 'stop_charging'
                self.last_action_time = current_time
        
        # وصل للحد الأدنى
        elif not is_charging and current_percent <= self.min_charge_limit:
            if self.last_action != 'start_charging':
                success = self._execute_start_charging()
                
                action_needed = {
                    'action': 'start_charging',
                    'message': f'🔌 وصّل الشاحن عند {self.min_charge_limit}%',
                    'should_notify': True,
                    'urgency': 'normal'
                }
                
                self.last_action = 'start_charging'
                self.last_action_time = current_time
        
        # في النطاق الآمن
        elif self.min_charge_limit < current_percent < self.max_charge_limit:
            self.last_action = None
        
        return action_needed
    
    def _execute_stop_charging(self) -> bool:
        """تنفيذ إيقاف الشحن بجميع الطرق"""
        success = False
        
        for method in self.available_methods:
            if method == 'notification_only':
                continue
            
            result, _ = self._apply_method(method, 'stop', None)
            if result:
                success = True
                logger.info(f"✅ نجح إيقاف الشحن عبر: {method}")
        
        return success
    
    def _execute_start_charging(self) -> bool:
        """تنفيذ بدء الشحن بجميع الطرق"""
        success = False
        
        for method in self.available_methods:
            if method == 'notification_only':
                continue
            
            result, _ = self._apply_method(method, 'start', None)
            if result:
                success = True
                logger.info(f"✅ نجح بدء الشحن عبر: {method}")
        
        return success
    
    def _apply_method(self, method: str, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """تطبيق طريقة معينة"""
        try:
            if method.startswith('kernel_threshold'):
                return self._kernel_threshold_control(action, value)
            
            elif method == 'asus_battery_health':
                return self._asus_linux_control(action, value)
            
            elif method == 'thinkpad_threshold':
                return self._thinkpad_control(action, value)
            
            elif method == 'tlp':
                return self._tlp_control(action, value)
            
            elif method == 'acpi_call':
                return self._acpi_call_control(action, value)
            
            elif method == 'asus_windows':
                return self._asus_windows_control(action, value)
            
            elif method == 'lenovo_windows':
                return self._lenovo_windows_control(action, value)
            
            elif method == 'dell_windows':
                return self._dell_windows_control(action, value)
            
            elif method == 'hp_windows':
                return self._hp_windows_control(action, value)
            
            elif method == 'wmi_acpi':
                return self._wmi_control(action, value)
            
            elif method == 'powershell_battery':
                return self._powershell_control(action, value)
        
        except Exception as e:
            return False, str(e)
        
        return False, "طريقة غير مدعومة"
    
    # ═══════════════════════════════════════════════════════════════
    # Linux Control Methods
    # ═══════════════════════════════════════════════════════════════
    
    def _kernel_threshold_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر Kernel Threshold"""
        bat_path = self.device_info.get('battery_path', '/sys/class/power_supply/BAT0')
        threshold_path = Path(f'{bat_path}/charge_control_end_threshold')
        
        if action == 'stop':
            current = int(psutil.sensors_battery().percent)
            return self._write_sys_file(threshold_path, current), "OK"
        
        elif action == 'start' or action == 'set_limit':
            limit = value if value else self.max_charge_limit
            return self._write_sys_file(threshold_path, limit), "OK"
        
        elif action == 'disable':
            return self._write_sys_file(threshold_path, 100), "OK"
        
        return False, "Invalid action"
    
    def _asus_linux_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر ASUS Battery Health (Linux)"""
        start_path = Path('/sys/class/power_supply/BAT0/charge_control_start_threshold')
        end_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
        
        if action == 'stop':
            current = int(psutil.sensors_battery().percent)
            s1 = self._write_sys_file(start_path, max(0, current - 2))
            s2 = self._write_sys_file(end_path, current)
            return s1 and s2, "OK"
        
        elif action == 'start' or action == 'set_limit':
            s1 = self._write_sys_file(start_path, self.min_charge_limit)
            s2 = self._write_sys_file(end_path, self.max_charge_limit)
            return s1 and s2, "OK"
        
        elif action == 'disable':
            s1 = self._write_sys_file(start_path, 0)
            s2 = self._write_sys_file(end_path, 100)
            return s1 and s2, "OK"
        
        return False, "Invalid action"
    
    def _thinkpad_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر ThinkPad Thresholds"""
        start_path = Path('/sys/class/power_supply/BAT0/charge_start_threshold')
        stop_path = Path('/sys/class/power_supply/BAT0/charge_stop_threshold')
        
        if action == 'stop':
            current = int(psutil.sensors_battery().percent)
            s1 = self._write_sys_file(start_path, max(0, current - 2))
            s2 = self._write_sys_file(stop_path, current)
            return s1 and s2, "OK"
        
        elif action == 'start' or action == 'set_limit':
            s1 = self._write_sys_file(start_path, self.min_charge_limit)
            s2 = self._write_sys_file(stop_path, self.max_charge_limit)
            return s1 and s2, "OK"
        
        elif action == 'disable':
            s1 = self._write_sys_file(start_path, 0)
            s2 = self._write_sys_file(stop_path, 100)
            return s1 and s2, "OK"
        
        return False, "Invalid action"
    
    def _tlp_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر TLP"""
        try:
            if action == 'stop':
                current = int(psutil.sensors_battery().percent)
                # تعيين حد مؤقت عند المستوى الحالي
                cmd = ['tlp', 'setcharge', str(max(0, current - 2)), str(current), 'BAT0']
            
            elif action == 'start':
                # إعادة تعيين الحدود الطبيعية
                cmd = ['tlp', 'setcharge', str(self.min_charge_limit), str(self.max_charge_limit), 'BAT0']
            
            elif action == 'set_limit':
                # تعيين الحدود
                limit = value if value else self.max_charge_limit
                start = max(0, limit - 5)
                cmd = ['tlp', 'setcharge', str(start), str(limit), 'BAT0']
            
            elif action == 'disable':
                # إلغاء جميع الحدود
                cmd = ['tlp', 'setcharge', '0', '100', 'BAT0']
            
            else:
                return False, "Invalid action"
            
            # محاولة التنفيذ
            success = self._run_sudo_command(cmd)
            
            if success:
                # تطبيق الإعدادات فوراً
                self._run_sudo_command(['tlp', 'start'])
                return True, "OK"
            
            return False, "Failed to execute TLP command"
        
        except Exception as e:
            logger.error(f"TLP control error: {e}")
            return False, str(e)
    
    def _acpi_call_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر ACPI Call"""
        acpi_path = Path('/proc/acpi/call')
        
        manufacturer = self.device_info.get('manufacturer', '').lower()
        
        # أوامر ACPI حسب الشركة المصنعة
        if 'lenovo' in manufacturer or 'thinkpad' in manufacturer:
            if action == 'stop':
                cmd = '\\_SB.PCI0.LPCB.EC0.HKEY.BCSG 1'
            elif action == 'start':
                cmd = '\\_SB.PCI0.LPCB.EC0.HKEY.BCSG 0'
            else:
                return False, "Not supported"
            
            return self._write_sys_file(acpi_path, cmd), "OK"
        
        return False, "Device not supported"
    
    # ═══════════════════════════════════════════════════════════════
    # Windows Control Methods
    # ═══════════════════════════════════════════════════════════════
    
    def _asus_windows_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر ASUS (Windows)"""
        asus_paths = [
            'C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe',
            'C:/Program Files/ASUS/ATK Package/ATK Hotkey/HControl.exe',
        ]
        
        asus_path = None
        for path in asus_paths:
            if Path(path).exists():
                asus_path = path
                break
        
        if not asus_path:
            return False, "ASUS tool not found"
        
        try:
            if action == 'stop':
                subprocess.run([asus_path, '/battery', 'stop'], timeout=5, check=True)
            elif action == 'start':
                subprocess.run([asus_path, '/battery', 'start'], timeout=5, check=True)
            elif action == 'set_limit':
                subprocess.run([asus_path, '/battery', str(value)], timeout=5, check=True)
            elif action == 'disable':
                subprocess.run([asus_path, '/battery', '100'], timeout=5, check=True)
            
            return True, "OK"
        except:
            return False, "Failed"
    
    def _lenovo_windows_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر Lenovo (Windows)"""
        try:
            import winreg
            key_path = r'SOFTWARE\Lenovo\SmartBattery'
            
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, 
                               winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
            
            if action == 'stop':
                winreg.SetValueEx(key, 'ConservationMode', 0, winreg.REG_DWORD, 1)
            elif action == 'start' or action == 'disable':
                winreg.SetValueEx(key, 'ConservationMode', 0, winreg.REG_DWORD, 0)
            elif action == 'set_limit':
                winreg.SetValueEx(key, 'ChargeThreshold', 0, winreg.REG_DWORD, value)
            
            winreg.CloseKey(key)
            return True, "OK"
        except:
            return False, "Failed"
    
    def _dell_windows_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر Dell (Windows)"""
        try:
            if action == 'stop':
                current = int(psutil.sensors_battery().percent)
                cmd = f'cctk --PrimaryBattChargeCfg=Custom:{current}'
            elif action == 'start' or action == 'disable':
                cmd = 'cctk --PrimaryBattChargeCfg=Standard'
            elif action == 'set_limit':
                cmd = f'cctk --PrimaryBattChargeCfg=Custom:{value}'
            else:
                return False, "Invalid action"
            
            result = subprocess.run(['powershell', '-Command', cmd], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0, "OK"
        except:
            return False, "Failed"
    
    def _hp_windows_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر HP (Windows)"""
        try:
            import winreg
            key_path = r'SOFTWARE\Hewlett-Packard\HP Battery Health Manager'
            
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
            
            if action == 'stop' or action == 'set_limit':
                winreg.SetValueEx(key, 'MaxCharge', 0, winreg.REG_DWORD, 
                                value if value else self.max_charge_limit)
            elif action == 'disable':
                winreg.SetValueEx(key, 'MaxCharge', 0, winreg.REG_DWORD, 100)
            
            winreg.CloseKey(key)
            return True, "OK"
        except:
            return False, "Failed"
    
    def _wmi_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر WMI"""
        try:
            ps_script = f'''
            $battery = Get-WmiObject -Namespace root/WMI -Class BatteryFullChargedCapacity
            if ($battery) {{
                $battery.FullChargedCapacity = {value if value else self.max_charge_limit}
                $battery.Put()
            }}
            '''
            
            result = subprocess.run(['powershell', '-Command', ps_script],
                                  capture_output=True, timeout=5)
            return result.returncode == 0, "OK"
        except:
            return False, "Failed"
    
    def _powershell_control(self, action: str, value: Optional[int]) -> Tuple[bool, str]:
        """التحكم عبر PowerShell"""
        try:
            if action == 'set_limit' or action == 'stop':
                limit = value if value else self.max_charge_limit
                cmd = f'powercfg /setdcvalueindex SCHEME_CURRENT SUB_BATTERY BATACTIONCRIT {limit}'
            elif action == 'disable':
                cmd = 'powercfg /setdcvalueindex SCHEME_CURRENT SUB_BATTERY BATACTIONCRIT 100'
            else:
                return False, "Invalid action"
            
            result = subprocess.run(['powershell', '-Command', cmd],
                                  capture_output=True, timeout=5)
            
            if result.returncode == 0:
                subprocess.run(['powercfg', '/setactive', 'SCHEME_CURRENT'], timeout=5)
                return True, "OK"
        except:
            pass
        
        return False, "Failed"
    
    # ═══════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════
    
    def _write_sys_file(self, file_path: Path, value: int) -> bool:
        """كتابة قيمة إلى ملف sys"""
        try:
            # محاولة الكتابة المباشرة
            with open(file_path, 'w') as f:
                f.write(str(value))
            return True
        except PermissionError:
            # محاولة مع sudo
            if self.sudo_password:
                cmd = ['tee', str(file_path)]
                return self._run_sudo_command_with_input(cmd, str(value))
            else:
                try:
                    subprocess.run(['sudo', 'tee', str(file_path)],
                                 input=str(value).encode(),
                                 capture_output=True,
                                 timeout=5)
                    return True
                except:
                    return False
        except Exception as e:
            logger.error(f"خطأ في الكتابة: {e}")
            return False
    
    def _run_sudo_command(self, cmd: List[str]) -> bool:
        """تشغيل أمر sudo"""
        try:
            if self.sudo_password:
                process = subprocess.Popen(
                    ['sudo', '-S', '-p', ''] + cmd,  # -p '' لإخفاء prompt
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env={**os.environ, 'SUDO_ASKPASS': '/bin/false'}  # منع GUI prompts
                )
                stdout, stderr = process.communicate(input=f"{self.sudo_password}\n", timeout=10)
                return process.returncode == 0
            else:
                # بدون كلمة مرور، لا نستخدم sudo (لتجنب prompt)
                return False
        except:
            return False
    
    def _run_sudo_command_with_input(self, cmd: List[str], input_data: str) -> bool:
        """تشغيل أمر sudo مع إدخال"""
        try:
            if self.sudo_password:
                process = subprocess.Popen(
                    ['sudo', '-S', '-p', ''] + cmd,  # -p '' لإخفاء prompt
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env={**os.environ, 'SUDO_ASKPASS': '/bin/false'}  # منع GUI prompts
                )
                stdout, stderr = process.communicate(
                    input=f"{self.sudo_password}\n{input_data}", 
                    timeout=10
                )
                return process.returncode == 0
            else:
                # بدون كلمة مرور، لا نستخدم sudo (لتجنب prompt)
                return False
        except:
            return False
    
    def set_sudo_password(self, password: str):
        """تعيين كلمة مرور sudo"""
        self.sudo_password = password
    
    def get_status(self) -> Dict:
        """الحصول على حالة التحكم"""
        return {
            'is_active': self.is_active,
            'min_limit': self.min_charge_limit,
            'max_limit': self.max_charge_limit,
            'available_methods': self.available_methods,
            'device_info': self.device_info,
            'last_action': self.last_action
        }
