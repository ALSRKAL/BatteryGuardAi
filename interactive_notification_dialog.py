#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نافذة حوار تفاعلية للإشعارات المتكررة
تظهر عندما لا تدعم الإشعارات الأزرار التفاعلية
"""

import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWidget, QApplication)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor

# استيراد نظام الألوان الموحد
from app_colors import (
    get_notification_colors, get_button_style,
    PRIMARY, SUCCESS, WARNING, DANGER,
    GRAY_200, GRAY_500, GRAY_600, WHITE
)


class InteractiveNotificationDialog(QDialog):
    """نافذة حوار تفاعلية للإشعارات"""
    
    # إشارات للتواصل مع مدير الإشعارات
    stop_clicked = pyqtSignal(str)      # إيقاف نهائي
    snooze_clicked = pyqtSignal(str)    # غفوة
    mute_clicked = pyqtSignal(str)      # كتم الصوت
    
    def __init__(self, title: str, message: str, reminder_type: str, 
                 urgency: str = 'normal', parent=None):
        super().__init__(parent)
        
        self.reminder_type = reminder_type
        self.urgency = urgency
        
        self.setup_ui(title, message)
        self.setup_style()
        
        # جعل النافذة دائماً في المقدمة
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        
        # إغلاق تلقائي بعد 30 ثانية إذا لم يتفاعل المستخدم
        self.auto_close_timer = QTimer()
        self.auto_close_timer.timeout.connect(self.auto_close)
        self.auto_close_timer.start(30000)  # 30 ثانية
    
    def setup_ui(self, title: str, message: str):
        """إعداد واجهة المستخدم"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # الأيقونة والعنوان
        header_layout = QHBoxLayout()
        
        # أيقونة حسب الأولوية
        icon_label = QLabel()
        icon_text = self._get_icon_text()
        icon_label.setText(icon_text)
        icon_label.setFont(QFont('Arial', 32))
        header_layout.addWidget(icon_label)
        
        # العنوان
        title_label = QLabel(title)
        title_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"color: {WHITE};")
        header_layout.addWidget(title_label, 1)
        
        layout.addLayout(header_layout)
        
        # خط فاصل
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet(f"background-color: rgba(255, 255, 255, 0.2);")
        layout.addWidget(separator)
        
        # الرسالة
        message_label = QLabel(message)
        message_label.setFont(QFont('Arial', 11))
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        message_label.setStyleSheet(f"color: {WHITE};")
        layout.addWidget(message_label)
        
        # مساحة فارغة
        layout.addStretch()
        
        # نص توضيحي
        info_label = QLabel("اختر إجراء:")
        info_label.setFont(QFont('Arial', 10))
        info_label.setStyleSheet(f"color: rgba(255, 255, 255, 0.8);")
        layout.addWidget(info_label)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        # زر الإيقاف النهائي
        stop_btn = QPushButton("⏹️ إيقاف نهائي")
        stop_btn.setFont(QFont('Arial', 10))
        stop_btn.setMinimumHeight(40)
        stop_btn.clicked.connect(self.on_stop_clicked)
        stop_btn.setStyleSheet(get_button_style('danger'))
        buttons_layout.addWidget(stop_btn)
        
        # زر الغفوة
        snooze_btn = QPushButton("😴 غفوة 10 دقائق")
        snooze_btn.setFont(QFont('Arial', 10))
        snooze_btn.setMinimumHeight(40)
        snooze_btn.clicked.connect(self.on_snooze_clicked)
        snooze_btn.setStyleSheet(get_button_style('primary'))
        buttons_layout.addWidget(snooze_btn)
        
        # زر كتم الصوت
        mute_btn = QPushButton("🔇 كتم الصوت")
        mute_btn.setFont(QFont('Arial', 10))
        mute_btn.setMinimumHeight(40)
        mute_btn.clicked.connect(self.on_mute_clicked)
        mute_btn.setStyleSheet(get_button_style('warning'))
        buttons_layout.addWidget(mute_btn)
        
        layout.addLayout(buttons_layout)
        
        # زر الاستمرار (إغلاق فقط)
        continue_btn = QPushButton("✅ استمرار (سيتكرر التنبيه)")
        continue_btn.setFont(QFont('Arial', 9))
        continue_btn.setMinimumHeight(35)
        continue_btn.clicked.connect(self.accept)
        continue_btn.setStyleSheet(get_button_style('success'))
        layout.addWidget(continue_btn)
        
        self.setLayout(layout)
        self.setMinimumWidth(450)
        self.setMaximumWidth(600)
    
    def setup_style(self):
        """تطبيق الأنماط - خلفية أزرق غامق مع حدود ملونة"""
        # الحصول على ألوان الإشعار حسب الأولوية
        colors = get_notification_colors(self.urgency)
        
        # خلفية أزرق غامق موحدة
        bg_color = "#1e3a5f"  # أزرق غامق
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 3px solid {colors['border']};
                border-radius: 12px;
            }}
        """)
    
    def _get_icon_text(self) -> str:
        """الحصول على أيقونة حسب الأولوية"""
        if self.urgency == 'critical':
            return "🚨"
        elif self.urgency == 'high':
            return "⚠️"
        else:
            return "🔔"
    
    def on_stop_clicked(self):
        """معالجة نقر زر الإيقاف النهائي"""
        self.stop_clicked.emit(self.reminder_type)
        self.accept()
    
    def on_snooze_clicked(self):
        """معالجة نقر زر الغفوة"""
        self.snooze_clicked.emit(self.reminder_type)
        self.accept()
    
    def on_mute_clicked(self):
        """معالجة نقر زر كتم الصوت"""
        self.mute_clicked.emit(self.reminder_type)
        self.accept()
    
    def auto_close(self):
        """إغلاق تلقائي بعد انتهاء الوقت"""
        self.accept()
    
    def showEvent(self, event):
        """عند إظهار النافذة، ضعها في وسط الشاشة"""
        super().showEvent(event)
        
        # وضع النافذة في وسط الشاشة
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)


# اختبار سريع
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    dialog = InteractiveNotificationDialog(
        title="🚨 تحذير - بطارية منخفضة جداً!",
        message="البطارية 8%! وصّل الشاحن فوراً لتجنب إيقاف الجهاز.\n\nهذا التنبيه سيتكرر كل دقيقة حتى تتخذ إجراء.",
        reminder_type="battery_critical",
        urgency="critical"
    )
    
    # ربط الإشارات
    dialog.stop_clicked.connect(lambda t: print(f"إيقاف نهائي: {t}"))
    dialog.snooze_clicked.connect(lambda t: print(f"غفوة: {t}"))
    dialog.mute_clicked.connect(lambda t: print(f"كتم: {t}"))
    
    dialog.exec()
    
    sys.exit(0)
