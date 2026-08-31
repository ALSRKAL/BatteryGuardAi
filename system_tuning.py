#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
محرك الضبط الآمن - BatteryGuardAI

هذه الوحدة تملك كل تغيير يجريه التطبيق على النظام خارج حدود الشحن. وُلدت من
أعطال حقيقية سبّبها المحسّن السابق: كان يرفع السطوع إلى قيمة يختارها بنفسه
بعد أن ينزله المستخدم، ويعلّق كل أجهزة USB ويجبر إدارة طاقة الرسوم على
التوفير فتسقط الشاشة الخارجية.

القواعد ملزمة عند أي تعديل، وكلٌّ منها مكتوب لأن نقيضه أعطب جهاز مستخدم:

1. **لا كتابة قبل التقاط الأصل.** كل قيمة تُغيَّر تُحفَظ قبلها في لقطة دائمة
   على القرص، فيبقى التراجع ممكناً بعد إعادة التشغيل أو الانهيار.
2. **السطوع يُخفَض ولا يُرفَع أبداً.** المستخدم يرى شاشته ونحن لا نراها.
   ولا نلمسه إذا تغيّر بعد آخر كتابة لنا: ذلك يعني أن المستخدم اختار قيمته.
3. **اللوحة الداخلية فقط** (eDP / LVDS / DSI). أي `backlight` خارجي (ddcci)
   ليس ملكنا.
4. **عند وجود شاشة خارجية موصولة تُلغى إجراءات الرسوم وتعليق USB.** سقوط
   شاشة المستخدم أثناء عمله أغلى من كل واط قد نوفّره.
5. **لا صلاحيات جذر للسطوع.** يوجد مسار مصرّح به للجلسة النشطة (GNOME ثم
   logind)، واستخدام كلمة مرور المستخدم لعمل لا يحتاجها خطأ أمني.
6. **لا كتم راديو ولا تغيير دائم في النواة** (swappiness، drop_caches،
   مجدول القرص) من مسار تلقائي: مكسبها غير مثبت وضررها مثبت.

الوحدة نقية بما يكفي للاختبار: كل مسارات النظام قابلة للحقن.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger('BatteryGuard')

IS_LINUX = sys.platform.startswith('linux')
IS_WINDOWS = sys.platform == 'win32'

# ═══════════════════════════════════════════════════════════
# ثوابت معلنة (لا رقم سحري داخل الشيفرة)
# ═══════════════════════════════════════════════════════════

#: مسارات النظام الافتراضية
DRM_ROOT = Path('/sys/class/drm')
BACKLIGHT_ROOT = Path('/sys/class/backlight')

#: علامات موصّلات اللوحة الداخلية: ما عداها شاشة خارجية
INTERNAL_CONNECTOR_MARKERS: Tuple[str, ...] = ('edp', 'lvds', 'dsi')

#: أدنى سطوع مسموح كنسبة من الأقصى. تحت هذا الحد تصير الشاشة غير مقروءة،
#: والتوفير الناتج لا يساوي أن يعمل المستخدم في العتمة.
BRIGHTNESS_FLOOR_PERCENT = 30

#: مقدار الخفض الافتراضي بالنقاط المئوية عند طلب توفير الطاقة
BRIGHTNESS_STEP_PERCENT = 15

#: مهلة كل أمر خارجي (ثانية): لا ينتظر التطبيق نظاماً لا يستجيب
COMMAND_TIMEOUT = 5

#: ملف اللقطة: يبقى بعد إعادة التشغيل ليظل التراجع ممكناً
SNAPSHOT_FILE = 'system_tuning_snapshot.json'


