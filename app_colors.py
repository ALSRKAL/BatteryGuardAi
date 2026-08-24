#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ألوان التطبيق الموحدة - BatteryGuard Pro
نظام ألوان احترافي وهادئ
"""

# ═══════════════════════════════════════════════════════════
# الألوان الأساسية
# ═══════════════════════════════════════════════════════════

PRIMARY = "#3b82f6"      # أزرق - اللون الأساسي
PRIMARY_LIGHT = "#60a5fa"
PRIMARY_DARK = "#2563eb"
PRIMARY_BG = "#eff6ff"   # خلفية أزرق فاتح جداً

SUCCESS = "#10b981"      # أخضر - نجاح
SUCCESS_LIGHT = "#34d399"
SUCCESS_DARK = "#059669"
SUCCESS_BG = "#f0fdf4"

WARNING = "#f97316"      # برتقالي - تحذير (بدلاً من الأصفر المزعج)
WARNING_LIGHT = "#fb923c"
WARNING_DARK = "#ea580c"
WARNING_BG = "#fff7ed"

DANGER = "#ef4444"       # أحمر - خطر
DANGER_LIGHT = "#f87171"
DANGER_DARK = "#dc2626"
DANGER_BG = "#fef2f2"

INFO = "#06b6d4"         # سماوي - معلومات
INFO_LIGHT = "#22d3ee"
INFO_DARK = "#0891b2"
INFO_BG = "#ecfeff"

# ═══════════════════════════════════════════════════════════
# الألوان المحايدة
# ═══════════════════════════════════════════════════════════

GRAY_50 = "#f9fafb"
GRAY_100 = "#f3f4f6"
GRAY_200 = "#e5e7eb"
GRAY_300 = "#d1d5db"
GRAY_400 = "#9ca3af"
GRAY_500 = "#6b7280"
GRAY_600 = "#4b5563"
GRAY_700 = "#374151"
GRAY_800 = "#1f2937"
GRAY_900 = "#111827"

WHITE = "#ffffff"
BLACK = "#000000"

# ═══════════════════════════════════════════════════════════
# ألوان البطارية
# ═══════════════════════════════════════════════════════════

BATTERY_FULL = SUCCESS       # 80-100%
BATTERY_GOOD = PRIMARY       # 40-80%
BATTERY_LOW = WARNING        # 20-40%
BATTERY_CRITICAL = DANGER    # 0-20%

# ═══════════════════════════════════════════════════════════
# ألوان الإشعارات
# ═══════════════════════════════════════════════════════════

NOTIFICATION_COLORS = {
    'critical': {
        'bg': WHITE,
        'border': DANGER,
        'accent': DANGER_BG,
        'text': GRAY_900,
        'icon': DANGER
    },
    'high': {
        'bg': WHITE,
        'border': WARNING,
        'accent': WARNING_BG,
        'text': GRAY_900,
        'icon': WARNING
    },
    'normal': {
        'bg': WHITE,
        'border': PRIMARY,
        'accent': PRIMARY_BG,
        'text': GRAY_900,
        'icon': PRIMARY
    },
    'low': {
        'bg': WHITE,
        'border': GRAY_300,
        'accent': GRAY_50,
        'text': GRAY_700,
        'icon': GRAY_500
    },
    'success': {
        'bg': WHITE,
        'border': SUCCESS,
        'accent': SUCCESS_BG,
        'text': GRAY_900,
        'icon': SUCCESS
    },
    'info': {
        'bg': WHITE,
        'border': INFO,
        'accent': INFO_BG,
        'text': GRAY_900,
        'icon': INFO
    }
}

# ═══════════════════════════════════════════════════════════
# ألوان الأزرار
# ═══════════════════════════════════════════════════════════

BUTTON_STYLES = {
    'primary': {
        'bg': PRIMARY,
        'bg_hover': PRIMARY_DARK,
        'text': WHITE,
        'border': 'none'
    },
    'success': {
        'bg': SUCCESS,
        'bg_hover': SUCCESS_DARK,
        'text': WHITE,
        'border': 'none'
    },
    'warning': {
        'bg': WARNING,
        'bg_hover': WARNING_DARK,
        'text': WHITE,
        'border': 'none'
    },
    'danger': {
        'bg': DANGER,
        'bg_hover': DANGER_DARK,
        'text': WHITE,
        'border': 'none'
    },
    'secondary': {
        'bg': GRAY_200,
        'bg_hover': GRAY_300,
        'text': GRAY_700,
        'border': 'none'
    },
    'outline': {
        'bg': 'transparent',
        'bg_hover': GRAY_100,
        'text': GRAY_700,
        'border': f'1px solid {GRAY_300}'
    }
}

# ═══════════════════════════════════════════════════════════
# دوال مساعدة
# ═══════════════════════════════════════════════════════════

def get_notification_colors(urgency: str) -> dict:
    """الحصول على ألوان الإشعار حسب الأولوية"""
    return NOTIFICATION_COLORS.get(urgency, NOTIFICATION_COLORS['normal'])


def get_button_style(style: str) -> str:
    """الحصول على نمط الزر"""
    btn = BUTTON_STYLES.get(style, BUTTON_STYLES['secondary'])
    
    return f"""
        QPushButton {{
            background-color: {btn['bg']};
            color: {btn['text']};
            border: {btn['border']};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {btn['bg_hover']};
        }}
        QPushButton:pressed {{
            opacity: 0.8;
        }}
    """


def get_battery_color(percentage: int) -> str:
    """الحصول على لون البطارية حسب النسبة"""
    if percentage >= 80:
        return BATTERY_FULL
    elif percentage >= 40:
        return BATTERY_GOOD
    elif percentage >= 20:
        return BATTERY_LOW
    else:
        return BATTERY_CRITICAL


def get_battery_gradient(percentage: int) -> str:
    """الحصول على تدرج لوني للبطارية"""
    color = get_battery_color(percentage)
    
    if percentage >= 80:
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {SUCCESS_LIGHT}, stop:1 {SUCCESS})"
    elif percentage >= 40:
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {PRIMARY_LIGHT}, stop:1 {PRIMARY})"
    elif percentage >= 20:
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {WARNING_LIGHT}, stop:1 {WARNING})"
    else:
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {DANGER_LIGHT}, stop:1 {DANGER})"


# ═══════════════════════════════════════════════════════════
# أنماط Qt جاهزة
# ═══════════════════════════════════════════════════════════

DIALOG_STYLE = f"""
    QDialog {{
        background-color: {WHITE};
        border-radius: 12px;
    }}
