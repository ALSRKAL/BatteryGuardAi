#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
واجهة التحكم في الشحن - تفويض مباشر للنظام المتقدم

ملاحظة معمارية: كان هذا الملف يحتوي سابقاً على تطبيق قديم موازٍ
(~700 سطر) لا يُنفذ أبداً لأن AdvancedChargeController متاح دائماً
في نفس المستودع. أصبح الآن غلافاً رفيعاً يفوض كل العمليات له،
مع إبقاء الواجهة العامة (enable_control/disable_control/
check_and_control/get_status) كما هي للتوافق.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

from charge_control_advanced import AdvancedChargeController

logger = logging.getLogger('BatteryGuard')


class ChargeController:
    """التحكم الفعلي في الشحن عبر المنصات"""

    def __init__(self, sudo_password=None):
        self.is_active = False
        self.max_charge_limit = 80
        self.min_charge_limit = 40
        self.sudo_password = sudo_password
        self.last_action = None
        self.last_action_time = 0.0

        self._advanced = AdvancedChargeController(sudo_password)
        if self._advanced.available_methods:
            self.control_method = self._advanced.available_methods[0]
        else:
            self.control_method = 'none'
        logger.info(
            f"نظام التحكم المتقدم - الطرق المتاحة: "
            f"{', '.join(self._advanced.available_methods) or 'لا شيء'}"
        )

    def set_sudo_password(self, password: str):
        """تعيين كلمة مرور sudo لـ Linux"""
        self.sudo_password = password
        self._advanced.set_sudo_password(password)

    def enable_control(self, min_limit: int, max_limit: int) -> Tuple[bool, str]:
        """تفعيل التحكم في الشحن"""
        self.min_charge_limit = min_limit
        self.max_charge_limit = max_limit
        self.is_active = True
        return self._advanced.enable_control(min_limit, max_limit)

    def disable_control(self) -> Tuple[bool, str]:
        """إيقاف التحكم في الشحن"""
        self.is_active = False
        return self._advanced.disable_control()

    def check_and_control(self, current_percent: int, is_charging: bool) -> Optional[Dict]:
        """فحص والتحكم في الشحن بناءً على المستوى الحالي"""
        if not self.is_active:
            return None
        return self._advanced.check_and_control(current_percent, is_charging)

    def get_status(self) -> Dict:
        """الحصول على حالة التحكم"""
        return {
            'is_active': self.is_active,
            'control_method': self.control_method,
            'max_limit': self.max_charge_limit,
            'min_limit': self.min_charge_limit,
            'last_action': self.last_action,
            'can_control': self.control_method != 'none',
        }
