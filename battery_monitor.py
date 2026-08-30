#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مراقب البطارية عبر المنصات - BatteryGuardAI

مسؤوليات هذه الطبقة:
- قراءة الحالة اللحظية بقراءات محدودة بمهلة (`hardware_capability`) حتى لا
  يتجمّد خيط المراقبة على عتاد لا يستجيب.
- الحكم بصدق على صلاحية القياس: بطارية تُبلّغ بصفر شحن وصفر جهد ليست
  «بطارية فارغة»، بل بطارية لا تُبلّغ، ولا يجوز بناء تنبيهات عليها.
- الصحة الحقيقية من العتاد، مع `None` صريحة حين لا يوفّرها العتاد بدل رقم
  مطمئن مختلق.
- التحكم في الشحن عبر `ChargeController`، ولا يُعلن النجاح إلا بعد قراءة
  العتبة من العتاد للتأكد من قبولها.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import psutil

import hardware_capability as hw
from battery_science import state_of_health

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

if IS_WINDOWS:
    try:
        import wmi  # type: ignore
    except ImportError:
        wmi = None
else:
    wmi = None

logger = logging.getLogger('BatteryGuard')

try:
    from charge_controller import ChargeController
except ImportError:  # pragma: no cover
    ChargeController = None
    logger.warning("ChargeController غير متاح")

#: عمر التخزين المؤقت لقراءة الصحة (ثواني) - قيم بطيئة التغيّر
HEALTH_CACHE_TTL = 60

#: خرائط حالة الشاحن كما يعرضها sysfs إلى مفاتيح الترجمة
STATUS_KEYS = {
    'charging': 'status.charging',
    'discharging': 'status.discharging',
    'full': 'status.full',
    'not charging': 'status.not_charging',
}


def _battery_base_path() -> Optional[Path]:
    """
    مسار أول بطارية حقيقية. تبقى الدالة هنا لأن الاختبارات والوحدات الأخرى
    تعتمد عليها، والتنفيذ الفعلي في `hardware_capability`.
    """
    return hw.find_battery_path()


