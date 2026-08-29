#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
عناصر لوحة القياس - BatteryGuardAI

الأجزاء الحاملة لهوية عالم «لوحة القياس»:
- `EngravedRail`: شريط رأس محفور يحمل هوية الجهاز وحكماً واحداً بلغة بسيطة.
- `StatePlate`: حقل الحالة المشبع مع القراءة الأساسية وأثر الفوسفور.
- `CapabilityStrip`: الأرض الثابتة المعنونة (ما يدعمه هذا العتاد فعلاً).
- `ChargeWindowJaw`: فكّ نافذة الشحن بمقبضين ومسنّنات - التفاعل المميّز.
- `AdviceLayer`: الطبقة المعلَّمة فوق الأرض (التوصيات مع سندها).

كل الألوان والمقاسات من `theme`، وكل الأيقونات من `icons`، وكل نص من `i18n`.
"""

import logging
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from PyQt6.QtCore import (QEasingCurve, QPointF, QRect, QRectF, Qt,
                          QVariantAnimation, pyqtSignal)
from PyQt6.QtGui import (QColor, QFontMetrics, QPainter, QPainterPath, QPen,
                         QPolygonF)
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QPushButton, QSizePolicy, QTextEdit, QVBoxLayout,
                             QWidget)

import icons
import theme
from i18n import t

logger = logging.getLogger('BatteryGuard')

TRACE_CAPACITY = 240             # أقصى عدد عينات في أثر الفوسفور
SETTLE_MS = 260                  # زمن استقرار القراءة (تخميد حاد، لا ارتداد)


def _hairline(painter: QPainter, x1: float, y1: float, x2: float, y2: float,
              color: str, width: float = 1.0) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    painter.setPen(pen)
    painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class _Plate(QFrame):
    """صفيحة مرفوعة بحفر بحدّين - أساس معظم العناصر"""

    def __init__(self, role: str = 'plate', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty('role', role)
        self.setFrameShape(QFrame.Shape.NoFrame)


# ═══════════════════════════════════════════════════════════
# شريط الرأس المحفور
# ═══════════════════════════════════════════════════════════

class EngravedRail(_Plate):
    """
    هوية الجهاز على اليمين، وحكم واحد بلغة بسيطة في المنتصف، وطبقة القدرة
    على الطرف الآخر. لا شعار مكرّر ولا عنوان فرعي فوق العنوان.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__('rail', parent)
        self.setFixedHeight(76)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_5, theme.SPACE_3, theme.SPACE_5, theme.SPACE_3)
        layout.setSpacing(theme.SPACE_4)

        identity = QVBoxLayout()
        identity.setSpacing(0)
        self.instrument_label = QLabel(t('app.instrument_id'))
        self.instrument_label.setFont(theme.legend_font())
        self.instrument_label.setProperty('role', 'legend')
        self.device_label = QLabel('')
        self.device_label.setFont(theme.font(theme.SIZE_LABEL, 500, mono=True))
        self.device_label.setStyleSheet(f"color: {theme.INK_DIM};")
        identity.addWidget(self.instrument_label)
        identity.addWidget(self.device_label)

        self.verdict_label = QLabel(t('status.reading'))
        self.verdict_label.setFont(theme.font(theme.SIZE_SECTION, 600))
        self.verdict_label.setWordWrap(False)

        self.tier_mark = QLabel()
        self.tier_mark.setFixedWidth(18)
        self.tier_label = QLabel('')
        self.tier_label.setFont(theme.legend_font())
        self._tier_key = 'notify_only'

        tier_row = QHBoxLayout()
        tier_row.setSpacing(theme.SPACE_2)
        tier_row.addWidget(self.tier_mark)
        tier_row.addWidget(self.tier_label)

        layout.addLayout(identity)
        layout.addStretch(1)
        layout.addWidget(self.verdict_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)
        layout.addLayout(tier_row)

    def set_device(self, vendor: str, product: str) -> None:
        text = ' '.join(part for part in (vendor, product) if part).strip()
        self.device_label.setText(text or '—')

    def set_verdict(self, text: str, band: str = 'low') -> None:
        self.verdict_label.setText(text)
        self.verdict_label.setStyleSheet(f"color: {theme.stress_color(band)};")

    def set_tier(self, tier: str) -> None:
        self._tier_key = tier
        color = theme.TIER_COLORS.get(tier, theme.STATE_DEAD)
        self.tier_label.setText(t(f'tier.{tier}'))
        self.tier_label.setStyleSheet(f"color: {color};")
        self.tier_label.setToolTip(t(f'tier.{tier}.desc'))
        self.tier_mark.setPixmap(
            icons.pixmap(icons.TIER_ICONS.get(tier, 'info'), 17, color))
        self.tier_mark.setToolTip(t(f'tier.{tier}.desc'))


# ═══════════════════════════════════════════════════════════
# حقل الحالة: القراءة الأساسية وأثر الفوسفور
# ═══════════════════════════════════════════════════════════