"""

LABEL_TITLE_STYLE = f"""
    QLabel {{
        color: {GRAY_900};
        font-weight: bold;
    }}
"""

LABEL_SUBTITLE_STYLE = f"""
    QLabel {{
        color: {GRAY_600};
    }}
"""

LABEL_MUTED_STYLE = f"""
    QLabel {{
        color: {GRAY_500};
        font-size: 11px;
    }}
"""

SEPARATOR_STYLE = f"""
    QWidget {{
        background-color: {GRAY_200};
    }}
"""

SCROLLAREA_STYLE = f"""
    QScrollArea {{
        border: none;
        background-color: {GRAY_50};
    }}
"""

PROGRESSBAR_STYLE = f"""
    QProgressBar {{
        border: none;
        background-color: {GRAY_200};
        border-radius: 2px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {PRIMARY};
        border-radius: 2px;
    }}
"""


if __name__ == '__main__':
    # عرض الألوان
    print("═" * 60)
    print("  ألوان التطبيق - BatteryGuard Pro")
    print("═" * 60)
    
    print("\n🎨 الألوان الأساسية:")
    print(f"  Primary:  {PRIMARY}")
    print(f"  Success:  {SUCCESS}")
    print(f"  Warning:  {WARNING}")
    print(f"  Danger:   {DANGER}")
    print(f"  Info:     {INFO}")
    
    print("\n🔋 ألوان البطارية:")
    for percent in [90, 60, 30, 10]:
        color = get_battery_color(percent)
        print(f"  {percent}%: {color}")
    
    print("\n🔔 ألوان الإشعارات:")
    for urgency in ['critical', 'high', 'normal', 'success']:
        colors = get_notification_colors(urgency)
        print(f"  {urgency}: border={colors['border']}, bg={colors['bg']}")
    
    print("\n" + "═" * 60)
