#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مراقب البطارية عبر المنصات"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

import psutil

if IS_WINDOWS:
    try:
        import wmi
    except ImportError:
        wmi = None

logger = logging.getLogger('BatteryGuard')

# استيراد نظام التحكم في الشحن
try:
    from charge_controller import ChargeController
except ImportError:
    ChargeController = None
    logger.warning("ChargeController not available")


class BatteryMonitor:
    """مراقب البطارية عبر المنصات"""
    
    def __init__(self, sudo_password=None):
        self.battery_info = {}
        self.charge_controller = ChargeController(sudo_password) if ChargeController else None
        self.can_control_charging = self.charge_controller is not None and self.charge_controller.control_method != 'none'
        self.charge_control_enabled = False
        self.min_charge_limit = 40
        self.max_charge_limit = 80
    
    def set_sudo_password(self, password: str):
        """تعيين كلمة مرور sudo"""
        if self.charge_controller:
            self.charge_controller.set_sudo_password(password)
        
    def detect_charging_control(self) -> bool:
        """الكشف عن إمكانية التحكم في الشحن"""
        if IS_WINDOWS:
            if wmi:
                try:
                    w = wmi.WMI()
                    return True
                except:
                    return False
            return False
        elif IS_LINUX:
            charge_control = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            return charge_control.exists()
        return False
    
    def get_battery_status(self) -> Dict:
        """الحصول على حالة البطارية الحالية"""
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return {'percent': 0, 'is_charging': False, 'time_left': None, 'available': False, 'power_draw': 0}
            
            # حساب استهلاك الطاقة الحقيقي
            power_draw = 0
            voltage = 0
            current = 0
            
            if IS_LINUX:
                try:
                    bat_path = Path('/sys/class/power_supply/BAT0')
                    
                    # قراءة الطاقة مباشرة
                    power_now = bat_path / 'power_now'
                    if power_now.exists():
                        power_draw = int(power_now.read_text().strip()) / 1000000
                    else:
                        # حساب من الفولت والأمبير
                        voltage_now = bat_path / 'voltage_now'
                        current_now = bat_path / 'current_now'
                        
                        if voltage_now.exists() and current_now.exists():
                            voltage = int(voltage_now.read_text().strip()) / 1000000
                            current = int(current_now.read_text().strip()) / 1000000
                            power_draw = voltage * current
                except Exception as e:
                    logger.debug(f"Linux power read: {e}")
                    
            elif IS_WINDOWS:
                try:
                    if wmi:
                        w = wmi.WMI()
                        for bat in w.Win32_Battery():
                            if hasattr(bat, 'EstimatedChargeRemaining'):
                                design_capacity = getattr(bat, 'DesignCapacity', 0)
                                if design_capacity:
                                    power_draw = design_capacity * 0.01
                except Exception as e:
                    logger.debug(f"Windows power read: {e}")
            
            # الوقت المتبقي
            time_left = None
            if battery.secsleft > 0 and battery.secsleft != psutil.POWER_TIME_UNLIMITED:
                time_left = battery.secsleft
            
            return {
                'percent': int(battery.percent),
                'is_charging': battery.power_plugged,
                'time_left': time_left,
                'available': True,
                'power_draw': round(abs(power_draw), 2),
                'voltage': round(voltage, 2),
                'current': round(abs(current), 2)
            }
        except Exception as e:
            logger.error(f"خطأ في قراءة حالة البطارية: {e}")
            return {'percent': 0, 'is_charging': False, 'time_left': None, 'available': False, 'power_draw': 0}
    
    def enable_charge_control(self, min_charge: int, max_charge: int) -> bool:
        """تفعيل التحكم التلقائي في الشحن"""
        self.charge_control_enabled = True
        self.min_charge_limit = min_charge
        self.max_charge_limit = max_charge
        
        # استخدام نظام التحكم الجديد
        if self.charge_controller:
            success, message = self.charge_controller.enable_control(min_charge, max_charge)
            logger.info(f"تفعيل التحكم: {message}")
            return success
        else:
            # تطبيق الحد الأقصى على مستوى النظام (الطريقة القديمة)
            success = self._apply_system_charge_limit(max_charge)
            
            if success:
                logger.info(f"تم تفعيل التحكم في الشحن: {min_charge}%-{max_charge}%")
            else:
                logger.warning("التحكم الكامل غير متاح - سيتم استخدام الإشعارات")
            
            return success
    
    def disable_charge_control(self):
        """إيقاف التحكم التلقائي"""
        self.charge_control_enabled = False
        
        # استخدام نظام التحكم الجديد
        if self.charge_controller:
            self.charge_controller.disable_control()
        else:
            self._apply_system_charge_limit(100)  # إعادة تعيين إلى 100%
        
        logger.info("تم إيقاف التحكم في الشحن")
    
    def _apply_system_charge_limit(self, limit: int) -> bool:
        """تطبيق حد الشحن على مستوى النظام"""
        if not self.can_control_charging:
            return False
        
        try:
            if IS_LINUX:
                # Linux: استخدام charge_control_end_threshold
                charge_control = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
                if charge_control.exists():
                    # محاولة الكتابة مباشرة
                    try:
                        with open(charge_control, 'w') as f:
                            f.write(str(limit))
                        return True
                    except PermissionError:
                        # استخدام sudo
                        result = os.system(f'echo {limit} | sudo tee {charge_control} > /dev/null 2>&1')
                        return result == 0
                
                # محاولة TLP (إذا كان مثبتاً)
                try:
                    result = os.system(f'sudo tlp setcharge {limit-5} {limit} BAT0 > /dev/null 2>&1')
                    if result == 0:
                        return True
                except:
                    pass
            
            elif IS_WINDOWS:
                # Windows: استخدام ACPI أو أدوات الشركة المصنعة
                try:
                    # محاولة استخدام powercfg
                    import subprocess
                    
                    # تعيين حد الشحن عبر ACPI
                    result = subprocess.run(
                        ['powershell', '-Command', 
                         f'(Get-WmiObject -Namespace root/WMI -Class BatteryFullChargedCapacity).FullChargedCapacity = {limit}'],
                        capture_output=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        return True
                    
                    # محاولة استخدام ASUS Battery Health Charging
                    asus_path = Path('C:/Program Files (x86)/ASUS/ATK Package/ATK Hotkey/HControl.exe')
                    if asus_path.exists():
                        os.system(f'"{asus_path}" /battery {limit}')
                        return True
                    
                    # محاولة Lenovo Conservation Mode
                    lenovo_reg = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Lenovo\\SmartBattery'
                    try:
                        import winreg
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                           'SOFTWARE\\Lenovo\\SmartBattery', 
                                           0, winreg.KEY_SET_VALUE)
                        winreg.SetValueEx(key, 'ChargeThreshold', 0, winreg.REG_DWORD, limit)
                        winreg.CloseKey(key)
                        return True
                    except:
                        pass
                    
                except Exception as e:
                    logger.debug(f"Windows charge control: {e}")
        
        except Exception as e:
            logger.error(f"خطأ في تطبيق حد الشحن: {e}")
        
        return False
    
    def check_charge_limits(self, current_percent: int, is_charging: bool) -> Dict:
        """التحقق من حدود الشحن وإرجاع الإجراء المطلوب"""
        if not hasattr(self, 'charge_control_enabled') or not self.charge_control_enabled:
            return {'action': 'none'}
        
        # استخدام نظام التحكم الجديد
        if self.charge_controller and self.charge_controller.is_active:
            action = self.charge_controller.check_and_control(current_percent, is_charging)
            if action:
                return action
        
        # الطريقة القديمة (للإشعارات فقط)
        min_limit = getattr(self, 'min_charge_limit', 40)
        max_limit = getattr(self, 'max_charge_limit', 80)
        
        if is_charging and current_percent >= max_limit:
            # يجب إيقاف الشحن
            return {
                'action': 'stop_charging',
                'message': f'تم الوصول للحد الأقصى ({max_limit}%)',
                'should_notify': True
            }
        elif not is_charging and current_percent <= min_limit:
            # يجب بدء الشحن
            return {
                'action': 'start_charging',
                'message': f'الوصول للحد الأدنى ({min_limit}%)',
                'should_notify': True
            }
        
        return {'action': 'none'}
    
    def get_battery_health(self) -> Dict:
        """الحصول على معلومات صحة البطارية"""
        health_info = {
            'design_capacity': 0,
            'full_capacity': 0,
            'health_percentage': 100,
            'cycle_count': 0
        }
        
        try:
            if IS_LINUX:
                bat_path = Path('/sys/class/power_supply/BAT0')
                if bat_path.exists():
                    # قراءة السعة
                    try:
                        design_file = bat_path / 'energy_full_design'
                        full_file = bat_path / 'energy_full'
                        
                        if not design_file.exists():
                            design_file = bat_path / 'charge_full_design'
                            full_file = bat_path / 'charge_full'
                        
                        if design_file.exists() and full_file.exists():
                            design = int(design_file.read_text().strip())
                            full = int(full_file.read_text().strip())
                            
                            health_info['design_capacity'] = design / 1000
                            health_info['full_capacity'] = full / 1000
                            
                            if design > 0:
                                health_info['health_percentage'] = min(100, int((full / design) * 100))
                    except Exception as e:
                        logger.debug(f"Linux capacity read: {e}")
                    
                    # قراءة دورات الشحن
                    try:
                        cycle_file = bat_path / 'cycle_count'
                        if cycle_file.exists():
                            health_info['cycle_count'] = int(cycle_file.read_text().strip())
                        else:
                            # محاولة قراءة من uevent
                            uevent_file = bat_path / 'uevent'
                            if uevent_file.exists():
                                content = uevent_file.read_text()
                                for line in content.split('\n'):
                                    if 'CYCLE_COUNT' in line:
                                        health_info['cycle_count'] = int(line.split('=')[1])
                    except Exception as e:
                        logger.debug(f"Linux cycle read: {e}")
            
            elif IS_WINDOWS:
                try:
                    import subprocess
                    import tempfile
                    import xml.etree.ElementTree as ET
                    
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
                        temp_file = f.name
                    
                    try:
                        result = subprocess.run(
                            ['powercfg', '/batteryreport', '/output', temp_file, '/xml'],
                            capture_output=True,
                            timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
                        )
                        
                        if result.returncode == 0 and os.path.exists(temp_file):
                            tree = ET.parse(temp_file)
                            root = tree.getroot()
                            
                            for battery in root.findall('.//Battery'):
                                design = battery.find('.//DesignCapacity')
                                full = battery.find('.//FullChargeCapacity')
                                cycles = battery.find('.//CycleCount')
                                
                                if design is not None and design.text:
                                    health_info['design_capacity'] = int(design.text)
                                if full is not None and full.text:
                                    health_info['full_capacity'] = int(full.text)
                                if cycles is not None and cycles.text:
                                    health_info['cycle_count'] = int(cycles.text)
                            
                            if health_info['design_capacity'] > 0:
                                health_info['health_percentage'] = min(100, int(
                                    (health_info['full_capacity'] / health_info['design_capacity']) * 100
                                ))
                    finally:
                        try:
                            if os.path.exists(temp_file):
                                os.unlink(temp_file)
                        except:
                            pass
                            
                except Exception as e:
                    logger.debug(f"Windows powercfg read: {e}")
                
                # محاولة WMI كبديل
                if health_info['design_capacity'] == 0 and wmi:
                    try:
                        w = wmi.WMI()
                        for bat in w.Win32_Battery():
                            design = getattr(bat, 'DesignCapacity', 0)
                            full = getattr(bat, 'FullChargeCapacity', 0)
                            
                            if design and full:
                                health_info['design_capacity'] = design
                                health_info['full_capacity'] = full
                                health_info['health_percentage'] = min(100, int((full / design) * 100))
                    except Exception as e:
                        logger.debug(f"Windows WMI read: {e}")
        
        except Exception as e:
            logger.error(f"خطأ في قراءة صحة البطارية: {e}")
        
        return health_info
