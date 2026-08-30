#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نسب استهلاك الطاقة إلى العمليات - BatteryGuardAI

يجيب على السؤال الذي لا تجيب عليه أي لوحة بطارية: **من** يستهلك بطاريتك الآن،
بالواط، لا بالنسبة المئوية من المعالج.

كيف يعمل بصدق
──────────────
1. تُقاس القدرة الكلية من العتاد (`power_now`، أو `voltage_now × current_now`).
   هذا الرقم مقيس لا مُخترع، ويأتي من `battery_monitor.get_battery_status()`.
2. تُقاس أحمال كل عملية من عدّادات النظام: زمن المعالج، بايتات القرص الفعلية،
   وتبديلات السياق (وكيل عن عدد الإيقاظات التي تمنع نوم المعالج العميق).
3. يتعلّم `PowerModel` **من قياسات هذا الجهاز نفسه** كم واط تكلّف كل وحدة حِمل،
   بانحدار خطي غير سالب على المجاميع الكلية:

       واط ≈ أساس + (معامل المعالج × حِمل المعالج) + (معامل القرص × حِمل القرص)
                  + (معامل الإيقاظ × معدل الإيقاظات)

   المعاملات تُقدَّر بالمعادلات الطبيعية مع تنظيم ridge، وتُقصّ عند الصفر لأن
   حِملاً موجباً لا يمكن أن يوفّر طاقة. قبل توفّر بيانات كافية تُستخدم قيم
   أولية (`PRIORS`) وتُعلَن الثقة منخفضة صراحةً.
4. تُوزَّع القدرة الديناميكية المقيسة على العمليات بنسبة تكلفتها، ثم تُعاير
   حتى يساوي مجموعها ما قِيس فعلاً. الفارق غير المنسوب يُعرض باسمه
   (`UNATTRIBUTED`) بدل توزيعه قسراً على العمليات.

قيود مُعلَنة
────────────
- التدريب يجري **أثناء التفريغ فقط**. أثناء الشحن يقيس `current_now` تيار
  الشحن لا الاستهلاك، فالتغذية به تفسد المعامل.
- لا يُنسب استهلاك الشاشة ولا الشبكة الراديوية إلى عملية، لأن العتاد لا
  يعرضهما لكل عملية. يبقى ذلك ضمن الأساس أو غير المنسوب.
- `io_counters` تحتاج نفس المستخدم أو صلاحيات أعلى؛ عند تعذّرها يُهمل بُعد
  القرص للعملية ويُعلَم ذلك في `partial_dimensions`.

المراجع المستخدمة للقيم الأولية فقط (ثم يستبدلها التعلّم):
- Linux kernel documentation, ABI/testing/sysfs-class-power: دلالات
  `power_now` و`current_now` و`voltage_now` ووحداتها (ميكرو).
  https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-class-power
- systemd, `systemd-inhibit(1)`: أوضاع `block` و`delay` ودلالة `idle`
  و`sleep`، وهي الأساس في تمييز مانع النوم الحقيقي من المؤجِّل الحميد.
  https://www.freedesktop.org/software/systemd/man/systemd-inhibit.html
