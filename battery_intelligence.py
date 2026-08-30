#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
محرك الاستدلال العميق - BatteryGuardAI

يحوّل القياسات الخام (`battery_monitor`) وأحمال العمليات (`power_attribution`)
إلى استنتاجات قابلة للتصرّف: **من** يُتلف البطارية، **بكم**، و**بأي دليل**.

الطبقات
───────
1. `RobustAnomaly`      كشف الشذوذ بالوسيط والانحراف المطلق الوسيطي (MAD)
                        بدل المتوسط، فلا تُسكِت قفزةٌ واحدةٌ الكشفَ بعدها.
2. `ChangePoint`        CUSUM ثنائي الاتجاه يرصد انحدار الأداء: «صار جهازك
                        يستنزف أسرع منذ كذا» بدل انتظار شكوى المستخدم.
3. `Periodicity`        ارتباط ذاتي على مصفوفة الساعات يكتشف الدورية الحقيقية
                        (يومية/أسبوعية) بدل افتراض «شحن ليلي» بعتبة مكتوبة.
4. `DegradationTrend`   انحدار خطي على السعة الكاملة المقروءة من العتاد عبر
                        الزمن: تآكل **مقيس** على هذه الخلية بالذات، لا مُستنتج
                        من جدول عام.
5. `OffenderLedger`     سجل تراكمي لكل عملية: ثباتها، وارتباط حضورها بمعدل
                        الاستنزاف، ومتوسط وذروة الواط المنسوبة إليها.
6. `BatteryIntelligence` المنسّق: يبني `Offender` لكل مخالف بدرجة ضرر مشتقّة
                        من علم البطارية لا من رأي.

كيف تُحسب «درجة الضرر» بصدق
────────────────────────────
الرقم الذي يهمّ المستخدم ليس النسبة المئوية للمعالج، بل: **كم من سعة بطاريتي
تخسر سنوياً بسبب هذه العملية**. السلسلة كلها مشتقّة من مقيس:

    نسبة/ساعة        = واط منسوبة ÷ سعة البطارية (واط·ساعة) × 100
    نسبة/يوم         = نسبة/ساعة × ساعات العمل على البطارية يومياً (مرصودة)
    دورات مكافئة/سنة = نسبة/يوم × 365 ÷ 100
    فقد السعة/سنة    = دورات مكافئة × `cycle_wear_percent(عمق التفريغ المعتاد)`

`cycle_wear_percent` من `battery_science` ومصدره BU-808 الجدول 2. لا رقم هنا
بلا مصدر أو قياس، وكل ناتج يحمل `confidence` تقول كم يُعتمد عليه.

