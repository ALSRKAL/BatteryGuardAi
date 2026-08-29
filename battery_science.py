#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
محرك علم البطارية - BatteryGuardAI

وحدة نقية (بلا Qt وبلا حالة عالمية) تحوّل قياسات البطارية إلى أرقام تآكل
حقيقية: تآكل تقويمي بدلالة درجة الحرارة ومستوى الشحن، تآكل دوري بدلالة عمق
التفريغ، مؤشر إجهاد لحظي، وتقدير للعمر المتبقي حتى نهاية العمر الافتراضي.

كل ثابت هنا مأخوذ من مرجع منشور ومُسمّى في `SOURCES`، ولا يُضاف رقم بلا مصدر.
المراجع (تمت إعادة صياغة محتواها، والأرقام مستخرجة من جداولها):

- Battery University, BU-808 "How to Prolong Lithium-based Batteries"
  https://batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries
  الجدول 2: عدد الدورات بدلالة عمق التفريغ حتى هبوط السعة إلى 70%.
  الجدول 3: السعة المستردة بعد سنة تخزين بدلالة الحرارة ومستوى الشحن.
  وأيضاً: تجاوز 4.10 فولت للخلية يُعدّ جهداً عالياً، وما فوق 30°م حرارة مرتفعة،
  وكل تخفيض 0.10 فولت في جهد الشحن الأقصى يضاعف عدد الدورات تقريباً.
- Battery University, BU-502 "Discharging at High and Low Temperatures"
  https://www.batteryuniversity.com/article/bu-502-discharging-at-high-and-low-temperatures
  التشغيل عند 30°م بدل ~20°م يقلّص عمر الدورات بنحو 20%.
- USABC / Sandia National Laboratories: 80% من السعة الابتدائية هي حدّ نهاية
  العمر الافتراضي المتعارف عليه.
  https://www.sandia.gov/files/ess/uploads/2021/ESSRF/Preger_Yuliya.pdf

ملاحظة صدق مهمة: هذه الجداول تصف خلايا ليثيوم-كوبالت/NMC تجارية كاتجاه عام،
والبطاريات لا تتصرف كلها بنفس الشكل. لذلك كل ناتج هنا يحمل حقل `assumed`
أو `confidence` حين يُبنى على قيمة غير مقروءة من العتاد.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# ═══════════════════════════════════════════════════════════
# المصادر (تُعرض للمستخدم كسند لكل توصية)
# ═══════════════════════════════════════════════════════════

SOURCES: Dict[str, Dict[str, str]] = {
    'bu808': {
        'label': 'Battery University BU-808',
        'url': 'https://batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries',
    },
    'bu502': {
        'label': 'Battery University BU-502',
        'url': 'https://www.batteryuniversity.com/article/bu-502-discharging-at-high-and-low-temperatures',
    },
    'usabc': {
        'label': 'USABC / Sandia',
        'url': 'https://www.sandia.gov/files/ess/uploads/2021/ESSRF/Preger_Yuliya.pdf',
    },
}

# ═══════════════════════════════════════════════════════════
# الثوابت المرجعية
# ═══════════════════════════════════════════════════════════

#: حدّ نهاية العمر الافتراضي المتعارف عليه (% من السعة التصميمية) - USABC
END_OF_LIFE_SOH = 80.0

#: حرارة مرجعية تُفترض عند غياب حسّاس حرارة (°م)
ASSUMED_TEMP_C = 25.0

#: ما فوقها تُعدّ الحرارة مرتفعة (°م) - BU-808
ELEVATED_TEMP_C = 30.0

#: نافذة الشحن الأقل إجهاداً للاستخدام اليومي (%)
OPTIMAL_WINDOW: Tuple[int, int] = (40, 80)

#: فوق هذا المستوى يعمل الجهد العالي على تسريع التآكل - BU-808
HIGH_SOC_THRESHOLD = 80

#: تحت هذا المستوى يبدأ التفريغ العميق بإضافة إجهاد ملحوظ
DEEP_DISCHARGE_THRESHOLD = 20

