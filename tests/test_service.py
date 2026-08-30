#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات التشغيل الدائم في الخلفية.

الاختبارات هنا تُثبِّت الأخطاء التي كانت تجعل الخدمة السابقة لا تعمل، حتى لا
تعود: مسار غير مقتبس، مفتاح في القسم الخطأ، منع الكتابة على مجلد المستخدم،
ومتغيّرات صدفة لا تُوسَّع. كلها أخطاء «تُثبَّت بنجاح» ثم تفشل بعد إعادة الإقلاع.

كل اختبار يكتب في `XDG_CONFIG_HOME` معزول: بلا ذلك تُثبّت الاختبارات خدمة
حقيقية للمستخدم لم يطلبها.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import service_installer as installer

LINUX_ONLY = pytest.mark.skipif(not sys.platform.startswith('linux'),
                                reason='لينكس فقط')
NEEDS_ANALYZE = pytest.mark.skipif(shutil.which('systemd-analyze') is None,
                                   reason='systemd-analyze غير متوفّر')

#: مسار فيه فراغات وحروف عربية، مثل مسار هذا المشروع نفسه
AWKWARD_DIR = '/mnt/sda2/اخر المشاريع بالموقع و فلاتر /BatteryGuardAI'

#: أوامر يُسمح بتشغيلها فعلاً: قراءة محضة لا تغيّر شيئاً في النظام
_READ_ONLY_COMMANDS = frozenset({'is-system-running', 'is-enabled', 'is-active',
                                 'show-user', 'verify', 'show'})


@pytest.fixture(autouse=True)
def no_real_systemctl(monkeypatch):
    """
    منع الاختبارات من لمس مدير systemd الحقيقي.

    هذا ليس تحسين عزل بل إصلاح خطأ حقيقي: عزل `XDG_CONFIG_HOME` يعزل مسارات
    الملفات فقط، أما `systemctl --user stop/disable` فيخاطب مدير المستخدم
    الحقيقي دائماً بصرف النظر عن أي متغيّر بيئة. فكان اختبار «الإزالة»
    **يُزيل خدمة المستخدم الحقيقية** التي ثبّتها لنفسه.

    تُسمح أوامر القراءة فقط، ويُمنع كل ما يُغيّر حالة النظام.
    """
    real_run = installer._run
    blocked = []

    def guarded(command, timeout=installer.COMMAND_TIMEOUT):
        name = list(command)
        if name and name[0] in ('systemctl', 'loginctl', 'schtasks',
                                'journalctl', 'systemd-analyze'):
            if not any(part in _READ_ONLY_COMMANDS for part in name):
                blocked.append(' '.join(name[:4]))
                # نحاكي «الوحدة غير محمّلة»: أقرب ما يقوله systemd فعلاً
                return 1, '', 'Unit not loaded (محجوب في الاختبار)'
        return real_run(name, timeout=timeout)

    monkeypatch.setattr(installer, '_run', guarded)
    yield blocked


def _target(working=AWKWARD_DIR):
    return installer.LaunchTarget(
        executable='/usr/bin/python3.12',
        arguments=[f'{working}/main.py', '--background'],
        working_dir=working)


def _sections(unit: str):
    """
    تفكيك ملف الوحدة إلى أقسام مع تجاهل التعليقات.

    التفكيك بالبحث النصّي عن `[Service]` لا يصلح: التعليقات التوضيحية في الملف
    تذكر أسماء الأقسام، فيقع الفصل عند تعليق لا عند ترويسة قسم. نعتمد بداية
    السطر كما يفعل systemd نفسه.
    """
    sections = {}
    current = None
    for line in unit.splitlines():
        stripped = line.strip()
        if stripped.startswith('#') or not stripped:
            continue
        if stripped.startswith('[') and stripped.endswith(']'):
            current = stripped[1:-1]
            sections[current] = []
        elif current is not None:
            sections[current].append(stripped)
    return sections


