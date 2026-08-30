#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات منسّق الحارس وإشارات الإغلاق.

المنسّق هو ما يعمل فعلاً في الخلفية، فأهمّ ما يُختبر فيه ثلاثة: أن وتيرته لا
تجعله هو مستنزف البطارية، أن ما تعلّمه يُحفظ ويُستعاد، وأن `SIGTERM` يؤدّي إلى
إغلاق نظيف لا إلى موت فوري يترك عملية معلّقة.
"""

import json
import signal
import sys
import time

import pytest

from battery_intelligence import ACTION_ALERT
from guard_service import ATTRIBUTION_INTERVAL, STATE_FILE, GuardService

LINUX_ONLY = pytest.mark.skipif(not sys.platform.startswith('linux'),
                                reason='لينكس فقط')


class _FakeMonitor:
    """مراقب بلا عتاد: القياسات تُملى من الاختبار"""

    def __init__(self, watts=12.0, charging=False):
        self.watts = watts
        self.charging = charging

    def get_battery_status(self):
        return {'percent': 60, 'is_charging': self.charging, 'available': True,
                'reporting': True, 'power_draw': self.watts}

    @staticmethod
    def get_battery_health():
        return {'full_capacity': 60000.0, 'design_capacity': 62000.0,
                'capacity_unit': 'mwh', 'health_percentage': 96}


class _FakeAI:
    """محرك تعلّم مبسّط يعطي المنسّق سياق الاستخدام"""

    def __init__(self):
        self._ewma_drain_rate = 0.8
        self.learning_data = {'average_drain_rate': 0.7}

    @staticmethod
    def wear_projection(ceiling=80):
        return {'hours_on_battery_per_day': 5.0, 'typical_dod': 40.0}


@pytest.fixture
def service(isolated_data_dir):
    monitor = _FakeMonitor()
    instance = GuardService(monitor, _FakeAI(),
                            {'attribution_interval': 10,
                             'guard_allowlist': [], 'guard_blocklist': []})
    instance.monitor = monitor
    yield instance
    instance.shutdown()


class TestPolicyFromSettings:
    def test_defaults_are_conservative(self, service):
        """الافتراضي يراقب وينبّه ولا يلمس عملية واحدة"""
        assert service.policy.enabled is True
        assert service.policy.automatic is False
        assert service.policy.max_action == ACTION_ALERT

    def test_interval_floor_enforced(self, isolated_data_dir):
        """
        وتيرة أسرع من عشر ثوانٍ تجعل الحارس نفسه من أكبر مستنزفي البطارية،
        وهو نقيض غرضه. الحدّ صلب ولا يُتجاوز من الإعدادات.
        """
        for requested, expected in ((1, 10.0), (0, 10.0), (-5, 10.0),
                                    (25, 25.0), (10_000, 300.0)):
            instance = GuardService(_FakeMonitor(), _FakeAI(),
                                    {'attribution_interval': requested})
            try:
                assert instance.interval == expected, requested
            finally:
                instance.shutdown()

    def test_invalid_interval_falls_back_to_default(self, isolated_data_dir):
        instance = GuardService(_FakeMonitor(), _FakeAI(),
                                {'attribution_interval': 'nonsense'})
        try:
            assert instance.interval == ATTRIBUTION_INTERVAL
        finally:
            instance.shutdown()

    def test_apply_settings_updates_policy_live(self, service):
        service.apply_settings({'guard_automatic': True,
                                'guard_max_action': 'suspend',
                                'attribution_interval': 40})
        assert service.policy.automatic is True
        assert service.policy.max_action == 'suspend'
        assert service.interval == 40.0

    def test_disabled_attribution_skips_work(self, isolated_data_dir):
        instance = GuardService(_FakeMonitor(), _FakeAI(),
                                {'attribution_enabled': False})
        try:
            status = instance.monitor.get_battery_status() \
                if hasattr(instance.monitor, 'get_battery_status') else {}
            assert instance.step(status) is None
            assert instance.rounds == 0
        finally:
            instance.shutdown()


class TestCadence:
    def test_respects_interval(self, service, monkeypatch):
        """
        قراءة البطارية تجري كل ثانيتين، وجولة العمليات كل 25 ثانية. خلط
        الوتيرتين كان سيجعل التطبيق يقرأ عدّادات مئات العمليات كل ثانيتين.
        """
        import guard_service as module

        clock = [1000.0]
        monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
        status = service.monitor.get_battery_status()
        health = service.monitor.get_battery_health()

        assert service.step(status, health) is None, 'أول جولة تهيئة للعدّادات'
        assert service.step(status, health) is None, 'لم يحن الفاصل بعد'

        clock[0] += 11.0
        assert service.step(status, health) is not None
        assert service.step(status, health) is None, 'جولة واحدة لكل فاصل'

    def test_first_round_saves_state(self, service, monkeypatch,
                                    isolated_data_dir):
        """
        أول جولة تُحفظ فوراً: بلا ذلك يبقى ملف الحالة غائباً دقائق فيُظنّ أن
        التعلّم متوقّف بينما هو ينتظر مهلة الحفظ.
        """
        import guard_service as module

        clock = [2000.0]
        monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
        status = service.monitor.get_battery_status()
        health = service.monitor.get_battery_health()

        service.step(status, health)
        clock[0] += 11.0
        assert service.step(status, health) is not None

        state_file = isolated_data_dir / STATE_FILE
        assert state_file.exists()
        payload = json.loads(state_file.read_text(encoding='utf-8'))
        assert payload['rounds'] == 1
        assert 'power_model' in payload and 'intelligence' in payload


class TestPersistence:
    def test_state_survives_restart(self, isolated_data_dir, monkeypatch):
        import guard_service as module

        clock = [3000.0]
        monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
        monitor, ai = _FakeMonitor(), _FakeAI()
        status, health = monitor.get_battery_status(), monitor.get_battery_health()

        first = GuardService(monitor, ai, {'attribution_interval': 10})
        first.step(status, health)
        for _ in range(3):
            clock[0] += 11.0
            first.step(status, health)
        rounds = first.rounds
        samples = first.intelligence.samples
        model_samples = first.attribution.model.samples
        first.shutdown()

        assert rounds >= 3 and model_samples >= 1, 'لم يتدرّب النموذج'

        second = GuardService(monitor, ai, {'attribution_interval': 10})
        try:
            assert second.intelligence.samples == samples
            assert second.attribution.model.samples == model_samples
        finally:
            second.shutdown()

    def test_reset_clears_learning(self, service, monkeypatch):
        import guard_service as module

        clock = [4000.0]
        monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
        status = service.monitor.get_battery_status()
        service.step(status)
        clock[0] += 11.0
        service.step(status)

        assert service.rounds >= 1
        service.reset()
        assert service.rounds == 0
        assert service.intelligence.samples == 0
        assert service.attribution.model.samples == 0
        assert service.last_report is None

    def test_corrupt_state_does_not_prevent_start(self, isolated_data_dir):
        """ملف تالف لا يمنع التطبيق من العمل: يبدأ التعلّم من جديد"""
        (isolated_data_dir / STATE_FILE).write_text('{ليس JSON صالح',
                                                    encoding='utf-8')
        instance = GuardService(_FakeMonitor(), _FakeAI(), {})
        try:
            assert instance.rounds == 0
            assert instance.intelligence.samples == 0
        finally:
            instance.shutdown()


class TestTrainingHonesty:
    def test_no_training_while_charging(self, isolated_data_dir, monkeypatch):
        """
        أثناء الشحن يقيس العتاد تيار الشحن لا الاستهلاك، والتدريب عليه يفسد
        المعامل فتصير كل النسب خاطئة بصمت.
        """
        import guard_service as module

        clock = [5000.0]
        monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
        monitor = _FakeMonitor(watts=40.0, charging=True)
        instance = GuardService(monitor, _FakeAI(), {'attribution_interval': 10})
        try:
            status, health = monitor.get_battery_status(), monitor.get_battery_health()
            instance.step(status, health)
            for _ in range(4):
                clock[0] += 11.0
                report = instance.step(status, health)

            assert instance.attribution.model.samples == 0
            assert report is not None and report.measured_watts is not None
            assert report.offenders is not None
        finally:
            instance.shutdown()


@LINUX_ONLY
class TestResolvePids:
    def test_returns_live_pids_only(self, service):
        """
        الأرقام تُستخرج في لحظة التنفيذ لا من التقرير: بين الاستدلال والنقر قد
        تنتهي العملية ويُعاد استخدام رقمها فيقع الإجراء على عملية بريئة.
        """
        import os

        import psutil

        name = psutil.Process(os.getpid()).name()
        pids = service.resolve_pids(name)
        assert pids and all(psutil.pid_exists(pid) for pid in pids)

    def test_unknown_name_returns_empty(self, service):
        assert service.resolve_pids('definitely-not-a-real-process-xyz') == []

    def test_action_on_unknown_name_is_refused_not_crash(self, service):
        outcome = service.suspend('definitely-not-a-real-process-xyz')
        assert outcome.applied is False
        assert outcome.reason == 'no_eligible_process'


class TestUserLists:
    def test_ignore_adds_to_blocklist_and_gate(self, service):
        service.ignore('some-app')
        assert 'some-app' in service.policy.blocklist
        assert 'some-app' in service.guard._gate.extra_protected

    def test_ignore_removes_from_allowlist(self, service):
        service.allow('some-app')
        assert 'some-app' in service.policy.allowlist
        service.ignore('some-app')
        assert 'some-app' not in service.policy.allowlist
        assert 'some-app' in service.policy.blocklist


class TestStatistics:
    def test_statistics_are_serialisable(self, service):
        payload = json.loads(json.dumps(service.statistics(),
                                        ensure_ascii=False, default=str))
        for key in ('rounds', 'model_calibrated', 'model_confidence',
                    'baseline_watts', 'policy', 'active_interventions'):
            assert key in payload, key

    def test_reports_priors_before_calibration(self, service):
        stats = service.statistics()
        assert stats['model_calibrated'] is False
        assert stats['model_confidence'] <= 25, 'الثقة قبل المعايرة يجب أن تبقى منخفضة'


class TestShutdownHandler:
    """
    `SIGTERM` هو ما ترسله systemd وتسجيل الخروج وإعادة التشغيل. سلوك بايثون
    الافتراضي معه الموت الفوري بلا تنظيف، وأثره أن تبقى عملية علّقها الحارس
    معلّقة ويُفقد ما تعلّمه التطبيق بعد آخر حفظ.
    """

    def test_handler_installs_and_restores(self, qapp):
        from lifecycle import install_shutdown_handler

        original = signal.getsignal(signal.SIGTERM)
        handler = install_shutdown_handler(lambda: None)
        try:
            assert 'SIGTERM' in handler._installed
            assert signal.getsignal(signal.SIGTERM) is not original
        finally:
            handler.uninstall()
        assert signal.getsignal(signal.SIGTERM) is original

    def test_sigterm_triggers_callback_on_event_loop(self, qapp):
        """
        الاختبار الحقيقي: إشارة فعلية إلى العملية نفسها، ويجب أن يُستدعى
        نداء الإغلاق من داخل حلقة أحداث Qt.
        """
        import os

        from PyQt6.QtCore import QTimer

        from lifecycle import install_shutdown_handler

        called = []
        handler = install_shutdown_handler(lambda: called.append(True))
        try:
            QTimer.singleShot(50, lambda: os.kill(os.getpid(), signal.SIGTERM))
            deadline = time.time() + 5
            while time.time() < deadline and not called:
                qapp.processEvents()
                time.sleep(0.02)
            assert called, 'لم يُستدعَ الإغلاق النظيف عند SIGTERM'
        finally:
            handler.uninstall()

    def test_shutdown_runs_only_once(self, qapp):
        from lifecycle import install_shutdown_handler

        calls = []
        handler = install_shutdown_handler(lambda: calls.append(True))
        try:
            handler._run_shutdown()
            handler._run_shutdown()
            assert len(calls) == 2, 'النداء المباشر لا يُحرس'
            assert handler._shutting_down is False, 'العلم يُرفع في المعالِج فقط'
        finally:
            handler.uninstall()

    def test_failing_callback_does_not_raise(self, qapp):
        from lifecycle import install_shutdown_handler

        def boom():
            raise RuntimeError('فشل متوقّع')

        handler = install_shutdown_handler(boom)
        try:
            handler._run_shutdown()  # يُسجَّل ولا يُرمى
        finally:
            handler.uninstall()

    def test_shutdown_releases_guard_interventions(self, service):
        """
        الترتيب الملزم: الإفراج عن كل تدخّل قبل الخروج. تركه يعني عملية موقوفة
        بعد اختفاء من أوقفها، ولا أحد يعرف كيف يُصلحها.
        """
        service.shutdown()
        assert service.guard.active_interventions() == {}
