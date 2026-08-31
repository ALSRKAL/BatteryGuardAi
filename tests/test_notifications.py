#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات منطق الإشعارات (بدون واجهة رسومية فعلية)"""

import time
from datetime import datetime

import pytest

from notification_manager import SmartNotificationManager


@pytest.fixture
def mgr(qapp):
    return SmartNotificationManager()


class TestCooldownLogic:
    def test_critical_always_passes(self, mgr):
        assert mgr._should_send_notification('battery_critical', 'critical') is True

    def test_cooldown_suppresses_repeats(self, mgr):
        # ساعات الهدوء تُعطَّل صراحةً: الاختبار عن التهدئة لا عن الوقت،
        # وكان يفشل عند تشغيله فعلياً بين الواحدة والسادسة صباحاً.
        mgr.smart_timing_enabled = False
        assert mgr._should_send_notification('type_a', 'normal') is True
        mgr.last_notification_time['type_a'] = time.time()
        assert mgr._should_send_notification('type_a', 'normal') is False
        # بعد انتهاء التهدئة يمر
        mgr.last_notification_time['type_a'] = time.time() - 400
        assert mgr._should_send_notification('type_a', 'normal') is True

    def test_quiet_hours_drop_normal(self, mgr, monkeypatch):
        class FakeDT(datetime):
            @classmethod
            def now(cls):
                real = super().now()
                return real.replace(hour=3)

        import notification_manager as nm
        monkeypatch.setattr(nm, 'datetime', FakeDT)
        assert mgr._should_send_notification('general', 'normal') is False
        # الحرجة تتجاوز ساعات الهدوء
        assert mgr._should_send_notification('critical', 'critical') is True


class TestSoundMapping:
    def test_sound_type_mapping(self, mgr):
        assert mgr._get_sound_type('critical', 'x') == 'critical'
        assert mgr._get_sound_type('high', 'warning') == 'warning'
        assert mgr._get_sound_type('normal', 'charge_complete') == 'success'
        assert mgr._get_sound_type('low', 'optimization') == 'optimization'
        assert mgr._get_sound_type('normal', 'anything') == 'info'

    def test_icon_mapping(self, mgr):
        assert mgr._get_icon_for_type('x', 'critical') == 'dialog-warning'
        assert mgr._get_icon_for_type('battery_low', 'normal') == 'battery-caution'


class TestThresholdAlerts:
    """
    المقارنة بمفتاح الترجمة لا بنصّ حرفي: الاختبار الذي يثبّت صياغة الرسالة
    يفشل عند أول تحسين لغوي ويُخفي الفشل الحقيقي (تنبيه لم يُرسَل أصلاً).
    """

    def test_critical_threshold_triggers(self, mgr, monkeypatch):
        from i18n import t
        sent = {}
        monkeypatch.setattr(mgr, 'send_notification',
                            lambda **kw: sent.setdefault('title', kw['title']) or True)
        monkeypatch.setattr(mgr, 'start_reminder', lambda *a, **k: None)
        result = mgr.send_battery_threshold_alert(5, False, 100)
        assert result is True
        assert sent['title'] == t('alert.critical_title')

    def test_low_threshold_triggers(self, mgr, monkeypatch):
        from i18n import t
        sent = {}
        monkeypatch.setattr(mgr, 'send_notification',
                            lambda **kw: sent.setdefault('title', kw['title']) or True)
        monkeypatch.setattr(mgr, 'start_reminder', lambda *a, **k: None)
        result = mgr.send_battery_threshold_alert(15, False, 100)
        assert result is True
        assert sent['title'] == t('alert.low_title')

    def test_full_charge_triggers(self, mgr, monkeypatch):
        from i18n import t
        sent = {}
        monkeypatch.setattr(mgr, 'send_notification',
                            lambda **kw: sent.setdefault('title', kw['title']) or True)
        monkeypatch.setattr(mgr, 'start_reminder', lambda *a, **k: None)
        result = mgr.send_battery_threshold_alert(96, True, 100)
        assert result is True
        assert sent['title'] == t('alert.full_title')

    def test_alert_texts_are_translated_not_hardcoded(self, mgr, monkeypatch):
        """
        كل عنوان ورسالة يجب أن يخرج من `i18n`: النص المكتوب داخل المنطق يبقى
        عربياً في الواجهة الإنجليزية.
        """
        from i18n import t
        captured = {}
        monkeypatch.setattr(mgr, 'send_notification',
                            lambda **kw: captured.update(kw) or True)
        monkeypatch.setattr(mgr, 'start_reminder', lambda *a, **k: None)
        mgr.send_battery_threshold_alert(5, False, 100)
        assert captured['message'] == t('alert.critical_body', percent=5)
        assert not captured['message'].startswith('alert.')

    def test_reminder_carries_a_live_readout(self, mgr, monkeypatch):
        """
        التذكير يحمل قراءة منفصلة عن نصّه، فتُعرض كرقم كبير ولا تُدفن في سطر.
        """
        captured = {}
        monkeypatch.setattr(mgr, 'send_notification', lambda **kw: True)
        monkeypatch.setattr(mgr, 'start_reminder',
                            lambda kind, cond, data, **k: captured.update(data))
        mgr.send_battery_threshold_alert(7, False, 100)
        assert captured['readout'] == '7%'

    def test_healthy_range_no_alert(self, mgr, monkeypatch):
        monkeypatch.setattr(mgr, 'send_notification', lambda **kw: True)
        # 50% على الشاحن داخل النطاق الأمثل لكن مع إيقاف التنبيه الذكي
        mgr.smart_alerts['optimal_charge_reminder'] = False
        assert mgr.send_battery_threshold_alert(50, True, 95) is False


