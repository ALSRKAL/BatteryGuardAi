#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خيط المراقبة الخلفي"""

import time
import logging
from typing import Dict
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger('BatteryGuard')


class MonitorThread(QThread):
    """خيط المراقبة الخلفي"""
    
    battery_updated = pyqtSignal(dict)
    notification_requested = pyqtSignal(str, str, str)
    
    def __init__(self, monitor, ai, settings: Dict):
        super().__init__()
        self.monitor = monitor
        self.ai = ai
        self.settings = settings
        self.running = True
        self.last_notification_time = {}
        
    def run(self):
        """تشغيل المراقبة المستمرة"""
        while self.running:
            try:
                battery_status = self.monitor.get_battery_status()
                
                if battery_status['available']:
                    self.ai.analyze_usage_pattern(battery_status)
                    self.check_and_notify(battery_status)
                    
                    # التحقق من حدود الشحن
                    charge_action = self.monitor.check_charge_limits(
                        battery_status['percent'],
                        battery_status['is_charging']
                    )
                    
                    if charge_action['action'] != 'none' and charge_action.get('should_notify'):
                        self.notification_requested.emit(
                            "⚡ التحكم في الشحن",
                            charge_action['message'],
                            'normal'
                        )
                    
                    self.battery_updated.emit(battery_status)
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"خطأ في خيط المراقبة: {e}")
                time.sleep(30)
    
    def check_and_notify(self, battery_status: Dict):
        """التحقق وإرسال الإشعارات المطلوبة"""
        percent = battery_status['percent']
        is_charging = battery_status['is_charging']
        current_time = time.time()
        
        if self.settings.get('notify_low_battery', True):
            low_threshold = self.settings.get('low_battery_threshold', 20)
            if percent <= low_threshold and not is_charging:
                if self._should_notify('low_battery', current_time, 300):
                    self.notification_requested.emit(
                        "⚠️ تحذير البطارية",
                        f"البطارية منخفضة ({percent}%)! يرجى توصيل الشاحن.",
                        'critical'
                    )
        
        if self.settings.get('notify_charge_suggested', True):
            charge_threshold = self.settings.get('charge_threshold', 40)
            if percent <= charge_threshold and not is_charging:
                if self._should_notify('charge_suggested', current_time, 600):
                    self.notification_requested.emit(
                        "🔋 توصية الشحن",
                        f"البطارية عند {percent}%. يُنصح بتوصيل الشاحن للحفاظ على صحة البطارية.",
                        'normal'
                    )
        
        if self.settings.get('notify_unplug_suggested', True):
            unplug_threshold = self.settings.get('unplug_threshold', 80)
            if percent >= unplug_threshold and is_charging:
                if self._should_notify('unplug_suggested', current_time, 600):
                    self.notification_requested.emit(
                        "✓ اكتمل الشحن الأمثل",
                        f"البطارية عند {percent}%. يمكن فصل الشاحن للحفاظ على عمر البطارية.",
                        'normal'
                    )
        
        if self.settings.get('notify_full_charge', True):
            if percent >= 95 and is_charging:
                if self._should_notify('full_charge', current_time, 1800):
                    self.notification_requested.emit(
                        "✓ البطارية ممتلئة",
                        f"البطارية مشحونة بالكامل ({percent}%). افصل الشاحن لتجنب الشحن الزائد.",
                        'low'
                    )
    
    def _should_notify(self, notification_type: str, current_time: float, cooldown: int) -> bool:
        """التحقق من إمكانية إرسال الإشعار (منع التكرار)"""
        last_time = self.last_notification_time.get(notification_type, 0)
        if current_time - last_time >= cooldown:
            self.last_notification_time[notification_type] = current_time
            return True
        return False
    
    def stop(self):
        """إيقاف خيط المراقبة"""
        self.running = False
