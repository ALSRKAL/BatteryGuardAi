#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
محرك الذكاء الاصطناعي لتحليل البطارية - الجيل الخامس

تحسينات هذا الإصدار:
- تقدير معدلات الشحن/التفريغ بمرشح EWMA متجاوب (بدل المتوسط مدى الحياة)
- تنبؤ الوقت المتبقي بانحدار خطي على النافذة الأخيرة (أدق من المعدل الثابت)
- درجة ثقة صادقة مبنية على حجم البيانات وثبات القياسات
- كتابة ذرية آمنة بين الخيوط عبر storage.py
- إصلاح أخطاء رياضية (فروع لا تُصل، أسبقية عمليات، O(n²))
"""

import logging
import math
import statistics
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from battery_intelligence import (ANOMALY_WINDOW, ROBUST_Z_THRESHOLD,
                                  robust_z_score)
from battery_science import (Advice, BatterySnapshot, build_advice,
                             days_to_end_of_life, equivalent_full_cycles,
                             projected_annual_loss)
from i18n import t
from storage import JsonStore

logger = logging.getLogger('BatteryGuard')

# سقف موحد لسجل الاستخدام في الذاكرة وعلى القرص
HISTORY_LIMIT = 2000

# ─────────────────────────────────────────────────────────────
# وتيرة العمل الثقيل
#
# قياس فعلي على سجل ممتلئ (2000 نقطة) على جهاز حقيقي:
#   save_learning_data()      ≈ 840 مللي ثانية  (كلها ترميز JSON للسجل)
#   _perform_deep_analysis()  ≈ 140 مللي ثانية  بلا الحفظ
#
# الوتيرة السابقة كانت: تحليل عميق كل 30 عيّنة وحفظ كل 50، أي عند عيّنة كل
# ثانيتين: تحليل كل دقيقة وحفظ كل 100 ثانية. النتيجة نحو 1.5 ثانية معالج في
# كل دقيقة، وكتابة نحو 200 كيلوبايت على القرص كل دقيقة.
#
# هذا نقيض غرض التطبيق مرتين: يحرق معالجاً، ويوقظ القرص باستمرار — وهو نفس
# سلوك `disk_thrash` الذي يحذّر منه المستخدم. الأنماط السلوكية تتغيّر على مدى
# ساعات لا ثوانٍ، فالتحليل كل عشر دقائق يعطي نفس النتيجة بجزء من الكلفة.
#
# الحفظ الأقل تكراراً صار آمناً لأن الإغلاق النظيف (lifecycle.py) يضمن حفظاً
# قسرياً عند SIGTERM وتسجيل الخروج وإعادة التشغيل، فلا تُفقد ساعة من التعلّم
# عند إغلاق الجهاز.
# ─────────────────────────────────────────────────────────────

#: كل كم عيّنة يجري التحليل العميق (عيّنة كل ثانيتين ⇒ نحو عشر دقائق)
DEEP_ANALYSIS_EVERY = 300

#: كل كم عيّنة تُحدَّث بصمة السلوك (عملية رخيصة على آخر 20 عيّنة)
FINGERPRINT_EVERY = 60

#: أقصر مدة بين كتابتين فعليتين على القرص (ثانية).
#: حرس زمني فوق العدّادات: أي مسار يطلب الحفظ بتكرار أعلى لا يصل إلى القرص.
MIN_SAVE_INTERVAL = 300.0

# أطول فجوة بين عينتين تُحسب كزمن متصل (دقائق). ما بعدها = نوم/إيقاف.
MAX_SAMPLE_GAP_MIN = 15

# أصغر عمق تفريغ يُعدّ حدثاً يستحق الحساب (%)
MIN_DISCHARGE_DEPTH = 3

# طول النافذة المستخدمة للتنبؤ اللحظي بالانحدار الخطي
REGRESSION_WINDOW = 40

# معامل التمهيد (Smoothing) لمرشح EWMA: قيمة أعلى = استجابة أسرع للتغيرات
EWMA_ALPHA = 0.25


class BatteryAI:
    """محرك تحليل سلوك البطارية والتنبؤ به"""

    def __init__(self):
        self._lock = threading.RLock()
        self.usage_history: List[Dict] = []

        self.store = JsonStore('battery_ai_data.json', defaults=self._default_learning_data())
        self.learning_data = self.store.data

        # استعادة السجل من التخزين
        saved_history = self.learning_data.pop('usage_history', [])
        if isinstance(saved_history, list):
            self.usage_history = [e for e in saved_history if isinstance(e, dict)][-HISTORY_LIMIT:]

        self.predictions: Dict[str, float] = {}
        # تنبؤات معلقة تنتظر التحقق: [{'target_ts': float, 'expected': float}]
        self._pending_validations: List[Dict] = []
        self.prediction_accuracy: List[float] = []

        self.behavior_model: Dict = {}
        self.anomaly_detector = AnomalyDetector()

        # معدلات EWMA اللحظية (% في الدقيقة)
        self._ewma_drain_rate = 0.0
        self._ewma_charge_rate = 0.0

        # صحة العتاد الحقيقية (من sysfs/WMI) إن توفرت
        self._hardware_health: Optional[int] = None

        # حرس الكتابة على القرص: آخر حفظ فعلي، وهل بقي تغيير غير محفوظ
        self._last_save_time = 0.0
        self._save_pending = False

        # عدّاد عيّنات تصاعدي لا يتوقّف.
        #
        # لا يجوز استخدام `len(usage_history)` لتحديد وتيرة العمل الثقيل: السجل
        # مقصوص عند `HISTORY_LIMIT`، فبعد امتلائه يبقى طوله ثابتاً عند 2000
        # إلى الأبد. وبما أن 2000 يقبل القسمة على 30 و50 و60، فإن **كل** عيّنة
        # بعد الامتلاء كانت تُطلق تحليلاً عميقاً وكتابة كاملة على القرص. أي أن
        # التطبيق كان يعمل بلا مشكلة أول ساعة ثم يبدأ حرق المعالج والكتابة كل
        # ثانيتين بلا سبب ظاهر. القياس: 7.9٪ من نواة و300 كتابة لكل عشر دقائق.
        self._sample_count = int(self.learning_data.get('sample_count', 0))

        # حقول يقرؤها الواجهة مباشرة
        self.learning_progress = int(self.learning_data.get('learning_progress', 0))
        self.ai_maturity_level = self.learning_data.get('ai_maturity_level', 'مبتدئ')
        self.personalization_score = int(self.learning_data.get('personalization_level', 0))

        logger.info(
            f"تم تهيئة محرك AI - نقاط مسجلة: {len(self.usage_history)}, "
            f"دورات تعلم: {self.learning_data.get('learning_iterations', 0)}"
        )

    # ──────────────────────────────────────────────────────────────
    # التخزين الافتراضي
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _default_learning_data() -> Dict:
        return {
            'patterns': [],
            'recommendations': [],
            'efficiency_score': 100,
            'health_score': 100,
            'heavy_usage_hours': [],
            'moderate_usage_hours': [],
            'light_usage_hours': [],
            'optimal_charge_times': [],
            'average_drain_rate': 0.0,
            'median_drain_rate': 0.0,
            'peak_drain_rate': 0.0,
            'average_charge_rate': 0.0,
            'usage_statistics': {},
            'behavior_profile': {},
            'anomalies_detected': [],
            'charge_cycle_count': 0,
            'total_charge_time': 0,
            'total_discharge_time': 0,
            'learning_iterations': 0,
            'prediction_accuracy_history': [],
            'user_behavior_fingerprint': {},
            'weekly_patterns': {},
            'degradation_rate': 0,
            'optimal_soc_range': [40, 80],
            'charge_efficiency': 100,
            'discharge_efficiency': 100,
            'usage_intensity_score': 0,
            'battery_longevity_score': 100,
            'ai_confidence_level': 0,
            'personalization_level': 0,
            'optimization_history': [],
            #: عدّاد العيّنات التصاعدي؛ يحكم وتيرة العمل الثقيل عبر الجلسات
            'sample_count': 0,
            'last_updated': None,
        }

    def save_learning_data(self, force: bool = False) -> bool:
        """
        حفظ بيانات التعلم (كتابة ذرية آمنة بين الخيوط).

        ترميز السجل الممتلئ إلى JSON يكلّف نحو 840 مللي ثانية ويكتب مئات
        الكيلوبايتات، فالكتابة محدودة بـ `MIN_SAVE_INTERVAL`. أي نداء أسرع من
        ذلك يُهمل بصمت ويُعاد `False`، إلا أن يكون `force=True`.

        `force=True` تُستخدم في مسار الإغلاق وعند إعادة التعيين: هناك الحفظ
        واجب لا اختياري، ولا يجوز أن يمنعه مؤقّت.
        """
        now = time.monotonic()
        with self._lock:
            if not force and (now - self._last_save_time) < MIN_SAVE_INTERVAL:
                self._save_pending = True
                return False

            self.learning_data['usage_history'] = self.usage_history[-HISTORY_LIMIT:]
            self.learning_data['last_updated'] = datetime.now().isoformat()
            self.learning_data['prediction_accuracy_history'] = self.prediction_accuracy[-50:]
            self.learning_data['learning_progress'] = self.learning_progress
            self.learning_data['ai_maturity_level'] = self.ai_maturity_level
            self.learning_data['personalization_level'] = self.personalization_score
            self.learning_data['sample_count'] = self._sample_count
            points = len(self.learning_data['usage_history'])
            self._last_save_time = now
            self._save_pending = False

        if self.store.save():
            logger.debug(f"تم حفظ بيانات AI ({points} نقطة)")
            return True
        return False

    def reset(self):
        """
        تصفير كامل للتعلم داخل نفس الكائن (آمن مع المراجع الأخرى).
        ملاحظة مهمة: يعيد استخدام نفس المثال حتى تبقى مراجع
        MonitorThread/Optimizer صالحة بدلاً من استبدال الكائن.
        """
        with self._lock:
            defaults = self._default_learning_data()
            self.usage_history.clear()
            self.predictions.clear()
            self._pending_validations.clear()
            self.prediction_accuracy.clear()
            self.behavior_model.clear()
            self.anomaly_detector.anomalies.clear()
            self._ewma_drain_rate = 0.0
            self._ewma_charge_rate = 0.0
            self.learning_progress = 0
            self.ai_maturity_level = 'مبتدئ'
            self.personalization_score = 0
            self.learning_data.clear()
            self.learning_data.update(defaults)
            self._last_save_time = 0.0
            self._sample_count = 0
        # إعادة التعيين تُكتب فوراً: المستخدم طلب المسح ويتوقّع أثره الآن
        self.save_learning_data(force=True)
        logger.info("تمت إعادة تعيين بيانات الذكاء الاصطناعي")

    # ──────────────────────────────────────────────────────────────
    # التحليل الرئيسي
    # ──────────────────────────────────────────────────────────────

    def analyze_usage_pattern(self, battery_data: Dict):
        """تحليل عينة جديدة من حالة البطارية مع التعلم التدريجي"""
        current_time = datetime.now()

        entry = {
            'timestamp': current_time.isoformat(),
            'battery_percent': int(battery_data['percent']),
            'is_charging': bool(battery_data['is_charging']),
            'power_draw': round(float(battery_data.get('power_draw', 0)), 2),
            'voltage': round(float(battery_data.get('voltage', 0)), 2),
            'current': round(float(battery_data.get('current', 0)), 2),
            'hour': current_time.hour,
            'day_of_week': current_time.weekday(),
            'is_weekend': current_time.weekday() >= 5,
        }

        with self._lock:
            self._validate_predictions(current_time)
            self._update_ewma_rates(entry)

            prev = self.usage_history[-1] if self.usage_history else None
            self.usage_history.append(entry)
            if len(self.usage_history) > HISTORY_LIMIT:
                del self.usage_history[:len(self.usage_history) - HISTORY_LIMIT]

            self._detect_instant_anomalies(entry)

            # العدّاد التصاعدي هو مرجع الوتيرة، لا طول السجل المقصوص
            self._sample_count += 1
            counter = self._sample_count
            n = len(self.usage_history)
            deep_due = (counter % DEEP_ANALYSIS_EVERY == 0)
            fingerprint_due = (counter % FINGERPRINT_EVERY == 0)

        if deep_due and n >= 50:
            self._perform_deep_analysis()
        elif fingerprint_due:
            with self._lock:
                self.learning_data['learning_iterations'] += 1
                self._update_behavior_fingerprint(self.usage_history[-20:])

        # الحفظ يقرّر بنفسه: `MIN_SAVE_INTERVAL` هو الحاكم، لا عدّاد العيّنات.
        # المحاولة رخيصة (مقارنة زمن) والكتابة وحدها هي المكلفة.
        if deep_due or fingerprint_due:
            self.save_learning_data()

    def _update_ewma_rates(self, entry: Dict):
        """تحديث معدلات EWMA اللحظية من فرق العينتين المتتاليتين"""
        if len(self.usage_history) < 1:
            return
        try:
            prev = self.usage_history[-1]
            dt_min = (datetime.fromisoformat(entry['timestamp']) -
                      datetime.fromisoformat(prev['timestamp'])).total_seconds() / 60.0
            if not (0 < dt_min <= 10):  # تجاهل الفجوات الطويلة أو القفزات
                return
            dpct = entry['battery_percent'] - prev['battery_percent']
            if abs(dpct) < 1:  # تغيير أقل من 1% غير مفيد (دقة العداد الصحيحة)
                return
            rate = dpct / dt_min  # + شحن، − تفريغ
            if rate > 0 and entry['is_charging']:
                base = self._ewma_charge_rate
                self._ewma_charge_rate = (EWMA_ALPHA * rate + (1 - EWMA_ALPHA) * base) if base > 0 else rate
            elif rate < 0 and not entry['is_charging']:
                drain = -rate
                base = self._ewma_drain_rate
                self._ewma_drain_rate = (EWMA_ALPHA * drain + (1 - EWMA_ALPHA) * base) if base > 0 else drain
        except Exception as e:
            logger.debug(f"خطأ في تحديث معدلات EWMA: {e}")

    def _get_recent_rates(self, charging: bool) -> List[float]:
        """استخراج معدلات فردية (%/دقيقة) من آخر عينات متوافقة الحالة"""
        rates = []
        hist = self.usage_history[-(REGRESSION_WINDOW * 4):]
        for i in range(1, len(hist)):
            prev, curr = hist[i - 1], hist[i]
            if bool(curr['is_charging']) != charging:
                continue
            try:
                dt = (datetime.fromisoformat(curr['timestamp']) -
                      datetime.fromisoformat(prev['timestamp'])).total_seconds() / 60.0
            except Exception:
                continue
            if not (0 < dt <= 15):
                continue
            dpct = curr['battery_percent'] - prev['battery_percent']
            if charging and dpct > 0:
                rates.append(dpct / dt)
            elif not charging and dpct < 0:
                rates.append(-dpct / dt)
        return rates

    def _regression_minutes(self, start_pct: int, target_pct: int, charging: bool) -> Optional[float]:
        """
        تقدير الدقائق للانتقال من مستوى إلى آخر باستخدام انحدار خطي
        على (الزمن بالدقائق، نسبة البطارية) في النافذة الأخيرة.
        """
        pts: List[Tuple[float, float]] = []
        t0 = None
        hist = self.usage_history[-(REGRESSION_WINDOW * 4):]
        for e in hist:
            if bool(e['is_charging']) != charging:
                continue
            ts = datetime.fromisoformat(e['timestamp'])
            if t0 is None:
                t0 = ts
            pts.append(((ts - t0).total_seconds() / 60.0, float(e['battery_percent'])))

        if len(pts) < REGRESSION_WINDOW // 2:
            return None

        n = len(pts)
        mean_x = sum(p[0] for p in pts) / n
        mean_y = sum(p[1] for p in pts) / n
        var_x = sum((p[0] - mean_x) ** 2 for p in pts)
        if var_x <= 1e-9:
            return None
        cov_xy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pts)
        slope = cov_xy / var_x  # %/دقيقة (سالب عند التفريغ)

        if charging and slope <= 0.01:
            return None
        if not charging and slope >= -0.01:
            return None

        delta = abs(target_pct - start_pct)
        return delta / abs(slope)

    # ──────────────────────────────────────────────────────────────
    # التنبؤ بالوقت المتبقي
    # ──────────────────────────────────────────────────────────────

    def predict_time_remaining(self, current_battery: int, is_charging: bool) -> Optional[str]:
        """تنبؤ دقيق بالوقت المتبقي (انحدار خطي ثم EWMA ثم متوسط عام)"""
        with self._lock:
            enough_data = len(self.usage_history) >= 20
            avg_charge = float(self.learning_data.get('average_charge_rate', 0) or 0)
            avg_drain = float(self.learning_data.get('average_drain_rate', 0) or 0)

        if not enough_data:
            return "جارٍ جمع البيانات..."

        if is_charging:
            target = 80
            if current_battery >= target:
                return "وصلت للمستوى الأمثل"
            minutes = self._regression_minutes(current_battery, target, charging=True)
            if minutes is None:
                rate = self._ewma_charge_rate or avg_charge
                if rate <= 0:
                    return None
                minutes = (target - current_battery) / rate
            # الشحن يتباطأ قرب الامتلاء (منحنى CV)
            if current_battery >= 70:
                minutes *= 1.25
            return self._format_time(minutes)

        safe_level = 20
        if current_battery <= safe_level:
            return "أقل من الحد الآمن"
        minutes = self._regression_minutes(current_battery, safe_level, charging=False)
        if minutes is None:
            rate = self._ewma_drain_rate or avg_drain
            if rate <= 0:
                return None
            minutes = (current_battery - safe_level) / rate
        # تسريع الاستنزاف في ساعات الاستخدام المكثف
        heavy_hours = self.learning_data.get('heavy_usage_hours', [])
        if datetime.now().hour in heavy_hours:
            minutes *= 0.8
        return self._format_time(minutes)

    @staticmethod
    def _format_time(minutes: float) -> str:
        if not math.isfinite(minutes) or minutes < 1:
            return "أقل من دقيقة"
        if minutes < 60:
            return f"~{int(minutes)} دقيقة"
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if hours > 24:
            days = hours // 24
            hours %= 24
            return f"~{days} يوم {hours}س"
        return f"~{hours}س {mins}د"

    # ──────────────────────────────────────────────────────────────
    # التحقق الصادق من دقة التنبؤ
    # ──────────────────────────────────────────────────────────────

    def _validate_predictions(self, now: datetime):
        """
        التحقق من التنبؤات المعلقة بعد مرور ساعة كاملة عن وقتها
        (بدلاً من مقارنة كل عينة كل ثانيتين كما كان سابقاً).
        """
        still_pending = []
        for p in self._pending_validations:
            age_min = (now - p['created']).total_seconds() / 60.0
            if age_min < 60:
                still_pending.append(p)
                continue
            actual = self.usage_history[-1]['battery_percent'] if self.usage_history else None
            if actual is not None:
                error = abs(p['expected'] - actual)
                self.prediction_accuracy.append(max(0.0, 100.0 - error * 2))
        self._pending_validations = still_pending[-12:]

        if len(self.prediction_accuracy) > 100:
            del self.prediction_accuracy[:-100]

    def _queue_hourly_prediction(self):
        """جدولة تنبؤ الساعة القادمة للتحقق لاحقاً"""
        if len(self.usage_history) < 50:
            return
        now = datetime.now()
        similar = [e for e in self.usage_history
                   if e['hour'] == now.hour and e['day_of_week'] == now.weekday()]
        if similar:
            expected = statistics.mean(e['battery_percent'] for e in similar)
            self.predictions['expected_battery_next_hour'] = expected
            self._pending_validations.append({
                'created': now,
                'expected': expected,
            })

    # ──────────────────────────────────────────────────────────────
    # التحليل العميق الدوري
    # ──────────────────────────────────────────────────────────────

    def _perform_deep_analysis(self):
        with self._lock:
            if len(self.usage_history) < 50:
                return
            self._analyze_advanced_rates()
            self._analyze_time_patterns()
            self._build_behavior_model()
            self._calculate_health_efficiency_scores()
            self._detect_patterns()
            self._predict_future_behavior()
            self._analyze_charge_cycles()
            self._update_weekly_patterns()
            self._calculate_learning_progress()
            self.last_analysis_time = datetime.now()
        # الحفظ محدود بمهلته: التحليل العميق لا يفرض كتابة على القرص
        self.save_learning_data()
        logger.info("اكتمل التحليل العميق الدوري للبيانات")

    def _iter_pairs(self):
        """تكرار زوجي مع تخزين مؤقت للطوابع الزمنية (بدل التحليل المتكرر)"""
        cache: Dict[int, datetime] = {}

        def parse(idx: int, entry: Dict) -> Optional[datetime]:
            ts = cache.get(idx)
            if ts is None:
                try:
                    ts = datetime.fromisoformat(entry['timestamp'])
                except Exception:
                    return None
                cache[idx] = ts
            return ts

        hist = self.usage_history
        for i in range(1, len(hist)):
            t_prev = parse(i - 1, hist[i - 1])
            t_curr = parse(i, hist[i])
            if t_prev is None or t_curr is None:
                continue
            yield hist[i - 1], hist[i], (t_curr - t_prev).total_seconds() / 60.0

    def _analyze_advanced_rates(self):
        """إحصائيات شاملة لمعدلات الشحن/التفريغ"""
        drain_rates, charge_rates, power_levels = [], [], []
        for prev, curr, dt_min in self._iter_pairs():
            if not (0 < dt_min < 30):
                continue
            dpct = curr['battery_percent'] - prev['battery_percent']
            if curr['is_charging'] and dpct > 0:
                charge_rates.append(dpct / dt_min)
            elif not curr['is_charging'] and dpct < 0:
                drain_rates.append(-dpct / dt_min)
            power = curr.get('power_draw', 0)
            if power > 0:
                power_levels.append(power)

        ld = self.learning_data
        if drain_rates:
            ld['average_drain_rate'] = statistics.mean(drain_rates)
            ld['median_drain_rate'] = statistics.median(drain_rates)
            ld['peak_drain_rate'] = max(drain_rates)
            ld['drain_rate_std'] = statistics.stdev(drain_rates) if len(drain_rates) > 1 else 0.0
        if charge_rates:
            ld['average_charge_rate'] = statistics.mean(charge_rates)
            ld['median_charge_rate'] = statistics.median(charge_rates)
            ld['peak_charge_rate'] = max(charge_rates)
        if power_levels:
            ld['average_power_draw'] = statistics.mean(power_levels)
            ld['peak_power_draw'] = max(power_levels)

    def _analyze_time_patterns(self):
        """تصنيف ساعات اليوم حسب شدة الاستخدام"""
        hourly: Dict[int, List[float]] = defaultdict(list)
        for prev, curr, dt_min in self._iter_pairs():
            if (0 < dt_min < 30 and not curr['is_charging']
                    and curr['battery_percent'] < prev['battery_percent']):
                hourly[curr['hour']].append(
                    (prev['battery_percent'] - curr['battery_percent']) / dt_min)

        heavy, moderate, light = [], [], []
        for hour, rates in hourly.items():
            avg = statistics.mean(rates)
            if avg > 1.5:
                heavy.append(hour)
            elif avg > 0.8:
                moderate.append(hour)
            else:
                light.append(hour)

        self.learning_data['heavy_usage_hours'] = sorted(heavy)
        self.learning_data['moderate_usage_hours'] = sorted(moderate)
        self.learning_data['light_usage_hours'] = sorted(light)

        # أكثر الساعات شيوعاً للشحن
        charge_counts: Dict[int, int] = defaultdict(int)
        for e in self.usage_history:
            if e['is_charging']:
                charge_counts[e['hour']] += 1
        top = sorted(charge_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        self.learning_data['optimal_charge_times'] = [h for h, _ in top]

    def _build_behavior_model(self):
        """نمذجة عادات الشحن للمستخدم"""
        if len(self.usage_history) < 100:
            return
        recent = self.usage_history[-200:]

        sessions: List[List[Dict]] = []
        current: List[Dict] = []
        for e in recent:
            if e['is_charging']:
                current.append(e)
            elif current:
                sessions.append(current)
                current = []
        if current:
            sessions.append(current)

        if sessions:
            self.behavior_model['avg_charge_session_length'] = statistics.mean(len(s) for s in sessions)
            starts = [s[0]['battery_percent'] for s in sessions]
            ends = [s[-1]['battery_percent'] for s in sessions]
            self.behavior_model['typical_charge_start'] = statistics.mean(starts)
            self.behavior_model['typical_charge_end'] = statistics.mean(ends)

    def _calculate_health_efficiency_scores(self):
        """
        حساب درجات الكفاءة (سلوكية) والصحة.
        الصحة تمزج صحة العتاد الحقيقية (energy_full/design) مع السلوك
        بدلاً من رقم سلوكي فقط يتناقض مع قراءة النظام.
        """
        if len(self.usage_history) < 100:
            return
        recent = self.usage_history[-200:]
        total = len(recent)

        optimal_range = sum(1 for e in recent if 40 <= e['battery_percent'] <= 80)
        overcharge = sum(1 for e in recent if e['battery_percent'] > 90 and e['is_charging'])
        deep_discharge = sum(1 for e in recent if e['battery_percent'] < 20)
        critical_discharge = sum(1 for e in recent if e['battery_percent'] < 10)

        # درجة تبدأ عند 50 وتتحرك نحو 0-100 بحيث تكون المكافآت والعقوبات مرئية فعلاً
        behavior = 50.0
        behavior += (optimal_range / total) * 30      # مكافأة النطاق الأمثل
        behavior -= (overcharge / total) * 20         # عقوبة الشحن الزائد
        behavior -= (deep_discharge / total) * 25     # عقوبة التفريغ العميق
        behavior -= (critical_discharge / total) * 35  # عقوبة شديدة للحرج
        behavior = max(0.0, min(100.0, behavior))

        hw = self._hardware_health
        if hw is not None and hw > 0:
            # 70% عتاد حقيقي + 30% سلوك
            health = hw * 0.7 + behavior * 0.3
        else:
            cycles = self.learning_data.get('charge_cycle_count', 0)
            health = behavior - min(15, cycles / 20)
            if overcharge > total * 0.2:
                health -= 10
            if deep_discharge > total * 0.15:
                health -= 15
            health = max(0.0, min(100.0, health))

        self.learning_data['efficiency_score'] = int(round(behavior))
        self.learning_data['health_score'] = int(round(max(0.0, min(100.0, health))))

    def update_hardware_health(self, health_percentage: int):
        """تغذية المحرك بصحة العتاد الحقيقية من نظام التشغيل"""
        if health_percentage and 1 <= int(health_percentage) <= 100:
            self._hardware_health = int(health_percentage)

    def _detect_patterns(self):
        """اكتشاف أنماط سلوكية متكررة"""
        patterns: List[Dict] = []
        hist = self.usage_history
        n = len(hist)
        if n < 50:
            self.learning_data['patterns'] = patterns
            return

        night_charging = sum(1 for e in hist if e['is_charging'] and (e['hour'] >= 22 or e['hour'] <= 6))
        if night_charging > n * 0.25:
            patterns.append({
                'type': 'night_charging',
                'confidence': min(95, int(night_charging / n * 400)),
                'description': 'شحن ليلي منتظم'
            })

        heavy_hours = self.learning_data.get('heavy_usage_hours', [])
        if heavy_hours:
            patterns.append({
                'type': 'heavy_usage',
                'confidence': 85,
                'description': f"استخدام مكثف: {', '.join(f'{h}:00' for h in heavy_hours)}",
                'hours': heavy_hours,
            })

        partial = sum(1 for e in hist if e['is_charging'] and 40 <= e['battery_percent'] <= 80)
        if partial > n * 0.3:
            patterns.append({
                'type': 'partial_charging',
                'confidence': 90,
                'description': 'شحن جزئي صحي (40-80%)',
            })

        quick = sum(1 for e in hist if e['is_charging'] and e['battery_percent'] < 40)
        if quick > n * 0.15:
            patterns.append({
                'type': 'quick_charging',
                'confidence': 75,
                'description': 'شحن متكرر من مستويات منخفضة',
            })

        continuous = 0
        for e in reversed(hist):
            if not e['is_charging']:
                continuous += 1
            else:
                break
        if continuous > 30:
            patterns.append({
                'type': 'continuous_use',
                'confidence': 80,
                'description': f'استخدام مستمر لـ {continuous} قراءة',
            })

        weekend = self.learning_data.get('weekend_usage_pattern')
        weekday = self.learning_data.get('weekday_usage_pattern')
        if weekend and weekday and abs(weekend - weekday) > 15:
            patterns.append({
                'type': 'weekend_heavy' if weekend > weekday else 'weekday_heavy',
                'confidence': 70,
                'description': 'استخدام أكبر في نهاية الأسبوع' if weekend > weekday else 'استخدام أكبر في أيام العمل',
            })

        self.learning_data['patterns'] = patterns

    def _predict_future_behavior(self):
        """التنبؤ بمستوى البطارية المتوقع وجدولة التحقق منه"""
        if len(self.usage_history) < 100:
            return
        now = datetime.now()
        similar = [e for e in self.usage_history
                   if e['hour'] == now.hour and e['day_of_week'] == now.weekday()]
        if similar:
            self.predictions['expected_battery_next_hour'] = statistics.mean(
                e['battery_percent'] for e in similar)
        self._queue_hourly_prediction()

        # مستوى بدء الشحن المعتاد: انتقال واحد pass واحد بدون .index() (كان O(n²))
        starts: List[int] = []
        hist = self.usage_history
        for i in range(1, len(hist)):
            if hist[i]['is_charging'] and not hist[i - 1]['is_charging']:
                starts.append(hist[i]['battery_percent'])
        if starts:
            self.predictions['typical_charge_start_level'] = statistics.mean(starts)

    def _analyze_charge_cycles(self):
        """إحصاء دورات الشحن في مسار واحد O(n)"""
        cycles: List[Dict] = []
        session: Optional[Tuple[Dict, Dict]] = None

        for e in self.usage_history:
            if e['is_charging']:
                if session is None:
                    session = (e, e)
                else:
                    session = (session[0], e)
            elif session is not None:
                start_e, end_e = session
                try:
                    duration = ((datetime.fromisoformat(end_e['timestamp']) -
                                 datetime.fromisoformat(start_e['timestamp'])).total_seconds()) / 60.0
                except Exception:
                    duration = 0
                gain = end_e['battery_percent'] - start_e['battery_percent']
                if gain > 3:  # تجاهل جلسات الشحن الرمزية
                    cycles.append({
                        'start_percent': start_e['battery_percent'],
                        'end_percent': end_e['battery_percent'],
                        'duration_minutes': duration,
                        'gain': gain,
                    })
                session = None

        if cycles:
            self.learning_data['charge_cycle_count'] = len(cycles)
            self.learning_data['avg_charge_duration'] = statistics.mean(c['duration_minutes'] for c in cycles)
            self.learning_data['avg_charge_gain'] = statistics.mean(c['gain'] for c in cycles)

    def _update_weekly_patterns(self):
        """أنماط أيام الأسبوع"""
        if len(self.usage_history) < 100:
            return
        day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']

        weekly: Dict[int, Dict[str, List[float]]] = defaultdict(lambda: {'drain': [], 'usage': []})
        weekend_levels, weekday_levels = [], []

        for e in self.usage_history[-500:]:
            power = e.get('power_draw', 0)
            if power > 0:
                weekly[e['day_of_week']]['usage'].append(power)
            if not e['is_charging']:
                weekly[e['day_of_week']]['drain'].append(e['battery_percent'])
                (weekend_levels if e['is_weekend'] else weekday_levels).append(e['battery_percent'])

        patterns = {}
        for day, data in weekly.items():
            usage_avg = statistics.mean(data['usage']) if data['usage'] else 0
            patterns[day] = {
                'day': day_names[day],
                'avg_drain': statistics.mean(data['drain']) if data['drain'] else 0,
                'avg_usage': usage_avg,
                'intensity': 'high' if usage_avg > 15 else 'normal',
            }
        self.learning_data['weekly_patterns'] = patterns

        if weekend_levels and weekday_levels:
            self.learning_data['weekend_usage_pattern'] = statistics.mean(weekend_levels)
            self.learning_data['weekday_usage_pattern'] = statistics.mean(weekday_levels)

    def _detect_instant_anomalies(self, current_entry: Dict):
        """
        كشف الاستهلاك غير الطبيعي بدرجة z متينة (وسيط + انحراف مطلق وسيطي).

        الطريقة السابقة كانت «أكبر من ضعف متوسط آخر عشر قراءات»، وفيها عيبان
        جوهريان: القراءة الشاذة نفسها تدخل في المتوسط فترفعه وتُسكِت الكشف
        بعدها، والعتبة الثابتة 10 واط تعني أن جهازاً منخفض الاستهلاك لا يُكتشف
        فيه شذوذ أبداً. الوسيط لا تفسده القيم الشاذة، والحدّ نسبي لا مطلق.
        """
        current_power = float(current_entry.get('power_draw', 0) or 0)
        if current_power <= 0:
            return

        # نافذة أطول من عشر قراءات: الوسيط يحتاج بيانات ليكون خط أساس
        window = [float(e.get('power_draw', 0) or 0)
                  for e in self.usage_history[-ANOMALY_WINDOW - 1:-1]
                  if float(e.get('power_draw', 0) or 0) > 0]
        score = robust_z_score(current_power, window)
        if score is None or score < ROBUST_Z_THRESHOLD:
            return

        baseline = statistics.median(window)
        self.anomaly_detector.add_anomaly({
            'type': 'high_power_consumption',
            'timestamp': current_entry['timestamp'],
            'value': round(current_power, 2),
            'average': round(baseline, 2),
            'z_score': round(score, 2),
            'severity': 'critical' if score >= ROBUST_Z_THRESHOLD * 2 else 'warning',
            'key': 'anomaly.high_power',
            'params': {'value': round(current_power, 1),
                       'baseline': round(baseline, 1)},
        })

    def _update_behavior_fingerprint(self, recent_data: List[Dict]):
        """تحديث بصمة سلوك المستخدم"""
        if len(recent_data) < 2:
            return
        fp = self.learning_data.setdefault('user_behavior_fingerprint', {})

        sessions = 0
        prev_charging = False
        for e in recent_data:
            if e['is_charging'] and not prev_charging:
                sessions += 1
            prev_charging = e['is_charging']
        fp['charge_frequency'] = sessions

        charge_levels = [e['battery_percent'] for e in recent_data if e['is_charging']]
        if charge_levels:
            fp['preferred_charge_level'] = statistics.mean(charge_levels)

        powers = [e.get('power_draw', 0) for e in recent_data if e.get('power_draw', 0) > 0]
        if powers:
            fp['typical_usage_intensity'] = statistics.mean(powers)

        # ملاحظة: الأقواس هنا ضرورية (خطأ أسبقية سابق جعل الشرط صحيباً دائماً ليلاً)
        night_usage = sum(1 for e in recent_data if e['hour'] >= 22 or e['hour'] <= 6)
        fp['night_owl_score'] = (night_usage / len(recent_data)) * 100

        high_power = sum(1 for e in recent_data if e.get('power_draw', 0) > 15)
        fp['power_user_score'] = (high_power / len(recent_data)) * 100

    # ──────────────────────────────────────────────────────────────
    # التوصيات
    # ──────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────
    # ملف الاستخدام المرصود (أساس كل تقدير تآكل)
    # ──────────────────────────────────────────────────────────────

    def usage_profile(self, ceiling: int = 80) -> Dict:
        """
        ملف الاستخدام الفعلي من السجل: كم من الوقت فوق السقف، وكم على
        البطارية، وما أعماق التفريغ المرصودة، وتوزيع الوقت على مستويات الشحن.

        الفجوات الأطول من `MAX_SAMPLE_GAP_MIN` تُستثنى: نوم الجهاز ليس
        زمن بقاء عند مستوى شحن، وحسابه كذلك يضخّم التقدير.
        """
        with self._lock:
            history = list(self.usage_history)

        profile = {
            'minutes_total': 0.0,
            'minutes_plugged': 0.0,
            'minutes_on_battery': 0.0,
            'minutes_high_soc': 0.0,
            'soc_histogram': {},
            'discharge_events': [],
            'observed_days': 0.0,
        }
        if len(history) < 2:
            return profile

        histogram: Dict[int, float] = defaultdict(float)
        events: List[float] = []
        run_start: Optional[float] = None
        previous_percent: Optional[float] = None

        for index in range(1, len(history)):
            prev, curr = history[index - 1], history[index]
            try:
                delta_min = (datetime.fromisoformat(curr['timestamp']) -
                             datetime.fromisoformat(prev['timestamp'])).total_seconds() / 60.0
            except (KeyError, ValueError):
                continue
            if not (0 < delta_min <= MAX_SAMPLE_GAP_MIN):
                # فجوة طويلة: أغلق أي تفريغ مفتوح ولا تحسب الزمن
                if run_start is not None and previous_percent is not None:
                    depth = run_start - previous_percent
                    if depth >= MIN_DISCHARGE_DEPTH:
                        events.append(depth)
                    run_start = None
                previous_percent = curr.get('battery_percent')
                continue

            percent = float(prev.get('battery_percent', 0))
            charging = bool(prev.get('is_charging'))

            profile['minutes_total'] += delta_min
            if charging:
                profile['minutes_plugged'] += delta_min
            else:
                profile['minutes_on_battery'] += delta_min
            if percent > ceiling:
                profile['minutes_high_soc'] += delta_min
            histogram[int(percent // 10 * 10)] += delta_min

            # أعماق التفريغ: بداية كل هبوط متصل وحتى انعكاسه
            current_percent = float(curr.get('battery_percent', percent))
            if not charging and current_percent < percent:
                if run_start is None:
                    run_start = percent
            elif run_start is not None:
                depth = run_start - percent
                if depth >= MIN_DISCHARGE_DEPTH:
                    events.append(depth)
                run_start = None
            previous_percent = current_percent

        if run_start is not None and previous_percent is not None:
            depth = run_start - previous_percent
            if depth >= MIN_DISCHARGE_DEPTH:
                events.append(depth)

        profile['soc_histogram'] = dict(histogram)
        profile['discharge_events'] = events
        profile['observed_days'] = round(profile['minutes_total'] / 1440.0, 3)
        return profile

    def wear_projection(self, ceiling: int = 80, temp_c: Optional[float] = None,
                        soh_percent: Optional[float] = None) -> Dict:
        """
        تقدير التآكل السنوي (تقويمي + دوري) والزمن المتبقي حتى حدّ نهاية
        العمر الافتراضي، مبنياً على ملف الاستخدام المرصود لا على افتراضات.
        """
        profile = self.usage_profile(ceiling)
        loss = projected_annual_loss(
            soc_profile=profile['soc_histogram'] or None,
            temp_c=temp_c,
            discharge_events=profile['discharge_events'] or None,
            days_observed=max(0.5, profile['observed_days']),
        )
        health = soh_percent if soh_percent is not None else self._hardware_health
        return {
            **loss,
            'observed_days': profile['observed_days'],
            'equivalent_cycles': round(
                equivalent_full_cycles(sum(profile['discharge_events'])), 2),
            'hours_high_soc_per_day': round(
                profile['minutes_high_soc'] / 60.0 / max(0.5, profile['observed_days']), 2),
            'hours_plugged_per_day': round(
                profile['minutes_plugged'] / 60.0 / max(0.5, profile['observed_days']), 2),
            'hours_on_battery_per_day': round(
                profile['minutes_on_battery'] / 60.0 / max(0.5, profile['observed_days']), 2),
            'typical_dod': round(
                statistics.median(profile['discharge_events']), 1) if profile['discharge_events'] else 0.0,
            'days_to_eol': days_to_end_of_life(health, loss['total']),
            'soh_percent': health,
        }

    # ──────────────────────────────────────────────────────────────
    # النصائح المهيكلة
    # ──────────────────────────────────────────────────────────────

    def snapshot(self, battery_status: Dict, health: Optional[Dict] = None,
                 floor: int = 40, ceiling: int = 80,
                 control_available: bool = False,
                 control_active: bool = False) -> BatterySnapshot:
        """بناء لقطة الحالة التي يعمل عليها محرك النصائح"""
        health = health or {}
        temp = battery_status.get('temperature')
        projection = self.wear_projection(ceiling, temp, health.get('health_percentage'))

        with self._lock:
            drain = self._ewma_drain_rate or float(self.learning_data.get('average_drain_rate', 0) or 0)
            charge = self._ewma_charge_rate or float(self.learning_data.get('average_charge_rate', 0) or 0)
            heavy_hours = list(self.learning_data.get('heavy_usage_hours', []))

        return BatterySnapshot(
            percent=float(battery_status.get('percent', 0)),
            is_charging=bool(battery_status.get('is_charging')),
            reporting=bool(battery_status.get('reporting', True)),
            temp_c=temp,
            soh_percent=health.get('health_percentage'),
            cycle_count=health.get('cycle_count'),
            drain_rate_pct_min=drain,
            charge_rate_pct_min=charge,
            hours_high_soc_per_day=projection['hours_high_soc_per_day'],
            hours_plugged_per_day=projection['hours_plugged_per_day'] or 12.0,
            hours_on_battery_per_day=projection['hours_on_battery_per_day'],
            typical_dod=projection['typical_dod'],
            night_usage_score=float(
                (self.learning_data.get('user_behavior_fingerprint') or {})
                .get('night_owl_score', 0) or 0),
            control_available=control_available,
            control_active=control_active,
            ceiling=int(ceiling),
            floor=int(floor),
            heavy_usage_hours=heavy_hours,
            hour=datetime.now().hour,
        )

    def get_advice(self, battery_status: Dict, health: Optional[Dict] = None,
                   floor: int = 40, ceiling: int = 80,
                   control_available: bool = False,
                   control_active: bool = False, limit: int = 6) -> List[Advice]:
        """
        نصائح مهيكلة (شدّة + مفتاح ترجمة + سند + إجراء) من محرك علم البطارية.
        الواجهة هي من تترجم وتعرض؛ هذه الطبقة لا تعرف شيئاً عن النصوص.
        """
        snap = self.snapshot(battery_status, health, floor, ceiling,
                             control_available, control_active)
        advice = build_advice(snap, limit=limit)
        with self._lock:
            self.learning_data['recommendations'] = [a.id for a in advice]
            self.learning_data['last_recommendation_time'] = datetime.now().isoformat()
        return advice

    def get_smart_recommendations(self, current_battery: int, is_charging: bool,
                                  ceiling: int = 80, floor: int = 40) -> List[str]:
        """
        نصوص التوصيات جاهزة للعرض. غلاف رفيع فوق `get_advice` يبقي التوافق
        مع المستدعين الذين يحتاجون نصوصاً مباشرة.
        """
        advice = self.get_advice(
            {'percent': current_battery, 'is_charging': is_charging, 'reporting': True},
            floor=floor, ceiling=ceiling)
        return [t(item.key, **item.params) for item in advice]

    def get_optimization_recommendations(self, current_battery: int, is_charging: bool) -> List[str]:
        """توصيات تحسين النظام بناءً على الحالة المرصودة"""
        with self._lock:
            drain_rate = self._ewma_drain_rate or float(
                self.learning_data.get('average_drain_rate', 0) or 0)
            efficiency = int(self.learning_data.get('efficiency_score', 100))

        recs: List[str] = []
        if current_battery < 20 and not is_charging:
            recs.append(t('opt.low_battery'))
        elif current_battery < 40 and not is_charging:
            recs.append(t('opt.extend_runtime'))
        if drain_rate > 1.5:
            recs.append(t('opt.high_drain', rate=round(drain_rate, 2)))
        if efficiency < 70:
            recs.append(t('opt.low_efficiency', score=efficiency))
        return recs[:3]

    # ──────────────────────────────────────────────────────────────
    # الإحصائيات والثقة
    # ──────────────────────────────────────────────────────────────

    def get_usage_statistics(self) -> Dict:
        """إحصائيات شاملة للعرض"""
        with self._lock:
            self._calculate_learning_progress()
            total = len(self.usage_history)
            charging = sum(1 for e in self.usage_history if e['is_charging'])

        if total == 0:
            return {}

        ld = self.learning_data
        return {
            'total_records': total,
            'charging_percentage': charging / total * 100,
            'average_drain_rate': ld.get('average_drain_rate', 0),
            'median_drain_rate': ld.get('median_drain_rate', 0),
            'peak_drain_rate': ld.get('peak_drain_rate', 0),
            'average_charge_rate': ld.get('average_charge_rate', 0),
            'peak_charge_rate': ld.get('peak_charge_rate', 0),
            'efficiency_score': ld.get('efficiency_score', 100),
            'health_score': ld.get('health_score', 100),
            'patterns_found': len(ld.get('patterns', [])),
            'heavy_usage_hours': ld.get('heavy_usage_hours', []),
            'optimal_charge_times': ld.get('optimal_charge_times', []),
            'charge_cycle_count': ld.get('charge_cycle_count', 0),
            'avg_charge_duration': ld.get('avg_charge_duration', 0),
            'average_power_draw': ld.get('average_power_draw', 0),
            'peak_power_draw': ld.get('peak_power_draw', 0),
            'learning_progress': self.learning_progress,
            'ai_maturity_level': self.ai_maturity_level,
            'personalization_score': self.personalization_score,
            'degradation_rate': ld.get('degradation_rate', 0),
            'battery_longevity_score': ld.get('battery_longevity_score', 100),
        }

    def get_detailed_analysis(self) -> Dict:
        """تحليل مفصل للعرض"""
        return {
            'behavior_model': self.behavior_model,
            'predictions': dict(self.predictions),
            'patterns': self.learning_data.get('patterns', []),
            'anomalies': self.anomaly_detector.get_recent_anomalies(),
            'efficiency_score': self.learning_data.get('efficiency_score', 100),
            'health_score': self.learning_data.get('health_score', 100),
        }

    def _calculate_learning_progress(self):
        """تقدم التعلم ومستوى النضج"""
        factors = [
            min(100.0, len(self.usage_history) / 2000 * 100),
            min(100.0, self.learning_data.get('learning_iterations', 0) / 500 * 100),
        ]
        if self.prediction_accuracy:
            factors.append(statistics.mean(self.prediction_accuracy[-50:]))
        factors.append(min(100.0, len(self.learning_data.get('patterns', [])) / 10 * 100))

        self.learning_progress = int(statistics.mean(factors))
        if self.learning_progress < 20:
            self.ai_maturity_level = 'مبتدئ'
        elif self.learning_progress < 40:
            self.ai_maturity_level = 'يتعلم'
        elif self.learning_progress < 60:
            self.ai_maturity_level = 'متوسط'
        elif self.learning_progress < 80:
            self.ai_maturity_level = 'متقدم'
        else:
            self.ai_maturity_level = 'خبير'

    def _calculate_confidence(self) -> int:
        """
        درجة ثقة صادقة: تعتمد على حجم البيانات وثبات معدل الاستنزاف
        ونتائج التنبؤ الفعلية (بدل مقاييس وهمية).
        """
        with self._lock:
            data_factor = min(100.0, len(self.usage_history) / 800 * 100)
            accuracy_factor = (
                statistics.mean(self.prediction_accuracy[-20:]) if self.prediction_accuracy else 60.0
            )

        # ثبات المعدل: انحراف معياري صغير نسبياً = ثقة أعلى
        drain_std = float(self.learning_data.get('drain_rate_std', 0) or 0)
        drain_avg = float(self.learning_data.get('average_drain_rate', 0) or 0)
        stability_factor = 70.0
        if drain_avg > 0 and drain_std > 0:
            cv = drain_std / drain_avg  # معامل الاختلاف
            stability_factor = max(20.0, 100.0 - cv * 100)

        confidence = data_factor * 0.3 + accuracy_factor * 0.45 + stability_factor * 0.25
        return int(min(99, max(5, confidence)))

    def _get_prediction_confidence(self) -> int:
        """ثقة التنبؤ الحالي بناءً على الدقة الأخيرة وتباينها"""
        if not self.prediction_accuracy:
            return 55
        recent = self.prediction_accuracy[-10:]
        avg = statistics.mean(recent)
        if len(recent) > 1:
            std_dev = statistics.stdev(recent)
            if std_dev < 10:
                avg += 5
        return int(min(99, max(5, avg)))


class AnomalyDetector:
    """كاشف شذوذ بسيط بسعة محدودة"""

    def __init__(self, max_anomalies: int = 50):
        self.anomalies: List[Dict] = []
        self.max_anomalies = max_anomalies

    def add_anomaly(self, anomaly: Dict):
        self.anomalies.append(anomaly)
        if len(self.anomalies) > self.max_anomalies:
            del self.anomalies[:len(self.anomalies) - self.max_anomalies]

    def get_recent_anomalies(self, count: int = 5) -> List[Dict]:
        return self.anomalies[-count:]
