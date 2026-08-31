#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
الحوارات - BatteryGuardAI

مصدر واحد لكل نافذة منبثقة في التطبيق. وُلد هذا الملف لأن الواجهة كانت
تستخدم `QMessageBox` في ثمانية مواضع: نافذة يرسمها النظام بخلفية فاتحة
وأزرار «Yes / No» لاتينية من اليسار إلى اليمين، داخل تطبيق عربي داكن كامل
الاتجاه من اليمين إلى اليسار. كانت تبدو كأنها من برنامج آخر، وكانت نصوصها
مكتوبة داخل منطق الواجهة بلا مفتاح ترجمة.

القواعد:
- لا لون ولا مقاس ولا خط هنا: كل شيء من `theme`.
- لا نص مكتوب: كل نص من `i18n`، والمُنادي يمرّر نصاً مترجماً أو مفتاحاً.
- الاتجاه من `i18n.is_rtl()`، وترتيب الأزرار يتبعه: الإجراء الأساسي أولاً
  في اتجاه القراءة.
- الشدّة تُقرأ بثلاثة أشياء معاً: أيقونة، وحرف ملوّن، ونص. لا باللون وحده،
  حتى تُقرأ الحالة على شاشة رمادية أو بعين لا تفرّق الأحمر من الأخضر.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QVBoxLayout,
                             QWidget)

import icons
import theme
from i18n import is_rtl, t

logger = logging.getLogger('BatteryGuard')

#: شدّة الحوار ← (أيقونة، لون الحرف)
SEVERITY: dict = {
    'info': ('info', theme.STATE_MAINS),
    'success': ('check', theme.STATE_OK),
    'warning': ('alert', theme.STATE_WARN),
    'danger': ('alert', theme.STATE_CRITICAL),
    'question': ('info', theme.STATE_MAINS),
}

#: أقصى عرض للحوار: السطر الطويل لا يُقرأ
MAX_WIDTH = 520


def fit_wrapped_labels(root: QWidget) -> None:
    """
    ضبط الحدّ الأدنى لارتفاع كل نص ملفوف داخل `root`.

    Qt لا يحسب ارتفاع النص الملفوف حساباً موثوقاً داخل التخطيطات: دعم
    `heightForWidth` ناقص في `QGridLayout`، فيُخصَّص للنص ارتفاع سطر واحد
    ويُقصّ سطره الثاني بلا خطأ ولا تحذير. الأثر مرئي فقط، ولذلك يمرّ في
    المراجعة: نص ناقص يبدو نصاً قصيراً.

    تُستدعى بعد أن يُعرف العرض (من `showEvent` أو بعد `activate()`).
    """
    from PyQt6.QtWidgets import QLabel
    for label in root.findChildren(QLabel):
        if not label.wordWrap():
            continue
        width = label.width()
        if width <= 0:
            continue
        needed = label.heightForWidth(width)
        if needed > 0 and label.minimumHeight() < needed:
            label.setMinimumHeight(needed)


