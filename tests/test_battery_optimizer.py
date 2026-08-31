#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات المحسّن الآمن

القسم الأول يثبّت **انحدارات**: كل أمر منها كان في الإصدار السابق وأعطب
جهاز مستخدم، ولا يجوز أن يعود عبر تعديل لاحق. القسم الثاني يقيس أن النتيجة
صادقة: لا رقم توفير بلا قياس، ولا نجاح مزعوم لإجراء لم يُنفَّذ.
"""

from pathlib import Path

import pytest

import battery_optimizer as bo
import system_tuning as st
from test_system_tuning import RecordingWriter, make_backlight, make_drm

SOURCE = Path(__file__).resolve().parent.parent / 'battery_optimizer.py'


def executable_source() -> str:
    """
    شيفرة الوحدة بلا توثيق ولا تعليقات.

    التوثيق يشرح ما حُذف ولماذا، فلو فُحص كما هو لفشل الاختبار على النص الذي
    يحذّر من الأمر نفسه. الاستثناء يجري بـ `ast` لا بتقطيع نصي هشّ.
    """
    import ast
    source = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(source)

    docstrings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            text = ast.get_docstring(node, clean=False)
            if text:
                docstrings.append(text)

    for text in docstrings:
        source = source.replace(text, '')
    return '\n'.join(line.split('#')[0] for line in source.splitlines())


# ═══════════════════════════════════════════════════════════
# انحدارات: أوامر أعطبت أجهزة ولا تعود
# ═══════════════════════════════════════════════════════════

#: (النمط، ما فعله بجهاز المستخدم)
BANNED_PATTERNS = (
    ('/sys/bus/usb/devices/*/power/control',
     'تعليق كل أجهزة USB يفصل محطة الإرساء ولوحة المفاتيح والفأرة'),
    ('rfkill', 'حجب البلوتوث يقطع الفأرة ولم يكن يُستعاد'),
    ('power_dpm_force_performance_level',
     'إجبار مستوى أداء الرسوم على منخفض يسقط الشاشة الخارجية'),
    ('card0', 'رقم بطاقة مثبّت لا وجود له على أجهزة كثيرة'),
    ('drop_caches', 'إفراغ الكاش يُجبر إعادة القراءة من القرص فيزيد السحب'),
    ('swappiness', 'تغيير دائم في النواة بلا طريق رجوع'),
    ('queue/scheduler', 'كتابة مجدول على قرص مفترض بقيمة لم تعد موجودة'),
    ('vblankoffdelay', 'تغيير معامل نواة للرسوم أثناء وصل شاشة'),
    ('cpupower', 'تغيير حاكم المعالج يحتاج جذراً ولم يكن يُستعاد'),
    ("'sudo'", 'كلمة مرور المستخدم لعمل لا يحتاجها'),
    ('sudo -S', 'تمرير كلمة المرور عبر المدخل القياسي'),
    ('powercfg', 'خطة طاقة كاملة تُستبدل بلا التقاط الخطة الأصلية'),
    ('WmiSetBrightness', 'ضبط سطوع بقيمة مطلقة يرفعه بعد أن ينزله المستخدم'),
)


@pytest.mark.parametrize('pattern,why', BANNED_PATTERNS)
def test_dangerous_command_is_absent_from_optimizer(pattern, why):
    """
    لا يكفي حذف الأمر مرة: بلا هذا الاختبار يعود عند أول «تحسين» لاحق.
    التوثيق في `why` حتى يعرف من يقرأ الفشل سببه لا مجرد وجود نمط.
    """
    assert pattern not in executable_source(), f'عاد أمر خطر: {pattern} — {why}'


def test_optimizer_never_writes_process_nice():
    """
    `renice` غير قابل للاستعادة بلا صلاحيات على معظم التوزيعات، فخفض أولوية
    المعالج من مسار تلقائي تغيير دائم بلا إذن. المسموح: أولوية القرص وحدها.
    """
    body = executable_source()
    assert '.nice(' not in body
    assert 'ionice' in body


@pytest.mark.parametrize('pattern,why', BANNED_PATTERNS)
def test_dangerous_command_is_absent_from_tuning_engine(pattern, why):
    """
    نفس الفحص على `system_tuning`: هو الوحدة الوحيدة التي تكتب على النظام،
    فلو عاد الأمر فيها لعاد الضرر مهما كان المحسّن نظيفاً.
    """
    import ast
    from pathlib import Path as _Path
    source = (_Path(__file__).resolve().parent.parent /
              'system_tuning.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            text = ast.get_docstring(node, clean=False)
            if text:
                source = source.replace(text, '')
    body = '\n'.join(line.split('#')[0] for line in source.splitlines())
    assert pattern not in body, f'عاد أمر خطر إلى المحرك: {pattern} — {why}'


# ═══════════════════════════════════════════════════════════
# محسّن على عتاد مصنوع
# ═══════════════════════════════════════════════════════════

class FakeMonitor:
    """مقياس قدرة مصنوع: يعيد قيمة السحب من قائمة معطاة"""

    def __init__(self, readings):
        self.readings = list(readings)

    def get_battery_status(self):
        value = self.readings.pop(0) if self.readings else None
        return {'power_draw': value} if value is not None else {}


@pytest.fixture
def optimizer(tmp_path, monkeypatch):
    """محسّن على لوحة داخلية 80% وشاشة داخلية فقط، بلا مقياس قدرة"""
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                         writer=RecordingWriter(), snapshot_file='opt_test.json')
    monkeypatch.setattr(bo, 'MEASURE_SETTLE_SECONDS', 0.0)
    return bo.BatteryOptimizer(tuner=tuner)


def test_run_dims_panel_and_reports_it_as_reversible(optimizer):
    result = optimizer.optimize_battery()

    dim = next(a for a in result['actions'] if a['key'] == 'dim_panel')
    assert dim['success'] is True
    assert dim['reversible'] is True
    assert result['reversible'] is True
    assert result['can_restore'] is True


def test_no_saving_number_without_a_power_measurement(optimizer):
    """
    الجهاز الذي لا يبلّغ القدرة لا يُعطى رقم توفير. الإصدار السابق كان يعلن
    «توفير 15٪» من ثوابت مكتوبة في الشيفرة بلا أي قياس.
    """
    result = optimizer.optimize_battery()

    assert result['power_saved'] == 0.0
    assert result['power_saved_measured'] is False
    assert all(action['power_saved'] == 0.0 for action in result['actions'])


def test_saving_is_the_measured_difference_when_hardware_reports_power(
        tmp_path, monkeypatch):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                         writer=RecordingWriter(), snapshot_file='m.json')
    monkeypatch.setattr(bo, 'MEASURE_SETTLE_SECONDS', 0.0)

    optimizer = bo.BatteryOptimizer(monitor=FakeMonitor([14.0, 11.5]), tuner=tuner)
    result = optimizer.optimize_battery()

    assert result['power_saved_measured'] is True
    assert result['power_saved'] == 2.5
    assert result['draw_before'] == 14.0


def test_external_display_blocks_graphics_and_is_declared(tmp_path, monkeypatch):
    """
    الشكوى الأصلية: التحسين يفصل الشاشة الثانية. البوابة تمنع كل إجراءات
    الرسوم، والامتناع يظهر للمستخدم بسببه لا يُخفى.
    """
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected',
                              'card1-HDMI-A-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (800, 1000)})
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                         writer=RecordingWriter(), snapshot_file='e.json')
    monkeypatch.setattr(bo, 'MEASURE_SETTLE_SECONDS', 0.0)

    result = bo.BatteryOptimizer(tuner=tuner).optimize_battery()

    graphics = next(a for a in result['actions'] if a['key'] == 'graphics')
    assert graphics['declined'] is True
    assert graphics['reason'] == 'external_display_connected'
    assert graphics['details']            # سبب مترجم لا مفتاح خام
    assert graphics['success'] is False


def test_usb_and_radio_and_kernel_are_always_declared(optimizer):
    result = optimizer.optimize_battery()
    declined = {action['key']: action for action in result['actions']
                if action['declined']}

    for key in ('usb', 'radio', 'kernel'):
        assert key in declined, f'{key} يجب أن يظهر كامتناع معلن'
        assert declined[key]['details']


def test_every_declined_reason_has_a_translation(optimizer):
    """امتناع بلا سبب مقروء يساوي امتناعاً غامضاً: المستخدم لا يفهم ما جرى"""
    result = optimizer.optimize_battery()
    for action in result['actions']:
        if action['declined']:
            assert not action['details'].startswith('opt.'), action


def test_unknown_reason_is_reported_not_leaked_as_a_key():
    text = bo.BatteryOptimizer._reason_text('no-permitted-path:denied')
    assert 'no-permitted-path:denied' in text
    assert not text.startswith('opt.reason')


def test_concurrent_run_is_refused_not_duplicated(optimizer):
    optimizer.is_optimizing = True
    result = optimizer.optimize_battery()
    assert result['success'] is False
    assert result['actions'] == []


def test_restore_undoes_the_dim(optimizer):
    original = optimizer.tuner.internal_backlights()[0].current
    optimizer.optimize_battery()
    assert optimizer.tuner.internal_backlights()[0].current < original

    outcome = optimizer.restore()

    assert outcome['success'] is True
    assert optimizer.tuner.internal_backlights()[0].current == original
    assert optimizer.get_statistics()['pending_restore'] is False


def test_statistics_report_measured_runs_only(tmp_path, monkeypatch):
    drm = make_drm(tmp_path, {'card1-eDP-1': 'connected'})
    backlight = make_backlight(tmp_path, {'intel_backlight': (900, 1000)})
    tuner = st.SafeTuner(drm_root=drm, backlight_root=backlight,
                         writer=RecordingWriter(), snapshot_file='s.json')
    monkeypatch.setattr(bo, 'MEASURE_SETTLE_SECONDS', 0.0)

    optimizer = bo.BatteryOptimizer(tuner=tuner)
    optimizer.optimize_battery()
    stats = optimizer.get_statistics()

    assert stats['runs'] == 1
    assert stats['measured_runs'] == 0
    assert stats['watts_saved_average'] is None


def test_sudo_password_is_stored_but_never_used(optimizer):
    optimizer.set_sudo_password('secret')
    assert optimizer.sudo_password == 'secret'
    body = executable_source()
    # الخاصية موجودة للتوافق، ولا مسار يمرّرها إلى أي أمر
    assert 'self.sudo_password' in body
    assert 'communicate' not in body
    assert 'Popen' not in body
