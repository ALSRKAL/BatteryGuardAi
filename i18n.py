#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
طبقة الترجمة الموحدة - BatteryGuardAI

مصدر واحد لكل نص يراه المستخدم: لا نصوص مكتوبة داخل منطق الواجهة.
الملفات في `locales/<lang>.json`، والمفاتيح مسطّحة بنقاط (`status.title`).

الاستخدام:
    from i18n import t, set_language
    set_language('ar')
    t('status.charging_from_mains')
    t('advice.high_soc_dwell', hours=6, loss=20)

قواعد:
- كل نص جديد في الواجهة يمرّ عبر `t()` ويُضاف مفتاحه إلى ar.json و en.json.
- المفتاح المفقود يُسجَّل مرة واحدة ويُعاد كما هو بدل الانهيار.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger('BatteryGuard')

try:
    from resource_path import get_resource_path
except ImportError:  # pragma: no cover - وضع تطوير بديل
    def get_resource_path(relative: str) -> Path:
        return Path(__file__).parent / relative

DEFAULT_LANGUAGE = 'ar'
RTL_LANGUAGES = frozenset({'ar', 'fa', 'he', 'ur'})

_lock = threading.RLock()
_catalogs: Dict[str, Dict[str, str]] = {}
_current_language = DEFAULT_LANGUAGE
_missing_keys: set = set()


def _locales_dir() -> Path:
    return Path(get_resource_path('locales'))


def available_languages() -> List[str]:
    """رموز اللغات المتوفرة فعلاً كملفات ترجمة"""
    try:
        return sorted(p.stem for p in _locales_dir().glob('*.json'))
    except OSError as e:
        logger.debug(f"i18n: تعذّر سرد ملفات الترجمة: {e}")
        return [DEFAULT_LANGUAGE]


def _load_catalog(language: str) -> Dict[str, str]:
    """تحميل ملف ترجمة واحد مع تخزين مؤقت"""
    with _lock:
        cached = _catalogs.get(language)
        if cached is not None:
            return cached

        path = _locales_dir() / f'{language}.json'
        catalog: Dict[str, str] = {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                catalog = {str(k): str(v) for k, v in raw.items() if isinstance(v, (str, int, float))}
            else:
                logger.warning(f"i18n: {path.name} ليس كائن JSON - تم تجاهله")
        except FileNotFoundError:
            logger.warning(f"i18n: ملف الترجمة غير موجود: {path}")
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"i18n: تعذّر تحميل {path.name}: {e}")

        _catalogs[language] = catalog
        return catalog


def set_language(language: Optional[str]) -> str:
    """تعيين لغة الواجهة؛ يعيد اللغة المستخدمة فعلاً"""
    global _current_language
    lang = (language or DEFAULT_LANGUAGE).strip().lower()
    if not _load_catalog(lang):
        if lang != DEFAULT_LANGUAGE:
            logger.warning(f"i18n: اللغة '{lang}' غير متوفرة - الرجوع إلى '{DEFAULT_LANGUAGE}'")
        lang = DEFAULT_LANGUAGE
        _load_catalog(lang)
    with _lock:
        _current_language = lang
    return lang


def get_language() -> str:
    return _current_language


def is_rtl(language: Optional[str] = None) -> bool:
    """هل اللغة تُقرأ من اليمين إلى اليسار"""
    return (language or _current_language) in RTL_LANGUAGES


def t(key: str, **params: Any) -> str:
    """
    ترجمة مفتاح مع تعويض المعاملات.

    الترتيب: اللغة الحالية ← العربية ← المفتاح نفسه.
    لا يرمي استثناءً أبداً: نص ناقص أفضل من واجهة منهارة.
    """
    catalog = _load_catalog(_current_language)
    template = catalog.get(key)

    if template is None and _current_language != DEFAULT_LANGUAGE:
        template = _load_catalog(DEFAULT_LANGUAGE).get(key)

    if template is None:
        if key not in _missing_keys:
            _missing_keys.add(key)
            logger.warning(f"i18n: مفتاح ترجمة مفقود: {key}")
        return key

    if not params:
        return template
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"i18n: معاملات ناقصة للمفتاح {key}: {e}")
        return template


def missing_keys() -> List[str]:
    """المفاتيح التي طُلبت ولم تُوجد (للتشخيص والاختبارات)"""
    return sorted(_missing_keys)


def reload_catalogs() -> None:
    """إعادة تحميل ملفات الترجمة (مفيد للاختبارات وتغيير اللغة أثناء التشغيل)"""
    with _lock:
        _catalogs.clear()
        _missing_keys.clear()