class MessageDialog(QDialog):
    """
    حوار رسالة واحدة: أيقونة الشدّة، عنوان، نص، وصف أزرار.

    يُستخدم عبر الدوال القصيرة أسفل الملف (`inform`، `confirm`، …) ولا
    يُنشأ مباشرة إلا عند الحاجة إلى أزرار غير قياسية.
    """

    def __init__(self, title: str, message: str, severity: str = 'info',
                 buttons: Sequence[Tuple[str, str, bool]] = (),
                 detail: str = '', parent: Optional[QWidget] = None):
        """
        `buttons`: تسلسل من (النص، دور الزر في `theme`، هل هو الإجراء المؤكِّد).
        الترتيب في القائمة هو ترتيب القراءة، وQt تعكسه تلقائياً في RTL.
        """
        super().__init__(parent)
        self._confirmed = False
        self.setWindowTitle(title)
        self.setModal(True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if is_rtl()
                                else Qt.LayoutDirection.LeftToRight)

        icon_name, accent = SEVERITY.get(severity, SEVERITY['info'])
        self._build(title, message, detail, icon_name, accent,
                    buttons or ((t('action.ok'), 'primary', True),))
        self._apply_style(accent)

    # ── البناء ──────────────────────────────────────────────

    def _build(self, title: str, message: str, detail: str, icon_name: str,
               accent: str, buttons: Sequence[Tuple[str, str, bool]]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_5, theme.SPACE_4,
                                  theme.SPACE_5, theme.SPACE_4)
        layout.setSpacing(theme.SPACE_3)

        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_3)

        mark = QLabel()
        mark.setPixmap(icons.pixmap(icon_name, 22, accent))
        mark.setFixedWidth(24)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(mark)

        heading = QLabel(title)
        heading.setStyleSheet(theme.font_css(theme.SIZE_SECTION, 700,
                                            color=theme.INK))
        heading.setWordWrap(True)
        header.addWidget(heading, 1)
        layout.addLayout(header)

        rule = QFrame()
        rule.setFixedHeight(theme.BORDER_HAIRLINE)
        rule.setStyleSheet(f"background-color: {theme.HAIRLINE};")
        layout.addWidget(rule)

        body = QLabel(message)
        body.setStyleSheet(theme.font_css(theme.SIZE_BODY, 500, color=theme.INK))
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        if detail:
            note = QLabel(detail)
            note.setStyleSheet(theme.font_css(theme.SIZE_LABEL, 500,
                                             color=theme.INK_DIM))
            note.setWordWrap(True)
            layout.addWidget(note)

        layout.addSpacing(theme.SPACE_2)

        actions = QHBoxLayout()
        actions.setSpacing(theme.SPACE_2)
        actions.addStretch(1)
        for text, role, confirming in buttons:
            button = QPushButton(text)
            button.setFont(theme.font(theme.SIZE_LABEL, 600))
            button.setMinimumHeight(34)
            button.setMinimumWidth(104)
            button.setStyleSheet(theme.button_style(role))
            if confirming:
                button.setDefault(True)
                button.clicked.connect(self._on_confirm)
            else:
                button.clicked.connect(self.reject)
            actions.addWidget(button)
        layout.addLayout(actions)

        self.setMinimumWidth(360)
        self.setMaximumWidth(MAX_WIDTH)

    def _apply_style(self, accent: str) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.PANEL};
                border: {theme.BORDER_HAIRLINE}px solid {accent};
                border-radius: {theme.RADIUS_PLATE}px;
            }}
            QLabel {{ color: {theme.INK}; background: transparent; }}
        """)

    # ── النتيجة ─────────────────────────────────────────────

    def showEvent(self, event):
        """ضبط ارتفاع النصوص الملفوفة بعد أن يُعرف العرض الفعلي"""
        super().showEvent(event)
        fit_wrapped_labels(self)
        self.adjustSize()

    def _on_confirm(self) -> None:
        self._confirmed = True
        self.accept()

    @property
    def confirmed(self) -> bool:
        return self._confirmed


class PasswordDialog(QDialog):
    """
    طلب كلمة مرور، بنفس عالم اللوحة وبتعليل صريح لسبب الطلب.

    الحوار يذكر ما سيُفعل بالصلاحية: مطالبة بكلمة مرور بلا سبب معروف تدرّب
    المستخدم على إدخالها لأي نافذة تطلبها، وذلك ضرر أمني بحدّ ذاته.
    """

    def __init__(self, reason: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(t('perm.title'))
        self.setModal(True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if is_rtl()
                                else Qt.LayoutDirection.LeftToRight)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_5, theme.SPACE_4,
                                  theme.SPACE_5, theme.SPACE_4)
        layout.setSpacing(theme.SPACE_3)

        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_3)
        mark = QLabel()
        mark.setPixmap(icons.pixmap('shield', 22, theme.STATE_WARN))
        mark.setFixedWidth(24)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(mark)
        heading = QLabel(t('perm.title'))
        heading.setFont(theme.font(theme.SIZE_SECTION, 700))
        header.addWidget(heading, 1)
        layout.addLayout(header)

        why = QLabel(reason)
        why.setFont(theme.font(theme.SIZE_BODY, 500))
        why.setWordWrap(True)
        layout.addWidget(why)

        self.field = QLineEdit()
        self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setPlaceholderText(t('perm.password'))
        self.field.setMinimumHeight(30)
        self.field.returnPressed.connect(self.accept)
        layout.addWidget(self.field)

        note = QLabel(t('perm.not_stored'))
        note.setFont(theme.font(theme.SIZE_LABEL, 500))
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {theme.INK_DIM};")
        layout.addWidget(note)

        actions = QHBoxLayout()
        actions.setSpacing(theme.SPACE_2)
        actions.addStretch(1)
        cancel = QPushButton(t('action.cancel'))
        cancel.setStyleSheet(theme.button_style('quiet'))
        cancel.setMinimumHeight(34)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        confirm_button = QPushButton(t('action.grant'))
        confirm_button.setStyleSheet(theme.button_style('live'))
        confirm_button.setMinimumHeight(34)
        confirm_button.setDefault(True)
        confirm_button.clicked.connect(self.accept)
        actions.addWidget(confirm_button)
        layout.addLayout(actions)

        self.setMinimumWidth(400)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.PANEL};
                border: {theme.BORDER_HAIRLINE}px solid {theme.STATE_WARN};
                border-radius: {theme.RADIUS_PLATE}px;
            }}
            QLabel {{ color: {theme.INK}; background: transparent; }}
        """)

    def password(self) -> str:
        return self.field.text()