class PhosphorTrace(QWidget):
    """
    أثر القياس: نسبة الشحن عبر الزمن المرصود، بحبر واحد وشبكة عند الحدّين
    الصحيّين فقط. هذا هو الرسم اليدوي الوحيد في اللوحة، وله حدوده الخاصة.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._samples: Deque[float] = deque(maxlen=TRACE_CAPACITY)
        self._minutes = 0.0
        self._floor, self._ceiling = theme.OPTIMAL_WINDOW_DEFAULT

    def set_window(self, floor: int, ceiling: int) -> None:
        self._floor, self._ceiling = int(floor), int(ceiling)
        self.update()

    def push(self, percent: float, span_minutes: float) -> None:
        self._samples.append(float(max(0.0, min(100.0, percent))))
        self._minutes = max(0.0, span_minutes)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        area = self.rect().adjusted(0, theme.SPACE_2, 0, -theme.SPACE_2)
        rtl = self.isRightToLeft()

        painter.setFont(theme.legend_font(11))
        for level in (self._ceiling, self._floor):
            y = area.bottom() - area.height() * (level / 100.0)
            _hairline(painter, area.left(), y, area.right(), y, 'rgba(242,239,230,0.22)')
            painter.setPen(QColor(theme.INK_ON_FIELD))
            painter.setOpacity(0.6)
            label_rect = QRect(area.left(), int(y) - 16, 40, 14) if rtl else \
                QRect(area.right() - 40, int(y) - 16, 40, 14)
            painter.drawText(label_rect,
                             Qt.AlignmentFlag.AlignLeft if rtl else Qt.AlignmentFlag.AlignRight,
                             f"{level}")
            painter.setOpacity(1.0)

        if len(self._samples) < 2:
            painter.setPen(QColor(theme.INK_ON_FIELD))
            painter.setOpacity(0.5)
            painter.setFont(theme.legend_font(12))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, t('trace.empty'))
            painter.setOpacity(1.0)
            painter.end()
            return

        step = area.width() / float(len(self._samples) - 1)
        polygon = QPolygonF()
        for index, sample in enumerate(self._samples):
            position = index if not rtl else (len(self._samples) - 1 - index)
            x = area.left() + position * step
            y = area.bottom() - area.height() * (sample / 100.0)
            polygon.append(QPointF(x, y))

        pen = QPen(QColor(theme.INK_ON_FIELD))
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setOpacity(0.94)
        painter.drawPolyline(polygon)
        painter.setOpacity(1.0)

        if self._minutes >= 1:
            painter.setFont(theme.legend_font(11))
            painter.setPen(QColor(theme.INK_ON_FIELD))
            painter.setOpacity(0.6)
            painter.drawText(area,
                             (Qt.AlignmentFlag.AlignLeft if rtl else Qt.AlignmentFlag.AlignRight)
                             | Qt.AlignmentFlag.AlignBottom,
                             f"{int(self._minutes)} {t('unit.minute_short')}")
            painter.setOpacity(1.0)
        painter.end()


class ResponsiveGrid(QWidget):
    """
    شبكة تعيد توزيع عناصرها حسب العرض المتاح فعلاً: عمود واحد على نافذة
    ضيّقة، وحتى أربعة أعمدة على شاشة عريضة. هذا ما يمنع الفراغ الكبير على
    الشاشات الكبيرة بدل تمديد عنصر واحد بلا داعٍ.
    """

    def __init__(self, min_column_width: int = 300, max_columns: int = 4,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._min_column_width = int(min_column_width)
        self._max_columns = int(max_columns)
        self._items: List[QWidget] = []
        self._columns = 0

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(theme.SPACE_4)
        self._grid.setVerticalSpacing(theme.SPACE_2)

    def add(self, widget: QWidget) -> None:
        self._items.append(widget)
        self._relayout(force=True)

    def clear(self) -> None:
        for widget in self._items:
            self._grid.removeWidget(widget)
            widget.deleteLater()
        self._items.clear()
        self._columns = 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self, force: bool = False) -> None:
        if not self._items:
            return
        available = max(self.width(), self._min_column_width)
        columns = max(1, min(self._max_columns, available // self._min_column_width))
        if columns == self._columns and not force:
            return
        self._columns = columns

        for widget in self._items:
            self._grid.removeWidget(widget)
        for index, widget in enumerate(self._items):
            self._grid.addWidget(widget, index // columns, index % columns)
        for column in range(self._max_columns):
            self._grid.setColumnStretch(column, 1 if column < columns else 0)


class _MeasureCell(QWidget):
    """قياس ثانوي على حقل الحالة: أيقونة، تسمية، قيمة - في تخطيط حقيقي"""

    def __init__(self, icon_name: str, label: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_name = icon_name
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACE_2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.mark = QLabel()
        self.mark.setPixmap(icons.pixmap(icon_name, 16, theme.INK_ON_FIELD))
        self.mark.setFixedWidth(18)
        self.mark.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        text_column = QVBoxLayout()
        text_column.setSpacing(1)
        self.label = QLabel(label)
        self.label.setFont(theme.legend_font(11))
        self.label.setStyleSheet(f"color: rgba(242, 239, 230, 0.62);")
        self.value = QLabel('—')
        self.value.setFont(theme.font(theme.SIZE_LABEL, 700, mono=True))
        self.value.setStyleSheet(f"color: {theme.INK_ON_FIELD};")
        text_column.addWidget(self.label)
        text_column.addWidget(self.value)

        layout.addWidget(self.mark)
        layout.addLayout(text_column)
        layout.addStretch(1)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class StatePlate(QFrame):
    """
    الحقل المشبع الذي يملك أعلى الشاشة: القراءة الأساسية على اليمين، القياسات
    الثانوية بجانبها، وأثر الاستهلاك أسفلها. كل شيء في تخطيط حقيقي حتى لا
    يتراكب عند تغيّر اللغة أو مقاس الشاشة، والرسم اليدوي محصور في الأثر.
    """

    MEASURE_SLOTS = (
        ('bolt', 'status.draw'),
        ('thermometer', 'status.temperature'),
        ('pulse', 'health.title'),
        ('cycle', 'health.cycles'),
        ('plug', 'field.status'),
        ('gauge', 'status.stress'),
    )

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._percent = 0.0
        self._shown_percent = 0.0
        self._is_charging = False
        self._reporting = True
        self._floor, self._ceiling = theme.OPTIMAL_WINDOW_DEFAULT
        self._field = theme.FIELD_DEAD

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SPACE_5, theme.SPACE_4, theme.SPACE_5, theme.SPACE_4)
        outer.setSpacing(theme.SPACE_3)

        top = QHBoxLayout()
        top.setSpacing(theme.SPACE_5)

        # ── القراءة الأساسية ──
        reading = QHBoxLayout()
        reading.setSpacing(theme.SPACE_2)
        self.value_label = QLabel('--')
        self.value_label.setFont(theme.font(theme.SIZE_READOUT, 700, mono=True))
        self.value_label.setStyleSheet(f"color: {theme.INK_ON_FIELD};")
        # عرض ثابت لثلاث خانات حتى لا يتحرك ما حوله عند تغيّر الرقم
        self.value_label.setMinimumWidth(int(theme.SIZE_READOUT * 2.0))
        self.unit_label = QLabel(t('unit.percent'))
        self.unit_label.setFont(theme.legend_font(theme.SIZE_LABEL))
        self.unit_label.setStyleSheet("color: rgba(242, 239, 230, 0.7);")
        reading.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignBottom)
        reading.addWidget(self.unit_label, 0, Qt.AlignmentFlag.AlignBottom)

        # عمود القراءة بعرض أدنى ثابت حتى لا يُقصّ نص الحالة تحت الرقم
        reading_host = QWidget()
        reading_host.setMinimumWidth(320)
        reading_column = QVBoxLayout(reading_host)
        reading_column.setContentsMargins(0, 0, 0, 0)
        reading_column.setSpacing(theme.SPACE_1)
        reading_column.addLayout(reading)

        status_row = QHBoxLayout()
        status_row.setSpacing(theme.SPACE_2)
        self.status_mark = QLabel()
        self.status_mark.setFixedWidth(18)
        self.status_label = QLabel(t('status.reading'))
        self.status_label.setFont(theme.font(theme.SIZE_LABEL, 700))
        self.status_label.setStyleSheet(f"color: {theme.INK_ON_FIELD};")
        status_row.addWidget(self.status_mark)
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        reading_column.addLayout(status_row)
        reading_column.addStretch(1)

        top.addWidget(reading_host, 0, Qt.AlignmentFlag.AlignTop)
        top.addStretch(1)

        # ── القياسات الثانوية: تتوزّع على أعمدة حسب العرض المتاح ──
        measures_grid = ResponsiveGrid(min_column_width=210, max_columns=3)
        self.measure_cells: Dict[str, _MeasureCell] = {}
        for icon_name, key in self.MEASURE_SLOTS:
            cell = _MeasureCell(icon_name, t(key))
            self.measure_cells[key] = cell
            measures_grid.add(cell)
        top.addWidget(measures_grid, 1, Qt.AlignmentFlag.AlignTop)

        outer.addLayout(top)

        self.trace = PhosphorTrace()
        outer.addWidget(self.trace, 1)

        self._settle = QVariantAnimation(self)
        self._settle.setDuration(SETTLE_MS)
        self._settle.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._settle.valueChanged.connect(self._on_settle)

    # ── واجهة البيانات ──────────────────────────────────────

    def set_reading(self, percent: float, is_charging: bool, reporting: bool,
                    status_key: str, floor: int = 40, ceiling: int = 80) -> None:
        self._is_charging = bool(is_charging)
        self._reporting = bool(reporting)
        self._floor, self._ceiling = int(floor), int(ceiling)
        self.trace.set_window(self._floor, self._ceiling)

        target = float(max(0.0, min(100.0, percent)))
        if abs(target - self._percent) >= 0.5:
            self._settle.stop()
            self._settle.setStartValue(self._shown_percent)
            self._settle.setEndValue(target)
            self._settle.start()
        else:
            self._shown_percent = target
        self._percent = target
        self._paint_value()

        self._field, mark_color, _headline = theme.field_for_state(
            self._percent, self._is_charging, self._reporting, self._floor, self._ceiling)

        mark = 'blocked' if not reporting else ('bolt' if is_charging else 'arrow_down')
        self.status_mark.setPixmap(icons.pixmap(mark, 17, theme.INK_ON_FIELD))
        self.status_label.setText(t(status_key))
        self.update()

    def set_measures(self, measures: List[Tuple[str, str, str]]) -> None:
        """(أيقونة، مفتاح التسمية، القيمة) لكل خانة قياس ثانوية"""
        for _icon_name, key, value in measures:
            cell = self.measure_cells.get(key)
            if cell is not None:
                cell.set_value(value)

    def push_sample(self, percent: float, span_minutes: float) -> None:
        if self._reporting:
            self.trace.push(percent, span_minutes)

    def _on_settle(self, value) -> None:
        self._shown_percent = float(value)
        self._paint_value()

    def _paint_value(self) -> None:
        """
        الرقم يملك المكان حين يوجد قياس. حين لا تُبلّغ البطارية تُكتب كلمة
        صريحة بحجم أصغر: شرطة يتيمة في مكان رقم ضخم تبدو خللاً لا معلومة.
        """
        if self._reporting:
            self.value_label.setFont(theme.font(theme.SIZE_READOUT, 700, mono=True))
            self.value_label.setText(f"{int(round(self._shown_percent))}")
            self.unit_label.setVisible(True)
        else:
            self.value_label.setFont(theme.font(theme.SIZE_READOUT_SM, 700))
            self.value_label.setText(t('status.no_signal'))
            self.unit_label.setVisible(False)

    # ── الحقل ───────────────────────────────────────────────

    def paintEvent(self, event):
        """الحقل المشبع وحرفه المحفور؛ المحتوى كله في التخطيط لا في الرسم"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        path = QPainterPath()
        path.addRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5),
                            theme.RADIUS_PLATE, theme.RADIUS_PLATE)
        painter.fillPath(path, QColor(self._field))

        if not self._reporting:
            # لا إشارة: شريط مهشّر ضيّق أعلى الحقل، لا تهشير يغطي القراءة
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(icons.hatch_brush('rgba(122,129,137,0.55)', 6))
            painter.drawRect(rect.left() + 1, rect.top() + 1, rect.width() - 2, 6)
            painter.setBrush(Qt.BrushStyle.NoBrush)

        pen = QPen(QColor(theme.HAIRLINE_STRONG))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawPath(path)

        _hairline(painter, rect.left() + 2, rect.top() + 1, rect.right() - 2, rect.top() + 1,
                  'rgba(255,255,255,0.12)')
        _hairline(painter, rect.left() + 2, rect.bottom() - 1, rect.right() - 2, rect.bottom() - 1,
                  'rgba(0,0,0,0.45)')
        painter.end()


