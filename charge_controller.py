#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نظام التحكم الفعلي في الشحن - Windows & Linux"""

import sys
import os
import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import psutil

# استيراد النظام المتقدم
try:
    from charge_control_advanced import AdvancedChargeController
    USE_ADVANCED = True
except ImportError:
    USE_ADVANCED = False

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

logger = logging.getLogger('BatteryGuard')


class ChargeController:
    """التحكم الفعلي في الشحن عبر المنصات"""
    
    def __init__(self, sudo_password=None):
        self.is_active = False
        self.max_charge_limit = 80
        self.min_charge_limit = 40
        self.sudo_password = sudo_password
        self.last_action = None
        self.last_action_time = 0
        
        # استخدام النظام المتقدم إذا كان متاحاً
        if USE_ADVANCED:
            self._advanced = AdvancedChargeController(sudo_password)
            # تعيين control_method بناءً على الطرق المتاحة
            if self._advanced.available_methods:
                self.control_method = self._advanced.available_methods[0]
            else:
                self.control_method = 'none'
            logger.info("✅ تم تفعيل نظام التحكم المتقدم")
            logger.info(f"📱 الطرق المتاحة: {', '.join(self._advanced.available_methods)}")
        else:
            # اكتشاف طريقة التحكم المتاحة
            self.control_method = self._detect_control_method()
            logger.info(f"طريقة التحكم المكتشفة: {self.control_method}")
    
    def _detect_control_method(self) -> str:
        """اكتشاف طريقة التحكم في الشحن المتاحة - محسّن"""
        methods = []
        
        if IS_LINUX:
            # 1. التحقق من charge_control_end_threshold (الأفضل)
            threshold_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            if threshold_path.exists():
                methods.append('linux_threshold')
            
            # 2. التحقق من ASUS Battery Health
            asus_start = Path('/sys/class/power_supply/BAT0/charge_control_start_threshold')
            asus_end = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            if asus_start.exists() and asus_end.exists():
                methods.append('linux_asus')
            
            # 3. التحقق من TLP
            try:
                result = subprocess.run(['which', 'tlp'], capture_output=True, timeout=2)
                if result.returncode == 0:
                    methods.append('linux_tlp')
            except:
                pass
            
            # 4. التحقق من laptop-mode-tools
            try:
                result = subprocess.run(['which', 'laptop_mode'], capture_output=True, timeout=2)
                if result.returncode == 0:
                    methods.append('linux_laptop_mode')
            except:
                pass
            
            # 5. استخدام ACPI calls
            acpi_call = Path('/proc/acpi/call')
            if acpi_call.exists():
                methods.append('linux_acpi')
            
            # 6. استخدام upower (للإشعارات فقط)
            try:
                result = subprocess.run(['which', 'upower'], capture_output=True, timeout=2)
                if result.returncode == 0:
                    methods.append('linux_upower')
            except:
                pass
            
            # إرجاع أفضل طريقة متاحة
            if methods:
                logger.info(f"الطرق المتاحة: {', '.join(methods)}")
                return methods[0]
            
            return 'linux_notification_only'
        
        elif IS_WINDOWS:
            # 1. التحقق من ASUS Battery Health Charging
            asus_path = Path('C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe')
            if asus_path.exists():
                return 'windows_asus'
            
            # 2. التحقق من Lenovo Vantage
            lenovo_path = Path('C:/Program Files (x86)/Lenovo/VantageService/3.0.23.0/LenovoVantageService.exe')
            if lenovo_path.exists():
                return 'windows_lenovo'
            
            # 3. التحقق من Dell Power Manager
            dell_path = Path('C:/Program Files/Dell/DellPowerManager/DellPowerManager.exe')
            if dell_path.exists():
                return 'windows_dell'
            
            # 4. استخدام WMI/ACPI
            return 'windows_wmi'
        
        return 'none'
    
    def set_sudo_password(self, password: str):
        """تعيين كلمة مرور sudo لـ Linux"""
        self.sudo_password = password
        if USE_ADVANCED and hasattr(self, '_advanced'):
            self._advanced.set_sudo_password(password)
    
    def enable_control(self, min_limit: int, max_limit: int) -> Tuple[bool, str]:
        """تفعيل التحكم في الشحن"""
        self.min_charge_limit = min_limit
        self.max_charge_limit = max_limit
        self.is_active = True
        
        # استخدام النظام المتقدم إذا كان متاحاً
        if USE_ADVANCED and hasattr(self, '_advanced'):
            return self._advanced.enable_control(min_limit, max_limit)
        
        # تطبيق الحد الأقصى على مستوى النظام
        success, message = self._apply_charge_limit(max_limit)
        
        if success:
            logger.info(f"تم تفعيل التحكم: {min_limit}%-{max_limit}%")
            return True, f"تم التفعيل بنجاح باستخدام {self.control_method}"
        else:
            logger.warning(f"فشل التفعيل الكامل: {message}")
            return False, f"تم الحفظ - {message}"
    
    def disable_control(self) -> Tuple[bool, str]:
        """إيقاف التحكم في الشحن"""
        self.is_active = False
        
        # استخدام النظام المتقدم إذا كان متاحاً
        if USE_ADVANCED and hasattr(self, '_advanced'):
            return self._advanced.disable_control()
        
        success, message = self._apply_charge_limit(100)
        logger.info("تم إيقاف التحكم في الشحن")
        return success, "تم إيقاف التحكم"
    
    def check_and_control(self, current_percent: int, is_charging: bool) -> Optional[Dict]:
        """فحص والتحكم في الشحن بناءً على المستوى الحالي - محسّن"""
        if not self.is_active:
            return None
        
        # استخدام النظام المتقدم إذا كان متاحاً
        if USE_ADVANCED and hasattr(self, '_advanced'):
            return self._advanced.check_and_control(current_percent, is_charging)
        
        # منع الإجراءات المتكررة (انتظار 30 ثانية بين الإجراءات)
        current_time = time.time()
        if current_time - self.last_action_time < 30:
            return None
        
        action_needed = None
        
        # التحقق من الحد الأقصى
        if is_charging and current_percent >= self.max_charge_limit:
            if self.last_action != 'stop_charging':
                action_needed = {
                    'action': 'stop_charging',
                    'message': f'🛑 وصلت للحد الأقصى {self.max_charge_limit}%\nافصل الشاحن الآن للحفاظ على صحة البطارية!',
                    'should_notify': True,
                    'urgency': 'critical'
                }
                
                # محاولة إيقاف الشحن بجميع الطرق المتاحة
                success = self._stop_charging_multi_method()
                
                if success:
                    self.last_action = 'stop_charging'
                    self.last_action_time = current_time
                    logger.info(f"✅ تم إيقاف الشحن عند {current_percent}%")
                    action_needed['message'] = f'✅ تم إيقاف الشحن عند {self.max_charge_limit}%'
                else:
                    logger.warning(f"⚠️ فشل إيقاف الشحن - يرجى الفصل يدوياً")
                    # إرسال إشعار قوي للمستخدم
                    action_needed['message'] = f'⚠️ لم يتمكن النظام من إيقاف الشحن\nيرجى فصل الشاحن يدوياً عند {self.max_charge_limit}%'
        
        # التحقق من الحد الأدنى
        elif not is_charging and current_percent <= self.min_charge_limit:
            if self.last_action != 'start_charging':
                action_needed = {
                    'action': 'start_charging',
                    'message': f'🔌 وصلت للحد الأدنى {self.min_charge_limit}%\nوصّل الشاحن الآن!',
                    'should_notify': True,
                    'urgency': 'normal'
                }
                
                # محاولة بدء الشحن
                success = self._start_charging_multi_method()
                
                if success:
                    self.last_action = 'start_charging'
                    self.last_action_time = current_time
                    logger.info(f"✅ تم بدء الشحن عند {current_percent}%")
                else:
                    logger.warning(f"⚠️ فشل بدء الشحن - يرجى التوصيل يدوياً")
        
        # إعادة تعيين الحالة إذا كان في النطاق الآمن
        elif self.min_charge_limit < current_percent < self.max_charge_limit:
            if self.last_action == 'stop_charging' and not is_charging:
                self.last_action = None
            elif self.last_action == 'start_charging' and is_charging:
                self.last_action = None
        
        return action_needed
    
    def _stop_charging_multi_method(self) -> bool:
        """محاولة إيقاف الشحن بجميع الطرق المتاحة"""
        methods_tried = []
        
        if IS_LINUX:
            # الطريقة 1: charge_control_end_threshold
            if self._try_linux_threshold_stop():
                logger.info("✅ نجح: linux_threshold")
                return True
            methods_tried.append('threshold')
            
            # الطريقة 2: ASUS
            if self._try_linux_asus_stop():
                logger.info("✅ نجح: linux_asus")
                return True
            methods_tried.append('asus')
            
            # الطريقة 3: TLP
            if self._try_linux_tlp_stop():
                logger.info("✅ نجح: linux_tlp")
                return True
            methods_tried.append('tlp')
            
            # الطريقة 4: ACPI
            if self._try_linux_acpi_stop():
                logger.info("✅ نجح: linux_acpi")
                return True
            methods_tried.append('acpi')
        
        elif IS_WINDOWS:
            # الطريقة 1: ASUS
            if self._try_windows_asus_stop():
                logger.info("✅ نجح: windows_asus")
                return True
            methods_tried.append('asus')
            
            # الطريقة 2: Lenovo
            if self._try_windows_lenovo_stop():
                logger.info("✅ نجح: windows_lenovo")
                return True
            methods_tried.append('lenovo')
            
            # الطريقة 3: Dell
            if self._try_windows_dell_stop():
                logger.info("✅ نجح: windows_dell")
                return True
            methods_tried.append('dell')
        
        logger.warning(f"❌ فشلت جميع الطرق: {', '.join(methods_tried)}")
        return False
    
    def _start_charging_multi_method(self) -> bool:
        """محاولة بدء الشحن بجميع الطرق المتاحة"""
        # في معظم الحالات، بدء الشحن يحدث تلقائياً عند توصيل الشاحن
        # لكن يمكن إعادة تعيين الحدود
        
        if IS_LINUX:
            if self._try_linux_threshold_start():
                return True
            if self._try_linux_asus_start():
                return True
            if self._try_linux_tlp_start():
                return True
        
        elif IS_WINDOWS:
            if self._try_windows_asus_start():
                return True
            if self._try_windows_lenovo_start():
                return True
        
        return False
    
    def _apply_charge_limit(self, limit: int) -> Tuple[bool, str]:
        """تطبيق حد الشحن على مستوى النظام"""
        if self.control_method == 'none':
            return False, "لا توجد طريقة تحكم متاحة"
        
        try:
            if self.control_method == 'linux_threshold':
                return self._linux_threshold_control(limit)
            
            elif self.control_method == 'linux_tlp':
                return self._linux_tlp_control(limit)
            
            elif self.control_method == 'linux_asus':
                return self._linux_asus_control(limit)
            
            elif self.control_method == 'linux_acpi':
                return self._linux_acpi_control(limit)
            
            elif self.control_method == 'windows_asus':
                return self._windows_asus_control(limit)
            
            elif self.control_method == 'windows_lenovo':
                return self._windows_lenovo_control(limit)
            
            elif self.control_method == 'windows_dell':
                return self._windows_dell_control(limit)
            
            elif self.control_method == 'windows_wmi':
                return self._windows_wmi_control(limit)
        
        except Exception as e:
            logger.error(f"خطأ في تطبيق حد الشحن: {e}")
            return False, str(e)
        
        return False, "طريقة غير مدعومة"
    
    def _stop_charging(self) -> bool:
        """إيقاف الشحن فعلياً"""
        try:
            if IS_LINUX:
                # طريقة 1: استخدام charge_control_end_threshold
                threshold_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
                if threshold_path.exists():
                    current_percent = psutil.sensors_battery().percent
                    return self._write_to_sys_file(threshold_path, int(current_percent))
                
                # طريقة 2: استخدام TLP
                try:
                    result = subprocess.run(
                        ['sudo', 'tlp', 'chargeonce'],
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return True
                except:
                    pass
                
                # طريقة 3: تعطيل منفذ USB-C/الشاحن مؤقتاً
                try:
                    # إيجاد منفذ الشاحن
                    ac_path = Path('/sys/class/power_supply/AC/online')
                    if ac_path.exists():
                        # لا يمكن تعطيله مباشرة، لكن يمكن تحديد الحد
                        pass
                except:
                    pass
            
            elif IS_WINDOWS:
                # طريقة 1: استخدام ASUS Battery Health Charging
                asus_path = Path('C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe')
                if asus_path.exists():
                    try:
                        subprocess.run([str(asus_path), '/battery', 'stop'], timeout=5)
                        return True
                    except:
                        pass
                
                # طريقة 2: استخدام powercfg لتعطيل الشحن
                try:
                    # تعيين حد الشحن الحالي
                    current_percent = psutil.sensors_battery().percent
                    subprocess.run(
                        ['powercfg', '/setdcvalueindex', 'SCHEME_CURRENT', 
                         'SUB_BATTERY', 'BATACTIONCRIT', str(current_percent)],
                        capture_output=True,
                        timeout=5
                    )
                    return True
                except:
                    pass
        
        except Exception as e:
            logger.error(f"خطأ في إيقاف الشحن: {e}")
        
        return False
    
    def _start_charging(self) -> bool:
        """بدء الشحن فعلياً"""
        try:
            if IS_LINUX:
                # إعادة تعيين الحد الأقصى للسماح بالشحن
                threshold_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
                if threshold_path.exists():
                    return self._write_to_sys_file(threshold_path, self.max_charge_limit)
                
                # استخدام TLP
                try:
                    result = subprocess.run(
                        ['sudo', 'tlp', 'setcharge', str(self.min_charge_limit), 
                         str(self.max_charge_limit), 'BAT0'],
                        capture_output=True,
                        timeout=5
                    )
                    return result.returncode == 0
                except:
                    pass
            
            elif IS_WINDOWS:
                # إعادة تفعيل الشحن
                asus_path = Path('C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe')
                if asus_path.exists():
                    try:
                        subprocess.run([str(asus_path), '/battery', 'start'], timeout=5)
                        return True
                    except:
                        pass
                
                # إعادة تعيين حد الشحن
                try:
                    subprocess.run(
                        ['powercfg', '/setdcvalueindex', 'SCHEME_CURRENT', 
                         'SUB_BATTERY', 'BATACTIONCRIT', str(self.max_charge_limit)],
                        capture_output=True,
                        timeout=5
                    )
                    return True
                except:
                    pass
        
        except Exception as e:
            logger.error(f"خطأ في بدء الشحن: {e}")
        
        return False
    
    # طرق التحكم المختلفة
    
    def _linux_threshold_control(self, limit: int) -> Tuple[bool, str]:
        """التحكم عبر charge_control_end_threshold"""
        threshold_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
        
        if self._write_to_sys_file(threshold_path, limit):
            return True, "تم التطبيق عبر kernel threshold"
        
        return False, "فشل الكتابة - قد تحتاج صلاحيات sudo"
    
    def _try_linux_threshold_stop(self) -> bool:
        """محاولة إيقاف الشحن عبر threshold"""
        try:
            threshold_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            if not threshold_path.exists():
                return False
            
            current_percent = int(psutil.sensors_battery().percent)
            return self._write_to_sys_file(threshold_path, current_percent)
        except:
            return False
    
    def _try_linux_threshold_start(self) -> bool:
        """محاولة بدء الشحن عبر threshold"""
        try:
            threshold_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            if not threshold_path.exists():
                return False
            
            return self._write_to_sys_file(threshold_path, self.max_charge_limit)
        except:
            return False
    
    def _try_linux_asus_stop(self) -> bool:
        """محاولة إيقاف الشحن عبر ASUS"""
        try:
            start_path = Path('/sys/class/power_supply/BAT0/charge_control_start_threshold')
            end_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            
            if not (start_path.exists() and end_path.exists()):
                return False
            
            current_percent = int(psutil.sensors_battery().percent)
            return (self._write_to_sys_file(start_path, current_percent - 1) and
                   self._write_to_sys_file(end_path, current_percent))
        except:
            return False
    
    def _try_linux_asus_start(self) -> bool:
        """محاولة بدء الشحن عبر ASUS"""
        try:
            start_path = Path('/sys/class/power_supply/BAT0/charge_control_start_threshold')
            end_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            
            if not (start_path.exists() and end_path.exists()):
                return False
            
            return (self._write_to_sys_file(start_path, self.min_charge_limit) and
                   self._write_to_sys_file(end_path, self.max_charge_limit))
        except:
            return False
    
    def _try_linux_tlp_stop(self) -> bool:
        """محاولة إيقاف الشحن عبر TLP"""
        try:
            current_percent = int(psutil.sensors_battery().percent)
            cmd = ['tlp', 'setcharge', str(current_percent - 1), str(current_percent), 'BAT0']
            
            if self.sudo_password:
                return self._run_sudo_command(cmd)
            else:
                result = subprocess.run(['sudo'] + cmd, capture_output=True, timeout=5)
                return result.returncode == 0
        except:
            return False
    
    def _try_linux_tlp_start(self) -> bool:
        """محاولة بدء الشحن عبر TLP"""
        try:
            cmd = ['tlp', 'setcharge', str(self.min_charge_limit), str(self.max_charge_limit), 'BAT0']
            
            if self.sudo_password:
                return self._run_sudo_command(cmd)
            else:
                result = subprocess.run(['sudo'] + cmd, capture_output=True, timeout=5)
                return result.returncode == 0
        except:
            return False
    
    def _try_linux_acpi_stop(self) -> bool:
        """محاولة إيقاف الشحن عبر ACPI"""
        try:
            acpi_call = Path('/proc/acpi/call')
            if not acpi_call.exists():
                return False
            
            # أوامر ACPI لإيقاف الشحن
            commands = [
                '\\_SB.PCI0.LPCB.EC0.HKEY.BCSG 1',  # ThinkPad
                '\\_SB.BAT0._BST',  # Generic
            ]
            
            for cmd in commands:
                if self._write_to_sys_file(acpi_call, cmd):
                    return True
        except:
            pass
        
        return False
    
    def _try_windows_asus_stop(self) -> bool:
        """محاولة إيقاف الشحن عبر ASUS (Windows)"""
        try:
            asus_path = Path('C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe')
            if not asus_path.exists():
                return False
            
            result = subprocess.run([str(asus_path), '/battery', 'stop'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _try_windows_asus_start(self) -> bool:
        """محاولة بدء الشحن عبر ASUS (Windows)"""
        try:
            asus_path = Path('C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe')
            if not asus_path.exists():
                return False
            
            result = subprocess.run([str(asus_path), '/battery', 'start'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _try_windows_lenovo_stop(self) -> bool:
        """محاولة إيقاف الشحن عبر Lenovo (Windows)"""
        try:
            import winreg
            key_path = r'SOFTWARE\Lenovo\SmartBattery'
            
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, 'ConservationMode', 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            return True
        except:
            return False
    
    def _try_windows_lenovo_start(self) -> bool:
        """محاولة بدء الشحن عبر Lenovo (Windows)"""
        try:
            import winreg
            key_path = r'SOFTWARE\Lenovo\SmartBattery'
            
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, 'ConservationMode', 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            return True
        except:
            return False
    
    def _try_windows_dell_stop(self) -> bool:
        """محاولة إيقاف الشحن عبر Dell (Windows)"""
        try:
            current_percent = int(psutil.sensors_battery().percent)
            cmd = f'cctk --PrimaryBattChargeCfg=Custom:{current_percent}'
            result = subprocess.run(['powershell', '-Command', cmd], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _run_sudo_command(self, cmd: List) -> bool:
        """تشغيل أمر sudo مع كلمة المرور"""
        try:
            if not self.sudo_password:
                return False
            
            process = subprocess.Popen(
                ['sudo', '-S'] + cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=f"{self.sudo_password}\n", timeout=10)
            return process.returncode == 0
        except:
            return False
    
    def _linux_tlp_control(self, limit: int) -> Tuple[bool, str]:
        """التحكم عبر TLP"""
        try:
            cmd = ['tlp', 'setcharge', str(limit-5), str(limit), 'BAT0']
            
            if self.sudo_password:
                if self._run_sudo_command(cmd):
                    return True, "تم التطبيق عبر TLP"
            else:
                result = subprocess.run(['sudo'] + cmd, capture_output=True, timeout=10)
                if result.returncode == 0:
                    return True, "تم التطبيق عبر TLP"
        
        except Exception as e:
            logger.error(f"TLP control error: {e}")
        
        return False, "فشل TLP - تحقق من التثبيت والصلاحيات"
    
    def _linux_asus_control(self, limit: int) -> Tuple[bool, str]:
        """التحكم عبر ASUS Battery Health"""
        start_path = Path('/sys/class/power_supply/BAT0/charge_control_start_threshold')
        end_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
        
        start_success = self._write_to_sys_file(start_path, limit - 5)
        end_success = self._write_to_sys_file(end_path, limit)
        
        if start_success and end_success:
            return True, "تم التطبيق عبر ASUS Battery Health"
        
        return False, "فشل ASUS control"
    
    def _linux_acpi_control(self, limit: int) -> Tuple[bool, str]:
        """التحكم عبر ACPI calls"""
        try:
            # محاولة استخدام acpi_call
            acpi_call = Path('/proc/acpi/call')
            if acpi_call.exists():
                # أوامر ACPI لبعض الأجهزة الشائعة
                commands = [
                    f'\\_SB.PCI0.LPCB.EC0.HKEY.BCTG {limit:02X}',  # ThinkPad
                    f'\\_SB.BAT0._BTP {limit}',  # Generic
                ]
                
                for cmd in commands:
                    if self._write_to_sys_file(acpi_call, cmd):
                        return True, "تم التطبيق عبر ACPI"
        
        except Exception as e:
            logger.error(f"ACPI control error: {e}")
        
        return False, "ACPI غير متاح"
    
    def _windows_asus_control(self, limit: int) -> Tuple[bool, str]:
        """التحكم عبر ASUS Battery Health Charging"""
        asus_path = Path('C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe')
        
        try:
            result = subprocess.run(
                [str(asus_path), '/battery', str(limit)],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, "تم التطبيق عبر ASUS Battery Health"
        
        except Exception as e:
            logger.error(f"ASUS control error: {e}")
        
        return False, "فشل ASUS control"
    
    def _windows_lenovo_control(self, limit: int) -> Tuple[bool, str]:
        """التحكم عبر Lenovo Conservation Mode"""
        try:
            import winreg
            
            # تعيين حد الشحن في Registry
            key_path = r'SOFTWARE\Lenovo\SmartBattery'
            
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE
                )
                
                winreg.SetValueEx(key, 'ChargeThreshold', 0, winreg.REG_DWORD, limit)
                winreg.SetValueEx(key, 'ConservationMode', 0, winreg.REG_DWORD, 1 if limit < 100 else 0)
                winreg.CloseKey(key)
                
                return True, "تم التطبيق عبر Lenovo Vantage"
            
            except WindowsError:
                # محاولة عبر PowerShell
                ps_cmd = f'''
                $path = "HKLM:\\{key_path}"
                Set-ItemProperty -Path $path -Name "ChargeThreshold" -Value {limit}
                Set-ItemProperty -Path $path -Name "ConservationMode" -Value {1 if limit < 100 else 0}
                '''
                
                result = subprocess.run(
                    ['powershell', '-Command', ps_cmd],
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    return True, "تم التطبيق عبر Lenovo Registry"
        
        except Exception as e:
            logger.error(f"Lenovo control error: {e}")
        
        return False, "فشل Lenovo control - قد تحتاج صلاحيات إدارية"
    
    def _windows_dell_control(self, limit: int) -> Tuple[bool, str]:
        """التحكم عبر Dell Power Manager"""
        try:
            # استخدام Dell Command | Configure
            dell_cmd = f'cctk --PrimaryBattChargeCfg=Custom:{limit}'
            
            result = subprocess.run(
                ['powershell', '-Command', dell_cmd],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, "تم التطبيق عبر Dell Power Manager"
        
        except Exception as e:
            logger.error(f"Dell control error: {e}")
        
        return False, "فشل Dell control"
    
    def _windows_wmi_control(self, limit: int) -> Tuple[bool, str]:
        """التحكم عبر WMI/ACPI"""
        try:
            # محاولة عبر WMI
            ps_cmd = f'''
            $battery = Get-WmiObject -Namespace root/WMI -Class BatteryFullChargedCapacity
            $battery.FullChargedCapacity = {limit}
            $battery.Put()
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, "تم التطبيق عبر WMI"
            
            # محاولة عبر powercfg
            result = subprocess.run(
                ['powercfg', '/setdcvalueindex', 'SCHEME_CURRENT', 
                 'SUB_BATTERY', 'BATACTIONCRIT', str(limit)],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                subprocess.run(['powercfg', '/setactive', 'SCHEME_CURRENT'], timeout=5)
                return True, "تم التطبيق عبر powercfg"
        
        except Exception as e:
            logger.error(f"WMI control error: {e}")
        
        return False, "فشل WMI control - قد لا يكون مدعوماً"
    
    def _write_to_sys_file(self, file_path: Path, value: int) -> bool:
        """كتابة قيمة إلى ملف sys"""
        try:
            # محاولة الكتابة المباشرة
            with open(file_path, 'w') as f:
                f.write(str(value))
            return True
        
        except PermissionError:
            # استخدام sudo
            if self.sudo_password:
                try:
                    cmd = ['sudo', '-S', 'tee', str(file_path)]
                    process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate(
                        input=f"{self.sudo_password}\n{value}",
                        timeout=5
                    )
                    return process.returncode == 0
                except:
                    pass
            
            # محاولة بدون كلمة مرور (إذا كان sudo بدون كلمة مرور)
            try:
                result = subprocess.run(
                    ['sudo', 'tee', str(file_path)],
                    input=str(value),
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0
            except:
                pass
        
        except Exception as e:
            logger.error(f"خطأ في الكتابة إلى {file_path}: {e}")
        
        return False
    
    def get_status(self) -> Dict:
        """الحصول على حالة التحكم"""
        return {
            'is_active': self.is_active,
            'control_method': self.control_method,
            'max_limit': self.max_charge_limit,
            'min_limit': self.min_charge_limit,
            'last_action': self.last_action,
            'can_control': self.control_method != 'none'
        }
