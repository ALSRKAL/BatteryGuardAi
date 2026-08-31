#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تذكير البطارية - BatteryGuardAI

الإصدار السابق كان نافذة في وسط الشاشة، فيها أربعة أزرار متساوية الوزن،
والمعلومة الأهم (نسبة الشحن) مدفونة في سطر نص صغير. النتيجة أن المستخدم
يقرأ الأزرار قبل أن يقرأ سبب ظهورها، وأن النافذة تتوسّط عمله وتسرق التركيز.

هذا الإصدار:

- **الرقم أولاً**: نسبة الشحن قراءة كبيرة بأرقام أحادية العرض. سبب ظهور
  التذكير يُقرأ في لمحة بلا قراءة نص.
- **شريط الأولوية على الحرف**: الحالة تُقرأ بلون وأيقونة ونص معاً، لا بلون
  وحده.
- **إجراء أساسي واحد**: «حسناً» يغلق. الإيقاف والغفوة والكتم أزرار هادئة،
  لأن أخطرها (الإيقاف النهائي للتذكير) لا يجوز أن يكون أسهلها.
- **زاوية الشاشة لا وسطها**، وبلا سرقة تركيز: التذكير لا يقطع عملاً جارياً.
- **العدّاد ظاهر**: المستخدم يرى أن النافذة ستغلق نفسها بدل أن يظنّها معلّقة.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
                             QLabel, QPushButton, QVBoxLayout, QWidget)

import icons
import theme
from i18n import is_rtl, t

logger = logging.getLogger('BatteryGuard')

#: مهلة الإغلاق التلقائي (ثانية) حين لا يتفاعل المستخدم
AUTO_CLOSE_SECONDS = 30

