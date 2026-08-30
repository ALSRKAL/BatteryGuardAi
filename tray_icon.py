#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أيقونة صينية النظام - BatteryGuardAI

الأيقونة هي الواجهة الأكثر رؤية في اليوم، فتحمل نفس عالم لوحة القياس:
صفيحة بطارية مسطّحة بحبر واحد، رقم أحادي العرض، وعلامة حالة مرسومة
(لا إيموجي ولا تدرّجات ولا هالات).
"""

import logging
import sys
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import (QAction, QColor, QFont, QIcon, QPainter, QPen,
                         QPixmap)
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

import icons as icon_set
import theme
from default_settings import APP_NAME
from i18n import t

logger = logging.getLogger('BatteryGuard')

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

#: مقاس رسم الأيقونة (تُصغّرها البيئة بنفسها)
ICON_SIZE = 128

#: أقصى عدد أيقونات مخزّنة قبل التفريغ
ICON_CACHE_LIMIT = 60

#: محاولات إظهار الأيقونة قبل الاستسلام، وتباعدها بالمللي ثانية
TRAY_RETRY_LIMIT = 12
TRAY_RETRY_BASE_MS = 1500
TRAY_RETRY_MAX_MS = 10000

#: أقصى عدد مخالفين يُعرضون في القائمة
MENU_OFFENDER_LIMIT = 4


class BatteryTrayIcon:
    """أيقونة الصينية وقائمتها"""

    def __init__(self, parent):
        self.parent = parent
        self.tray_icon = QSystemTrayIcon(parent)
        self.current_percent = 0
        self.is_charging = False
        self.health_score: Optional[int] = None
        self.reporting = True

        self._icon_cache: Dict[Tuple[int, bool, bool], QIcon] = {}
        self._offender_actions: List[QAction] = []
        self._show_attempts = 0

        self.create_menu()
        self.update_icon(0, False)
        self.tray_icon.activated.connect(self.on_activated)
        self._ensure_visible()

    # ── الظهور ──────────────────────────────────────────────

    def _ensure_visible(self):
        """
        إظهار الأيقونة، وإعادة المحاولة إن لم تكن صينية النظام جاهزة بعد.

        هذا ليس احتياطاً نظرياً: في وضع التشغيل التلقائي يبدأ التطبيق مع
        الجلسة قبل أن يُسجّل مضيف الصينية نفسه على ناقل الرسائل، فتُهمل
        الأيقونة صامتةً ويظنّ المستخدم أن التطبيق لم يعمل. نعيد المحاولة
        بتباعد متزايد حتى تتوفر الصينية أو تنتهي المحاولات.
        """
        self.tray_icon.show()
        if self.tray_icon.isVisible():
            if self._show_attempts:
                logger.info(f"ظهرت أيقونة الصينية بعد {self._show_attempts} محاولة")
            return

        self._show_attempts += 1
        if self._show_attempts > TRAY_RETRY_LIMIT:
            logger.warning(
                "صينية النظام غير متاحة - التطبيق يعمل في الخلفية بلا أيقونة. "
                "على بيئات GNOME الحديثة تحتاج إضافة AppIndicator.")
            return
        delay = min(TRAY_RETRY_MAX_MS, TRAY_RETRY_BASE_MS * self._show_attempts)
        logger.debug(f"صينية النظام غير جاهزة - إعادة المحاولة بعد {delay}ms")
        QTimer.singleShot(delay, self._ensure_visible)

    @property
    def available(self) -> bool:
        """هل الأيقونة ظاهرة فعلاً في الصينية"""
        return bool(self.tray_icon.isVisible())

    # ── القائمة ─────────────────────────────────────────────

    def create_menu(self):
        """
        القائمة يُحتفظ بمرجعها حتى لا يجمعها جامع النفايات.

        تُبنى بلا أب عن قصد: في وضع الخلفية لا توجد نافذة، والمتحكّم كائن
        `QObject` لا `QWidget`، و`QMenu` لا تقبل إلا أباً من نوع `QWidget`.
        قائمة الصينية لا تحتاج أباً أصلاً لأنها تُعرض في سياق الصينية.
        """
        self.menu = QMenu()
        menu = self.menu

        show_action = menu.addAction(icon_set.icon('crosshair', 16, theme.INK),
                                     t('app.name'))
        show_action.triggered.connect(self.parent.show_window)
        menu.addSeparator()

        self.status_action = menu.addAction(f"{t('field.percent')}: --")
        self.status_action.setEnabled(False)
        self.health_action = menu.addAction(f"{t('health.title')}: --")
        self.health_action.setEnabled(False)
        self.time_action = menu.addAction(f"{t('status.time_to_empty')}: --")
        self.time_action.setEnabled(False)
        menu.addSeparator()

        # مجال المخالفين: أهمّ ما يريد المستخدم رؤيته بلا فتح النافذة
        self.offenders_header = menu.addAction(t('guard.tray_header'))
        self.offenders_header.setEnabled(False)
        self.offenders_menu = menu.addMenu(t('guard.no_offenders'))
        self.offenders_menu.setEnabled(False)
        menu.addSeparator()

        optimize_action = menu.addAction(icon_set.icon('gauge', 16, theme.INK),
                                         t('action.optimize'))
        optimize_action.triggered.connect(self.parent.run_optimization)
        menu.addSeparator()

        quit_action = menu.addAction(icon_set.icon('power', 16, theme.INK),
                                     t('notify.action.stop'))
        quit_action.triggered.connect(self.parent.quit_application)

        self.tray_icon.setContextMenu(menu)

    # ── المخالفون ───────────────────────────────────────────

    def update_offenders(self, report) -> None:
        """
        بناء قائمة المخالفين مع إجراءاتها. تُعاد بناؤها كل تقرير لأن الأسماء
        والأرقام تتغيّر، ويُحتفظ بمراجع الإجراءات حتى لا يجمعها جامع النفايات.
        """
        menu = getattr(self, 'offenders_menu', None)
        if menu is None:
            return
        menu.clear()
        self._offender_actions = []

        offenders = [item for item in getattr(report, 'offenders', [])
                     if item.recommended_action != 'none'][:MENU_OFFENDER_LIMIT]
        if not offenders:
            menu.setTitle(t('guard.no_offenders'))
            menu.setEnabled(False)
            return

        menu.setTitle(t('guard.offenders_count', count=len(offenders)))
        menu.setEnabled(True)
        for offender in offenders:
            watts = (f"{offender.watts:.1f}{t('unit.watt')}"
                     if offender.watts else '—')
            submenu = menu.addMenu(
                t('guard.offender_line', name=offender.name, watts=watts,
                  score=int(offender.damage_score),
                  loss=round(offender.annual_capacity_loss, 2)))
            self._add_offender_actions(submenu, offender.name)

    def _add_offender_actions(self, submenu: QMenu, name: str) -> None:
        """إجراءات مخالف واحد. الترتيب من الأخفّ إلى الأشدّ عن قصد."""
        entries = (
            ('guard.action.throttle', lambda: self.parent.guard_throttle(name)),
            ('guard.action.restore', lambda: self.parent.guard_restore(name)),
            ('guard.action.suspend', lambda: self.parent.guard_suspend(name)),
            ('guard.action.resume', lambda: self.parent.guard_resume(name)),
            ('guard.action.ignore', lambda: self.parent.guard_ignore(name)),
            ('guard.action.terminate', lambda: self.parent.guard_terminate(name)),
        )
        for key, handler in entries:
            action = submenu.addAction(t(key))
            action.triggered.connect(handler)
            self._offender_actions.append(action)

    # ── التحديث ─────────────────────────────────────────────

    def update_icon(self, percent: int, is_charging: bool,
                    health: Optional[int] = None, reporting: bool = True):
        """تحديث الأيقونة والتلميح والقائمة من قراءة واحدة"""
        self.current_percent = int(percent)
        self.is_charging = bool(is_charging)
        self.health_score = health
        self.reporting = bool(reporting)

        cache_key = (self.current_percent // 5, self.is_charging, self.reporting)
        if cache_key not in self._icon_cache:
            if len(self._icon_cache) > ICON_CACHE_LIMIT:
                self._icon_cache.clear()
            self._icon_cache[cache_key] = QIcon(
                self._render(self.current_percent, self.is_charging, self.reporting))
        self.tray_icon.setIcon(self._icon_cache[cache_key])

        status = t('status.charging') if is_charging else t('status.discharging')
        if not reporting:
            status = t('status.not_reporting')
        health_text = f"{health}%" if health is not None else t('health.unknown')

        self.tray_icon.setToolTip(
            f"{APP_NAME}\n{percent}{t('unit.percent')} · {status}\n"
            f"{t('health.title')}: {health_text}")

        if hasattr(self, 'status_action'):
            self.status_action.setText(
                f"{t('field.percent')}: {percent}{t('unit.percent')} · {status}")
        if hasattr(self, 'health_action'):
            self.health_action.setText(f"{t('health.title')}: {health_text}")

    def update_time_remaining(self, time_str: str):
        if hasattr(self, 'time_action'):
            self.time_action.setText(f"{t('status.time_to_empty')}: {time_str}")

    # ── الرسم ───────────────────────────────────────────────

    def _render(self, percent: int, is_charging: bool, reporting: bool) -> QPixmap:
        """
        صفيحة بطارية مسطّحة: إطار محفور، حقل ممتلئ بلون الحالة، رقم فوقه،
        وعلامة مرسومة للشحن أو لانعدام التبليغ.
        """
        pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        field, mark_color, _headline = theme.field_for_state(
            percent, is_charging, reporting, *theme.OPTIMAL_WINDOW_DEFAULT)

        body = QRect(14, 34, 88, 60)
        terminal = QRect(102, 52, 10, 24)

        # التجويف
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.PANEL_SUNKEN))
        painter.drawRoundedRect(body, 8, 8)
        painter.drawRoundedRect(terminal, 3, 3)

        # الحقل الممتلئ بقدر النسبة
        if reporting and percent > 0:
            fill_width = max(4, int((body.width() - 10) * percent / 100))
            painter.setBrush(QColor(field))
            painter.drawRoundedRect(
                QRect(body.x() + 5, body.y() + 5, fill_width, body.height() - 10), 5, 5)

        # الإطار المحفور
        pen = QPen(QColor(theme.INK))
        pen.setWidthF(4.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body, 8, 8)

        # الرقم بأرقام أحادية العرض
        painter.setPen(QColor(theme.INK_ON_FIELD if percent >= 45 else theme.INK))
        number_font = QFont(theme.mono_family())
        number_font.setPixelSize(40)
        number_font.setWeight(QFont.Weight.Bold)
        painter.setFont(number_font)
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter,
                         str(percent) if reporting else '--')

        # علامة الحالة في الزاوية
        if not reporting:
            icon_set.draw(painter, 'blocked', QRect(4, 4, 30, 30), theme.STATE_DEAD, stroke=2.4)
        elif is_charging:
            icon_set.draw(painter, 'bolt', QRect(4, 4, 30, 30), mark_color, stroke=2.4)
        if self.health_score is not None and self.health_score < 80:
            icon_set.draw(painter, 'alert', QRect(4, ICON_SIZE - 34, 28, 28),
                          theme.STATE_WARN, stroke=2.4)

        painter.end()
        return pixmap

    # ── التفاعل ─────────────────────────────────────────────

    def on_activated(self, reason):
        """
        نقرة واحدة تُظهر أو تُخفي، ونقرة مزدوجة تُظهر دائماً.

        `window_visible` بدل `isVisible` المباشرة: في وضع الخلفية لا توجد
        نافذة بعد، والمتحكّم يقرّر بنفسه معنى «ظاهرة».
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._window_visible():
                self.parent.hide()
            else:
                self.parent.show_window()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.parent.show_window()

    def _window_visible(self) -> bool:
        """هل نافذة التطبيق ظاهرة الآن (نافذة كاملة أو متحكّم خلفية)"""
        checker = getattr(self.parent, 'window_visible', None)
        if callable(checker):
            return bool(checker())
        try:
            return bool(self.parent.isVisible())
        except (AttributeError, RuntimeError):
            return False

    def show_message(self, title: str, message: str,
                     icon=QSystemTrayIcon.MessageIcon.Information):
        self.tray_icon.showMessage(title, message, icon, 5000)

    def show_smart_notification(self, notification_type: str, data: dict):
        """إشعار من الصينية بأولوية مطابقة لشدّة الحالة"""
        levels = {
            'critical': QSystemTrayIcon.MessageIcon.Critical,
            'warning': QSystemTrayIcon.MessageIcon.Warning,
            'info': QSystemTrayIcon.MessageIcon.Information,
        }
        self.show_message(
            data.get('title', APP_NAME),
            data.get('message', ''),
            levels.get(notification_type, QSystemTrayIcon.MessageIcon.Information))

    def hide(self):
        self.tray_icon.hide()
