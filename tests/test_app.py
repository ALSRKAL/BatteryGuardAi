#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات مدير التشغيل التلقائي واختبار دخان للتطبيق الكامل"""

import sys

import pytest

import service_installer
from autostart_manager import AutostartManager

LINUX_ONLY = pytest.mark.skipif(not sys.platform.startswith('linux'),
                                reason='لينكس فقط')


@LINUX_ONLY
class TestLinuxAutostart:
    """
    `AutostartManager` صار غلافاً فوق `service_installer`، فالمُختبَر هنا هو
    التفويض الصحيح لا كتابة الملف: كتابة الملف تُختبر في `test_service.py`.
    """

    def test_enable_delegates_to_installer(self, isolated_xdg_config, monkeypatch):
        """التفعيل يستخدم أفضل طريقة متوفّرة ويُبلّغ عنها"""
        recorded = {}

        def fake_install(prefer_systemd=True, start_now=True):
            recorded['prefer_systemd'] = prefer_systemd
            recorded['start_now'] = start_now
            return service_installer.InstallResult(
                True, service_installer.METHOD_SYSTEMD, '/tmp/unit',
                follow_up=['sudo loginctl enable-linger user'])

        monkeypatch.setattr(service_installer, 'install', fake_install)
        ok, message = AutostartManager().enable()

        assert ok is True
        # التفعيل من الإعدادات لا يبدأ الخدمة فوراً: المستخدم يضبط ثم يحفظ
        assert recorded == {'prefer_systemd': True, 'start_now': False}
        assert 'linger' in message

    def test_enable_reports_failure_honestly(self, isolated_xdg_config, monkeypatch):
        """الفشل يُنقل بسببه، لا يُبلَع فيظنّ المستخدم أنه نجح"""
        monkeypatch.setattr(
            service_installer, 'install',
            lambda **kwargs: service_installer.InstallResult(
                False, service_installer.METHOD_SYSTEMD,
                error='تعذّرت كتابة ملف الوحدة'))
        ok, message = AutostartManager().enable()
        assert ok is False
        assert 'الوحدة' in message

    def test_disable_removes_every_method(self, isolated_xdg_config, monkeypatch):
        """الإلغاء يُزيل كل صور التشغيل الدائم لا واحدة منها"""
        called = []
        monkeypatch.setattr(
            service_installer, 'uninstall',
            lambda: (called.append(True) or
                     service_installer.InstallResult(True,
                                                     service_installer.METHOD_NONE)))
        ok, _ = AutostartManager().disable()
        assert ok is True and called == [True]

    def test_is_enabled_reads_real_state(self, isolated_xdg_config, monkeypatch):
        """`is_enabled` يقرأ الحالة الفعلية من المثبّت"""
        mgr = AutostartManager()

        monkeypatch.setattr(service_installer, 'status',
                            lambda: service_installer.ServiceStatus())
        assert mgr.is_enabled() is False

        monkeypatch.setattr(
            service_installer, 'status',
            lambda: service_installer.ServiceStatus(
                method=service_installer.METHOD_SYSTEMD,
                installed=True, enabled=True))
        assert mgr.is_enabled() is True
        assert mgr.active_method() == service_installer.METHOD_SYSTEMD

        # مثبّت لكن غير مفعّل: ليس تشغيلاً تلقائياً
        monkeypatch.setattr(
            service_installer, 'status',
            lambda: service_installer.ServiceStatus(
                method=service_installer.METHOD_SYSTEMD,
                installed=True, enabled=False))
        assert mgr.is_enabled() is False

    def test_is_enabled_survives_installer_error(self, isolated_xdg_config,
                                                 monkeypatch):
        """خطأ في قراءة الحالة لا ينهار به مربّع اختيار في الإعدادات"""
        def boom():
            raise OSError('لا مدير مستخدم')

        monkeypatch.setattr(service_installer, 'status', boom)
        assert AutostartManager().is_enabled() is False
        assert AutostartManager().active_method() == 'none'


@pytest.mark.gui
class TestAppSmoke:
    """اختبار دخان: إنشاء النافذة الرئيسية كاملة وتنظيفها"""

    def test_modern_ui_lifecycle(self, qapp, isolated_data_dir, clean_qsettings):
        from i18n import t
        from main_window import ModernUI
        window = ModernUI()
        try:
            # خمسة مجالات مستقلة: الحالة، التحكم، التحليل، السجل، الإعدادات
            expected = [t('tab.status'), t('tab.control'), t('tab.intelligence'),
                        t('diag.title'), t('tab.record'), t('tab.settings')]
            assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == expected
            assert window.monitor_thread is not None
            assert window.ai is not None
            # كل مجال يجب أن يكون قد أنشأ عناصره الأساسية
            assert window.state_plate is not None
            assert window.charge_window_jaw is not None
            assert window.capability_strip is not None
            assert window.diagnostics_panel is not None
        finally:
            window.ai_timer.stop()
            window.auto_save_timer.stop()
            window.uptime_timer.stop()
            window.auto_optimizer.auto_optimize_enabled = False
            window.auto_optimizer.stop()
            window.notification_manager.stop_all_reminders()
            if window.monitor_thread.isRunning():
                window.monitor_thread.stop(timeout_ms=4000)
            window.tray.hide()

    def test_settings_roundtrip_flat_keys(self, qapp, isolated_data_dir, clean_qsettings):
        """
        إصلاح خطأ تاريخي: الحفظ كان يكتب قواميس متداخلة بينما القراءة
        تبحث عن مفاتيح فردية - يجب أن تتطابق الآن.
        """
        from main_window import ModernUI
        window = ModernUI()
        try:
            # ضبط قيم معروفة ضمن مدى العناصر (low: 15-30، optimal_min: 30-50)
            window.low_battery_spin.setValue(25)
            window.optimal_min_spin.setValue(44)
            window.save_all_settings()

            settings = window.settings
            assert settings.value('low_battery_threshold', type=int) == 25
            assert settings.value('optimal_min_threshold', type=int) == 44

            # تغيير القيم ثم إعادة تحميلها من QSettings
            window.low_battery_spin.setValue(20)
            window.optimal_min_spin.setValue(40)
            window.load_settings()
            assert window.low_battery_spin.value() == 25
            assert window.optimal_min_spin.value() == 44
        finally:
            window.ai_timer.stop()
            window.auto_save_timer.stop()
            window.uptime_timer.stop()
            window.auto_optimizer.auto_optimize_enabled = False
            window.auto_optimizer.stop()
            window.notification_manager.stop_all_reminders()
            if window.monitor_thread.isRunning():
                window.monitor_thread.stop(timeout_ms=4000)
            window.tray.hide()
