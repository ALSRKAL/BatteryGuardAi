#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات محرك الذكاء الاصطناعي"""

import statistics
from datetime import datetime, timedelta

import pytest

from battery_ai import HISTORY_LIMIT, AnomalyDetector, BatteryAI


def make_status(percent, charging=False, power=10.0, reporting=True,
                temperature=None):
    return {
        'percent': percent,
        'is_charging': charging,
        'power_draw': power,
        'voltage': 11.4,
        'current': 1.0,
        'reporting': reporting,
        'temperature': temperature,
    }


@pytest.fixture
def ai():
    return BatteryAI()


class TestInitAndPersistence:
    def test_fresh_init_empty_history(self, ai):
        assert len(ai.usage_history) == 0
        assert ai.learning_data.get('efficiency_score') == 100

    def test_save_and_reload(self, isolated_data_dir):
        ai = BatteryAI()
        for i in range(25):
            ai.analyze_usage_pattern(make_status(50 - i // 5))
        ai.save_learning_data()

        # مثيل جديد يقرأ من نفس الملف المعزول
        ai2 = BatteryAI()
        assert len(ai2.usage_history) == 25

    def test_reset_clears_everything(self, ai):
        for i in range(60):
            ai.analyze_usage_pattern(make_status(80 - i // 5))
        ai.reset()
        assert len(ai.usage_history) == 0
        assert ai.learning_data.get('charge_cycle_count', 0) == 0
        assert not ai.prediction_accuracy

    def test_history_capped(self, ai):
        for i in range(HISTORY_LIMIT + 120):
            ai.analyze_usage_pattern({'percent': 50, 'is_charging': False,
                                      'power_draw': 5})
        assert len(ai.usage_history) <= HISTORY_LIMIT


class TestRateLearning:
    def _feed_series(self, ai, levels, charging_seq, power=12.0, step_min=2):
        """تغذية السلسلة عينة عينة عبر المسار الحقيقي لتحديث المعدلات"""
        end = datetime.now()
        with ai._lock:
            for i, (level, chg) in enumerate(zip(levels, charging_seq)):
                t = end - timedelta(minutes=(len(levels) - i) * step_min)
                entry = {
                    'timestamp': t.isoformat(),
                    'battery_percent': int(level),
                    'is_charging': chg,
                    'power_draw': 0.0 if chg else power,
                    'hour': t.hour,
                    'day_of_week': 0,
                    'is_weekend': False,
                }
                ai._update_ewma_rates(entry)
                ai.usage_history.append(entry)

    def test_drain_rate_learned_from_constant_discharge(self, ai):
        # تفريغ ثابت: 1% كل دقيقتين = 0.5 %/دقيقة
        n = 40
        levels = [90 - i for i in range(n)]
        self._feed_series(ai, levels, [False] * n)
        assert ai._ewma_drain_rate == pytest.approx(0.5, abs=0.15)

    def test_deep_analysis_computes_lifetime_stats(self, ai):
        n = 60
        levels = [88 - i for i in range(n)]
        self._feed_series(ai, levels, [False] * n)
        ai._analyze_advanced_rates()
        assert ai.learning_data.get('average_drain_rate', 0) > 0.3
        assert ai.learning_data.get('peak_drain_rate', 0) >= 0.5

    def test_charge_rate_positive_only_when_charging(self, ai):
        n = 20
        levels = [30 + i for i in range(n)]
        self._feed_series(ai, levels, [True] * n, power=0.0)
        assert ai._ewma_charge_rate == pytest.approx(0.5, abs=0.15)
        assert ai._ewma_drain_rate == 0


class TestPrediction:
    def _seed_linear_discharge(self, ai, rate_pct_per_min=1.0, samples=70):
        """
        زرع تاريخ تفريغ خطي ينتهي الآن:
        المستوى ينخفض بمعدل ثابت مع تقدم الزمن (L0 - rate*i).
        """
        end = datetime.now()
        start_level = 90.0
        hist = []
        for i in range(samples):
            t = end - timedelta(minutes=samples - i)
            level = start_level - rate_pct_per_min * i
            hist.append({
                'timestamp': t.isoformat(),
                'battery_percent': int(round(level)),
                'is_charging': False,
                'power_draw': 15.0,
                'hour': t.hour,
                'day_of_week': 0,
                'is_weekend': False,
            })
        with ai._lock:
            ai.usage_history.extend(hist)

    def test_predict_returns_string_with_data(self, ai):
        self._seed_linear_discharge(ai)
        result = ai.predict_time_remaining(60, is_charging=False)
        assert isinstance(result, str)
        assert 'جارٍ' not in result

    def test_predict_collecting_with_no_data(self, ai):
        assert 'جمع' in ai.predict_time_remaining(50, False)

    def test_regression_tracks_true_rate(self, ai):
        """معدل حقيقي 1%/د → التوقع حتى 20% من 60% ≈ 40 دقيقة"""
        self._seed_linear_discharge(ai, rate_pct_per_min=1.0)
        minutes = ai._regression_minutes(60, 20, charging=False)
        assert minutes is not None
        assert 30 <= minutes <= 55

    def test_charging_at_target_returns_optimal(self, ai):
        self._seed_linear_discharge(ai)
        assert 'أمثل' in ai.predict_time_remaining(85, is_charging=True)


def advice_ids(items):
    return [item.id for item in items]


class TestStructuredAdvice:
    """النصائح المهيكلة: كل نصيحة بمعرّف وشدّة وسند"""

    def test_full_charge_dwell_reported_at_high_soc(self, ai):
        ids = advice_ids(ai.get_advice(make_status(97, charging=True)))
        assert 'full_charge_dwell' in ids

    def test_critical_battery_comes_first(self, ai):
        items = ai.get_advice(make_status(8, charging=False))
        assert items[0].id == 'critical_low'
        assert items[0].severity == 'critical'

    def test_unreporting_battery_suppresses_soc_advice(self, ai):
        """بطارية بصفر شحن وصفر جهد لا تُنتج تنبيهات مستوى شحن كاذبة"""
        status = make_status(0, charging=True)
        status['reporting'] = False
        items = ai.get_advice(status)
        assert advice_ids(items) == ['battery_not_reporting']

    def test_night_usage_requires_learned_pattern(self, ai):
        import battery_ai as bai

        real_datetime = bai.datetime

        class NightDT(real_datetime):
            @classmethod
            def now(cls):
                return real_datetime.now().replace(hour=23)

        bai.datetime = NightDT
        try:
            ai.learning_data['user_behavior_fingerprint'] = {'night_owl_score': 0}
            assert 'night_usage' not in advice_ids(ai.get_advice(make_status(45)))

            ai.learning_data['user_behavior_fingerprint'] = {'night_owl_score': 80}
            assert 'night_usage' in advice_ids(ai.get_advice(make_status(45)))
        finally:
            bai.datetime = real_datetime

    def test_every_advice_carries_evidence(self, ai):
        for percent, charging in ((5, False), (45, False), (97, True), (82, True)):
            for item in ai.get_advice(make_status(percent, charging)):
                assert item.evidence, f"نصيحة بلا سند: {item.id}"

    def test_advice_ids_persisted(self, ai):
        ai.get_advice(make_status(50))
        assert isinstance(ai.learning_data.get('recommendations'), list)

    def test_legacy_string_api_still_renders(self, ai):
        texts = ai.get_smart_recommendations(50, is_charging=False)
        assert texts and all(isinstance(text, str) and text for text in texts)


class TestUsageProfileAndWear:
    """ملف الاستخدام المرصود وتقدير التآكل"""

    def _seed(self, ai, series, step_min=5):
        """series: [(percent, charging)] بفواصل زمنية منتظمة تنتهي الآن"""
        end = datetime.now()
        with ai._lock:
            for index, (percent, charging) in enumerate(series):
                stamp = end - timedelta(minutes=(len(series) - index) * step_min)
                ai.usage_history.append({
                    'timestamp': stamp.isoformat(),
                    'battery_percent': int(percent),
                    'is_charging': bool(charging),
                    'power_draw': 0.0 if charging else 9.0,
                    'hour': stamp.hour,
                    'day_of_week': 0,
                    'is_weekend': False,
                })

    def test_high_soc_time_counted_above_ceiling(self, ai):
        self._seed(ai, [(95, True)] * 13)          # 12 فاصل × 5 دقائق = ساعة
        profile = ai.usage_profile(ceiling=80)
        assert profile['minutes_high_soc'] == pytest.approx(60, abs=6)
        assert profile['minutes_plugged'] == pytest.approx(60, abs=6)

    def test_long_gap_not_counted_as_dwell(self, ai):
        """فجوة نوم طويلة لا تُحسب زمن بقاء عند مستوى شحن"""
        now = datetime.now()
        with ai._lock:
            ai.usage_history.extend([
                {'timestamp': (now - timedelta(hours=9)).isoformat(),
                 'battery_percent': 100, 'is_charging': True, 'power_draw': 0.0,
                 'hour': 0, 'day_of_week': 0, 'is_weekend': False},
                {'timestamp': now.isoformat(),
                 'battery_percent': 100, 'is_charging': True, 'power_draw': 0.0,
                 'hour': 9, 'day_of_week': 0, 'is_weekend': False},
            ])
        assert ai.usage_profile(ceiling=80)['minutes_high_soc'] == 0

    def test_discharge_depth_detected(self, ai):
        self._seed(ai, [(90 - i * 5, False) for i in range(9)] + [(50, True)])
        events = ai.usage_profile()['discharge_events']
        assert events and max(events) >= 30

    def test_wear_projection_shape(self, ai):
        self._seed(ai, [(100, True)] * 20)
        projection = ai.wear_projection(ceiling=80, temp_c=25, soh_percent=90)
        assert projection['total'] >= projection['calendar'] > 0
        assert projection['days_to_eol'] is not None
        assert projection['hours_high_soc_per_day'] > 0

    def test_wear_projection_without_health_has_no_eol(self, ai):
        self._seed(ai, [(70, False)] * 10)
        assert ai.wear_projection(soh_percent=None)['days_to_eol'] is None


class TestCycleAnalysis:
    def test_charge_cycles_counted(self, ai):
        now = datetime.now()
        pattern = []
        # جلسة شحن واحدة كاملة: تفريغ ثم شحن ثم تفريغ
        seq = [False] * 20 + [True] * 30 + [False] * 20
        for i, charging in enumerate(seq):
            t = now - timedelta(minutes=len(seq) * 2) + timedelta(minutes=i * 2)
            if charging:
                level = 40 + min(40, (i - 20))
            else:
                level = 80 - min(40, i) if i < 20 else max(41, 80 - (i - 50) * 1)
            pattern.append({
                'timestamp': t.isoformat(),
                'battery_percent': int(level),
                'is_charging': charging,
                'power_draw': 8.0 if not charging else 0.0,
                'hour': t.hour,
                'day_of_week': 0,
                'is_weekend': False,
            })
        ai.usage_history.extend(pattern)
        ai._analyze_charge_cycles()
        assert ai.learning_data['charge_cycle_count'] == 1
        # جلسة الشحن تبدأ عند 40 وتنتهي عند 40+29=69
        assert ai.learning_data['avg_charge_gain'] == 29


class TestConfidence:
    def test_confidence_bounded(self, ai):
        c = ai._calculate_confidence()
        assert 5 <= c <= 99

    def test_confidence_grows_with_data(self, ai):
        c_small = ai._calculate_confidence()
        for i in range(400):
            ai.analyze_usage_pattern(make_status(50, power=6.0))
        c_big = ai._calculate_confidence()
        assert c_big >= c_small

    def test_prediction_confidence_default(self, ai):
        assert ai._get_prediction_confidence() == 55


class TestAnomalyDetector:
    def test_add_and_recent(self):
        det = AnomalyDetector(max_anomalies=3)
        for i in range(5):
            det.add_anomaly({'type': 'x', 'i': i})
        recent = det.get_recent_anomalies(2)
        assert len(recent) == 2
        assert recent[-1]['i'] == 4
        assert len(det.anomalies) == 3  # السعة محدودة


class TestHardwareHealthBlend:
    def test_hardware_health_updates_score(self, ai):
        for i in range(200):
            ai.analyze_usage_pattern(make_status(60, power=6.0))
        score_before = ai.learning_data.get('health_score')
        ai.update_hardware_health(70)
        ai._calculate_health_efficiency_scores()
        score_after = ai.learning_data.get('health_score')
        # صحة العتاد المنخفضة تسحب الدرجة نحو الأسفل
        assert score_after <= score_before
