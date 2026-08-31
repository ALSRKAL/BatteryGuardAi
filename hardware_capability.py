#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص قدرات العتاد - BatteryGuardAI

هذه الوحدة هي مصدر الحقيقة الوحيد لسؤال: ما الذي يستطيع هذا التطبيق فعله
على *هذا* الجهاز بالضبط؟ لا وعود عامة، ولا ادّعاء نجاح غير متحقَّق منه.

ثلاث طبقات قدرة صريحة:
- `hardware_control`: يوجد مسار كتابة فعلي لحدود الشحن يمكن قراءته للتحقق.
- `firmware_setting`: الحدّ موجود لكن في إعداد BIOS/UEFI لا يملكه نظام التشغيل
  (مثل HP Battery Health Manager). التطبيق يرشد ولا يزعم أنه ضبطه.
- `notify_only`: لا مسار على الإطلاق. التطبيق يراقب وينبّه ويقول ذلك صراحةً.

كل قراءة sysfs محدودة بمهلة: بعض وحدات التحكم المدمجة (EC) تتجمّد عند القراءة،
ولا يجوز لخيط المراقبة أن يتوقف بسببها.

مراجع مسارات التحكم (تمت إعادة صياغة محتواها):
- TLP - Battery Care Vendor Specifics: قائمة العتاد المدعوم وسواقات النواة
  المطلوبة، وتنصّ صراحةً على أن العتاد غير المذكور فيها غير مدعوم.
  https://linrunner.de/tlp/settings/bc-vendors.html
- ArchWiki - Laptop/ASUS و tpacpi-bat لحدود الشحن على ASUS وThinkPad.
  https://wiki.archlinux.org/title/Laptop/ASUS
- HP - Battery Health Manager: إعداد BIOS يحدّ الشحن الأقصى عند 80% تقريباً
  في معظم حواسيب HP للأعمال.
  https://support.hp.com/emea_africa-en/document/ish_4449597-3519507-16
- HP Client Management Script Library: ضبط إعدادات BIOS من PowerShell على ويندوز.
  https://developers.hp.com/hp-client-management/doc/bios-and-device
- Dell Command PowerShell Provider - PrimaryBattChargeCfg لضبط سلوك الشحن.
  https://www.dell.com/support/manuals/command-powershell-provider/dcpp_ug_2.2/using-the-primarybattchargecfg-feature