"""

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger('BatteryGuard')

IS_LINUX = sys.platform.startswith('linux')
IS_WINDOWS = sys.platform == 'win32'

#: معرّف السطر الذي يحمل ما لم يُنسب إلى أي عملية (شاشة، راديو، عتاد طرفي)
UNATTRIBUTED = '__unattributed__'

#: أقل فاصل بين عيّنتين ليكون الفرق ذا معنى (ثانية)
MIN_SAMPLE_INTERVAL = 3.0

#: أقصى فاصل يُحسب كزمن متصل؛ ما بعده = نوم الجهاز فتُلغى العيّنة
MAX_SAMPLE_INTERVAL = 300.0

#: عدد العمليات المتتبَّعة بأثر رجعي (لحساب الاستمرار)
TRACK_LIMIT = 600

# ═══════════════════════════════════════════════════════════
# عتبات السلوك الضار (كل واحدة مُسمّاة ومُبرَّرة)
# ═══════════════════════════════════════════════════════════

# عتبات المعالج تُقاس بمقياس «نواة واحدة = 100%» لا بنسبة الجهاز كله، لأن
# عملية تشغل نواة كاملة تستنزف البطارية بنفس القدر على جهاز بأربع أنوية أو
# باثنتين وثلاثين، بينما نسبتها من الجهاز تتغيّر بينهما تغيّراً كبيراً.

#: نسبة نواة واحدة تُعدّ حِملاً ثقيلاً إن استمرت
CPU_SUSTAINED_CORE_PERCENT = 25.0

#: كم ثانية يجب أن يستمر الحِمل قبل تسميته «مستمراً» لا «قفزة»
CPU_SUSTAINED_SECONDS = 120.0

#: قفزة معالج لحظية تستحق الانتباه (60% من نواة)
CPU_SPIKE_CORE_PERCENT = 60.0

#: تبديلات سياق في الثانية تمنع دخول المعالج حالات النوم العميقة
WAKEUP_STORM_PER_SEC = 400.0

#: ميغابايت/ثانية من القرص الفعلي تُعدّ إرهاقاً للقرص
DISK_THRASH_MB_PER_SEC = 6.0

#: نسبة الذاكرة الفيزيائية التي تجعل العملية سبباً محتملاً للتبديل (swap)
MEMORY_PRESSURE_PERCENT = 18.0

BEHAVIOUR_CPU_SUSTAINED = 'cpu_sustained'
BEHAVIOUR_CPU_SPIKE = 'cpu_spike'
BEHAVIOUR_WAKEUP_STORM = 'wakeup_storm'
BEHAVIOUR_DISK_THRASH = 'disk_thrash'
BEHAVIOUR_MEMORY_PRESSURE = 'memory_pressure'
BEHAVIOUR_SLEEP_INHIBITOR = 'sleep_inhibitor'
BEHAVIOUR_IDLE_INHIBITOR = 'idle_inhibitor'

ALL_BEHAVIOURS = (
    BEHAVIOUR_CPU_SUSTAINED, BEHAVIOUR_CPU_SPIKE, BEHAVIOUR_WAKEUP_STORM,
    BEHAVIOUR_DISK_THRASH, BEHAVIOUR_MEMORY_PRESSURE,
    BEHAVIOUR_SLEEP_INHIBITOR, BEHAVIOUR_IDLE_INHIBITOR,
)


# ═══════════════════════════════════════════════════════════
# نموذج الطاقة المتعلَّم
# ═══════════════════════════════════════════════════════════

class PowerModel:
    """
    انحدار خطي غير سالب يتعلّم تكلفة كل وحدة حِمل بالواط على هذا الجهاز.

    يُخزَّن بشكل تراكمي (مجاميع المعادلات الطبيعية) لا بحفظ العيّنات، فحجمه
    ثابت مهما طال التشغيل. يُطبَّق تلاشٍ أسّي حتى يتبع النموذج تغيّر العتاد
    (تعتيم الشاشة، تغيّر مُنظّم ترددات المعالج) بدل أن يتجمّد على ماضٍ بعيد.
    """

    #: أسماء الأبعاد بالترتيب الثابت المستخدم في المصفوفات
    FEATURES: Tuple[str, ...] = ('cpu', 'io', 'wake')

    #: قيم أولية بمرتبة المقدار فقط، تُستبدل بالتعلّم بأسرع ما تسمح البيانات.
    #: cpu: واط لكل 1% من كامل المعالج. io: واط لكل ميغابايت/ثانية.
    #: wake: واط لكل إيقاظ/ثانية.
    PRIORS: Dict[str, float] = {'cpu': 0.22, 'io': 0.012, 'wake': 0.0012}

    #: أساس افتراضي (واط) قبل قياس أي فترة خمول حقيقية
    PRIOR_BASELINE = 4.0

    #: معامل التنظيم يمنع انفجار المعاملات عند ترابط الأبعاد
    RIDGE = 1e-4

    #: نصف عمر التلاشي بالعيّنات: بعده يصبح وزن العيّنة نصفاً
    DECAY_HALFLIFE = 400.0

    #: أقل عدد عيّنات قبل الوثوق بالمعاملات المتعلَّمة
    MIN_SAMPLES = 25

    def __init__(self, state: Optional[Dict] = None):
        n = len(self.FEATURES) + 1  # +1 للأساس (intercept)
        self._n = n
        self._xtx: List[List[float]] = [[0.0] * n for _ in range(n)]
        self._xty: List[float] = [0.0] * n
        self._yy = 0.0
        self._y_sum = 0.0
        self._weight = 0.0
        self.samples = 0
        self._coefficients: Optional[Dict[str, float]] = None
        self._baseline: Optional[float] = None
        self._r2: Optional[float] = None
        if state:
            self.load(state)

    # ── التغذية ─────────────────────────────────────────────

    def observe(self, features: Dict[str, float], watts: float) -> None:
        """
        إضافة عيّنة: أحمال كلية مقاسة مقابل قدرة كلية مقاسة.

        تُرفض العيّنات غير الفيزيائية (قدرة صفر أو سالبة، أو قدرة أعلى من أي
        سقف معقول للابتوب) لأن عيّنة واحدة فاسدة تفسد المعامل لمئات العيّنات.
        """
        if not (0.5 <= watts <= 250.0):
            return
        row = [1.0] + [max(0.0, float(features.get(name, 0.0)))
                       for name in self.FEATURES]

        decay = 0.5 ** (1.0 / self.DECAY_HALFLIFE)
        for i in range(self._n):
            self._xty[i] = self._xty[i] * decay + row[i] * watts
            for j in range(self._n):
                self._xtx[i][j] = self._xtx[i][j] * decay + row[i] * row[j]
        self._yy = self._yy * decay + watts * watts
        self._y_sum = self._y_sum * decay + watts
        self._weight = self._weight * decay + 1.0
        self.samples += 1
        self._coefficients = None  # إبطال الحل المخزَّن
        self._baseline = None
        self._r2 = None

    # ── الحل ────────────────────────────────────────────────

    def _solve(self) -> None:
        """
        حل المعادلات الطبيعية بحذف غاوس، ثم قصّ المعاملات السالبة وإعادة
        الحل على الأبعاد الباقية (تقريب عملي لانحدار غير سالب).
        """
        priors = dict(self.PRIORS)
        if self.samples < self.MIN_SAMPLES or self._weight <= 0:
            self._coefficients = priors
            self._baseline = self.PRIOR_BASELINE
            self._r2 = None
            return

        active = list(range(self._n))  # 0 = الأساس، دائماً نشط
        solution: Optional[List[float]] = None

        for _ in range(len(self.FEATURES) + 1):
            solution = self._solve_subset(active)
            if solution is None:
                break
            negative = [idx for pos, idx in enumerate(active)
                        if idx != 0 and solution[pos] < 0.0]
            if not negative:
                break
            for idx in negative:
                active.remove(idx)

        if solution is None:
            self._coefficients = priors
            self._baseline = self.PRIOR_BASELINE
            self._r2 = None
            return

        values = {idx: solution[pos] for pos, idx in enumerate(active)}
        baseline = max(0.0, values.get(0, self.PRIOR_BASELINE))
        coefficients = {}
        for offset, name in enumerate(self.FEATURES, start=1):
            coefficients[name] = max(0.0, values.get(offset, 0.0))

        self._baseline = baseline
        self._coefficients = coefficients
        self._r2 = self._compute_r2(coefficients, baseline)

    def _solve_subset(self, active: List[int]) -> Optional[List[float]]:
        """حل نظام مصغَّر على الأبعاد النشطة فقط"""
        size = len(active)
        matrix = [[self._xtx[i][j] for j in active] for i in active]
        vector = [self._xty[i] for i in active]
        for k in range(size):
            matrix[k][k] += self.RIDGE * max(1.0, self._weight)

        # حذف غاوس مع محورة جزئية
        for col in range(size):
            pivot = max(range(col, size), key=lambda r: abs(matrix[r][col]))
            if abs(matrix[pivot][col]) < 1e-12:
                return None
            if pivot != col:
                matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
                vector[col], vector[pivot] = vector[pivot], vector[col]
            inv = 1.0 / matrix[col][col]
            for row in range(col + 1, size):
                factor = matrix[row][col] * inv
                if factor == 0.0:
                    continue
                for c in range(col, size):
                    matrix[row][c] -= factor * matrix[col][c]
                vector[row] -= factor * vector[col]

        result = [0.0] * size
        for row in reversed(range(size)):
            total = vector[row] - sum(matrix[row][c] * result[c]
                                      for c in range(row + 1, size))
            result[row] = total / matrix[row][row]
        return result

    def _compute_r2(self, coefficients: Dict[str, float], baseline: float) -> Optional[float]:
        """
        نسبة التباين المفسَّر، محسوبة من المجاميع التراكمية بلا حفظ عيّنات:
            SSE = yᵀy − 2·βᵀ(Xᵀy) + βᵀ(XᵀX)β
        """
        if self._weight <= 1.0:
            return None
        beta = [baseline] + [coefficients.get(name, 0.0) for name in self.FEATURES]
        sse = self._yy
        sse -= 2.0 * sum(beta[i] * self._xty[i] for i in range(self._n))
        for i in range(self._n):
            for j in range(self._n):
                sse += beta[i] * self._xtx[i][j] * beta[j]
        mean = self._y_sum / self._weight
        sst = self._yy - self._weight * mean * mean
        if sst <= 1e-9:
            return None
        return max(0.0, min(1.0, 1.0 - sse / sst))

    # ── القراءة ─────────────────────────────────────────────

    @property
    def coefficients(self) -> Dict[str, float]:
        if self._coefficients is None:
            self._solve()
        return dict(self._coefficients or self.PRIORS)

    @property
    def baseline_watts(self) -> float:
        """القدرة التي يستهلكها الجهاز بلا حِمل قابل للنسب (شاشة، راديو، عتاد)"""
        if self._baseline is None:
            self._solve()
        return float(self._baseline if self._baseline is not None else self.PRIOR_BASELINE)

    @property
    def r_squared(self) -> Optional[float]:
        if self._coefficients is None:
            self._solve()
        return self._r2

    @property
    def calibrated(self) -> bool:
        """هل المعاملات متعلَّمة من هذا الجهاز أم ما تزال قيماً أولية"""
        return self.samples >= self.MIN_SAMPLES

    def confidence(self) -> int:
        """
        ثقة النموذج 0..100: حجم البيانات نصفها، وجودة المطابقة نصفها.
        قبل المعايرة تبقى منخفضة عن قصد حتى لا يُعرض تخمين كأنه قياس.
        """
        if not self.calibrated:
            return int(min(25, self.samples / self.MIN_SAMPLES * 25))
        data = min(1.0, self.samples / (self.MIN_SAMPLES * 8))
        fit = self.r_squared if self.r_squared is not None else 0.4
        return int(round(25 + data * 30 + fit * 45))

    def predict(self, features: Dict[str, float]) -> float:
        """القدرة المتوقّعة (واط) لأحمال معيّنة، بما فيها الأساس"""
        coefficients = self.coefficients
        total = self.baseline_watts
        for name in self.FEATURES:
            total += coefficients.get(name, 0.0) * max(0.0, features.get(name, 0.0))
        return total

    def cost_watts(self, features: Dict[str, float]) -> float:
        """نصيب حِمل معيّن من القدرة، بلا الأساس (الأساس ليس لعملية)"""
        coefficients = self.coefficients
        return sum(coefficients.get(name, 0.0) * max(0.0, features.get(name, 0.0))
                   for name in self.FEATURES)

    # ── التخزين ─────────────────────────────────────────────

    def dump(self) -> Dict:
        """حالة قابلة للتخزين في JSON"""
        return {
            'version': 1,
            'features': list(self.FEATURES),
            'xtx': [list(row) for row in self._xtx],
            'xty': list(self._xty),
            'yy': self._yy,
            'y_sum': self._y_sum,
            'weight': self._weight,
            'samples': self.samples,
        }

    def load(self, state: Dict) -> bool:
        """استعادة الحالة؛ يُهمل أي حالة لا تطابق أبعاد النموذج الحالي"""
        try:
            if list(state.get('features') or []) != list(self.FEATURES):
                return False
            xtx = state['xtx']
            xty = state['xty']
            if len(xtx) != self._n or len(xty) != self._n:
                return False
            self._xtx = [[float(v) for v in row] for row in xtx]
            self._xty = [float(v) for v in xty]
            self._yy = float(state.get('yy', 0.0))
            self._y_sum = float(state.get('y_sum', 0.0))
            self._weight = float(state.get('weight', 0.0))
            self.samples = int(state.get('samples', 0))
            self._coefficients = None
            self._baseline = None
            self._r2 = None
            return True
        except (KeyError, TypeError, ValueError) as e:
            logger.debug(f"نموذج الطاقة: حالة محفوظة غير صالحة ({e}) - بداية جديدة")
            return False


# ═══════════════════════════════════════════════════════════
# نماذج البيانات
# ═══════════════════════════════════════════════════════════

@dataclass
class ProcessLoad:
    """حِمل عملية واحدة خلال فترة القياس، ونصيبها من القدرة المقيسة"""
    pid: int
    name: str
    cmdline: str = ''
    username: str = ''
    #: نسبة من كامل الجهاز (100 = كل الأنوية). هذه هي التي تُترجم إلى واط.
    cpu_percent: float = 0.0
    #: نسبة من نواة واحدة (100 = نواة كاملة، وقد تتجاوز 100 لعملية متعددة
    #: الخيوط). هذه هي المعروضة للمستخدم والمستخدمة في عتبات السلوك، لأنها
    #: لا تتغيّر بعدد أنوية الجهاز.
    cpu_core_percent: float = 0.0
    io_mb_per_sec: float = 0.0
    wakeups_per_sec: float = 0.0
    memory_percent: float = 0.0
    watts: Optional[float] = None   # None حين لا تتوفّر قدرة مقيسة
    share: float = 0.0              # 0..1 من القدرة الديناميكية
    sustained_seconds: float = 0.0
    behaviours: List[str] = field(default_factory=list)
    io_available: bool = True

    @property
    def is_unattributed(self) -> bool:
        return self.name == UNATTRIBUTED

    def as_dict(self) -> Dict[str, object]:
        return {
            'pid': self.pid,
            'name': self.name,
            'cmdline': self.cmdline,
            'username': self.username,
            'cpu_percent': round(self.cpu_percent, 2),
            'cpu_core_percent': round(self.cpu_core_percent, 1),
            'io_mb_per_sec': round(self.io_mb_per_sec, 3),
            'wakeups_per_sec': round(self.wakeups_per_sec, 1),
            'memory_percent': round(self.memory_percent, 2),
            'watts': None if self.watts is None else round(self.watts, 2),
            'share': round(self.share, 4),
            'sustained_seconds': round(self.sustained_seconds, 1),
            'behaviours': list(self.behaviours),
            'io_available': self.io_available,
        }


@dataclass
class AttributionResult:
    """نتيجة دورة نسب كاملة"""
    timestamp: float = 0.0
    interval_seconds: float = 0.0
    measured_watts: Optional[float] = None
    baseline_watts: float = 0.0
    dynamic_watts: Optional[float] = None
    unattributed_watts: Optional[float] = None
    loads: List[ProcessLoad] = field(default_factory=list)
    model_calibrated: bool = False
    model_confidence: int = 0
    model_r_squared: Optional[float] = None
    partial_dimensions: List[str] = field(default_factory=list)
    is_charging: bool = False
    trained: bool = False

    def top(self, count: int = 5, minimum_watts: float = 0.0) -> List[ProcessLoad]:
        """أعلى العمليات استهلاكاً، بلا سطر «غير المنسوب»"""
        real = [load for load in self.loads if not load.is_unattributed]
        if minimum_watts > 0:
            real = [load for load in real
                    if load.watts is not None and load.watts >= minimum_watts]
        return real[:count]

    def as_dict(self) -> Dict[str, object]:
        return {
            'timestamp': self.timestamp,
            'interval_seconds': round(self.interval_seconds, 2),
            'measured_watts': self.measured_watts,
            'baseline_watts': round(self.baseline_watts, 2),
            'dynamic_watts': self.dynamic_watts,
            'unattributed_watts': self.unattributed_watts,
            'model_calibrated': self.model_calibrated,
            'model_confidence': self.model_confidence,
            'model_r_squared': self.model_r_squared,
            'partial_dimensions': list(self.partial_dimensions),
            'is_charging': self.is_charging,
            'trained': self.trained,
            'loads': [load.as_dict() for load in self.loads],
        }


# ═══════════════════════════════════════════════════════════
# موانع النوم (سبب ضرر حقيقي ومباشر)
# ═══════════════════════════════════════════════════════════

#: ما يُعدّ منعاً فعلياً للنوم/الخمول حين يكون النمط `block`
BLOCKING_TARGETS = ('idle', 'sleep', 'suspend', 'hibernate')

#: سطر واحد من `systemd-inhibit --list`:
#: WHO(قد يحتوي فراغات) UID USER PID COMM WHAT WHY(قد يحتوي فراغات) MODE
_INHIBITOR_LINE = re.compile(
    r'^(?P<who>.*?)\s+(?P<uid>\d+)\s+(?P<user>\S+)\s+(?P<pid>\d+)\s+'
    r'(?P<comm>\S+)\s+(?P<what>\S+)\s+(?P<why>.*?)\s+(?P<mode>block|delay)\s*$'
)

_INHIBIT_CACHE_TTL = 25.0
_inhibit_cache: Tuple[float, Dict[int, Dict[str, str]]] = (0.0, {})
_inhibit_lock = threading.Lock()


def sleep_inhibitors(force: bool = False) -> Dict[int, Dict[str, str]]:
    """
    العمليات التي تمنع الجهاز من النوم أو من الخمول التلقائي.

    التمييز مهم ولا يُختصر: `mode=delay` يؤجّل النوم ثوانٍ معدودة وهو سلوك
    طبيعي لمدير الشبكة ومدير الطاقة، أما `mode=block` على هدف نوم أو خمول
    فيمنع النوم إلى ما لا نهاية، وهو من أكثر ما يستنزف بطارية لابتوب.
    يعيد `{pid: {...}}` مع `blocking` صريحة للتمييز بينهما.
    """
    global _inhibit_cache
    if not IS_LINUX or not shutil.which('systemd-inhibit'):
        return {}

    now = time.monotonic()
    with _inhibit_lock:
        stamp, cached = _inhibit_cache
        if not force and (now - stamp) < _INHIBIT_CACHE_TTL:
            return dict(cached)

    result: Dict[int, Dict[str, str]] = {}
    try:
        completed = subprocess.run(
            ['systemd-inhibit', '--list', '--no-pager', '--no-legend'],
            capture_output=True, text=True, timeout=6)
        lines = completed.stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug(f"systemd-inhibit غير متاح: {e}")
        lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.lower().startswith('who'):
            continue
        # الحقل الأول (WHO) قد يحتوي فراغات ("GNOME Shell")، فلا يصلح للترسية.
        # نُرسي على التتالي غير الملتبس: UID رقمي، ثم USER، ثم PID رقمي، ثم
        # COMM، ثم WHAT، ثم WHY (قد يحتوي فراغات)، والنمط آخر الحقول.
        match = _INHIBITOR_LINE.search(stripped)
        if not match:
            continue
        pid = int(match.group('pid'))
        comm = match.group('comm')
        what = match.group('what')
        why = match.group('why').strip()
        mode = match.group('mode')
        targets = [part for part in what.split(':') if part]
        blocking = mode == 'block' and any(
            target in BLOCKING_TARGETS for target in targets)
        entry = result.get(pid)
        if entry is not None and entry.get('blocking') and not blocking:
            continue  # لا تُخفِ منعاً حقيقياً بسجل تأجيل لاحق لنفس العملية
        result[pid] = {
            'comm': comm,
            'what': what,
            'why': why,
            'mode': mode,
            'blocking': blocking,
            'idle': 'idle' in targets,
        }

    with _inhibit_lock:
        _inhibit_cache = (now, dict(result))
    return result


# ═══════════════════════════════════════════════════════════
# محرّك النسب
# ═══════════════════════════════════════════════════════════

@dataclass
class _Counter:
    """عدّادات عملية في لحظة واحدة"""
    key: Tuple[int, float]
    cpu_seconds: float
    io_bytes: float
    ctx_switches: float
    io_available: bool


class PowerAttribution:
    """
    يحوّل عدّادات النظام إلى نسب طاقة لكل عملية.

    الاستخدام:
        attribution = PowerAttribution()
        attribution.sample(measured_watts=8.4, is_charging=False)   # تهيئة
        ...بعد ثوانٍ...
        result = attribution.sample(measured_watts=8.1, is_charging=False)

    أول نداء يعيد `None` لأن الفرق يحتاج عيّنتين. الكائن آمن بين الخيوط.
    """

    def __init__(self, model_state: Optional[Dict] = None,
                 cpu_count: Optional[int] = None):
        self._lock = threading.RLock()
        self.model = PowerModel(model_state)
        self.cpu_count = max(1, cpu_count or psutil.cpu_count(logical=True) or 1)

        self._previous: Dict[Tuple[int, float], _Counter] = {}
        self._previous_time: Optional[float] = None
        self._previous_cpu_busy: Optional[float] = None
        self._previous_disk_bytes: Optional[float] = None
        #: بداية استمرار الحِمل الثقيل لكل عملية {key: timestamp}
        self._sustained_since: Dict[Tuple[int, float], float] = {}
        self.last_result: Optional[AttributionResult] = None

    # ── القراءة الخام ───────────────────────────────────────

    @staticmethod
    def _read_counters() -> Tuple[Dict[Tuple[int, float], _Counter],
                                  Dict[Tuple[int, float], Dict[str, object]]]:
        """
        عدّادات كل العمليات المرئية مع بياناتها الوصفية.

        المفتاح `(pid, create_time)` لا `pid` وحده: أرقام العمليات تُعاد
        استخدامها، ونسبة حِمل عملية جديدة إلى قديمة تعطي قفزات كاذبة.
        """
        counters: Dict[Tuple[int, float], _Counter] = {}
        meta: Dict[Tuple[int, float], Dict[str, object]] = {}
        own_pid = os.getpid()

        # `username` و`memory_percent` مستثنيان من المسار الساخن عن قصد.
        #
        # قياس على جهاز بستّ مئات عملية: قراءة الحقول كلها 364 مللي ثانية،
        # وبلا هذين الحقلين 205 مللي ثانية (توفير 44٪). السبب أن `username`
        # يستدعي `pwd.getpwuid` لكل عملية (178 مللي ثانية وحده)، و`memory_percent`
        # يقرأ ملفاً إضافياً لكل عملية.
        #
        # وهما غير لازمين لكل العمليات: يُقرآن لاحقاً للعمليات القليلة التي
        # تُرشَّح فعلاً (46 من 596 في القياس)، وكلفتهما هناك نحو ثلاث مللي ثانية.
        # تطبيق يوفّر البطارية لا يجوز أن يقرأ ست مئة ملف ليعرض اثني عشر سطراً.
        attributes = ['pid', 'name', 'create_time', 'cpu_times', 'status',
                      'num_ctx_switches']
        for process in psutil.process_iter(attributes):
            try:
                info = process.info
                pid = info['pid']
                if pid in (0, own_pid):
                    continue
                # عملية زومبي انتهت فعلاً ولم يحصدها أبوها: لا تستهلك طاقة،
                # وعدّاد /proc/<pid>/io لها غير مقروء، فإدراجها يُنتج بُعداً
                # «ناقصاً» كاذباً ويشوّه حصص باقي العمليات.
                if info.get('status') == psutil.STATUS_ZOMBIE:
                    continue
                created = float(info.get('create_time') or 0.0)
                key = (pid, created)

                cpu_times = info.get('cpu_times')
                cpu_seconds = 0.0
                if cpu_times is not None:
                    cpu_seconds = float(cpu_times.user) + float(cpu_times.system)

                switches = info.get('num_ctx_switches')
                ctx = 0.0
                if switches is not None:
                    ctx = float(switches.voluntary) + float(switches.involuntary)

                io_bytes = 0.0
                io_available = True
                try:
                    io = process.io_counters()
                    io_bytes = float(getattr(io, 'read_bytes', 0) or 0) + \
                        float(getattr(io, 'write_bytes', 0) or 0)
                except (psutil.AccessDenied, psutil.NoSuchProcess,
                        NotImplementedError, AttributeError):
                    io_available = False

                counters[key] = _Counter(key, cpu_seconds, io_bytes, ctx, io_available)
                meta[key] = {'name': info.get('name') or f'pid-{pid}'}
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:  # عملية غريبة لا يجوز أن تُسقط الدورة كلها
                logger.debug(f"تعذّرت قراءة عدّادات عملية: {e}")
                continue
        return counters, meta

    @staticmethod
    def _system_totals() -> Tuple[Optional[float], Optional[float]]:
        """(ثواني المعالج المشغولة تراكمياً، بايتات القرص تراكمياً)"""
        busy = None
        try:
            times = psutil.cpu_times()
            idle = float(times.idle) + float(getattr(times, 'iowait', 0.0) or 0.0)
            busy = float(sum(times)) - idle
        except Exception as e:
            logger.debug(f"تعذّرت قراءة أزمنة المعالج: {e}")
        disk = None
        try:
            counters = psutil.disk_io_counters()
            if counters is not None:
                disk = float(counters.read_bytes) + float(counters.write_bytes)
        except Exception as e:
            logger.debug(f"تعذّرت قراءة عدّادات القرص: {e}")
        return busy, disk

    # ── الدورة الرئيسية ─────────────────────────────────────

    def sample(self, measured_watts: Optional[float] = None,
               is_charging: bool = False) -> Optional[AttributionResult]:
        """
        عيّنة جديدة. يعيد نتيجة النسب، أو `None` إن كانت هذه أول عيّنة أو
        كان الفاصل الزمني غير صالح (قصير جداً أو يتخطّى نوم الجهاز).
        """
        now = time.monotonic()
        counters, meta = self._read_counters()
        cpu_busy, disk_bytes = self._system_totals()

        with self._lock:
            previous = self._previous
            previous_time = self._previous_time
            previous_cpu = self._previous_cpu_busy
            previous_disk = self._previous_disk_bytes

            self._previous = counters
            self._previous_time = now
            self._previous_cpu_busy = cpu_busy
            self._previous_disk_bytes = disk_bytes

            if previous_time is None:
                return None

            interval = now - previous_time
            if interval < MIN_SAMPLE_INTERVAL or interval > MAX_SAMPLE_INTERVAL:
                # فاصل غير صالح: نحتفظ بالعيّنة الجديدة كأساس ولا نستنتج شيئاً.
                # الفجوة الطويلة تعني نوم الجهاز، فأي «استمرار» قبلها لاغٍ.
                if interval > MAX_SAMPLE_INTERVAL:
                    self._sustained_since.clear()
                return None

            result = self._attribute(counters, meta, previous, interval,
                                     cpu_busy, previous_cpu,
                                     disk_bytes, previous_disk,
                                     measured_watts, is_charging, now)
            self.last_result = result
            return result

    def _attribute(self, counters, meta, previous, interval,
                   cpu_busy, previous_cpu, disk_bytes, previous_disk,
                   measured_watts, is_charging, now) -> AttributionResult:
        """حساب الأحمال، تدريب النموذج، ثم توزيع القدرة المقيسة"""
        loads: List[ProcessLoad] = []
        partial: List[str] = []

        process_cpu_percent = 0.0
        process_io_mb = 0.0
        process_wakeups = 0.0
        io_denied = 0

        inhibitors = sleep_inhibitors()
        wall_now = time.time()

        for key, current in counters.items():
            before = previous.get(key)
            span = interval
            if before is None:
                # عملية ظهرت بين العيّنتين. عدّاداتها بدأت من الصفر عند إنشائها،
                # فعمرها هو الفاصل الصحيح لها. بلا هذا الفرع تبقى العملية
                # المستنزفة الجديدة غير مرئية دورة كاملة، وهي أهم ما يُرصد.
                age = wall_now - key[1]
                if not (0.5 <= age <= interval * 1.5):
                    continue
                span = age
                before = _Counter(key, 0.0, 0.0, 0.0, current.io_available)

            cpu_delta = max(0.0, current.cpu_seconds - before.cpu_seconds)
            cpu_core_percent = cpu_delta / span * 100.0
            cpu_percent = cpu_core_percent / self.cpu_count
            # فرق خيالي يعني إعادة استخدام رقم عملية أو عدّاداً ملتفاً:
            # لا يمكن لعملية أن تستهلك أكثر من كل أنوية الجهاز
            if cpu_percent > 100.0:
                continue

            io_mb = 0.0
            if current.io_available and before.io_available:
                io_mb = max(0.0, current.io_bytes - before.io_bytes) / 1_048_576.0 / span
            else:
                io_denied += 1

            wakeups = max(0.0, current.ctx_switches - before.ctx_switches) / span

            information = meta.get(key, {})
            load = ProcessLoad(
                pid=key[0],
                name=str(information.get('name') or f'pid-{key[0]}'),
                cpu_percent=cpu_percent,
                cpu_core_percent=cpu_core_percent,
                io_mb_per_sec=io_mb,
                wakeups_per_sec=wakeups,
                io_available=current.io_available and before.io_available,
            )
            load.sustained_seconds = self._track_sustained(key, cpu_core_percent, now)
            inhibitor = inhibitors.get(key[0])
            load.behaviours = self._behaviours(load, inhibitor)
            if load.cpu_percent > 0 or load.io_mb_per_sec > 0 or load.behaviours:
                # الحقول المكلفة تُقرأ الآن فقط، وللمرشَّحين وحدهم
                self._enrich(load, inhibitor)
                loads.append(load)

            process_cpu_percent += cpu_percent
            process_io_mb += io_mb
            process_wakeups += wakeups

        self._prune_sustained(counters)
        if io_denied:
            partial.append('io')

        # ── الأحمال الكلية: من عدّادات النظام حين تتوفّر، فهي تشمل زمن النواة
        #    والمقاطعات التي لا تُنسب إلى عملية ──
        total_cpu_percent = process_cpu_percent
        if cpu_busy is not None and previous_cpu is not None:
            system_cpu = max(0.0, cpu_busy - previous_cpu) / interval / self.cpu_count * 100.0
            if 0.0 <= system_cpu <= 100.0:
                total_cpu_percent = max(process_cpu_percent, system_cpu)
        total_io_mb = process_io_mb
        if disk_bytes is not None and previous_disk is not None:
            system_io = max(0.0, disk_bytes - previous_disk) / 1_048_576.0 / interval
            total_io_mb = max(process_io_mb, system_io)

        features = {'cpu': total_cpu_percent, 'io': total_io_mb,
                    'wake': process_wakeups}

        # ── التدريب: أثناء التفريغ فقط، وبقياس صالح فقط ──
        trained = False
        if measured_watts is not None and not is_charging and measured_watts > 0:
            before_samples = self.model.samples
            self.model.observe(features, float(measured_watts))
            trained = self.model.samples > before_samples

        baseline = self.model.baseline_watts
        dynamic: Optional[float] = None
        if measured_watts is not None and not is_charging:
            dynamic = max(0.0, float(measured_watts) - baseline)

        # ── توزيع القدرة: تكلفة كل عملية بمعاملات النموذج، ثم معايرة
        #    المجموع على ما قِيس فعلاً ──
        costs = [self.model.cost_watts({'cpu': load.cpu_percent,
                                        'io': load.io_mb_per_sec,
                                        'wake': load.wakeups_per_sec})
                 for load in loads]
        total_cost = sum(costs)

        unattributed: Optional[float] = None
        if dynamic is not None and total_cost > 0:
            # لا نضخّم التكاليف لتبلغ القدرة المقيسة: التضخيم يخترع استهلاكاً.
            # نقلّصها فقط إن تجاوزت المقيس، ونعرض الفارق باسمه.
            scale = min(1.0, dynamic / total_cost)
            for load, cost in zip(loads, costs):
                load.watts = cost * scale
                load.share = cost / total_cost
            unattributed = max(0.0, dynamic - total_cost * scale)
        elif dynamic is not None:
            unattributed = dynamic
            for load in loads:
                load.watts = 0.0
                load.share = 0.0
        else:
            # لا قدرة مقيسة (شحن أو عتاد لا يعرض التيار): الحصص فقط
            for load, cost in zip(loads, costs):
                load.share = (cost / total_cost) if total_cost > 0 else 0.0

        loads.sort(key=lambda item: (item.watts if item.watts is not None else item.share,
                                     item.cpu_percent), reverse=True)

        if unattributed is not None and unattributed > 0.05:
            loads.append(ProcessLoad(
                pid=0, name=UNATTRIBUTED, watts=unattributed,
                share=(unattributed / dynamic) if dynamic else 0.0))

        return AttributionResult(
            timestamp=time.time(),
            interval_seconds=interval,
            measured_watts=None if measured_watts is None else round(float(measured_watts), 2),
            baseline_watts=baseline,
            dynamic_watts=None if dynamic is None else round(dynamic, 2),
            unattributed_watts=None if unattributed is None else round(unattributed, 2),
            loads=loads,
            model_calibrated=self.model.calibrated,
            model_confidence=self.model.confidence(),
            model_r_squared=self.model.r_squared,
            partial_dimensions=partial,
            is_charging=bool(is_charging),
            trained=trained,
        )

    # ── الاستمرار والسلوك ───────────────────────────────────

    def _track_sustained(self, key: Tuple[int, float], cpu_core_percent: float,
                         now: float) -> float:
        """كم ثانية استمرت هذه العملية فوق عتبة الحِمل الثقيل بلا انقطاع"""
        if cpu_core_percent >= CPU_SUSTAINED_CORE_PERCENT:
            started = self._sustained_since.setdefault(key, now)
            return max(0.0, now - started)
        self._sustained_since.pop(key, None)
        return 0.0

    def _prune_sustained(self, counters: Dict) -> None:
        """نسيان العمليات المنتهية حتى لا ينمو التتبّع بلا حدّ"""
        self._sustained_since = {
            key: value for key, value in self._sustained_since.items()
            if key in counters}
        if len(self._sustained_since) > TRACK_LIMIT:
            # حدّ صلب: نُبقي الأقدم استمراراً لأنه الأجدر بالانتباه
            oldest = sorted(self._sustained_since.items(), key=lambda item: item[1])
            self._sustained_since = dict(oldest[:TRACK_LIMIT])

    @staticmethod
    def _enrich(load: ProcessLoad, inhibitor: Optional[Dict[str, str]]) -> None:
        """
        استكمال الحقول المكلفة للعمليات المرشَّحة فقط: المستخدم المالك ونسبة
        الذاكرة. قراءتهما لكل العمليات تكلّف 44٪ من زمن الجولة بلا فائدة، لأن
        تسعة أعشار العمليات لا تصل إلى العرض ولا إلى أي قرار.

        وسم ضغط الذاكرة يُضاف هنا لا في `_behaviours`، لأن معرفته تحتاج القراءة
        التي نؤجّلها. فشل القراءة (عملية انتهت) يُهمل: الحقلان للعرض لا للقرار.
        """
        try:
            process = psutil.Process(load.pid)
            with process.oneshot():
                load.username = process.username() or ''
                load.memory_percent = float(process.memory_percent() or 0.0)
        except (psutil.Error, OSError, ValueError):
            return
        if (load.memory_percent >= MEMORY_PRESSURE_PERCENT
                and BEHAVIOUR_MEMORY_PRESSURE not in load.behaviours):
            load.behaviours.append(BEHAVIOUR_MEMORY_PRESSURE)

    @staticmethod
    def _behaviours(load: ProcessLoad,
                    inhibitor: Optional[Dict[str, str]]) -> List[str]:
        """السلوكيات الضارة المرصودة لهذه العملية، بمعرّفات ثابتة للترجمة"""
        tags: List[str] = []
        if load.sustained_seconds >= CPU_SUSTAINED_SECONDS:
            tags.append(BEHAVIOUR_CPU_SUSTAINED)
        elif load.cpu_core_percent >= CPU_SPIKE_CORE_PERCENT:
            tags.append(BEHAVIOUR_CPU_SPIKE)
        if load.wakeups_per_sec >= WAKEUP_STORM_PER_SEC:
            tags.append(BEHAVIOUR_WAKEUP_STORM)
        if load.io_mb_per_sec >= DISK_THRASH_MB_PER_SEC:
            tags.append(BEHAVIOUR_DISK_THRASH)
        # ملاحظة صدق: `memory_percent` يُقرأ تأخيرياً في `_enrich`، فهذا الفحص
        # هنا لا يُطلق إلا حين تكون القيمة معروفة أصلاً. أثر ذلك أن عملية
        # ضاغطة على الذاكرة بلا أي معالج ولا قرص لا تُوسَم — وهو مقبول: ضغط
        # الذاكرة يستنزف البطارية حين يُسبّب تبديلاً، والتبديل يظهر كقرص.
        if load.memory_percent >= MEMORY_PRESSURE_PERCENT:
            tags.append(BEHAVIOUR_MEMORY_PRESSURE)
        if inhibitor and inhibitor.get('blocking'):
            tags.append(BEHAVIOUR_IDLE_INHIBITOR if inhibitor.get('idle')
                        else BEHAVIOUR_SLEEP_INHIBITOR)
        return tags

    # ── التخزين ─────────────────────────────────────────────

    def model_state(self) -> Dict:
        """حالة النموذج للحفظ مع بيانات التعلّم"""
        with self._lock:
            return self.model.dump()

    def reset(self) -> None:
        """تصفير التتبّع والنموذج (يستخدمه زر إعادة تعيين التعلّم)"""
        with self._lock:
            self.model = PowerModel()
            self._previous.clear()
            self._previous_time = None
            self._previous_cpu_busy = None
            self._previous_disk_bytes = None
            self._sustained_since.clear()
            self.last_result = None
