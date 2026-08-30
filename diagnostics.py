#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
محرك التشخيص العميق - BatteryGuardAI

يجيب على سؤال واحد بدقة: ما حالة منظومة الطاقة في هذا الجهاز بالضبط، وما
الذي يمنع التطبيق من فعل ما يفعله عادةً؟

يعمل في كل الحالات، بما فيها:
- لا توجد بطارية في العتاد أصلاً (جهاز مكتبي أو بطارية مفصولة).
- بطارية موجودة لكن وحدة التحكم المدمجة لا تُبلّغ.
- بطارية تُبلّغ بقيم غير معقولة (السعة الكاملة تساوي التصميمية والشحن صفر).
- عتاد يدعم حدود الشحن لكن سوّاقة النواة غير محمّلة.

كل نتيجة (Finding) تحمل: معرّفاً ثابتاً، شدّة، مفتاح ترجمة، أدلة خام مقروءة
من النظام، خطوات معالجة، ودرجة ثقة. لا استنتاج بلا دليل مكتوب بجانبه.

المراجع المستخدمة في التصنيف مذكورة في `hardware_capability` و
`battery_science`؛ هذه الوحدة تقرأ وتستنتج ولا تخترع ثوابت.
"""

import logging
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import hardware_capability as hw

logger = logging.getLogger('BatteryGuard')

IS_LINUX = sys.platform.startswith('linux')
IS_WINDOWS = sys.platform == 'win32'

POWER_SUPPLY_ROOT = Path('/sys/class/power_supply')
DMI_ROOT = Path('/sys/class/dmi/id')
MODULES_FILE = Path('/proc/modules')

#: أنواع الهياكل المحمولة حسب مواصفة DMI (8/9/10 محمول، 14 فرعي، 31/32 قابل للتحويل)
PORTABLE_CHASSIS = {'8', '9', '10', '11', '12', '14', '30', '31', '32'}
DESKTOP_CHASSIS = {'3', '4', '5', '6', '7', '15', '16', '17', '23', '24', '28'}

#: سواقات النواة التي تعرض عتبات الشحن، مفتاحها اسم المصنّع في DMI
VENDOR_DRIVERS = {
    'lenovo': ('thinkpad_acpi',),
    'asus': ('asus_wmi', 'asus_nb_wmi'),
    'asustek': ('asus_wmi', 'asus_nb_wmi'),
    'huawei': ('huawei_wmi',),
    'msi': ('msi_ec',),
    'framework': ('cros_ec_lpcs', 'cros_ec_dev'),
    'apple': ('macsmc_power', 'applesmc'),
    'lg': ('lg_laptop',),
    'samsung': ('samsung_laptop',),
    'toshiba': ('toshiba_acpi',),
    'dell': ('dell_laptop', 'dell_smbios'),
    'hp': ('hp_wmi',),
    'hewlett-packard': ('hp_wmi',),
}

#: مصنّعون يضعون حدّ الشحن في BIOS ولا يعرضونه لنظام التشغيل
FIRMWARE_ONLY_VENDORS = ('hp', 'hewlett-packard')

SEVERITY_RANK = {'critical': 0, 'warning': 1, 'advice': 2, 'info': 3, 'good': 4}


# ═══════════════════════════════════════════════════════════
# نماذج البيانات
# ═══════════════════════════════════════════════════════════

@dataclass
class Reading:
    """قراءة واحدة من العتاد مع حالتها الصريحة"""
    name: str
    value: Optional[str]
    status: str          # ok | missing | unreadable | timeout
    path: str = ''

    @property
    def display(self) -> str:
        return self.value if self.status == 'ok' and self.value is not None else '—'


@dataclass
class Finding:
    """نتيجة تشخيص واحدة: ما المشكلة، بأي دليل، وما الحل"""
    id: str
    severity: str
    key: str
    params: Dict[str, object] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    remediation: List[str] = field(default_factory=list)
    confidence: int = 80

    @property
    def rank(self) -> int:
        return SEVERITY_RANK.get(self.severity, 9)


@dataclass
class DiagnosticsReport:
    """التقرير الكامل الذي تعرضه لوحة التشخيص وتُصدّره"""
    generated_at: str = ''
    environment: Dict[str, str] = field(default_factory=dict)
    batteries: List[Dict[str, object]] = field(default_factory=list)
    mains: Dict[str, object] = field(default_factory=dict)
    drivers: Dict[str, object] = field(default_factory=dict)
    thermal: Dict[str, object] = field(default_factory=dict)
    cross_check: Dict[str, object] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)
    device_mode: str = 'unknown'     # portable_with_battery | portable_no_battery
    #                                  | desktop | unknown
    grade: str = 'unknown'           # ok | degraded | impaired | unmeasurable

    @property
    def top_finding(self) -> Optional[Finding]:
        return self.findings[0] if self.findings else None

    def as_dict(self) -> Dict[str, object]:
        return {
            'generated_at': self.generated_at,
            'device_mode': self.device_mode,
            'grade': self.grade,
            'environment': dict(self.environment),
            'mains': dict(self.mains),
            'batteries': list(self.batteries),
            'drivers': dict(self.drivers),
            'thermal': dict(self.thermal),
            'cross_check': dict(self.cross_check),
            'findings': [
                {
                    'id': finding.id,
                    'severity': finding.severity,
                    'key': finding.key,
                    'params': finding.params,
                    'evidence': finding.evidence,
                    'remediation': finding.remediation,
                    'confidence': finding.confidence,
                }
                for finding in self.findings
            ],
        }


# ═══════════════════════════════════════════════════════════
# جمع البيانات
# ═══════════════════════════════════════════════════════════

def _dmi(field_name: str) -> str:
    if not IS_LINUX:
        return ''
    return hw.read_text_bounded(DMI_ROOT / field_name) or ''


def collect_environment() -> Dict[str, str]:
    """بيئة التشغيل والعتاد كما يعرّفها النظام نفسه"""
    environment = {
        'platform': sys.platform,
        'system': platform.system(),
        'release': platform.release(),
        'python': platform.python_version(),
    }
    if IS_LINUX:
        environment.update({
            'vendor': _dmi('sys_vendor'),
            'product': _dmi('product_name'),
            'board': _dmi('board_name'),
            'bios_vendor': _dmi('bios_vendor'),
            'bios_version': _dmi('bios_version'),
            'bios_date': _dmi('bios_date'),
            'chassis_type': _dmi('chassis_type'),
        })
    elif IS_WINDOWS:
        environment.update({'vendor': '', 'product': platform.machine()})
    return environment


def _read(path: Path, name: str) -> Reading:
    """قراءة واحدة مع تصنيف صريح لحالتها"""
    if not path.exists():
        return Reading(name, None, 'missing', str(path))
    value = hw.read_text_bounded(path)
    if value is None:
        return Reading(name, None, 'timeout', str(path))
    return Reading(name, value, 'ok', str(path))


BATTERY_ATTRIBUTES = (
    'status', 'present', 'capacity', 'capacity_level', 'voltage_now',
    'voltage_min_design', 'current_now', 'power_now', 'charge_now',
    'charge_full', 'charge_full_design', 'energy_now', 'energy_full',
    'energy_full_design', 'cycle_count', 'technology', 'manufacturer',
    'model_name', 'serial_number', 'temp',
    'charge_control_start_threshold', 'charge_control_end_threshold',
    'charge_start_threshold', 'charge_stop_threshold',
)


def collect_power_supplies() -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    """
    كل مصادر الطاقة التي يعرفها النظام: البطاريات بكل خصائصها المقروءة،
    ومحوّل الكهرباء. الغياب نفسه نتيجة تشخيصية.
    """
    batteries: List[Dict[str, object]] = []
    mains: Dict[str, object] = {'present': False, 'online': None, 'name': ''}

    if not IS_LINUX or not POWER_SUPPLY_ROOT.exists():
        return batteries, mains

    try:
        entries = sorted(POWER_SUPPLY_ROOT.iterdir())
    except OSError as e:
        logger.error(f"تعذّر سرد مصادر الطاقة: {e}")
        return batteries, mains

    for entry in entries:
        supply_type = (hw.read_text_bounded(entry / 'type') or '').strip()
        if supply_type == 'Battery':
            readings = [_read(entry / name, name) for name in BATTERY_ATTRIBUTES]
            batteries.append({
                'name': entry.name,
                'path': str(entry),
                'readings': {reading.name: reading for reading in readings},
            })
        elif supply_type in ('Mains', 'USB', 'UPS'):
            online = hw.read_text_bounded(entry / 'online')
            mains = {
                'present': True,
                'online': (online == '1') if online is not None else None,
                'name': entry.name,
                'type': supply_type,
            }
    return batteries, mains


def collect_drivers() -> Dict[str, object]:
    """السوّاقات المحمّلة والأدوات المتاحة: هنا يظهر سبب غياب العتبات كثيراً"""
    loaded: List[str] = []
    if IS_LINUX and MODULES_FILE.exists():
        content = hw.read_text_bounded(MODULES_FILE, timeout=2.0) or ''
        loaded = [line.split()[0] for line in content.splitlines() if line.strip()]

    tools = {
        name: bool(shutil.which(name))
        for name in ('tlp', 'tlp-stat', 'upower', 'ectool', 'cctk', 'powercfg')
    }
    return {
        'loaded_modules': loaded,
        'tools': tools,
        'acpi_call': 'acpi_call' in loaded,
        'ec_sys': 'ec_sys' in loaded,
    }


def collect_thermal() -> Dict[str, object]:
    """حرارة البطارية إن وُجدت، ومناطق الحرارة العامة للسياق"""
    result: Dict[str, object] = {'battery_temp_c': None, 'zones': []}
    if not IS_LINUX:
        return result

    result['battery_temp_c'] = hw.read_battery_temperature()

    zones_root = Path('/sys/class/thermal')
    if zones_root.exists():
        try:
            for zone in sorted(zones_root.glob('thermal_zone*')):
                zone_type = hw.read_text_bounded(zone / 'type') or zone.name
                raw = hw.read_int_bounded(zone / 'temp')
                if raw is None:
                    continue
                celsius = round(raw / 1000.0, 1)
                if not _plausible_temperature(celsius):
                    # قيم حارس معروفة (127 من acpitz مثلاً) تُستبعد بدل عرضها
                    result['zones'].append({'type': zone_type, 'celsius': celsius,
                                            'plausible': False})
                    continue
                result['zones'].append({'type': zone_type, 'celsius': celsius,
                                        'plausible': True})
        except OSError as e:
            logger.debug(f"تعذّرت قراءة مناطق الحرارة: {e}")
    return result


#: قيم حارس شائعة تعرضها بعض مناطق الحرارة عند عدم توفّر قياس حقيقي
SENTINEL_TEMPERATURES = (127.0, 128.0, -273.2, 0.0)


def _plausible_temperature(celsius: float) -> bool:
    """
    هل هذه الحرارة قياس حقيقي؟ بعض مناطق ACPI تعرض 127 درجة كقيمة حارس،
    وعرضها كأعلى حرارة في النظام معلومة خاطئة لا معلومة ناقصة.
    """
    if celsius in SENTINEL_TEMPERATURES:
        return False
    return 5.0 < celsius < 105.0


def plausible_zones(thermal: Dict[str, object]) -> List[Dict[str, object]]:
    """مناطق الحرارة القابلة للاعتماد فقط"""
    return [zone for zone in (thermal.get('zones') or []) if zone.get('plausible')]


def collect_cross_check(batteries: List[Dict[str, object]]) -> Dict[str, object]:
    """
    مقارنة ثلاثة مصادر: psutil وsysfs وupower. اختلافها دليل على مشكلة في
    الطبقة الوسيطة لا في البطارية، وهو فرق يصعب على المستخدم رؤيته وحده.
    """
    result: Dict[str, object] = {'psutil': None, 'sysfs': None, 'upower': None,
                                 'agree': None}
    try:
        import psutil
        reading = psutil.sensors_battery()
        if reading is not None:
            result['psutil'] = round(float(reading.percent), 1)
    except Exception as e:
        logger.debug(f"psutil غير متاح في المقارنة: {e}")

    if batteries:
        capacity = batteries[0]['readings'].get('capacity')
        if capacity is not None and capacity.status == 'ok':
            try:
                result['sysfs'] = float(capacity.value)
            except (TypeError, ValueError):
                pass

    if shutil.which('upower'):
        try:
            output = subprocess.run(
                ['upower', '-i', '/org/freedesktop/UPower/devices/battery_BAT0'],
                capture_output=True, text=True, timeout=6).stdout
            for line in output.splitlines():
                if 'percentage:' in line:
                    result['upower'] = float(line.split(':')[1].strip().rstrip('%'))
                    break
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            logger.debug(f"upower غير متاح في المقارنة: {e}")

    values = [value for value in (result['psutil'], result['sysfs'], result['upower'])
              if value is not None]
    if len(values) >= 2:
        result['agree'] = (max(values) - min(values)) <= 2.0
    return result


# ═══════════════════════════════════════════════════════════
# التصنيف
# ═══════════════════════════════════════════════════════════

def _device_mode(environment: Dict[str, str], batteries: List[Dict]) -> str:
    chassis = (environment.get('chassis_type') or '').strip()
    portable = chassis in PORTABLE_CHASSIS
    desktop = chassis in DESKTOP_CHASSIS
    if batteries:
        return 'portable_with_battery' if portable or not desktop else 'desktop_with_ups'
    if desktop:
        return 'desktop'
    if portable:
        return 'portable_no_battery'
    return 'unknown'


def _battery_numbers(readings: Dict[str, Reading]) -> Dict[str, Optional[float]]:
    """تحويل القراءات النصية إلى أرقام حيث أمكن"""
    def number(name: str) -> Optional[float]:
        reading = readings.get(name)
        if reading is None or reading.status != 'ok' or reading.value is None:
            return None
        try:
            return float(reading.value)
        except (TypeError, ValueError):
            return None

    return {
        'capacity': number('capacity'),
        'voltage_now': number('voltage_now'),
        'current_now': number('current_now'),
        'power_now': number('power_now'),
        'charge_now': number('charge_now'),
        'charge_full': number('charge_full'),
        'charge_full_design': number('charge_full_design'),
        'energy_now': number('energy_now'),
        'energy_full': number('energy_full'),
        'energy_full_design': number('energy_full_design'),
        'cycle_count': number('cycle_count'),
        'present': number('present'),
    }


def classify(report: DiagnosticsReport) -> List[Finding]:
    """
    تحويل القياسات الخام إلى نتائج مفهومة. الترتيب بالشدّة، وكل نتيجة
    تحمل أدلتها من نفس الجهاز.
    """
    findings: List[Finding] = []
    environment = report.environment
    vendor = (environment.get('vendor') or '').strip()
    vendor_key = vendor.lower()
    mains_online = report.mains.get('online')

    # ── لا توجد بطارية في العتاد ──
    if not report.batteries:
        if report.device_mode == 'desktop':
            findings.append(Finding(
                id='desktop_no_battery', severity='info',
                key='diag.finding.desktop_no_battery',
                evidence=[f"chassis_type={environment.get('chassis_type', '?')}",
                          f"power_supply: {report.mains.get('name') or 'AC'}"],
                remediation=['diag.remedy.desktop_mode'],
                confidence=95,
            ))
        else:
            findings.append(Finding(
                id='battery_not_detected', severity='warning',
                key='diag.finding.battery_not_detected',
                evidence=[f"لا يوجد أي مصدر من نوع Battery تحت {POWER_SUPPLY_ROOT}",
                          f"chassis_type={environment.get('chassis_type', '?')}"],
                remediation=['diag.remedy.reseat_battery', 'diag.remedy.check_bios_battery',
                             'diag.remedy.desktop_mode'],
                confidence=85,
            ))
        return sorted(findings, key=lambda item: item.rank)

    battery = report.batteries[0]
    readings: Dict[str, Reading] = battery['readings']
    numbers = _battery_numbers(readings)
    path = battery['path']

    timeouts = [reading.name for reading in readings.values() if reading.status == 'timeout']
    missing = [reading.name for reading in readings.values() if reading.status == 'missing']

    present = numbers.get('present')
    capacity = numbers.get('capacity')
    voltage = numbers.get('voltage_now')
    current = numbers.get('current_now')
    status_reading = readings.get('status')
    status_text = status_reading.value if status_reading and status_reading.status == 'ok' else ''

    # ── بطارية معلَّمة كغير موجودة ──
    if present == 0:
        findings.append(Finding(
            id='battery_absent_flag', severity='warning',
            key='diag.finding.battery_absent_flag',
            evidence=[f"{path}/present=0"],
            remediation=['diag.remedy.reseat_battery', 'diag.remedy.check_bios_battery'],
            confidence=90,
        ))

    # ── وحدة التحكم المدمجة لا تُبلّغ ──
    elif (capacity in (0, None) and (voltage in (0, None)) and (current in (0, None))):
        evidence = [f"{path}/capacity={readings['capacity'].display}",
                    f"{path}/voltage_now={readings['voltage_now'].display}",
                    f"{path}/current_now={readings['current_now'].display}",
                    f"{path}/status={status_text or '—'}"]
        confidence = 92 if status_text in ('Not charging', 'Unknown') else 80
        findings.append(Finding(
            id='ec_not_reporting', severity='critical',
            key='diag.finding.ec_not_reporting',
            params={'status': status_text or '—'},
            evidence=evidence,
            remediation=['diag.remedy.power_cycle_ec', 'diag.remedy.check_bios_battery',
                         'diag.remedy.replace_cells', 'diag.remedy.notify_mode'],
            confidence=confidence,
        ))

    # ── قيم غير معقولة: السعة الكاملة تساوي التصميمية بالضبط والشحن صفر ──
    full = numbers.get('charge_full') or numbers.get('energy_full')
    design = numbers.get('charge_full_design') or numbers.get('energy_full_design')
    if full and design and abs(full - design) < 1 and (capacity in (0, None)):
        findings.append(Finding(
            id='capacity_implausible', severity='warning',
            key='diag.finding.capacity_implausible',
            evidence=[f"full={int(full)}", f"design={int(design)}",
                      f"capacity={readings['capacity'].display}"],
            remediation=['diag.remedy.ignore_soh', 'diag.remedy.replace_cells'],
            confidence=88,
        ))

    # ── قراءات لا تستجيب ──
    if timeouts:
        findings.append(Finding(
            id='sysfs_timeout', severity='warning',
            key='diag.finding.sysfs_timeout',
            params={'count': len(timeouts), 'names': ', '.join(timeouts[:4])},
            evidence=[f"{path}/{name}: تجاوز المهلة" for name in timeouts[:6]],
            remediation=['diag.remedy.power_cycle_ec', 'diag.remedy.kernel_update'],
            confidence=85,
        ))

    # ── عدد الدورات ──
    cycles = numbers.get('cycle_count')
    if cycles in (0, None):
        findings.append(Finding(
            id='cycles_unavailable', severity='info',
            key='diag.finding.cycles_unavailable',
            evidence=[f"{path}/cycle_count={readings['cycle_count'].display}"],
            remediation=['diag.remedy.cycles_estimate'],
            confidence=90,
        ))

    # ── الحرارة ──
    if report.thermal.get('battery_temp_c') is None:
        findings.append(Finding(
            id='temp_unavailable', severity='info',
            key='diag.finding.temp_unavailable',
            evidence=['temp: missing' if 'temp' in missing else 'temp: unreadable',
                      f"مناطق حرارة النظام الموثوقة: {len(plausible_zones(report.thermal))}"
                      f" من {len(report.thermal.get('zones') or [])}"],
            remediation=['diag.remedy.assume_temp'],
            confidence=95,
        ))

    # ── حدود الشحن والسوّاقة ──
    threshold_names = ('charge_control_end_threshold', 'charge_stop_threshold')
    has_threshold = any(readings[name].status == 'ok' for name in threshold_names
                        if name in readings)
    if not has_threshold:
        expected_drivers = ()
        for key, drivers in VENDOR_DRIVERS.items():
            if key in vendor_key:
                expected_drivers = drivers
                break
        loaded = set(report.drivers.get('loaded_modules') or [])
        missing_drivers = [name for name in expected_drivers if name not in loaded]

        if expected_drivers and missing_drivers and not any(
                name in vendor_key for name in FIRMWARE_ONLY_VENDORS):
            findings.append(Finding(
                id='driver_not_loaded', severity='warning',
                key='diag.finding.driver_not_loaded',
                params={'driver': missing_drivers[0], 'vendor': vendor},
                evidence=[f"سوّاقات محمّلة تخص المصنّع: "
                          f"{', '.join(sorted(set(expected_drivers) & loaded)) or 'لا شيء'}",
                          f"غير محمّل: {', '.join(missing_drivers)}"],
                remediation=['diag.remedy.load_driver', 'diag.remedy.kernel_update'],
                confidence=75,
            ))
        elif any(name in vendor_key for name in FIRMWARE_ONLY_VENDORS):
            findings.append(Finding(
                id='firmware_only_control', severity='advice',
                key='diag.finding.firmware_only_control',
                params={'vendor': vendor},
                evidence=[f"لا يوجد {threshold_names[0]} تحت {path}",
                          f"tlp متاح: {report.drivers.get('tools', {}).get('tlp')}"],
                remediation=['remedy.hp.bios', 'remedy.hp.cmsl'],
                confidence=90,
            ))
        else:
            findings.append(Finding(
                id='no_threshold_path', severity='advice',
                key='diag.finding.no_threshold_path',
                evidence=[f"لا يوجد {threshold_names[0]} ولا {threshold_names[1]} تحت {path}"],
                remediation=['remedy.generic.check_vendor_list',
                             'remedy.generic.bios_hint', 'diag.remedy.notify_mode'],
                confidence=85,
            ))
    else:
        findings.append(Finding(
            id='threshold_path_available', severity='good',
            key='diag.finding.threshold_path_available',
            evidence=[f"{path}/{threshold_names[0]}="
                      f"{readings[threshold_names[0]].display}"],
            confidence=95,
        ))

    # ── اختلاف المصادر ──
    cross = report.cross_check
    if cross.get('agree') is False:
        findings.append(Finding(
            id='source_disagreement', severity='warning',
            key='diag.finding.source_disagreement',
            params={'psutil': cross.get('psutil'), 'sysfs': cross.get('sysfs'),
                    'upower': cross.get('upower')},
            evidence=[f"psutil={cross.get('psutil')}", f"sysfs={cross.get('sysfs')}",
                      f"upower={cross.get('upower')}"],
            remediation=['diag.remedy.trust_sysfs'],
            confidence=80,
        ))

    # ── نمط التشغيل: موصول دائماً ──
    if mains_online and (capacity in (0, None) or present == 0):
        findings.append(Finding(
            id='mains_only_operation', severity='advice',
            key='diag.finding.mains_only_operation',
            evidence=[f"{report.mains.get('name', 'AC')}/online=1"],
            remediation=['diag.remedy.mains_only_guidance'],
            confidence=85,
        ))

    return sorted(findings, key=lambda item: item.rank)


def _grade(findings: List[Finding], batteries: List[Dict]) -> str:
    """تقدير عام واحد يُعرض في أعلى لوحة التشخيص"""
    ids = {finding.id for finding in findings}
    if 'ec_not_reporting' in ids or 'battery_absent_flag' in ids:
        return 'unmeasurable'
    if not batteries:
        return 'unmeasurable'
    if {'sysfs_timeout', 'capacity_implausible', 'source_disagreement'} & ids:
        return 'impaired'
    if {'driver_not_loaded', 'no_threshold_path', 'firmware_only_control'} & ids:
        return 'degraded'
    return 'ok'


# ═══════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════

def run(deep: bool = True) -> DiagnosticsReport:
    """
    فحص كامل. `deep=False` يتخطّى الفحوص التي تشغّل أدوات خارجية
    (upower وقراءة كل مناطق الحرارة) لاستخدامه في التحديث الدوري.
    """
    # صيغة مقروءة في سياق يمين-إلى-يسار: ISO تتفكك بصريًا داخل نص عربي
    report = DiagnosticsReport(generated_at=datetime.now().strftime('%Y/%m/%d %H:%M'))
    report.environment = collect_environment()
    report.batteries, report.mains = collect_power_supplies()
    report.drivers = collect_drivers()
    report.thermal = collect_thermal() if deep else {'battery_temp_c':
                                                    hw.read_battery_temperature(),
                                                    'zones': []}
    report.cross_check = collect_cross_check(report.batteries) if deep else {}
    report.device_mode = _device_mode(report.environment, report.batteries)
    report.findings = classify(report)
    report.grade = _grade(report.findings, report.batteries)

    logger.info(f"التشخيص: الوضع={report.device_mode} التقدير={report.grade} "
                f"نتائج={[finding.id for finding in report.findings]}")
    return report


def readable_table(report: DiagnosticsReport) -> List[Tuple[str, str, str]]:
    """
    جدول الأدلة الخام للعرض: (المسار، القيمة، الحالة).
    هذا ما يُنسخ في تقرير المشكلة، ولا يُجمَّل.
    """
    rows: List[Tuple[str, str, str]] = []
    for key, value in report.environment.items():
        if value:
            rows.append((f"dmi/{key}", str(value), 'ok'))

    if report.mains.get('present'):
        rows.append((f"{report.mains.get('name')}/online",
                     str(report.mains.get('online')), 'ok'))

    for battery in report.batteries:
        for reading in battery['readings'].values():
            rows.append((f"{battery['name']}/{reading.name}",
                         reading.display, reading.status))

    for zone in (report.thermal.get('zones') or [])[:10]:
        rows.append((f"thermal/{zone['type']}", f"{zone['celsius']}",
                     'ok' if zone.get('plausible') else 'sentinel'))

    for name, available in (report.drivers.get('tools') or {}).items():
        rows.append((f"tool/{name}", 'متاح' if available else 'غير متاح',
                     'ok' if available else 'missing'))
    return rows