#: BU-808 الجدول 2 - دورات حتى 70% من السعة، خلايا NMC، مفتاح = عمق التفريغ %
CYCLES_TO_70_BY_DOD: Dict[int, int] = {
    100: 300,
    80: 400,
    60: 600,
    40: 1000,
    20: 2000,
    10: 6000,
}

#: نسبة السعة المفقودة التي تصفها أرقام الجدول 2 (100% ← 70%)
_TABLE2_CAPACITY_SPAN = 30.0

#: BU-808 الجدول 3 - الفقد السنوي % عند (حرارة °م) لمستوى شحن 40% و100%
#: القيمة عند 60°م مقيسة بعد 3 أشهر (40% فقد) وحُوّلت إلى معدل سنوي محافظ.
CALENDAR_LOSS_TABLE: Dict[float, Dict[int, float]] = {
    0.0:  {40: 2.0, 100: 6.0},
    25.0: {40: 4.0, 100: 20.0},
    40.0: {40: 15.0, 100: 35.0},
    60.0: {40: 25.0, 100: 40.0},
}


# ═══════════════════════════════════════════════════════════
# أدوات رقمية صغيرة
# ═══════════════════════════════════════════════════════════

def clamp(value: float, low: float, high: float) -> float:
    """تقييد قيمة داخل مجال"""
    return max(low, min(high, value))


def _interpolate(x: float, points: Sequence[Tuple[float, float]]) -> float:
    """
    استيفاء خطي على نقاط مرتّبة تصاعدياً بـ x، مع تثبيت الأطراف.
    تُستخدم لقراءة جداول المراجع بين قيمها المنشورة بدل التقريب العشوائي.
    """
    if not points:
        return 0.0
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        if x <= x1:
            span = (x1 - x0) or 1.0
            return y0 + (y1 - y0) * (x - x0) / span
    return points[-1][1]


# ═══════════════════════════════════════════════════════════
# التآكل الدوري (عمق التفريغ)
# ═══════════════════════════════════════════════════════════

def cycles_for_dod(dod_percent: float) -> float:
    """
    عدد الدورات المتوقّع عند عمق تفريغ معيّن حتى هبوط السعة إلى 70%.
    مبني على BU-808 الجدول 2 (NMC) باستيفاء بين قيم الجدول.
    """
    dod = clamp(dod_percent, 1.0, 100.0)
    points = sorted((float(k), float(v)) for k, v in CYCLES_TO_70_BY_DOD.items())
    return max(1.0, _interpolate(dod, points))


def cycle_wear_percent(dod_percent: float) -> float:
    """
    السعة المفقودة (% من السعة التصميمية) مقابل دورة واحدة بهذا العمق.
    مشتقّة مباشرة من الجدول 2: 30% سعة موزّعة على عدد دورات ذلك العمق.
    """
    if dod_percent <= 0:
        return 0.0
    return _TABLE2_CAPACITY_SPAN / cycles_for_dod(dod_percent)


def equivalent_full_cycles(total_discharged_percent: float) -> float:
    """تحويل مجموع ما تم تفريغه (بالنسب) إلى دورات كاملة مكافئة"""
    return max(0.0, total_discharged_percent) / 100.0


# ═══════════════════════════════════════════════════════════
# التآكل التقويمي (الحرارة × مستوى الشحن)
# ═══════════════════════════════════════════════════════════

def calendar_loss_percent_per_year(soc_percent: float,
                                   temp_c: Optional[float] = None) -> float:
    """
    الفقد التقويمي السنوي المتوقّع (% من السعة) عند بقاء البطارية عند مستوى
    شحن وحرارة معيّنين. مبني على BU-808 الجدول 3 باستيفاء ثنائي.

    ملاحظة صدق: الجدول يعطي قيمتين فقط لمستوى الشحن (40% و100%). ما دون 40%
    لا يوجد له رقم منشور، فنستخدم قيمة 40% كأفضل حالة بدل اختلاق مكافأة.
    """
    temp = ASSUMED_TEMP_C if temp_c is None else float(temp_c)
    soc = clamp(soc_percent, 0.0, 100.0)

    temps = sorted(CALENDAR_LOSS_TABLE.keys())
    loss_at_40 = _interpolate(temp, [(tp, CALENDAR_LOSS_TABLE[tp][40]) for tp in temps])
    loss_at_100 = _interpolate(temp, [(tp, CALENDAR_LOSS_TABLE[tp][100]) for tp in temps])

    if soc <= 40.0:
        return round(loss_at_40, 3)
    ratio = (soc - 40.0) / 60.0
    return round(loss_at_40 + (loss_at_100 - loss_at_40) * ratio, 3)