# ═══════════════════════════════════════════════════════════
# حالة الشاشات
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DisplayState:
    """موصّلات العرض المتصلة فعلاً، مفصولة داخلية عن خارجية"""

    internal: Tuple[str, ...] = ()
    external: Tuple[str, ...] = ()
    readable: bool = True

    @property
    def has_external(self) -> bool:
        return bool(self.external)

    @property
    def total_connected(self) -> int:
        return len(self.internal) + len(self.external)

    def as_dict(self) -> Dict:
        return {
            'internal': list(self.internal),
            'external': list(self.external),
            'has_external': self.has_external,
            'readable': self.readable,
        }


def _is_internal_connector(connector: str) -> bool:
    """هل اسم الموصّل يدل على لوحة مدمجة في الجهاز"""
    lowered = connector.lower()
    return any(marker in lowered for marker in INTERNAL_CONNECTOR_MARKERS)


def read_display_state(drm_root: Path = DRM_ROOT) -> DisplayState:
    """
    قراءة الموصّلات المتصلة من `/sys/class/drm`.

    يُعتمد على `status == connected` وحده: الموصّل الموجود غير المتصل لا يعني
    شاشة. إذا تعذّرت القراءة يُعاد `readable=False`، وتتصرّف بوابات السلامة
    كأن هناك شاشة خارجية: الجهل ليس إذناً بالتصرف.
    """
    drm_root = Path(drm_root)
    if not drm_root.exists():
        return DisplayState(readable=False)

    internal: List[str] = []
    external: List[str] = []
    try:
        for entry in sorted(drm_root.iterdir()):
            status_file = entry / 'status'
            if not status_file.is_file():
                continue
            try:
                status = status_file.read_text(errors='ignore').strip().lower()
            except OSError:
                continue
            if status != 'connected':
                continue
            name = entry.name
            (internal if _is_internal_connector(name) else external).append(name)
    except OSError as e:
        logger.warning(f"ضبط: تعذّرت قراءة حالة الشاشات: {e}")
        return DisplayState(readable=False)

    return DisplayState(internal=tuple(internal), external=tuple(external))


# ═══════════════════════════════════════════════════════════
# أجهزة السطوع
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Backlight:
    """جهاز سطوع واحد بقيمته الحالية وحدّه الأقصى"""

    name: str
    path: Path
    current: int
    maximum: int
    internal: bool

    @property
    def percent(self) -> int:
        if self.maximum <= 0:
            return 0
        return max(0, min(100, round(self.current * 100 / self.maximum)))

    def raw_for_percent(self, percent: int) -> int:
        """القيمة الخام المقابلة لنسبة، بحدّ أدنى واحد حتى لا تنطفئ الشاشة"""
        bounded = max(1, min(100, int(percent)))
        return max(1, min(self.maximum, round(self.maximum * bounded / 100)))

    def as_dict(self) -> Dict:
        return {
            'name': self.name, 'current': self.current,
            'maximum': self.maximum, 'percent': self.percent,
            'internal': self.internal,
        }


def _backlight_is_internal(device_dir: Path) -> bool:
    """
    هل جهاز السطوع تابعاً للوحة الداخلية.

    الحكم من مسار الجهاز الحقيقي: `intel_backlight` يقع تحت
    `.../card1/card1-eDP-1/intel_backlight`. أجهزة `ddcci` لشاشة خارجية
    لا تحمل موصّلاً داخلياً في مسارها، ويُستبعد اسمها صراحةً كذلك.
    """
    name = device_dir.name.lower()
    if 'ddcci' in name:
        return False
    try:
        resolved = str(device_dir.resolve()).lower()
    except OSError:
        resolved = str(device_dir).lower()
    if any(marker in resolved for marker in INTERNAL_CONNECTOR_MARKERS):
        return True
    # لوحات معروفة لا تعرض الموصّل في مسارها (acpi_video0 على عتاد قديم)
    return name in {'acpi_video0', 'intel_backlight', 'amdgpu_bl0', 'amdgpu_bl1',
                    'nv_backlight', 'apple_backlight'}


def _read_int(path: Path) -> Optional[int]:
    try:
        return int(path.read_text(errors='ignore').strip())
    except (OSError, ValueError):
        return None


