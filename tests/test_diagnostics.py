#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات محرك التشخيص: التصنيف يعتمد على القياس لا على التخمين"""

import pytest

import diagnostics as diag
from diagnostics import DiagnosticsReport, Reading


def reading(name, value, status='ok'):
    return Reading(name, value, status, f"/sys/class/power_supply/BAT0/{name}")


def battery(**values):
    """بطارية اختبارية: أي مفتاح غير مذكور يُعدّ مفقوداً"""
    readings = {}
    for name in diag.BATTERY_ATTRIBUTES:
        if name in values:
            entry = values[name]
            if isinstance(entry, tuple):
                readings[name] = reading(name, entry[0], entry[1])
            else:
                readings[name] = reading(name, str(entry))
        else:
            readings[name] = Reading(name, None, 'missing',
                                     f"/sys/class/power_supply/BAT0/{name}")
    return {'name': 'BAT0', 'path': '/sys/class/power_supply/BAT0',
            'readings': readings}


def make_report(batteries=None, vendor='HP', chassis='10', mains_online=True,
                drivers=None, thermal=None, cross=None) -> DiagnosticsReport:
    report = DiagnosticsReport(generated_at='2026/08/30 01:00')
    report.environment = {'vendor': vendor, 'product': 'Test Model',
                          'chassis_type': chassis, 'bios_version': 'X01'}
    report.batteries = batteries if batteries is not None else []
    report.mains = {'present': True, 'online': mains_online, 'name': 'AC'}
    report.drivers = drivers or {'loaded_modules': [], 'tools': {'tlp': True}}
    report.thermal = thermal or {'battery_temp_c': None, 'zones': []}
    report.cross_check = cross or {}
    report.device_mode = diag._device_mode(report.environment, report.batteries)
    report.findings = diag.classify(report)
    report.grade = diag._grade(report.findings, report.batteries)
    return report


def ids(report):
    return [finding.id for finding in report.findings]


class TestDeviceMode:
    def test_laptop_with_battery(self):
        report = make_report([battery(present=1, capacity=55, voltage_now=11400000)])
        assert report.device_mode == 'portable_with_battery'

    def test_desktop_without_battery(self):
        report = make_report([], chassis='3')
        assert report.device_mode == 'desktop'
        assert 'desktop_no_battery' in ids(report)
        assert report.grade == 'unmeasurable'

    def test_laptop_without_battery_is_a_warning(self):
        """لابتوب بلا بطارية مكتشفة ليس حالة طبيعية"""
        report = make_report([], chassis='10')
        assert report.device_mode == 'portable_no_battery'
        finding = report.findings[0]
        assert finding.id == 'battery_not_detected'
        assert finding.severity == 'warning'
        assert finding.remediation


class TestFaultClassification:
    def test_absent_flag_detected(self):
        report = make_report([battery(present=0)])
        assert 'battery_absent_flag' in ids(report)
        assert report.grade == 'unmeasurable'

    def test_ec_not_reporting_is_critical_with_evidence(self):
        """الحالة الحقيقية: بطارية موجودة بصفر شحن وجهد وتيار"""
        report = make_report([battery(
            present=1, capacity=0, voltage_now=0, current_now=0,
            status='Not charging', charge_full=2880000, charge_full_design=2880000)])
        finding = next(item for item in report.findings if item.id == 'ec_not_reporting')
        assert finding.severity == 'critical'
        assert finding.confidence >= 90
        assert any('capacity=0' in line for line in finding.evidence)
        assert 'diag.remedy.replace_cells' in finding.remediation

    def test_implausible_capacity_detected(self):
        report = make_report([battery(
            present=1, capacity=0, voltage_now=0, current_now=0,
            status='Unknown', charge_full=2880000, charge_full_design=2880000)])
        assert 'capacity_implausible' in ids(report)

    def test_healthy_battery_has_no_fault(self):
        report = make_report([battery(
            present=1, capacity=62, voltage_now=11800000, current_now=1200000,
            status='Discharging', charge_full=4200000, charge_full_design=5000000,
            cycle_count=212, temp=305,
            charge_control_end_threshold=80)],
            thermal={'battery_temp_c': 30.5, 'zones': []})
        assert 'ec_not_reporting' not in ids(report)
        assert 'capacity_implausible' not in ids(report)
        assert 'threshold_path_available' in ids(report)
        assert report.grade == 'ok'

    def test_timeout_is_reported(self):
        report = make_report([battery(
            present=1, capacity=50, voltage_now=('', 'timeout'),
            current_now=('', 'timeout'), status='Discharging',
            charge_control_end_threshold=80)])
        finding = next(item for item in report.findings if item.id == 'sysfs_timeout')
        assert finding.params['count'] == 2
        assert report.grade == 'impaired'