def soc_stress_multiplier(soc_percent: float, temp_c: Optional[float] = None) -> float:
    """
    كم يضاعف مستوى الشحن الحالي التآكل مقارنة بالبقاء عند 40% في نفس الحرارة.
    قيمة 1.0 تعني أفضل ما يمكن عند هذه الحرارة.
    """
    base = calendar_loss_percent_per_year(40.0, temp_c)
    if base <= 0:
        return 1.0
    return round(calendar_loss_percent_per_year(soc_percent, temp_c) / base, 3)


def temperature_stress_multiplier(temp_c: Optional[float] = None) -> float:
    """كم تضاعف الحرارة الحالية التآكل مقارنة بالحرارة المرجعية 25°م"""
    base = calendar_loss_percent_per_year(70.0, ASSUMED_TEMP_C)
    if base <= 0:
        return 1.0
    return round(calendar_loss_percent_per_year(70.0, temp_c) / base, 3)


# ═══════════════════════════════════════════════════════════
# الصحة والعمر المتبقي
# ═══════════════════════════════════════════════════════════

def state_of_health(full_capacity: float, design_capacity: float) -> Optional[float]:
    """
    صحة البطارية = السعة الكاملة الحالية ÷ السعة التصميمية.
    يعيد None حين لا يمكن حسابها بدل إرجاع 100% مطمئنة وكاذبة.
    """
    try:
        if design_capacity and design_capacity > 0 and full_capacity > 0:
            return round(clamp(full_capacity / design_capacity * 100.0, 0.0, 100.0), 1)
    except (TypeError, ZeroDivisionError):
        pass
    return None


def days_to_end_of_life(soh_percent: Optional[float],
                        annual_loss_percent: float) -> Optional[int]:
    """
    الأيام المتوقّعة حتى الوصول إلى 80% من السعة التصميمية بمعدل التآكل الحالي.
    يعيد None إذا كانت الصحة غير معروفة، و0 إذا كان الحدّ قد تجاوزناه أصلاً.
    """
    if soh_percent is None:
        return None
    if soh_percent <= END_OF_LIFE_SOH:
        return 0
    if annual_loss_percent <= 0.01:
        return None
    remaining = soh_percent - END_OF_LIFE_SOH
    return int(remaining / annual_loss_percent * 365)


def projected_annual_loss(soc_profile: Optional[Dict[int, float]] = None,
                          temp_c: Optional[float] = None,
                          discharge_events: Optional[Sequence[float]] = None,
                          days_observed: float = 1.0) -> Dict[str, float]:
    """
    الفقد السنوي المتوقّع = تآكل تقويمي (حسب توزيع الوقت على مستويات الشحن)
    + تآكل دوري (حسب أعماق التفريغ المرصودة فعلاً).

    soc_profile: {مستوى الشحن %: نسبة الوقت 0..1}
    discharge_events: أعماق التفريغ المرصودة (%) خلال `days_observed` يوماً.
    """
    calendar = 0.0
    if soc_profile:
        total_weight = sum(max(0.0, w) for w in soc_profile.values()) or 1.0
        for soc, weight in soc_profile.items():
            calendar += calendar_loss_percent_per_year(float(soc), temp_c) * (max(0.0, weight) / total_weight)
    else:
        calendar = calendar_loss_percent_per_year(70.0, temp_c)

    cyclic = 0.0
    if discharge_events:
        observed = sum(cycle_wear_percent(d) for d in discharge_events if d > 0)
        days = max(0.5, days_observed)
        cyclic = observed / days * 365.0

    return {
        'calendar': round(calendar, 3),
        'cyclic': round(cyclic, 3),
        'total': round(calendar + cyclic, 3),
        'temp_assumed': temp_c is None,
    }


# ═══════════════════════════════════════════════════════════
# مؤشر الإجهاد اللحظي
# ═══════════════════════════════════════════════════════════

