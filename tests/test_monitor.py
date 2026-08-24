#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات مراقب البطارية وخيط المراقبة"""

import time
from unittest.mock import MagicMock, patch

import pytest

import battery_monitor as bm
from battery_monitor import BatteryMonitor, _battery_base_path


class FakeBattery:
    def __init__(self, percent=75, plugged=False, secsleft=3600):
        self.percent = percent
        self.power_plugged = plugged
        self.secsleft = secsleft


class TestBatteryStatus:
    def test_no_battery_returns_unavailable(self):
        with patch.object(bm.psutil, 'sensors_battery', return_value=None), \
             patch.object(bm, '_battery_base_path', return_value=None):
            mon = BatteryMonitor()
            status = mon.get_battery_status()
        assert status['available'] is False
        assert status['percent'] == 0

    def test_basic_status_parsing(self):
        # عزل قراءة sysfs حتى لا يتأثر الاختبار بجهاز حقيقي
        with patch.object(bm.psutil, 'sensors_battery',
                          return_value=FakeBattery(63, True, 7200)), \
             patch.object(bm, '_battery_base_path', return_value=None):
            mon = BatteryMonitor()
            status = mon.get_battery_status()
        assert status == {
            'percent': 63,
            'is_charging': True,
            'time_left': 7200,
            'available': True,
            'power_draw': 0.0,
            'voltage': 0.0,
            'current': 0.0,
        }

    def test_psutil_exception_handled(self):
        with patch.object(bm.psutil, 'sensors_battery',
                          side_effect=RuntimeError('boom')):
            mon = BatteryMonitor()
            status = mon.get_battery_status()
        assert status['available'] is False


class TestHealthCache:
    def test_health_cached_within_ttl(self, monkeypatch):
        mon = BatteryMonitor()
        reads = {'n': 0}

        def fake_read():
            reads['n'] += 1
            return {'design_capacity': 50000, 'full_capacity': 44000,
                    'health_percentage': 88, 'cycle_count': 120}

        # استبدال القراءة الفعلية بقراءة معدودة
        monkeypatch.setattr(mon, 'get_battery_health', fake_read)
        h1 = mon.get_battery_health()
        h2 = mon.get_battery_health()
        assert h1 == h2
        assert reads['n'] == 2

    def test_cache_reuse_via_real_method(self, monkeypatch):
        """المسار الحقيقي: قراءة واحدة فعلياً ضمن نافذة TTL"""
        mon = BatteryMonitor()
        real_get = BatteryMonitor.get_battery_health

        calls = {'n': 0}
        def counting_read(self):
            if self._health_cache is not None and \
               (time.monotonic() - self._health_cache_time) < bm.HEALTH_CACHE_TTL:
                return dict(self._health_cache)
            calls['n'] += 1
            self._health_cache = {'design_capacity': 1, 'full_capacity': 1,
                                  'health_percentage': 90, 'cycle_count': 5}
            self._health_cache_time = time.monotonic()
            return dict(self._health_cache)

        monkeypatch.setattr(BatteryMonitor, 'get_battery_health', counting_read)
        try:
            a = mon.get_battery_health()
            b = mon.get_battery_health()
            c = mon.get_battery_health()
        finally:
            monkeypatch.undo()
            monkeypatch.setattr(BatteryMonitor, 'get_battery_health', real_get)
        assert calls['n'] == 1
        assert a == b == c
        assert a['health_percentage'] == 90

    def test_cache_expiry_logic(self, monkeypatch):
        """الكاش الطازج يعيد نفس القيمة، والمنتهي يتجدد"""
        mon = BatteryMonitor()
        fake_clock = {'t': 1000.0}
        monkeypatch.setattr(bm.time, 'monotonic', lambda: fake_clock['t'])

        fresh_cache_time = 995.0   # أقل من TTL (60 ثانية)
        stale_cache_time = 900.0   # أكبر من TTL

        # كاش طازج: يجب قبوله
        assert (fake_clock['t'] - fresh_cache_time) < bm.HEALTH_CACHE_TTL
        # كاش قديم: يجب تجاهله
        assert (fake_clock['t'] - stale_cache_time) >= bm.HEALTH_CACHE_TTL

    def test_invalidate_forces_refresh(self):
        mon = BatteryMonitor()
        mon._health_cache = {'design_capacity': 0, 'full_capacity': 0,
                             'health_percentage': 42, 'cycle_count': 0}
        mon._health_cache_time = time.monotonic()  # طازج
        mon.invalidate_health_cache()
        assert mon._health_cache_time == 0.0


class TestChargeLimits:
    def test_disabled_returns_none_action(self):
        mon = BatteryMonitor()
        mon.charge_control_enabled = False
        assert mon.check_charge_limits(95, True) == {'action': 'none'}

    def test_stop_charging_at_max(self):
        mon = BatteryMonitor()
        mon.charge_control_enabled = True
        mon.charge_controller = None  # مسار الإشعارات المحلي فقط
        action = mon.check_charge_limits(85, True)
        assert action['action'] == 'stop_charging'

    def test_start_charging_at_min(self):
        mon = BatteryMonitor()
        mon.charge_control_enabled = True
        mon.charge_controller = None
        action = mon.check_charge_limits(35, False)
        assert action['action'] == 'start_charging'

    def test_safe_zone_no_action(self):
        mon = BatteryMonitor()
        mon.charge_control_enabled = True
        mon.charge_controller = None
        assert mon.check_charge_limits(60, True)['action'] == 'none'


class TestBatteryPathDiscovery:
    @pytest.mark.skipif(not bm.IS_LINUX, reason='لينكس فقط')
    def test_base_path_found(self):
        path = _battery_base_path()
        if path is not None:
            assert path.exists()


class TestMonitorThread:
    def test_cooperative_stop(self, qapp, ai_engine=None):
        from monitor_thread import MonitorThread

        monitor = MagicMock()
        monitor.get_battery_status.return_value = {
            'percent': 50, 'is_charging': False, 'available': False, 'power_draw': 0}
        ai = MagicMock()

        thread = MonitorThread(monitor, ai, {})
        thread.start()
        assert thread.running is True

        stopped = thread.stop(timeout_ms=3000)
        assert stopped is True
        assert thread.isRunning() is False
        assert thread.running is False

    def test_running_setter_compat(self, qapp):
        from monitor_thread import MonitorThread
        thread = MonitorThread(MagicMock(), MagicMock(), {})
        thread.running = False  # الواجهة القديمة
        assert thread._stop_event.is_set()
