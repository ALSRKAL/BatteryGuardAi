#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات محرك الاستدلال العميق.

كل اختبار هنا يقيس صفة نريدها في الاستنتاج نفسه: متانة الكشف أمام التلويث،
رفض الحكم بلا بيانات كافية، وأن درجة الضرر مشتقّة من سلسلة حسابية يمكن
التحقق منها يدوياً لا من أوزان اعتباطية.
"""

import math
import random
import statistics
import time

import pytest

from battery_intelligence import (ACTION_ALERT, ACTION_NONE, ACTION_SUSPEND,
                                  ACTION_THROTTLE, ANOMALY_MIN_SAMPLES,
                                  ASSUMED_CAPACITY_WH,
                                  DEGRADATION_MIN_READINGS,
                                  DEGRADATION_MIN_SPAN_DAYS,
                                  ROBUST_Z_THRESHOLD, BatteryIntelligence,
                                  ChangePoint, DegradationTrend,
                                  OffenderLedger, Periodicity, RobustAnomaly,
                                  autocorrelation, robust_z_score)
from battery_science import cycle_wear_percent
from power_attribution import (BEHAVIOUR_CPU_SUSTAINED,
                              BEHAVIOUR_IDLE_INHIBITOR, AttributionResult,
                              ProcessLoad)

DISCHARGING = {'percent': 60, 'is_charging': False, 'reporting': True,
               'power_draw': 12.0}
CHARGING = {'percent': 60, 'is_charging': True, 'reporting': True,
            'power_draw': 40.0}
HEALTH = {'full_capacity': 60000.0, 'design_capacity': 62000.0,
          'capacity_unit': 'mwh'}


class TestRobustZScore:
    def test_refuses_to_judge_without_enough_data(self):
        """حكم مبنيّ على أربع قراءات ليس حكماً: يُعاد None لا رقم"""
        assert robust_z_score(5.0, [1.0, 2.0, 3.0]) is None
        assert robust_z_score(5.0, []) is None

    def test_zero_spread_does_not_divide_by_zero(self):
        """تشتّت صفري: لا لا-نهاية ولا استثناء، بل امتناع صريح"""
        assert robust_z_score(5.0, [1.0] * 30) is None

    def test_detects_outlier_in_noisy_baseline(self):
        random.seed(5)
        baseline = [random.gauss(1.0, 0.1) for _ in range(60)]
        assert abs(robust_z_score(1.05, baseline)) < ROBUST_Z_THRESHOLD
        assert robust_z_score(3.0, baseline) > ROBUST_Z_THRESHOLD

    def test_robust_where_mean_based_detection_fails(self):
        """
        جوهر استخدام الوسيط: خط أساس ملوَّث بقيم شاذة. الطريقة القديمة
        (المتوسط والانحراف المعياري) تفشل هنا لأن الشواذ ترفع كلا المقياسين
        فتُسكِت الكشف بعدها، والوسيط لا تفسده.
        """
        random.seed(9)
        polluted = [random.gauss(1.0, 0.1) for _ in range(60)] + [50.0] * 10

        assert robust_z_score(3.0, polluted) > ROBUST_Z_THRESHOLD
        mean_based = ((3.0 - statistics.mean(polluted))
                      / statistics.stdev(polluted))
        assert abs(mean_based) < ROBUST_Z_THRESHOLD, 'الطريقة القديمة تفشل هنا'


class TestRobustAnomaly:
    def test_hourly_baselines_are_independent(self):
        """
        استنزاف 2٪/د الظهر عادي، وفي الثالثة فجراً والشاشة مطفأة يعني شيئاً
        يعمل بلا إذن. خط أساس واحد يخفي الحالتين.
        """
        detector = RobustAnomaly('drain')
        random.seed(3)
        for _ in range(40):
            detector.observe(random.gauss(2.0, 0.15), hour=14)
            detector.observe(random.gauss(0.2, 0.02), hour=3)

        assert detector.observe(2.1, hour=14) is None
        night = detector.observe(2.1, hour=3)
        assert night is not None
        assert night.z_score > ROBUST_Z_THRESHOLD
        assert night.hour == 3
        assert night.baseline == pytest.approx(0.2, abs=0.05)

    def test_value_judged_before_joining_baseline(self):
        """القراءة تُحكَم ثم تُضاف: إضافتها أولاً تجعلها ترفع خط أساسها"""
        detector = RobustAnomaly('power')
        random.seed(4)
        for _ in range(ANOMALY_MIN_SAMPLES + 10):
            detector.observe(random.gauss(8.0, 0.2), hour=10)
        assert detector.observe(40.0, hour=10) is not None

    def test_state_roundtrip(self):
        import json

        detector = RobustAnomaly('drain')
        for index in range(40):
            detector.observe(1.0 + index * 0.01, hour=9)

        restored = RobustAnomaly('drain')
        restored.load(json.loads(json.dumps(detector.dump())))
        assert restored.baseline(9) == pytest.approx(detector.baseline(9))


class TestChangePoint:
    def test_silent_while_level_is_stable(self):
        detector = ChangePoint('drain')
        random.seed(6)
        events = [detector.observe(random.gauss(1.0, 0.1)) for _ in range(150)]
        assert not [event for event in events if event is not None]

    def test_false_alarm_rate_stays_low(self):
        """
        حرس على المعايرة: «صار جهازك يستنزف أسرع» رسالة مقلقة، وإطلاقها كذباً
        يُفقد التطبيق ثقة المستخدم. الإعداد السابق (k=0.5, h=5) كان يُنتج
        تنبيهاً كاذباً كل 490 عيّنة، أي كل ثلاث ساعات تفريغ متصل.

        نقيس هنا على 2000 عيّنة ثابتة × 10 تجارب = 20 ألف عيّنة، ونشترط ألّا
        يتجاوز عدد التجارب المُنبِّهة كذباً واحدة.
        """
        false_alarms = 0
        for trial in range(10):
            random.seed(4000 + trial)
            detector = ChangePoint('drain')
            for _ in range(2000):
                if detector.observe(random.gauss(1.0, 0.1)) is not None:
                    false_alarms += 1
                    break
        assert false_alarms <= 1, (
            f'{false_alarms} من 10 تجارب أنتجت تنبيهاً كاذباً على مستوى ثابت')

    def test_detects_sustained_shift_with_correct_levels(self):
        """
        المستوى «بعد» يجب أن يعكس الارتفاع فعلاً. خطأ سابق جعله يساوي المستوى
        «قبل» لأن نافذة الحساب كانت تحتوي مئات قيم خط الأساس.
        """
        detector = ChangePoint('drain')
        random.seed(6)
        for _ in range(120):
            detector.observe(random.gauss(1.0, 0.1))

        events = [detector.observe(random.gauss(1.6, 0.1)) for _ in range(60)]
        found = [event for event in events if event is not None]

        assert found, 'لم يُرصد ارتفاع مستدام بنسبة 60٪'
        event = found[0]
        assert event.direction == 'up'
        assert event.before == pytest.approx(1.0, abs=0.1)
        assert event.after > event.before * 1.3
        assert event.change_percent > 25

    def test_does_not_repeat_the_same_change_forever(self):
        """بعد الإعلان يصير المستوى الجديد هو الأساس، فلا يُعلن التغيّر مراراً"""
        detector = ChangePoint('drain')
        random.seed(6)
        for _ in range(120):
            detector.observe(random.gauss(1.0, 0.1))
        found = [detector.observe(random.gauss(1.6, 0.1)) for _ in range(120)]
        assert len([event for event in found if event is not None]) <= 3

    def test_detects_improvement_too(self):
        detector = ChangePoint('drain')
        random.seed(8)
        for _ in range(120):
            detector.observe(random.gauss(2.0, 0.1))
        found = [detector.observe(random.gauss(0.8, 0.1)) for _ in range(60)]
        events = [event for event in found if event is not None]
        assert events and events[0].direction == 'down'
        assert events[0].change_percent < 0


class TestPeriodicity:
    def test_autocorrelation_matches_known_period(self):
        series = [math.sin(index * 2 * math.pi / 24) for index in range(24 * 10)]
        # السقف النظري هنا 0.9 لا 1.0: البسط يجمع N−lag حداً والمقام يجمع N
        assert autocorrelation(series, 24) > 0.85
        assert autocorrelation(series, 12) < -0.5
        assert autocorrelation(series, 0) is None
        assert autocorrelation([1.0, 2.0], 24) is None

    def test_finds_working_hours_pattern(self):
        periodicity = Periodicity()
        random.seed(2)
        for _ in range(12):
            for hour in range(24):
                rate = 2.2 if 9 <= hour <= 17 else 0.25
                periodicity.observe(rate + random.gauss(0, 0.05), hour=hour)

        rhythm = periodicity.analyse()
        assert rhythm is not None
        assert rhythm.period_hours == 24
        assert set(rhythm.peak_hours) <= set(range(9, 18))
        assert all(hour < 9 or hour > 17 for hour in rhythm.quiet_hours)

    def test_no_claim_without_enough_history(self):
        periodicity = Periodicity()
        for hour in range(20):
            periodicity.observe(1.0, hour=hour)
        assert periodicity.analyse() is None


class TestDegradationTrend:
    def test_measures_real_slope(self):
        """
        تآكل مقيس على هذه الخلية، لا مُستنتج من جدول عام. الميل المصنوع
        0.03 نقطة صحة يومياً = 10.95٪ سنوياً.
        """
        trend = DegradationTrend()
        now = time.time()
        for day in range(0, 200, 10):
            soh = 95.0 - day * 0.03
            trend.observe(60000.0 * soh / 100.0, 60000.0,
                          timestamp=now - (200 - day) * 86400)

        estimate = trend.estimate()
        assert estimate is not None
        assert estimate.annual_loss_percent == pytest.approx(0.03 * 365, abs=0.2)
        assert estimate.readings == 20
        assert estimate.r_squared > 0.99
        assert estimate.current_soh == pytest.approx(89.3, abs=0.1)
        assert estimate.days_to_eol > 0
        assert estimate.measured is True

    def test_refuses_annual_claim_from_hours_of_data(self):
        """
        انحدار على ساعات يعطي ميلاً هائلاً بلا معنى، وعرضه كـ«فقد سنوي» تضليل.
        """
        trend = DegradationTrend()
        now = time.time()
        for index in range(DEGRADATION_MIN_READINGS + 4):
            trend.observe(60000.0 - index * 100, 60000.0,
                          timestamp=now - (10 - index) * 3600)
        assert trend.estimate() is None

    def test_refuses_with_too_few_readings(self):
        trend = DegradationTrend()
        now = time.time()
        for index in range(DEGRADATION_MIN_READINGS - 1):
            trend.observe(60000.0 - index * 500, 60000.0,
                          timestamp=now - (100 - index * 10) * 86400)
        assert trend.estimate() is None

    def test_identical_readings_not_stored(self):
        """قراءة كل ثانيتين بنفس القيمة تُضخّم الملف بلا معلومة جديدة"""
        trend = DegradationTrend()
        now = time.time()
        for index in range(50):
            trend.observe(60000.0, 60000.0, timestamp=now - (50 - index) * 86400)
        assert len(trend._readings) == 1

    def test_ignores_invalid_capacity(self):
        trend = DegradationTrend()
        for full, design in ((0, 60000), (60000, 0), (None, 60000), (60000, None)):
            trend.observe(full, design)
        assert trend._readings == []

    def test_reports_zero_days_past_end_of_life(self):
        trend = DegradationTrend()
        now = time.time()
        for day in range(0, 200, 20):
            soh = 82.0 - day * 0.02
            trend.observe(60000.0 * soh / 100.0, 60000.0,
                          timestamp=now - (200 - day) * 86400)
        estimate = trend.estimate()
        assert estimate is not None and estimate.days_to_eol == 0


class TestOffenderLedger:
    def test_tracks_persistence_and_correlation(self):
        """
        التتبّع بالاسم لا برقم العملية: المتصفّحات تُعيد إنشاء عملياتها كثيراً،
        والتتبّع بالرقم ينسى كل شيء عند كل إعادة تشغيل فيستحيل الحكم على الثبات.
        """
        ledger = OffenderLedger()
        for index in range(60):
            watts = 3.0 + (index % 10) * 0.3
            drain = 0.5 + (index % 10) * 0.05
            loads = [ProcessLoad(pid=100 + index, name='greedy', watts=watts)]
            if index % 6 == 0:
                loads.append(ProcessLoad(pid=200, name='rare', watts=2.0))
            ledger.observe(loads, drain)

        greedy = ledger.record('greedy')
        rare = ledger.record('rare')

        assert greedy.persistence > 0.9
        assert rare.persistence < 0.35, 'الغياب معلومة: يجب أن يخفض الثبات'
        assert greedy.correlation > 0.9
        assert greedy.average_watts == pytest.approx(4.35, abs=0.1)

    def test_correlation_needs_enough_pairs(self):
        ledger = OffenderLedger()
        for _ in range(5):
            ledger.observe([ProcessLoad(pid=1, name='x', watts=3.0)], 0.5)
        assert ledger.record('x').correlation is None

    def test_state_roundtrip(self):
        import json

        ledger = OffenderLedger()
        for index in range(30):
            ledger.observe([ProcessLoad(pid=1, name='x', watts=2.0 + index * 0.1)],
                           0.4 + index * 0.01)

        restored = OffenderLedger()
        restored.load(json.loads(json.dumps(ledger.dump())))
        assert restored.record('x').persistence == pytest.approx(
            ledger.record('x').persistence)


class TestDamageScore:
    """
    درجة الضرر ليست رأياً: هي سلسلة حسابية من قياس وعلم منشور، ويمكن التحقق
    من كل خطوة فيها يدوياً.
    """

    @staticmethod
    def _report(watts=6.0, behaviours=(), hours=5.0, dod=40.0,
                health=None, model_confidence=80, baseline=5.0):
        intelligence = BatteryIntelligence()
        loads = [ProcessLoad(pid=1, name='hog', watts=watts,
                             cpu_percent=20.0, cpu_core_percent=160.0,
                             behaviours=list(behaviours))]
        attribution = AttributionResult(
            measured_watts=watts + baseline, baseline_watts=baseline,
            dynamic_watts=watts, loads=loads, model_calibrated=True,
            model_confidence=model_confidence, interval_seconds=30.0)
        return intelligence.update(
            attribution, DISCHARGING, HEALTH if health is None else health,
            drain_rate=0.9, hours_on_battery_per_day=hours, typical_dod=dod)

    def test_chain_matches_manual_calculation(self):
        report = self._report(watts=6.0)
        offender = report.worst

        assert report.capacity_wh == 60.0 and report.capacity_assumed is False
        expected_per_hour = 6.0 / 60.0 * 100
        assert offender.percent_per_hour == pytest.approx(expected_per_hour)

        expected_loss = (expected_per_hour * 5.0 * 365 / 100.0) * \
            cycle_wear_percent(40.0)
        assert offender.annual_capacity_loss == pytest.approx(expected_loss,
                                                              rel=1e-9)
        assert offender.recommended_action == ACTION_SUSPEND
        assert offender.evidence, 'كل رقم يحتاج سنده المكتوب'

    def test_idle_inhibitor_flagged_despite_low_watts(self):
        """
        مانع الخمول كلفته أن الجهاز لا ينام أصلاً، لا واطه. عملية بنصف واط
        تمنع النوم أضرّ من عملية بواطين تنتهي بسرعة.
        """
        report = self._report(watts=0.5, behaviours=[BEHAVIOUR_IDLE_INHIBITOR])
        offender = report.worst

        assert offender.damage_score >= 30
        assert offender.recommended_action != ACTION_NONE
        assert any('idle_inhibitor' in item for item in offender.evidence)

    def test_behaviour_raises_score(self):
        plain = self._report(watts=1.0).worst.damage_score
        tagged = self._report(watts=1.0,
                              behaviours=[BEHAVIOUR_CPU_SUSTAINED]).worst.damage_score
        assert tagged > plain

    def test_mah_capacity_declared_assumed(self):
        """
        سعة بوحدة الشحنة لا تُحوَّل إلى طاقة بلا جهد: الافتراض يُعلَن بدل حساب
        رقم خاطئ يبدو دقيقاً.
        """
        report = self._report(health={'full_capacity': 5000.0,
                                      'design_capacity': 5200.0,
                                      'capacity_unit': 'mah'})
        assert report.capacity_assumed is True
        assert report.capacity_wh == ASSUMED_CAPACITY_WH
        assert report.worst.capacity_assumed is True

    def test_implausible_capacity_rejected(self):
        report = self._report(health={'full_capacity': 900.0,
                                      'design_capacity': 900.0,
                                      'capacity_unit': 'mwh'})
        assert report.capacity_assumed is True

    def test_low_model_confidence_lowers_offender_confidence(self):
        high = self._report(model_confidence=90).worst.confidence
        low = self._report(model_confidence=10).worst.confidence
        assert low < high


class TestIntelligenceLifecycle:
    def test_no_drain_analysis_while_charging(self):
        """
        أثناء الشحن لا معنى لمعدل استنزاف، والقدرة المقروءة قدرة الشاحن.
        تحليلها يُنتج شذوذاً كاذباً كل مرة يوصل المستخدم الشاحن.
        """
        intelligence = BatteryIntelligence()
        for _ in range(60):
            intelligence.update(None, CHARGING, HEALTH, drain_rate=1.5)
        assert len(intelligence.recent_anomalies) == 0
        assert intelligence.periodicity.analyse() is None

    def test_capacity_tracked_even_while_charging(self):
        """تآكل السعة لا يتوقّف عند الشحن، فقراءتها تستمر"""
        intelligence = BatteryIntelligence()
        intelligence.update(None, CHARGING, HEALTH)
        assert len(intelligence.degradation._readings) == 1

    def test_handles_missing_attribution(self):
        intelligence = BatteryIntelligence()
        report = intelligence.update(None, DISCHARGING, HEALTH, drain_rate=0.8)
        assert report.offenders == []
        assert report.measured_watts is None

    def test_actionable_filters_none(self):
        intelligence = BatteryIntelligence()
        loads = [ProcessLoad(pid=1, name='big', watts=8.0),
                 ProcessLoad(pid=2, name='small', watts=0.5)]
        attribution = AttributionResult(
            measured_watts=13.0, baseline_watts=5.0, dynamic_watts=8.5,
            loads=loads, model_confidence=80, interval_seconds=30.0)
        report = intelligence.update(attribution, DISCHARGING, HEALTH,
                                     drain_rate=0.9, hours_on_battery_per_day=5.0)

        assert all(item.recommended_action != ACTION_NONE
                   for item in report.actionable())
        assert len(report.actionable()) <= len(report.offenders)

    def test_state_roundtrip_and_reset(self):
        import json

        intelligence = BatteryIntelligence()
        for _ in range(10):
            intelligence.update(None, DISCHARGING, HEALTH, drain_rate=0.7)

        restored = BatteryIntelligence(json.loads(json.dumps(intelligence.dump())))
        assert restored.samples == intelligence.samples

        intelligence.reset()
        assert intelligence.samples == 0
        assert intelligence.last_report is None
        assert intelligence.ledger.record('anything') is None

    def test_report_is_json_serialisable(self):
        import json

        intelligence = BatteryIntelligence()
        report = intelligence.update(None, DISCHARGING, HEALTH, drain_rate=0.7)
        payload = json.loads(json.dumps(report.as_dict(), ensure_ascii=False))
        assert 'offenders' in payload and 'capacity_assumed' in payload
