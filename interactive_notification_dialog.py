#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
حوار الإشعار التفاعلي - BatteryGuardAI

يظهر عندما لا تدعم إشعارات النظام أزراراً تفاعلية. يحمل نفس عالم لوحة
القياس: لوحة داكنة، حرف ملوّن يحمل الأولوية، أيقونات مرسومة، نصوص مترجمة.
"""

import logging

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
                             QLabel, QPushButton, QVBoxLayout)

import icons
import theme
from i18n import t

logger = logging.getLogger('BatteryGuard')

#: مهلة الإغلاق التلقائي (ملي ثانية) حين لا يتفاعل المستخدم
AUTO_CLOSE_MS = 30000

#: أيقونة كل أولوية من نظام الأيقونات المرسومة
URGENCY_ICONS = {
    'critical': 'alert',
    'high': 'alert',
    'normal': 'bell',
    'low': 'bell',
    'success': 'check',
    'info': 'info',
}


class InteractiveNotificationDialog(QDialog):
    """حوار تذكير مع ثلاثة إجراءات صريحة: إيقاف، غفوة، كتم"""

    stop_clicked = pyqtSignal(str)
    snooze_clicked = pyqtSignal(str)
    mute_clicked = pyqtSignal(str)

    def __init__(self, title: str, message: str, reminder_type: str,
                 urgency: str = 'normal', parent=None):
        super().__init__(parent)
        self.reminder_type = reminder_type
        self.urgency = urgency

        self._build(title, message)
        self._apply_style()

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )

        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.accept)
        self.auto_close_timer.start(AUTO_CLOSE_MS)

    # ── البناء ──────────────────────────────────────────────

    def _build(self, title: str, message: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_3)
        layout.setContentsMargins(theme.SPACE_5, theme.SPACE_4,
                                  theme.SPACE_5, theme.SPACE_4)

        accent = theme.URGENCY_COLORS.get(self.urgency, theme.STATE_MAINS)

        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_3)

        mark = QLabel()
        mark.setPixmap(icons.pixmap(URGENCY_ICONS.get(self.urgency, 'bell'), 22, accent))
        mark.setFixedWidth(24)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(mark)

        title_label = QLabel(title)
        title_label.setFont(theme.font(theme.SIZE_SECTION, 700))
        title_label.setWordWrap(True)
        header.addWidget(title_label, 1)
        layout.addLayout(header)

        rule = QFrame()
        rule.setFixedHeight(theme.BORDER_HAIRLINE)
        rule.setStyleSheet(f"background-color: {theme.HAIRLINE};")
        layout.addWidget(rule)

        message_label = QLabel(message)
        message_label.setFont(theme.font(theme.SIZE_BODY, 500))
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"color: {theme.INK};")
        layout.addWidget(message_label)
        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(theme.SPACE_2)
        for key, role, icon_name, handler in (
            ('notify.action.stop', 'danger', 'stop', self._on_stop),
            ('notify.action.snooze', 'neutral', 'snooze', self._on_snooze),
            ('notify.action.mute', 'neutral', 'mute', self._on_mute),
        ):
            button = QPushButton(t(key))
            button.setFont(theme.font(theme.SIZE_LABEL, 600))
            button.setMinimumHeight(34)
            button.setIcon(icons.icon(icon_name, 15, theme.INK))
            button.setStyleSheet(theme.button_style(role))
            button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)

        keep = QPushButton(t('notify.action.details'))
        keep.setFont(theme.font(theme.SIZE_LABEL, 600))
        keep.setMinimumHeight(30)
        keep.setStyleSheet(theme.button_style('quiet'))
        keep.clicked.connect(self.accept)
        layout.addWidget(keep)

        self.setMinimumWidth(420)
        self.setMaximumWidth(560)

    def _apply_style(self) -> None:
        accent = theme.URGENCY_COLORS.get(self.urgency, theme.STATE_MAINS)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.PANEL};
                border: {theme.BORDER_HAIRLINE}px solid {accent};
                border-radius: {theme.RADIUS_PLATE}px;
            }}
            QLabel {{ color: {theme.INK}; background: transparent; }}
        """)

    # ── الإجراءات ───────────────────────────────────────────

    def _on_stop(self) -> None:
        self.stop_clicked.emit(self.reminder_type)
        self.accept()

    def _on_snooze(self) -> None:
        self.snooze_clicked.emit(self.reminder_type)
        self.accept()

    def _on_mute(self) -> None:
        self.mute_clicked.emit(self.reminder_type)
        self.accept()

    def showEvent(self, event):
        """يظهر في وسط الشاشة النشطة"""
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(geometry.center().x() - self.width() // 2,
                  geometry.center().y() - self.height() // 2)
