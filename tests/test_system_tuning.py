#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات محرك الضبط الآمن

كل اختبار هنا يقيس **امتناعاً** عن التصرف أو **قابلية تراجع**، لأن أعطال
المحسّن السابق كانت كلها تصرّفاً بلا إذن أو بلا طريق رجوع:

- رفع السطوع بعد أن ينزله المستخدم.
- إجبار إدارة طاقة الرسوم على التوفير أثناء وصل شاشة خارجية.
- تعليق كل أجهزة USB بما فيها محطة الإرساء ولوحة المفاتيح.
"""

import pytest

import system_tuning as st


# ═══════════════════════════════════════════════════════════
# عتاد مصنوع: شجرة sysfs كاملة داخل tmp_path
# ═══════════════════════════════════════════════════════════

def make_drm(tmp_path, connectors):
    """بناء `/sys/class/drm` مصنوع: {اسم الموصّل: 'connected'|'disconnected'}"""
    drm = tmp_path / 'drm'
    drm.mkdir(parents=True, exist_ok=True)
    for name, status in connectors.items():
        entry = drm / name
        entry.mkdir(parents=True, exist_ok=True)
        (entry / 'status').write_text(f'{status}\n')
    # بطاقة بلا ملف status: يجب تجاهلها لا اعتبارها شاشة
    (drm / 'card1').mkdir(parents=True, exist_ok=True)
    return drm


def make_backlight(tmp_path, devices):
    """بناء `/sys/class/backlight` مصنوع: {الاسم: (الحالي، الأقصى)}"""
    root = tmp_path / 'backlight'
    root.mkdir(parents=True, exist_ok=True)
    for name, (current, maximum) in devices.items():
        entry = root / name
        entry.mkdir(parents=True, exist_ok=True)
        (entry / 'brightness').write_text(f'{current}\n')
        (entry / 'max_brightness').write_text(f'{maximum}\n')
    return root


class RecordingWriter(st.BrightnessWriter):
    """كاتب سطوع يسجّل ما كُتب ويعدّل الملف المصنوع فعلاً"""

    def __init__(self, fail=False):
        super().__init__(runner=lambda args: (1, 'test-runner'))
        self.writes = []
        self.fail = fail

    def write(self, device, raw_value):
        raw_value = max(1, min(device.maximum, int(raw_value)))
        if self.fail:
            return False, 'no-permitted-path:test'
        self.writes.append((device.name, raw_value))
        (device.path / 'brightness').write_text(f'{raw_value}\n')
        return True, 'test'

    def probe(self):
        return 'test'


@pytest.fixture
def tuner(tmp_path):
    """محرك ضبط على عتاد مصنوع: لوحة داخلية عند 80% وشاشة داخلية فقط"""
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected',
                              'card1-HDMI-A-1': 'disconnected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    return st.SafeTuner(drm_root=drm, backlight_root=backlight,
                        writer=RecordingWriter(),
                        snapshot_file='test_tuning_snapshot.json')


# ═══════════════════════════════════════════════════════════
# قراءة الشاشات
# ═══════════════════════════════════════════════════════════

def test_internal_and_external_connectors_are_separated(tmp_path):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected',
                              'card1-HDMI-A-1': 'connected',
                              'card1-DP-1': 'disconnected'})
    state = st.read_display_state(drm)
    assert state.internal == ('card1-eDP-1',)
    assert state.external == ('card1-HDMI-A-1',)
    assert state.has_external is True
    assert state.total_connected == 2


def test_disconnected_connector_is_not_a_display(tmp_path):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected',
                              'card1-HDMI-A-1': 'disconnected'})
    assert st.read_display_state(drm).has_external is False


def test_missing_drm_root_is_reported_unreadable(tmp_path):
    state = st.read_display_state(tmp_path / 'absent')
    assert state.readable is False
    assert state.has_external is False


# ═══════════════════════════════════════════════════════════
# بوابات السلامة: الجهل ليس إذناً بالتصرف
# ═══════════════════════════════════════════════════════════

def test_graphics_tuning_blocked_while_external_display_connected(tmp_path):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected',
                              'card1-HDMI-A-1': 'connected'})
    allowed, reason = st.graphics_tuning_allowed(st.read_display_state(drm))
    assert allowed is False
    assert reason == 'external_display_connected'


def test_graphics_tuning_blocked_when_display_state_unreadable(tmp_path):
    allowed, reason = st.graphics_tuning_allowed(
        st.read_display_state(tmp_path / 'absent'))
    assert allowed is False
    assert reason == 'displays_unreadable'


def test_graphics_tuning_allowed_on_laptop_panel_only(tmp_path):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    allowed, reason = st.graphics_tuning_allowed(st.read_display_state(drm))
    assert allowed is True
    assert reason == ''


def test_usb_tuning_is_never_allowed(tmp_path):
    """
    التعليق الشامل لأجهزة USB يفصل محطات الإرساء ولوحات المفاتيح، ولا يوجد
    تمييز موثوق للجهاز الآمن. لا مسار يعيد True من هذه البوابة.
    """
    for connectors in ({'card1-eDP-1': 'connected'},
                       {'card1-eDP-1': 'connected', 'card1-HDMI-A-1': 'connected'}):
        drm = make_drm(tmp_path / str(hash(str(connectors))), connectors)
        allowed, reason = st.usb_tuning_allowed(st.read_display_state(drm))
        assert allowed is False
        assert reason == 'unsafe_by_design'


# ═══════════════════════════════════════════════════════════
# أجهزة السطوع: اللوحة الداخلية وحدها
# ═══════════════════════════════════════════════════════════

def test_external_ddcci_backlight_is_excluded(tmp_path):
    root = make_backlight(tmp_path, {'intel_backlight': (800, 1000),
                                     'ddcci1': (50, 100)})
    names = [device.name for device in st.read_backlights(root, internal_only=True)]
    assert names == ['intel_backlight']
    all_names = [d.name for d in st.read_backlights(root, internal_only=False)]
    assert 'ddcci1' in all_names


def test_backlight_percent_and_raw_conversion(tmp_path):
    root = make_backlight(tmp_path, {'intel_backlight': (761, 937)})
    panel = st.read_backlights(root)[0]
    assert panel.percent == 81
    assert panel.raw_for_percent(50) == 468       # round(937*0.5) بتقريب بايثون
    # لا صفر أبداً: شاشة منطفئة ليست شاشة خافتة
    assert panel.raw_for_percent(0) >= 1


# ═══════════════════════════════════════════════════════════
# السطوع: لا يُرفَع أبداً
# ═══════════════════════════════════════════════════════════

def test_dim_lowers_brightness_by_one_step(tuner):
    result = tuner.dim_internal_panel(step_percent=15, floor_percent=30)
    assert result.applied is True
    assert result.reversible is True
    assert tuner.writer.writes == [('intel_backlight', 650)]  # 80% - 15% = 65%


def test_dim_never_raises_brightness_when_user_set_it_low(tmp_path):
    """
    الشكوى الأصلية: المستخدم ينزل السطوع فيرفعه المحسّن إلى قيمته المختارة.
    هنا اللوحة على 10% والحدّ الأدنى 30%: الرفع إلى 30% ممنوع، والنتيجة
    امتناع مُعلَن لا كتابة.
    """
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (100, 1000)})
    writer = RecordingWriter()
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight, writer=writer,
                         snapshot_file='t.json')

    result = tuner.dim_internal_panel(step_percent=15, floor_percent=30)

    assert result.applied is False
    assert result.reason == 'already_at_floor'
    assert writer.writes == []
    assert (backlight / 'intel_backlight' / 'brightness').read_text().strip() == '100'


def test_dim_stops_at_floor_and_does_not_go_dark(tmp_path):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (400, 1000)})
    writer = RecordingWriter()
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight, writer=writer,
                         snapshot_file='t.json')

    result = tuner.dim_internal_panel(step_percent=50, floor_percent=30)

    assert result.applied is True
    assert writer.writes == [('intel_backlight', 300)]  # توقف عند 30% لا 0%


def test_repeated_dim_never_falls_below_floor(tuner):
    for _ in range(10):
        tuner.dim_internal_panel(step_percent=15, floor_percent=30)
    panel = tuner.internal_backlights()[0]
    assert panel.percent >= 30


def test_manual_user_change_becomes_the_new_original(tuner, tmp_path):
    """
    إذا غيّر المستخدم السطوع بعد كتابتنا، فقيمته هي الأصل الجديد: الاستعادة
    لا تُعيده إلى قيمة قديمة اختارها التطبيق لا المستخدم.
    """
    tuner.dim_internal_panel(step_percent=15, floor_percent=30)   # 800 -> 650
    panel_file = tuner.internal_backlights()[0].path / 'brightness'
    panel_file.write_text('900\n')                                # المستخدم رفعه

    tuner.dim_internal_panel(step_percent=15, floor_percent=30)   # 900 -> 750
    assert tuner.snapshot['brightness']['intel_backlight']['original'] == 900

    tuner.restore_brightness()
    assert panel_file.read_text().strip() == '900'


def test_no_internal_panel_is_declared_not_silently_ignored(tmp_path):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'ddcci1': (50, 100)})
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                         writer=RecordingWriter(), snapshot_file='t.json')

    result = tuner.dim_internal_panel()

    assert result.applied is False
    assert result.reason == 'no_internal_panel'


def test_write_failure_is_reported_not_claimed_as_success(tmp_path):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                         writer=RecordingWriter(fail=True), snapshot_file='t.json')

    result = tuner.dim_internal_panel()

    assert result.applied is False
    assert 'no-permitted-path' in result.reason
    # اللقطة تُكتب بعد نجاح الكتابة وحده: كتابتها قبل معرفة النتيجة تُنشئ
    # حقّ استعادة لقيمة لم تُغيَّر أصلاً
    assert tuner.has_pending_restore() is False
    assert tuner.snapshot.get('brightness') in (None, {})


# ═══════════════════════════════════════════════════════════
# الاستعادة
# ═══════════════════════════════════════════════════════════

def test_declining_does_not_create_a_pending_restore(tmp_path):
    """
    عُثر على هذا العطل في تجربة حقيقية على جهاز: عندما تمتنع الوحدة عن الخفض
    (السطوع عند الحدّ الأدنى) كانت تكتب لقطة على القرص، فيظنّ التطبيق أن
    هناك تغييراً ينتظر الاستعادة، ثم يكتب لاحقاً قيمة لم يضبطها هو أصلاً.
    """
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (150, 1000)})
    writer = RecordingWriter()
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight, writer=writer,
                         snapshot_file='decline.json')

    result = tuner.dim_internal_panel(floor_percent=30)

    assert result.applied is False
    assert writer.writes == []
    assert tuner.snapshot.get('brightness') in (None, {})
    assert tuner.has_pending_restore() is False


def test_user_change_after_our_write_drops_our_claim(tmp_path):
    """
    غيّر المستخدم السطوع بعد كتابتنا: تغييرنا لم يبق قائماً، فلا نحتفظ بحقّ
    استعادة قيمة لم نعد نحن من ضبطها.
    """
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (900, 1000)})
    writer = RecordingWriter()
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight, writer=writer,
                         snapshot_file='drop.json')

    tuner.dim_internal_panel(step_percent=15, floor_percent=30)   # 900 -> 750
    assert tuner.has_pending_restore() is True

    # المستخدم أنزله بنفسه إلى 20٪ (تحت الحدّ الأدنى)
    (backlight / 'intel_backlight' / 'brightness').write_text('200\n')
    result = tuner.dim_internal_panel(step_percent=15, floor_percent=30)

    assert result.applied is False
    assert tuner.has_pending_restore() is False


def test_failed_restore_keeps_the_snapshot(tmp_path):
    """طريق الرجوع لا يُحذف عند فشل الاستعادة: الفشل ليس نجاحاً"""
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    writer = RecordingWriter()
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight, writer=writer,
                         snapshot_file='keep.json')
    tuner.dim_internal_panel(step_percent=20, floor_percent=30)

    writer.fail = True
    result = tuner.restore_brightness()

    assert result.applied is False
    assert tuner.has_pending_restore() is True


def test_restore_returns_exactly_the_original_value(tuner):
    original = tuner.internal_backlights()[0].current
    tuner.dim_internal_panel(step_percent=25, floor_percent=30)
    assert tuner.internal_backlights()[0].current != original

    result = tuner.restore_brightness()

    assert result.applied is True
    assert tuner.internal_backlights()[0].current == original
    assert tuner.has_pending_restore() is False


def test_snapshot_survives_a_new_tuner_instance(tmp_path):
    """التراجع يبقى ممكناً بعد إعادة تشغيل التطبيق: اللقطة على القرص"""
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})

    first = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                         writer=RecordingWriter(), snapshot_file='persist.json')
    first.dim_internal_panel(step_percent=20, floor_percent=30)

    second = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                          writer=RecordingWriter(), snapshot_file='persist.json')
    assert second.has_pending_restore() is True
    assert second.restore_brightness().applied is True
    assert second.internal_backlights()[0].current == 800


def test_restore_with_nothing_applied_is_a_declared_no_op(tuner):
    result = tuner.restore_brightness()
    assert result.applied is False
    assert result.reason == 'nothing_to_restore'
    assert tuner.restore_all() == []


# ═══════════════════════════════════════════════════════════
# التقرير عن القدرات
# ═══════════════════════════════════════════════════════════

def test_capabilities_report_is_honest_about_blocked_paths(tmp_path):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected',
                              'card1-HDMI-A-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                         writer=RecordingWriter(), snapshot_file='t.json')

    caps = tuner.capabilities()

    assert caps['can_dim'] is True
    assert caps['can_tune_graphics'] is False
    assert caps['graphics_blocked_reason'] == 'external_display_connected'
    assert caps['can_tune_usb'] is False
    assert caps['displays']['external'] == ['card1-HDMI-A-1']


# ═══════════════════════════════════════════════════════════
# كاتب السطوع: ترتيب المسارات ولا كلمة مرور
# ═══════════════════════════════════════════════════════════

def test_writer_prefers_desktop_path_then_logind(tmp_path):
    calls = []

    def runner(args):
        calls.append(list(args))
        # المسار الأول يفشل، والثاني ينجح
        return (0, '()') if 'login1' in ' '.join(args) else (1, 'no gnome')

    root = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    panel = st.read_backlights(root)[0]
    writer = st.BrightnessWriter(runner=runner)

    ok, backend = writer.write(panel, 500)

    assert ok is True
    assert backend == 'logind'
    assert 'SettingsDaemon' in ' '.join(calls[0])
    assert 'login1' in ' '.join(calls[1])


def test_writer_never_invokes_sudo(tmp_path):
    invoked = []

    def runner(args):
        invoked.append(list(args))
        return 1, 'denied'

    root = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    panel = st.read_backlights(root)[0]
    ok, reason = st.BrightnessWriter(runner=runner).write(panel, 500)

    assert ok is True or ok is False           # النتيجة غير مهمة هنا
    assert all('sudo' not in ' '.join(call) for call in invoked)
    assert all('pkexec' not in ' '.join(call) for call in invoked)


def test_writer_clamps_value_inside_device_range(tmp_path):
    written = []

    def runner(args):
        written.append(list(args))
        return 0, '()'

    root = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    panel = st.read_backlights(root)[0]
    writer = st.BrightnessWriter(runner=runner)

    writer.write(panel, 99999)
    writer.write(panel, -50)

    percents = [call[-1] for call in written]
    assert percents == ['<int32 100>', '<int32 1>']