class TestLaunchTarget:
    def test_uses_current_interpreter_not_bare_python(self):
        """
        الخدمة لا ترث `PATH` الخاص بصدفة المستخدم، فـ`python3` المجرّد قد لا
        يوجد أو يشير إلى مفسّر آخر. `sys.executable` يعمل داخل بيئة افتراضية.
        """
        target = installer.detect_launch_target()
        assert Path(target.executable).is_absolute()
        assert target.executable == str(Path(sys.executable).resolve())

    def test_background_flag_present(self):
        assert '--background' in installer.detect_launch_target(True).arguments
        assert '--background' not in installer.detect_launch_target(False).arguments

    def test_exec_line_quotes_paths_with_spaces(self):
        """
        `ExecStart` سطر أوامر يُقسَّم على الفراغات، فمسار غير مقتبس يصير
        وسيطين ويفشل التشغيل برسالة مضلّلة عن ملف غير موجود.
        """
        line = _target().exec_line
        assert '"' in line
        assert f'"{AWKWARD_DIR}/main.py"' in line
        assert line.endswith('--background')
        assert '"--background"' not in line, 'العلم لا يحتاج اقتباساً'

    def test_simple_paths_not_quoted_needlessly(self):
        target = installer.LaunchTarget(executable='/usr/bin/python3',
                                        arguments=['/opt/app/main.py'])
        assert target.exec_line == '/usr/bin/python3 /opt/app/main.py'


class TestUnitFile:
    def test_working_directory_is_not_quoted(self):
        """
        خطأ حقيقي رصدناه: `WorkingDirectory` ليس سطر أوامر بل مسار واحد يمتد
        إلى آخر السطر. اقتباسه يجعل systemd يعدّ علامتي التنصيص جزءاً من
        المسار فيرفض الوحدة بأن المسار «ليس مطلقاً».
        """
        line = [row for row in installer.build_unit(_target()).splitlines()
                if row.startswith('WorkingDirectory=')][0]
        value = line.split('=', 1)[1]

        assert not value.startswith('"'), 'المسار مقتبس - سيرفضه systemd'
        assert value == AWKWARD_DIR
        assert Path(value).is_absolute()

    def test_start_limit_keys_live_in_unit_section(self):
        """
        خطأ حقيقي رصدناه: `StartLimitIntervalSec` و`StartLimitBurst` من خصائص
        الوحدة. كتابتهما في `[Service]` تجعل systemd يتجاهلهما صامتاً، فيبقى
        التطبيق يُعاد تشغيله بلا حدّ إن كان خطؤه دائماً.
        """
        sections = _sections(installer.build_unit(_target()))

        for key in ('StartLimitIntervalSec', 'StartLimitBurst'):
            assert any(row.startswith(key) for row in sections['Unit']), \
                f'{key} ليس في [Unit]'
            assert not any(row.startswith(key) for row in sections['Service']), \
                f'{key} في [Service] - سيتجاهله systemd صامتاً'

    def test_expected_sections_present(self):
        sections = _sections(installer.build_unit(_target()))
        assert set(sections) == {'Unit', 'Service', 'Install'}

    def test_wanted_by_default_target(self):
        """
        `graphical.target` هدف نظام لا معنى له في مدير المستخدم.
        `default.target` هو ما يُبلَغ عند تسجيل الدخول، ومع linger عند الإقلاع.
        """
        unit = installer.build_unit(_target())
        assert 'WantedBy=default.target' in unit
        assert 'WantedBy=graphical.target' not in unit

    def test_graphical_session_is_ordering_not_requirement(self):
        """
        لو اشترطنا الجلسة الرسومية لما عمل التطبيق حيث لا تتوفّر. الترتيب
        يُفضّل البدء بعدها، ويعمل بدونها بلا أيقونة.
        """
        unit = installer.build_unit(_target())
        assert 'After=graphical-session.target' in unit
        assert 'Requires=graphical-session.target' not in unit
        assert 'Requisite=graphical-session.target' not in unit

    def test_no_path_protection_that_blocks_learning_data(self):
        """
        خطأ حقيقي رصدناه: `ProtectHome=read-only` مع كتابة التطبيق إلى
        `~/.config/batteryguard` يجعل الخدمة تفشل عند أول حفظ لبيانات التعلّم.
        """
        unit = installer.build_unit(_target())
        assert 'ProtectHome' not in unit
        assert 'ProtectSystem=strict' not in unit

    def test_no_unexpanded_shell_substitution(self):
        """
        خطأ حقيقي رصدناه: `XDG_RUNTIME_DIR=/run/user/$(id -u user)`. systemd لا
        يشغّل صدفة فلا يُوسَّع `$(...)`، فتصير القيمة نصاً حرفياً ولا يجد
        التطبيق ناقل الرسائل.
        """
        unit = installer.build_unit(_target())
        assert '$(' not in unit
        assert '`' not in unit

    def test_no_hardcoded_display(self):
        """
        تثبيت `DISPLAY=:0` يكسر التشغيل على Wayland وعند تغيّر رقم الشاشة.
        مدير المستخدم يملك هذه المتغيّرات أصلاً في الجلسات الحديثة.
        """
        unit = installer.build_unit(_target())
        assert 'Environment="DISPLAY' not in unit
        assert 'Environment=DISPLAY' not in unit

    def test_restart_and_stop_timeout_present(self):
        """
        `Restart=always` لأن التطبيق مراقِب وتوقّفه الصامت يعني بطارية بلا
        حماية. `TimeoutStopSec` كافٍ للإفراج عن العمليات المعلّقة قبل القطع.
        """
        unit = installer.build_unit(_target())
        assert 'Restart=always' in unit
        assert 'RestartSec=' in unit

        timeout = int([row for row in unit.splitlines()
                       if row.startswith('TimeoutStopSec=')][0].split('=')[1])
        assert timeout >= 10, 'مهلة قصيرة تقطع الإفراج عن العمليات المعلّقة'

    @NEEDS_ANALYZE
    def test_systemd_accepts_generated_unit(self, isolated_xdg_config):
        """
        الحكم الوحيد المعتبر: systemd نفسه. هذا الاختبار كان سيمنع خطأي
        الاقتباس والقسم الخطأ من الوصول إلى المستخدم.
        """
        unit_path = (isolated_xdg_config / 'systemd' / 'user'
                     / installer.SERVICE_NAME)
        unit_path.write_text(installer.build_unit(_target(str(isolated_xdg_config))),
                             encoding='utf-8')
        assert installer.verify_unit(unit_path) == []

    @NEEDS_ANALYZE
    def test_verify_catches_bad_unit(self, isolated_xdg_config):
        """التحقق يكشف الخطأ فعلاً، فلا يمرّ بنجاح كاذب"""
        unit_path = (isolated_xdg_config / 'systemd' / 'user'
                     / installer.SERVICE_NAME)
        unit_path.write_text(
            '[Unit]\nDescription=bad\n\n[Service]\n'
            'WorkingDirectory="/relative path"\nExecStart=/bin/true\n',
            encoding='utf-8')
        assert installer.verify_unit(unit_path) != []


