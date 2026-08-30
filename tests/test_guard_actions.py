#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات حارس البطارية.

هذه الوحدة الوحيدة في التطبيق التي تلمس عمليات نظام التشغيل، فأكثر ما يُختبر
هنا ليس أنها تعمل بل أنها **لا تعمل** حيث يجب أن تمتنع: عملية نظام، خيط نواة،
عملية مستخدم آخر، رقم عملية أُعيد استخدامه، أو التطبيق نفسه.

العمليات المستهدفة في الاختبار تُنشأ بـ `setsid --fork` حتى تكون مستقلة فعلاً:
عملية ابنة للاختبار تحميها البوابة كـ«ذرّية التطبيق»، فيمرّ الاختبار كذباً.
"""

import os
import shutil
import subprocess
import sys
import time
import uuid

import psutil
import pytest

from battery_intelligence import (ACTION_ALERT, ACTION_NONE, ACTION_SUSPEND,
                                  ACTION_THROTTLE, IntelligenceReport, Offender)
from guard_actions import (ACTION_TERMINATE, PROTECTED_NAMES, BatteryGuard,
                           GuardPolicy, SafetyGate, is_kernel_thread,
                           is_protected_name)

LINUX_ONLY = pytest.mark.skipif(not sys.platform.startswith('linux'),
                                reason='لينكس فقط')
NEEDS_SETSID = pytest.mark.skipif(shutil.which('setsid') is None,
                                  reason='setsid غير متوفّر')

DISCHARGING = {'percent': 55, 'is_charging': False, 'reporting': True}
CHARGING = {'percent': 55, 'is_charging': True, 'reporting': True}
NOT_REPORTING = {'percent': 55, 'is_charging': False, 'reporting': False}

MARKER = 'BG_TEST_TARGET'


def _spawn_independent(seconds: int = 60) -> int:
    """
    عملية مستقلة تماماً عن الاختبار: `setsid --fork` يجعل الجدّ يخرج فوراً
    فتُعاد نسبة الحفيد إلى init، وهذا ما يحاكي تطبيق مستخدم حقيقي.

    العلامة فريدة لكل نداء عن قصد. العلامة الثابتة كانت تجعل الاختبار يجد
    عملية متبقّية من تشغيل سابق (الانفصال يعني أن قتلها قد يفشل بصمت)، فيعمل
    على هدف حالته مغيَّرة أصلاً — فيفشل الاختبار لسبب لا علاقة له بالشيفرة.
    """
    unique = f'{MARKER}_{uuid.uuid4().hex}'
    code = f'import time\n_m = {unique!r}\ntime.sleep({seconds})\n'
    subprocess.run(['setsid', '--fork', sys.executable, '-c', code],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=10, check=False)
    deadline = time.time() + 5
    while time.time() < deadline:
        for process in psutil.process_iter(['pid', 'cmdline']):
            try:
                if any(unique in str(part)
                       for part in (process.info['cmdline'] or [])):
                    return int(process.info['pid'])
            except psutil.Error:
                continue
        time.sleep(0.1)
    pytest.skip('تعذّر إنشاء عملية مستقلة للاختبار')


@pytest.fixture
def target():
    """عملية هدف مستقلة، تُقتل بعد الاختبار حتماً"""
    pid = _spawn_independent()
    process = psutil.Process(pid)
    yield process
    try:
        process.kill()
        process.wait(timeout=3)
    except (psutil.Error, OSError):
        pass


@pytest.fixture
def guard():
    """حارس بأوسع سياسة، ليُختبر أن السلامة تمنعه لا أن السياسة تمنعه"""
    instance = BatteryGuard(GuardPolicy(
        enabled=True, automatic=True, max_action=ACTION_SUSPEND,
        only_on_battery=False, min_confidence=0, min_damage_score=0))
    yield instance
    instance.stop()


def _report(name, score=90.0, action=ACTION_SUSPEND, confidence=80, pids=None):
    return IntelligenceReport(offenders=[Offender(
        name=name, pids=list(pids or []), watts=6.0, damage_score=score,
        recommended_action=action, confidence=confidence)])


class TestProtectedNames:
    @pytest.mark.parametrize('name', [
        'systemd', 'Xorg', 'gnome-shell', 'kwin_wayland', 'gdm3',
        'NetworkManager', 'polkitd', 'pipewire', 'dpkg', 'apt', 'sudo',
        'dbus-daemon', 'plasmashell', 'sshd',
    ])
    def test_critical_processes_protected(self, name):
        assert is_protected_name(name), name

    @pytest.mark.parametrize('name', ['systemd-resolved', 'gsd-power',
                                      'gvfs-daemon', 'at-spi-bus-launcher'])
    def test_prefixes_protected(self, name):
        assert is_protected_name(name), name

    def test_empty_name_treated_as_protected(self):
        """الشك يُفسَّر لصالح الامتناع: اسم مجهول قد يكون عملية حرجة"""
        assert is_protected_name('') is True
        assert is_protected_name(None) is True

    def test_ordinary_applications_not_protected(self):
        for name in ('brave', 'firefox', 'code', 'slack', 'mpv'):
            assert not is_protected_name(name), name

    def test_protected_list_covers_both_platforms(self):
        assert 'systemd' in PROTECTED_NAMES and 'explorer.exe' in PROTECTED_NAMES


@LINUX_ONLY
class TestSafetyGate:
    def test_refuses_own_process(self):
        verdict = SafetyGate().check(os.getpid())
        assert not verdict.allowed and verdict.reason == 'self'

    def test_refuses_pid_one(self):
        assert not SafetyGate().check(1).allowed

    def test_refuses_kernel_threads(self):
        gate = SafetyGate()
        found = 0
        for process in psutil.process_iter(['pid']):
            try:
                candidate = psutil.Process(process.info['pid'])
                if candidate.ppid() != 2:
                    continue
            except psutil.Error:
                continue
            assert is_kernel_thread(candidate)
            verdict = gate.check(candidate.pid)
            assert not verdict.allowed
            assert verdict.reason in ('kernel_thread', 'protected', 'gone')
            found += 1
            if found >= 3:
                break
        assert found, 'لم تُوجد خيوط نواة للفحص'

    def test_refuses_other_users_processes(self):
        gate = SafetyGate()
        for process in psutil.process_iter(['pid', 'username']):
            if process.info['username'] == 'root' and process.info['pid'] > 300:
                verdict = gate.check(process.info['pid'])
                assert not verdict.allowed
                return
        pytest.skip('لا عملية root للفحص')

    def test_refuses_missing_pid(self):
        verdict = SafetyGate().check(4_194_303)
        assert not verdict.allowed and verdict.reason in ('gone', 'invalid_pid')

    def test_refuses_invalid_pid(self):
        for pid in (0, -1):
            assert not SafetyGate().check(pid).allowed

    def test_refuses_own_children(self):
        """
        عملية أنشأها التطبيق ليست مخالفاً: إيقافها يعطّل عمل التطبيق نفسه.
        الفحص بصعود شجرة الأبوّة لا بمقارنة مجموعة العمليات، لأن المقارنة
        بالمجموعة تحمي كل ما أُطلق من نفس الطرفية بما فيه متصفّح المستخدم.
        """
        child = subprocess.Popen(['sleep', '30'])
        try:
            time.sleep(0.4)
            verdict = SafetyGate().check(child.pid)
            assert not verdict.allowed and verdict.reason == 'own_descendant'
        finally:
            child.kill()
            child.wait()

    @NEEDS_SETSID
    def test_allows_independent_user_process(self, target):
        verdict = SafetyGate().check(target.pid, target.name())
        assert verdict.allowed, verdict.reason

    @NEEDS_SETSID
    def test_refuses_when_name_no_longer_matches(self, target):
        """
        بين لحظة الاستدلال ولحظة التنفيذ قد تنتهي العملية ويُعاد استخدام رقمها.
        التصرّف وقتها يوقف عملية بريئة، وهو أسوأ من عدم التصرّف.
        """
        verdict = SafetyGate().check(target.pid, 'definitely-not-this')
        assert not verdict.allowed and verdict.reason == 'pid_reused'


@LINUX_ONLY
class TestProtectedProcessesUntouchable:
    """القائمة المحمية لا تُخترق حتى بأمر مباشر يتجاوز السياسة"""

    def test_cannot_suspend_pid_one(self, guard):
        outcome = guard.suspend('systemd', [1])
        assert not outcome.applied
        assert outcome.reason == 'no_eligible_process'
        assert psutil.pid_exists(1)

    def test_cannot_terminate_pid_one(self, guard):
        outcome = guard.terminate('systemd', [1])
        assert not outcome.applied
        assert psutil.pid_exists(1)

    def test_cannot_throttle_display_server(self, guard):
        for process in psutil.process_iter(['pid', 'name']):
            if process.info['name'] in ('Xorg', 'gnome-shell', 'Xwayland'):
                outcome = guard.throttle(process.info['name'],
                                         [process.info['pid']])
                assert not outcome.applied
                return
        pytest.skip('لا خادم عرض مرئي')


@LINUX_ONLY
@NEEDS_SETSID
class TestReversibleActions:
    def test_suspend_and_resume(self, guard, target):
        name = target.name()
        outcome = guard.suspend(name, [target.pid])
        time.sleep(0.4)

        assert outcome.applied and outcome.affected == 1
        assert outcome.reversible is True
        assert target.status() == psutil.STATUS_STOPPED

        active = guard.active_interventions()
        assert name in active
        assert active[name]['kind'] == ACTION_SUSPEND
        assert 0 < active[name]['seconds_left'] <= 300

        resumed = guard.resume(name)
        time.sleep(0.4)
        assert resumed.applied and resumed.affected == 1
        assert target.status() != psutil.STATUS_STOPPED
        assert name not in guard.active_interventions()

    def test_throttle_uses_reversible_ionice_by_default(self, guard, target):
        name = target.name()
        outcome = guard.throttle(name, [target.pid])

        assert outcome.applied
        assert outcome.reversible is True, 'ionice وحده قابل للتراجع'
        assert int(target.ionice().ioclass) == int(psutil.IOPRIO_CLASS_IDLE)
        assert target.nice() == 0, 'nice لا يُلمس بلا موافقة صريحة'

        guard.restore(name)
        assert int(target.ionice().ioclass) != int(psutil.IOPRIO_CLASS_IDLE)

    def test_nice_declared_irreversible_when_opted_in(self, target):
        """
        على لينكس `RLIMIT_NICE=0`: يمكن خفض الأولوية ولا يمكن رفعها. الصدق هنا
        أن يُعلَن ذلك في النتيجة بدل ادّعاء تراجع لا يحدث.
        """
        instance = BatteryGuard(GuardPolicy(
            enabled=True, automatic=True, max_action=ACTION_SUSPEND,
            only_on_battery=False, allow_irreversible_nice=True))
        try:
            name = target.name()
            outcome = instance.throttle(name, [target.pid])
            assert outcome.applied
            assert target.nice() == 19
            assert outcome.reversible is False

            restored = instance.restore(name)
            assert target.nice() == 19, 'الاستعادة تفشل فعلاً بلا صلاحيات'
            assert 'nice_needs_privilege' in restored.skipped
            assert restored.reversible is False
        finally:
            instance.stop()

    def test_stop_releases_everything(self, target):
        """
        عملية معلّقة بعد اختفاء من علّقها مشكلة لا يفهمها المستخدم. الإفراج
        الشامل في مسار الإغلاق ليس تحسيناً بل شرط سلامة.
        """
        instance = BatteryGuard(GuardPolicy(
            enabled=True, automatic=True, max_action=ACTION_SUSPEND,
            only_on_battery=False))
        name = target.name()
        instance.suspend(name, [target.pid])
        time.sleep(0.3)
        assert target.status() == psutil.STATUS_STOPPED

        instance.stop()
        time.sleep(0.4)
        assert target.status() != psutil.STATUS_STOPPED
        assert not instance.active_interventions()

    def test_watchdog_forces_release_after_timeout(self, monkeypatch, target):
        """حبل النجاة: التعليق يُفرَج عنه تلقائياً حتى لو لم يطلب أحد ذلك"""
        import guard_actions

        monkeypatch.setattr(guard_actions, 'SUSPEND_MAX_SECONDS', 2.0)
        monkeypatch.setattr(guard_actions, 'WATCHDOG_INTERVAL', 0.5)
        instance = BatteryGuard(GuardPolicy(
            enabled=True, automatic=True, max_action=ACTION_SUSPEND,
            only_on_battery=False))
        try:
            name = target.name()
            instance.suspend(name, [target.pid])
            time.sleep(0.3)
            assert target.status() == psutil.STATUS_STOPPED

            deadline = time.time() + 10
            while time.time() < deadline:
                if target.status() != psutil.STATUS_STOPPED:
                    break
                time.sleep(0.3)
            assert target.status() != psutil.STATUS_STOPPED, 'لم يُفرج تلقائياً'
            assert not instance.active_interventions()
        finally:
            instance.stop()


class TestPolicy:
    def test_terminate_rejected_as_policy_ceiling(self):
        """لا إيقاف تلقائي أبداً: لا يُقبل حتى كإعداد محفوظ"""
        policy = GuardPolicy.from_dict({'max_action': ACTION_TERMINATE})
        assert policy.max_action != ACTION_TERMINATE

    def test_cap_limits_recommendation(self):
        policy = GuardPolicy(max_action=ACTION_ALERT)
        assert policy.cap(ACTION_SUSPEND) == ACTION_ALERT
        assert policy.cap(ACTION_THROTTLE) == ACTION_ALERT
        assert policy.cap(ACTION_ALERT) == ACTION_ALERT

        policy.max_action = ACTION_THROTTLE
        assert policy.cap(ACTION_SUSPEND) == ACTION_THROTTLE
        assert policy.cap(ACTION_ALERT) == ACTION_ALERT

    def test_defaults_are_conservative(self):
        """الافتراضي يراقب وينبّه ولا يلمس شيئاً"""
        policy = GuardPolicy()
        assert policy.enabled is True
        assert policy.automatic is False
        assert policy.max_action == ACTION_ALERT
        assert policy.only_on_battery is True
        assert policy.allow_irreversible_nice is False

    def test_from_dict_ignores_invalid_values(self):
        policy = GuardPolicy.from_dict({
            'max_action': 'nonsense', 'act_below_percent': 'abc',
            'min_damage_score': None, 'min_confidence': 'x',
            'allowlist': 'not-a-list'})
        assert policy.max_action == ACTION_ALERT
        assert 1 <= policy.act_below_percent <= 100
        assert isinstance(policy.min_damage_score, float)


class TestPlanning:
    @staticmethod
    def _guard(**kwargs):
        options = dict(enabled=True, automatic=True, max_action=ACTION_SUSPEND,
                       only_on_battery=True, min_confidence=55,
                       min_damage_score=45)
        options.update(kwargs)
        return BatteryGuard(GuardPolicy(**options), dry_run=True)

    def test_alerts_instead_of_acting_on_mains(self):
        plan = self._guard().plan(_report('hog'), CHARGING)
        assert plan and plan[0][1] == ACTION_ALERT and plan[0][2] == 'on_mains'

    def test_alerts_when_measurement_untrustworthy(self):
        plan = self._guard().plan(_report('hog'), NOT_REPORTING)
        assert plan and plan[0][1] == ACTION_ALERT
        assert plan[0][2] == 'not_reporting'

    def test_alerts_when_confidence_low(self):
        plan = self._guard().plan(_report('hog', confidence=20), DISCHARGING)
        assert plan and plan[0][1] == ACTION_ALERT
        assert plan[0][2] == 'low_confidence'

    def test_ignores_scores_below_threshold(self):
        assert self._guard().plan(_report('hog', score=20.0), DISCHARGING) == []

    def test_respects_user_blocklist(self):
        plan = self._guard(blocklist=['hog']).plan(_report('hog'), DISCHARGING)
        assert plan and plan[0][1] == ACTION_NONE and plan[0][2] == 'blocklisted'

    def test_respects_user_allowlist(self):
        plan = self._guard(allowlist=['other']).plan(_report('hog'), DISCHARGING)
        assert plan and plan[0][1] == ACTION_ALERT
        assert plan[0][2] == 'not_allowlisted'

    def test_acts_when_all_conditions_met(self):
        plan = self._guard().plan(_report('hog'), DISCHARGING)
        assert plan and plan[0][1] == ACTION_SUSPEND and plan[0][2] == 'policy'

    def test_disabled_guard_plans_nothing(self):
        assert self._guard(enabled=False).plan(_report('hog'), DISCHARGING) == []


@LINUX_ONLY
@NEEDS_SETSID
class TestEnforcement:
    def test_manual_mode_touches_nothing(self, target):
        """
        الوضع الافتراضي: لا يتغيّر شيء في جهاز المستخدم بلا إذنه، حتى لو كان
        التغيير مفيداً وقابلاً للتراجع.
        """
        instance = BatteryGuard(GuardPolicy(
            enabled=True, automatic=False, max_action=ACTION_SUSPEND,
            only_on_battery=False, min_confidence=0, min_damage_score=0))
        try:
            name = target.name()
            outcomes = instance.enforce(_report(name, pids=[target.pid]),
                                        DISCHARGING)
            time.sleep(0.3)

            assert outcomes and all(item.kind == ACTION_ALERT
                                    for item in outcomes)
            assert outcomes[0].reason == 'manual_mode'
            # المُختبَر هو ألّا تُعلَّق العملية. لا تُقارن الحالة حرفياً:
            # `running` و`sleeping` تتبادلان مع جدولة النواة، فالمقارنة
            # الحرفية تفشل عشوائياً لسبب لا علاقة له بالحارس.
            assert target.status() != psutil.STATUS_STOPPED
            assert not instance.active_interventions()
        finally:
            instance.stop()

    def test_terminate_never_reached_automatically(self, target):
        """لا مسار تلقائي يصل إلى الإيقاف النهائي، ولو أوصى الاستدلال به"""
        instance = BatteryGuard(GuardPolicy(
            enabled=True, automatic=True, max_action=ACTION_SUSPEND,
            only_on_battery=False, min_confidence=0, min_damage_score=0))
        try:
            name = target.name()
            outcomes = instance.enforce(
                _report(name, score=100.0, action=ACTION_TERMINATE,
                        pids=[target.pid]), DISCHARGING)
            assert ACTION_TERMINATE not in [item.kind for item in outcomes]
            assert psutil.pid_exists(target.pid)
        finally:
            instance.stop()

    def test_explicit_terminate_works_and_is_declared_final(self, guard):
        pid = _spawn_independent(120)
        process = psutil.Process(pid)
        outcome = guard.terminate(process.name(), [pid])
        time.sleep(0.5)

        assert outcome.applied and outcome.affected >= 1
        assert outcome.reversible is False
        assert not psutil.pid_exists(pid) or \
            psutil.Process(pid).status() == psutil.STATUS_ZOMBIE

    def test_dry_run_changes_nothing(self, target):
        instance = BatteryGuard(GuardPolicy(
            enabled=True, automatic=True, max_action=ACTION_SUSPEND,
            only_on_battery=False), dry_run=True)
        name = target.name()

        outcome = instance.suspend(name, [target.pid])
        time.sleep(0.3)
        assert outcome.applied and outcome.reason == 'dry_run'
        # الحالة الحرفية تتبادل مع الجدولة؛ المُختبَر أنها لم تُعلَّق ولم
        # يُسجَّل أي تدخّل نشط
        assert target.status() != psutil.STATUS_STOPPED, \
            'وضع التجربة علّق العملية فعلاً'
        assert not instance.active_interventions()


class TestOutcomeShape:
    def test_outcome_is_json_serialisable(self):
        import json

        guard = BatteryGuard(GuardPolicy(), dry_run=True)
        outcome = guard.suspend('nonexistent-process', [4_194_303])
        payload = json.loads(json.dumps(outcome.as_dict(), ensure_ascii=False))
        assert payload['applied'] is False
        assert payload['reason'] == 'no_eligible_process'
        assert isinstance(payload['skipped'], dict)

    def test_history_is_bounded(self):
        guard = BatteryGuard(GuardPolicy(), dry_run=True)
        offender = Offender(name='x', watts=1.0, damage_score=50.0)
        for _ in range(260):
            guard._alert(offender, 'test')
        assert len(guard.history) <= 200
        assert len(guard.recent_history(10)) == 10