def read_backlights(backlight_root: Path = BACKLIGHT_ROOT,
                    internal_only: bool = True) -> Tuple[Backlight, ...]:
    """قراءة أجهزة السطوع المتاحة. الافتراضي: اللوحة الداخلية وحدها"""
    backlight_root = Path(backlight_root)
    if not backlight_root.exists():
        return ()

    devices: List[Backlight] = []
    try:
        entries = sorted(backlight_root.iterdir())
    except OSError as e:
        logger.warning(f"ضبط: تعذّر سرد أجهزة السطوع: {e}")
        return ()

    for entry in entries:
        current = _read_int(entry / 'brightness')
        maximum = _read_int(entry / 'max_brightness')
        if current is None or maximum is None or maximum <= 0:
            continue
        internal = _backlight_is_internal(entry)
        if internal_only and not internal:
            continue
        devices.append(Backlight(name=entry.name, path=entry, current=current,
                                 maximum=maximum, internal=internal))
    return tuple(devices)


# ═══════════════════════════════════════════════════════════
# كتابة السطوع: مسار مصرَّح به للجلسة، بلا كلمة مرور
# ═══════════════════════════════════════════════════════════

class BrightnessWriter:
    """
    يكتب السطوع عبر أول مسار متاح، بترتيب مقصود:

    1. `org.gnome.SettingsDaemon.Power.Screen` (نسبة مئوية): يحدّث شريط
       النظام أيضاً، فيرى المستخدم ما جرى ويستطيع إرجاعه بنفسه.
    2. `org.freedesktop.login1.Session.SetBrightness` (قيمة خام): معيار
       يعمل على كل سطح مكتب حديث، مصرَّح به لمالك الجلسة النشطة.
    3. كتابة مباشرة في sysfs: فقط إذا كان الملف قابلاً للكتابة أصلاً.

    لا مسار رابع. الرفع إلى الجذر لضبط السطوع خطأ أمني لا حلّ.
    """

    GNOME_ARGS = ('gdbus', 'call', '--session',
                  '--dest', 'org.gnome.SettingsDaemon.Power',
                  '--object-path', '/org/gnome/SettingsDaemon/Power',
                  '--method', 'org.freedesktop.DBus.Properties.Set',
                  'org.gnome.SettingsDaemon.Power.Screen', 'Brightness')

    LOGIND_ARGS = ('gdbus', 'call', '--system',
                   '--dest', 'org.freedesktop.login1',
                   '--object-path', '/org/freedesktop/login1/session/auto',
                   '--method', 'org.freedesktop.login1.Session.SetBrightness',
                   'backlight')

    def __init__(self, runner=None):
        #: يُحقَن في الاختبارات: (args) -> (returncode, output)
        self._run = runner or self._default_runner
        self._backend: Optional[str] = None

    @staticmethod
    def _default_runner(args: Sequence[str]) -> Tuple[int, str]:
        try:
            result = subprocess.run(list(args), capture_output=True, text=True,
                                    timeout=COMMAND_TIMEOUT, check=False)
            return result.returncode, (result.stdout or '') + (result.stderr or '')
        except FileNotFoundError:
            return 127, 'command-not-found'
        except subprocess.TimeoutExpired:
            return 124, 'timeout'
        except OSError as e:  # pragma: no cover - بيئة نظام غير متوقعة
            return 1, str(e)

    # ── الكتابة ─────────────────────────────────────────────

    def write(self, device: Backlight, raw_value: int) -> Tuple[bool, str]:
        """
        كتابة قيمة خام. يعيد (نجح، اسم المسار المستخدم أو سبب الفشل).
        القيمة تُقيَّد داخل [1, max] قبل أي محاولة.
        """
        raw_value = max(1, min(device.maximum, int(raw_value)))
        percent = max(1, min(100, round(raw_value * 100 / device.maximum)))

        code, output = self._run(self.GNOME_ARGS + (f'<int32 {percent}>',))
        if code == 0:
            self._backend = 'gnome'
            return True, 'gnome'

        code, output = self._run(self.LOGIND_ARGS + (device.name, str(raw_value)))
        if code == 0:
            self._backend = 'logind'
            return True, 'logind'

        target = device.path / 'brightness'
        if os.access(target, os.W_OK):
            try:
                target.write_text(f'{raw_value}\n')
                self._backend = 'sysfs'
                return True, 'sysfs'
            except OSError as e:
                return False, f'sysfs:{e}'

        return False, f'no-permitted-path:{output.strip()[:120]}'

    def probe(self) -> str:
        """اسم المسار المتاح دون تغيير أي قيمة (للتشخيص والواجهة)"""
        if self._backend:
            return self._backend
        code, _ = self._run(('gdbus', 'introspect', '--session', '--dest',
                             'org.gnome.SettingsDaemon.Power', '--object-path',
                             '/org/gnome/SettingsDaemon/Power'))
        if code == 0:
            return 'gnome'
        code, _ = self._run(('gdbus', 'introspect', '--system', '--dest',
                             'org.freedesktop.login1', '--object-path',
                             '/org/freedesktop/login1/session/auto'))
        if code == 0:
            return 'logind'
        for device in read_backlights():
            if os.access(device.path / 'brightness', os.W_OK):
                return 'sysfs'
        return 'none'


