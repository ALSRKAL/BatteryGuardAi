#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات محرك الذكاء الاصطناعي"""

import statistics
from datetime import datetime, timedelta

import pytest

from battery_ai import HISTORY_LIMIT, AnomalyDetector, BatteryAI


def make_status(percent, charging=False, power=10.0):
    return {
        'percent': percent,
        'is_charging': charging,
        'power_draw': power,
        'voltage': 11.4,
        'current': 1.0,
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


class TestRecommendationBugFixes:
    """اختبارات مخصصة للأخطاء التي أُصلحت"""

    def test_overcharge_warning_fires_before_85(self, ai):
        """كان فرع >95 لا يُصل أبداً لأن >85 يسبقه"""
        recs = ai.get_smart_recommendations(97, is_charging=True)
        assert any('زائد' in r or 'افصل' in r for r in recs)

    def test_critical_battery_short_circuits(self, ai):
        recs = ai.get_smart_recommendations(8, is_charging=False)
        assert len(recs) == 1
        assert '10%' in recs[0]

    def test_night_owl_requires_both_conditions(self, ai):
        """
        كان الشرط `a and h>=22 or h<=6` يعمل ليلاً دائماً حتى بدون نمط ليلي.
        بعد الإصلاح: توصية الليل تتطلب night_owl_score>50.
        """
        ai.learning_data['user_behavior_fingerprint'] = {'night_owl_score': 0}
        recs_morning = [r for r in ai.get_smart_recommendations(45, False)]
        # صباحاً (الساعة الحالية في بيئة الاختبار غير معروفة) - نتحقق فقط من عدم الانهيار
        assert isinstance(recs_morning, list)

        # محاكاة ليل مع بصمة ضعيفة: لا يجب أن تظهر توصية "ليلي متوقع"
        import battery_ai as bai
        orig_hour = datetime.now().hour
        fake_night = bai.datetime
        class FakeDT(fake_night):
            @classmethod
            def now(cls):
                real = fake_night.now()
                return real.replace(hour=23)
        bai.datetime = FakeDT
        try:
            recs_weak = ai.get_smart_recommendations(45, False)
            assert not any('ليلي متوقع' in r for r in recs_weak)

            # بصمة قوية ليلياً: يجب أن تظهر التوصية
            ai.learning_data['user_behavior_fingerprint'] = {'night_owl_score': 80}
            recs_strong = ai.get_smart_recommendations(45, False)
            assert any('ليلي متوقع' in r for r in recs_strong)
        finally:
            bai.datetime = fake_night
            assert datetime.now().hour >= 0  # استعادة ضمنية

    def test_recommendations_persisted(self, ai):
        ai.get_smart_recommendations(50, False)
        assert 'recommendations' in ai.learning_data


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
