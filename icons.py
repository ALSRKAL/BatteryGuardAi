#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظام الأيقونات المرسومة - BatteryGuardAI

كل أيقونة مرسومة بمسارات على شبكة 24×24 بثخانة خط واحدة ونهايات مستديرة،
بلا أي إيموجي ولا حروف يونيكود بديلة. هذا هو المصدر الوحيد للأيقونات:
أي رمز جديد يُضاف هنا لا يُرسم داخل الواجهة.

الاستخدام:
    from icons import icon, draw
    button.setIcon(icon('bolt', 18, theme.PHOSPHOR))
    draw(painter, 'alert', QRect(x, y, 16, 16), theme.STATE_WARN)
"""

import logging
from typing import Callable, Dict, Optional, Tuple

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QIcon, QPainter, QPainterPath, QPen,
                         QPixmap)

logger = logging.getLogger('BatteryGuard')

GRID = 24.0
STROKE = 1.9                     # ثخانة الخط على شبكة 24 (نُقاس ونُحفظ ثابتة)

_cache: Dict[Tuple[str, int, str, float], QPixmap] = {}


# ═══════════════════════════════════════════════════════════
# مسارات الأيقونات (إحداثيات على شبكة 24×24)
# ═══════════════════════════════════════════════════════════

def _battery(p: QPainterPath) -> None:
    p.addRoundedRect(QRectF(2.5, 7.5, 16, 9), 1.5, 1.5)
    p.moveTo(20, 10.5)
    p.lineTo(20, 13.5)


def _battery_low(p: QPainterPath) -> None:
    _battery(p)
    p.addRect(QRectF(4.5, 9.5, 3.5, 5))


def _bolt(p: QPainterPath) -> None:
    p.moveTo(13.5, 2.5)
    p.lineTo(6, 13.5)
    p.lineTo(11, 13.5)
    p.lineTo(10.5, 21.5)
    p.lineTo(18, 10.5)
    p.lineTo(13, 10.5)
    p.closeSubpath()


def _plug(p: QPainterPath) -> None:
    p.moveTo(9, 2.5)
    p.lineTo(9, 7)
    p.moveTo(15, 2.5)
    p.lineTo(15, 7)
    p.addRoundedRect(QRectF(6, 7, 12, 7), 1.5, 1.5)
    p.moveTo(12, 14)
    p.lineTo(12, 21.5)


def _arrow_up(p: QPainterPath) -> None:
    p.moveTo(12, 20)
    p.lineTo(12, 4.5)
    p.moveTo(6.5, 10)
    p.lineTo(12, 4.5)
    p.lineTo(17.5, 10)


def _arrow_down(p: QPainterPath) -> None:
    p.moveTo(12, 4)
    p.lineTo(12, 19.5)
    p.moveTo(6.5, 14)
    p.lineTo(12, 19.5)
    p.lineTo(17.5, 14)


def _thermometer(p: QPainterPath) -> None:
    p.moveTo(10, 14.5)
    p.lineTo(10, 5.5)
    p.arcTo(QRectF(9.5, 3, 5, 5), 180, -180)
    p.lineTo(14.5, 14.5)
    p.arcTo(QRectF(8, 13, 8, 8), 60, 240)
    p.moveTo(16.5, 7)
    p.lineTo(19.5, 7)
    p.moveTo(16.5, 10.5)
    p.lineTo(18.5, 10.5)


def _gauge(p: QPainterPath) -> None:
    p.arcMoveTo(QRectF(3, 4.5, 18, 18), 200)
    p.arcTo(QRectF(3, 4.5, 18, 18), 200, -220)
    p.moveTo(12, 13.5)
    p.lineTo(16.5, 9)


def _pulse(p: QPainterPath) -> None:
    p.moveTo(2.5, 12)
    p.lineTo(7, 12)
    p.lineTo(9.5, 5.5)
    p.lineTo(13, 18.5)
    p.lineTo(15.5, 12)
    p.lineTo(21.5, 12)


def _cycle(p: QPainterPath) -> None:
    p.arcMoveTo(QRectF(3.5, 3.5, 17, 17), 60)
    p.arcTo(QRectF(3.5, 3.5, 17, 17), 60, 280)
    p.moveTo(14.5, 3.5)
    p.lineTo(19.5, 5.5)
    p.lineTo(17.5, 10)


def _clock(p: QPainterPath) -> None:
    p.addEllipse(QRectF(3.5, 3.5, 17, 17))
    p.moveTo(12, 7.5)
    p.lineTo(12, 12.5)
    p.lineTo(15.5, 14.5)


def _bell(p: QPainterPath) -> None:
    p.moveTo(6, 16.5)
    p.lineTo(6, 11)
    p.arcTo(QRectF(6, 3.5, 12, 12), 180, -180)
    p.lineTo(18, 16.5)
    p.closeSubpath()
    p.moveTo(4.5, 16.5)
    p.lineTo(19.5, 16.5)
    p.moveTo(10, 19.5)
    p.lineTo(14, 19.5)


def _gear(p: QPainterPath) -> None:
    p.addEllipse(QRectF(9, 9, 6, 6))
    p.addRoundedRect(QRectF(4.5, 4.5, 15, 15), 5, 5)


def _chart(p: QPainterPath) -> None:
    p.moveTo(3.5, 20.5)
    p.lineTo(20.5, 20.5)
    p.addRect(QRectF(5.5, 12, 3.5, 6))
    p.addRect(QRectF(10.5, 8, 3.5, 10))
    p.addRect(QRectF(15.5, 4.5, 3.5, 13.5))


def _check(p: QPainterPath) -> None:
    p.moveTo(4.5, 12.5)
    p.lineTo(9.5, 17.5)
    p.lineTo(19.5, 6.5)


def _alert(p: QPainterPath) -> None:
    p.moveTo(12, 3.5)
    p.lineTo(21.5, 20)
    p.lineTo(2.5, 20)
    p.closeSubpath()
    p.moveTo(12, 9)
    p.lineTo(12, 14)
    p.moveTo(12, 16.8)
    p.lineTo(12, 17.2)


def _blocked(p: QPainterPath) -> None:
    p.addEllipse(QRectF(3.5, 3.5, 17, 17))
    p.moveTo(6.5, 17.5)
    p.lineTo(17.5, 6.5)


def _copy(p: QPainterPath) -> None:
    p.addRoundedRect(QRectF(8.5, 8.5, 11, 11), 1.5, 1.5)
    p.moveTo(15.5, 5.5)
    p.lineTo(6, 5.5)
    p.lineTo(6, 15)


def _refresh(p: QPainterPath) -> None:
    p.arcMoveTo(QRectF(4, 4, 16, 16), 40)
    p.arcTo(QRectF(4, 4, 16, 16), 40, 280)
    p.moveTo(18.5, 3.5)
    p.lineTo(18.5, 8.5)
    p.lineTo(13.5, 8.5)


def _chevron(p: QPainterPath) -> None:
    p.moveTo(14.5, 5.5)
    p.lineTo(8.5, 12)
    p.lineTo(14.5, 18.5)


def _jaw(p: QPainterPath) -> None:
    """فكّ نافذة الشحن: قوسان متقابلان يحيطان بمجال"""
    p.moveTo(7.5, 4.5)
    p.lineTo(4.5, 4.5)
    p.lineTo(4.5, 19.5)
    p.lineTo(7.5, 19.5)
    p.moveTo(16.5, 4.5)
    p.lineTo(19.5, 4.5)
    p.lineTo(19.5, 19.5)
    p.lineTo(16.5, 19.5)
    p.moveTo(12, 8)
    p.lineTo(12, 16)


def _crosshair(p: QPainterPath) -> None:
    p.addEllipse(QRectF(5.5, 5.5, 13, 13))
    p.moveTo(12, 2.5)
    p.lineTo(12, 6)
    p.moveTo(12, 18)
    p.lineTo(12, 21.5)
    p.moveTo(2.5, 12)
    p.lineTo(6, 12)
    p.moveTo(18, 12)
    p.lineTo(21.5, 12)


def _info(p: QPainterPath) -> None:
    p.addEllipse(QRectF(3.5, 3.5, 17, 17))
    p.moveTo(12, 10.5)
    p.lineTo(12, 16.5)
    p.moveTo(12, 7.3)
    p.lineTo(12, 7.7)


def _power(p: QPainterPath) -> None:
    p.arcMoveTo(QRectF(4.5, 4.5, 15, 15), 65)
    p.arcTo(QRectF(4.5, 4.5, 15, 15), 65, 230)
    p.moveTo(12, 2.5)
    p.lineTo(12, 9.5)


def _mute(p: QPainterPath) -> None:
    _bell(p)
    p.moveTo(4.5, 4.5)
    p.lineTo(19.5, 19.5)


def _snooze(p: QPainterPath) -> None:
    _clock(p)
    p.moveTo(15, 4.5)
    p.lineTo(20.5, 4.5)
    p.lineTo(15, 9.5)
    p.lineTo(20.5, 9.5)


def _stop(p: QPainterPath) -> None:
    p.addRoundedRect(QRectF(5.5, 5.5, 13, 13), 1.5, 1.5)


def _close(p: QPainterPath) -> None:
    p.moveTo(5.5, 5.5)
    p.lineTo(18.5, 18.5)
    p.moveTo(18.5, 5.5)
    p.lineTo(5.5, 18.5)


def _minus(p: QPainterPath) -> None:
    p.moveTo(5.5, 12)
    p.lineTo(18.5, 12)


def _shield(p: QPainterPath) -> None:
    p.moveTo(12, 3)
    p.lineTo(19.5, 6)
    p.lineTo(19.5, 12)
    p.cubicTo(19.5, 17, 16, 19.5, 12, 21)
    p.cubicTo(8, 19.5, 4.5, 17, 4.5, 12)
    p.lineTo(4.5, 6)
    p.closeSubpath()


ICONS: Dict[str, Callable[[QPainterPath], None]] = {
    'battery': _battery,
    'battery_low': _battery_low,
    'bolt': _bolt,
    'plug': _plug,
    'arrow_up': _arrow_up,
    'arrow_down': _arrow_down,
    'thermometer': _thermometer,
    'gauge': _gauge,
    'pulse': _pulse,
    'cycle': _cycle,
    'clock': _clock,
    'bell': _bell,
    'gear': _gear,
    'chart': _chart,
    'check': _check,
    'alert': _alert,
    'blocked': _blocked,
    'copy': _copy,
    'refresh': _refresh,
    'chevron': _chevron,
    'jaw': _jaw,
    'crosshair': _crosshair,
    'info': _info,
    'power': _power,
    'mute': _mute,
    'snooze': _snooze,
    'stop': _stop,
    'close': _close,
    'minus': _minus,
    'shield': _shield,
}

#: أيقونة كل شدّة نصيحة (علامة إضافية فوق اللون، لا لون وحده)
SEVERITY_ICONS = {
    'critical': 'alert',
    'warning': 'alert',
    'advice': 'info',
    'good': 'check',
}

#: أيقونة كل طبقة قدرة
TIER_ICONS = {
    'hardware_control': 'check',
    'firmware_setting': 'info',
    'notify_only': 'blocked',
}


# ═══════════════════════════════════════════════════════════
# الرسم
# ═══════════════════════════════════════════════════════════

def draw(painter: QPainter, name: str, rect: QRect, color: str,
         stroke: float = STROKE, opacity: float = 1.0) -> bool:
    """
    رسم أيقونة داخل مستطيل. يعيد False إن كان الاسم غير معروف
    (بلا انهيار وبلا رمز بديل مضلّل).
    """
    builder = ICONS.get(name)
    if builder is None:
        logger.warning(f"أيقونة غير معروفة: {name}")
        return False

    path = QPainterPath()
    builder(path)

    scale = min(rect.width(), rect.height()) / GRID
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setOpacity(opacity)
    painter.translate(rect.x() + (rect.width() - GRID * scale) / 2.0,
                      rect.y() + (rect.height() - GRID * scale) / 2.0)
    painter.scale(scale, scale)

    pen = QPen(QColor(color))
    pen.setWidthF(stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.restore()
    return True


def pixmap(name: str, size: int = 20, color: str = '#E6E2D7',
           stroke: float = STROKE) -> QPixmap:
    """صورة أيقونة مخزّنة مؤقتاً (الرسم ليس مجانياً في حلقة تحديث)"""
    key = (name, size, color, stroke)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    draw(painter, name, QRect(0, 0, size, size), color, stroke)
    painter.end()

    _cache[key] = pm
    return pm


def icon(name: str, size: int = 20, color: str = '#E6E2D7') -> QIcon:
    """أيقونة Qt جاهزة للأزرار والقوائم"""
    return QIcon(pixmap(name, size, color))


def hatch_brush(color: str, spacing: int = 5) -> QBrush:
    """
    فرشاة تهشير مائل تُستخدم كـ«صفيحة مثقوبة» فوق أي قدرة غير مدعومة:
    العلامة تحمل المعنى حتى لو لم يُقرأ اللون.
    """
    tile = QPixmap(spacing * 2, spacing * 2)
    tile.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tile)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(1.0)
    painter.setPen(pen)
    painter.drawLine(QPointF(0, spacing * 2), QPointF(spacing * 2, 0))
    painter.drawLine(QPointF(-1, 1), QPointF(1, -1))
    painter.drawLine(QPointF(spacing * 2 - 1, spacing * 2 + 1),
                     QPointF(spacing * 2 + 1, spacing * 2 - 1))
    painter.end()
    return QBrush(tile)


def clear_cache() -> None:
    """تفريغ ذاكرة الأيقونات (عند تغيير السمة)"""
    _cache.clear()