STRESS_BANDS: Tuple[Tuple[int, str], ...] = (
    (25, 'low'),
    (50, 'moderate'),
    (75, 'high'),
    (101, 'severe'),
)


def stress_band(index: float) -> str:
    """تحويل مؤشر الإجهاد إلى نطاق مسمّى"""
    for ceiling, name in STRESS_BANDS:
        if index < ceiling:
            return name
    return 'severe'


def stress_index(soc_percent: float,
                 temp_c: Optional[float] = None,
                 is_charging: bool = False,
                 charging_above_ceiling: bool = False) -> Dict[str, object]:
    """
    مؤشر إجهاد لحظي 0..100 مبني على معدل الفقد التقويمي في هذه اللحظة،
    مُعاير على مجال الجدول 3 (من أفضل حالة عند 0°م/40% إلى أسوأ حالة).

    يُضاف إجهاد صغير عند الشحن فوق السقف الموصى به لأن الجهد يبقى مرتفعاً
    أطول (BU-808)، ويُضاف عند التفريغ العميق.
    """
    loss_now = calendar_loss_percent_per_year(soc_percent, temp_c)
    best = CALENDAR_LOSS_TABLE[0.0][40]
    worst = CALENDAR_LOSS_TABLE[60.0][100]
    span = max(0.1, worst - best)
    index = (loss_now - best) / span * 100.0

    if is_charging and charging_above_ceiling:
        index += 8.0
    if soc_percent < DEEP_DISCHARGE_THRESHOLD:
        index += (DEEP_DISCHARGE_THRESHOLD - soc_percent) * 0.4

    index = clamp(index, 0.0, 100.0)
    return {
        'index': round(index, 1),
        'band': stress_band(index),
        'annual_loss_at_this_state': loss_now,
        'soc_multiplier': soc_stress_multiplier(soc_percent, temp_c),
        'temp_multiplier': temperature_stress_multiplier(temp_c),
        'temp_assumed': temp_c is None,
    }


# ═══════════════════════════════════════════════════════════
# أثر تغيير سقف الشحن (رقم ملموس للمستخدم)
# ═══════════════════════════════════════════════════════════

def ceiling_saving_percent_per_year(current_ceiling: int,
                                    proposed_ceiling: int,
                                    hours_plugged_per_day: float = 12.0,
                                    temp_c: Optional[float] = None) -> float:
    """
    كم سعة (% سنوياً) يوفّرها خفض سقف الشحن، بافتراض بقاء الجهاز موصولاً
    عدد ساعات معيّناً يومياً عند السقف. مشتق من BU-808 الجدول 3.
    """
    share = clamp(hours_plugged_per_day, 0.0, 24.0) / 24.0
    now = calendar_loss_percent_per_year(current_ceiling, temp_c) * share
    proposed = calendar_loss_percent_per_year(proposed_ceiling, temp_c) * share
    return round(max(0.0, now - proposed), 2)


def recommend_ceiling(hours_on_battery_per_day: float,
                      typical_dod: float,
                      soh_percent: Optional[float] = None) -> Dict[str, object]:
    """
    اقتراح سقف شحن يوازن بين حماية البطارية واحتياج المستخدم الفعلي للاستقلالية.
    كلما زاد اعتماد المستخدم على البطارية ارتفع السقف الموصى به.
    """
    if hours_on_battery_per_day >= 5 or typical_dod >= 60:
        ceiling, reason = 90, 'high_autonomy_need'
    elif hours_on_battery_per_day >= 2 or typical_dod >= 30:
        ceiling, reason = 85, 'moderate_autonomy_need'
    else:
        ceiling, reason = 80, 'mostly_plugged'

    if soh_percent is not None and soh_percent < 60 and ceiling < 90:
        # بطارية متهالكة: رفع السقف يمنح المستخدم زمناً قابلاً للاستخدام
        ceiling, reason = ceiling + 5, 'degraded_needs_headroom'

    floor = max(20, min(OPTIMAL_WINDOW[0], ceiling - 30))
    return {'ceiling': int(ceiling), 'floor': int(floor), 'reason': reason}