"""

import logging
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger('BatteryGuard')

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

POWER_SUPPLY_ROOT = Path('/sys/class/power_supply')
DMI_ROOT = Path('/sys/class/dmi/id')

#: مهلة قراءة ملف sysfs واحد (ثانية). أطول من ذلك يعني عتاداً لا يستجيب.
SYSFS_READ_TIMEOUT = 1.5

#: أسماء ملفات حدود الشحن كما تعرضها سواقات النواة المختلفة
END_THRESHOLD_FILES = ('charge_control_end_threshold', 'charge_stop_threshold')
START_THRESHOLD_FILES = ('charge_control_start_threshold', 'charge_start_threshold')

TIER_HARDWARE = 'hardware_control'
TIER_FIRMWARE = 'firmware_setting'
TIER_NOTIFY = 'notify_only'


# ═══════════════════════════════════════════════════════════
# قراءة sysfs بمهلة (لا تجميد لخيط المراقبة)
# ═══════════════════════════════════════════════════════════

_reader_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='sysfs')
_stuck_paths: set = set()
_stuck_lock = threading.Lock()


def read_text_bounded(path: Path, timeout: float = SYSFS_READ_TIMEOUT) -> Optional[str]:
    """
    قراءة ملف نصي بمهلة قصوى. يعيد None عند الفشل أو التجاوز.

    المسار الذي تجاوز المهلة مرة يُسجَّل ويُتخطّى لاحقاً: العتاد الذي لا يستجيب
    لا يستجيب في كل دورة مراقبة، ولا معنى لإنفاق مهلة جديدة عليه كل مرة.
    """
    key = str(path)
    with _stuck_lock:
        if key in _stuck_paths:
            return None
    try:
        future = _reader_pool.submit(lambda: Path(path).read_text(encoding='utf-8', errors='replace'))
        return future.result(timeout=timeout).strip()
    except FutureTimeout:
        with _stuck_lock:
            _stuck_paths.add(key)
        logger.warning(f"تجاوز مهلة قراءة العتاد: {path} (سيُتخطّى لاحقاً)")
        return None
    except (OSError, ValueError) as e:
        logger.debug(f"تعذّرت قراءة {path}: {e}")
        return None
    except RuntimeError as e:
        # `cannot schedule new futures after shutdown`: يحدث عند إغلاق التطبيق
        # أثناء فحص عميق جارٍ. قراءة فائتة عند الخروج ليست خطأً يستحق انهياراً.
        logger.debug(f"تعذّرت جدولة قراءة {path} (إغلاق جارٍ): {e}")
        return None


def read_int_bounded(path: Path, timeout: float = SYSFS_READ_TIMEOUT) -> Optional[int]:
    """قراءة عدد صحيح من sysfs بمهلة"""
    raw = read_text_bounded(path, timeout)
    if raw is None:
        return None
    try:
        return int(raw.split()[0])
    except (ValueError, IndexError):
        return None


def clear_stuck_paths() -> None:
    """نسيان المسارات المعطّلة (بعد استئناف من نوم مثلاً)"""
    with _stuck_lock:
        _stuck_paths.clear()


# ═══════════════════════════════════════════════════════════
# نماذج البيانات
# ═══════════════════════════════════════════════════════════

@dataclass
class ControlPath:
    """مسار تحكم مكتشف فعلاً على هذا الجهاز"""
    id: str
    kind: str                      # sysfs | tlp | tool | firmware
    detail: str                    # المسار أو الأمر
    writable_check: bool = False   # هل الكتابة ممكنة (قد تحتاج صلاحيات)
    requires_root: bool = False
    supports_start: bool = False
    supports_end: bool = True


@dataclass
class RemediationStep:
    """خطوة معالجة قابلة للتنفيذ عند غياب التحكم أو فشله"""
    key: str                       # مفتاح ترجمة
    params: Dict[str, object] = field(default_factory=dict)
    command: Optional[str] = None  # أمر يمكن نسخه، لا يُنفّذ تلقائياً
    url: Optional[str] = None


def device_name(vendor: str, product: str) -> str:
    """
    اسم الجهاز المعروض، بلا تكرار المصنّع.

    كثير من المصنّعين يضعون اسمهم في `product_name` أيضاً، فالجمع الساذج
    يعطي «HP HP ZBook 15 G3». الدمج هنا مصدر واحد يستخدمه الشريط ونافذة
    التعريف والتشخيص، حتى لا يُصلَح في موضع ويبقى في آخر.
    """
    vendor = (vendor or '').strip()
    product = (product or '').strip()
    if not vendor:
        return product
    if not product:
        return vendor
    if product.lower().startswith(vendor.lower()):
        return product
    return f'{vendor} {product}'


@dataclass
class CapabilityReport:
    """تقرير القدرات الكامل - ما يُعرض في شريط «ما يدعمه جهازك»"""
    platform: str = 'unknown'
    vendor: str = ''
    product: str = ''
    battery_path: Optional[str] = None
    battery_present: bool = False
    tier: str = TIER_NOTIFY
    control_paths: List[ControlPath] = field(default_factory=list)
    readable: Dict[str, bool] = field(default_factory=dict)
    remediation: List[RemediationStep] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def can_control(self) -> bool:
        return self.tier == TIER_HARDWARE and bool(self.control_paths)

    @property
    def primary_path(self) -> Optional[ControlPath]:
        return self.control_paths[0] if self.control_paths else None

    def as_dict(self) -> Dict[str, object]:
        """تمثيل قابل للتخزين والعرض"""
        return {
            'platform': self.platform,
            'vendor': self.vendor,
            'product': self.product,
            'battery_path': self.battery_path,
            'battery_present': self.battery_present,
            'tier': self.tier,
            'can_control': self.can_control,
            'control_paths': [p.__dict__ for p in self.control_paths],
            'readable': dict(self.readable),
            'remediation': [
                {'key': s.key, 'params': s.params, 'command': s.command, 'url': s.url}
                for s in self.remediation
            ],
            'notes': list(self.notes),
        }


# ═══════════════════════════════════════════════════════════
# كتالوج المعالجة حسب المصنّع
# ═══════════════════════════════════════════════════════════

def _hp_remediation(product: str) -> List[RemediationStep]:
    return [
        RemediationStep(
            key='remedy.hp.bios',
            params={'product': product},
            url='https://support.hp.com/emea_africa-en/document/ish_4449597-3519507-16',
        ),
        RemediationStep(
            key='remedy.hp.cmsl',
            command='Set-HPBIOSSettingValue -Name "Battery Health Manager" '
                    '-Value "Maximize my battery health"',
            url='https://developers.hp.com/hp-client-management/doc/bios-and-device',
        ),
        RemediationStep(key='remedy.generic.notify_mode'),
    ]


def _lenovo_remediation() -> List[RemediationStep]:
    return [
        RemediationStep(
            key='remedy.lenovo.driver',
            command='sudo modprobe thinkpad_acpi',
            url='https://linrunner.de/tlp/settings/bc-vendors.html',
        ),
        RemediationStep(
            key='remedy.lenovo.conservation',
            command='sudo tlp setcharge 40 80 BAT0',
            url='https://linrunner.de/tlp/settings/bc-vendors.html',
        ),
        RemediationStep(key='remedy.generic.notify_mode'),
    ]


def _asus_remediation() -> List[RemediationStep]:
    return [
        RemediationStep(
            key='remedy.asus.driver',
            command='sudo modprobe asus_wmi',
            url='https://wiki.archlinux.org/title/Laptop/ASUS',
        ),
        RemediationStep(key='remedy.asus.reset_on_reboot'),
        RemediationStep(key='remedy.generic.notify_mode'),
    ]


def _dell_remediation() -> List[RemediationStep]:
    return [
        RemediationStep(
            key='remedy.dell.cctk',
            command='cctk --PrimaryBattChargeCfg=Custom:50-80',
            url='https://www.dell.com/support/manuals/command-powershell-provider/'
                'dcpp_ug_2.2/using-the-primarybattchargecfg-feature',
        ),
        RemediationStep(key='remedy.dell.bios'),
        RemediationStep(key='remedy.generic.notify_mode'),
    ]


def _generic_remediation() -> List[RemediationStep]:
    return [
        RemediationStep(
            key='remedy.generic.check_vendor_list',
            url='https://linrunner.de/tlp/settings/bc-vendors.html',
        ),
        RemediationStep(key='remedy.generic.bios_hint'),
        RemediationStep(key='remedy.generic.notify_mode'),
    ]


VENDOR_REMEDIATION = {
    'hp': _hp_remediation,
    'hewlett-packard': _hp_remediation,
    'lenovo': _lenovo_remediation,
    'asus': _asus_remediation,
    'asustek': _asus_remediation,
    'dell': _dell_remediation,
}


def remediation_for(vendor: str, product: str = '') -> List[RemediationStep]:
    """خطوات المعالجة المناسبة للمصنّع، مع سقوط إلى الخطوات العامة"""
    key = (vendor or '').strip().lower()
    for name, builder in VENDOR_REMEDIATION.items():
        if name in key:
            try:
                return builder(product) if builder is _hp_remediation else builder()
            except TypeError:  # pragma: no cover - حماية من تغيّر التوقيع
                return builder()
    return _generic_remediation()


# ═══════════════════════════════════════════════════════════
# الفحص
# ═══════════════════════════════════════════════════════════

def find_battery_path() -> Optional[Path]:
    """أول بطارية حقيقية في sysfs (BAT0/BAT1/CMB0/macsmc-battery/...)"""
    if not IS_LINUX or not POWER_SUPPLY_ROOT.exists():
        return None
    candidates: List[Path] = []
    try:
        for entry in sorted(POWER_SUPPLY_ROOT.iterdir()):
            type_value = read_text_bounded(entry / 'type')
            if type_value == 'Battery':
                candidates.append(entry)
    except OSError as e:
        logger.debug(f"تعذّر سرد {POWER_SUPPLY_ROOT}: {e}")
    return candidates[0] if candidates else None


def _dmi(field_name: str) -> str:
    value = read_text_bounded(DMI_ROOT / field_name)
    return value or ''


def _readable_fields(bat: Optional[Path]) -> Dict[str, bool]:
    """أي القياسات يمكن قراءتها فعلاً من هذا العتاد"""
    if bat is None:
        return {k: False for k in
                ('percent', 'status', 'voltage', 'current', 'power', 'temperature',
                 'cycles', 'capacity_full', 'capacity_design')}
    def has(*names: str) -> bool:
        return any((bat / n).exists() for n in names)
    return {
        'percent': has('capacity'),
        'status': has('status'),
        'voltage': has('voltage_now'),
        'current': has('current_now'),
        'power': has('power_now') or (has('voltage_now') and has('current_now')),
        'temperature': has('temp') or _hwmon_temp_file(bat) is not None,
        'cycles': has('cycle_count'),
        'capacity_full': has('energy_full', 'charge_full'),
        'capacity_design': has('energy_full_design', 'charge_full_design'),
    }


def _linux_control_paths(bat: Optional[Path]) -> List[ControlPath]:
    """مسارات التحكم الفعلية: sysfs أولاً لأنه الوحيد القابل للتحقق بالقراءة"""
    paths: List[ControlPath] = []
    if bat is None:
        return paths

    end_file = next((bat / n for n in END_THRESHOLD_FILES if (bat / n).exists()), None)
    start_file = next((bat / n for n in START_THRESHOLD_FILES if (bat / n).exists()), None)

    if end_file is not None:
        paths.append(ControlPath(
            id='sysfs_threshold',
            kind='sysfs',
            detail=str(end_file),
            writable_check=_is_writable(end_file),
            requires_root=not _is_writable(end_file),
            supports_start=start_file is not None,
            supports_end=True,
        ))

    # TLP لا يُعدّ مساراً مستقلاً: هو غلاف على نفس sysfs، ويدعم عتاداً محدداً
    # موثقاً في صفحته. نسجّله فقط كمساعد عندما توجد عتبات فعلية.
    if end_file is not None and shutil.which('tlp'):
        paths.append(ControlPath(
            id='tlp',
            kind='tlp',
            detail='tlp setcharge',
            requires_root=True,
            supports_start=start_file is not None,
        ))
    return paths


def _is_writable(path: Path) -> bool:
    """هل الملف قابل للكتابة بالمستخدم الحالي (بدون محاولة كتابة فعلية)"""
    try:
        import os
        return os.access(path, os.W_OK)
    except OSError:
        return False


def _windows_control_paths() -> Tuple[List[ControlPath], List[str]]:
    """أدوات المصنّعين على ويندوز: وجود الأداة يُفحص، ونجاحها لا يُفترض"""
    found: List[ControlPath] = []
    notes: List[str] = []

    candidates = (
        ('dell_cctk', 'cctk.exe', 'Dell Command Configure'),
        ('lenovo_vantage', 'powershell.exe', 'Lenovo Conservation Mode (WMI)'),
        ('hp_cmsl', 'powershell.exe', 'HP Client Management Script Library'),
    )
    seen_exe = set()
    for cid, exe, label in candidates:
        location = shutil.which(exe)
        if location and (cid, location) not in seen_exe:
            seen_exe.add((cid, location))
            found.append(ControlPath(
                id=cid, kind='tool', detail=label,
                writable_check=False, requires_root=True,
            ))
    if not found:
        notes.append('no_vendor_tool_found')
    return found, notes


def probe(force: bool = False) -> CapabilityReport:
    """
    فحص كامل لقدرات هذا الجهاز. النتيجة مخزّنة مؤقتاً لأن العتاد لا يتغيّر
    أثناء الجلسة (إلا بتحميل سوّاقة، ولذلك `force`).
    """
    global _cached_report
    if _cached_report is not None and not force:
        return _cached_report

    report = CapabilityReport()

    if IS_LINUX:
        report.platform = 'linux'
        bat = find_battery_path()
        report.battery_path = str(bat) if bat else None
        report.battery_present = bat is not None and (read_text_bounded(bat / 'present') or '1') == '1'
        report.vendor = _dmi('sys_vendor')
        report.product = _dmi('product_name')
        report.readable = _readable_fields(bat)
        report.control_paths = _linux_control_paths(bat)
    elif IS_WINDOWS:
        report.platform = 'windows'
        report.battery_present = True  # يتحقق منه psutil في طبقة المراقبة
        report.vendor, report.product = _windows_identity()
        report.readable = {
            'percent': True, 'status': True, 'voltage': False, 'current': False,
            'power': False, 'temperature': False, 'cycles': True,
            'capacity_full': True, 'capacity_design': True,
        }
        report.control_paths, report.notes = _windows_control_paths()
    else:
        report.platform = sys.platform
        report.notes.append('unsupported_platform')

    # الطبقة: تحكم فعلي فقط عند وجود مسار يمكن التحقق منه بالقراءة
    if any(p.kind == 'sysfs' for p in report.control_paths):
        report.tier = TIER_HARDWARE
    elif report.control_paths:
        report.tier = TIER_FIRMWARE
    elif _has_firmware_setting(report.vendor):
        report.tier = TIER_FIRMWARE
    else:
        report.tier = TIER_NOTIFY

    if report.tier != TIER_HARDWARE:
        report.remediation = remediation_for(report.vendor, report.product)

    logger.info(
        f"قدرات العتاد: {report.vendor} {report.product} | الطبقة: {report.tier} | "
        f"مسارات: {[p.id for p in report.control_paths] or 'لا شيء'}"
    )
    _cached_report = report
    return report


_cached_report: Optional[CapabilityReport] = None


def _has_firmware_setting(vendor: str) -> bool:
    """مصنّعون يضعون حدّ الشحن في BIOS ولا يعرضونه لنظام التشغيل"""
    key = (vendor or '').lower()
    return any(name in key for name in ('hp', 'hewlett', 'dell', 'asus', 'lenovo'))


def _windows_identity() -> Tuple[str, str]:
    """اسم المصنّع والطراز على ويندوز عبر WMIC/PowerShell بمهلة قصيرة"""
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-CimInstance Win32_ComputerSystem).Manufacturer + "|" + '
             '(Get-CimInstance Win32_ComputerSystem).Model'],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode == 0 and '|' in result.stdout:
            vendor, _, product = result.stdout.strip().partition('|')
            return vendor.strip(), product.strip()
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug(f"تعذّرت قراءة هوية الجهاز على ويندوز: {e}")
    return '', ''


# ═══════════════════════════════════════════════════════════
# التحقق بعد الكتابة (لا نجاح بلا قراءة)
# ═══════════════════════════════════════════════════════════

def verify_threshold(path: Path, expected: int, tolerance: int = 0) -> Tuple[bool, Optional[int]]:
    """
    قراءة العتبة بعد كتابتها للتأكد من أن العتاد قبلها فعلاً.
    يعيد (نجح، القيمة المقروءة). القيمة None تعني تعذّر التحقق.
    """
    actual = read_int_bounded(path)
    if actual is None:
        return False, None
    return abs(actual - expected) <= tolerance, actual


def _hwmon_temp_file(bat: Path) -> Optional[Path]:
    """ملف حرارة البطارية داخل hwmon المرافق لها (رقم hwmon يتغيّر بين الأجهزة)"""
    try:
        for hwmon in sorted(bat.glob('hwmon*')):
            candidate = hwmon / 'temp1_input'
            if candidate.exists():
                return candidate
    except OSError as e:
        logger.debug(f"تعذّر البحث في hwmon: {e}")
    return None


def read_battery_temperature(bat: Optional[Path] = None) -> Optional[float]:
    """
    حرارة البطارية بالدرجات المئوية، أو None حين لا يوفّرها العتاد.

    مصدران فقط، وكلاهما خاص بالبطارية: ملف `temp` (بعُشر الدرجة حسب واجهة
    النواة) وملف hwmon المرافق (بالملي درجة). لا نستخدم حرارة المعالج بديلاً:
    رقم قريب من مصدر خاطئ أسوأ من لا رقم.
    """
    if not IS_LINUX:
        return None
    bat = bat or find_battery_path()
    if bat is None:
        return None

    raw = read_int_bounded(bat / 'temp')
    if raw is not None and -400 < raw < 1500:
        return round(raw / 10.0, 1)

    hwmon_file = _hwmon_temp_file(bat)
    if hwmon_file is not None:
        milli = read_int_bounded(hwmon_file)
        if milli is not None and -40000 < milli < 150000:
            return round(milli / 1000.0, 1)
    return None


def read_current_thresholds(bat: Optional[Path] = None) -> Dict[str, Optional[int]]:
    """العتبات المضبوطة حالياً في العتاد (لا ما يظنّه التطبيق)"""
    bat = bat or find_battery_path()
    if bat is None:
        return {'start': None, 'end': None}
    end_file = next((bat / n for n in END_THRESHOLD_FILES if (bat / n).exists()), None)
    start_file = next((bat / n for n in START_THRESHOLD_FILES if (bat / n).exists()), None)
    return {
        'end': read_int_bounded(end_file) if end_file else None,
        'start': read_int_bounded(start_file) if start_file else None,
    }
