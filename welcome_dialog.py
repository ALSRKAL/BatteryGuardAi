#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نافذة التعريف الأولى - BatteryGuardAI

الإصدار السابق كان صفحة تمرير فيها أربعون سطراً من التعداد النقطي بخلفية
فاتحة وخط Arial وإيموجي، داخل تطبيق عربي داكن. لم يكن يُقرأ: من يفتح تطبيقاً
لأول مرة لا يقرأ دليل استخدام، ومن يقرأه لا يتذكّره.

هذا الإصدار يجيب على ثلاثة أسئلة فقط، بثلاث بطاقات، بلا تمرير:

1. **ماذا يفعل؟** يقيس الإجهاد الفعلي على البطارية ويقلّله حيث يسمح العتاد.
2. **ماذا يستطيع على *جهازك أنت*؟** طبقة القدرة تُقرأ من العتاد الآن لا
   تُوعَد. جهاز بلا مسار كتابة يُقال له ذلك في أول شاشة، لا بعد أسبوع من
   الانتظار.
3. **ماذا لن يفعله بلا إذنك؟** لا يوقف عملية، ولا يقطع بلوتوث، ولا يلمس
   شاشة خارجية، ولا يرفع سطوعاً أنت أنزلته.

الباقي يُكتشف بالاستخدام، وهذا أفضل من قائمة تُنسى.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QFrame,
                             QGridLayout, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout)

import icons
import theme
from dialogs import fit_wrapped_labels
from i18n import is_rtl, t

logger = logging.getLogger('BatteryGuard')

#: رمز الخروج الذي يعني «افتح الإعدادات» (يقرؤه `main`)
RESULT_OPEN_SETTINGS = 2

#: طبقة القدرة ← (مفتاح العنوان، مفتاح الشرح، لون الحالة)
TIER_PRESENTATION = {
    'hardware_control': ('tier.hardware_control', 'welcome.tier_control_body',
                         theme.STATE_OK),
    'firmware_setting': ('tier.firmware_setting', 'welcome.tier_firmware_body',
                         theme.STATE_WARN),
    'notify_only': ('tier.notify_only', 'welcome.tier_notify_body',
                    theme.STATE_DEAD),
}