# ═══════════════════════════════════════════════════════════
# الأرض الثابتة: قدرات هذا العتاد
# ═══════════════════════════════════════════════════════════

class CapabilityStrip(_Plate):
    """
    ما يدعمه هذا الجهاز فعلاً، بأسطورة معنونة. القدرة غير المتاحة تُغطّى
    بتهشير (صفيحة مثقوبة) ولا تُخفى: الغياب معلومة يحتاجها المستخدم.
    """

    remediationRequested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__('plate', parent)
        self._rows: List[Tuple[str, bool]] = []
        self._tier = 'notify_only'

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_4, theme.SPACE_3, theme.SPACE_4, theme.SPACE_3)
        layout.setSpacing(theme.SPACE_2)

        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_2)
        title = QLabel(t('capability.title'))
        title.setFont(theme.legend_font())
        title.setProperty('role', 'legend')
        self.tier_desc = QLabel('')
        self.tier_desc.setWordWrap(True)
        self.tier_desc.setFont(theme.font(theme.SIZE_BODY, 500))
        self.tier_desc.setStyleSheet(f"color: {theme.INK_DIM};")
        self.tier_desc.setMaximumWidth(theme.MAX_TEXT_WIDTH)
        header.addWidget(title)
        header.addStretch(1)

        self.remedy_button = QPushButton(t('remedy.title'))
        self.remedy_button.setProperty('role', 'quiet')
        self.remedy_button.setIcon(icons.icon('crosshair', 14, theme.INK_DIM))
        self.remedy_button.clicked.connect(self.remediationRequested.emit)
        header.addWidget(self.remedy_button)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(theme.SPACE_4)
        self.grid.setVerticalSpacing(theme.SPACE_1)

        layout.addLayout(header)
        layout.addWidget(self.tier_desc)
        layout.addLayout(self.grid)

    def set_report(self, report: Dict) -> None:
        self._tier = str(report.get('tier', 'notify_only'))
        self.tier_desc.setText(t(f'tier.{self._tier}.desc'))
        self.remedy_button.setVisible(bool(report.get('remediation')))

        readable = dict(report.get('readable') or {})
        rows: List[Tuple[str, bool]] = [
            ('field.percent', bool(readable.get('percent'))),
            ('field.power', bool(readable.get('power'))),
            ('field.temperature', bool(readable.get('temperature'))),
            ('field.cycles', bool(readable.get('cycles'))),
            ('field.capacity_design', bool(readable.get('capacity_design'))),
            ('window.title', bool(report.get('can_control'))),
        ]
        self._rows = rows

        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        columns = 3
        for index, (key, available) in enumerate(rows):
            cell = _CapabilityCell(t(key), available)
            self.grid.addWidget(cell, index // columns, index % columns)


class _CapabilityCell(QWidget):
    """خلية قدرة واحدة: علامة + اسم، والغياب مهشّر"""

    def __init__(self, label: str, available: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._label = label
        self._available = available
        self.setMinimumHeight(34)
        self.setToolTip(label if available else f"{label} — {t('capability.unavailable')}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rtl = self.isRightToLeft()
        rect = self.rect()
        icon_size = 14

        if not self._available:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(icons.hatch_brush('rgba(122,129,137,0.45)'))
            painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 2.5, -0.5, -2.5), 2, 2)
            painter.setBrush(Qt.BrushStyle.NoBrush)

        color = theme.STATE_OK if self._available else theme.STATE_DEAD
        icon_name = 'check' if self._available else 'blocked'
        icon_x = rect.right() - icon_size - theme.SPACE_2 if rtl else rect.left() + theme.SPACE_2
        icons.draw(painter, icon_name,
                   QRect(int(icon_x), rect.center().y() - icon_size // 2, icon_size, icon_size),
                   color)

        painter.setFont(theme.font(theme.SIZE_LABEL, 500))
        painter.setPen(QColor(theme.INK if self._available else theme.INK_FAINT))
        text_rect = QRect(rect.left() + theme.SPACE_2 if rtl
                          else rect.left() + icon_size + theme.SPACE_3,
                          rect.top(),
                          rect.width() - icon_size - theme.SPACE_4, rect.height())
        painter.drawText(text_rect,
                         (Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
                         | Qt.AlignmentFlag.AlignVCenter, self._label)
        painter.end()


# ═══════════════════════════════════════════════════════════
# فكّ نافذة الشحن: التفاعل المميّز
# ═══════════════════════════════════════════════════════════

class ChargeWindowJaw(QWidget):
    """
    مقبضان على مجرى محفور بمسنّنات كل 5٪. تحريك أي مقبض يعيد حساب اللوحة
    فوراً، ولا يُطبَّق على العتاد إلا بضغطة صريحة.

    الوصول بلوحة المفاتيح: Tab للتركيز، Space لتبديل المقبض النشط،
    الأسهم للتحريك، مع حقلين رقميين مكافئين بجانب الفكّ.
    """

    windowChanged = pyqtSignal(int, int)

    DETENT = 5
    MIN_GAP = 10

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._floor = 40
        self._ceiling = 80
        self._supported = False
        self._active = 1                      # 0 = الأدنى، 1 = الأقصى
        self._dragging: Optional[int] = None
        self.setMinimumHeight(84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ── الحالة ──────────────────────────────────────────────

    def window(self) -> Tuple[int, int]:
        return self._floor, self._ceiling

    def set_window(self, floor: int, ceiling: int, emit: bool = False) -> None:
        floor = int(max(0, min(100 - self.MIN_GAP, floor)))
        ceiling = int(max(floor + self.MIN_GAP, min(100, ceiling)))
        changed = (floor, ceiling) != (self._floor, self._ceiling)
        self._floor, self._ceiling = floor, ceiling
        self.update()
        if changed and emit:
            self.windowChanged.emit(self._floor, self._ceiling)

    def set_supported(self, supported: bool) -> None:
        self._supported = bool(supported)
        self.setToolTip('' if supported else t('window.unsupported'))
        self.update()

    # ── التفاعل ─────────────────────────────────────────────

    def _value_at(self, x: int) -> int:
        track = self._track_rect()
        if track.width() <= 0:
            return 0
        ratio = (x - track.left()) / track.width()
        if self.isRightToLeft():
            ratio = 1.0 - ratio
        raw = ratio * 100.0
        return int(max(0, min(100, round(raw / self.DETENT) * self.DETENT)))

    def _track_rect(self) -> QRect:
        """المجرى في الوسط، بمساحة أعلاه للأرقام وأسفله للمسنّنات"""
        return self.rect().adjusted(theme.SPACE_4, 32, -theme.SPACE_4, -30)

    def mousePressEvent(self, event):
        if not self._supported:
            return
        value = self._value_at(int(event.position().x()))
        self._dragging = 0 if abs(value - self._floor) < abs(value - self._ceiling) else 1
        self._active = self._dragging
        self._apply_handle(value)

    def mouseMoveEvent(self, event):
        if self._dragging is None or not self._supported:
            return
        self._apply_handle(self._value_at(int(event.position().x())))

    def mouseReleaseEvent(self, event):
        self._dragging = None

    def keyPressEvent(self, event):
        if not self._supported:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._active = 1 - self._active
            self.update()
            return
        step = self.DETENT if key in (Qt.Key.Key_Right, Qt.Key.Key_Up) else \
            -self.DETENT if key in (Qt.Key.Key_Left, Qt.Key.Key_Down) else 0
        if step == 0:
            super().keyPressEvent(event)
            return
        if self.isRightToLeft() and key in (Qt.Key.Key_Right, Qt.Key.Key_Left):
            step = -step
        current = self._floor if self._active == 0 else self._ceiling
        self._apply_handle(current + step)

    def _apply_handle(self, value: int) -> None:
        value = int(max(0, min(100, value)))
        if self._active == 0:
            self.set_window(min(value, self._ceiling - self.MIN_GAP), self._ceiling, emit=True)
        else:
            self.set_window(self._floor, max(value, self._floor + self.MIN_GAP), emit=True)

    # ── الرسم ───────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = self._track_rect()
        rtl = self.isRightToLeft()

        # المجرى المحفور: تجويف بحرف واضح حتى يُقرأ كعنصر تحكم
        groove = QRectF(track.left(), track.center().y() - 7, track.width(), 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.PANEL_SUNKEN))
        painter.drawRoundedRect(groove, 3, 3)
        outline = QPen(QColor(theme.HAIRLINE_STRONG))
        outline.setWidthF(1.0)
        painter.setPen(outline)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(groove, 3, 3)

        def pos_for(value: int) -> float:
            ratio = value / 100.0
            if rtl:
                ratio = 1.0 - ratio
            return track.left() + track.width() * ratio

        # المسنّنات كل 10٪ مع أرقام على الأطراف
        painter.setFont(theme.legend_font(9))
        for level in range(0, 101, 10):
            x = pos_for(level)
            tall = level % 50 == 0
            _hairline(painter, x, groove.bottom() + 3, x,
                      groove.bottom() + (9 if tall else 5),
                      theme.HAIRLINE_STRONG if tall else theme.HAIRLINE)
            if tall:
                painter.setPen(QColor(theme.INK_FAINT))
                # تقييد المستطيل داخل العنصر حتى لا يُقصّ رقم الطرف
                label_x = int(min(max(x - 16, self.rect().left()),
                                  self.rect().right() - 32))
                painter.drawText(QRect(label_x, int(groove.bottom()) + 10, 32, 14),
                                 Qt.AlignmentFlag.AlignHCenter, f"{level}")

        # النافذة المختارة: حقل فوسفوري بين المقبضين
        left = min(pos_for(self._floor), pos_for(self._ceiling))
        right = max(pos_for(self._floor), pos_for(self._ceiling))
        window_rect = QRectF(left, groove.top(), right - left, groove.height())
        painter.setPen(Qt.PenStyle.NoPen)
        if self._supported:
            painter.setBrush(QColor(theme.PHOSPHOR))
            painter.setOpacity(0.55)
            painter.drawRoundedRect(window_rect, 2, 2)
            painter.setOpacity(1.0)
        else:
            painter.setBrush(icons.hatch_brush('rgba(122,129,137,0.5)'))
            painter.drawRoundedRect(window_rect, 2, 2)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # المقبضان
        for index, value in enumerate((self._floor, self._ceiling)):
            x = pos_for(value)
            active = (index == self._active) and self.hasFocus()
            handle = QRectF(x - 6, groove.top() - 8, 12, groove.height() + 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.INK if self._supported else theme.INK_FAINT))
            painter.drawRoundedRect(handle, 3, 3)
            if active:
                pen = QPen(QColor(theme.FOCUS_RING))
                pen.setWidthF(1.8)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(handle.adjusted(-3, -3, 3, 3), 4, 4)

            painter.setFont(theme.font(theme.SIZE_LABEL, 700, mono=True))
            painter.setPen(QColor(theme.INK if self._supported else theme.INK_FAINT))
            painter.drawText(QRect(int(x) - 24, int(groove.top()) - 28, 48, 20),
                             Qt.AlignmentFlag.AlignHCenter, f"{value}")
        painter.end()


# ═══════════════════════════════════════════════════════════
# طبقة التوصيات المعلَّمة
# ═══════════════════════════════════════════════════════════

class AdviceRow(_Plate):
    """صف توصية: علامة الشدّة، النص، السند، وإجراء واحد"""

    actionTriggered = pyqtSignal(str)

    def __init__(self, severity: str, text: str, evidence: str = '',
                 action: str = '', parent: Optional[QWidget] = None):
        super().__init__('groove', parent)
        self._severity = severity

        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_3, theme.SPACE_2, theme.SPACE_3, theme.SPACE_2)
        layout.setSpacing(theme.SPACE_3)

        mark = QLabel()
        mark.setPixmap(icons.pixmap(icons.SEVERITY_ICONS.get(severity, 'info'), 18,
                                    theme.SEVERITY_COLORS.get(severity, theme.INK_DIM)))
        mark.setFixedWidth(20)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # حاوية محدودة العرض بدل تحديد عرض التسمية نفسها: التسمية الملتفّة
        # داخل تخطيط أوسع تحسب ارتفاعها على العرض الكامل ثم تُقصّ.
        holder = QWidget()
        holder.setMaximumWidth(theme.MAX_TEXT_WIDTH)
        body = QVBoxLayout(holder)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)

        message = QLabel(text)
        message.setWordWrap(True)
        message.setFont(theme.font(theme.SIZE_BODY, 500))
        body.addWidget(message)

        if evidence:
            source = QLabel(evidence)
            source.setFont(theme.legend_font(11))
            source.setStyleSheet(f"color: {theme.INK_FAINT};")
            source.setOpenExternalLinks(True)
            source.setTextFormat(Qt.TextFormat.RichText)
            source.setWordWrap(True)
            body.addWidget(source)

        layout.addWidget(mark)
        layout.addWidget(holder, 1)

        layout.addStretch(1)

        if action:
            button = QPushButton(t(f'action.{action}'))
            button.setProperty('role', 'live' if severity in ('critical', 'warning') else 'quiet')
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            # الزر لا يتمدد: عرضه من نصّه، والفراغ يذهب للمساحة لا للزر
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda: self.actionTriggered.emit(action))
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)