class TestControlPathClassification:
    def test_hp_is_firmware_only(self):
        report = make_report([battery(present=1, capacity=44,
                                      voltage_now=11400000, current_now=0,
                                      status='Not charging')], vendor='HP')
        finding = next(item for item in report.findings
                       if item.id == 'firmware_only_control')
        assert 'remedy.hp.bios' in finding.remediation

    def test_missing_vendor_driver_is_actionable(self):
        report = make_report([battery(present=1, capacity=44,
                                      voltage_now=11400000, current_now=0,
                                      status='Not charging')],
                             vendor='LENOVO',
                             drivers={'loaded_modules': ['acpi'], 'tools': {}})
        finding = next(item for item in report.findings
                       if item.id == 'driver_not_loaded')
        assert finding.params['driver'] == 'thinkpad_acpi'
        assert 'diag.remedy.load_driver' in finding.remediation

    def test_unknown_vendor_falls_back_to_generic(self):
        report = make_report([battery(present=1, capacity=44,
                                      voltage_now=11400000, current_now=0,
                                      status='Not charging')],
                             vendor='NoName Devices')
        assert 'no_threshold_path' in ids(report)


class TestCrossCheck:
    def test_disagreement_reported(self):
        report = make_report([battery(present=1, capacity=50,
                                      voltage_now=11400000, current_now=1000,
                                      status='Discharging')],
                             cross={'psutil': 50.0, 'sysfs': 62.0,
                                    'upower': 50.0, 'agree': False})
        finding = next(item for item in report.findings
                       if item.id == 'source_disagreement')
        assert finding.params['sysfs'] == 62.0


class TestThermalPlausibility:
    @pytest.mark.parametrize('celsius,expected', [
        (127.0, False), (0.0, False), (-40.0, False), (110.0, False),
        (31.5, True), (78.0, True),
    ])
    def test_sentinel_values_rejected(self, celsius, expected):
        assert diag._plausible_temperature(celsius) is expected

    def test_plausible_zones_filtered(self):
        thermal = {'zones': [{'type': 'acpitz', 'celsius': 127.0, 'plausible': False},
                             {'type': 'x86_pkg_temp', 'celsius': 54.0, 'plausible': True}]}
        zones = diag.plausible_zones(thermal)
        assert len(zones) == 1
        assert zones[0]['type'] == 'x86_pkg_temp'


class TestRealMachineProbe:
    def test_run_produces_a_report(self):
        """الفحص الحقيقي على جهاز التطوير يجب أن ينتهي بتقرير صالح"""
        report = diag.run(deep=False)
        assert report.generated_at
        assert report.device_mode in ('portable_with_battery', 'portable_no_battery',
                                     'desktop', 'desktop_with_ups', 'unknown')
        assert report.grade in ('ok', 'degraded', 'impaired', 'unmeasurable', 'unknown')
        assert isinstance(diag.readable_table(report), list)

    def test_all_finding_keys_translate(self):
        """كل مفتاح تصنيف يجب أن يكون له نص مترجم"""
        from i18n import missing_keys, reload_catalogs, set_language, t
        reload_catalogs()
        set_language('ar')
        report = diag.run(deep=False)
        for finding in report.findings:
            t(finding.key, **finding.params)
            for step in finding.remediation:
                t(step)
        assert missing_keys() == []