class WelcomeDialog(QDialog):
    """نافذة التعريف: ثلاث بطاقات وإجراءان"""

    def __init__(self, parent=None, capability=None):
        """
        `capability` كائن قدرات العتاد (`hardware_capability`). إن لم يُمرَّر
        يُقرأ مباشرة: أول شاشة يراها المستخدم يجب أن تقول حقيقة جهازه لا
        نصاً عاماً.
        """
        super().__init__(parent)
        self._capability = capability or self._probe_capability(parent)

        self.setWindowTitle(t('welcome.title'))
        self.setModal(True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if is_rtl()
                                else Qt.LayoutDirection.LeftToRight)
        self.setMinimumWidth(560)
        self.setMaximumWidth(680)

        self._build()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.WINDOW};
                border: {theme.BORDER_HAIRLINE}px solid {theme.HAIRLINE_STRONG};
                border-radius: {theme.RADIUS_PLATE}px;
            }}
            QLabel {{ color: {theme.INK}; background: transparent; }}
        """)

    # ── قراءة قدرات الجهاز ──────────────────────────────────

    @staticmethod
    def _probe_capability(parent):
        """قدرات العتاد من النافذة الأم إن وُجدت، وإلا بفحص مباشر"""
        monitor = getattr(parent, 'monitor', None)
        if monitor is not None and getattr(monitor, 'capability', None) is not None:
            return monitor.capability
        try:
            import hardware_capability as hw
            return hw.probe()
        except Exception as e:
            logger.debug(f"ترحيب: تعذّر فحص القدرات: {e}")
            return None

    # ── البناء ──────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_5, theme.SPACE_5,
                                  theme.SPACE_5, theme.SPACE_4)
        layout.setSpacing(theme.SPACE_4)

        layout.addLayout(self._header())
        layout.addWidget(self._what_it_does())
        layout.addWidget(self._what_your_machine_supports())
        layout.addWidget(self._what_it_never_does())

        rule = QFrame()
        rule.setFixedHeight(theme.BORDER_HAIRLINE)
        rule.setStyleSheet(f"background-color: {theme.HAIRLINE};")
        layout.addWidget(rule)

        self.dont_show_again = QCheckBox(t('welcome.dont_show_again'))
        self.dont_show_again.setFont(theme.font(theme.SIZE_LABEL, 500))
        layout.addWidget(self.dont_show_again)

        actions = QHBoxLayout()
        actions.setSpacing(theme.SPACE_2)
        actions.addStretch(1)

        settings_button = QPushButton(t('welcome.open_settings'))
        settings_button.setFont(theme.font(theme.SIZE_LABEL, 600))
        settings_button.setMinimumHeight(34)
        settings_button.setStyleSheet(theme.button_style('quiet'))
        settings_button.clicked.connect(self.open_settings)
        actions.addWidget(settings_button)

        start_button = QPushButton(t('welcome.start'))
        start_button.setFont(theme.font(theme.SIZE_LABEL, 600))
        start_button.setMinimumHeight(34)
        start_button.setMinimumWidth(140)
        start_button.setDefault(True)
        start_button.setStyleSheet(theme.button_style('live'))
        start_button.clicked.connect(self.accept)
        actions.addWidget(start_button)
        layout.addLayout(actions)

    def _header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_3)

        mark = QLabel()
        mark.setPixmap(icons.pixmap('battery', 30, theme.PHOSPHOR))
        mark.setFixedWidth(34)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(mark)

        titles = QVBoxLayout()
        titles.setSpacing(theme.SPACE_1)

        title = QLabel(t('welcome.title'))
        title.setStyleSheet(theme.font_css(theme.SIZE_TITLE, 700,
                                           color=theme.INK))
        titles.addWidget(title)

        tagline = QLabel(t('app.tagline'))
        tagline.setStyleSheet(theme.font_css(theme.SIZE_LABEL, 500,
                                             color=theme.INK_DIM))
        tagline.setWordWrap(True)
        titles.addWidget(tagline)

        header.addLayout(titles, 1)
        return header

    # ── البطاقات الثلاث ─────────────────────────────────────

    def _what_it_does(self) -> QFrame:
        return self._card('welcome.does_title', theme.PHOSPHOR, [
            ('gauge', t('welcome.does_measure')),
            ('chart', t('welcome.does_learn')),
            ('shield', t('welcome.does_protect')),
        ])

    def _what_your_machine_supports(self) -> QFrame:
        """طبقة القدرة المقروءة من العتاد، لا وعد عام"""
        tier = getattr(self._capability, 'tier', None) or 'notify_only'
        title_key, body_key, accent = TIER_PRESENTATION.get(
            tier, TIER_PRESENTATION['notify_only'])

        from hardware_capability import device_name
        device = device_name(getattr(self._capability, 'vendor', '') or '',
                             getattr(self._capability, 'product', '') or '')

        rows: List[Tuple[str, str]] = [('crosshair', t(title_key)),
                                       ('info', t(body_key))]
        if device:
            rows.insert(0, ('shield', device))
        return self._card('welcome.machine_title', accent, rows)

    def _what_it_never_does(self) -> QFrame:
        return self._card('welcome.never_title', theme.STATE_DEAD, [
            ('blocked', t('welcome.never_processes')),
            ('blocked', t('welcome.never_radio')),
            ('blocked', t('welcome.never_display')),
            ('blocked', t('welcome.never_brightness')),
        ])

    def _card(self, title_key: str, accent: str,
              rows: List[Tuple[str, str]]) -> QFrame:
        """
        صفيحة معنونة بحرف ملوّن وصفوف بأيقونة ونص.

        الصفوف في `QGridLayout` لا في عناصر مغلَّفة: النص الملفوف داخل عنصر
        مغلَّف يعطي ارتفاع سطر واحد فيتراكب سطره الثاني على الصف التالي، وهي
        علّة تخطيط قديمة في Qt تحلّها الشبكة لأنها تحترم `heightForWidth`.
        """
        plate = QFrame()
        plate.setProperty('role', 'plate')
        plate.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.PANEL};
                border: {theme.BORDER_HAIRLINE}px solid {theme.HAIRLINE};
                border-right: {theme.DETENT_WIDTH}px solid {accent};
                border-radius: {theme.RADIUS_PLATE}px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        grid = QGridLayout(plate)
        grid.setContentsMargins(theme.SPACE_4, theme.SPACE_3,
                                theme.SPACE_4, theme.SPACE_3)
        grid.setHorizontalSpacing(theme.SPACE_2)
        grid.setVerticalSpacing(theme.SPACE_2)
        grid.setColumnStretch(1, 1)

        legend = QLabel(t(title_key))
        legend.setStyleSheet(
            theme.font_css(theme.SIZE_LEGEND, 600, color=theme.INK_FAINT,
                           tracking=theme.TRACKING_LEGEND))
        grid.addWidget(legend, 0, 0, 1, 2)

        for index, (icon_name, text) in enumerate(rows, start=1):
            mark = QLabel()
            mark.setPixmap(icons.pixmap(icon_name, 14, accent))
            mark.setFixedWidth(18)
            grid.addWidget(mark, index, 0, Qt.AlignmentFlag.AlignTop)

            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet(theme.font_css(theme.SIZE_LABEL, 500,
                                               color=theme.INK))
            grid.addWidget(label, index, 1)
        return plate

    # ── النتيجة ─────────────────────────────────────────────

    def open_settings(self) -> None:
        self.done(RESULT_OPEN_SETTINGS)

    def should_show_again(self) -> bool:
        return not self.dont_show_again.isChecked()

    def showEvent(self, event):
        """
        ضبط ارتفاع النصوص الملفوفة بعد أن يُعرف العرض.

        بلا هذا يُقصّ السطر الثاني من كل نص طويل: التخطيط يمنحه ارتفاع سطر
        واحد لأن `QGridLayout` لا يستشير `heightForWidth`.
        """
        super().showEvent(event)
        layout = self.layout()
        if layout is not None:
            layout.activate()
        fit_wrapped_labels(self)
        self.adjustSize()


if __name__ == '__main__':  # pragma: no cover - تجربة سريعة
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.stylesheet())
    dialog = WelcomeDialog()
    print('result:', dialog.exec(), 'show again:', dialog.should_show_again())
