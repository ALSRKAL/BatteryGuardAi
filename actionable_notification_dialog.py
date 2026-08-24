#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نافذة إشعارات قابلة للتنفيذ مع أزرار إجراءات
"""

import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWidget, QApplication, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

# استيراد نظام الألوان
try:
    from app_colors import (get_notification_colors, get_button_style, 
                           PRIMARY, SUCCESS, WARNING, DANGER, GRAY_500)
except ImportError:
    # قيم افتراضية إذا لم يكن متاحاً
    PRIMARY = "#3b82f6"
    SUCCESS = "#10b981"
    WARNING = "#f97316"
    DANGER = "#ef4444"
    GRAY_500 = "#6b7280"
    
    def get_notification_colors(urgency):
        return {
            'bg': '#ffffff',
            'border': PRIMARY,
            'text': '#111827'
        }
    
    def get_button_style(style):
        return ""


class ActionableNotificationDialog(QDialog):
    """نافذة إشعار مع أزرار إجراءات"""
    
    # إشارات للإجراءات
    action_clicked = pyqtSignal(str, str)  # (notification_type, action)
    dismissed = pyqtSignal(str)  # (notification_type)
    
    def __init__(self, title: str, message: str, notification_type: str,
                 actions: list = None, urgency: str = 'normal', 
                 auto_dismiss: int = 0, parent=None):
        """
        Args:
            title: عنوان الإشعار
            message: نص الإشعار
            notification_type: نوع الإشعار (high_consumption, ai_suggestion, etc.)
            actions: قائمة الإجراءات [(text, action_id, style), ...]
            urgency: الأولوية (normal, high, critical)
            auto_dismiss: إغلاق تلقائي بعد ثواني (0 = لا يغلق)
            parent: النافذة الأم
        """
        super().__init__(parent)
        
        self.notification_type = notification_type
        self.urgency = urgency
        self.actions = actions or []
        self.auto_dismiss_time = auto_dismiss
        
        self.setup_ui(title, message)
        self.setup_style()
        
        # جعل النافذة دائماً في المقدمة
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        
        # إغلاق تلقائي
        if auto_dismiss > 0:
            self.auto_dismiss_timer = QTimer()
            self.auto_dismiss_timer.timeout.connect(self.auto_dismiss)
            self.auto_dismiss_timer.start(auto_dismiss * 1000)
            
            self.remaining_time = auto_dismiss
            self.countdown_timer = QTimer()
            self.countdown_timer.timeout.connect(self.update_countdown)
            self.countdown_timer.start(1000)
    
    def setup_ui(self, title: str, message: str):
        """إعداد واجهة المستخدم"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # الأيقونة والعنوان
        header_layout = QHBoxLayout()
        
        # أيقونة
        icon_label = QLabel()
        icon_text = self._get_icon_text()
        icon_label.setText(icon_text)
        icon_label.setFont(QFont('Arial', 28))
        header_layout.addWidget(icon_label)
        
        # العنوان
        title_label = QLabel(title)
        title_label.setFont(QFont('Arial', 13, QFont.Weight.Bold))
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label, 1)
        
        # زر الإغلاق
        close_btn = QPushButton("✕")
        close_btn.setFont(QFont('Arial', 14))
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.dismiss)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #666;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
                border-radius: 15px;
                color: #000;
            }
        """)
        header_layout.addWidget(close_btn)
        
        layout.addLayout(header_layout)
        
        # الرسالة
        message_label = QLabel(message)
        message_label.setFont(QFont('Arial', 10))
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #4b5563; padding: 5px 0;")
        layout.addWidget(message_label)
        
        # أزرار الإجراءات
        if self.actions:
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(10)
            
            for action_text, action_id, style in self.actions:
                btn = QPushButton(action_text)
                btn.setFont(QFont('Arial', 10))
                btn.setMinimumHeight(35)
                btn.clicked.connect(lambda checked, aid=action_id: self.on_action(aid))
                
                # تطبيق الأنماط من نظام الألوان الموحد
                btn.setStyleSheet(get_button_style(style))
                
                actions_layout.addWidget(btn)
            
            layout.addLayout(actions_layout)
        
        # شريط العد التنازلي
        if self.auto_dismiss_time > 0:
            self.countdown_label = QLabel(f"سيتم الإغلاق خلال {self.auto_dismiss_time} ثانية")
            self.countdown_label.setFont(QFont('Arial', 8))
            self.countdown_label.setStyleSheet("color: #9ca3af;")
            self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.countdown_label)
            
            self.progress_bar = QProgressBar()
            self.progress_bar.setMaximum(self.auto_dismiss_time)
            self.progress_bar.setValue(self.auto_dismiss_time)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setFixedHeight(3)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    background-color: #e5e7eb;
                    border-radius: 1px;
                }
                QProgressBar::chunk {
                    background-color: #3b82f6;
                    border-radius: 1px;
                }
            """)
            layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
        self.setMinimumWidth(400)
        self.setMaximumWidth(500)
    
    def setup_style(self):
        """تطبيق الأنماط - ألوان احترافية"""
        colors = get_notification_colors(self.urgency)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                border: 2px solid {colors['border']};
                border-radius: 12px;
            }}
        """)
    
    def _get_icon_text(self) -> str:
        """الحصول على أيقونة"""
        icons = {
            'high_consumption': '⚡',
            'ai_suggestion': '🤖',
            'battery_low': '🔋',
            'battery_critical': '🚨',
            'optimization': '🚀',
            'health_warning': '💊',
        }
        return icons.get(self.notification_type, '💡')
    
    def on_action(self, action_id: str):
        """معالجة نقر زر إجراء"""
        self.action_clicked.emit(self.notification_type, action_id)
        self.accept()
    
    def dismiss(self):
        """إغلاق الإشعار"""
        self.dismissed.emit(self.notification_type)
        self.reject()
    
    def auto_dismiss(self):
        """إغلاق تلقائي"""
        self.dismiss()
    
    def update_countdown(self):
        """تحديث العد التنازلي"""
        self.remaining_time -= 1
        if hasattr(self, 'countdown_label'):
            self.countdown_label.setText(f"سيتم الإغلاق خلال {self.remaining_time} ثانية")
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(self.remaining_time)
    
    def showEvent(self, event):
        """عند إظهار النافذة"""
        super().showEvent(event)
        
        # وضع النافذة في الزاوية السفلية اليمنى
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 20
        y = screen.height() - self.height() - 60
        self.move(x, y)


# أمثلة على الإشعارات القابلة للتنفيذ

def show_high_consumption_notification(parent=None):
    """إشعار استهلاك عالي"""
    dialog = ActionableNotificationDialog(
        title="⚡ استهلاك طاقة عالي",
        message="استهلاك الطاقة الحالي 25W - أعلى من المعتاد.\nيمكن توفير حتى 40% من الطاقة.",
        notification_type="high_consumption",
        actions=[
            ("🚀 حسّن الآن", "optimize", "primary"),
            ("📊 عرض التفاصيل", "details", "secondary"),
            ("⏭️ تجاهل", "dismiss", "secondary"),
        ],
        urgency="high",
        auto_dismiss=15,
        parent=parent
    )
    return dialog


def show_ai_suggestion_notification(parent=None):
    """إشعار اقتراح ذكي"""
    dialog = ActionableNotificationDialog(
        title="🤖 اقتراح ذكي",
        message="لاحظنا أنك تستخدم الجهاز بكثافة الآن.\nننصح بتقليل السطوع إلى 60% لتوفير الطاقة.",
        notification_type="ai_suggestion",
        actions=[
            ("✅ تطبيق", "apply", "success"),
            ("⚙️ تخصيص", "customize", "secondary"),
            ("❌ رفض", "reject", "secondary"),
        ],
        urgency="normal",
        auto_dismiss=20,
        parent=parent
    )
    return dialog


def show_optimization_complete_notification(parent=None):
    """إشعار اكتمال التحسين"""
    dialog = ActionableNotificationDialog(
        title="✅ اكتمل التحسين",
        message="تم تحسين النظام بنجاح!\nتوفير متوقع: 35% من الطاقة",
        notification_type="optimization",
        actions=[
            ("📊 عرض النتائج", "results", "primary"),
            ("👍 حسناً", "ok", "secondary"),
        ],
        urgency="normal",
        auto_dismiss=10,
        parent=parent
    )
    return dialog


# اختبار
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # اختبار استهلاك عالي
    dialog = show_high_consumption_notification()
    
    dialog.action_clicked.connect(
        lambda ntype, action: print(f"✅ إجراء: {action} على {ntype}")
    )
    dialog.dismissed.connect(
        lambda ntype: print(f"❌ تم إغلاق: {ntype}")
    )
    
    dialog.exec()
    
    sys.exit(0)
