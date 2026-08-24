#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مراقب البطارية عبر المنصات مع تخزين مؤقت لقراءات الصحة"""

import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

import psutil

if IS_WINDOWS:
    try:
        import wmi  # type: ignore
    except ImportError:
        wmi = None

logger = logging.getLogger('BatteryGuard')

try:
    from charge_controller import ChargeController
except ImportError:  # pragma: no cover
    ChargeController = None
    logger.warning("ChargeController not available")

# عمر التخزين المؤقت لقراءة صحة البطارية (ثواني) - ملفات sysfs بطيئة وثابتة
HEALTH_CACHE_TTL = 60


def _battery_base_path() -> Optional[Path]:
    """إيجاد أول بطارية متاحة (BAT0/BAT1/battery) بدل تثبيت BAT0"""
    if not IS_LINUX:
        return None
    base = Path('/sys/class/power_supply')
    for name in ('BAT0', 'BAT1', 'BATT', 'battery'):
        p = base / name
        if p.exists():
            return p
    return None


class BatteryMonitor:
    """مراقب البطارية عبر المنصات"""

    def __init__(self, sudo_password=None):
        self.battery_info = {}
        self.charge_controller = ChargeController(sudo_password) if ChargeController else None
        self.can_control_charging = (
            self.charge_controller is not None and self.charge_controller.control_method != 'none'
        )
        self.charge_control_enabled = False
        self.min_charge_limit = 40
        self.max_charge_limit = 80

        # تخزين مؤقت لصحة البطارية
        self._health_cache: Optional[Dict] = None
        self._health_cache_time = 0.0

    def set_sudo_password(self, password: str):
        """تعيين كلمة مرور sudo"""
        if self.charge_controller:
            self.charge_controller.set_sudo_password(password)

    def invalidate_health_cache(self):
        """إجبار قراءة صحة جديدة عند التحديث التالي"""
        self._health_cache_time = 0.0

    # ──────────────────────────────────────────────────────────────

    def detect_charging_control(self) -> bool:
        """الكشف عن إمكانية التحكم في الشحن"""
        if IS_WINDOWS:
            if wmi:
                try:
                    wmi.WMI()
                    return True
                except Exception:
                    return False
            return False
        elif IS_LINUX:
            bat = _battery_base_path()
            if bat is None:
                return False
            return any(
                (bat / f).exists() for f in (
                    'charge_control_end_threshold',
                    'charge_stop_threshold',
                )
            )
        return False

    def get_battery_status(self) -> Dict:
        """الحصول على حالة البطارية الحالية"""
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return {'percent': 0, 'is_charging': False, 'time_left': None,
                        'available': False, 'power_draw': 0}

            power_draw = 0.0
            voltage = 0.0
            current = 0.0

            if IS_LINUX:
                try:
                    bat_path = _battery_base_path()
                    if bat_path is not None:
                        power_now = bat_path / 'power_now'
                        voltage_now = bat_path / 'voltage_now'
                        current_now = bat_path / 'current_now'

                        if power_now.exists():
                            raw = int(power_now.read_text().strip())
                            power_draw = abs(raw) / 1_000_000
                        elif voltage_now.exists() and current_now.exists():
                            voltage = int(voltage_now.read_text().strip()) / 1_000_000
                            current = int(current_now.read_text().strip()) / 1_000_000
                            power_draw = abs(voltage * current)
                except (OSError, ValueError) as e:
                    logger.debug(f"Linux power read: {e}")

            elif IS_WINDOWS:
                # لا توجد طريقة موثوقة لقراءة الاستهلاك اللحظي عبر WMI؛
                # نُبقي القيمة صفراً بدل رقم مفبرك سابقاً.
                pass

            time_left = None
            if battery.secsleft > 0 and battery.secsleft != psutil.POWER_TIME_UNLIMITED:
                time_left = battery.secsleft

            return {
                'percent': int(battery.percent),
                'is_charging': bool(battery.power_plugged),
                'time_left': time_left,
                'available': True,
                'power_draw': round(power_draw, 2),
                'voltage': round(voltage, 2),
                'current': round(abs(current), 2),
            }
        except Exception as e:
            logger.error(f"خطأ في قراءة حالة البطارية: {e}")
            return {'percent': 0, 'is_charging': False, 'time_left': None,
                    'available': False, 'power_draw': 0}

    # ──────────────────────────────────────────────────────────────

    def enable_charge_control(self, min_charge: int, max_charge: int) -> bool:
        """تفعيل التحكم التلقائي في الشحن"""
        self.charge_control_enabled = True
        self.min_charge_limit = min_charge
        self.max_charge_limit = max_charge

        if self.charge_controller:
            success, message = self.charge_controller.enable_control(min_charge, max_charge)
            logger.info(f"تفعيل التحكم: {message}")
            return success
        logger.warning("التحكم غير متاح - سيتم استخدام الإشعارات فقط")
        return False

    def disable_charge_control(self):
        """إيقاف التحكم التلقائي"""
        self.charge_control_enabled = False
        if self.charge_controller:
            self.charge_controller.disable_control()
        logger.info("تم إيقاف التحكم في الشحن")

    def check_charge_limits(self, current_percent: int, is_charging: bool) -> Dict:
        """التحقق من حدود الشحن وإرجاع الإجراء المطلوب"""
        if not self.charge_control_enabled:
            return {'action': 'none'}

        if self.charge_controller and self.charge_controller.is_active:
            action = self.charge_controller.check_and_control(current_percent, is_charging)
            if action:
                return action

        min_limit = self.min_charge_limit
        max_limit = self.max_charge_limit

        if is_charging and current_percent >= max_limit:
            return {
                'action': 'stop_charging',
                'message': f'تم الوصول للحد الأقصى ({max_limit}%)',
                'should_notify': True,
            }
        elif not is_charging and current_percent <= min_limit:
            return {
                'action': 'start_charging',
                'message': f'الوصول للحد الأدنى ({min_limit}%)',
                'should_notify': True,
            }
        return {'action': 'none'}

    # ──────────────────────────────────────────────────────────────

    def get_battery_health(self) -> Dict:
        """معلومات صحة البطارية مع تخزين مؤقت لتقليل قراءات sysfs المتكررة"""
        now = time.monotonic()
        if self._health_cache is not None and (now - self._health_cache_time) < HEALTH_CACHE_TTL:
            return dict(self._health_cache)

        health_info = {
            'design_capacity': 0,
            'full_capacity': 0,
            'health_percentage': 100,
            'cycle_count': 0,
        }

        try:
            if IS_LINUX:
                bat_path = _battery_base_path()
                if bat_path is not None:
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
                                health_info['health_percentage'] = min(100, int(full / design * 100))
                    except (OSError, ValueError) as e:
                        logger.debug(f"Linux capacity read: {e}")

                    try:
                        cycle_file = bat_path / 'cycle_count'
                        if cycle_file.exists():
                            health_info['cycle_count'] = int(cycle_file.read_text().strip())
                        else:
                            uevent_file = bat_path / 'uevent'
                            if uevent_file.exists():
                                content = uevent_file.read_text()
                                for line in content.split('\n'):
                                    if 'CYCLE_COUNT' in line and '=' in line:
                                        health_info['cycle_count'] = int(line.split('=')[1])
                    except (OSError, ValueError) as e:
                        logger.debug(f"Linux cycle read: {e}")

            elif IS_WINDOWS:
                health_info = self._get_windows_health(health_info)

        except Exception as e:
            logger.error(f"خطأ في قراءة صحة البطارية: {e}")

        self._health_cache = dict(health_info)
        self._health_cache_time = now
        return health_info

    def _get_windows_health(self, health_info: Dict) -> Dict:
        """قراءة صحة البطارية على Windows عبر powercfg ثم WMI كبديل"""
        import subprocess
        import tempfile
        import xml.etree.ElementTree as ET

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
                temp_file = f.name

            result = subprocess.run(
                ['powercfg', '/batteryreport', '/output', temp_file, '/xml'],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )

            if result.returncode == 0 and Path(temp_file).exists():
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
                        health_info['full_capacity'] / health_info['design_capacity'] * 100))
        finally:
            if temp_file:
                try:
                    Path(temp_file).unlink(missing_ok=True)
                except OSError:
                    pass

        # بديل WMI إذا فشل powercfg
        if health_info['design_capacity'] == 0 and wmi:
            try:
                w = wmi.WMI()
                for bat in w.Win32_Battery():
                    design = getattr(bat, 'DesignCapacity', 0)
                    full = getattr(bat, 'FullChargeCapacity', 0)
                    if design and full:
                        health_info['design_capacity'] = design
                        health_info['full_capacity'] = full
                        health_info['health_percentage'] = min(100, int(full / design * 100))
            except Exception as e:
                logger.debug(f"Windows WMI read: {e}")

        return health_info