# ═══════════════════════════════════════════════════════════
# نتيجة إجراء واحد: صادقة عن الأثر وعن قابلية التراجع
# ═══════════════════════════════════════════════════════════

@dataclass
class TuningResult:
    """
    نتيجة إجراء ضبط واحد.

    `applied=False` مع `reason` ليست فشلاً بل امتناعاً مُعلَناً في معظم
    الحالات: هذا هو الفرق بين تطبيق يقول ما فعل وتطبيق يزعم النجاح.
    """

    action: str
    applied: bool = False
    reversible: bool = True
    reason: str = ''
    detail: Dict = field(default_factory=dict)

    def as_dict(self) -> Dict:
        return {'action': self.action, 'applied': self.applied,
                'reversible': self.reversible, 'reason': self.reason,
                'detail': dict(self.detail)}


# ═══════════════════════════════════════════════════════════
# بوابات السلامة
# ═══════════════════════════════════════════════════════════

def graphics_tuning_allowed(displays: DisplayState) -> Tuple[bool, str]:
    """
    هل يجوز لمس إدارة طاقة الرسوم.

    الجواب لا كلما وُجدت شاشة خارجية أو تعذّرت القراءة. إجبار مستوى أداء
    الرسوم على «منخفض» أو تسليم البطاقة لإدارة طاقة تلقائية أثناء وصل شاشة
    خارجية يسقط الوصلة، وهذا ما اشتكى منه المستخدم فعلاً.
    """
    if not displays.readable:
        return False, 'displays_unreadable'
    if displays.has_external:
        return False, 'external_display_connected'
    return True, ''


def usb_tuning_allowed(displays: DisplayState) -> Tuple[bool, str]:
    """
    تعليق أجهزة USB تلقائياً: ممنوع دائماً في هذا الإصدار.

    التعليق الشامل لكل ما في `/sys/bus/usb/devices/*/power/control` كان يفصل
    محطات الإرساء ولوحات المفاتيح والفأرة. لا يوجد تمييز موثوق للجهاز الآمن
    من داخل التطبيق، وإدارة طاقة USB وظيفة `TLP` أو `powertop` بإعداد صريح
    من المستخدم لا قرار خفي من محسّن بطارية.
    """
    return False, 'unsafe_by_design'


# ═══════════════════════════════════════════════════════════
# المحرك
# ═══════════════════════════════════════════════════════════

