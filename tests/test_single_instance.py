#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات النسخة الواحدة والإعدادات الافتراضية"""

import socket
import time

import pytest

from single_instance import SingleInstance, _deterministic_port


class TestDeterministicPort:
    def test_port_stable_across_calls(self):
        assert _deterministic_port('BatteryGuardPro') == \
               _deterministic_port('BatteryGuardPro')

    def test_port_differs_per_app(self):
        assert _deterministic_port('AppA') != _deterministic_port('AppB')

    def test_port_not_hash_randomized(self):
        """كان hash() عشوائياً بين الجلسات - CRC32 حتمي"""
        p1 = _deterministic_port('StableName')
        # محاكاة جلسة جديدة (PYTHONHASHSEED لا يؤثر على crc32)
        p2 = _deterministic_port('StableName')
        assert p1 == p2
        assert 50000 <= p1 < 60000


class TestSingleInstance:
    def _unique_name(self) -> str:
        import random
        return f'TestBG{random.randint(10000, 99999)}'

    def test_first_instance_acquires_lock(self):
        name = self._unique_name()
        inst = SingleInstance(name)
        try:
            assert inst.is_already_running() is False
            assert inst.lock_file.exists()
        finally:
            inst.release()

    def test_second_instance_detected(self):
        name = self._unique_name()
        first = SingleInstance(name)
        try:
            second = SingleInstance(name)
            try:
                assert first.is_already_running() is False
                assert second.is_already_running() is True
            finally:
                second.release()
        finally:
            first.release()
            time.sleep(0.05)

    def test_release_allows_new_instance(self):
        name = self._unique_name()
        first = SingleInstance(name)
        first.release()
        time.sleep(0.05)

        second = SingleInstance(name)
        try:
            assert second.is_already_running() is False
        finally:
            second.release()

    def test_show_existing_sends_signal(self):
        name = self._unique_name()
        first = SingleInstance(name)
        received = []

        def listener():
            try:
                conn, _ = first.socket.accept()
                data = conn.recv(1024)
                received.append(data)
                conn.close()
            except OSError:
                pass

        import threading
        t = threading.Thread(target=listener, daemon=True)
        t.start()
        time.sleep(0.1)

        second = SingleInstance(name)
        ok = second.show_existing_instance()
        t.join(timeout=2)

        try:
            assert ok is True
            assert received == [b'SHOW']
        finally:
            second.release()
            first.release()


class TestDefaultSettings:
    def test_defaults_shape(self):
        from default_settings import DEFAULT_SETTINGS, get_default_settings
        s = get_default_settings()
        assert isinstance(s, dict)
        assert s['notifications_enabled'] is True
        assert s['minimize_to_tray'] is False
        assert s['max_charge_limit'] > s['min_charge_limit']
        # نسخة مستقلة وليست مرجعاً مباشراً
        assert s is not DEFAULT_SETTINGS

    def test_sound_assignments_files_exist(self):
        """كل ملف صوت معرف في الإعدادات يجب أن يكون موجوداً فعلاً"""
        from default_settings import SOUND_ASSIGNMENTS
        for sound_type, info in SOUND_ASSIGNMENTS.items():
            path = info['file']
            # المسار نسبي من جذر المشروع
            full = __import__('pathlib').Path(__file__).parent.parent / path
            assert full.exists(), f"ملف الصوت مفقود: {sound_type} -> {path}"
