#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات مدير التشغيل التلقائي واختبار دخان للتطبيق الكامل"""

import pytest

from autostart_manager import AutostartManager


class TestLinuxAutostart:
    def test_desktop_entry_quotes_paths(self, isolated_data_dir, monkeypatch):
        """مسارات بفراغات/حروف عربية يجب اقتباسها في Exec"""
        if not __import__('sys').platform.startswith('linux'):
            pytest.skip('لينكس فقط')

        mgr = AutostartManager()
        # فرض وضع تطوير بمسار فيه فراغات
        monkeypatch.setattr(mgr, 'is_frozen', False)
        monkeypatch.setattr(mgr, 'python_path', '/home/user with space/py 3')
        monkeypatch.setattr(
            mgr, 'main_script',
            __import__('pathlib').Path('/mnt/sda2/مشروع عربي/main.py'))

        home = isolated_data_dir / 'home'
        autostart = home / '.config' / 'autostart'
        autostart.mkdir(parents=True)

        import default_settings  # noqa: F401 - تأكيد استيراد سليم
        real_home = __import__('pathlib').Path.home
        monkeypatch.setattr(__import__('pathlib').Path, 'home',
                            staticmethod(lambda: home))

        ok, msg = mgr._enable_linux()
        assert ok is True, msg

        desktop_file = autostart / 'batteryguard.desktop'
        content = desktop_file.read_text(encoding='utf-8')
        exec_line = [l for l in content.splitlines() if l.startswith('Exec=')][0]
        # المسارات المقتبسة
        assert '"--background"' not in exec_line
        assert exec_line.count('"') >= 4  # اقتباس بايثون + السكربت
        assert '--background' in exec_line
        assert 'X-GNOME-Autostart-enabled=true' in content

    def test_is_enabled_respects_disabled_flag(self, isolated_data_dir, monkeypatch):
        if not __import__('sys').platform.startswith('linux'):
            pytest.skip('لينكس فقط')

        home = isolated_data_dir / 'home'
        autostart = home / '.config' / 'autostart'
        autostart.mkdir(parents=True)
        monkeypatch.setattr(__import__('pathlib').Path, 'home',
                            staticmethod(lambda: home))

        mgr = AutostartManager()

        # لا يوجد ملف
        assert mgr.is_enabled() is False

        # ملف مفعل
        desktop_file = autostart / 'batteryguard.desktop'
        desktop_file.write_text('[Desktop Entry]\nX-GNOME-Autostart-enabled=true\n',
                                encoding='utf-8')
        assert mgr.is_enabled() is True

        # ملف معطل داخلياً
        desktop_file.write_text('[Desktop Entry]\nX-GNOME-Autostart-enabled=false\n',
                                encoding='utf-8')
        assert mgr.is_enabled() is False


@pytest.mark.gui
class TestAppSmoke:
    """اختبار دخان: إنشاء النافذة الرئيسية كاملة وتنظيفها"""

    def test_modern_ui_lifecycle(self, qapp, isolated_data_dir, clean_qsettings):
        from main_window import ModernUI
        window = ModernUI()
        try:
            assert window.tabs.count() == 4  # الحالة/الإعدادات/AI/الإحصائيات
            assert window.monitor_thread is not None
            assert window.ai is not None
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