class SafeTuner:
    """
    كل تغيير على النظام يمرّ من هنا: يقيس، يلتقط الأصل، يغيّر ما يجوز،
    ويستعيد بطلب واحد.
    """

    def __init__(self, drm_root: Path = DRM_ROOT,
                 backlight_root: Path = BACKLIGHT_ROOT,
                 writer: Optional[BrightnessWriter] = None,
                 snapshot_file: str = SNAPSHOT_FILE):
        self.drm_root = Path(drm_root)
        self.backlight_root = Path(backlight_root)
        self.writer = writer or BrightnessWriter()
        self.snapshot_file = snapshot_file
        self._snapshot: Dict = self._load_snapshot()

    # ── اللقطة ──────────────────────────────────────────────

    def _load_snapshot(self) -> Dict:
        try:
            from storage import load_json_data
            data = load_json_data(self.snapshot_file, None)
            return data if isinstance(data, dict) else {}
        except Exception as e:  # pragma: no cover - تخزين غير متاح
            logger.debug(f"ضبط: تعذّر تحميل اللقطة: {e}")
            return {}

    def _save_snapshot(self) -> None:
        try:
            from storage import save_json_data
            save_json_data(self.snapshot_file, self._snapshot)
        except Exception as e:  # pragma: no cover
            logger.debug(f"ضبط: تعذّر حفظ اللقطة: {e}")

    @property
    def snapshot(self) -> Dict:
        """اللقطة الحالية (للعرض والاختبار)"""
        return dict(self._snapshot)

    def has_pending_restore(self) -> bool:
        """هل يوجد تغيير مطبَّق ينتظر الاستعادة"""
        return bool(self._snapshot.get('brightness'))

    # ── القياس ──────────────────────────────────────────────

    def displays(self) -> DisplayState:
        return read_display_state(self.drm_root)

    def internal_backlights(self) -> Tuple[Backlight, ...]:
        return read_backlights(self.backlight_root, internal_only=True)

    def capabilities(self) -> Dict:
        """ما يستطيعه هذا الجهاز فعلاً، بلا وعود"""
        displays = self.displays()
        panels = self.internal_backlights()
        graphics_ok, graphics_reason = graphics_tuning_allowed(displays)
        return {
            'displays': displays.as_dict(),
            'panels': [panel.as_dict() for panel in panels],
            'brightness_backend': self.writer.probe() if panels else 'none',
            'can_dim': bool(panels),
            'can_tune_graphics': graphics_ok,
            'graphics_blocked_reason': graphics_reason,
            'can_tune_usb': False,
            'pending_restore': self.has_pending_restore(),
        }

    # ── السطوع ──────────────────────────────────────────────

    def dim_internal_panel(self, step_percent: int = BRIGHTNESS_STEP_PERCENT,
                           floor_percent: int = BRIGHTNESS_FLOOR_PERCENT
                           ) -> TuningResult:
        """
        خفض سطوع اللوحة الداخلية خفضاً نسبياً واحداً.

        الشروط كلها لازمة، وأي واحدة تفشل تعني امتناعاً مُعلَناً لا كتابة:
        - يوجد جهاز سطوع داخلي.
        - القيمة الحالية أعلى من الحدّ الأدنى بعد الخفض.
        - لم يغيّر المستخدم السطوع بعد آخر كتابة لنا (وإن غيّره، يُعاد
          التقاط الأصل على قيمته الجديدة ولا يُرفَع إليها شيء).

        لا تُرفع القيمة أبداً: `target < current` شرط رياضي لا استثناء له.
        """
        panels = self.internal_backlights()
        if not panels:
            return TuningResult('dim_panel', reason='no_internal_panel')

        floor_percent = max(5, min(95, int(floor_percent)))
        step_percent = max(1, min(60, int(step_percent)))

        applied_any = False
        details: List[Dict] = []
        reason = ''
        store = dict(self._snapshot.get('brightness') or {})

        for panel in panels:
            record = store.get(panel.name)
            if record and record.get('last_written') is not None:
                if int(record['last_written']) != panel.current:
                    # المستخدم تدخّل بعد كتابتنا: تغييرنا لم يبق قائماً، فلا
                    # يجوز أن نحتفظ بحقّ استعادة قيمة لم نعد نحن من ضبطها
                    store.pop(panel.name, None)
                    record = None

            if panel.percent <= floor_percent:
                details.append({'panel': panel.name, 'skipped': 'already_at_floor',
                                'percent': panel.percent})
                reason = reason or 'already_at_floor'
                continue

            target_percent = max(floor_percent, panel.percent - step_percent)
            target_raw = panel.raw_for_percent(target_percent)
            if target_raw >= panel.current:
                details.append({'panel': panel.name, 'skipped': 'no_headroom',
                                'percent': panel.percent})
                reason = reason or 'no_headroom'
                continue

            ok, backend = self.writer.write(panel, target_raw)
            if not ok:
                details.append({'panel': panel.name, 'failed': backend,
                                'percent': panel.percent})
                reason = reason or backend
                continue

            # اللقطة تُكتب بعد نجاح الكتابة وحده. كتابتها عند الامتناع كانت
            # تُنشئ «تغييراً ينتظر الاستعادة» بلا تغيير، فيُعيد زر الاستعادة
            # لاحقاً قيمة لم يضبطها التطبيق أصلاً.
            store[panel.name] = {
                'original': (record or {}).get('original', panel.current),
                'maximum': panel.maximum,
                'last_written': target_raw,
                'written_at': time.time(),
                'backend': backend,
            }
            applied_any = True
            details.append({'panel': panel.name, 'from': panel.percent,
                            'to': target_percent, 'backend': backend})

        if store:
            self._snapshot['brightness'] = store
        else:
            self._snapshot.pop('brightness', None)
        self._save_snapshot()

        return TuningResult('dim_panel', applied=applied_any, reversible=True,
                            reason='' if applied_any else reason,
                            detail={'panels': details, 'floor': floor_percent})

    def restore_brightness(self) -> TuningResult:
        """إرجاع السطوع إلى القيمة التي كانت قبل أول خفض منّا"""
        store = dict(self._snapshot.get('brightness') or {})
        if not store:
            return TuningResult('restore_brightness', reason='nothing_to_restore')

        panels = {panel.name: panel for panel in self.internal_backlights()}
        details: List[Dict] = []
        restored_any = False
        remaining: Dict[str, Dict] = {}

        for name, record in store.items():
            panel = panels.get(name)
            original = record.get('original')
            if panel is None or original is None:
                details.append({'panel': name, 'skipped': 'panel_absent'})
                continue
            if panel.current == int(original):
                details.append({'panel': name, 'skipped': 'already_original'})
                restored_any = True
                continue
            ok, backend = self.writer.write(panel, int(original))
            if ok:
                details.append({'panel': name, 'to': int(original),
                                'backend': backend})
                restored_any = True
            else:
                # ما فشلت استعادته يبقى في اللقطة: حذفه يعني فقدان طريق الرجوع
                details.append({'panel': name, 'failed': backend})
                remaining[name] = record

        if remaining:
            self._snapshot['brightness'] = remaining
        else:
            self._snapshot.pop('brightness', None)
        self._save_snapshot()

        return TuningResult('restore_brightness', applied=restored_any,
                            reversible=True,
                            reason='' if restored_any else 'restore_failed',
                            detail={'panels': details})

    # ── الاستعادة الشاملة ───────────────────────────────────

    def restore_all(self) -> List[TuningResult]:
        """إرجاع كل ما غيّره التطبيق. تُستدعى يدوياً وعند الإغلاق النظيف"""
        results = [self.restore_brightness()]
        return [result for result in results if result.reason != 'nothing_to_restore']
