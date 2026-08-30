#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات نسب استهلاك الطاقة إلى العمليات.

المُختبَر هنا هو الصدق قبل الدقة: ألّا يُخترع واط لم يُقس، وألّا يُدرَّب النموذج
على قياس لا يعني ما نظنّه (تيار الشحن)، وأن تُعلَن الأبعاد الناقصة صراحةً.
"""

import random
import sys

import pytest

from power_attribution import (BEHAVIOUR_CPU_SPIKE, BEHAVIOUR_CPU_SUSTAINED,
                               BEHAVIOUR_DISK_THRASH, BEHAVIOUR_IDLE_INHIBITOR,
                               BEHAVIOUR_MEMORY_PRESSURE,
                               BEHAVIOUR_SLEEP_INHIBITOR,
                               BEHAVIOUR_WAKEUP_STORM,
                               CPU_SPIKE_CORE_PERCENT,
                               CPU_SUSTAINED_SECONDS, DISK_THRASH_MB_PER_SEC,
                               UNATTRIBUTED, WAKEUP_STORM_PER_SEC,
                               AttributionResult, PowerAttribution, PowerModel,
                               ProcessLoad, _INHIBITOR_LINE, sleep_inhibitors)

LINUX_ONLY = pytest.mark.skipif(not sys.platform.startswith('linux'),
                                reason='لينكس فقط')


class TestPowerModel:
    """النموذج يتعلّم من قياسات الجهاز نفسه، ولا يخترع معاملات"""

    @staticmethod
    def _train(model, base, coefficients, count=400, noise=0.05, seed=7):
        random.seed(seed)
        for _ in range(count):
            features = {'cpu': random.uniform(0, 90),
                        'io': random.uniform(0, 120),
                        'wake': random.uniform(0, 3000)}
            watts = base + sum(coefficients[k] * features[k] for k in features)
            model.observe(features, watts + random.gauss(0, noise))
        return model

    def test_recovers_known_coefficients(self):
        """انحدار صحيح رياضياً: يستعيد معاملات معروفة من بيانات مصنوعة"""
        expected = {'cpu': 0.30, 'io': 0.02, 'wake': 0.001}
        model = self._train(PowerModel(), 5.0, expected)

        assert model.calibrated is True
        learned = model.coefficients
        assert model.baseline_watts == pytest.approx(5.0, abs=0.05)
        for name, value in expected.items():
            assert learned[name] == pytest.approx(value, rel=0.05), name
        assert model.r_squared > 0.99

    def test_never_returns_negative_coefficient(self):
        """
        بُعد لا علاقة له بالقدرة يجب أن يخرج صفراً لا سالباً: معامل سالب يعني
        «هذا الحِمل يوفّر طاقة»، وهو مستحيل فيزيائياً ويقلب النسب رأساً على عقب.
        """
        model = PowerModel()
        random.seed(11)
        for _ in range(300):
            cpu = random.uniform(0, 90)
            model.observe({'cpu': cpu, 'io': random.uniform(0, 120), 'wake': 0.0},
                          6.0 + 0.25 * cpu + random.gauss(0, 0.3))

        coefficients = model.coefficients
        assert all(value >= 0.0 for value in coefficients.values()), coefficients
        assert coefficients['cpu'] == pytest.approx(0.25, rel=0.1)
        assert coefficients['io'] == pytest.approx(0.0, abs=0.005)

    def test_rejects_implausible_watts(self):
        """عيّنة واحدة فاسدة تفسد المعامل لمئات العيّنات، فتُرفض عند الباب"""
        model = PowerModel()
        for watts in (0.0, -5.0, 900.0, 1e9):
            model.observe({'cpu': 10.0}, watts)
        assert model.samples == 0
        assert model.calibrated is False

    def test_priors_used_before_calibration(self):
        """قبل البيانات الكافية: قيم أولية معلنة وثقة منخفضة، لا تخمين مُطمئن"""
        model = PowerModel()
        assert model.coefficients == PowerModel.PRIORS
        assert model.baseline_watts == PowerModel.PRIOR_BASELINE
        assert model.calibrated is False
        assert model.confidence() <= 25

        model.observe({'cpu': 20.0, 'io': 5.0, 'wake': 100.0}, 12.0)
        assert model.confidence() <= 25, 'عيّنة واحدة لا ترفع الثقة'

    def test_confidence_grows_with_data_and_fit(self):
        model = self._train(PowerModel(), 5.0, {'cpu': 0.3, 'io': 0.02, 'wake': 0.001})
        assert model.confidence() > 80

    def test_state_survives_json_roundtrip(self):
        """الحالة تُحفظ تراكمياً بحجم ثابت وتُستعاد بلا فقد"""
        import json

        model = self._train(PowerModel(), 5.0, {'cpu': 0.3, 'io': 0.02, 'wake': 0.001})
        restored = PowerModel(json.loads(json.dumps(model.dump())))

        assert restored.samples == model.samples
        assert restored.coefficients['cpu'] == pytest.approx(
            model.coefficients['cpu'], rel=1e-9)
        assert restored.baseline_watts == pytest.approx(model.baseline_watts,
                                                        rel=1e-9)

    def test_ignores_incompatible_state(self):
        """حالة محفوظة بأبعاد مختلفة تُهمل بلا انهيار"""
        model = PowerModel({'features': ['cpu'], 'xtx': [[1.0]], 'xty': [1.0]})
        assert model.samples == 0
        assert model.coefficients == PowerModel.PRIORS

    def test_cost_watts_excludes_baseline(self):
        """الأساس ليس نصيب عملية: نصيبها هو حِملها وحده"""
        model = PowerModel()
        features = {'cpu': 10.0, 'io': 0.0, 'wake': 0.0}
        assert model.predict(features) - model.cost_watts(features) == \
            pytest.approx(model.baseline_watts)


class TestInhibitorParsing:
    """
    تحليل `systemd-inhibit`: الحقل الأول قد يحتوي فراغات، والتمييز بين المنع
    الحقيقي والتأجيل الحميد هو جوهر الفائدة.
    """

    @pytest.mark.parametrize('line,pid,what,mode', [
        ('ModemManager 0 root 1537 ModemManager sleep '
         'ModemManager needs to reset devices delay', 1537, 'sleep', 'delay'),
        # الحقل الأول بفراغات: كان يُلتقط UID مكان رقم العملية
        ('GNOME Shell 1000 mohammed 4737 gnome-shell sleep '
         'GNOME needs to lock the screen delay', 4737, 'sleep', 'delay'),
        ('Unattended Upgrades Shutdown 0 root 2192 unattended-upgr shutdown '
         'Stop ongoing upgrades before shutdown delay', 2192, 'shutdown', 'delay'),
        ('mpv 1000 user 9001 mpv idle Playing video block',
         9001, 'idle', 'block'),
    ])
    def test_parses_lines_with_spaces_in_first_field(self, line, pid, what, mode):
        match = _INHIBITOR_LINE.search(line)
        assert match is not None, line
        assert int(match.group('pid')) == pid
        assert match.group('what') == what
        assert match.group('mode') == mode

    def test_rejects_non_inhibitor_lines(self):
        for line in ('WHO UID USER PID COMM WHAT WHY MODE',
                     '9 inhibitors listed.', '', 'garbage'):
            assert _INHIBITOR_LINE.search(line) is None

    @LINUX_ONLY
    def test_reads_real_inhibitors(self):
        """
        على جهاز حقيقي: كل رقم عملية مُرجَع يجب أن يكون موجوداً فعلاً. رقم
        وهمي يعني تحليلاً خاطئاً يُنتج إجراءً على عملية بريئة.
        """
        import psutil

        result = sleep_inhibitors(force=True)
        assert isinstance(result, dict)
        for pid, info in result.items():
            assert psutil.pid_exists(pid), f'رقم عملية وهمي: {pid}'
            assert info['mode'] in ('block', 'delay')
            assert isinstance(info['blocking'], bool)
            # المنع الحقيقي = block على هدف نوم/خمول، لا كل block
            if info['blocking']:
                assert info['mode'] == 'block'


@LINUX_ONLY
class TestAttribution:
    """النسب على عتاد حقيقي"""

    def test_first_sample_returns_none(self):
        """الفرق يحتاج عيّنتين: أول نداء يسجّل العدّادات ولا يستنتج"""
        assert PowerAttribution().sample(measured_watts=10.0) is None

    def test_short_interval_rejected(self):
        """فاصل أقصر من الحدّ يعطي معدلات ضجيج، فيُرفض بلا نتيجة"""
        attribution = PowerAttribution()
        attribution.sample(measured_watts=10.0)
        assert attribution.sample(measured_watts=10.0) is None

    def test_training_only_while_discharging(self, monkeypatch):
        """
        أثناء الشحن يقيس `current_now` تيار الشحن لا الاستهلاك. التدريب عليه
        يفسد المعامل، والنسب المبنيّة عليه تكون خاطئة بصمت.
        """
        import time as time_module

        attribution = PowerAttribution()
        clock = [1000.0]
        monkeypatch.setattr(time_module, 'monotonic', lambda: clock[0])

        attribution.sample(measured_watts=12.0, is_charging=True)
        clock[0] += 5.0
        charging = attribution.sample(measured_watts=12.0, is_charging=True)
        assert charging is not None
        assert charging.trained is False
        assert attribution.model.samples == 0
        assert charging.dynamic_watts is None, 'لا قدرة ديناميكية أثناء الشحن'

        clock[0] += 5.0
        discharging = attribution.sample(measured_watts=12.0, is_charging=False)
        assert discharging.trained is True
        assert attribution.model.samples == 1
        assert discharging.dynamic_watts is not None

    def test_never_invents_power_above_measurement(self, monkeypatch):
        """
        مجموع ما يُنسب + غير المنسوب لا يتجاوز ما قِيس أبداً. التضخيم لبلوغ
        الرقم المقيس يعني اختراع استهلاك لم يحدث.
        """
        import time as time_module

        attribution = PowerAttribution()
        clock = [500.0]
        monkeypatch.setattr(time_module, 'monotonic', lambda: clock[0])

        attribution.sample(measured_watts=9.0, is_charging=False)
        clock[0] += 6.0
        result = attribution.sample(measured_watts=9.0, is_charging=False)

        assert result is not None
        total = sum(load.watts for load in result.loads if load.watts is not None)
        assert total <= (result.dynamic_watts or 0.0) + 0.01

    def test_reports_partial_dimensions(self, monkeypatch):
        """
        بُعد لا يمكن قياسه (io لعمليات مستخدم آخر) يُعلَن ناقصاً لا يُتجاهل:
        نسبة مبنيّة على بُعد ناقص تحتاج قارئاً يعرف ذلك.
        """
        import time as time_module

        attribution = PowerAttribution()
        clock = [700.0]
        monkeypatch.setattr(time_module, 'monotonic', lambda: clock[0])
        attribution.sample(measured_watts=9.0, is_charging=False)
        clock[0] += 6.0
        result = attribution.sample(measured_watts=9.0, is_charging=False)

        assert isinstance(result.partial_dimensions, list)
        assert set(result.partial_dimensions) <= {'io'}

    def test_zombie_processes_excluded(self):
        """
        الزومبي انتهت فعلاً ولا تستهلك شيئاً، و`/proc/<pid>/io` لها غير مقروء
        فإدراجها يُنتج بُعداً «ناقصاً» كاذباً ويشوّه حصص الباقين.
        """
        import subprocess
        import time

        import psutil

        child = subprocess.Popen([sys.executable, '-c', 'pass'])
        try:
            deadline = time.time() + 5
            while time.time() < deadline:
                if psutil.Process(child.pid).status() == psutil.STATUS_ZOMBIE:
                    break
                time.sleep(0.1)
            else:
                pytest.skip('لم تصر العملية زومبي في الوقت المتوقّع')

            counters, _ = PowerAttribution()._read_counters()
            assert not [key for key in counters if key[0] == child.pid]
        finally:
            child.wait()

    def test_reset_clears_everything(self):
        attribution = PowerAttribution()
        attribution.sample(measured_watts=10.0)
        attribution.model.observe({'cpu': 10.0}, 8.0)
        attribution.reset()

        assert attribution.model.samples == 0
        assert attribution.last_result is None
        assert attribution.sample(measured_watts=10.0) is None, 'العدّادات صُفّرت'


class TestBehaviourTags:
    """
    عتبات السلوك تُقاس بمقياس النواة الواحدة لا بنسبة الجهاز: عملية تشغل نواة
    كاملة تستنزف البطارية بنفس القدر على جهاز بأربع أنوية أو باثنتين وثلاثين.
    """

    @staticmethod
    def _tags(**kwargs):
        load = ProcessLoad(pid=1, name='x', **kwargs)
        return PowerAttribution._behaviours(load, None)

    def test_core_percent_drives_spike_not_machine_percent(self):
        """
        نواة مشغولة على جهاز بثماني أنوية = 12.5% من الجهاز فقط. لو كانت
        العتبة على نسبة الجهاز لما رُصدت هذه العملية أبداً.
        """
        assert BEHAVIOUR_CPU_SPIKE in self._tags(
            cpu_percent=12.5, cpu_core_percent=100.0)
        assert BEHAVIOUR_CPU_SPIKE not in self._tags(
            cpu_percent=12.5, cpu_core_percent=CPU_SPIKE_CORE_PERCENT - 1)

    def test_sustained_outranks_spike(self):
        """الحِمل المستمر تصنيف أخطر من القفزة، فلا يُعرضان معاً"""
        tags = self._tags(cpu_core_percent=100.0,
                          sustained_seconds=CPU_SUSTAINED_SECONDS + 1)
        assert tags == [BEHAVIOUR_CPU_SUSTAINED]

    def test_wakeup_storm_and_disk_thrash(self):
        assert BEHAVIOUR_WAKEUP_STORM in self._tags(
            wakeups_per_sec=WAKEUP_STORM_PER_SEC + 1)
        assert BEHAVIOUR_DISK_THRASH in self._tags(
            io_mb_per_sec=DISK_THRASH_MB_PER_SEC + 1)
        assert BEHAVIOUR_MEMORY_PRESSURE in self._tags(memory_percent=25.0)

    def test_quiet_process_has_no_tags(self):
        assert self._tags(cpu_core_percent=2.0, io_mb_per_sec=0.1,
                          wakeups_per_sec=10.0, memory_percent=1.0) == []

    def test_blocking_inhibitor_tagged_delay_ignored(self):
        """
        `delay` سلوك طبيعي لمدير الشبكة والطاقة ولا يُعدّ ضرراً. `block` على
        هدف خمول يمنع نوم الجهاز إلى ما لا نهاية، وهو الضرر الحقيقي.
        """
        load = ProcessLoad(pid=1, name='x')

        assert PowerAttribution._behaviours(
            load, {'blocking': False, 'idle': False, 'mode': 'delay'}) == []
        assert PowerAttribution._behaviours(
            load, {'blocking': True, 'idle': True, 'mode': 'block'}) == \
            [BEHAVIOUR_IDLE_INHIBITOR]
        assert PowerAttribution._behaviours(
            load, {'blocking': True, 'idle': False, 'mode': 'block'}) == \
            [BEHAVIOUR_SLEEP_INHIBITOR]


class TestResultShape:
    """النتيجة قابلة للتخزين والعرض بلا معالجة إضافية"""

    def test_top_excludes_unattributed(self):
        result = AttributionResult(
            dynamic_watts=10.0,
            loads=[ProcessLoad(pid=1, name='a', watts=4.0),
                   ProcessLoad(pid=2, name='b', watts=1.0),
                   ProcessLoad(pid=0, name=UNATTRIBUTED, watts=5.0)])

        top = result.top(5)
        assert [load.name for load in top] == ['a', 'b']
        assert [load.name for load in result.top(5, minimum_watts=2.0)] == ['a']

    def test_as_dict_is_json_serialisable(self):
        import json

        result = AttributionResult(
            measured_watts=9.0, dynamic_watts=5.0, baseline_watts=4.0,
            loads=[ProcessLoad(pid=1, name='a', watts=2.0,
                               behaviours=[BEHAVIOUR_CPU_SPIKE])])
        payload = json.loads(json.dumps(result.as_dict(), ensure_ascii=False))

        assert payload['measured_watts'] == 9.0
        assert payload['loads'][0]['behaviours'] == [BEHAVIOUR_CPU_SPIKE]
        assert 'cpu_core_percent' in payload['loads'][0]