class BatteryMonitor:
    """مراقب البطارية عبر المنصات"""

    def __init__(self, sudo_password=None):
        self.battery_info: Dict = {}
        self.capability = hw.probe()

        self.charge_controller = ChargeController(sudo_password) if ChargeController else None
        self.can_control_charging = self.capability.can_control and (
            self.charge_controller is not None
            and self.charge_controller.control_method != 'none'
        )
        self.charge_control_enabled = False
        self.control_verified = False
        self.last_control_error: Optional[Dict] = None

        self.min_charge_limit = 40
        self.max_charge_limit = 80

        self._health_cache: Optional[Dict] = None
        self._health_cache_time = 0.0

    # ── الإعداد ─────────────────────────────────────────────

    def set_sudo_password(self, password: str):
        if self.charge_controller:
            self.charge_controller.set_sudo_password(password)

    def invalidate_health_cache(self):
        """إجبار قراءة صحة جديدة عند الاستدعاء التالي"""
        self._health_cache_time = 0.0

    def refresh_capability(self) -> Dict:
        """إعادة فحص العتاد (بعد تحميل سوّاقة أو استئناف من نوم)"""
        hw.clear_stuck_paths()
        self.capability = hw.probe(force=True)
        self.can_control_charging = self.capability.can_control and (
            self.charge_controller is not None
            and self.charge_controller.control_method != 'none'
        )
        return self.capability.as_dict()

    def detect_charging_control(self) -> bool:
        """هل يوجد مسار تحكم فعلي قابل للتحقق على هذا الجهاز"""
        return self.capability.can_control

    # ── الحالة اللحظية ──────────────────────────────────────

    def get_battery_status(self) -> Dict:
        """
        حالة البطارية الآن. الحقول الجديدة المهمة:
        - `reporting`: هل القياس صالح للاعتماد عليه في التنبيهات.
        - `temperature` / `temp_assumed`: حرارة البطارية أو غيابها الصريح.
        - `status_key`: مفتاح ترجمة حالة الشاحن كما يقولها العتاد.
        """
        empty = {
            'percent': 0, 'is_charging': False, 'time_left': None,
            'available': False, 'reporting': False, 'power_draw': 0.0,
            'voltage': 0.0, 'current': 0.0, 'temperature': None,
            'temp_assumed': True, 'status_key': 'status.no_battery',
        }

        try:
            battery = psutil.sensors_battery()
        except Exception as e:
            logger.error(f"تعذّرت قراءة حالة البطارية: {e}")
            return dict(empty)

        if battery is None:
            return dict(empty)

        percent = int(max(0, min(100, battery.percent)))
        is_charging = bool(battery.power_plugged)

        voltage = current = power_draw = 0.0
        raw_status = ''
        bat_path = hw.find_battery_path() if IS_LINUX else None

        if bat_path is not None:
            raw_status = (hw.read_text_bounded(bat_path / 'status') or '').strip()
            micro_power = hw.read_int_bounded(bat_path / 'power_now')
            micro_voltage = hw.read_int_bounded(bat_path / 'voltage_now')
            micro_current = hw.read_int_bounded(bat_path / 'current_now')

            if micro_voltage:
                voltage = micro_voltage / 1_000_000
            if micro_current:
                current = abs(micro_current) / 1_000_000
            if micro_power:
                power_draw = abs(micro_power) / 1_000_000
            elif voltage and current:
                power_draw = voltage * current

        temperature = hw.read_battery_temperature(bat_path)

        # صلاحية القياس: خلية حيّة تعرض جهداً دائماً. صفر شحن مع صفر جهد
        # يعني عتاداً لا يُبلّغ، لا بطارية فارغة.
        if bat_path is not None:
            reporting = percent > 0 or voltage > 0 or power_draw > 0
        else:
            reporting = True  # لا يمكن التحقق على هذه المنصة: لا نتّهم العتاد

        time_left = None
        if battery.secsleft is not None and battery.secsleft > 0 and \
                battery.secsleft != psutil.POWER_TIME_UNLIMITED:
            time_left = int(battery.secsleft)

        return {
            'percent': percent,
            'is_charging': is_charging,
            'time_left': time_left,
            'available': True,
            'reporting': reporting,
            'power_draw': round(power_draw, 2),
            'voltage': round(voltage, 2),
            'current': round(current, 2),
            'temperature': temperature,
            'temp_assumed': temperature is None,
            'status_key': self._status_key(raw_status, is_charging, percent, reporting),
        }

    @staticmethod
    def _status_key(raw_status: str, is_charging: bool, percent: int,
                    reporting: bool) -> str:
        """مفتاح ترجمة حالة الشاحن، مأخوذ من العتاد حين يقوله"""
        if not reporting:
            return 'status.not_reporting'
        mapped = STATUS_KEYS.get(raw_status.lower())
        if mapped:
            return mapped
        if is_charging:
            return 'status.full' if percent >= 99 else 'status.charging'
        return 'status.discharging'

    # ── التحكم في الشحن ─────────────────────────────────────

    def enable_charge_control(self, min_charge: int, max_charge: int) -> bool:
        """
        تفعيل حدود الشحن ثم التحقق بالقراءة من العتاد.
        النجاح المُعلن هنا يعني: العتاد أعاد القيمة المطلوبة فعلاً.
        """
        self.min_charge_limit = int(min_charge)
        self.max_charge_limit = int(max_charge)
        self.last_control_error = None
        self.control_verified = False

        if not self.capability.can_control:
            self.charge_control_enabled = False
            self.last_control_error = {'reason': 'no_path'}
            logger.warning("لا يوجد مسار تحكم على هذا الجهاز - وضع الإشعارات فقط")
            return False

        if self.charge_controller is None:
            self.charge_control_enabled = False
            self.last_control_error = {'reason': 'no_path'}
            return False

        self.charge_control_enabled = True
        success, message = self.charge_controller.enable_control(min_charge, max_charge)
        logger.info(f"تفعيل التحكم: {message}")

        verified, detail = self._verify_thresholds(max_charge)
        self.control_verified = verified
        if not verified:
            self.last_control_error = detail
            logger.warning(f"تعذّر تأكيد ضبط الحدود: {detail}")
        return verified

    def _verify_thresholds(self, expected_max: int) -> tuple:
        """قراءة العتبة من العتاد بعد الكتابة"""
        thresholds = hw.read_current_thresholds()
        actual = thresholds.get('end')
        if actual is None:
            return False, {'reason': 'unreadable'}
        if abs(actual - int(expected_max)) > 1:
            return False, {'reason': 'rejected', 'actual': actual, 'expected': int(expected_max)}
        return True, {}

    def disable_charge_control(self):
        """إيقاف التحكم وإرجاع العتاد إلى سلوكه الافتراضي"""
        self.charge_control_enabled = False
        self.control_verified = False
        if self.charge_controller:
            self.charge_controller.disable_control()
        logger.info("تم إيقاف التحكم في الشحن")

    def check_charge_limits(self, current_percent: int, is_charging: bool) -> Dict:
        """الإجراء المطلوب حسب الحدود (تحكم فعلي أو تنبيه)"""
        if not self.charge_control_enabled:
            return {'action': 'none'}

        if self.charge_controller and self.charge_controller.is_active:
            action = self.charge_controller.check_and_control(current_percent, is_charging)
            if action:
                return action

        if is_charging and current_percent >= self.max_charge_limit:
            return {
                'action': 'stop_charging',
                'message_key': 'notify.ceiling_reached',
                'params': {'ceiling': self.max_charge_limit},
                'should_notify': True,
            }
        if not is_charging and current_percent <= self.min_charge_limit:
            return {
                'action': 'start_charging',
                'message_key': 'notify.floor_reached',
                'params': {'floor': self.min_charge_limit},
                'should_notify': True,
            }
        return {'action': 'none'}

    # ── الصحة ───────────────────────────────────────────────

    def get_battery_health(self) -> Dict:
        """
        صحة البطارية من العتاد. الحقول التي لا يوفّرها العتاد تعود `None`
        بشكل صريح: «غير معروف» معلومة صحيحة، و«100٪» تخمين كاذب.
        """
        now = time.monotonic()
        if self._health_cache is not None and (now - self._health_cache_time) < HEALTH_CACHE_TTL:
            return dict(self._health_cache)

        info: Dict = {
            'design_capacity': 0.0,
            'full_capacity': 0.0,
            'health_percentage': None,
            'cycle_count': None,
            # هل يمكن الوثوق بقراءة السعة (بطارية تُبلّغ فعلاً)
            'trusted': True,
            # وحدة السعة المعروضة: طاقة (mwh) أو شحنة (mah) عند غياب الجهد
            'capacity_unit': 'mwh',
        }

        try:
            if IS_LINUX:
                info = self._linux_health(info)
            elif IS_WINDOWS:
                info = self._windows_health(info)
        except Exception as e:
            logger.error(f"خطأ في قراءة صحة البطارية: {e}")

        self._health_cache = dict(info)
        self._health_cache_time = now
        return dict(info)

    @staticmethod
    def _linux_health(info: Dict) -> Dict:
        """
        السعة والدورات من sysfs بوحدتيه المحتملتين (طاقة أو شحنة).

        صدق مهم: على بطارية لا تُبلّغ (صفر جهد وصفر شحن) تكون السعة الكاملة
        مساوية للتصميمية في كثير من الأجهزة، فيخرج الحساب 100٪ وهو رقم
        مطمئن كاذب. في هذه الحالة تبقى الصحة غير معروفة.
        """
        bat = hw.find_battery_path()
        if bat is None:
            return info

        voltage = hw.read_int_bounded(bat / 'voltage_now') or 0
        capacity = hw.read_int_bounded(bat / 'capacity') or 0
        info['trusted'] = bool(voltage > 0 or capacity > 0)

        # sysfs يعرض إما طاقة (µWh) أو شحنة (µAh). الصحة تُحسب بنفس الوحدة،
        # أما العرض فيحتاج طاقة، فتُحوَّل الشحنة بجهد التصميم.
        design_file, full_file, is_energy = None, None, True
        for design_name, full_name, energy in (
                ('energy_full_design', 'energy_full', True),
                ('charge_full_design', 'charge_full', False)):
            if (bat / design_name).exists() and (bat / full_name).exists():
                design_file, full_file, is_energy = bat / design_name, bat / full_name, energy
                break

        if design_file is not None:
            design = hw.read_int_bounded(design_file)
            full = hw.read_int_bounded(full_file)
            if design and full:
                if is_energy:
                    info['design_capacity'] = design / 1000.0     # µWh ← mWh
                    info['full_capacity'] = full / 1000.0
                else:
                    volts = (hw.read_int_bounded(bat / 'voltage_min_design')
                             or hw.read_int_bounded(bat / 'voltage_now') or 0) / 1_000_000
                    if volts > 0:
                        # (µAh ← Ah) × فولت ← واط·ساعة، ثم إلى ملي واط·ساعة
                        info['design_capacity'] = design / 1_000_000 * volts * 1000
                        info['full_capacity'] = full / 1_000_000 * volts * 1000
                    else:
                        info['design_capacity'] = design / 1000.0   # µAh ← mAh
                        info['full_capacity'] = full / 1000.0
                        info['capacity_unit'] = 'mah'
                if info['trusted']:
                    info['health_percentage'] = state_of_health(full, design)

        cycles = hw.read_int_bounded(bat / 'cycle_count')
        # صفر يعني «لا يبلّغ العتاد» على معظم الأجهزة، لا صفر دورة حقيقية
        info['cycle_count'] = cycles if cycles and cycles > 0 else None
        return info

    def _windows_health(self, info: Dict) -> Dict:
        """صحة البطارية على ويندوز عبر powercfg ثم WMI كبديل"""
        import subprocess
        import tempfile
        import xml.etree.ElementTree as ET

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
                temp_file = f.name

            result = subprocess.run(
                ['powercfg', '/batteryreport', '/output', temp_file, '/xml'],
                capture_output=True, timeout=15,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )

            if result.returncode == 0 and Path(temp_file).exists():
                root = ET.parse(temp_file).getroot()
                for battery in root.findall('.//Battery'):
                    design = battery.find('.//DesignCapacity')
                    full = battery.find('.//FullChargeCapacity')
                    cycles = battery.find('.//CycleCount')

                    if design is not None and design.text:
                        info['design_capacity'] = float(design.text)
                    if full is not None and full.text:
                        info['full_capacity'] = float(full.text)
                    if cycles is not None and cycles.text and int(cycles.text) > 0:
                        info['cycle_count'] = int(cycles.text)

                info['health_percentage'] = state_of_health(
                    info['full_capacity'], info['design_capacity'])
        except (OSError, subprocess.SubprocessError, ET.ParseError) as e:
            logger.debug(f"powercfg غير متاح أو فشل: {e}")
        finally:
            if temp_file:
                try:
                    Path(temp_file).unlink(missing_ok=True)
                except OSError:
                    pass

        if not info['design_capacity'] and wmi:
            try:
                w = wmi.WMI()
                for bat in w.Win32_Battery():
                    design = getattr(bat, 'DesignCapacity', 0)
                    full = getattr(bat, 'FullChargeCapacity', 0)
                    if design and full:
                        info['design_capacity'] = float(design)
                        info['full_capacity'] = float(full)
                        info['health_percentage'] = state_of_health(full, design)
            except Exception as e:
                logger.debug(f"تعذّرت قراءة WMI: {e}")

        return info

    # ── التشخيص ─────────────────────────────────────────────

    def diagnostics(self) -> Dict:
        """
        كل ما قُرئ فعلاً من العتاد، بما فيه ما تعذّرت قراءته. هذا ما يُعرض
        في لوحة التشخيص وما يُصدَّر في تقرير المشكلة.
        """
        status = self.get_battery_status()
        health = self.get_battery_health()
        return {
            'capability': self.capability.as_dict(),
            'status': status,
            'health': health,
            'thresholds': hw.read_current_thresholds(),
            'control': {
                'enabled': self.charge_control_enabled,
                'verified': self.control_verified,
                'last_error': self.last_control_error,
                'method': getattr(self.charge_controller, 'control_method', 'none'),
            },
        }
