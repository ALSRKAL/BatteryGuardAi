#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ويدجت البطارية المتحرك"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QBrush


class AnimatedBatteryWidget(QWidget):
    """ويدجت بطارية متحرك مع تأثير الماء"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 300)
        self._battery_level = 0
        self._wave_offset = 0
        self._is_charging = False
        
        # أنيميشن الموجة
        self.wave_timer = QTimer()
        self.wave_timer.timeout.connect(self.update_wave)
        self.wave_timer.start(50)
        
        # أنيميشن التعبئة
        self.fill_animation = QPropertyAnimation(self, b"battery_level")
        self.fill_animation.setDuration(800)
        self.fill_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    @pyqtProperty(int)
    def battery_level(self):
        return self._battery_level
    
    @battery_level.setter
    def battery_level(self, value):
        self._battery_level = value
        self.update()
    
    def set_battery_level(self, level: int, is_charging: bool):
        """تعيين مستوى البطارية مع أنيميشن"""
        self._is_charging = is_charging
        if not self.isVisible():
            # تحديث مباشر بدون أنيميشن عند الإخفاء
            self.battery_level = level
            return
        self.fill_animation.stop()
        self.fill_animation.setStartValue(self._battery_level)
        self.fill_animation.setEndValue(level)
        self.fill_animation.start()

    def showEvent(self, event):
        """استئناف الأنيميشن عند الظهور"""
        super().showEvent(event)
        if not self.wave_timer.isActive():
            self.wave_timer.start(50)

    def hideEvent(self, event):
        """إيقاف الأنيميشن عند الإخفاء لتوفير المعالج والبطارية"""
        super().hideEvent(event)
        self.wave_timer.stop()
    
    def update_wave(self):
        """تحديث موجة الماء"""
        self._wave_offset += 2
        if self._wave_offset > 360:
            self._wave_offset = 0
        self.update()
    
    def paintEvent(self, event):
        """رسم البطارية"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # حساب أبعاد البطارية
        battery_width = min(width * 0.6, 150)
        battery_height = min(height * 0.7, 250)
        battery_x = (width - battery_width) / 2
        battery_y = (height - battery_height) / 2 + 20
        
        # رسم رأس البطارية
        head_width = battery_width * 0.3
        head_height = 15
        head_x = battery_x + (battery_width - head_width) / 2
        head_y = battery_y - head_height
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(58, 58, 92))
        painter.drawRoundedRect(int(head_x), int(head_y), int(head_width), int(head_height), 5, 5)
        
        # رسم إطار البطارية
        painter.setPen(QPen(QColor(58, 58, 92), 4))
        painter.setBrush(QColor(15, 52, 96))
        painter.drawRoundedRect(int(battery_x), int(battery_y), int(battery_width), int(battery_height), 15, 15)
        
        # حساب مستوى التعبئة
        fill_height = (battery_height - 10) * (self._battery_level / 100)
        fill_y = battery_y + battery_height - fill_height - 5
        
        # تحديد اللون حسب المستوى
        if self._battery_level >= 80:
            color1 = QColor(16, 185, 129)
            color2 = QColor(5, 150, 105)
        elif self._battery_level >= 40:
            color1 = QColor(59, 130, 246)
            color2 = QColor(37, 99, 235)
        elif self._battery_level >= 20:
            color1 = QColor(251, 191, 36)
            color2 = QColor(245, 158, 11)
        else:
            color1 = QColor(239, 68, 68)
            color2 = QColor(220, 38, 38)
        
        # رسم التعبئة مع تدرج
        if self._battery_level > 0:
            gradient = QLinearGradient(0, fill_y, 0, battery_y + battery_height)
            gradient.setColorAt(0, color1)
            gradient.setColorAt(1, color2)
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            
            # رسم مع تأثير الموجة
            import math
            from PyQt6.QtGui import QPainterPath
            
            path = QPainterPath()
            wave_amplitude = 8
            wave_length = 40
            
            # بداية المسار
            path.moveTo(battery_x + 5, fill_y)
            
            # رسم الموجة العلوية
            for x in range(int(battery_x + 5), int(battery_x + battery_width - 5), 2):
                wave_x = (x - battery_x) / wave_length * 2 * math.pi + math.radians(self._wave_offset)
                wave_y = fill_y + math.sin(wave_x) * wave_amplitude
                path.lineTo(x, wave_y)
            
            # إكمال الشكل
            path.lineTo(battery_x + battery_width - 5, battery_y + battery_height - 5)
            path.lineTo(battery_x + 5, battery_y + battery_height - 5)
            path.closeSubpath()
            
            painter.setClipRect(int(battery_x + 5), int(battery_y + 5), 
                              int(battery_width - 10), int(battery_height - 10))
            painter.drawPath(path)
            painter.setClipping(False)
        
        # رسم النسبة المئوية
        painter.setPen(QColor(255, 255, 255))
        from PyQt6.QtGui import QFont
        font = QFont("Arial", 32, QFont.Weight.Bold)
        painter.setFont(font)
        text = f"{self._battery_level}%"
        painter.drawText(int(battery_x), int(battery_y), int(battery_width), int(battery_height),
                        Qt.AlignmentFlag.AlignCenter, text)
        
        # رسم رمز الشحن
        if self._is_charging:
            painter.setPen(QColor(251, 191, 36))
            font = QFont("Arial", 40, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(int(battery_x), int(battery_y - 60), int(battery_width), 50,
                           Qt.AlignmentFlag.AlignCenter, "⚡")