class TestReminderState:
    def test_mute_stops_timer(self, qapp, mgr):
        fired = {'n': 0}

        def condition():
            return True

        data = {'title': 't', 'message': 'm', 'urgency': 'normal'}
        mgr.start_reminder('test_r', condition, data, interval=3600)
        assert 'test_r' in mgr._reminder_timers

        mgr.mute_reminder('test_r')
        assert 'test_r' not in mgr._reminder_timers
        assert 'test_r' in mgr.muted_reminders

    def test_stop_all_reminders(self, qapp, mgr):
        data = {'title': 't', 'message': 'm', 'urgency': 'normal'}
        cond = lambda: True  # noqa: E731
        for name in ('r1', 'r2'):
            mgr.start_reminder(name, cond, dict(data), interval=3600)
        mgr.stop_all_reminders()
        assert mgr._reminder_timers == {}

    def test_snooze_defers_tick(self, qapp, mgr, monkeypatch):
        """غفوة تمنع الإرسال حتى لو تحقق الشرط"""
        sent = []
        data = {'title': 't', 'message': 'm', 'urgency': 'normal',
                'play_sound': False}
        mgr.start_reminder('snooze_test', lambda: True, data,
                           interval=3600, interactive=False)
        monkeypatch.setattr(
            mgr, 'send_notification',
            lambda *a, **kw: sent.append(kw.get('notification_type')) or True)

        mgr.snoozed_reminders['snooze_test'] = time.time() + 9999
        mgr._reminder_tick('snooze_test')
        assert sent == []

    def test_condition_false_stops_reminder(self, qapp, mgr):
        data = {'title': 't', 'message': 'm', 'urgency': 'normal'}
        mgr.start_reminder('cond_test', lambda: False, data, interval=3600)
        # النبضة الأولى اكتشفت شرطاً خاطئاً وأوقفت التذكير
        assert 'cond_test' not in mgr._reminder_timers


class TestSettingsUpdates:
    def test_update_thresholds(self, mgr):
        mgr.update_battery_thresholds({'low': 25})
        assert mgr.battery_thresholds['low'] == 25

    def test_update_intervals_clamped(self, mgr):
        mgr.update_reminder_intervals({'battery_low': 0})
        assert mgr.reminder_intervals['battery_low'] >= 30

    def test_toggle_smart_alert_unknown_ignored(self, mgr):
        before = dict(mgr.smart_alerts)
        mgr.toggle_smart_alert('nonexistent', False)
        assert mgr.smart_alerts == before

    def test_set_sound_volume_clamped(self, mgr):
        mgr.set_sound_settings(True, volume=5.0)
        assert mgr.sound_volume == 1.0
        mgr.set_sound_settings(True, volume=-1)
        assert mgr.sound_volume == 0.0


class TestStats:
    def test_stats_shape(self, mgr):
        stats = mgr.get_advanced_statistics()
        for key in ('total_sent', 'total_suppressed', 'reminders_sent',
                    'active_reminders', 'battery_thresholds',
                    'smart_alerts_status'):
            assert key in stats
