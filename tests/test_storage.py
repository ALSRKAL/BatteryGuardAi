#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات وحدة التخزين الذري"""

import json
import threading

from storage import (
    JsonStore,
    atomic_write_json,
    read_json,
)


def _write_repeatedly(path, index, failures):
    """
    كاتب يعمل في عملية منفصلة (لا خيط): سباق الملف المؤقت يظهر بين العمليات
    فقط، لأن القفل داخل العملية يسلسل الخيوط ولا يُرى من عملية أخرى.
    """
    for iteration in range(40):
        if not atomic_write_json(path, {'worker': index, 'iter': iteration}):
            failures.append((index, iteration))


class TestAtomicWrite:
    def test_write_and_read_roundtrip(self, isolated_data_dir):
        path = isolated_data_dir / 'data.json'
        payload = {'name': 'بطارية', 'level': 85, 'nested': {'a': [1, 2, 3]}}
        assert atomic_write_json(path, payload) is True
        assert read_json(path) == payload
        # لا يبقى ملف مؤقت
        assert not (isolated_data_dir / 'data.json.tmp').exists()

    def test_overwrite(self, isolated_data_dir):
        path = isolated_data_dir / 'data.json'
        atomic_write_json(path, {'v': 1})
        atomic_write_json(path, {'v': 2})
        assert read_json(path) == {'v': 2}

    def test_missing_file_returns_default(self, isolated_data_dir):
        assert read_json(isolated_data_dir / 'nope.json') is None
        sentinel = {'x': 1}
        assert read_json(isolated_data_dir / 'nope.json', sentinel) is sentinel

    def test_corrupt_file_recovery(self, isolated_data_dir):
        path = isolated_data_dir / 'corrupt.json'
        path.write_text('{broken json!!', encoding='utf-8')
        result = read_json(path, default={'recovered': True})
        assert result == {'recovered': True}
        # نسخة تشخيصية من الملف التالف محفوظة
        backup = isolated_data_dir / 'corrupt.json.corrupt'
        assert backup.exists()
        # الملف الأصلي أُزيل لصالح الافتراضي عند القراءات القادمة
        assert not path.exists()

    def test_concurrent_writes_produce_valid_file(self, isolated_data_dir):
        """كتابات متزامنة من خيوط متعددة يجب أن تنتج ملفاً صالحاً دائماً"""
        path = isolated_data_dir / 'concurrent.json'
        errors = []

        def writer(i):
            for j in range(10):
                ok = atomic_write_json(path, {'writer': i, 'iter': j})
                if not ok:
                    errors.append((i, j))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        data = read_json(path)
        assert isinstance(data, dict)
        assert 'writer' in data

    def test_writes_from_two_processes_do_not_destroy_each_other(
            self, isolated_data_dir):
        """
        عُثر على هذا العطل في سجل جهاز حقيقي: خدمة الخلفية ونسخة تعمل من
        الطرفية كتبتا `battery_ai_data.json` معاً، فسقطت إحداهما بـ
        `No such file or directory: ...json.tmp -> ...json` وخسرت كتابتها.

        السبب أن اسم الملف المؤقت كان مشتركاً (`<name>.tmp`): استبدلت الأولى
        الملف المؤقت الذي تكتبه الثانية. القفل داخل العملية لا يحمي من ذلك
        لأنه لا يُرى من عملية أخرى، فالاسم يجب أن يكون فريداً لكل عملية.
        """
        import multiprocessing as mp

        path = isolated_data_dir / 'cross_process.json'

        with mp.Manager() as manager:
            failures = manager.list()
            procs = [mp.Process(target=_write_repeatedly,
                                args=(path, i, failures))
                     for i in range(4)]
            for p in procs:
                p.start()
            for p in procs:
                p.join(timeout=30)
            assert list(failures) == [], f'كتابات فاشلة: {list(failures)}'

        assert isinstance(read_json(path), dict)
        # لا ملف مؤقت متبقٍّ باسم مشترك يمكن أن تتنازع عليه عمليتان
        assert not (isolated_data_dir / 'cross_process.json.tmp').exists()


class TestJsonStore:
    def test_defaults_and_update(self, isolated_data_dir):
        store = JsonStore('store.json', defaults={'score': 0, 'mode': 'auto'})
        assert store.get('score') == 0
        store.update(score=42)
        store.set('extra', True)
        store.save()
        assert (isolated_data_dir / 'store.json').exists()

    def test_persistence_across_instances(self, isolated_data_dir):
        store1 = JsonStore('persist.json', defaults={'a': 1})
        store1.data['b'] = 2
        store1.save()

        store2 = JsonStore('persist.json', defaults={'a': 999, 'c': 3})
        # القيم المحفوظة تتقدم على الافتراضيات، والافتراضيات الجديدة تُضاف
        assert store2.get('a') == 1
        assert store2.get('b') == 2
        assert store2.get('c') == 3

    def test_corrupt_store_falls_back_to_defaults(self, isolated_data_dir):
        (isolated_data_dir / 'bad.json').write_text('not json', encoding='utf-8')
        store = JsonStore('bad.json', defaults={'safe': True})
        assert store.get('safe') is True

    def test_reload(self, isolated_data_dir):
        store = JsonStore('reload.json', defaults={'v': 1})
        store.save()
        external = json.loads((isolated_data_dir / 'reload.json').read_text())
        external['v'] = 100
        (isolated_data_dir / 'reload.json').write_text(
            json.dumps(external), encoding='utf-8')
        store.reload()
        assert store.get('v') == 100