#: هامش النافذة عن حرف الشاشة (بكسل)
SCREEN_MARGIN = 24

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
    """تذكير بإجراء أساسي واحد وثلاثة إجراءات هادئة"""

    stop_clicked = pyqtSignal(str)
    snooze_clicked = pyqtSignal(str)
    mute_clicked = pyqtSignal(str)

    def __init__(self, title: str, message: str, reminder_type: str,
                 urgency: str = 'normal', readout: str = '', parent=None):
        """`readout` القراءة الكبيرة (نسبة الشحن مثلاً). فارغة تعني بلا رقم."""
        super().__init__(parent)
        self.reminder_type = reminder_type
        self.urgency = urgency
        self._remaining = AUTO_CLOSE_SECONDS

        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if is_rtl()
                                else Qt.LayoutDirection.LeftToRight)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._build(title, message, readout)
        self._apply_style()

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)
        self._countdown.start()

    # ── البناء ──────────────────────────────────────────────

    @property
    def _accent(self) -> str:
        return theme.URGENCY_COLORS.get(self.urgency, theme.STATE_MAINS)

    def _build(self, title: str, message: str, readout: str) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # شريط الأولوية: عرضه ثابت، ولونه هو المعلومة الأولى في المحيط البصري
        band = QFrame()
        band.setFixedWidth(4)
        band.setStyleSheet(f"background-color: {self._accent}; border: none;")
        outer.addWidget(band)

        body = QWidget()
        body.setStyleSheet('border: none; background: transparent;')
        layout = QVBoxLayout(body)
        layout.setContentsMargins(theme.SPACE_4, theme.SPACE_3,
                                  theme.SPACE_4, theme.SPACE_3)
        layout.setSpacing(theme.SPACE_3)
        outer.addWidget(body, 1)

        layout.addLayout(self._header(title, readout))

        text = QLabel(message)
        text.setFont(theme.font(theme.SIZE_LABEL, 500))
        text.setWordWrap(True)
        text.setStyleSheet(f"color: {theme.INK_DIM}; border: none;")
        layout.addWidget(text)

        rule = QFrame()
        rule.setFixedHeight(theme.BORDER_HAIRLINE)
        rule.setStyleSheet(f"background-color: {theme.HAIRLINE}; border: none;")
        layout.addWidget(rule)
        layout.addLayout(self._actions())

        self.setFixedWidth(400)

    def _header(self, title: str, readout: str) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_3)

        if readout:
            # القراءة الكبيرة: الرقم هو سبب ظهور التذكير، فيأخذ وزنه البصري.
            # الحجم عبر CSS لا `setFont`: ورقة أنماط التطبيق تتجاوز الثاني.
            number = QLabel(readout)
            number.setStyleSheet(
                theme.font_css(theme.SIZE_READOUT_SM, 700, mono=True,
                               color=self._accent) + ' border: none;')
            number.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            header.addWidget(number)
        else:
            mark = QLabel()
            mark.setPixmap(icons.pixmap(
                URGENCY_ICONS.get(self.urgency, 'bell'), 24, self._accent))
            mark.setFixedWidth(28)
            mark.setAlignment(Qt.AlignmentFlag.AlignTop)
            header.addWidget(mark)

        column = QVBoxLayout()
        column.setSpacing(2)

        heading = QLabel(title)
        heading.setWordWrap(True)
        heading.setStyleSheet(
            theme.font_css(theme.SIZE_BODY, 700, color=theme.INK) + ' border: none;')
        column.addWidget(heading)

        self.countdown_label = QLabel(
            t('notify.auto_close', seconds=self._remaining))
        self.countdown_label.setStyleSheet(
            theme.font_css(theme.SIZE_LEGEND, 600, color=theme.INK_FAINT,
                           tracking=theme.TRACKING_LEGEND) + ' border: none;')
        column.addWidget(self.countdown_label)

        header.addLayout(column, 1)
        return header

    def _actions(self) -> QHBoxLayout:
        """إجراء أساسي واحد، والباقي هادئ: الأخطر لا يكون الأسهل"""
        actions = QHBoxLayout()
        actions.setSpacing(theme.SPACE_2)

        for key, icon_name, handler in (
            ('notify.action.snooze', 'snooze', self._on_snooze),
            ('notify.action.mute', 'mute', self._on_mute),
            ('notify.action.stop', 'stop', self._on_stop),
        ):
            button = QPushButton(t(key))
            button.setFont(theme.font(theme.SIZE_LABEL, 600))
            button.setMinimumHeight(30)
            button.setIcon(icons.icon(icon_name, 14, theme.INK_DIM))
            button.setStyleSheet(theme.button_style('quiet'))
            button.clicked.connect(handler)
            actions.addWidget(button)

        actions.addStretch(1)

        acknowledge = QPushButton(t('action.ok'))
        acknowledge.setFont(theme.font(theme.SIZE_LABEL, 600))
        acknowledge.setMinimumHeight(30)
        acknowledge.setMinimumWidth(88)
        acknowledge.setStyleSheet(theme.button_style('primary'))
        acknowledge.clicked.connect(self.accept)
        actions.addWidget(acknowledge)
        return actions

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.PANEL};
                border: {theme.BORDER_HAIRLINE}px solid {theme.HAIRLINE_STRONG};
                border-radius: {theme.RADIUS_PLATE}px;
            }}
        """)

    # ── العدّاد ─────────────────────────────────────────────

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._countdown.stop()
            self.accept()
            return
        self.countdown_label.setText(
            t('notify.auto_close', seconds=self._remaining))

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

    # ── الموضع ──────────────────────────────────────────────

    def showEvent(self, event):
        """
        زاوية الشاشة السفلية في جهة القراءة، لا وسط الشاشة.

        الوسط يقطع ما ينظر إليه المستخدم؛ والزاوية هي المكان الذي تعلّم كل
        مستخدم أن يتوقّع فيه إشعاراً.
        """
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        y = area.bottom() - self.height() - SCREEN_MARGIN
        x = (area.left() + SCREEN_MARGIN if is_rtl()
             else area.right() - self.width() - SCREEN_MARGIN)
        self.move(max(area.left(), x), max(area.top(), y))
