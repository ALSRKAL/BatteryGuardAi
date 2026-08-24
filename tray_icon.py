#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إدارة أيقونة صينية النظام المحسّنة"""

import sys
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QBrush, QLinearGradient
from PyQt6.QtCore import Qt, QRect

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')


class BatteryTrayIcon:
    """أيقونة صينية النظام المحسّنة مع رسومات متقدمة"""
    
    def __init__(self, parent):
        self.parent = parent
        self.tray_icon = QSystemTrayIcon(parent)
        self.current_percent = 0
        self.is_charging = False
        self.health_score = 100
        
        # ذاكرة مؤقتة للأيقونات حسب (شريحة النسبة، حالة الشحن)
        # لتجنب إعادة الرسم الكامل كل ثانيتين
        self._icon_cache = {}
        
        self.create_menu()
        self.update_icon(0, False)
        self.tray_icon.activated.connect(self.on_activated)
        self.tray_icon.show()
    
    def create_menu(self):
        """إنشاء القائمة - يجب الاحتفاظ بمرجعها حتى لا يدمّرها جامع النفايات"""
        self.menu = QMenu(self.parent)
        menu = self.menu
        
        # عرض النافذة
        show_action = menu.addAction("🔋 عرض النافذة")
        show_action.triggered.connect(self.parent.show_window)
        
        menu.addSeparator()
        
        # معلومات الحالة
        self.status_action = menu.addAction("📊 الحالة: --")
        self.status_action.setEnabled(False)
        
        self.health_action = menu.addAction("💚 الصحة: 100%")
        self.health_action.setEnabled(False)
        
        self.time_action = menu.addAction("⏱️ الوقت: --")
        self.time_action.setEnabled(False)
        
        menu.addSeparator()
        
        # إجراءات سريعة
        optimize_action = menu.addAction("🚀 تحسين الآن")
        optimize_action.triggered.connect(self.parent.run_optimization)
        
        menu.addSeparator()
        
        # إنهاء
        quit_action = menu.addAction("❌ إنهاء البرنامج")
        quit_action.triggered.connect(self.parent.quit_application)
        
        self.tray_icon.setContextMenu(menu)
    
    def update_icon(self, percent: int, is_charging: bool, health: int = 100):
        """تحديث الأيقونة مع تخزين مؤقت حسب (شريحة النسبة، الشحن)"""
        self.current_percent = percent
        self.is_charging = is_charging
        self.health_score = health
        
        # شريحة 5% تكفي للتمييز البصري وتزيد نسبة إصابة الكاش
        cache_key = (percent // 5, bool(is_charging))
        
        if cache_key not in self._icon_cache:
            pixmap = self._render_battery_pixmap(percent, is_charging)
            self._icon_cache[cache_key] = QIcon(pixmap)
            # منع نمو الكاش بلا حدود
            if len(self._icon_cache) > 60:
                self._icon_cache.clear()
                self._icon_cache[cache_key] = QIcon(pixmap)
        
        icon = self._icon_cache[cache_key]
        self.tray_icon.setIcon(icon)
        
        # تحديث التلميح المحسّن
        status = "⚡ جارٍ الشحن" if is_charging else "🔋 يعمل على البطارية"
        health_status = f"💚 الصحة: {health}%"
        tooltip = f"BatteryGuard Pro\n{percent}% - {status}\n{health_status}"
        self.tray_icon.setToolTip(tooltip)
        
        # تحديث القائمة
        if hasattr(self, 'status_action'):
            self.status_action.setText(f"📊 الحالة: {percent}% - {status}")
        if hasattr(self, 'health_action'):
            health_emoji = "💚" if health >= 80 else "💛" if health >= 60 else "❤️"
            self.health_action.setText(f"{health_emoji} الصحة: {health}%")
    
    def _render_battery_pixmap(self, percent: int, is_charging: bool) -> QPixmap:
        """رسم أيقونة البطارية"""
        size = 128
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # تحديد الألوان حسب النسبة
        if percent >= 80:
            main_color = QColor(16, 185, 129)  # أخضر
            glow_color = QColor(16, 185, 129, 100)
        elif percent >= 40:
            main_color = QColor(59, 130, 246)  # أزرق
            glow_color = QColor(59, 130, 246, 100)
        elif percent >= 20:
            main_color = QColor(251, 191, 36)  # أصفر
            glow_color = QColor(251, 191, 36, 100)
        else:
            main_color = QColor(239, 68, 68)  # أحمر
            glow_color = QColor(239, 68, 68, 100)
        
        # رسم توهج خلفي
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow_color)
        painter.drawEllipse(10, 10, size-20, size-20)
        
        # رسم البطارية بتدرج لوني
        battery_rect = QRect(20, 35, 88, 58)
        gradient = QLinearGradient(
            battery_rect.left(), battery_rect.top(),
            battery_rect.left(), battery_rect.bottom()
        )
        gradient.setColorAt(0, main_color.lighter(120))
        gradient.setColorAt(1, main_color)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 150), 3))
        painter.drawRoundedRect(battery_rect, 8, 8)
        
        # رأس البطارية
        head_rect = QRect(108, 50, 8, 28)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(head_rect, 3, 3)
        
        # مستوى البطارية الداخلي
        if percent > 0:
            fill_width = int((battery_rect.width() - 12) * (percent / 100))
            fill_rect = QRect(battery_rect.x() + 6, battery_rect.y() + 6, 
                            fill_width, battery_rect.height() - 12)
            
            fill_gradient = QLinearGradient(
                fill_rect.left(), fill_rect.top(),
                fill_rect.left(), fill_rect.bottom()
            )
            fill_gradient.setColorAt(0, main_color.lighter(140))
            fill_gradient.setColorAt(1, main_color.darker(110))
            
            painter.setBrush(QBrush(fill_gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(fill_rect, 4, 4)
        
        # رسم النسبة بخط واضح
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 28, QFont.Weight.Bold)
        painter.setFont(font)
        
        # ظل للنص
        painter.setPen(QColor(0, 0, 0, 100))
        painter.drawText(battery_rect.adjusted(2, 2, 2, 2), 
                        Qt.AlignmentFlag.AlignCenter, str(percent))
        
        # النص الأساسي
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(battery_rect, Qt.AlignmentFlag.AlignCenter, str(percent))
        
        # رمز الشحن
        if is_charging:
            painter.setPen(QColor(251, 191, 36))
            painter.setFont(QFont("Arial", 36, QFont.Weight.Bold))
            painter.drawText(0, 0, size, size, 
                           Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, "⚡")
        
        # مؤشر الصحة (إذا كانت منخفضة)
        if self.health_score < 80:
            painter.setPen(QColor(239, 68, 68))
            painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            painter.drawText(0, 0, size, size, 
                           Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, "⚠")
        
        painter.end()
        return pixmap
    
    def update_time_remaining(self, time_str: str):
        """تحديث الوقت المتبقي في القائمة"""
        if hasattr(self, 'time_action'):
            self.time_action.setText(f"⏱️ الوقت: {time_str}")
    
    def on_activated(self, reason):
        """معالجة النقر على الأيقونة"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.parent.isVisible():
                self.parent.hide()
            else:
                self.parent.show_window()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.parent.show_window()
    
    def show_message(self, title: str, message: str, icon=QSystemTrayIcon.MessageIcon.Information):
        """عرض رسالة محسّنة"""
        self.tray_icon.showMessage(title, message, icon, 5000)
    
    def show_smart_notification(self, notification_type: str, data: dict):
        """عرض إشعار ذكي من الأيقونة"""
        icons = {
            'critical': QSystemTrayIcon.MessageIcon.Critical,
            'warning': QSystemTrayIcon.MessageIcon.Warning,
            'info': QSystemTrayIcon.MessageIcon.Information
        }
        
        icon = icons.get(notification_type, QSystemTrayIcon.MessageIcon.Information)
        title = data.get('title', 'BatteryGuard Pro')
        message = data.get('message', '')
        
        self.show_message(title, message, icon)
    
    def hide(self):
        """إخفاء الأيقونة"""
        self.tray_icon.hide()