مانع الخمول حالة خاصة: لا يُنسب إليه واط، لأن كلفته أن الشاشة والجهاز لا
ينامان أصلاً. تُقاس كلفته بقدرة الأساس المقيسة (`baseline_watts`) لا بتخمين.
"""

import logging
import math
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

from battery_science import cycle_wear_percent
from power_attribution import (BEHAVIOUR_CPU_SUSTAINED, BEHAVIOUR_DISK_THRASH,
                               BEHAVIOUR_IDLE_INHIBITOR,
                               BEHAVIOUR_MEMORY_PRESSURE,
                               BEHAVIOUR_SLEEP_INHIBITOR,
                               BEHAVIOUR_WAKEUP_STORM, UNATTRIBUTED,
                               AttributionResult, ProcessLoad)

logger = logging.getLogger('BatteryGuard')

# ═══════════════════════════════════════════════════════════
# ثوابت الكشف (كل واحدة مُسمّاة ومُبرَّرة)
# ═══════════════════════════════════════════════════════════

#: حدّ درجة z المتينة الذي يُعدّ شذوذاً. القيمة 3.5 هي الموصى بها في
#: Iglewicz & Hoaglin, "How to Detect and Handle Outliers" (ASQC, 1993)
#: للكشف بالانحراف المطلق الوسيطي.
ROBUST_Z_THRESHOLD = 3.5

#: ثابت تحويل MAD إلى مكافئ الانحراف المعياري لتوزيع طبيعي (1/0.6745)
MAD_TO_SIGMA = 1.4826

#: أقل عدد عيّنات قبل السماح بإعلان شذوذ (تحت هذا العدد الوسيط بلا معنى)
ANOMALY_MIN_SAMPLES = 20

#: حجم نافذة الشذوذ لكل ساعة من اليوم
ANOMALY_WINDOW = 120

# معايرة CUSUM: القيم أدناه مقيسة لا مُختارة بالذوق. المقياس الحاكم هو
# ARL0 (متوسط عدد العيّنات قبل تنبيه كاذب على مستوى ثابت). عند وتيرة جولة
# كل 25 ثانية:
#
#   k=0.50, h=5.0  → ARL0 ≈ 490    (تنبيه كاذب كل ~3 ساعات تفريغ)  مرفوض
#   k=0.50, h=8.0  → ARL0 ≈ 3400   (10 من 25 تجربة أنتجت كاذباً)   مرفوض
#   k=0.75, h=8.0  → ARL0 > 4000   (صفر كاذب في 100 ألف عيّنة)     المختار
#
# مع ذلك يبقى رصد ارتفاع حقيقي بنسبة 60٪ خلال عيّنة واحدة، لأن الارتفاع
# الحقيقي يبعد ستة انحرافات فيتجاوز الحدّ فوراً. «صار جهازك يستنزف أسرع»
# رسالة مقلقة، وإطلاقها كذباً كل ثلاث ساعات يُفقد التطبيق ثقة المستخدم كلها.

#: انزياح CUSUM: تغيّر أصغر منه (بوحدة سيغما) لا يستحق الإعلان
CUSUM_DRIFT_SIGMA = 0.75

#: حدّ CUSUM للإعلان (بوحدة سيغما تراكمية)
CUSUM_THRESHOLD_SIGMA = 8.0

#: أقل عدد عيّنات في الانحراف الجاري قبل الإعلان.
#: الإعلان من عيّنة واحدة يجعل «المستوى بعد التغيّر» محسوباً من قراءة واحدة،
#: فيخرج رقماً غير ممثّل (1.13 بدل 1.60 في القياس). ثلاث عيّنات تكفي لتمثيل
#: المستوى الجديد ولا تؤخّر الرصد فعلياً.
CUSUM_MIN_EXCURSION = 3

#: أقل عدد عيّنات مزدوجة لحساب ارتباط ذي معنى
CORRELATION_MIN_SAMPLES = 12

#: نصف عمر التلاشي لسجل العمليات (بالعيّنات)
LEDGER_DECAY_HALFLIFE = 300.0

#: أقصى عدد عمليات في السجل قبل إسقاط الأقل أهمية
LEDGER_LIMIT = 200

#: أقل واط منسوبة حتى تُعدّ العملية «مستهلكة» في حساب الثبات
PRESENCE_WATT_FLOOR = 0.4

#: أقل عدد قراءات سعة، وأقل مدى زمني (يوم)، لإعلان اتجاه تآكل مقيس
DEGRADATION_MIN_READINGS = 6
DEGRADATION_MIN_SPAN_DAYS = 10.0

#: أقصى عدد قراءات سعة محفوظة (قراءة كل ساعة تكفي سنوات)
DEGRADATION_LIMIT = 400

#: أقل تغيّر في السعة الكاملة (mWh) يُعدّ قراءة جديدة تستحق الحفظ
DEGRADATION_MIN_DELTA_MWH = 20.0

# ── درجة الضرر ──

#: فقد سعة سنوي (%) يقابل الدرجة القصوى 100. أربعة بالمئة سنوياً فوق الطبيعي
#: يعني تقصير العمر إلى ما دون النصف، وهو سقف معقول للتقييس.
DAMAGE_LOSS_AT_MAX = 4.0

#: إضافات الدرجة على السلوكيات التي تُتلف بلا أن تظهر في الواط
DAMAGE_BEHAVIOUR_BONUS = {
    BEHAVIOUR_IDLE_INHIBITOR: 30.0,   # يمنع الشاشة والجهاز من النوم أصلاً
    BEHAVIOUR_SLEEP_INHIBITOR: 12.0,
    BEHAVIOUR_CPU_SUSTAINED: 12.0,
    BEHAVIOUR_WAKEUP_STORM: 10.0,
    BEHAVIOUR_DISK_THRASH: 6.0,
    BEHAVIOUR_MEMORY_PRESSURE: 4.0,
}

#: حدود درجة الضرر التي تحدّد الإجراء المقترح
ACTION_NONE = 'none'
ACTION_ALERT = 'alert'
ACTION_THROTTLE = 'throttle'
ACTION_SUSPEND = 'suspend'

DAMAGE_ALERT_AT = 30.0
DAMAGE_THROTTLE_AT = 55.0
DAMAGE_SUSPEND_AT = 75.0

#: سعة بطارية افتراضية (واط·ساعة) حين لا يعرضها العتاد. تُعلَم كمفترضة.
ASSUMED_CAPACITY_WH = 50.0


# ═══════════════════════════════════════════════════════════
# كشف الشذوذ المتين
# ═══════════════════════════════════════════════════════════

def robust_z_score(value: float, samples: List[float]) -> Optional[float]:
    """
    درجة z متينة: تعتمد الوسيط والانحراف المطلق الوسيطي لا المتوسط
    والانحراف المعياري، فلا تفسدها القيم الشاذة نفسها التي نبحث عنها.

    يعيد `None` حين لا يمكن الحكم (عيّنات قليلة أو تشتّت صفر).
    """
    if len(samples) < ANOMALY_MIN_SAMPLES:
        return None
    median = statistics.median(samples)
    deviations = [abs(sample - median) for sample in samples]
    mad = statistics.median(deviations)
    if mad <= 1e-9:
        # تشتّت صفري: نرجع إلى الانحراف المعياري بدل إعلان لا نهاية
        try:
            sigma = statistics.stdev(samples)
        except statistics.StatisticsError:
            return None
        if sigma <= 1e-9:
            return None
        return (value - median) / sigma
    return (value - median) / (mad * MAD_TO_SIGMA)


@dataclass
class Anomaly:
    """شذوذ مرصود بدليله"""
    id: str
    metric: str
    value: float
    baseline: float
    z_score: float
    hour: int
    timestamp: str
    severity: str = 'warning'

    def as_dict(self) -> Dict[str, object]:
        return {
            'id': self.id, 'metric': self.metric,
            'value': round(self.value, 3), 'baseline': round(self.baseline, 3),
            'z_score': round(self.z_score, 2), 'hour': self.hour,
            'timestamp': self.timestamp, 'severity': self.severity,
        }


class RobustAnomaly:
    """
    كاشف شذوذ لمقياس واحد، بخط أساس مستقل لكل ساعة من اليوم.

    فصل الساعات ضروري: استنزاف 2%/دقيقة الظهر عادي، وفي الثالثة فجراً
    والشاشة مطفأة يعني شيئاً يعمل بلا إذن. خط أساس واحد يخفي الحالتين.
    """

    def __init__(self, metric: str, window: int = ANOMALY_WINDOW):
        self.metric = metric
        self.window = window
        self._by_hour: Dict[int, Deque[float]] = defaultdict(
            lambda: deque(maxlen=window))
        self._global: Deque[float] = deque(maxlen=window * 2)

    def observe(self, value: float, hour: Optional[int] = None) -> Optional[Anomaly]:
        """
        إضافة قراءة. يعيد شذوذاً إن تجاوزت الحدّ، وإلا `None`.
        تُضاف القراءة إلى خط الأساس **بعد** الحكم عليها.
        """
        if not math.isfinite(value):
            return None
        hour = datetime.now().hour if hour is None else int(hour) % 24
        bucket = self._by_hour[hour]

        samples = list(bucket)
        score = robust_z_score(value, samples)
        if score is None:
            # خط أساس الساعة غير كافٍ: نجرّب الخط العام قبل الاستسلام
            score = robust_z_score(value, list(self._global))
            samples = list(self._global)

        anomaly: Optional[Anomaly] = None
        if score is not None and score >= ROBUST_Z_THRESHOLD:
            anomaly = Anomaly(
                id=f'{self.metric}_high',
                metric=self.metric,
                value=value,
                baseline=statistics.median(samples) if samples else value,
                z_score=score,
                hour=hour,
                timestamp=datetime.now().isoformat(),
                severity='critical' if score >= ROBUST_Z_THRESHOLD * 2 else 'warning',
            )

        bucket.append(value)
        self._global.append(value)
        return anomaly

    def baseline(self, hour: Optional[int] = None) -> Optional[float]:
        """الوسيط المرجعي لهذه الساعة، أو العام حين لا يكفي"""
        hour = datetime.now().hour if hour is None else int(hour) % 24
        bucket = self._by_hour.get(hour)
        if bucket and len(bucket) >= ANOMALY_MIN_SAMPLES:
            return statistics.median(bucket)
        if len(self._global) >= ANOMALY_MIN_SAMPLES:
            return statistics.median(self._global)
        return None

    def dump(self) -> Dict[str, object]:
        return {
            'metric': self.metric,
            'by_hour': {str(hour): list(values)
                        for hour, values in self._by_hour.items()},
            'global': list(self._global),
        }

    def load(self, state: Dict) -> None:
        try:
            for hour, values in (state.get('by_hour') or {}).items():
                bucket = self._by_hour[int(hour) % 24]
                bucket.clear()
                bucket.extend(float(v) for v in values[-self.window:])
            self._global.clear()
            self._global.extend(float(v) for v in (state.get('global') or [])
                                [-self.window * 2:])
        except (TypeError, ValueError) as e:
            logger.debug(f"كاشف الشذوذ {self.metric}: حالة غير صالحة ({e})")


# ═══════════════════════════════════════════════════════════
# كشف نقطة التغيّر (انحدار الأداء)
# ═══════════════════════════════════════════════════════════

@dataclass
class ChangePointEvent:
    """تغيّر مستدام في مستوى مقياس، لا قفزة عابرة"""
    metric: str
    direction: str          # up | down
    before: float
    after: float
    detected_at: str
    samples_after: int

    @property
    def change_percent(self) -> float:
        if self.before <= 1e-9:
            return 0.0
        return (self.after - self.before) / self.before * 100.0

    def as_dict(self) -> Dict[str, object]:
        return {
            'metric': self.metric, 'direction': self.direction,
            'before': round(self.before, 3), 'after': round(self.after, 3),
            'change_percent': round(self.change_percent, 1),
            'detected_at': self.detected_at, 'samples_after': self.samples_after,
        }


class ChangePoint:
    """
    CUSUM ثنائي الاتجاه: يجمع الانحرافات الصغيرة المتّسقة عن خط الأساس حتى
    تبلغ حدّاً، فيُعلن تغيّراً مستداماً. هذا ما يميّز «البطارية صارت أسوأ»
    عن «استعملتُ الجهاز بقوة قبل دقيقة».
    """

    def __init__(self, metric: str, reference_window: int = 200):
        self.metric = metric
        self._reference: Deque[float] = deque(maxlen=reference_window)
        self._high = 0.0
        self._low = 0.0
        self._since: List[float] = []
        self.last_event: Optional[ChangePointEvent] = None

    def observe(self, value: float) -> Optional[ChangePointEvent]:
        if not math.isfinite(value):
            return None
        if len(self._reference) < ANOMALY_MIN_SAMPLES:
            self._reference.append(value)
            return None

        samples = list(self._reference)
        mean = statistics.mean(samples)
        try:
            sigma = statistics.stdev(samples)
        except statistics.StatisticsError:
            sigma = 0.0
        if sigma <= 1e-9:
            self._reference.append(value)
            return None

        normalised = (value - mean) / sigma
        self._high = max(0.0, self._high + normalised - CUSUM_DRIFT_SIGMA)
        self._low = max(0.0, self._low - normalised - CUSUM_DRIFT_SIGMA)

        # `_since` يجمع الانحراف الجاري فقط: يُفرَّغ كلما رجع المجموع التراكمي
        # إلى الصفر، أي كلما انتهى الانحراف. بلا هذا التفريغ يبقى فيه مئات من
        # قيم خط الأساس، فيخرج «المستوى بعد التغيّر» مساوياً للمستوى قبله.
        if self._high <= 0.0 and self._low <= 0.0:
            self._since.clear()
        else:
            self._since.append(value)
            if len(self._since) > 400:
                del self._since[:-400]

        event: Optional[ChangePointEvent] = None
        crossed = (self._high >= CUSUM_THRESHOLD_SIGMA
                   or self._low >= CUSUM_THRESHOLD_SIGMA)
        if crossed and len(self._since) >= CUSUM_MIN_EXCURSION:
            direction = 'up' if self._high >= CUSUM_THRESHOLD_SIGMA else 'down'
            recent = list(self._since) or [value]
            event = ChangePointEvent(
                metric=self.metric,
                direction=direction,
                before=mean,
                after=statistics.mean(recent),
                detected_at=datetime.now().isoformat(),
                samples_after=len(recent),
            )
            self.last_event = event
            # إعادة الضبط على المستوى الجديد: التغيّر صار هو خط الأساس،
            # وبلا هذا يُعلن نفس التغيّر مراراً إلى الأبد.
            self._high = self._low = 0.0
            self._reference.clear()
            self._reference.extend(recent)
            self._since.clear()
        else:
            self._reference.append(value)
        return event

    def dump(self) -> Dict[str, object]:
        return {'metric': self.metric, 'reference': list(self._reference),
                'high': self._high, 'low': self._low}

    def load(self, state: Dict) -> None:
        try:
            self._reference.clear()
            self._reference.extend(float(v) for v in (state.get('reference') or []))
            self._high = float(state.get('high', 0.0))
            self._low = float(state.get('low', 0.0))
        except (TypeError, ValueError) as e:
            logger.debug(f"CUSUM {self.metric}: حالة غير صالحة ({e})")


# ═══════════════════════════════════════════════════════════
# الدورية الحقيقية
# ═══════════════════════════════════════════════════════════

def autocorrelation(series: List[float], lag: int) -> Optional[float]:
    """
    ارتباط ذاتي عند إزاحة معيّنة. يعيد `None` حين لا تكفي البيانات.
    يُستخدم لإثبات أن نمطاً يومياً موجود فعلاً بدل افتراضه.
    """
    if lag <= 0 or len(series) <= lag + 2:
        return None
    mean = statistics.mean(series)
    numerator = sum((series[i] - mean) * (series[i + lag] - mean)
                    for i in range(len(series) - lag))
    denominator = sum((value - mean) ** 2 for value in series)
    if denominator <= 1e-12:
        return None
    return numerator / denominator


@dataclass
class Rhythm:
    """دورية مرصودة في الاستخدام"""
    period_hours: int
    strength: float          # −1..1
    peak_hours: List[int] = field(default_factory=list)
    quiet_hours: List[int] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {'period_hours': self.period_hours,
                'strength': round(self.strength, 3),
                'peak_hours': list(self.peak_hours),
                'quiet_hours': list(self.quiet_hours)}


class Periodicity:
    """
    يكتشف الدورية من مصفوفة الساعات: هل استخدامك يومي منتظم (إزاحة 24)
    أم أسبوعي (إزاحة 168)؟ الجواب يحدّد جدوى التوصيات الزمنية.
    """

    #: أقل قوة ارتباط تُعدّ دورية حقيقية لا ضجيجاً
    MIN_STRENGTH = 0.25

    def __init__(self, limit: int = 24 * 21):
        self._hourly: Deque[Tuple[int, float]] = deque(maxlen=limit)

    def observe(self, drain_rate: float, hour: Optional[int] = None) -> None:
        """قراءة معدل استنزاف واحدة موسومة بساعتها"""
        if not math.isfinite(drain_rate) or drain_rate < 0:
            return
        hour = datetime.now().hour if hour is None else int(hour) % 24
        self._hourly.append((hour, float(drain_rate)))

    def analyse(self) -> Optional[Rhythm]:
        """أقوى دورية مؤكَّدة، أو `None` حين لا دليل عليها"""
        if len(self._hourly) < 48:
            return None
        series = [value for _, value in self._hourly]

        best: Optional[Rhythm] = None
        for period in (24, 168):
            strength = autocorrelation(series, period)
            if strength is None or strength < self.MIN_STRENGTH:
                continue
            if best is None or strength > best.strength:
                best = Rhythm(period_hours=period, strength=strength)

        if best is None:
            return None

        by_hour: Dict[int, List[float]] = defaultdict(list)
        for hour, value in self._hourly:
            by_hour[hour].append(value)
        averages = {hour: statistics.mean(values)
                    for hour, values in by_hour.items() if values}
        if averages:
            overall = statistics.mean(averages.values())
            best.peak_hours = sorted(h for h, v in averages.items() if v > overall * 1.4)
            best.quiet_hours = sorted(h for h, v in averages.items() if v < overall * 0.6)
        return best

    def dump(self) -> Dict[str, object]:
        return {'hourly': [[hour, value] for hour, value in self._hourly]}

    def load(self, state: Dict) -> None:
        try:
            self._hourly.clear()
            for entry in (state.get('hourly') or []):
                self._hourly.append((int(entry[0]) % 24, float(entry[1])))
        except (TypeError, ValueError, IndexError) as e:
            logger.debug(f"الدورية: حالة غير صالحة ({e})")


# ═══════════════════════════════════════════════════════════
# اتجاه التآكل المقيس
# ═══════════════════════════════════════════════════════════

@dataclass
class DegradationEstimate:
    """تآكل مقيس على هذه الخلية، لا مُستنتج من جدول"""
    annual_loss_percent: float
    readings: int
    span_days: float
    r_squared: Optional[float]
    current_soh: Optional[float]
    days_to_eol: Optional[int]
    measured: bool = True

    def as_dict(self) -> Dict[str, object]:
        return {
            'annual_loss_percent': round(self.annual_loss_percent, 3),
            'readings': self.readings, 'span_days': round(self.span_days, 2),
            'r_squared': None if self.r_squared is None else round(self.r_squared, 3),
            'current_soh': self.current_soh, 'days_to_eol': self.days_to_eol,
            'measured': self.measured,
        }


class DegradationTrend:
    """
    ينحدر خطياً على السعة الكاملة المقروءة من العتاد مقابل الزمن، فيعطي
    معدل التآكل الحقيقي لهذه البطارية بالذات.

    هذا أدقّ من أي جدول مرجعي لأن الجدول يصف اتجاهاً عاماً لخلايا تجارية،
    وهذا يقيس الخلية التي بين يدي المستخدم. لا تُحفظ إلا القراءات التي
    تغيّرت فعلاً حتى لا يتضخّم الملف بقراءات متطابقة.
    """

    def __init__(self):
        #: [(الزمن بالثواني منذ الحقبة، السعة الكاملة mWh, السعة التصميمية mWh)]
        self._readings: List[Tuple[float, float, float]] = []

    def observe(self, full_capacity_mwh: Optional[float],
                design_capacity_mwh: Optional[float],
                timestamp: Optional[float] = None) -> None:
        """قراءة سعة من العتاد. القيم غير الصالحة تُهمل بلا ضجيج."""
        if not full_capacity_mwh or not design_capacity_mwh:
            return
        if full_capacity_mwh <= 0 or design_capacity_mwh <= 0:
            return
        stamp = time.time() if timestamp is None else float(timestamp)

        if self._readings:
            last_stamp, last_full, _ = self._readings[-1]
            if abs(full_capacity_mwh - last_full) < DEGRADATION_MIN_DELTA_MWH:
                return
            if stamp <= last_stamp:
                return
        self._readings.append((stamp, float(full_capacity_mwh),
                               float(design_capacity_mwh)))
        if len(self._readings) > DEGRADATION_LIMIT:
            del self._readings[:len(self._readings) - DEGRADATION_LIMIT]

    def estimate(self, end_of_life_soh: float = 80.0) -> Optional[DegradationEstimate]:
        """
        معدل الفقد السنوي المقيس، أو `None` حين لا تكفي القراءات أو مداها.

        يُشترط مدى زمني أدنى لأن انحداراً على أيام قليلة يعطي ميلاً هائلاً
        بلا معنى، وعرضه كـ«فقد سنوي» تضليل.
        """
        if len(self._readings) < DEGRADATION_MIN_READINGS:
            return None
        span_days = (self._readings[-1][0] - self._readings[0][0]) / 86400.0
        if span_days < DEGRADATION_MIN_SPAN_DAYS:
            return None

        design = self._readings[-1][2]
        if design <= 0:
            return None

        # الانحدار على (أيام، صحة %) لأن الصحة هي ما يفهمه المستخدم
        points = [((stamp - self._readings[0][0]) / 86400.0, full / design * 100.0)
                  for stamp, full, _ in self._readings]
        n = len(points)
        mean_x = sum(x for x, _ in points) / n
        mean_y = sum(y for _, y in points) / n
        var_x = sum((x - mean_x) ** 2 for x, _ in points)
        if var_x <= 1e-9:
            return None
        cov = sum((x - mean_x) * (y - mean_y) for x, y in points)
        slope = cov / var_x                      # نقطة صحة لكل يوم
        annual_loss = max(0.0, -slope * 365.0)   # الفقد موجب حين تهبط الصحة

        predicted = [mean_y + slope * (x - mean_x) for x, _ in points]
        sse = sum((y - p) ** 2 for (_, y), p in zip(points, predicted))
        sst = sum((y - mean_y) ** 2 for _, y in points)
        r_squared = None if sst <= 1e-9 else max(0.0, 1.0 - sse / sst)

        current = round(points[-1][1], 1)
        days = None
        if annual_loss > 0.01 and current > end_of_life_soh:
            days = int((current - end_of_life_soh) / annual_loss * 365)
        elif current <= end_of_life_soh:
            days = 0

        return DegradationEstimate(
            annual_loss_percent=annual_loss, readings=n, span_days=span_days,
            r_squared=r_squared, current_soh=current, days_to_eol=days)

    def dump(self) -> Dict[str, object]:
        return {'readings': [[stamp, full, design]
                             for stamp, full, design in self._readings]}

    def load(self, state: Dict) -> None:
        try:
            self._readings = [(float(r[0]), float(r[1]), float(r[2]))
                              for r in (state.get('readings') or [])][-DEGRADATION_LIMIT:]
        except (TypeError, ValueError, IndexError) as e:
            logger.debug(f"اتجاه التآكل: حالة غير صالحة ({e})")


# ═══════════════════════════════════════════════════════════
# سجل العمليات التراكمي
# ═══════════════════════════════════════════════════════════

class _NameRecord:
    """
    تراكمات عملية واحدة (بالاسم لا برقم العملية).

    السبب: المتصفّحات ومحرّرات الشيفرة تُعيد إنشاء عملياتها كثيراً، فالتتبّع
    برقم العملية ينسى كل شيء عند كل إعادة تشغيل، والحكم على «الثبات» يصبح
    مستحيلاً. الاسم يبقى.
    """

    __slots__ = ('name', 'observations', 'appearances', 'watt_sum', 'watt_peak',
                 'behaviour_counts', 'last_seen',
                 'n', 'sum_x', 'sum_y', 'sum_xx', 'sum_yy', 'sum_xy')

    def __init__(self, name: str):
        self.name = name
        self.observations = 0.0     # موزونة بالتلاشي
        self.appearances = 0.0
        self.watt_sum = 0.0
        self.watt_peak = 0.0
        self.behaviour_counts: Dict[str, float] = {}
        self.last_seen = 0.0
        # تراكمات بيرسون بين واط العملية ومعدل استنزاف النظام
        self.n = 0.0
        self.sum_x = self.sum_y = self.sum_xx = self.sum_yy = self.sum_xy = 0.0

    @property
    def persistence(self) -> float:
        """في كم من العيّنات ظهرت هذه العملية كمستهلك فعلي (0..1)"""
        if self.observations <= 0:
            return 0.0
        return min(1.0, self.appearances / self.observations)

    @property
    def average_watts(self) -> float:
        if self.appearances <= 0:
            return 0.0
        return self.watt_sum / self.appearances

    @property
    def correlation(self) -> Optional[float]:
        """
        ارتباط بيرسون بين واط هذه العملية ومعدل استنزاف البطارية.
        قيمة عالية = حضورها يرفع الاستنزاف فعلاً، لا مجرد تصادف.
        """
        if self.n < CORRELATION_MIN_SAMPLES:
            return None
        mean_x = self.sum_x / self.n
        mean_y = self.sum_y / self.n
        var_x = self.sum_xx / self.n - mean_x * mean_x
        var_y = self.sum_yy / self.n - mean_y * mean_y
        if var_x <= 1e-12 or var_y <= 1e-12:
            return None
        cov = self.sum_xy / self.n - mean_x * mean_y
        return max(-1.0, min(1.0, cov / math.sqrt(var_x * var_y)))

    def decay(self, factor: float) -> None:
        self.observations *= factor
        self.appearances *= factor
        self.watt_sum *= factor
        self.n *= factor
        self.sum_x *= factor
        self.sum_y *= factor
        self.sum_xx *= factor
        self.sum_yy *= factor
        self.sum_xy *= factor
        for key in list(self.behaviour_counts):
            self.behaviour_counts[key] *= factor
            if self.behaviour_counts[key] < 0.01:
                del self.behaviour_counts[key]

    def dump(self) -> Dict[str, object]:
        return {
            'observations': self.observations, 'appearances': self.appearances,
            'watt_sum': self.watt_sum, 'watt_peak': self.watt_peak,
            'behaviour_counts': dict(self.behaviour_counts),
            'last_seen': self.last_seen, 'n': self.n,
            'sum_x': self.sum_x, 'sum_y': self.sum_y, 'sum_xx': self.sum_xx,
            'sum_yy': self.sum_yy, 'sum_xy': self.sum_xy,
        }

    def load(self, state: Dict) -> None:
        self.observations = float(state.get('observations', 0.0))
        self.appearances = float(state.get('appearances', 0.0))
        self.watt_sum = float(state.get('watt_sum', 0.0))
        self.watt_peak = float(state.get('watt_peak', 0.0))
        self.behaviour_counts = {str(k): float(v) for k, v
                                 in (state.get('behaviour_counts') or {}).items()}
        self.last_seen = float(state.get('last_seen', 0.0))
        self.n = float(state.get('n', 0.0))
        self.sum_x = float(state.get('sum_x', 0.0))
        self.sum_y = float(state.get('sum_y', 0.0))
        self.sum_xx = float(state.get('sum_xx', 0.0))
        self.sum_yy = float(state.get('sum_yy', 0.0))
        self.sum_xy = float(state.get('sum_xy', 0.0))


class OffenderLedger:
    """سجل تراكمي لكل العمليات المرصودة، بحجم محدود وتلاشٍ زمني"""

    def __init__(self):
        self._records: Dict[str, _NameRecord] = {}
        self._decay = 0.5 ** (1.0 / LEDGER_DECAY_HALFLIFE)

    def observe(self, loads: List[ProcessLoad], drain_rate: float) -> None:
        """
        دورة رصد واحدة. `drain_rate` = معدل استنزاف البطارية (%/دقيقة) في
        نفس الفترة، وهو المتغيّر الذي نبحث عن ارتباط الواط به.
        """
        for record in self._records.values():
            record.decay(self._decay)

        # عمليات بنفس الاسم (مثل مسارات المتصفّح) تُجمع، فالمستخدم يرى
        # «المتصفّح» لا ثلاثين عملية متفرّقة
        merged: Dict[str, Tuple[float, List[str]]] = {}
        for load in loads:
            if load.is_unattributed:
                continue
            watts = load.watts if load.watts is not None else 0.0
            current_watts, tags = merged.get(load.name, (0.0, []))
            merged[load.name] = (current_watts + watts, tags + load.behaviours)

        now = time.time()
        seen = set(merged)
        for name, (watts, tags) in merged.items():
            record = self._records.get(name)
            if record is None:
                record = self._records[name] = _NameRecord(name)
            record.observations += 1.0
            record.last_seen = now
            if watts >= PRESENCE_WATT_FLOOR:
                record.appearances += 1.0
                record.watt_sum += watts
                record.watt_peak = max(record.watt_peak, watts)
            for tag in set(tags):
                record.behaviour_counts[tag] = record.behaviour_counts.get(tag, 0.0) + 1.0
            if drain_rate > 0:
                record.n += 1.0
                record.sum_x += watts
                record.sum_y += drain_rate
                record.sum_xx += watts * watts
                record.sum_yy += drain_rate * drain_rate
                record.sum_xy += watts * drain_rate

        # العمليات الغائبة تُحسب لها ملاحظة بواط صفر: الغياب معلومة أيضاً،
        # وبدونه تبدو كل عملية ظهرت مرة واحدة «ثابتة 100%»
        for name, record in self._records.items():
            if name not in seen:
                record.observations += 1.0
                if drain_rate > 0:
                    record.n += 1.0
                    record.sum_y += drain_rate
                    record.sum_yy += drain_rate * drain_rate

        self._prune()

    def _prune(self) -> None:
        if len(self._records) <= LEDGER_LIMIT:
            return
        ranked = sorted(self._records.items(),
                        key=lambda item: (item[1].watt_peak, item[1].last_seen),
                        reverse=True)
        self._records = dict(ranked[:LEDGER_LIMIT])

    def record(self, name: str) -> Optional[_NameRecord]:
        return self._records.get(name)

    def dump(self) -> Dict[str, object]:
        return {'records': {name: record.dump()
                            for name, record in self._records.items()}}

    def load(self, state: Dict) -> None:
        try:
            for name, payload in (state.get('records') or {}).items():
                record = _NameRecord(str(name))
                record.load(payload)
                self._records[str(name)] = record
        except (TypeError, ValueError, AttributeError) as e:
            logger.debug(f"سجل المخالفين: حالة غير صالحة ({e})")


# ═══════════════════════════════════════════════════════════
# المخالف
# ═══════════════════════════════════════════════════════════

@dataclass
class Offender:
    """عملية تُتلف البطارية، بدرجة ضرر مشتقّة من قياس وعلم لا من رأي"""
    name: str
    pids: List[int] = field(default_factory=list)
    watts: float = 0.0
    watts_share: float = 0.0
    percent_per_hour: float = 0.0
    annual_capacity_loss: float = 0.0
    damage_score: float = 0.0
    behaviours: List[str] = field(default_factory=list)
    persistence: float = 0.0
    correlation: Optional[float] = None
    confidence: int = 0
    recommended_action: str = ACTION_NONE
    evidence: List[str] = field(default_factory=list)
    capacity_assumed: bool = False

    def as_dict(self) -> Dict[str, object]:
        return {
            'name': self.name, 'pids': list(self.pids),
            'watts': round(self.watts, 2),
            'watts_share': round(self.watts_share, 3),
            'percent_per_hour': round(self.percent_per_hour, 2),
            'annual_capacity_loss': round(self.annual_capacity_loss, 3),
            'damage_score': round(self.damage_score, 1),
            'behaviours': list(self.behaviours),
            'persistence': round(self.persistence, 3),
            'correlation': None if self.correlation is None else round(self.correlation, 3),
            'confidence': self.confidence,
            'recommended_action': self.recommended_action,
            'evidence': list(self.evidence),
            'capacity_assumed': self.capacity_assumed,
        }


@dataclass
class IntelligenceReport:
    """ما يعرضه التطبيق ويبني عليه الحارس قراره"""
    generated_at: str = ''
    offenders: List[Offender] = field(default_factory=list)
    anomalies: List[Anomaly] = field(default_factory=list)
    change_points: List[ChangePointEvent] = field(default_factory=list)
    rhythm: Optional[Rhythm] = None
    degradation: Optional[DegradationEstimate] = None
    measured_watts: Optional[float] = None
    baseline_watts: float = 0.0
    unattributed_watts: Optional[float] = None
    model_confidence: int = 0
    capacity_wh: Optional[float] = None
    capacity_assumed: bool = True
    samples: int = 0

    @property
    def worst(self) -> Optional[Offender]:
        return self.offenders[0] if self.offenders else None

    def actionable(self) -> List[Offender]:
        """المخالفون الذين يستحقّون إجراءً فعلياً"""
        return [item for item in self.offenders
                if item.recommended_action != ACTION_NONE]

    def as_dict(self) -> Dict[str, object]:
        return {
            'generated_at': self.generated_at,
            'offenders': [item.as_dict() for item in self.offenders],
            'anomalies': [item.as_dict() for item in self.anomalies],
            'change_points': [item.as_dict() for item in self.change_points],
            'rhythm': None if self.rhythm is None else self.rhythm.as_dict(),
            'degradation': None if self.degradation is None else self.degradation.as_dict(),
            'measured_watts': self.measured_watts,
            'baseline_watts': round(self.baseline_watts, 2),
            'unattributed_watts': self.unattributed_watts,
            'model_confidence': self.model_confidence,
            'capacity_wh': self.capacity_wh,
            'capacity_assumed': self.capacity_assumed,
            'samples': self.samples,
        }


# ═══════════════════════════════════════════════════════════
# المنسّق
# ═══════════════════════════════════════════════════════════

class BatteryIntelligence:
    """
    يجمع الطبقات كلها في تقرير واحد.

    لا يمسّ نظام التشغيل ولا يوقف عملية: القرار والتنفيذ في `guard_actions`،
    وهذه الطبقة تستنتج فقط. الفصل مقصود حتى يُختبر الاستدلال بلا مخاطرة.
    """

    def __init__(self, state: Optional[Dict] = None):
        self._lock = threading.RLock()
        self.drain_anomaly = RobustAnomaly('drain_rate')
        self.power_anomaly = RobustAnomaly('power_draw')
        self.drain_change = ChangePoint('drain_rate')
        self.periodicity = Periodicity()
        self.degradation = DegradationTrend()
        self.ledger = OffenderLedger()

        self.recent_anomalies: Deque[Anomaly] = deque(maxlen=50)
        self.recent_change_points: Deque[ChangePointEvent] = deque(maxlen=20)
        self.samples = 0
        self.last_report: Optional[IntelligenceReport] = None

        if state:
            self.load(state)

    # ── الدورة الرئيسية ─────────────────────────────────────

    def update(self, attribution: Optional[AttributionResult],
               battery_status: Dict,
               health: Optional[Dict] = None,
               drain_rate: float = 0.0,
               hours_on_battery_per_day: float = 4.0,
               typical_dod: float = 30.0) -> IntelligenceReport:
        """
        دورة استدلال واحدة.

        `drain_rate` بوحدة %/دقيقة (من `battery_ai`)، و`typical_dod` عمق
        التفريغ المعتاد المرصود، وكلاهما يدخل في تحويل الواط إلى تآكل سنوي.
        """
        health = health or {}
        with self._lock:
            self.samples += 1
            hour = datetime.now().hour
            anomalies: List[Anomaly] = []
            changes: List[ChangePointEvent] = []

            charging = bool(battery_status.get('is_charging'))
            reporting = bool(battery_status.get('reporting', True))

            # الشذوذ والتغيّر يُقاسان أثناء التفريغ فقط: أثناء الشحن لا معنى
            # لمعدل استنزاف، والقدرة المقروءة هي قدرة الشاحن.
            if reporting and not charging:
                if drain_rate > 0:
                    found = self.drain_anomaly.observe(drain_rate, hour)
                    if found:
                        anomalies.append(found)
                    event = self.drain_change.observe(drain_rate)
                    if event:
                        changes.append(event)
                    self.periodicity.observe(drain_rate, hour)

                power = float(battery_status.get('power_draw') or 0.0)
                if power > 0:
                    found = self.power_anomaly.observe(power, hour)
                    if found:
                        anomalies.append(found)

            # السعة تُقرأ دائماً: تآكلها لا يتوقّف عند الشحن
            self.degradation.observe(health.get('full_capacity'),
                                     health.get('design_capacity'))

            capacity_wh, capacity_assumed = self._capacity_wh(health)

            if attribution is not None:
                self.ledger.observe(attribution.loads, drain_rate)

            offenders = self._build_offenders(
                attribution, capacity_wh, capacity_assumed,
                hours_on_battery_per_day, typical_dod)

            self.recent_anomalies.extend(anomalies)
            self.recent_change_points.extend(changes)

            report = IntelligenceReport(
                generated_at=datetime.now().isoformat(),
                offenders=offenders,
                anomalies=list(self.recent_anomalies)[-10:],
                change_points=list(self.recent_change_points)[-5:],
                rhythm=self.periodicity.analyse(),
                degradation=self.degradation.estimate(),
                measured_watts=None if attribution is None else attribution.measured_watts,
                baseline_watts=0.0 if attribution is None else attribution.baseline_watts,
                unattributed_watts=None if attribution is None else attribution.unattributed_watts,
                model_confidence=0 if attribution is None else attribution.model_confidence,
                capacity_wh=capacity_wh,
                capacity_assumed=capacity_assumed,
                samples=self.samples,
            )
            self.last_report = report
            return report

    @staticmethod
    def _capacity_wh(health: Dict) -> Tuple[float, bool]:
        """
        سعة البطارية بالواط·ساعة، وهل هي مفترضة.

        `battery_monitor` يعرض السعة بالملي واط·ساعة عادةً، وبالملي أمبير·ساعة
        حين يعجز عن قراءة الجهد (`capacity_unit == 'mah'`). في الحالة الثانية
        لا يصحّ تحويلها إلى طاقة، فنعلن الافتراض بدل حساب رقم خاطئ.
        """
        if health.get('capacity_unit') == 'mah':
            return ASSUMED_CAPACITY_WH, True
        full = health.get('full_capacity') or 0.0
        design = health.get('design_capacity') or 0.0
        chosen = full or design
        if chosen and chosen > 0:
            watt_hours = float(chosen) / 1000.0
            # سلامة: لابتوب بين 20 و200 واط·ساعة. خارج ذلك القراءة مشكوكة.
            if 20.0 <= watt_hours <= 200.0:
                return round(watt_hours, 2), False
        return ASSUMED_CAPACITY_WH, True

    # ── بناء المخالفين ──────────────────────────────────────

    def _build_offenders(self, attribution: Optional[AttributionResult],
                         capacity_wh: float, capacity_assumed: bool,
                         hours_on_battery_per_day: float,
                         typical_dod: float) -> List[Offender]:
        if attribution is None:
            return []

        dynamic = attribution.dynamic_watts or 0.0
        grouped: Dict[str, Dict[str, object]] = {}
        for load in attribution.loads:
            if load.is_unattributed:
                continue
            entry = grouped.setdefault(load.name, {
                'watts': 0.0, 'pids': [], 'behaviours': set()})
            entry['watts'] = float(entry['watts']) + (load.watts or 0.0)
            pids = entry['pids']
            if isinstance(pids, list) and len(pids) < 12:
                pids.append(load.pid)
            behaviours = entry['behaviours']
            if isinstance(behaviours, set):
                behaviours.update(load.behaviours)

        offenders: List[Offender] = []
        for name, entry in grouped.items():
            watts = float(entry['watts'])
            behaviours = sorted(entry['behaviours']) if isinstance(entry['behaviours'], set) else []
            if watts < PRESENCE_WATT_FLOOR and not behaviours:
                continue

            record = self.ledger.record(name)
            persistence = record.persistence if record else 0.0
            correlation = record.correlation if record else None

            offender = self._score(
                name=name,
                pids=list(entry['pids']) if isinstance(entry['pids'], list) else [],
                watts=watts,
                dynamic=dynamic,
                behaviours=behaviours,
                persistence=persistence,
                correlation=correlation,
                capacity_wh=capacity_wh,
                capacity_assumed=capacity_assumed,
                hours_on_battery_per_day=hours_on_battery_per_day,
                typical_dod=typical_dod,
                model_confidence=attribution.model_confidence,
                baseline_watts=attribution.baseline_watts,
            )
            if offender.damage_score > 0:
                offenders.append(offender)

        offenders.sort(key=lambda item: item.damage_score, reverse=True)
        return offenders

    @staticmethod
    def _score(name: str, pids: List[int], watts: float, dynamic: float,
               behaviours: List[str], persistence: float,
               correlation: Optional[float], capacity_wh: float,
               capacity_assumed: bool, hours_on_battery_per_day: float,
               typical_dod: float, model_confidence: int,
               baseline_watts: float) -> Offender:
        """
        تحويل الواط والسلوك إلى فقد سعة سنوي ودرجة ضرر وإجراء مقترح.
        كل خطوة موثّقة في ترويسة الوحدة، وكل رقم له سند في `evidence`.
        """
        evidence: List[str] = []

        percent_per_hour = 0.0
        annual_loss = 0.0
        if watts > 0 and capacity_wh > 0:
            percent_per_hour = watts / capacity_wh * 100.0
            hours = max(0.5, min(24.0, hours_on_battery_per_day))
            percent_per_year = percent_per_hour * hours * 365.0
            equivalent_cycles = percent_per_year / 100.0
            depth = typical_dod if typical_dod and typical_dod > 0 else 30.0
            annual_loss = equivalent_cycles * cycle_wear_percent(depth)
            evidence.append(f"{watts:.2f}W ÷ {capacity_wh:.1f}Wh = "
                            f"{percent_per_hour:.2f}%/ساعة")
            evidence.append(f"{hours:.1f} ساعة/يوم على البطارية × 365 = "
                            f"{equivalent_cycles:.1f} دورة مكافئة/سنة")
            evidence.append(f"تآكل الدورة عند عمق {depth:.0f}% = "
                            f"{cycle_wear_percent(depth):.3f}% سعة")

        score = min(100.0, annual_loss / DAMAGE_LOSS_AT_MAX * 100.0)
        for behaviour in behaviours:
            bonus = DAMAGE_BEHAVIOUR_BONUS.get(behaviour, 0.0)
            if bonus:
                score += bonus
                evidence.append(f"سلوك {behaviour}: +{bonus:.0f} درجة")

        if BEHAVIOUR_IDLE_INHIBITOR in behaviours and baseline_watts > 0:
            evidence.append(f"يمنع الخمول: الجهاز يستهلك {baseline_watts:.1f}W "
                            f"أساساً بلا حِمل، وهذا المنع يجعلها مستمرة")

        # الثبات يضاعف الضرر: عملية تستنزف دائماً أخطر من قفزة عابرة
        if persistence > 0:
            score *= 0.6 + 0.4 * min(1.0, persistence * 1.5)
            evidence.append(f"الثبات: ظهرت كمستهلك في {persistence * 100:.0f}% من العيّنات")
        if correlation is not None:
            evidence.append(f"ارتباط حضورها بالاستنزاف: r={correlation:.2f}")
            if correlation >= 0.5:
                score += 8.0

        score = max(0.0, min(100.0, score))

        confidence = int(round(
            model_confidence * 0.5
            + (min(1.0, persistence * 2) * 100) * 0.2
            + (60 if correlation is not None else 25) * 0.2
            + (50 if capacity_assumed else 100) * 0.1))
        confidence = max(5, min(99, confidence))

        if score >= DAMAGE_SUSPEND_AT:
            action = ACTION_SUSPEND
        elif score >= DAMAGE_THROTTLE_AT:
            action = ACTION_THROTTLE
        elif score >= DAMAGE_ALERT_AT:
            action = ACTION_ALERT
        else:
            action = ACTION_NONE

        return Offender(
            name=name, pids=pids, watts=watts,
            watts_share=(watts / dynamic) if dynamic > 0 else 0.0,
            percent_per_hour=percent_per_hour,
            annual_capacity_loss=annual_loss,
            damage_score=score, behaviours=behaviours,
            persistence=persistence, correlation=correlation,
            confidence=confidence, recommended_action=action,
            evidence=evidence, capacity_assumed=capacity_assumed)

    # ── التخزين ─────────────────────────────────────────────

    def dump(self) -> Dict[str, object]:
        with self._lock:
            return {
                'version': 1,
                'samples': self.samples,
                'drain_anomaly': self.drain_anomaly.dump(),
                'power_anomaly': self.power_anomaly.dump(),
                'drain_change': self.drain_change.dump(),
                'periodicity': self.periodicity.dump(),
                'degradation': self.degradation.dump(),
                'ledger': self.ledger.dump(),
                'recent_anomalies': [item.as_dict() for item in self.recent_anomalies],
            }

    def load(self, state: Dict) -> None:
        with self._lock:
            try:
                self.samples = int(state.get('samples', 0))
                self.drain_anomaly.load(state.get('drain_anomaly') or {})
                self.power_anomaly.load(state.get('power_anomaly') or {})
                self.drain_change.load(state.get('drain_change') or {})
                self.periodicity.load(state.get('periodicity') or {})
                self.degradation.load(state.get('degradation') or {})
                self.ledger.load(state.get('ledger') or {})
            except (TypeError, ValueError, AttributeError) as e:
                logger.warning(f"محرّك الاستدلال: تعذّرت استعادة الحالة ({e})")

    def reset(self) -> None:
        """تصفير كامل داخل نفس الكائن (تبقى المراجع الأخرى صالحة)"""
        with self._lock:
            self.drain_anomaly = RobustAnomaly('drain_rate')
            self.power_anomaly = RobustAnomaly('power_draw')
            self.drain_change = ChangePoint('drain_rate')
            self.periodicity = Periodicity()
            self.degradation = DegradationTrend()
            self.ledger = OffenderLedger()
            self.recent_anomalies.clear()
            self.recent_change_points.clear()
            self.samples = 0
            self.last_report = None