class AdviceLayer(QWidget):
    """
    الطبقة التي تمرّ فوق الأرض الثابتة: توصيات مرتّبة بالشدّة، كل واحدة
    بسندها. لا تعديل على القياس، ولا تكرار لنفس المعرّف.
    """

    actionTriggered = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(theme.SPACE_2)

        # العنوان يأتي من الصفيحة الحاوية، فلا يُكرَّر هنا
        self._empty = QLabel(t('advice.empty'))
        self._empty.setFont(theme.font(theme.SIZE_BODY, 500))
        self._empty.setStyleSheet(f"color: {theme.INK_FAINT};")
        self._layout.addWidget(self._empty)

        self._rows: List[AdviceRow] = []

    def set_rows(self, rows: List[Dict]) -> None:
        """rows: [{'severity','text','evidence','action'}]"""
        for row in self._rows:
            self._layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        self._empty.setVisible(not rows)
        for data in rows:
            row = AdviceRow(data.get('severity', 'advice'), data.get('text', ''),
                            data.get('evidence', ''), data.get('action', ''))
            row.actionTriggered.connect(self.actionTriggered.emit)
            self._layout.addWidget(row)
            self._rows.append(row)


# ═══════════════════════════════════════════════════════════
# لوحة التشخيص
# ═══════════════════════════════════════════════════════════