# ═══════════════════════════════════════════════════════════
# الواجهة القصيرة: تُستدعى من كل مكان بدل QMessageBox
# ═══════════════════════════════════════════════════════════

def _show(dialog: MessageDialog) -> bool:
    """عرض الحوار بأمان: بلا تطبيق Qt يُسجَّل النص ولا يُنهار"""
    if QApplication.instance() is None:  # pragma: no cover - وضع بلا واجهة
        logger.warning(f"حوار بلا واجهة: {dialog.windowTitle()}")
        return False
    dialog.exec()
    return dialog.confirmed


def inform(parent, title: str, message: str, detail: str = '') -> None:
    """إبلاغ محايد: زر واحد"""
    _show(MessageDialog(title, message, 'info', parent=parent, detail=detail))


def success(parent, title: str, message: str, detail: str = '') -> None:
    """إبلاغ بنجاح إجراء"""
    _show(MessageDialog(title, message, 'success', parent=parent, detail=detail))


def warn(parent, title: str, message: str, detail: str = '') -> None:
    """تحذير: أمر جرى أو سيجري وقد لا يكون مقصوداً"""
    _show(MessageDialog(title, message, 'warning', parent=parent, detail=detail))


def error(parent, title: str, message: str, detail: str = '') -> None:
    """فشل صريح مع سببه"""
    _show(MessageDialog(title, message, 'danger', parent=parent, detail=detail))


def confirm(parent, title: str, message: str, detail: str = '',
            confirm_text: Optional[str] = None,
            cancel_text: Optional[str] = None,
            destructive: bool = False) -> bool:
    """
    سؤال بإجابتين. يعيد True فقط عند الضغط على زر التأكيد.

    `destructive=True` يجعل زر التأكيد الطرف الحيّ ويجعل الإلغاء هو الزر
    الافتراضي: الإجراء الذي لا يُتراجع عنه لا يكون افتراضياً.
    """
    buttons = (
        (cancel_text or t('action.cancel'), 'quiet', False),
        (confirm_text or t('action.confirm'), 'danger' if destructive else 'primary',
         True),
    )
    dialog = MessageDialog(title, message,
                           'danger' if destructive else 'question',
                           buttons=buttons, detail=detail, parent=parent)
    return _show(dialog)


def ask_password(parent, reason: str) -> Optional[str]:
    """طلب كلمة مرور. يعيد None إذا ألغى المستخدم أو لم يُدخل شيئاً"""
    if QApplication.instance() is None:  # pragma: no cover
        return None
    dialog = PasswordDialog(reason, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.password() or None