# ═══════════════════════════════════════════════════════════
# لقطة الحالة والنصيحة المهيكلة
# ═══════════════════════════════════════════════════════════

@dataclass
class BatterySnapshot:
    """كل ما يحتاجه مولّد النصائح، مقروءاً من العتاد أو متعلّماً من الاستخدام"""
    percent: float = 0.0
    is_charging: bool = False
    reporting: bool = True                     # هل البطارية تُبلّغ بقيم معقولة
    temp_c: Optional[float] = None
    soh_percent: Optional[float] = None
    cycle_count: Optional[int] = None
    drain_rate_pct_min: float = 0.0
    charge_rate_pct_min: float = 0.0
    hours_high_soc_per_day: float = 0.0        # ساعات فوق سقف الشحن الصحي
    hours_plugged_per_day: float = 12.0
    hours_on_battery_per_day: float = 0.0
    typical_dod: float = 0.0                   # عمق التفريغ المعتاد %
    control_available: bool = False            # هل يوجد مسار تحكم فعلي
    control_active: bool = False               # هل التحكم مفعّل الآن
    ceiling: int = OPTIMAL_WINDOW[1]
    floor: int = OPTIMAL_WINDOW[0]
    heavy_usage_hours: List[int] = field(default_factory=list)
    night_usage_score: float = 0.0             # ميل مرصود للاستخدام الليلي
    hour: int = 0


SEVERITY_ORDER = {'critical': 0, 'warning': 1, 'advice': 2, 'good': 3}


@dataclass
class Advice:
    """
    نصيحة واحدة: معرّف ثابت، شدّة، مفتاح ترجمة مع معاملاته، وسند.

    `evidence` يشير إلى مفتاح في SOURCES أو `measured` حين يكون السند قياساً
    من نفس الجهاز. `action` معرّف إجراء تنفّذه الواجهة (لا نص).
    """
    id: str
    severity: str
    key: str
    params: Dict[str, object] = field(default_factory=dict)
    evidence: Optional[str] = None
    action: Optional[str] = None

    @property
    def rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 9)


