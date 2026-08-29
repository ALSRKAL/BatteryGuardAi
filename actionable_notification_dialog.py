#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
حوار إشعار بإجراءات - BatteryGuardAI

إشعار يظهر في زاوية الشاشة ويحمل إجراءات قابلة للتنفيذ. نفس عالم لوحة
القياس: لوحة داكنة، حرف ملوّن للأولوية، أيقونات مرسومة، وعدّ تنازلي صريح
حين يكون الإغلاق تلقائياً.
"""

import logging
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QProgressBar, QPushButton, QVBoxLayout)

import icons
import theme
from i18n import t

logger = logging.getLogger('BatteryGuard')

#: أيقونة كل نوع إشعار من نظام الأيقونات المرسومة
TYPE_ICONS = {
    'high_consumption': 'bolt',
    'ai_suggestion': 'info',
    'battery_low': 'battery_low',
    'battery_critical': 'alert',
    'optimization': 'gauge',
    'health_warning': 'pulse',
    'charging': 'plug',
    'general': 'bell',
}


class ActionableNotificationDialog(QDialog):
    """إشعار بإجراءات: كل إجراء زر واضح، والإغلاق التلقائي معلن"""

    action_clicked = pyqtSignal(str, str)
    dismissed = pyqtSignal(str)

    def __init__(self, title: str, message: str, notification_type: str,
                 actions: Optional[List[Tuple[str, str, str]]] = None,
                 urgency: str = 'normal', auto_dismiss: int = 0, parent=None):
        """
        actions: [(نص الزر، معرّف الإجراء، دور النمط)]
        auto_dismiss: ثوانٍ حتى الإغلاق التلقائي (0 = لا يُغلق تلقائياً)
        """
        super().__init__(parent)
        self.notification_type = notification_type
        self.urgency = urgency
        self.actions = actions or []
        self.auto_dismiss_time = max(0, int(auto_dismiss))
        self.remaining_time = self.auto_dismiss_time

        self._build(title, message)
        self._apply_style()

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )

        if self.auto_dismiss_time > 0:
            self.countdown_timer = QTimer(self)
            self.countdown_timer.timeout.connect(self._tick)
            self.countdown_timer.start(1000)

    # ── البناء ──────────────────────────────────────────────

    def _build(self, title: str, message: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_3)
        layout.setContentsMargins(theme.SPACE_4, theme.SPACE_3,
                                  theme.SPACE_4, theme.SPACE_3)

        accent = theme.URGENCY_COLORS.get(self.urgency, theme.STATE_MAINS)

        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_3)

        mark = QLabel()
        mark.setPixmap(icons.pixmap(
            TYPE_ICONS.get(self.notification_type, 'bell'), 20, accent))
        mark.setFixedWidth(22)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(mark)

        title_label = QLabel(title)
        title_label.setFont(theme.font(theme.SIZE_SECTION, 700))
        title_label.setWordWrap(True)
        header.addWidget(title_label, 1)

        close_button = QPushButton()
        close_button.setIcon(icons.icon('close', 14, theme.INK_DIM))
        close_button.setFixedSize(26, 26)
        close_button.setStyleSheet(theme.button_style('quiet'))
        close_button.setToolTip(t('notify.action.stop'))
        close_button.clicked.connect(self.dismiss)
        header.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        message_label = QLabel(message)
        message_label.setFont(theme.font(theme.SIZE_BODY, 500))
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"color: {theme.INK_DIM};")
        layout.addWidget(message_label)

        if self.actions:
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(theme.SPACE_2)
            for action_text, action_id, style in self.actions:
                button = QPushButton(action_text)
                button.setFont(theme.font(theme.SIZE_LABEL, 600))
                button.setMinimumHeight(30)
                button.setStyleSheet(theme.button_style(style))
                button.clicked.connect(
                    lambda _checked=False, aid=action_id: self._on_action(aid))
                actions_layout.addWidget(button)
            layout.addLayout(actions_layout)

        if self.auto_dismiss_time > 0:
            self.countdown_label = QLabel(self._countdown_text())
            self.countdown_label.setFont(theme.legend_font(10))
            self.countdown_label.setStyleSheet(f"color: {theme.INK_FAINT};")
            self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.countdown_label)

            self.progress_bar = QProgressBar()
            self.progress_bar.setMaximum(self.auto_dismiss_time)
            self.progress_bar.setValue(self.auto_dismiss_time)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setFixedHeight(3)
            layout.addWidget(self.progress_bar)

        self.setMinimumWidth(380)
        self.setMaximumWidth(480)

    def _apply_style(self) -> None:
        accent = theme.URGENCY_COLORS.get(self.urgency, theme.STATE_MAINS)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.PANEL};
                border: {theme.BORDER_HAIRLINE}px solid {accent};
                border-radius: {theme.RADIUS_PLATE}px;
            }}
            QLabel {{ color: {theme.INK}; background: transparent; }}
            QProgressBar {{
                background-color: {theme.PANEL_SUNKEN};
                border: none;
                border-radius: 1px;
            }}
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 1px;
            }}
        """)

    def _countdown_text(self) -> str:
        return t('notify.auto_close', seconds=max(0, self.remaining_time))

    # ── السلوك ──────────────────────────────────────────────

    def _tick(self) -> None:
        """العدّ التنازلي المعلن، ثم إغلاق واحد فقط"""
        self.remaining_time -= 1
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(max(0, self.remaining_time))
        if hasattr(self, 'countdown_label'):
            self.countdown_label.setText(self._countdown_text())
        if self.remaining_time <= 0:
            self.countdown_timer.stop()
            self.dismiss()

    def _on_action(self, action_id: str) -> None:
        self.action_clicked.emit(self.notification_type, action_id)
        self.accept()

    def dismiss(self) -> None:
        """إغلاق الإشعار وإبلاغ المدير حتى لا يُعاد فوراً"""
        self.dismissed.emit(self.notification_type)
        self.reject()

    def showEvent(self, event):
        """يظهر في الزاوية السفلية من الشاشة النشطة، بلا تغطية للمهام"""
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        margin = theme.SPACE_5
        x = area.left() + margin if self.isRightToLeft() else \
            area.right() - self.width() - margin
        self.move(x, area.bottom() - self.height() - margin)