class TestDesktopEntry:
    def test_quotes_paths_and_delays_start(self):
        content = installer.build_desktop_entry(_target())
        exec_line = [row for row in content.splitlines()
                     if row.startswith('Exec=')][0]

        assert f'"{AWKWARD_DIR}/main.py"' in exec_line
        assert '--background' in exec_line
        assert 'X-GNOME-Autostart-enabled=true' in content
        # تأخير يمنح البيئة وقتاً لتشغيل مضيف الصينية قبل أن يطلبها التطبيق
        assert 'X-GNOME-Autostart-Delay=' in content
        assert 'Terminal=false' in content


@LINUX_ONLY
class TestInstallLifecycle:
    def test_desktop_fallback_writes_entry(self, isolated_xdg_config):
        result = installer.install(prefer_systemd=False, start_now=False)
        entry = isolated_xdg_config / 'autostart' / installer.DESKTOP_NAME

        assert result.success and result.method == installer.METHOD_DESKTOP
        assert entry.exists()
        assert '--background' in entry.read_text(encoding='utf-8')
        # صدق: هذه الطريقة لا تُعيد التشغيل عند التوقّف، ويجب أن يُقال ذلك
        assert any('لا تُعيد تشغيله' in note for note in result.follow_up)

    def test_status_detects_desktop_entry(self, isolated_xdg_config):
        installer.install(prefer_systemd=False, start_now=False)
        state = installer.status()

        assert state.installed is True
        assert state.method == installer.METHOD_DESKTOP
        assert state.enabled is True

    def test_status_respects_disabled_flag_in_entry(self, isolated_xdg_config):
        entry = isolated_xdg_config / 'autostart' / installer.DESKTOP_NAME
        entry.write_text('[Desktop Entry]\nX-GNOME-Autostart-enabled=false\n',
                         encoding='utf-8')
        assert installer.status().enabled is False

    def test_uninstall_removes_every_method(self, isolated_xdg_config):
        """
        بقاء إحدى الطريقتين بعد «إزالة» يعني تطبيقاً يعود بعد الإقلاع بعد أن
        أُخبر المستخدم أنه أُزيل.
        """
        unit = isolated_xdg_config / 'systemd' / 'user' / installer.SERVICE_NAME
        entry = isolated_xdg_config / 'autostart' / installer.DESKTOP_NAME
        unit.write_text('[Unit]\n', encoding='utf-8')
        entry.write_text('[Desktop Entry]\n', encoding='utf-8')

        result = installer.uninstall()
        assert result.success
        assert not unit.exists()
        assert not entry.exists()
        assert installer.status().installed is False

    def test_uninstall_is_idempotent(self, isolated_xdg_config):
        result = installer.uninstall()
        assert result.success
        assert any('لم يكن' in message for message in result.messages)

    def test_uninstall_never_touches_real_manager_in_tests(
            self, isolated_xdg_config, no_real_systemctl):
        """
        حرس على العزل نفسه: لو عاد أي مسار إلى مخاطبة مدير systemd الحقيقي
        بأمر يُغيّر الحالة، لظهر هنا. الإخفاق السابق أزال خدمة المستخدم فعلاً.
        """
        (isolated_xdg_config / 'systemd' / 'user' / installer.SERVICE_NAME
         ).write_text('[Unit]\n', encoding='utf-8')
        installer.uninstall()

        # الأوامر المُغيِّرة حُجبت، والملف حُذف من المسار المعزول فقط
        assert all('stop' in item or 'disable' in item or 'daemon-reload' in item
                   or 'reset-failed' in item for item in no_real_systemctl), \
            no_real_systemctl
        assert not (isolated_xdg_config / 'systemd' / 'user'
                    / installer.SERVICE_NAME).exists()

    def test_status_flags_duplicate_methods(self, isolated_xdg_config):
        """وجود الطريقتين معاً يشغّل نسختين تتنافسان على القفل: يجب التحذير"""
        (isolated_xdg_config / 'systemd' / 'user' / installer.SERVICE_NAME
         ).write_text('[Unit]\n', encoding='utf-8')
        (isolated_xdg_config / 'autostart' / installer.DESKTOP_NAME
         ).write_text('[Desktop Entry]\n', encoding='utf-8')

        assert installer.status().conflicts, 'لم يُحذّر من التكرار'

    def test_control_refuses_when_not_installed(self, isolated_xdg_config):
        ok, message = installer.control('start')
        assert ok is False and message

    def test_control_rejects_unknown_action(self):
        ok, _ = installer.control('explode')
        assert ok is False

    def test_status_is_json_serialisable(self, isolated_xdg_config):
        import json

        payload = json.loads(json.dumps(installer.status().as_dict(),
                                        ensure_ascii=False))
        assert 'method' in payload and 'installed' in payload


@LINUX_ONLY
class TestCliSurface:
    """الأوامر التي يذكرها التوثيق يجب أن تعمل فعلاً"""

    @pytest.mark.parametrize('command', ['status', 'logs'])
    def test_readonly_commands_exit_zero(self, command, isolated_xdg_config,
                                        capsys):
        assert installer.main([command]) == 0
        assert capsys.readouterr().out

    def test_unknown_command_returns_error(self, capsys):
        assert installer.main(['nonsense']) == 2
        assert 'الأوامر' in capsys.readouterr().out

    def test_shell_wrapper_exists_and_is_executable(self):
        script = Path(__file__).resolve().parent.parent / 'service_manager.sh'
        assert script.exists()
        content = script.read_text(encoding='utf-8')
        # لا sudo: الخدمة خدمة مستخدم
        assert 'sudo systemctl' not in content
        for command in ('install', 'uninstall', 'status', 'check', 'linger'):
            assert f'cmd_{command}' in content, command

    def test_shell_wrapper_syntax_is_valid(self):
        script = Path(__file__).resolve().parent.parent / 'service_manager.sh'
        result = subprocess.run(['bash', '-n', str(script)],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
