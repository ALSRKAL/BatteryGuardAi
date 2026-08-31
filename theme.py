#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظام التصميم - BatteryGuardAI
عالم «لوحة القياس»: لوحة ألمنيوم مؤكسد مطفأة، حروف مطبوعة سلك-سكرين،
حواف محفورة بحدّين (ضوء أعلى وظل أسفل)، حبر فوسفوري واحد لكل رسوم القياس،
واللون محفوظ للحالة وحدها.

هذا الملف هو المصدر الوحيد لكل لون ومقاس وخط في التطبيق. لا قيمة لونية
مكتوبة داخل أي واجهة: أي حاجة جديدة تُضاف هنا أولاً.

قواعد العالم (مُلزمة عند أي تعديل):
- لا تدرّجات لونية على النصوص، ولا هالات ملوّنة بلا إزاحة كظل.
- الحواف نصف قطرها صغير (4 إلى 6 بكسل): لوحة أجهزة لا كبسولات.
- الأيقونات مرسومة بخط واحد الثخانة (icons.py)، ولا إيموجي في الواجهة.
- الحالة تُقرأ بعلامة ونص ولون معاً، لا باللون وحده.
- حقل الحالة مشبع ويأخذ مساحة كبيرة: اللون معلومة لا زخرفة.
"""

from typing import Dict, Iterable, Optional, Tuple

# ═══════════════════════════════════════════════════════════
# الأسطح: ألمنيوم مؤكسد مطفأ
# ═══════════════════════════════════════════════════════════

WINDOW = "#15181B"          # خلفية النافذة (أعمق سطح)
PANEL = "#1F2328"           # اللوحة الأساسية
PANEL_RAISED = "#282D33"    # صفيحة مرفوعة فوق اللوحة
PANEL_SUNKEN = "#111417"    # تجويف محفور (مجارٍ، حقول إدخال)
EDGE_LIGHT = "rgba(255, 255, 255, 0.08)"   # حرف الحفر العلوي
EDGE_DARK = "rgba(0, 0, 0, 0.55)"          # حرف الحفر السفلي
HAIRLINE = "#33383E"        # خط تقسيم بسماكة شعرة
HAIRLINE_STRONG = "#454B52"

# ═══════════════════════════════════════════════════════════
# الطباعة السلك-سكرين
# ═══════════════════════════════════════════════════════════

INK = "#E6E2D7"             # النص الأساسي المطبوع
INK_DIM = "#A7ACA5"         # نص ثانوي
INK_FAINT = "#767C77"       # أسطورة وتعليقات
INK_ON_FIELD = "#F2EFE6"    # نص فوق حقل حالة مشبع

# ═══════════════════════════════════════════════════════════
# حبر القياس (واحد فقط) والتفاوت بالكثافة
# ═══════════════════════════════════════════════════════════

PHOSPHOR = "#E0A63C"        # الحبر الوحيد لكل رسوم القياس
PHOSPHOR_DIM = "rgba(224, 166, 60, 0.42)"
PHOSPHOR_FAINT = "rgba(224, 166, 60, 0.16)"

# ═══════════════════════════════════════════════════════════
# ألوان الحالة (اللون معلومة: حقل مشبع يملك مساحة الشاشة)
# ═══════════════════════════════════════════════════════════

FIELD_MAINS = "#16508F"     # موصول بالكهرباء / يشحن
FIELD_WINDOW = "#1B5645"    # داخل النافذة الصحية على البطارية
FIELD_DISCHARGE = "#8A5410"  # يفرّغ خارج النافذة
FIELD_CRITICAL = "#8C2318"  # شحن حرج
FIELD_DEAD = "#2B3035"      # لا إشارة: بلا لون بشكل مقصود

STATE_MAINS = "#3C86E0"
STATE_OK = "#3E9E7C"
STATE_WARN = "#D98A21"
STATE_CRITICAL = "#D0483A"
STATE_DEAD = "#7A8189"

#: لون كل شدّة نصيحة (نفس مفردات الحالة، لا لوحة ثانية)
SEVERITY_COLORS: Dict[str, str] = {
    'critical': STATE_CRITICAL,
    'warning': STATE_WARN,
    'advice': STATE_MAINS,
    'good': STATE_OK,
}

#: طبقات القدرة: الأرض الثابتة تُقرأ بلون واحد لكل طبقة
TIER_COLORS: Dict[str, str] = {
    'hardware_control': STATE_OK,
    'firmware_setting': STATE_WARN,
    'notify_only': STATE_DEAD,
}

# ═══════════════════════════════════════════════════════════
# أطراف التوصيل (عناصر التفاعل)
# ═══════════════════════════════════════════════════════════

JACK_LIVE = "#C24634"       # الطرف الحيّ: الإجراء الأساسي
JACK_LIVE_HOVER = "#D2543F"
JACK_NEUTRAL = "#3A4046"    # الطرف المحايد: إجراء ثانوي
JACK_NEUTRAL_HOVER = "#464D54"
FOCUS_RING = "#E0A63C"

#: النافذة الافتراضية المعروضة قبل قراءة الإعدادات (الأدنى، الأقصى)
OPTIMAL_WINDOW_DEFAULT: Tuple[int, int] = (40, 80)

# ═══════════════════════════════════════════════════════════
# المقاسات: سلّم واحد للتباعد ونصف قطر صغير
# ═══════════════════════════════════════════════════════════

SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_5, SPACE_6 = 4, 8, 12, 16, 24, 32

RADIUS_PLATE = 6            # صفيحة مرفوعة
RADIUS_CONTROL = 4          # زر، حقل، خلية
RADIUS_GROOVE = 3           # تجويف محفور

BORDER_HAIRLINE = 1
DETENT_WIDTH = 2            # سماكة علامة المسنّنة

# ═══════════════════════════════════════════════════════════
# الخطوط: وجهان فقط
#   العربية والعناوين: كوفي هندسي يشبه الحرف المحفور
#   الأرقام والوحدات واللاتينية: أحادي العرض للقياس (بيانات، لا زينة)
# ═══════════════════════════════════════════════════════════

ARABIC_STACK: Tuple[str, ...] = (
    "Noto Kufi Arabic", "IBM Plex Sans Arabic", "Noto Sans Arabic",
    "Tahoma", "Segoe UI", "DejaVu Sans",
)
MONO_STACK: Tuple[str, ...] = (
    "DM Mono", "IBM Plex Mono", "Cascadia Mono", "Consolas",
    "DejaVu Sans Mono", "monospace",
)

SIZE_READOUT = 76           # الرقم الأساسي على حقل الحالة
SIZE_READOUT_SM = 34
SIZE_TITLE = 23
SIZE_SECTION = 17
SIZE_BODY = 15
SIZE_LABEL = 14
SIZE_LEGEND = 12            # أسطورة مطبوعة بأحرف متباعدة

#: أقصى عرض لعمود النص المقروء (بكسل) - السطر الطويل لا يُقرأ
MAX_TEXT_WIDTH = 780

#: أقصى عرض للوحة كاملة على شاشة عريضة
MAX_CONTENT_WIDTH = 1180

TRACKING_LEGEND = 1.4       # تباعد أحرف الأسطورة (بكسل)

_resolved_fonts: Dict[str, str] = {}


def resolve_font(stack: Iterable[str], fallback: str = "") -> str:
    """
    أول خط متوفر فعلاً على النظام من قائمة مرتّبة.
    يُخزَّن الناتج لأن استعلام قاعدة الخطوط ليس مجانياً.
    """
    key = "|".join(stack)
    cached = _resolved_fonts.get(key)
    if cached is not None:
        return cached

    chosen = fallback
    try:
        from PyQt6.QtGui import QFontDatabase
        from PyQt6.QtWidgets import QApplication
        if QApplication.instance() is None:
            # لا يجوز لمس قاعدة الخطوط قبل إنشاء التطبيق (تنهار Qt لا ترمي استثناءً)
            return fallback or next(iter(stack), "")
        available = {name.lower() for name in QFontDatabase.families()}
        for family in stack:
            if family.lower() in available:
                chosen = family
                break
        else:
            chosen = fallback or next(iter(stack), "")
    except Exception:  # pragma: no cover - بيئة بلا Qt (اختبارات نقية)
        chosen = fallback or next(iter(stack), "")

    _resolved_fonts[key] = chosen
    return chosen


def arabic_family() -> str:
    """وجه النصوص العربية والعناوين"""
    return resolve_font(ARABIC_STACK, "DejaVu Sans")


def mono_family() -> str:
    """وجه الأرقام والقياسات"""
    return resolve_font(MONO_STACK, "DejaVu Sans Mono")


def font(size: int = SIZE_BODY, weight: int = 500, mono: bool = False,
         tracking: Optional[float] = None):
    """
    بناء QFont من رموز النظام. الأرقام أحادية العرض دائماً حتى لا ترتجف
    القراءة عند تغيّر القيمة.
    """
    from PyQt6.QtGui import QFont
    qfont = QFont(mono_family() if mono else arabic_family())
    qfont.setPixelSize(size)
    qfont.setWeight(QFont.Weight(weight))
    if mono:
        qfont.setStyleHint(QFont.StyleHint.Monospace)
        qfont.setFixedPitch(True)
    if tracking is not None:
        qfont.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    return qfont


def legend_font(size: int = SIZE_LEGEND):
    """خط الأسطورة المطبوعة: صغير، متباعد، ثقيل قليلاً"""
    return font(size, weight=600, tracking=TRACKING_LEGEND)


def font_css(size: int = SIZE_BODY, weight: int = 500, mono: bool = False,
             color: Optional[str] = None, tracking: Optional[float] = None) -> str:
    """
    نفس رموز الخط لكن كتصريحات CSS.

    لازمة لا زائدة: ورقة أنماط التطبيق تحتوي `QWidget { font-size: 15px }`،
    وقاعدة ورقة الأنماط في Qt تتجاوز `setFont()` على أي عنصر تُطبَّق عليه.
    أي قراءة كبيرة تُضبط بـ `setFont` وحده تُرسم بحجم النص العادي بلا خطأ
    ظاهر، وهذا ما جعل رقم التذكير يُرسم بحجم السطر العادي.

    تُستخدم داخل `setStyleSheet` للعنصر نفسه، فتفوز بالخصوصية.
    """
    family = mono_family() if mono else arabic_family()
    parts = [
        f'font-family: "{family}"',
        f'font-size: {size}px',
        f'font-weight: {weight}',
    ]
    if color:
        parts.append(f'color: {color}')
    if tracking is not None:
        parts.append(f'letter-spacing: {tracking}px')
    return '; '.join(parts) + ';'


# ═══════════════════════════════════════════════════════════
# حالة الجهاز ← حقل اللون
# ═══════════════════════════════════════════════════════════

def field_for_state(percent: float, is_charging: bool, reporting: bool = True,
                    floor: int = 40, ceiling: int = 80) -> Tuple[str, str, str]:
    """
    حقل الحالة (خلفية، لون العلامة، مفتاح العنوان).
    ترتيب القرار مقصود: عدم التبليغ أولاً، فالحرج، فالكهرباء، فالنافذة.
    """
    if not reporting:
        return FIELD_DEAD, STATE_DEAD, 'status.headline_unreporting'
    if not is_charging and percent <= 10:
        return FIELD_CRITICAL, STATE_CRITICAL, 'status.headline_severe'
    if is_charging:
        return FIELD_MAINS, STATE_MAINS, 'status.headline_healthy'
    if floor <= percent <= ceiling:
        return FIELD_WINDOW, STATE_OK, 'status.headline_healthy'
    if percent < floor:
        return FIELD_DISCHARGE, STATE_WARN, 'status.headline_moderate'
    return FIELD_DISCHARGE, STATE_WARN, 'status.headline_high'


def stress_color(band: str) -> str:
    """لون نطاق الإجهاد"""
    return {
        'low': STATE_OK,
        'moderate': STATE_WARN,
        'high': STATE_WARN,
        'severe': STATE_CRITICAL,
    }.get(band, STATE_DEAD)


#: أولوية الإشعار ← لون الحالة المقابل (نفس مفردات اللوحة، لا لوحة ثانية)
URGENCY_COLORS: Dict[str, str] = {
    'critical': STATE_CRITICAL,
    'high': STATE_WARN,
    'normal': STATE_MAINS,
    'low': STATE_DEAD,
    'success': STATE_OK,
    'info': STATE_MAINS,
}


def notification_colors(urgency: str) -> Dict[str, str]:
    """ألوان حوار الإشعار: لوحة داكنة وحرف ملوّن يحمل الأولوية"""
    accent = URGENCY_COLORS.get(urgency, STATE_MAINS)
    return {
        'bg': PANEL,
        'border': accent,
        'accent': accent,
        'text': INK,
        'muted': INK_DIM,
        'icon': accent,
    }


#: أدوار الأزرار في الحوارات ← (خلفية، خلفية عند المرور، لون النص)
_BUTTON_ROLES: Dict[str, Tuple[str, str, str]] = {
    'live': (JACK_LIVE, JACK_LIVE_HOVER, INK_ON_FIELD),
    'danger': (JACK_LIVE, JACK_LIVE_HOVER, INK_ON_FIELD),
    'primary': (JACK_NEUTRAL, JACK_NEUTRAL_HOVER, INK),
    'neutral': (JACK_NEUTRAL, JACK_NEUTRAL_HOVER, INK),
    'secondary': (JACK_NEUTRAL, JACK_NEUTRAL_HOVER, INK),
    'success': (JACK_NEUTRAL, JACK_NEUTRAL_HOVER, STATE_OK),
    'warning': (JACK_NEUTRAL, JACK_NEUTRAL_HOVER, STATE_WARN),
    'quiet': ('transparent', PANEL_RAISED, INK_DIM),
}


def button_style(role: str = 'neutral') -> str:
    """نمط زر واحد مشتق من الرموز (يُستخدم في الحوارات المستقلة)"""
    background, hover, text = _BUTTON_ROLES.get(role, _BUTTON_ROLES['neutral'])
    return f"""
        QPushButton {{
            background-color: {background};
            color: {text};
            border: {BORDER_HAIRLINE}px solid {EDGE_DARK};
            border-top-color: {EDGE_LIGHT};
            border-radius: {RADIUS_CONTROL}px;
            padding: {SPACE_2}px {SPACE_4}px;
            font-size: {SIZE_LABEL}px;
            font-weight: 600;
        }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {PANEL_SUNKEN}; }}
    """


# ═══════════════════════════════════════════════════════════
# ورقة الأنماط: تُبنى مرة وتُطبَّق على التطبيق كله
# ═══════════════════════════════════════════════════════════

def stylesheet() -> str:
    """
    أنماط Qt المشتقّة من الرموز أعلاه. تشمل الأسطح التي لا نرسمها بأنفسنا
    (أشرطة التمرير، حلقات التركيز، التلميحات) لأنها تحمل الهوية أيضاً.
    """
    arabic = arabic_family()
    mono = mono_family()

    return f"""
    QMainWindow, QDialog {{
        background-color: {WINDOW};
    }}
    QWidget {{
        background-color: transparent;
        color: {INK};
        font-family: "{arabic}";
        font-size: {SIZE_BODY}px;
    }}
    QLabel {{
        color: {INK};
        background: transparent;
    }}
    QLabel[role="legend"] {{
        color: {INK_FAINT};
        font-size: {SIZE_LEGEND}px;
        font-weight: 600;
    }}
    QLabel[role="dim"] {{
        color: {INK_DIM};
    }}
    QLabel[role="measure"] {{
        font-family: "{mono}";
        color: {PHOSPHOR};
    }}

    /* ── الصفائح المرفوعة: حفر بحدّين لا ظل ملوّن ── */
    QFrame[role="plate"] {{
        background-color: {PANEL};
        border: {BORDER_HAIRLINE}px solid {HAIRLINE};
        border-top-color: {EDGE_LIGHT};
        border-bottom-color: {EDGE_DARK};
        border-radius: {RADIUS_PLATE}px;
    }}
    QFrame[role="groove"] {{
        background-color: {PANEL_SUNKEN};
        border: {BORDER_HAIRLINE}px solid {EDGE_DARK};
        border-top-color: {EDGE_DARK};
        border-bottom-color: {EDGE_LIGHT};
        border-radius: {RADIUS_GROOVE}px;
    }}
    QFrame[role="rail"] {{
        background-color: {PANEL_RAISED};
        border: none;
        border-bottom: {BORDER_HAIRLINE}px solid {EDGE_DARK};
    }}

    QGroupBox {{
        background-color: {PANEL};
        border: {BORDER_HAIRLINE}px solid {HAIRLINE};
        border-radius: {RADIUS_PLATE}px;
        margin-top: {SPACE_5}px;
        padding: {SPACE_5}px {SPACE_4}px {SPACE_4}px {SPACE_4}px;
        font-size: {SIZE_LEGEND}px;
        font-weight: 600;
        color: {INK_FAINT};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top right;
        right: {SPACE_4}px;
        top: {SPACE_2}px;
        padding: 0 {SPACE_2}px;
        background-color: {WINDOW};
        color: {INK_FAINT};
    }}

    /* ── مُحدِّد المجال (التبويبات) ── */
    QTabWidget::pane {{
        background-color: {PANEL};
        border: {BORDER_HAIRLINE}px solid {HAIRLINE};
        border-radius: {RADIUS_PLATE}px;
        top: -1px;
    }}
    QTabBar {{
        background: transparent;
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background-color: {PANEL_SUNKEN};
        color: {INK_FAINT};
        border: {BORDER_HAIRLINE}px solid {HAIRLINE};
        border-bottom: none;
        border-top-left-radius: {RADIUS_CONTROL}px;
        border-top-right-radius: {RADIUS_CONTROL}px;
        padding: {SPACE_2}px {SPACE_5}px;
        margin-left: 2px;
        font-size: {SIZE_LABEL}px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    QTabBar::tab:hover {{
        color: {INK_DIM};
        background-color: {PANEL};
    }}
    QTabBar::tab:selected {{
        background-color: {PANEL};
        color: {INK};
        border-color: {HAIRLINE_STRONG};
    }}

    /* ── الأزرار: طرف حيّ وطرف محايد ── */
    QPushButton {{
        background-color: {JACK_NEUTRAL};
        color: {INK};
        border: {BORDER_HAIRLINE}px solid {EDGE_DARK};
        border-top-color: {EDGE_LIGHT};
        border-radius: {RADIUS_CONTROL}px;
        padding: {SPACE_2}px {SPACE_4}px;
        font-size: {SIZE_LABEL}px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {JACK_NEUTRAL_HOVER}; }}
    QPushButton:pressed {{ background-color: {PANEL_SUNKEN}; }}
    QPushButton:disabled {{
        background-color: {PANEL};
        color: {INK_FAINT};
        border-color: {HAIRLINE};
    }}
    QPushButton[role="live"] {{
        background-color: {JACK_LIVE};
        color: {INK_ON_FIELD};
        border-color: {EDGE_DARK};
    }}
    QPushButton[role="live"]:hover {{ background-color: {JACK_LIVE_HOVER}; }}
    QPushButton[role="quiet"] {{
        background-color: transparent;
        color: {INK_DIM};
        border-color: {HAIRLINE};
    }}
    QPushButton[role="quiet"]:hover {{
        color: {INK};
        border-color: {HAIRLINE_STRONG};
    }}

    /* ── الحقول والمفاتيح ── */
    QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{
        background-color: {PANEL_SUNKEN};
        color: {PHOSPHOR};
        font-family: "{mono}";
        border: {BORDER_HAIRLINE}px solid {EDGE_DARK};
        border-bottom-color: {EDGE_LIGHT};
        border-radius: {RADIUS_GROOVE}px;
        padding: {SPACE_1}px {SPACE_2}px;
        selection-background-color: {PHOSPHOR};
        selection-color: {WINDOW};
        min-height: 22px;
    }}
    QSpinBox:focus, QLineEdit:focus, QComboBox:focus {{
        border-color: {FOCUS_RING};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: {JACK_NEUTRAL};
        border: none;
        width: 16px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background-color: {JACK_NEUTRAL_HOVER};
    }}
    QSpinBox::up-arrow {{
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid {INK_DIM};
    }}
    QSpinBox::down-arrow {{
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {INK_DIM};
    }}

    QCheckBox {{
        color: {INK};
        spacing: {SPACE_2}px;
        padding: {SPACE_1}px 0;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        background-color: {PANEL_SUNKEN};
        border: {BORDER_HAIRLINE}px solid {HAIRLINE_STRONG};
        border-radius: 2px;
    }}
    QCheckBox::indicator:hover {{ border-color: {FOCUS_RING}; }}
    QCheckBox::indicator:checked {{
        background-color: {PHOSPHOR};
        border-color: {PHOSPHOR};
    }}
    QCheckBox:disabled {{ color: {INK_FAINT}; }}

    QSlider::groove:horizontal {{
        background-color: {PANEL_SUNKEN};
        height: 6px;
        border: {BORDER_HAIRLINE}px solid {EDGE_DARK};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background-color: {PHOSPHOR_DIM};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background-color: {INK_DIM};
        border: {BORDER_HAIRLINE}px solid {EDGE_DARK};
        width: 12px;
        margin: -5px 0;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal:hover {{ background-color: {INK}; }}

    /* ── التقدّم: شريط قياس بحبر واحد ── */
    QProgressBar {{
        background-color: {PANEL_SUNKEN};
        border: {BORDER_HAIRLINE}px solid {EDGE_DARK};
        border-radius: 2px;
        height: 8px;
        text-align: center;
        color: {INK_DIM};
        font-family: "{mono}";
        font-size: {SIZE_LEGEND}px;
    }}
    QProgressBar::chunk {{
        background-color: {PHOSPHOR};
        border-radius: 1px;
    }}

    /* ── الأسطح التي لم نرسمها: تحمل الهوية أيضاً ── */
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{
        background-color: {PANEL_SUNKEN};
        width: 10px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background-color: {JACK_NEUTRAL};
        min-height: 28px;
        border-radius: 2px;
    }}
    QScrollBar::handle:vertical:hover {{ background-color: {JACK_NEUTRAL_HOVER}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QScrollBar:horizontal {{
        background-color: {PANEL_SUNKEN};
        height: 10px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {JACK_NEUTRAL};
        min-width: 28px;
        border-radius: 2px;
    }}

    QToolTip {{
        background-color: {PANEL_RAISED};
        color: {INK};
        border: {BORDER_HAIRLINE}px solid {HAIRLINE_STRONG};
        border-radius: {RADIUS_GROOVE}px;
        padding: {SPACE_1}px {SPACE_2}px;
        font-size: {SIZE_LABEL}px;
    }}
    QMenu {{
        background-color: {PANEL_RAISED};
        color: {INK};
        border: {BORDER_HAIRLINE}px solid {HAIRLINE_STRONG};
        border-radius: {RADIUS_CONTROL}px;
        padding: {SPACE_1}px;
    }}
    QMenu::item {{
        padding: {SPACE_1}px {SPACE_4}px;
        border-radius: 2px;
    }}
    QMenu::item:selected {{ background-color: {JACK_NEUTRAL}; }}
    QMenu::separator {{
        height: {BORDER_HAIRLINE}px;
        background-color: {HAIRLINE};
        margin: {SPACE_1}px {SPACE_2}px;
    }}
    QTextEdit, QPlainTextEdit, QListWidget {{
        background-color: {PANEL_SUNKEN};
        color: {INK};
        border: {BORDER_HAIRLINE}px solid {HAIRLINE};
        border-radius: {RADIUS_GROOVE}px;
        selection-background-color: {PHOSPHOR};
        selection-color: {WINDOW};
    }}
    """