class FindingCard(_Plate):
    """
    نتيجة تشخيص واحدة: علامة الشدّة، الحكم، الأدلة الخام كما قُرئت، خطوات
    المعالجة، ودرجة الثقة. الأدلة ليست تفصيلاً ثانوياً: هي ما يجعل الحكم
    قابلاً للتحقق بدل أن يكون رأياً.
    """

    def __init__(self, severity: str, title: str, evidence: List[str],
                 remediation: List[str], confidence: int,
                 parent: Optional[QWidget] = None):
        super().__init__('groove', parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_3, theme.SPACE_3, theme.SPACE_3, theme.SPACE_3)
        layout.setSpacing(theme.SPACE_2)

        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_2)
        mark = QLabel()
        mark.setPixmap(icons.pixmap(icons.SEVERITY_ICONS.get(severity, 'info'), 18,
                                    theme.SEVERITY_COLORS.get(severity, theme.INK_DIM)))
        mark.setFixedWidth(20)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        message = QLabel(title)
        message.setWordWrap(True)
        message.setFont(theme.font(theme.SIZE_BODY, 600))

        badge = QLabel(t('diag.confidence', value=int(confidence)))
        badge.setFont(theme.legend_font(11))
        badge.setStyleSheet(f"color: {theme.INK_FAINT};")

        header.addWidget(mark)
        header.addWidget(message, 1)
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        if evidence:
            evidence_label = QLabel('\n'.join(evidence))
            evidence_label.setFont(theme.font(theme.SIZE_LABEL, 500, mono=True))
            evidence_label.setStyleSheet(f"color: {theme.PHOSPHOR};")
            evidence_label.setWordWrap(True)
            layout.addWidget(evidence_label)

        for step in remediation:
            row = QHBoxLayout()
            row.setSpacing(theme.SPACE_2)
            bullet = QLabel()
            bullet.setPixmap(icons.pixmap('chevron', 13, theme.INK_FAINT))
            bullet.setFixedWidth(15)
            bullet.setAlignment(Qt.AlignmentFlag.AlignTop)
            text = QLabel(step)
            text.setWordWrap(True)
            text.setFont(theme.font(theme.SIZE_LABEL, 500))
            text.setStyleSheet(f"color: {theme.INK_DIM};")
            row.addWidget(bullet)
            row.addWidget(text, 1)
            layout.addLayout(row)


