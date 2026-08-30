#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تبويبات الواجهة - BatteryGuardAI

أربعة مجالات على مُحدِّد المجال: التحكم، التحليل، السجل، الإعدادات.
لا لون ولا مقاس مكتوب هنا: كل شيء من `theme`، والأيقونات من `icons`،
والنصوص من `i18n`. أي نمط محلي يعني كسر مصدر الحقيقة الواحد.

عقد الأسماء: كل عنصر تقرأه `main_window` يُنشأ هنا بنفس الاسم
(`parent.<attr>`) حتى تبقى طبقة التحديث واحدة ومستقلة عن التخطيط.
"""

import logging
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QPushButton, QScrollArea, QSpinBox,
                             QTextEdit, QVBoxLayout, QWidget)

import icons
import theme
from i18n import t
from panel_widgets import (AdviceLayer, CapabilityStrip, ChargeWindowJaw,
                           DiagnosticsPanel, ResponsiveGrid, StatePlate)

logger = logging.getLogger('BatteryGuard')


# ═══════════════════════════════════════════════════════════
# أدوات بناء مشتركة
# ═══════════════════════════════════════════════════════════

def create_styled_label(text: str, size: int = theme.SIZE_BODY,
                        color: Optional[str] = None, bold: bool = False,
                        mono: bool = False) -> QLabel:
    """
    تسمية بأسلوب النظام. تبقى هذه الدالة لأن وحدات أخرى تستدعيها،
    لكنها الآن تقرأ من رموز التصميم بدل قيم مكتوبة.
    """
    label = QLabel(text)
    label.setFont(theme.font(size, 700 if bold else 500, mono=mono))
    label.setStyleSheet(f"color: {color or theme.INK};")
    return label


def _legend(text: str) -> QLabel:
    """أسطورة مطبوعة: صغيرة، متباعدة، هادئة"""
    label = QLabel(text)
    label.setFont(theme.legend_font())
    label.setProperty('role', 'legend')
    label.setStyleSheet(f"color: {theme.INK_FAINT};")
    return label


def _plate(title_key: str) -> Tuple[QFrame, QVBoxLayout]:
    """صفيحة معنونة: العنوان أسطورة، والمحتوى في تخطيط عمودي"""
    plate = QFrame()
    plate.setProperty('role', 'plate')
    layout = QVBoxLayout(plate)
    layout.setContentsMargins(theme.SPACE_4, theme.SPACE_3, theme.SPACE_4, theme.SPACE_4)
    layout.setSpacing(theme.SPACE_3)
    layout.addWidget(_legend(t(title_key)))
    return plate, layout


def _measure_block(parent, rows: List[Tuple[str, str, str]],
                   min_column_width: int = 260) -> ResponsiveGrid:
    """
    كتلة قياسات تتوزّع على أعمدة حسب العرض المتاح، وتسجّل كل تسمية قيمة
    على `parent` بالاسم المتفق عليه.
    """
    grid = ResponsiveGrid(min_column_width=min_column_width, max_columns=4)
    for icon_name, key, attr in rows:
        row_widget, value_label = _measure_row(icon_name, key)
        setattr(parent, attr, value_label)
        grid.add(row_widget)
    return grid


def _measure_row(icon_name: str, label_key: str,
                 value_text: str = '—') -> Tuple[QWidget, QLabel]:
    """صف قياس: علامة، تسمية، قيمة بأرقام أحادية العرض"""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(theme.SPACE_2)

    mark = QLabel()
    mark.setPixmap(icons.pixmap(icon_name, 15, theme.INK_FAINT))
    mark.setFixedWidth(18)

    name = QLabel(t(label_key))
    name.setFont(theme.font(theme.SIZE_LABEL, 500))
    name.setStyleSheet(f"color: {theme.INK_DIM};")

    value = QLabel(value_text)
    value.setFont(theme.font(theme.SIZE_LABEL, 700, mono=True))
    value.setStyleSheet(f"color: {theme.PHOSPHOR};")

    layout.addWidget(mark)
    layout.addWidget(name)
    layout.addStretch(1)
    layout.addWidget(value)
    return row, value


def _check(text: str, tooltip: str = '') -> QCheckBox:
    box = QCheckBox(text)
    box.setFont(theme.font(theme.SIZE_BODY, 500))
    if tooltip:
        box.setToolTip(tooltip)
    return box


def _spin(minimum: int, maximum: int, value: int, suffix: str = '%') -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    spin.setSuffix(f" {suffix}" if suffix else '')
    spin.setMinimumWidth(84)
    spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return spin


def _scroll(content: QWidget) -> QScrollArea:
    """
    تمرير عمودي فقط: التمرير الأفقي يعني أن نصاً لم يُلَف، وذلك خطأ تخطيط
    لا ميزة تنقّل.
    """
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    return scroll


def _page() -> Tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(theme.SPACE_4, theme.SPACE_4, theme.SPACE_4, theme.SPACE_4)
    layout.setSpacing(theme.SPACE_4)
    return page, layout


# ═══════════════════════════════════════════════════════════
# مجال الحالة: القراءة الآن وما يستدعي تدخّلاً
# ═══════════════════════════════════════════════════════════

class StatusTab:
    """
    أول مجال يفتح عليه المستخدم: حقل الحالة بالقراءة الأساسية والأثر،
    ثم التوصية الواحدة أو الاثنتان الأهم. لا شيء آخر هنا حتى لا يتشتت.
    """

    @staticmethod
    def create(parent) -> QScrollArea:
        page, layout = _page()

        parent.state_plate = StatePlate()
        layout.addWidget(parent.state_plate)

        advice_plate, advice_layout = _plate('advice.title')
        parent.advice_layer = AdviceLayer()
        parent.advice_layer.actionTriggered.connect(parent.handle_advice_action)
        advice_layout.addWidget(parent.advice_layer)
        layout.addWidget(advice_plate)

        # ── ملخص الجهاز: يعمّر المساحة بحقائق لا بفراغ ──
        summary_plate, summary_layout = _plate('summary.title')
        summary_layout.addWidget(_measure_block(parent, [
            ('crosshair', 'summary.device', 'summary_device_label'),
            ('info', 'diag.device_mode', 'summary_mode_label'),
            ('shield', 'capability.title', 'summary_tier_label'),
            ('plug', 'summary.mains', 'summary_mains_label'),
            ('thermometer', 'summary.hottest_zone', 'summary_thermal_label'),
            ('gear', 'summary.control_state', 'summary_control_label'),
            ('jaw', 'window.title', 'summary_window_label'),
            ('chart', 'summary.samples', 'summary_samples_label'),
        ], min_column_width=280))
        layout.addWidget(summary_plate)

        layout.addStretch(1)
        return _scroll(page)


# ═══════════════════════════════════════════════════════════
# مجال التحكم: القدرات، الفكّ، التحقق، المعالجة، المحسّن
# ═══════════════════════════════════════════════════════════

class ControlTab:
    """ما يدعمه العتاد، ونافذة الشحن، وخطوات المعالجة عند غياب المسار"""

    @staticmethod
    def create(parent) -> QScrollArea:
        page, layout = _page()

        # ── الأرض الثابتة: قدرات هذا الجهاز ──
        parent.capability_strip = CapabilityStrip()
        parent.capability_strip.remediationRequested.connect(parent.show_remediation)
        layout.addWidget(parent.capability_strip)

        # ── نافذة الشحن ──
        window_plate, window_layout = _plate('window.title')

        parent.charge_window_jaw = ChargeWindowJaw()
        parent.charge_window_jaw.set_supported(parent.monitor.capability.can_control)
        window_layout.addWidget(parent.charge_window_jaw)

        controls = QHBoxLayout()
        controls.setSpacing(theme.SPACE_3)

        controls.addWidget(_legend(t('window.floor')))
        parent.min_charge_slider = _spin(20, 90, 40)
        controls.addWidget(parent.min_charge_slider)
        parent.min_charge_value_label = create_styled_label('40 %', theme.SIZE_LABEL,
                                                           theme.INK_DIM, mono=True)
        controls.addWidget(parent.min_charge_value_label)

        controls.addSpacing(theme.SPACE_4)

        controls.addWidget(_legend(t('window.ceiling')))
        parent.max_charge_slider = _spin(30, 100, 80)
        controls.addWidget(parent.max_charge_slider)
        parent.max_charge_value_label = create_styled_label('80 %', theme.SIZE_LABEL,
                                                           theme.INK_DIM, mono=True)
        controls.addWidget(parent.max_charge_value_label)

        controls.addStretch(1)

        parent.auto_charge_control = _check(t('control.enable'),
                                           t('control.verify_note'))
        controls.addWidget(parent.auto_charge_control)

        parent.apply_window_button = QPushButton(t('window.apply'))
        parent.apply_window_button.setProperty('role', 'live')
        parent.apply_window_button.setIcon(icons.icon('jaw', 15, theme.INK_ON_FIELD))
        controls.addWidget(parent.apply_window_button)
        window_layout.addLayout(controls)

        parent.control_status_label = create_styled_label(t('control.inactive'),
                                                         theme.SIZE_LABEL, theme.INK_DIM)
        parent.control_status_label.setWordWrap(True)
        window_layout.addWidget(parent.control_status_label)

        parent.window_projection_label = create_styled_label('', theme.SIZE_LABEL,
                                                            theme.PHOSPHOR)
        parent.window_projection_label.setWordWrap(True)
        window_layout.addWidget(parent.window_projection_label)
        layout.addWidget(window_plate)

        # ── خطوات المعالجة (تظهر فقط عند وجودها) ──
        parent.remediation_plate, remediation_layout = _plate('remedy.title')
        parent.remediation_body = QVBoxLayout()
        parent.remediation_body.setSpacing(theme.SPACE_2)
        remediation_layout.addLayout(parent.remediation_body)
        layout.addWidget(parent.remediation_plate)

        # ── القياسات الحالية ──
        measures_plate, measures_layout = _plate('capability.measurable')
        measures_layout.addWidget(_measure_block(parent, [
            ('clock', 'status.time_to_empty', 'time_remaining_label'),
            ('bolt', 'status.draw', 'power_draw_label'),
            ('pulse', 'health.soh', 'health_label'),
            ('cycle', 'health.cycles', 'cycle_count_label'),
            ('thermometer', 'status.temperature', 'temperature_label'),
            ('plug', 'field.status', 'charging_status'),
        ]))
        layout.addWidget(measures_plate)

        # ── المحسّن ──
        optimizer_plate, optimizer_layout = _plate('action.optimize')
        parent.optimize_button = QPushButton(t('action.optimize'))
        parent.optimize_button.setIcon(icons.icon('gauge', 15, theme.INK))
        parent.optimize_button.clicked.connect(parent.run_optimization)
        optimizer_layout.addWidget(parent.optimize_button)

        parent.optimize_status = create_styled_label('', theme.SIZE_LABEL, theme.INK_FAINT)
        parent.optimize_status.setWordWrap(True)
        optimizer_layout.addWidget(parent.optimize_status)
        layout.addWidget(optimizer_plate)

        layout.addStretch(1)
        return _scroll(page)


# ═══════════════════════════════════════════════════════════
# مجال التحليل
# ═══════════════════════════════════════════════════════════

class AnalysisTab:
    """ما تعلّمه التطبيق من هذا الجهاز، وما يتوقّعه، وبأي ثقة"""

    @staticmethod
    def create(parent) -> QScrollArea:
        page, layout = _page()

        advice_plate, advice_layout = _plate('advice.title')
        parent.advice_layer_full = AdviceLayer()
        parent.advice_layer_full.actionTriggered.connect(parent.handle_advice_action)
        advice_layout.addWidget(parent.advice_layer_full)
        layout.addWidget(advice_plate)

        wear_plate, wear_layout = _plate('health.annual_loss')
        wear_layout.addWidget(_measure_block(parent, [
            ('chart', 'record.calendar_loss', 'calendar_loss_label'),
            ('cycle', 'record.cyclic_loss', 'cyclic_loss_label'),
            ('gauge', 'status.stress', 'stress_label'),
            ('clock', 'health.eol_row', 'eol_label'),
            ('cycle', 'record.equivalent_cycles', 'equivalent_cycles_label'),
            ('battery', 'record.high_soc_hours', 'high_soc_hours_label'),
        ]))
        layout.addWidget(wear_plate)

        prediction_plate, prediction_layout = _plate('record.confidence')
        parent.prediction_text = create_styled_label(t('record.learning'),
                                                     theme.SIZE_BODY, theme.INK_DIM)
        parent.prediction_text.setWordWrap(True)
        prediction_layout.addWidget(parent.prediction_text)

        prediction_layout.addWidget(_measure_block(parent, [
            ('chart', 'record.samples', 'data_points_label'),
            ('crosshair', 'record.observed_days', 'patterns_found_label'),
            ('arrow_down', 'record.avg_drain', 'drain_rate_label'),
            ('arrow_up', 'record.avg_charge', 'charge_rate_label'),
            ('gauge', 'record.confidence', 'confidence_label'),
            ('pulse', 'health.soh', 'health_score_label'),
        ]))

        # حقول يقرؤها التحديث القديم؛ تبقى مخفية بلا تكرار بصري
        for attr, text in (('efficiency_score_label', '—'),
                           ('learning_iterations_label', '—'),
                           ('prediction_accuracy_label', '—'),
                           ('learning_progress_label', '—'),
                           ('ai_maturity_label', '—'),
                           ('personalization_label', '—')):
            hidden = create_styled_label(text, theme.SIZE_LABEL, theme.INK_FAINT, mono=True)
            hidden.setVisible(False)
            prediction_layout.addWidget(hidden)
            setattr(parent, attr, hidden)

        actions = QHBoxLayout()
        actions.setSpacing(theme.SPACE_3)
        refresh_button = QPushButton(t('action.refresh_analysis'))
        refresh_button.setIcon(icons.icon('refresh', 15, theme.INK))
        refresh_button.clicked.connect(parent.refresh_ai_analysis)
        actions.addWidget(refresh_button)

        diagnostics_button = QPushButton(t('diag.title'))
        diagnostics_button.setProperty('role', 'quiet')
        diagnostics_button.setIcon(icons.icon('crosshair', 15, theme.INK_DIM))
        diagnostics_button.clicked.connect(parent.show_diagnostics)
        actions.addWidget(diagnostics_button)
        actions.addStretch(1)
        prediction_layout.addLayout(actions)
        layout.addWidget(prediction_plate)

        layout.addStretch(1)
        return _scroll(page)


# ═══════════════════════════════════════════════════════════
# مجال التشخيص
# ═══════════════════════════════════════════════════════════

class DiagnosticsTab:
    """فحص عميق لمنظومة الطاقة، يعمل ببطارية أو بلا بطارية"""

    @staticmethod
    def create(parent) -> QScrollArea:
        page, layout = _page()

        parent.diagnostics_panel = DiagnosticsPanel()
        parent.diagnostics_panel.scanRequested.connect(parent.run_diagnostics)
        parent.diagnostics_panel.exportRequested.connect(parent.export_diagnostics)
        layout.addWidget(parent.diagnostics_panel)

        layout.addStretch(1)
        return _scroll(page)


# ═══════════════════════════════════════════════════════════
# مجال السجل
# ═══════════════════════════════════════════════════════════

class RecordTab:
    """الصحة المقروءة من العتاد، الأزمنة التراكمية، وسجل الأحداث"""

    @staticmethod
    def create(parent) -> QScrollArea:
        page, layout = _page()

        health_plate, health_layout = _plate('health.title')
        parent.health_progress = _progress_bar()
        health_layout.addWidget(parent.health_progress)

        parent.health_status_label = create_styled_label(t('health.unknown'),
                                                         theme.SIZE_BODY, theme.INK_DIM)
        health_layout.addWidget(parent.health_status_label)

        health_layout.addWidget(_measure_block(parent, [
            ('battery', 'health.design_capacity', 'design_capacity_label'),
            ('battery', 'health.full_capacity', 'current_capacity_label'),
            ('alert', 'record.cyclic_loss', 'wear_level_label'),
            ('cycle', 'health.cycles', 'cycle_count_stats_label'),
        ]))
        layout.addWidget(health_plate)

        totals_plate, totals_layout = _plate('record.totals')
        totals_rows = [
            ('bolt', 'record.total_charge_time', 'total_charge_time_label'),
            ('arrow_down', 'record.total_discharge_time', 'total_discharge_time_label'),
            ('bolt', 'record.avg_power', 'avg_power_draw_label'),
            ('alert', 'record.peak_power', 'peak_power_draw_label'),
            ('battery', 'record.avg_level', 'avg_battery_level_label'),
            ('cycle', 'record.cycles_today', 'charge_cycles_today_label'),
            ('gauge', 'record.system_health', 'system_health_label'),
            ('gear', 'record.auto_opt_runs', 'auto_opt_count_label'),
            ('bolt', 'record.auto_opt_saved', 'auto_opt_power_saved_label'),
        ]
        totals_layout.addWidget(_measure_block(parent, totals_rows))
        layout.addWidget(totals_plate)

        log_plate, log_layout = _plate('record.events')
        parent.events_log = QTextEdit()
        parent.events_log.setReadOnly(True)
        parent.events_log.setMinimumHeight(180)
        parent.events_log.setFont(theme.font(theme.SIZE_LABEL, 500, mono=True))
        log_layout.addWidget(parent.events_log)

        log_actions = QHBoxLayout()
        log_actions.setSpacing(theme.SPACE_3)
        clear_button = QPushButton(t('record.clear'))
        clear_button.setProperty('role', 'quiet')
        clear_button.setIcon(icons.icon('close', 14, theme.INK_DIM))
        clear_button.clicked.connect(parent.clear_log)
        log_actions.addWidget(clear_button)

        export_button = QPushButton(t('diag.export'))
        export_button.setProperty('role', 'quiet')
        export_button.setIcon(icons.icon('copy', 14, theme.INK_DIM))
        export_button.clicked.connect(parent.export_log)
        log_actions.addWidget(export_button)
        log_actions.addStretch(1)
        log_layout.addLayout(log_actions)
        layout.addWidget(log_plate)

        layout.addStretch(1)
        return _scroll(page)


def _progress_bar():
    from PyQt6.QtWidgets import QProgressBar
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setTextVisible(True)
    bar.setFormat('%p ' + t('unit.percent'))
    return bar


# ═══════════════════════════════════════════════════════════
# مجال الإعدادات
# ═══════════════════════════════════════════════════════════

class SettingsTab:
    """الإشعارات، العتبات، التشغيل، والتحسين التلقائي"""

    #: عتبات التنبيه: (مفتاح الوصف، اسم الحقل، الأدنى، الأقصى، الافتراضي)
    ALERT_THRESHOLDS = (
        ('threshold.critical', 'critical_battery_spin', 5, 15, 10),
        ('threshold.low', 'low_battery_spin', 15, 30, 20),
        ('threshold.optimal_min', 'optimal_min_spin', 30, 50, 40),
        ('threshold.optimal_max', 'optimal_max_spin', 70, 90, 80),
        ('threshold.high', 'high_battery_spin', 85, 95, 90),
        ('threshold.full', 'full_battery_spin', 90, 100, 95),
    )

    #: عتبات التحسين التلقائي: (تسمية، اسم الحقل، افتراضي، لاحقة، الأقصى)
    OPTIMIZER_THRESHOLDS = (
        ('CPU', 'opt_cpu_threshold', 70, '%', 100),
        ('RAM', 'opt_memory_threshold', 75, '%', 100),
        ('DISK', 'opt_disk_threshold', 85, '%', 100),
        ('W', 'opt_power_threshold', 15, 'W', 50),
    )

    @staticmethod
    def create(parent) -> QScrollArea:
        page, layout = _page()

        # ── الإشعارات ──
        notif_plate, notif_layout = _plate('startup.notifications')
        parent.enable_notifications = _check(t('startup.notifications'))
        parent.enable_notifications.setChecked(True)
        parent.enable_sounds = _check(t('startup.sounds'))
        parent.enable_sounds.setChecked(True)
        parent.enable_reminders = _check(t('startup.reminders'))
        parent.enable_reminders.setChecked(True)

        toggles = QHBoxLayout()
        toggles.setSpacing(theme.SPACE_5)
        for box in (parent.enable_notifications, parent.enable_sounds,
                    parent.enable_reminders):
            toggles.addWidget(box)
        toggles.addStretch(1)
        notif_layout.addLayout(toggles)

        thresholds_grid = QGridLayout()
        thresholds_grid.setHorizontalSpacing(theme.SPACE_4)
        thresholds_grid.setVerticalSpacing(theme.SPACE_2)
        for index, (key, attr, low, high, default) in enumerate(SettingsTab.ALERT_THRESHOLDS):
            label = QLabel(t(key))
            label.setFont(theme.font(theme.SIZE_LABEL, 500))
            label.setStyleSheet(f"color: {theme.INK_DIM};")
            spin = _spin(low, high, default)
            setattr(parent, attr, spin)
            row, col = index // 2, (index % 2) * 2
            thresholds_grid.addWidget(label, row, col)
            thresholds_grid.addWidget(spin, row, col + 1)
        notif_layout.addLayout(thresholds_grid)
        layout.addWidget(notif_plate)

        # ── التشغيل ──
        startup_plate, startup_layout = _plate('startup.on_boot')
        parent.start_on_boot = _check(t('startup.on_boot'))
        parent.start_on_boot.stateChanged.connect(parent.on_autostart_changed)
        parent.minimize_to_tray = _check(t('startup.minimize_to_tray'))
        parent.show_battery_in_tray = _check(t('startup.show_in_tray'))
        parent.show_battery_in_tray.setChecked(True)
        for box in (parent.start_on_boot, parent.minimize_to_tray,
                    parent.show_battery_in_tray):
            startup_layout.addWidget(box)
        layout.addWidget(startup_plate)

        # ── التحسين التلقائي ──
        auto_plate, auto_layout = _plate('action.optimize')
        parent.enable_auto_optimization = _check(t('startup.auto_optimize'))
        parent.enable_auto_optimization.stateChanged.connect(parent.on_auto_optimization_changed)
        auto_layout.addWidget(parent.enable_auto_optimization)

        modes = QHBoxLayout()
        modes.setSpacing(theme.SPACE_4)
        parent.opt_mode_continuous = _check(t('startup.mode_continuous'))
        parent.opt_mode_on_demand = _check(t('startup.mode_on_demand'))
        parent.opt_mode_on_demand.setChecked(True)
        parent.opt_mode_scheduled = _check(t('startup.mode_scheduled'))
        for box in (parent.opt_mode_continuous, parent.opt_mode_on_demand,
                    parent.opt_mode_scheduled):
            modes.addWidget(box)
        modes.addStretch(1)
        auto_layout.addLayout(modes)

        interval_row = QHBoxLayout()
        interval_row.setSpacing(theme.SPACE_3)
        interval_row.addWidget(_legend(t('startup.interval')))
        parent.opt_interval_slider = _spin(1, 60, 5, t('unit.minute_short'))
        interval_row.addWidget(parent.opt_interval_slider)
        parent.opt_interval_value_label = create_styled_label(
            f"5 {t('unit.minute_short')}", theme.SIZE_LABEL, theme.INK_DIM, mono=True)
        interval_row.addWidget(parent.opt_interval_value_label)
        interval_row.addStretch(1)
        auto_layout.addLayout(interval_row)

        optimizer_grid = QGridLayout()
        optimizer_grid.setHorizontalSpacing(theme.SPACE_4)
        optimizer_grid.setVerticalSpacing(theme.SPACE_2)
        for index, (name, attr, default, suffix, maximum) in enumerate(SettingsTab.OPTIMIZER_THRESHOLDS):
            label = QLabel(name)
            label.setFont(theme.font(theme.SIZE_LABEL, 600, mono=True))
            label.setStyleSheet(f"color: {theme.INK_DIM};")
            spin = _spin(10, maximum, default, suffix)
            setattr(parent, attr, spin)
            row, col = index // 2, (index % 2) * 2
            optimizer_grid.addWidget(label, row, col)
            optimizer_grid.addWidget(spin, row, col + 1)
        auto_layout.addLayout(optimizer_grid)
        layout.addWidget(auto_plate)

        save_button = QPushButton(t('startup.save'))
        save_button.setProperty('role', 'live')
        save_button.setIcon(icons.icon('check', 15, theme.INK_ON_FIELD))
        save_button.clicked.connect(parent.save_all_settings)
        layout.addWidget(save_button)

        layout.addStretch(1)
        return _scroll(page)


#: أسماء متوافقة مع الاستدعاءات السابقة
AITab = AnalysisTab
StatsTab = RecordTab
