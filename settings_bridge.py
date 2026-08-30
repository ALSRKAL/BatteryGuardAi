#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
جسر الإعدادات - BatteryGuardAI

يحوّل `QSettings` إلى دالة قراءة بسيطة `reader(key, default, kind)` تفهمها
`default_settings.guard_settings_from`.

سبب وجوده: لوحة القياس ومتحكّم الخلفية يحتاجان **نفس** الإعدادات، لكن أحدهما
يعمل بلا واجهة. جمع القراءة هنا يمنع نسختين من منطق القراءة تنحرف إحداهما عن
الأخرى فتختلف سياسة الحارس بين تشغيل بنافذة وتشغيل بلا نافذة، وهو خلاف لا
يلاحظه المستخدم ولا يفهم سببه.
"""

import logging
from typing import Any, Callable, Dict

from PyQt6.QtCore import QSettings

from default_settings import (APP_NAME, APP_ORG, get_default_settings,
                              guard_settings_from)

logger = logging.getLogger('BatteryGuard')


def qsettings_reader(settings: QSettings) -> Callable[[str, Any, type], Any]:
    """
    دالة قراءة من `QSettings` مع تحويل نوعي صريح.

    `QSettings` على لينكس يحفظ كل شيء نصاً، فقراءة قيمة منطقية بلا `type=bool`
    تعيد النص `'false'` وهو صادق منطقياً — خطأ صامت يقلب معنى كل إعداد.
    """
    def read(key: str, default: Any, kind: type) -> Any:
        try:
            if kind is bool:
                return bool(settings.value(key, bool(default), type=bool))
            if kind is int:
                return int(settings.value(key, int(default or 0), type=int))
            if kind is float:
                return float(settings.value(key, float(default or 0.0), type=float))
            value = settings.value(key, default if default is not None else '',
                                   type=str)
            return '' if value is None else str(value)
        except (TypeError, ValueError) as e:
            logger.debug(f"إعداد غير صالح {key} ({e}) - سيُستخدم الافتراضي")
            return default
    return read


def dict_reader(data: Dict) -> Callable[[str, Any, type], Any]:
    """دالة قراءة من قاموس عادي (تستخدمها الاختبارات ووضع بلا Qt)"""
    def read(key: str, default: Any, kind: type) -> Any:
        value = data.get(key, default)
        try:
            if kind is bool:
                return bool(value)
            if kind is int:
                return int(value)
            if kind is float:
                return float(value)
            return '' if value is None else str(value)
        except (TypeError, ValueError):
            return default
    return read


def effective_settings() -> Dict:
    """
    الإعدادات الفعّالة كاملة: الافتراضات المركزية، فوقها ما حفظه المستخدم.

    هذه هي التي يستخدمها وضع الخلفية: لا واجهة تُقرأ منها، فالمصدر هو
    `QSettings` نفسه الذي تكتب فيه لوحة القياس.
    """
    settings = QSettings(APP_ORG, APP_NAME)
    merged = get_default_settings()
    reader = qsettings_reader(settings)

    # المفاتيح المنطقية والرقمية العامة التي يحتاجها خيط المراقبة والإشعارات
    for key, default in list(merged.items()):
        if key.startswith(('guard_', 'attribution_')):
            continue
        if isinstance(default, bool):
            merged[key] = reader(key, default, bool)
        elif isinstance(default, int) and not isinstance(default, bool):
            merged[key] = reader(key, default, int)
        elif isinstance(default, float):
            merged[key] = reader(key, default, float)

    merged.update(guard_settings_from(reader))

    # حدود البطارية بالشكل الذي يتوقّعه خيط المراقبة ومدير الإشعارات
    merged['battery_thresholds'] = {
        'critical_low': reader('critical_battery', 10, int),
        'low': reader('low_battery_threshold', 20, int),
        'optimal_min': reader('min_charge_limit', 40, int),
        'optimal_max': reader('max_charge_limit', 80, int),
        'high': reader('high_battery', 90, int),
        'full': reader('full_battery', 95, int),
    }
    merged['low_battery_threshold'] = merged['battery_thresholds']['low']
    merged['enable_notifications'] = merged.get('notifications_enabled', True)
    merged['enable_sounds'] = merged.get('sounds_enabled', True)
    merged['enable_reminders'] = merged.get('reminders_enabled', True)
    return merged