class DiagnosticsPanel(QWidget):
    """
    لوحة التشخيص: تقدير عام، نمط الجهاز، نتائج مصنَّفة بأدلتها، وجدول خام
    لكل ما قُرئ. تعمل بلا بطارية أيضاً: الغياب نفسه نتيجة.
    """

    scanRequested = pyqtSignal()
    exportRequested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACE_3)

        # ── الحكم العام ──
        summary = _Plate('plate')
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(theme.SPACE_4, theme.SPACE_3,
                                          theme.SPACE_4, theme.SPACE_3)
        summary_layout.setSpacing(theme.SPACE_2)

        top_row = QHBoxLayout()
        top_row.setSpacing(theme.SPACE_3)
        self.grade_label = QLabel(t('diag.grade.unknown'))
        self.grade_label.setFont(theme.font(theme.SIZE_SECTION, 700))
        self.grade_label.setWordWrap(True)
        top_row.addWidget(self.grade_label, 1)

        self.scan_button = QPushButton(t('diag.run'))
        self.scan_button.setProperty('role', 'live')
        self.scan_button.setIcon(icons.icon('crosshair', 15, theme.INK_ON_FIELD))
        self.scan_button.clicked.connect(self.scanRequested.emit)
        top_row.addWidget(self.scan_button, 0)

        self.export_button = QPushButton(t('diag.export'))
        self.export_button.setProperty('role', 'quiet')
        self.export_button.setIcon(icons.icon('copy', 14, theme.INK_DIM))
        self.export_button.clicked.connect(self.exportRequested.emit)
        top_row.addWidget(self.export_button, 0)
        summary_layout.addLayout(top_row)

        self.meta_label = QLabel('')
        self.meta_label.setFont(theme.font(theme.SIZE_LABEL, 500, mono=True))
        self.meta_label.setStyleSheet(f"color: {theme.INK_DIM};")
        self.meta_label.setWordWrap(True)
        summary_layout.addWidget(self.meta_label)
        layout.addWidget(summary)

        # ── النتائج ──
        findings_plate = _Plate('plate')
        findings_layout = QVBoxLayout(findings_plate)
        findings_layout.setContentsMargins(theme.SPACE_4, theme.SPACE_3,
                                           theme.SPACE_4, theme.SPACE_4)
        findings_layout.setSpacing(theme.SPACE_2)

        findings_title = QLabel(t('diag.findings'))
        findings_title.setFont(theme.legend_font())
        findings_title.setStyleSheet(f"color: {theme.INK_FAINT};")
        findings_layout.addWidget(findings_title)

        self.empty_label = QLabel(t('diag.no_findings'))
        self.empty_label.setFont(theme.font(theme.SIZE_BODY, 500))
        self.empty_label.setStyleSheet(f"color: {theme.INK_FAINT};")
        self.empty_label.setWordWrap(True)
        findings_layout.addWidget(self.empty_label)

        self.findings_grid = ResponsiveGrid(min_column_width=420, max_columns=2)
        findings_layout.addWidget(self.findings_grid)
        layout.addWidget(findings_plate)

        # ── الجدول الخام ──
        raw_plate = _Plate('plate')
        raw_layout = QVBoxLayout(raw_plate)
        raw_layout.setContentsMargins(theme.SPACE_4, theme.SPACE_3,
                                      theme.SPACE_4, theme.SPACE_4)
        raw_layout.setSpacing(theme.SPACE_2)

        raw_title = QLabel(t('diag.raw'))
        raw_title.setFont(theme.legend_font())
        raw_title.setStyleSheet(f"color: {theme.INK_FAINT};")
        raw_layout.addWidget(raw_title)

        self.raw_view = QTextEdit()
        self.raw_view.setReadOnly(True)
        self.raw_view.setMinimumHeight(220)
        self.raw_view.setFont(theme.font(theme.SIZE_LABEL, 500, mono=True))
        self.raw_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        raw_layout.addWidget(self.raw_view)
        layout.addWidget(raw_plate)

    # ── العرض ───────────────────────────────────────────────

    def set_busy(self, busy: bool) -> None:
        self.scan_button.setEnabled(not busy)
        self.scan_button.setText(t('diag.running') if busy else t('diag.run'))

    def set_report(self, grade_text: str, grade_color: str, meta: str,
                   findings: List[Dict], raw_rows: List[tuple]) -> None:
        self.grade_label.setText(grade_text)
        self.grade_label.setStyleSheet(f"color: {grade_color};")
        self.meta_label.setText(meta)

        self.findings_grid.clear()
        self.empty_label.setVisible(not findings)
        for finding in findings:
            self.findings_grid.add(FindingCard(
                finding.get('severity', 'info'),
                finding.get('title', ''),
                finding.get('evidence') or [],
                finding.get('remediation') or [],
                int(finding.get('confidence', 0)),
            ))

        width = max((len(row[0]) for row in raw_rows), default=24) + 2
        lines = []
        for path, value, status in raw_rows:
            marker = '' if status == 'ok' else f"  [{status}]"
            lines.append(f"{path.ljust(width)}{value}{marker}")
        self.raw_view.setPlainText('\n'.join(lines))

    def raw_text(self) -> str:
        return self.raw_view.toPlainText()