def build_advice(snap: BatterySnapshot, limit: int = 6) -> List[Advice]:
    """
    توليد نصائح مرتّبة بالشدّة من لقطة الحالة.

    قواعد ثابتة:
    - لا نصيحة بلا سند: قياس من الجهاز أو مرجع منشور.
    - البطارية التي لا تُبلّغ لا تُنتج تنبيهات مستوى شحن كاذبة.
    - لا تكرار: كل معرّف يظهر مرة واحدة.
    """
    out: List[Advice] = []

    # ── بطارية لا تُبلّغ: تشخيص واحد صادق، لا تنبيهات وهمية ──
    if not snap.reporting:
        out.append(Advice(
            id='battery_not_reporting',
            severity='warning',
            key='advice.battery_not_reporting',
            evidence='measured',
            action='open_diagnostics',
        ))
        return out

    pct = snap.percent
    temp = snap.temp_c

    # ── مستويات حرجة ──
    if not snap.is_charging and pct <= 10:
        out.append(Advice(
            id='critical_low', severity='critical',
            key='advice.critical_low', params={'percent': int(pct)},
            evidence='measured', action='plug_in',
        ))
    elif not snap.is_charging and pct < DEEP_DISCHARGE_THRESHOLD:
        minutes = int((pct - 10) / snap.drain_rate_pct_min) if snap.drain_rate_pct_min > 0 else None
        out.append(Advice(
            id='deep_discharge', severity='warning',
            key='advice.deep_discharge' if minutes is None else 'advice.deep_discharge_eta',
            params={'percent': int(pct), 'minutes': minutes or 0,
                    'cycles': int(cycles_for_dod(100 - pct))},
            evidence='bu808', action='plug_in',
        ))

    # ── الجهد العالي: البقاء فوق السقف ──
    if snap.is_charging and pct >= 95:
        out.append(Advice(
            id='full_charge_dwell', severity='warning',
            key='advice.full_charge_dwell',
            params={'loss': calendar_loss_percent_per_year(100, temp),
                    'best': calendar_loss_percent_per_year(40, temp)},
            evidence='bu808', action='unplug',
        ))
    elif snap.is_charging and pct >= snap.ceiling:
        saving = ceiling_saving_percent_per_year(100, snap.ceiling,
                                                snap.hours_plugged_per_day, temp)
        out.append(Advice(
            id='above_ceiling', severity='advice',
            key='advice.above_ceiling',
            params={'ceiling': snap.ceiling, 'saving': saving},
            evidence='bu808', action='unplug',
        ))

    if snap.hours_high_soc_per_day >= 4:
        out.append(Advice(
            id='high_soc_habit', severity='warning',
            key='advice.high_soc_habit',
            params={'hours': round(snap.hours_high_soc_per_day, 1),
                    'multiplier': round(soc_stress_multiplier(95, temp), 1)},
            evidence='bu808',
            action='enable_control' if snap.control_available and not snap.control_active else 'lower_ceiling',
        ))

    # ── الحرارة ──
    if temp is not None and temp >= ELEVATED_TEMP_C:
        out.append(Advice(
            id='elevated_temp', severity='warning',
            key='advice.elevated_temp',
            params={'temp': round(temp, 1),
                    'multiplier': round(temperature_stress_multiplier(temp), 1)},
            evidence='bu502', action='cool_down',
        ))

    # ── الصحة والعمر ──
    if snap.soh_percent is not None:
        if snap.soh_percent <= END_OF_LIFE_SOH:
            out.append(Advice(
                id='end_of_life', severity='warning',
                key='advice.end_of_life',
                params={'soh': snap.soh_percent, 'eol': int(END_OF_LIFE_SOH)},
                evidence='usabc', action='open_health',
            ))
        elif snap.soh_percent >= 95:
            out.append(Advice(
                id='health_strong', severity='good',
                key='advice.health_strong', params={'soh': snap.soh_percent},
                evidence='measured',
            ))

    # ── التحكم الفعلي ──
    if snap.control_available and not snap.control_active:
        rec = recommend_ceiling(snap.hours_on_battery_per_day, snap.typical_dod, snap.soh_percent)
        out.append(Advice(
            id='enable_control', severity='advice',
            key='advice.enable_control',
            params={'ceiling': rec['ceiling'], 'floor': rec['floor'],
                    'saving': ceiling_saving_percent_per_year(
                        100, int(rec['ceiling']), snap.hours_plugged_per_day, temp)},
            evidence='bu808', action='enable_control',
        ))
    elif not snap.control_available:
        out.append(Advice(
            id='no_control_path', severity='advice',
            key='advice.no_control_path',
            evidence='measured', action='open_capability',
        ))

    # ── الأنماط المتعلَّمة من هذا المستخدم (سندها قياسه الخاص) ──
    if not snap.is_charging and snap.percent < 60 and snap.hour in snap.heavy_usage_hours:
        out.append(Advice(
            id='heavy_hour_ahead', severity='advice',
            key='advice.heavy_hour_ahead', params={'hour': snap.hour},
            evidence='measured', action='plug_in',
        ))

    is_night = snap.hour >= 22 or snap.hour <= 6
    if (not snap.is_charging and is_night and snap.percent < 50
            and snap.night_usage_score > 50):
        out.append(Advice(
            id='night_usage', severity='advice',
            key='advice.night_usage', params={'score': int(snap.night_usage_score)},
            evidence='measured', action='plug_in',
        ))

    # ── الاستهلاك المرصود ──
    if not snap.is_charging and snap.drain_rate_pct_min > 1.5:
        out.append(Advice(
            id='high_drain', severity='advice',
            key='advice.high_drain',
            params={'rate': round(snap.drain_rate_pct_min, 2)},
            evidence='measured', action='optimize',
        ))

    # ── النطاق الصحي ──
    if not snap.is_charging and snap.floor <= pct <= snap.ceiling:
        out.append(Advice(
            id='in_window', severity='good',
            key='advice.in_window',
            params={'floor': snap.floor, 'ceiling': snap.ceiling},
            evidence='bu808',
        ))

    out.sort(key=lambda a: a.rank)
    unique: List[Advice] = []
    seen = set()
    for advice in out:
        if advice.id in seen:
            continue
        seen.add(advice.id)
        unique.append(advice)
    return unique[:limit]
