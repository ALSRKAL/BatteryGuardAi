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
from typing import Dict, Optional, Tuple

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
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

        self.create_menu()
        self.update_icon(0, False)
        self.tray_icon.activated.connect(self.on_activated)
        self.tray_icon.show()

    # ── القائمة ─────────────────────────────────────────────

    def create_menu(self):
        """القائمة يُحتفظ بمرجعها حتى لا يجمعها جامع النفايات"""
        self.menu = QMenu(self.parent)
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

        optimize_action = menu.addAction(icon_set.icon('gauge', 16, theme.INK),
                                         t('action.optimize'))
        optimize_action.triggered.connect(self.parent.run_optimization)
        menu.addSeparator()

        quit_action = menu.addAction(icon_set.icon('power', 16, theme.INK),
                                     t('notify.action.stop'))
        quit_action.triggered.connect(self.parent.quit_application)

        self.tray_icon.setContextMenu(menu)

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
        """نقرة واحدة تُظهر أو تُخفي، ونقرة مزدوجة تُظهر دائماً"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.parent.isVisible():
                self.parent.hide()
            else:
                self.parent.show_window()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.parent.show_window()

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
