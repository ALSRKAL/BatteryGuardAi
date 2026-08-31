#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تخزين البيانات الموحد - كتابة ذرية آمنة عبر الخيوط

يوفر:
- قراءة/كتابة JSON بشكل ذري (tmp + os.replace) لمنع تلف الملفات
- أقفال لكل ملف تمنع تعارض الكتابة بين الخيوط
- مسارات موحدة عبر resource_path.get_data_path()
"""

import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from resource_path import get_data_path
except ImportError:  # pragma: no cover - وضع تطوير بديل
    def get_data_path(filename: str) -> Path:
        return Path(filename)

logger = logging.getLogger('BatteryGuard')

_locks_guard = threading.Lock()
_file_locks: Dict[str, threading.RLock] = {}


def _lock_for(path: Path) -> threading.RLock:
    """الحصول على قفل فريد لكل مسار ملف"""
    key = str(path)
    with _locks_guard:
        if key not in _file_locks:
            _file_locks[key] = threading.RLock()
        return _file_locks[key]


def atomic_write_json(path: Path, data: Any, indent: int = 2) -> bool:
    """
    كتابة JSON بشكل ذري: يُكتب في ملف مؤقت ثم يُستبدل الملف الأصلي.
    آمن ضد انقطاع الطاقة/الانهيار أثناء الكتابة، وآمن بين الخيوط والعمليات.

    اسم الملف المؤقت فريد لكل عملية وكل كتابة. كان مشتركاً (`<name>.tmp`)،
    فحين تكتب عمليتان نفس الملف — خدمة الخلفية ونسخة تعمل من الطرفية — تستبدل
    الأولى الملف المؤقت الذي تكتبه الثانية، فتفشل الثانية بـ
    `No such file or directory: ...json.tmp -> ...json` وتخسر كتابتها. القفل
    داخل العملية لا يحمي من ذلك لأنه لا يُرى من عملية أخرى.
    """
    path = Path(path)
    lock = _lock_for(path)
    tmp_path: Optional[Path] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(
            f'{path.suffix}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp')
        payload = json.dumps(data, ensure_ascii=False, indent=indent)
        with lock:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        return True
    except Exception as e:
        logger.error(f"خطأ في الكتابة الذرية لـ {path}: {e}")
        # تنظيف الملف المؤقت عند الفشل. `tmp_path` قد تبقى None إذا فشل إنشاء
        # المجلد قبل تعيينها، وكان ذلك يرفع NameError داخل معالج الاستثناء.
        try:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        return False


def read_json(path: Path, default: Optional[Any] = None) -> Any:
    """
    قراءة JSON بأمان. يعيد `default` إذا كان الملف مفقوداً أو تالفاً.
    عند وجود ملف مؤقت متبقٍ (بقايا فشل سابق) يتم تجاهله تلقائياً.
    """
    path = Path(path)
    lock = _lock_for(path)
    with lock:
        if not path.exists():
            return default
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"ملف {path.name} تالف ({e}) - سيتم استخدام القيمة الافتراضية")
            # الاحتفاظ بنسخة من الملف التالف للتشخيص بدلاً من حذفه
            try:
                backup = path.with_suffix(path.suffix + '.corrupt')
                if not backup.exists():
                    os.replace(path, backup)
                    logger.info(f"تم حفظ نسخة من الملف التالف: {backup.name}")
            except Exception:
                pass
            return default
        except OSError as e:
            logger.error(f"خطأ في قراءة {path}: {e}")
            return default


def load_json_data(filename: str, default: Optional[Any] = None) -> Any:
    """قراءة JSON من مجلد بيانات المستخدم"""
    return read_json(get_data_path(filename), default)


def save_json_data(filename: str, data: Any, indent: int = 2) -> bool:
    """كتابة JSON بشكل ذري إلى مجلد بيانات المستخدم"""
    return atomic_write_json(get_data_path(filename), data, indent=indent)


class JsonStore:
    """
    مخزن JSON عالي المستوى مع تحديثات جزئية آمنة.

    مثال:
        store = JsonStore('my_data.json', defaults={'score': 0})
        store.get('score', 10)
        store.update(score=42)
        store.data['x'] = 1; store.save()
    """

    def __init__(self, filename: str, defaults: Optional[Dict] = None):
        self.path = get_data_path(filename)
        self._lock = _lock_for(self.path)
        loaded = read_json(self.path, None)
        if not isinstance(loaded, dict):
            loaded = {}
        self._data = dict(defaults or {})
        self._data.update(loaded)

    @property
    def data(self) -> Dict:
        return self._data

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._data.get(key, fallback)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, **kwargs) -> None:
        self._data.update(kwargs)

    def save(self) -> bool:
        return atomic_write_json(self.path, self._data)

    def reload(self) -> None:
        loaded = read_json(self.path, None)
        if isinstance(loaded, dict):
            with self._lock:
                self._data = loaded
