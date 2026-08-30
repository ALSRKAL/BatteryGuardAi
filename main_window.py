#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""النافذة الرئيسية - لوحة قياس البطارية"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QMainWindow, QMessageBox, QPushButton, QTabWidget,
                             QTextEdit, QVBoxLayout, QWidget)

import diagnostics
import icons
import theme
from auto_optimizer import AutoOptimizer
from autostart_manager import autostart_manager
from battery_ai import BatteryAI
from battery_monitor import BatteryMonitor
from battery_science import (END_OF_LIFE_SOH, OPTIMAL_WINDOW, SOURCES,
                             ceiling_saving_percent_per_year, stress_index)
from battery_optimizer import BatteryOptimizer
from default_settings import (APP_NAME, APP_ORG, APP_VERSION,
                              get_default_settings, guard_settings_from)
from guard_service import GuardService
from settings_bridge import qsettings_reader
from i18n import is_rtl, t
from monitor_thread import MonitorThread
from notification_manager import SmartNotificationManager
from panel_widgets import ChargeWindowJaw, EngravedRail
from permission_manager import PermissionManager
from resource_path import get_data_path, get_resource_path
from tray_icon import BatteryTrayIcon
from ui_components import (AnalysisTab, ControlTab, DiagnosticsTab, RecordTab,
                           SettingsTab, StatusTab)

logger = logging.getLogger('BatteryGuard')


class _DiagnosticsWorker(QThread):
    """
    يشغّل الفحص العميق بعيداً عن خيط الواجهة: الفحص يقرأ عشرات المسارات
    ويستدعي أدوات خارجية، وتجميد الواجهة ثانيتين عيب لا عذر له.
    """

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.finished.emit(diagnostics.run(deep=True))
        except Exception as e:  # الفحص لا يجوز أن يُسقط التطبيق
            logger.error(f"خطأ في خيط التشخيص: {e}", exc_info=True)
            self.failed.emit(str(e))


class ModernUI(QMainWindow):
    """لوحة القياس: نافذة واحدة تحمل الحكم والقراءة والقدرات والتحكم"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_ORG, APP_NAME)
        self.permission_manager = PermissionManager()

        # سياق مشترك من متحكّم الخلفية: النافذة تُبنى بعد أن يكون التطبيق
        # يعمل ويتعلّم منذ مدة، فتتبنّى كائناته بدل إنشاء نسخ ثانية تقرأ نفس
        # العتاد وتكتب نفس ملفات التعلّم.
        shared = getattr(self, '_shared_context', None) or {}
        self._adopted_thread = 'monitor_thread' in shared

        self.monitor = shared.get('monitor') or BatteryMonitor()
        self.ai = shared.get('ai') or BatteryAI()
        self.notification_manager = (shared.get('notification_manager')
                                     or SmartNotificationManager())
        self.optimizer = BatteryOptimizer(ai_engine=self.ai)
        self.auto_optimizer = AutoOptimizer(self.optimizer, self.ai)

        # خطّ الحارس: نسب الطاقة للعمليات، الاستدلال، والإجراءات الفعلية.
        # يُبنى قبل الواجهة لأن لوحة التحليل تقرأ حالته عند التهيئة.
        self.guard_service = shared.get('guard_service') or GuardService(
            self.monitor, self.ai, self._settings_snapshot(),
            on_action=self._on_guard_action)
        self._shared_tray = shared.get('tray')
        self._last_intelligence = None

        # حالة التشخيص العميق
        self._diagnostics_report = None
        self._diagnostics_worker = None
        self._diagnostics_running = False
        self._last_diagnostics_finding = None
        self._last_notified_advice = None
        self._trace_started = None

        # تمرير كلمة مرور sudo إذا كانت متوفرة من البداية
        self._sync_permissions()
        
        # مؤقت الحفظ التلقائي
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self._auto_save_data)
        self.auto_save_timer.start(300000)  # حفظ كل 5 دقائق
        
        self.init_ui()
        self.load_settings()
        self._load_log_from_file()
        self.start_monitoring()

        # فحص أول بعد استقرار الواجهة: يحدّد نمط الجهاز وقدراته الحقيقية
        QTimer.singleShot(1500, self.run_diagnostics)
        
    def init_ui(self):
        """
        تهيئة لوحة القياس.

        عقد الاتجاه (عالم «لوحة القياس»، مفتاح الرمية beac5dd9):
        THESIS: التطبيق جهاز قياس يقول الحقيقة عن هذه البطارية بالذات ويعترف
          بما لا يستطيع فعله؛ يرفض حلقة النسبة والبطاقات الزجاجية التي تشحنها
          كل تطبيقات البطارية.
        OWN-WORLD: لوحة ألمنيوم مؤكسد مطفأة، حروف سلك-سكرين، حواف محفورة
          بحدّين، حبر فوسفوري واحد لرسوم القياس، واللون محفوظ لحقل الحالة.
        STORY: يرى المستخدم حكماً واحداً بلغة بسيطة، ثم الرقم والأثر، ثم ما
          يدعمه عتاده فعلاً، ثم خطوة واحدة قابلة للتنفيذ.
        FIRST VIEWPORT: شريط رأس محفور (هوية، حكم، طبقة القدرة)، تحته حقل
          الحالة المشبع بالقراءة الأساسية وأثر الاستهلاك، ثم طبقة التوصيات
          المعلَّمة، ثم شريط القدرات المعنون. الإجراء الأساسي في الطبقة نفسها.
        FORM: لوحة أجهزة القياس المخبرية، المرتبة الرابعة في قائمة العوالم
          المشتقّة، أسندتها الرمية بمفتاح beac5dd9.
        FINISH: unreviewed and undocumented is unfinished; this build ends with
          the finish review, the verdict, DESIGN.md, and every shipping raster
          carrying its provenance.
        """
        self.setWindowTitle(t('app.name'))
        self.setMinimumSize(960, 700)
        self.resize(1180, 860)

        if is_rtl():
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        icon_path = Path(get_resource_path('assets/logo.png'))
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setStyleSheet(theme.stylesheet())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── شريط الرأس المحفور ──
        self.rail = EngravedRail()
        self.rail.set_device(self.monitor.capability.vendor, self.monitor.capability.product)
        self.rail.set_tier(self.monitor.capability.tier)
        root.addWidget(self.rail)

        # ── الجسم: عمود واحد محدود العرض حتى لا تتمدد اللوحة بلا نظام ──
        body_host = QWidget()
        host_layout = QHBoxLayout(body_host)
        host_layout.setContentsMargins(theme.SPACE_4, theme.SPACE_3,
                                       theme.SPACE_4, theme.SPACE_3)
        host_layout.setSpacing(0)

        # المحتوى يملأ العرض المتاح؛ الكثافة تُدار داخل كل مجال بشبكة متكيّفة
        body = QWidget()
        host_layout.addWidget(body, 1)

        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(theme.SPACE_4)

        # ── مُحدِّد المجال: كل شيء داخل مجاله، ولا تكديس فوق التابات ──
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.state_tab = StatusTab.create(self)
        self.tabs.addTab(self.state_tab, t('tab.status'))

        self.status_tab = ControlTab.create(self)
        self.tabs.addTab(self.status_tab, t('tab.control'))

        self.ai_tab = AnalysisTab.create(self)
        self.tabs.addTab(self.ai_tab, t('tab.intelligence'))

        self.diagnostics_tab = DiagnosticsTab.create(self)
        self.tabs.addTab(self.diagnostics_tab, t('diag.title'))

        self.stats_tab = RecordTab.create(self)
        self.tabs.addTab(self.stats_tab, t('tab.record'))

        self.settings_tab = SettingsTab.create(self)
        self.tabs.addTab(self.settings_tab, t('tab.settings'))

        body_layout.addWidget(self.tabs, 1)
        root.addWidget(body_host, 1)

        # ── شريط سفلي: حالة التشغيل ──
        footer = QFrame()
        footer.setProperty('role', 'rail')
        footer.setFixedHeight(34)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(theme.SPACE_5, 0, theme.SPACE_5, 0)
        footer_layout.setSpacing(theme.SPACE_3)

        self.status_label = QLabel(t('status.reading'))
        self.status_label.setFont(theme.legend_font())
        self.status_label.setStyleSheet(f"color: {theme.INK_DIM};")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch(1)

        self.uptime_label = QLabel('')
        self.uptime_label.setFont(theme.font(theme.SIZE_LEGEND, 500, mono=True))
        self.uptime_label.setStyleSheet(f"color: {theme.INK_FAINT};")
        footer_layout.addWidget(self.uptime_label)

        version_label = QLabel(APP_VERSION)
        version_label.setFont(theme.font(theme.SIZE_LEGEND, 500, mono=True))
        version_label.setStyleSheet(f"color: {theme.INK_FAINT};")
        footer_layout.addWidget(version_label)
        root.addWidget(footer)

        # ── الربط النهائي ──
        self.charge_window_jaw.windowChanged.connect(self._on_jaw_changed)
        self.apply_window_button.clicked.connect(self.apply_charge_window)
        self.min_charge_slider.valueChanged.connect(self._on_spin_changed)
        self.max_charge_slider.valueChanged.connect(self._on_spin_changed)

        self._refresh_capability_ui()

        self.start_time = datetime.now()
        self.uptime_timer = QTimer()
        self.uptime_timer.timeout.connect(self._update_uptime)
        self.uptime_timer.start(60000)

        # أيقونة واحدة فقط: عند الفتح من وضع الخلفية تكون الأيقونة موجودة
        # منذ بدء الجلسة، وإنشاء ثانية يعني أيقونتين متطابقتين في الشريط.
        if self._shared_tray is not None:
            self.tray = self._shared_tray
            self.tray.parent = self
        else:
            self.tray = BatteryTrayIcon(self)

    # ══════════════════════════════════════════════════════
    # نافذة الشحن: مصدر واحد للقيمة، وتحقّق صريح بعد التطبيق
    # ══════════════════════════════════════════════════════

    def current_window(self) -> Tuple[int, int]:
        """النافذة المعروضة الآن (الأدنى، الأقصى)"""
        if hasattr(self, 'charge_window_jaw'):
            return self.charge_window_jaw.window()
        return (self.settings.value('min_charge_limit', 40, type=int),
                self.settings.value('max_charge_limit', 80, type=int))

    def _on_jaw_changed(self, floor: int, ceiling: int) -> None:
        """تحريك الفكّ يحدّث الحقول الرقمية والتوقّع بلا حلقة إشارات"""
        for widget, value in ((self.min_charge_slider, floor),
                              (self.max_charge_slider, ceiling)):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self._update_window_labels(floor, ceiling)

    def _on_spin_changed(self, _value: int) -> None:
        """الحقول الرقمية هي التوأم المتاح للفكّ نفسه"""
        floor = self.min_charge_slider.value()
        ceiling = self.max_charge_slider.value()
        if ceiling - floor < ChargeWindowJaw.MIN_GAP:
            ceiling = floor + ChargeWindowJaw.MIN_GAP
            self.max_charge_slider.blockSignals(True)
            self.max_charge_slider.setValue(ceiling)
            self.max_charge_slider.blockSignals(False)
        self.charge_window_jaw.set_window(floor, ceiling)
        self._update_window_labels(floor, ceiling)

    def _update_window_labels(self, floor: int, ceiling: int) -> None:
        """التوفير المتوقّع يُحسب لحظياً من نفس المحرك المرجعي"""
        percent = t('unit.percent')
        self.min_charge_value_label.setText(f"{floor} {percent}")
        self.max_charge_value_label.setText(f"{ceiling} {percent}")

        projection = self.ai.wear_projection(ceiling)
        saving = ceiling_saving_percent_per_year(
            100, ceiling, projection['hours_plugged_per_day'] or 12.0)
        self.window_projection_label.setText(t('window.projected_saving', saving=saving))

    def apply_charge_window(self) -> None:
        """تطبيق النافذة على العتاد، ثم قول الحقيقة عن النتيجة"""
        floor, ceiling = self.current_window()

        if not self.monitor.capability.can_control:
            self._set_control_status(t('control.fail_reason.no_path'), theme.STATE_DEAD)
            self.show_remediation()
            return

        try:
            if not self.auto_charge_control.isChecked():
                self.monitor.disable_charge_control()
                self._set_control_status(t('control.inactive'), theme.INK_DIM)
                return

            verified = self.monitor.enable_charge_control(floor, ceiling)
        except Exception as e:  # عتاد أو صلاحيات: لا يجوز أن ينهار التطبيق
            logger.error(f"فشل تطبيق حدود الشحن: {e}")
            self._set_control_status(t('control.failed'), theme.STATE_CRITICAL)
            return

        if verified:
            self._set_control_status(
                f"{t('window.applied', floor=floor, ceiling=ceiling)} · {t('window.verified')}",
                theme.STATE_OK)
            self.log_event(t('notify.control_applied'))
        else:
            error = self.monitor.last_control_error or {'reason': 'unreadable'}
            reason = error.get('reason', 'unreadable')
            self._set_control_status(
                t(f'control.fail_reason.{reason}', **{k: v for k, v in error.items()
                                                      if k != 'reason'}),
                theme.STATE_CRITICAL)
            self.log_event(t('notify.control_failed'))
            self.show_remediation()

        self.settings.setValue('min_charge_limit', floor)
        self.settings.setValue('max_charge_limit', ceiling)

    def _set_control_status(self, text: str, color: str) -> None:
        if hasattr(self, 'control_status_label'):
            self.control_status_label.setText(text)
            self.control_status_label.setStyleSheet(f"color: {color};")

    # ══════════════════════════════════════════════════════
    # القدرات والمعالجة
    # ══════════════════════════════════════════════════════

    def _refresh_capability_ui(self) -> None:
        """مزامنة كل ما يعتمد على قدرات العتاد بعد أي فحص"""
        report = self.monitor.capability.as_dict()
        self.capability_strip.set_report(report)
        self.charge_window_jaw.set_supported(bool(report.get('can_control')))
        self.rail.set_tier(str(report.get('tier', 'notify_only')))
        self._render_remediation(self.monitor.capability.remediation)

        # وصف الطبقة يظهر في شريط القدرات؛ سطر التحكم يقول النتيجة فقط
        if not report.get('can_control'):
            self._set_control_status(t('window.unsupported'), theme.STATE_DEAD)

    def _render_remediation(self, steps: List) -> None:
        """خطوات المعالجة: نص، وأمر قابل للنسخ، ومصدر"""
        if not hasattr(self, 'remediation_body'):
            return

        while self.remediation_body.count():
            item = self.remediation_body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.remediation_plate.setVisible(bool(steps))
        for index, step in enumerate(steps, 1):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(theme.SPACE_2)

            mark = QLabel()
            mark.setPixmap(icons.pixmap('chevron', 14, theme.PHOSPHOR))
            mark.setFixedWidth(16)
            mark.setAlignment(Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(mark)

            text = QLabel(t(step.key, **step.params))
            text.setWordWrap(True)
            text.setFont(theme.font(theme.SIZE_BODY, 500))
            text.setMaximumWidth(theme.MAX_TEXT_WIDTH)
            row_layout.addWidget(text, 1)

            if step.command:
                copy_button = QPushButton(t('action.copy'))
                copy_button.setProperty('role', 'quiet')
                copy_button.setIcon(icons.icon('copy', 14, theme.INK_DIM))
                command = step.command
                copy_button.clicked.connect(
                    lambda _checked=False, cmd=command, btn=copy_button:
                    self._copy_command(cmd, btn))
                row_layout.addWidget(copy_button, 0, Qt.AlignmentFlag.AlignTop)

            self.remediation_body.addWidget(row)

    def _copy_command(self, command: str, button) -> None:
        """نسخ أمر المعالجة إلى الحافظة بلا تنفيذ تلقائي"""
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(command)
        button.setText(t('action.copied'))
        QTimer.singleShot(2000, lambda: button.setText(t('action.copy')))

    def show_remediation(self) -> None:
        """إظهار مجال التحكم عند خطوات المعالجة"""
        self.tabs.setCurrentWidget(self.status_tab)
        if hasattr(self, 'remediation_plate'):
            self.remediation_plate.setVisible(bool(self.monitor.capability.remediation))

    def show_diagnostics(self) -> None:
        """الانتقال إلى مجال التشخيص، وتشغيل فحص إن لم يوجد تقرير بعد"""
        self.tabs.setCurrentWidget(self.diagnostics_tab)
        if self._diagnostics_report is None:
            self.run_diagnostics()

    def run_diagnostics(self) -> None:
        """
        فحص عميق في خيط منفصل: يقرأ العتاد ويشغّل أدوات خارجية، ولا يجوز
        أن يجمّد الواجهة أثناء ذلك.
        """
        if self._diagnostics_running:
            return
        self._diagnostics_running = True
        self.diagnostics_panel.set_busy(True)
        self.status_label.setText(t('diag.running'))

        worker = _DiagnosticsWorker(self)
        worker.finished.connect(self._on_diagnostics_ready)
        worker.failed.connect(self._on_diagnostics_failed)
        self._diagnostics_worker = worker
        worker.start()

    def _on_diagnostics_ready(self, report) -> None:
        """عرض التقرير: حكم عام، نتائج بأدلتها، وجدول خام"""
        self._diagnostics_report = report
        self._diagnostics_running = False
        self.diagnostics_panel.set_busy(False)

        grade_colors = {
            'ok': theme.STATE_OK,
            'degraded': theme.STATE_WARN,
            'impaired': theme.STATE_WARN,
            'unmeasurable': theme.STATE_CRITICAL,
            'unknown': theme.STATE_DEAD,
        }
        environment = report.environment
        device = ' '.join(part for part in (environment.get('vendor'),
                                            environment.get('product')) if part)
        bios = f"BIOS {environment.get('bios_version', '')} " \
               f"{environment.get('bios_date', '')}".strip()
        meta = ' · '.join(part for part in (
            f"{t('diag.device_mode')}: {t('diag.mode.' + report.device_mode)}",
            device, bios, f"{t('diag.generated')}: {report.generated_at}") if part)

        findings = [{
            'severity': finding.severity,
            'title': t(finding.key, **finding.params),
            'evidence': finding.evidence,
            'remediation': [t(key) for key in finding.remediation],
            'confidence': finding.confidence,
        } for finding in report.findings]

        self.diagnostics_panel.set_report(
            t('diag.grade.' + report.grade),
            grade_colors.get(report.grade, theme.STATE_DEAD),
            meta, findings, diagnostics.readable_table(report))

        top = report.top_finding
        if top is not None:
            self.log_event(f"{t('diag.title')}: {t(top.key, **top.params)}")
            if top.severity in ('critical', 'warning') and \
                    self._last_diagnostics_finding != top.id:
                self._last_diagnostics_finding = top.id
                self.notification_manager.send_notification(
                    title=t('diag.title'),
                    message=t(top.key, **top.params),
                    urgency='critical' if top.severity == 'critical' else 'high',
                    notification_type='health_warning', play_sound=True)
        self.status_label.setText(t('diag.grade.' + report.grade))

    def _on_diagnostics_failed(self, message: str) -> None:
        """فشل الفحص لا يُسكت: يُسجَّل ويُعلن في شريط الحالة"""
        self._diagnostics_running = False
        self.diagnostics_panel.set_busy(False)
        logger.error(f"فشل التشخيص: {message}")
        self.status_label.setText(t('diag.unreadable'))

    def export_diagnostics(self) -> None:
        """حفظ التقرير الكامل: التصنيف والأدلة الخام معاً"""
        if self._diagnostics_report is None:
            self.run_diagnostics()
            return
        try:
            path = Path(get_data_path('diagnostics_report.json'))
            payload = {
                'report': self._diagnostics_report.as_dict(),
                'monitor': self.monitor.diagnostics(),
                'raw_table': self.diagnostics_panel.raw_text().splitlines(),
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding='utf-8')
            self.status_label.setText(t('diag.exported', path=str(path)))
            self.log_event(t('diag.exported', path=str(path)))
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"تعذّر تصدير التشخيص: {e}")
            self.status_label.setText(t('diag.unreadable'))

    def handle_advice_action(self, action: str) -> None:
        """تنفيذ الإجراء المرافق للتوصية، أو إظهار المكان الذي يُنفّذ فيه"""
        if action == 'enable_control':
            self.auto_charge_control.setChecked(True)
            self.tabs.setCurrentWidget(self.status_tab)
            self.apply_charge_window()
        elif action == 'lower_ceiling':
            floor, _ceiling = self.current_window()
            self.charge_window_jaw.set_window(floor, OPTIMAL_WINDOW[1], emit=True)
            self.tabs.setCurrentWidget(self.status_tab)
        elif action == 'optimize':
            self.run_optimization()
        elif action == 'open_diagnostics':
            self.show_diagnostics()
        elif action == 'open_capability':
            self.show_remediation()
        elif action == 'open_health':
            self.tabs.setCurrentWidget(self.stats_tab)
        else:
            # إجراءات يدوية (وصل/فصل/تبريد): نكتفي بتسجيل النصيحة
            self.status_label.setText(t(f'action.{action}'))
            self.log_event(t(f'action.{action}'))

    def show_window(self):
        """عرض النافذة وتفعيلها"""
        self.show()
        self.activateWindow()
        self.raise_()
    
    def start_monitoring(self):
        """
        بدء المراقبة الخلفية، أو تبنّي خيط يعمل أصلاً.

        عند الفتح من وضع الخلفية يكون الخيط يعمل منذ مدة: تشغيل خيط ثانٍ يعني
        قراءتين للعتاد وكتابتين لملف التعلّم في نفس اللحظة، فنتبنّى القائم
        ونكتفي بوصل إشاراته إلى الواجهة.
        """
        shared = getattr(self, '_shared_context', None) or {}
        adopted = shared.get('monitor_thread')
        if adopted is not None:
            self.monitor_thread = adopted
            self.monitor_thread.update_settings(self.get_current_settings())
            logger.info("تبنّت اللوحة خيط المراقبة العامل في الخلفية")
        else:
            self.monitor_thread = MonitorThread(
                self.monitor,
                self.ai,
                self.get_current_settings(),
                guard_service=self.guard_service
            )
            self.monitor_thread.start()

        self.monitor_thread.battery_updated.connect(self.update_battery_display)
        self.monitor_thread.notification_requested.connect(self.send_notification)
        self.monitor_thread.intelligence_updated.connect(self.on_intelligence_report)
        
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self.refresh_ai_analysis)
        self.ai_timer.start(5000)
        
        # تحديث فوري عند البدء
        QTimer.singleShot(500, self.force_initial_update)
        
        self.log_event("تم بدء المراقبة بنجاح")
    
    def _update_uptime(self):
        """تحديث وقت التشغيل"""
        uptime = datetime.now() - self.start_time
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        
        if hours > 0:
            self.uptime_label.setText(f"وقت التشغيل: {hours}س {minutes}د")
        else:
            self.uptime_label.setText(f"وقت التشغيل: {minutes}د")
    
    def force_initial_update(self):
        """تحديث فوري عند البدء"""
        battery_status = self.monitor.get_battery_status()
        if battery_status['available']:
            self.update_battery_display(battery_status)
    
    def update_battery_display(self, battery_status: Dict):
        """تحديث لوحة القياس من قراءة واحدة للعتاد"""
        percent = battery_status['percent']
        is_charging = battery_status['is_charging']
        reporting = battery_status.get('reporting', True)
        floor, ceiling = self.current_window()

        self.check_battery_alerts(battery_status)

        health = self.monitor.get_battery_health()
        soh = health.get('health_percentage')
        self.tray.update_icon(percent, is_charging,
                              int(soh) if soh is not None else None, reporting)

        # ── حقل الحالة والأثر ──
        if hasattr(self, 'state_plate'):
            self.state_plate.set_reading(
                percent, is_charging, reporting,
                battery_status.get('status_key', 'status.reading'), floor, ceiling)

            # المفاتيح الخام هي معرّفات الخانات، لا النصوص المترجمة
            temp = battery_status.get('temperature')
            draw = battery_status.get('power_draw', 0) or 0
            cycles_value = health.get('cycle_count')
            stress = stress_index(percent, temp, is_charging, percent >= ceiling) \
                if reporting else None
            self.state_plate.set_measures([
                ('bolt', 'status.draw',
                 f"{draw:.1f} {t('unit.watt')}" if draw > 0.1 else '—'),
                ('thermometer', 'status.temperature',
                 f"{temp:.1f} {t('unit.celsius')}" if temp is not None
                 else t('status.assumed_temp', temp=25)),
                ('pulse', 'health.title',
                 f"{soh:.0f} {t('unit.percent')}" if soh is not None else t('health.unknown')),
                ('cycle', 'health.cycles', str(cycles_value) if cycles_value else '—'),
                ('plug', 'field.status', t(battery_status.get('status_key', 'status.reading'))),
                ('gauge', 'status.stress',
                 f"{stress['index']:.0f} · {t('stress.' + stress['band'])}"
                 if stress else '—'),
            ])
            self._trace_sample(percent)

        # ── القياسات في مجال التحكم ──
        time_text = self._format_time_left(battery_status, percent, is_charging)
        self._set_measure('time_remaining_label', time_text)
        self.tray.update_time_remaining(time_text)

        self._set_measure(
            'power_draw_label',
            f"{battery_status.get('power_draw', 0):.1f} {t('unit.watt')}"
            if (battery_status.get('power_draw') or 0) > 0.1 else '—')

        self._set_measure('health_label',
                          f"{soh:.0f} {t('unit.percent')}" if soh is not None
                          else t('health.unknown'))

        cycles = health.get('cycle_count')
        cycles_text = f"{cycles} {t('unit.cycles')}" if cycles else t('health.cycles_unavailable')
        self._set_measure('cycle_count_label', cycles_text)
        self._set_measure('cycle_count_stats_label', str(cycles) if cycles else '—')

        temperature = battery_status.get('temperature')
        self._set_measure('temperature_label',
                          f"{temperature:.1f} {t('unit.celsius')}" if temperature is not None
                          else t('status.temperature_unavailable'))

        self._set_measure('charging_status', t(battery_status.get('status_key', 'status.reading')))

        # ── الصحة في مجال السجل ──
        if hasattr(self, 'health_progress'):
            self.health_progress.setValue(int(soh) if soh is not None else 0)
        if soh is None:
            self._set_measure_text('health_status_label', t('health.unknown'), theme.INK_FAINT)
        elif soh >= 90:
            self._set_measure_text('health_status_label', t('advice.health_strong', soh=soh),
                                   theme.STATE_OK)
        elif soh > END_OF_LIFE_SOH:
            self._set_measure_text('health_status_label',
                                   t('health.soh') + f": {soh:.0f}%", theme.STATE_WARN)
        else:
            self._set_measure_text('health_status_label',
                                   t('health.eol_reached'), theme.STATE_CRITICAL)

        design = health.get('design_capacity') or 0
        full = health.get('full_capacity') or 0
        unit = t('unit.mah') if health.get('capacity_unit') == 'mah' else t('unit.wh')
        divisor = 1.0 if health.get('capacity_unit') == 'mah' else 1000.0
        self._set_measure('design_capacity_label',
                          f"{design / divisor:.1f} {unit}" if design else '—')
        self._set_measure('current_capacity_label',
                          f"{full / divisor:.1f} {unit}" if full else '—')
        self._set_measure('wear_level_label',
                          f"{100 - soh:.1f} {t('unit.percent')}" if soh is not None else '—')

        # شريط الصحة يختفي حين لا تُعرف الصحة: صفر بلا معنى يضلّل
        if hasattr(self, 'health_progress'):
            self.health_progress.setVisible(soh is not None)

        self._update_advanced_stats()

    def _trace_sample(self, percent: float) -> None:
        """تغذية أثر الفوسفور مع مدى زمني حقيقي مقروء من الفواصل"""
        now = datetime.now()
        first = getattr(self, '_trace_started', None) or now
        self._trace_started = first
        span_minutes = (now - first).total_seconds() / 60.0
        self.state_plate.push_sample(percent, span_minutes)

    def _format_time_left(self, battery_status: Dict, percent: int,
                          is_charging: bool) -> str:
        """الزمن المتبقي من العتاد إن أعطاه، وإلا من تنبؤ المحرك، وإلا صراحةً"""
        seconds = battery_status.get('time_left')
        if seconds and seconds > 0:
            hours, minutes = seconds // 3600, (seconds % 3600) // 60
            return f"{hours}{t('unit.hour_short')} {minutes}{t('unit.minute_short')}"
        if not battery_status.get('reporting', True):
            return t('status.not_reporting')
        prediction = self.ai.predict_time_remaining(percent, is_charging)
        return prediction or t('status.time_unknown')

    def _set_measure_text(self, attr: str, text: str, color: Optional[str] = None) -> None:
        """كتابة نص وصفي في تسمية إن وُجدت"""
        self._set_measure(attr, text, color)

    def send_notification(self, title: str, message: str, urgency: str):
        """إرسال إشعار ذكي"""
        if self.enable_notifications.isChecked():
            # تحديد نوع الإشعار
            notification_type = 'general'
            if 'منخفضة' in message or 'منخفض' in message:
                notification_type = 'battery_low'
            elif 'ممتلئة' in message or 'مشحونة' in message:
                notification_type = 'battery_full'
            elif 'شحن' in message:
                notification_type = 'charging'
            
            # إرسال مع النظام الذكي
            self.notification_manager.send_notification(
                title, message, urgency, notification_type
            )
            self.log_event(f"{title}: {message}")
    
    def refresh_ai_analysis(self):
        """تحديث طبقة التوصيات وتقديرات التآكل من القياس الفعلي"""
        battery_status = self.monitor.get_battery_status()
        if not battery_status['available']:
            return

        health = self.monitor.get_battery_health()
        floor, ceiling = self.current_window()

        advice = self.ai.get_advice(
            battery_status, health, floor, ceiling,
            control_available=self.monitor.capability.can_control,
            control_active=self.monitor.control_verified,
        )
        self._render_advice(advice)
        self._notify_top_advice(advice)

        projection = self.ai.wear_projection(
            ceiling, battery_status.get('temperature'), health.get('health_percentage'))
        stress = stress_index(
            battery_status['percent'], battery_status.get('temperature'),
            battery_status['is_charging'],
            battery_status['percent'] >= ceiling,
        )
        self._render_wear(projection, stress, battery_status)
        self._render_learning(projection)
        self._render_summary(battery_status, health)

    def _render_summary(self, battery_status: Dict, health: Dict) -> None:
        """ملخص الجهاز: حقائق مقروءة من العتاد والتشخيص، لا فراغ"""
        capability = self.monitor.capability
        report = self._diagnostics_report
        floor, ceiling = self.current_window()

        self._set_measure('summary_device_label',
                          ' '.join(part for part in (capability.vendor,
                                                     capability.product) if part) or '—')
        self._set_measure('summary_mode_label',
                          t('diag.mode.' + report.device_mode) if report else '—')
        self._set_measure('summary_tier_label', t('tier.' + capability.tier),
                          theme.TIER_COLORS.get(capability.tier, theme.INK_DIM))

        mains_online = (report.mains.get('online') if report else None)
        self._set_measure('summary_mains_label',
                          t('status.on_mains') if mains_online
                          else t('status.discharging') if mains_online is False else '—')

        zones = diagnostics.plausible_zones(report.thermal) if report else []
        hottest = max(zones, key=lambda zone: zone['celsius']) if zones else None
        self._set_measure('summary_thermal_label',
                          f"{hottest['celsius']:.0f} {t('unit.celsius')} · {hottest['type']}"
                          if hottest else '—')

        self._set_measure('summary_control_label',
                          t('control.active') if self.monitor.control_verified
                          else t('control.inactive'))
        self._set_measure('summary_window_label',
                          f"{floor}–{ceiling} {t('unit.percent')}")
        self._set_measure('summary_samples_label',
                          str(len(self.ai.usage_history)))

    def _render_advice(self, advice: List) -> None:
        """عرض التوصيات في الطبقة العليا وفي مجال التحليل"""
        rows = []
        for item in advice:
            evidence = ''
            if item.evidence == 'measured':
                evidence = t('evidence.measured')
            elif item.evidence in SOURCES:
                source = SOURCES[item.evidence]
                evidence = (f"{t('evidence.source', label=source['label'])} "
                            f"<a href=\"{source['url']}\" "
                            f"style=\"color:{theme.INK_FAINT};\">{t('evidence.why')}</a>")
            rows.append({
                'severity': item.severity,
                'text': t(item.key, **item.params),
                'evidence': evidence,
                'action': item.action or '',
            })

        # بطارية غير قابلة للقياس: نتائج التشخيص هي المحتوى المفيد الوحيد
        # في هذه الحالة، فتُضاف بدل ترك المجال بسطر واحد.
        report = self._diagnostics_report
        if report is not None and report.grade in ('unmeasurable', 'impaired'):
            for finding in report.findings[:3]:
                if finding.severity in ('critical', 'warning', 'advice'):
                    rows.append({
                        'severity': finding.severity,
                        'text': t(finding.key, **finding.params),
                        'evidence': t('diag.confidence', value=finding.confidence),
                        'action': 'open_diagnostics',
                    })

        # الطبقة العليا تحمل أهم صفّين فقط، والمجال يحمل القائمة كاملة
        compact = getattr(self, 'advice_layer', None)
        if compact is not None:
            compact.set_rows(rows[:2])
        full = getattr(self, 'advice_layer_full', None)
        if full is not None:
            full.set_rows(rows)

    def _notify_top_advice(self, advice: List) -> None:
        """
        إشعار واحد عند تغيّر أهم نصيحة فقط. التكرار كل دورة تحديث إزعاج
        لا معلومة، وكان السلوك السابق يرسل عند كل تحديث.
        """
        if not advice:
            return
        top = advice[0]
        if top.severity not in ('critical', 'warning'):
            return
        if getattr(self, '_last_notified_advice', None) == top.id:
            return
        self._last_notified_advice = top.id
        self.notification_manager.send_ai_recommendation(
            t(top.key, **top.params), priority=9 if top.severity == 'critical' else 7)

    def _render_wear(self, projection: Dict, stress: Dict, battery_status: Dict) -> None:
        """أرقام التآكل والإجهاد كما حسبها المحرك المرجعي"""
        per_year = t('unit.per_year')
        self._set_measure('calendar_loss_label', f"{projection['calendar']:.1f} {per_year}")
        self._set_measure('cyclic_loss_label', f"{projection['cyclic']:.1f} {per_year}")
        self._set_measure('equivalent_cycles_label',
                          f"{projection['equivalent_cycles']:.2f} {t('unit.cycles')}")
        self._set_measure('high_soc_hours_label',
                          f"{projection['hours_high_soc_per_day']:.1f} {t('unit.hour_short')}")

        band = stress['band']
        self._set_measure('stress_label',
                          f"{stress['index']:.0f} · {t('stress.' + band)}",
                          theme.stress_color(band))

        days = projection.get('days_to_eol')
        if days is None:
            eol_text = t('health.eol_unknown')
        elif days == 0:
            eol_text = t('health.eol_reached')
        else:
            eol_text = t('health.eol_days', days=days)
        self._set_measure('eol_label', eol_text)

        headline = theme.field_for_state(
            battery_status['percent'], battery_status['is_charging'],
            battery_status.get('reporting', True), *self.current_window())[2]
        if hasattr(self, 'rail'):
            self.rail.set_verdict(t(headline), band)

    def _render_learning(self, projection: Dict) -> None:
        """حجم ما تعلّمه المحرك من هذا الجهاز وثقته"""
        stats = self.ai.get_usage_statistics()
        self._set_measure('data_points_label', f"{stats.get('total_records', 0)}")
        self._set_measure('patterns_found_label', f"{projection['observed_days']:.2f}")
        self._set_measure('drain_rate_label',
                          f"{stats.get('average_drain_rate', 0):.2f} {t('unit.per_minute')}")
        self._set_measure('charge_rate_label',
                          f"{stats.get('average_charge_rate', 0):.2f} {t('unit.per_minute')}")
        self._set_measure('confidence_label', f"{self.ai._calculate_confidence()}%")

        soh = projection.get('soh_percent')
        self._set_measure('health_score_label',
                          f"{soh:.0f}%" if soh is not None else t('health.unknown'))

        if hasattr(self, 'prediction_text'):
            status = self.monitor.get_battery_status()
            # التنبؤ بلا قياس صالح تخمين: لا يُعرض على بطارية لا تُبلّغ
            prediction = self.ai.predict_time_remaining(
                int(status['percent']), status['is_charging']) \
                if status.get('reporting', True) else None
            lines = [prediction] if prediction else []
            heavy = stats.get('heavy_usage_hours') or []
            if heavy:
                lines.append(t('record.high_soc_hours') + ': ' +
                             ', '.join(f"{hour}:00" for hour in heavy))
            if projection['observed_days'] < 1:
                lines.append(t('record.learning'))
            self.prediction_text.setText('\n'.join(line for line in lines if line))

    def _set_measure(self, attr: str, text: str, color: Optional[str] = None) -> None:
        """كتابة قيمة قياس في تسمية إن وُجدت (التخطيط لا يقيّد التحديث)"""
        label = getattr(self, attr, None)
        if label is None:
            return
        label.setText(text)
        if color:
            label.setStyleSheet(f"color: {color};")

    def _sync_permissions(self):
        """مزامنة الصلاحيات مع جميع المكونات"""
        if self.permission_manager.sudo_password:
            if self.monitor.charge_controller:
                self.monitor.charge_controller.sudo_password = self.permission_manager.sudo_password
            self.optimizer.set_sudo_password(self.permission_manager.sudo_password)
            logger.info("تم مزامنة الصلاحيات مع جميع المكونات")
    
    def save_all_settings(self):
        """حفظ جميع الإعدادات (موحد)"""
        settings = self.get_current_settings()
        
        # حدود البطارية: نفس مفاتيح القراءة في load_settings
        # (المفتاح = اسم العنصر مع استبدال _spin بـ _threshold)
        thresholds = settings.get('battery_thresholds', {})
        threshold_keys = {
            'critical_low': ('critical_battery_threshold', 10),
            'low': ('low_battery_threshold', 20),
            'optimal_min': ('optimal_min_threshold', 40),
            'optimal_max': ('optimal_max_threshold', 80),
            'high': ('high_battery_threshold', 90),
            'full': ('full_battery_threshold', 95),
        }
        for tkey, (skey, default) in threshold_keys.items():
            self.settings.setValue(skey, thresholds.get(tkey, default))
        
        # التنبيهات الذكية: نفس مفاتيح القراءة
        smart_alerts = settings.get('smart_alerts', {})
        for alert_type, enabled in smart_alerts.items():
            self.settings.setValue(alert_type, bool(enabled))
        
        # فترات التذكير بالدقائق: نفس مفاتيح القراءة
        intervals = settings.get('reminder_intervals', {})
        interval_keys = {
            'battery_critical': ('battery_critical_interval', 1),
            'battery_low': ('battery_low_interval', 5),
            'charge_complete': ('charge_complete_interval', 10),
            'unplug_charger': ('unplug_charger_interval', 5),
        }
        for ikey, (skey, default_min) in interval_keys.items():
            self.settings.setValue(skey, int(intervals.get(ikey, default_min * 60) // 60))
        
        # حفظ إعدادات عامة
        if hasattr(self, 'start_on_boot'):
            self.settings.setValue('start_on_boot', self.start_on_boot.isChecked())
        if hasattr(self, 'minimize_to_tray'):
            self.settings.setValue('minimize_to_tray', self.minimize_to_tray.isChecked())
        if hasattr(self, 'show_battery_in_tray'):
            self.settings.setValue('show_battery_in_tray', self.show_battery_in_tray.isChecked())
        
        # حفظ إعدادات التحسين التلقائي
        if hasattr(self, 'enable_auto_optimization'):
            auto_opt_enabled = self.enable_auto_optimization.isChecked()
            self.settings.setValue('auto_optimization_enabled', auto_opt_enabled)
            
            # حفظ الوضع
            if hasattr(self, 'opt_mode_continuous') and self.opt_mode_continuous.isChecked():
                mode = 'continuous'
            elif hasattr(self, 'opt_mode_scheduled') and self.opt_mode_scheduled.isChecked():
                mode = 'scheduled'
            else:
                mode = 'on_demand'
            self.settings.setValue('auto_optimization_mode', mode)
            
            # حفظ الفترة
            if hasattr(self, 'opt_interval_slider'):
                interval = self.opt_interval_slider.value()
                self.settings.setValue('auto_optimization_interval', interval)
            
            # حفظ العتبات
            if hasattr(self, 'opt_cpu_threshold'):
                self.settings.setValue('opt_cpu_threshold', self.opt_cpu_threshold.value())
            if hasattr(self, 'opt_memory_threshold'):
                self.settings.setValue('opt_memory_threshold', self.opt_memory_threshold.value())
            if hasattr(self, 'opt_disk_threshold'):
                self.settings.setValue('opt_disk_threshold', self.opt_disk_threshold.value())
            if hasattr(self, 'opt_power_threshold'):
                self.settings.setValue('opt_power_threshold', self.opt_power_threshold.value())
        
        # حفظ إعدادات التحكم في الشحن
        if hasattr(self, 'max_charge_slider') and hasattr(self, 'min_charge_slider'):
            max_charge = self.max_charge_slider.value()
            min_charge = self.min_charge_slider.value()
            auto_enabled = self.auto_charge_control.isChecked()
            
            # التحقق من صحة القيم
            if auto_enabled and max_charge <= min_charge:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "خطأ في الإعدادات",
                    "الحد الأقصى للشحن يجب أن يكون أكبر من الحد الأدنى"
                )
                return
            
            # حفظ القيم
            self.settings.setValue('auto_charge_control', auto_enabled)
            self.settings.setValue('max_charge_limit', max_charge)
            self.settings.setValue('min_charge_limit', min_charge)
            
            # تطبيق التحكم في الشحن فقط إذا كان مفعلاً
            if auto_enabled:
                # طلب الصلاحيات فقط عند الحاجة ومرة واحدة
                needs_permission = self.monitor.can_control_charging and not self.permission_manager.has_admin_rights
                
                if needs_permission:
                    if self.permission_manager.request_permissions(self):
                        # مزامنة الصلاحيات مع جميع المكونات
                        self._sync_permissions()
                    else:
                        from PyQt6.QtWidgets import QMessageBox
                        result = QMessageBox.question(
                            self,
                            "صلاحيات محدودة",
                            "لم يتم الحصول على الصلاحيات الكاملة.\nسيعمل التطبيق بالإشعارات فقط.\n\nهل تريد المتابعة؟",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        if result == QMessageBox.StandardButton.No:
                            return
                
                # تفعيل التحكم
                success = self.monitor.enable_charge_control(min_charge, max_charge)
                
                if success:
                    self.log_event(f"تم تفعيل التحكم التلقائي: {min_charge}%-{max_charge}%")
                    self.status_label.setText("تم حفظ الإعدادات وتفعيل التحكم")
                else:
                    self.log_event("تم حفظ الإعدادات - سيتم استخدام الإشعارات فقط")
                    self.status_label.setText("تم الحفظ - إشعارات فقط")
            else:
                # إيقاف التحكم
                self.monitor.disable_charge_control()
                self.log_event("تم إيقاف التحكم التلقائي")
                self.status_label.setText("تم حفظ الإعدادات")
        else:
            self.status_label.setText("تم حفظ الإعدادات")
        
        # تحديث خيط المراقبة
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.settings = self.get_current_settings()
        
        # تحديث إعدادات الإشعارات
        self.update_notification_settings()
        
        self.log_event("تم حفظ جميع الإعدادات")
        QTimer.singleShot(3000, lambda: self.status_label.setText("جاهز للعمل"))
    
    def get_current_settings(self) -> Dict:
        """الحصول على الإعدادات الحالية المحسّنة"""
        settings = {
            # الإعدادات الأساسية
            'notify_low_battery': getattr(self, 'enable_notifications', None) and self.enable_notifications.isChecked() if hasattr(self, 'enable_notifications') else True,
            'notify_charge_suggested': getattr(self, 'enable_notifications', None) and self.enable_notifications.isChecked() if hasattr(self, 'enable_notifications') else True,
            'notify_unplug_suggested': getattr(self, 'enable_notifications', None) and self.enable_notifications.isChecked() if hasattr(self, 'enable_notifications') else True,
            'notify_full_charge': getattr(self, 'enable_notifications', None) and self.enable_notifications.isChecked() if hasattr(self, 'enable_notifications') else True,
            
            # الإعدادات الجديدة
            'enable_notifications': getattr(self, 'enable_notifications', None) and self.enable_notifications.isChecked() if hasattr(self, 'enable_notifications') else True,
            'enable_sounds': getattr(self, 'enable_sounds', None) and self.enable_sounds.isChecked() if hasattr(self, 'enable_sounds') else True,
            'enable_reminders': getattr(self, 'enable_reminders', None) and self.enable_reminders.isChecked() if hasattr(self, 'enable_reminders') else True,
        }
        
        # حدود البطارية المخصصة
        battery_thresholds = {}
        threshold_attrs = [
            ('critical_battery_spin', 'critical_low'),
            ('low_battery_spin', 'low'),
            ('optimal_min_spin', 'optimal_min'),
            ('optimal_max_spin', 'optimal_max'),
            ('high_battery_spin', 'high'),
            ('full_battery_spin', 'full')
        ]
        
        for attr_name, threshold_key in threshold_attrs:
            if hasattr(self, attr_name):
                battery_thresholds[threshold_key] = getattr(self, attr_name).value()
            else:
                # قيم افتراضية
                defaults = {
                    'critical_low': 10, 'low': 20, 'optimal_min': 40,
                    'optimal_max': 80, 'high': 90, 'full': 95
                }
                battery_thresholds[threshold_key] = defaults.get(threshold_key, 50)
        
        settings['battery_thresholds'] = battery_thresholds
        
        # إعدادات التنبيهات الذكية
        smart_alerts = {}
        smart_alert_attrs = [
            'charger_disconnect_reminder', 'optimal_charge_reminder',
            'health_warnings', 'usage_pattern_alerts',
            'temperature_warnings', 'ai_recommendations'
        ]
        
        for alert_type in smart_alert_attrs:
            checkbox_attr = f"{alert_type}_checkbox"
            if hasattr(self, checkbox_attr):
                smart_alerts[alert_type] = getattr(self, checkbox_attr).isChecked()
            else:
                smart_alerts[alert_type] = True  # افتراضي مفعّل
        
        settings['smart_alerts'] = smart_alerts
        
        # فترات التذكير
        reminder_intervals = {}
        reminder_attrs = [
            ('battery_critical_interval_spin', 'battery_critical'),
            ('battery_low_interval_spin', 'battery_low'),
            ('charge_complete_interval_spin', 'charge_complete'),
            ('unplug_charger_interval_spin', 'unplug_charger')
        ]
        
        for attr_name, interval_key in reminder_attrs:
            if hasattr(self, attr_name):
                reminder_intervals[interval_key] = getattr(self, attr_name).value() * 60  # تحويل لثواني
            else:
                # قيم افتراضية بالثواني
                defaults = {
                    'battery_critical': 60, 'battery_low': 300,
                    'charge_complete': 600, 'unplug_charger': 300
                }
                reminder_intervals[interval_key] = defaults.get(interval_key, 300)
        
        settings['reminder_intervals'] = reminder_intervals
        
        # الإعدادات القديمة للتوافق
        settings.update({
            'low_battery_threshold': battery_thresholds.get('low', 20),
            'charge_threshold': battery_thresholds.get('optimal_min', 40),
            'unplug_threshold': battery_thresholds.get('optimal_max', 80)
        })

        # سياسة الحارس: مصدر واحد يقرؤه المنسّق وخيط المراقبة معاً
        settings.update(self._guard_settings())
        
        return settings

    # ══════════════════════════════════════════════════════
    # الحارس: الإعدادات والتقارير والإجراءات
    # ══════════════════════════════════════════════════════

    def _guard_settings(self) -> Dict:
        """
        سياسة الحارس من الإعدادات المحفوظة.

        تُقرأ من QSettings لا من عناصر الواجهة، لأن المنسّق يُبنى قبل الواجهة
        وقد يعمل بلا واجهة أصلاً في وضع الخلفية. المنطق نفسه في
        `default_settings.guard_settings_from` يستخدمه متحكّم الخلفية، فلا
        تختلف السياسة بين الوضعين بصمت.
        """
        return guard_settings_from(qsettings_reader(self.settings))

    def _settings_snapshot(self) -> Dict:
        """إعدادات المنسّق عند البناء، قبل وجود أي عنصر واجهة"""
        return self._guard_settings()

    def on_intelligence_report(self, report) -> None:
        """
        تقرير استدلال جديد. يُحدّث لوحة التحليل والصينية، ويُنبّه على المخالف
        الأسوأ مرة واحدة لكل اسم حتى لا يتحوّل التنبيه إلى إزعاج متكرر.
        """
        self._last_intelligence = report
        try:
            self._render_offenders(report)
        except Exception as e:
            logger.error(f"تعذّر عرض تقرير الاستدلال: {e}")
        try:
            if hasattr(self, 'tray') and self.tray is not None:
                self.tray.update_offenders(report)
        except Exception as e:
            logger.debug(f"تعذّر تحديث الصينية بالمخالفين: {e}")

    def _render_offenders(self, report) -> None:
        """كتابة أعلى المخالفين في لوحة التحليل إن وُجد مكانها"""
        label = getattr(self, 'offenders_label', None)
        if label is None:
            return
        actionable = report.offenders[:5]
        if not actionable:
            label.setText(t('guard.no_offenders'))
            return
        lines = []
        for item in actionable:
            watts = f"{item.watts:.1f}{t('unit.watt')}" if item.watts else '—'
            lines.append(t('guard.offender_line', name=item.name, watts=watts,
                           score=int(item.damage_score),
                           loss=round(item.annual_capacity_loss, 2)))
        label.setText('\n'.join(lines))

    def _on_guard_action(self, outcome, offender) -> None:
        """
        بلاغ من الحارس. يُسجَّل دائماً، ويُشعَر به المستخدم حين يكون إجراءً
        فعلياً أو تنبيهاً على مخالف يستحق قراره.
        """
        try:
            self.log_event(t('guard.log_line', kind=t(f'guard.action.{outcome.kind}'),
                             name=outcome.name,
                             state=t('guard.applied') if outcome.applied
                             else t('guard.skipped')))
        except Exception as e:
            logger.debug(f"تعذّر تسجيل إجراء الحارس: {e}")

        if offender is None or not outcome.applied:
            return
        try:
            self.send_notification(
                t('guard.title'),
                t('guard.notify.offender', name=offender.name,
                  watts=round(offender.watts, 1),
                  loss=round(offender.annual_capacity_loss, 2)),
                'normal')
        except Exception as e:
            logger.debug(f"تعذّر إشعار الحارس: {e}")

    def guard_suspend(self, name: str) -> None:
        """تعليق مخالف بطلب المستخدم (قابل للتراجع)"""
        self._run_guard_action(self.guard_service.suspend, name)

    def guard_resume(self, name: str) -> None:
        self._run_guard_action(self.guard_service.resume, name)

    def guard_throttle(self, name: str) -> None:
        self._run_guard_action(self.guard_service.throttle, name)

    def guard_restore(self, name: str) -> None:
        self._run_guard_action(self.guard_service.restore, name)

    def guard_ignore(self, name: str) -> None:
        """منع الحارس من لمس هذا الاسم، وحفظ القرار"""
        self.guard_service.ignore(name)
        self.settings.setValue('guard_blocklist',
                               ','.join(self.guard_service.policy.blocklist))
        self.log_event(t('guard.ignored', name=name))

    def guard_terminate(self, name: str) -> None:
        """
        إيقاف نهائي بطلب صريح، بعد تأكيد. لا يُنفَّذ تلقائياً في أي حالة،
        لأن خسارة عمل غير محفوظ أغلى من أي توفير في الطاقة.
        """
        answer = QMessageBox.warning(
            self, t('guard.title'), t('guard.confirm_terminate', name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_guard_action(self.guard_service.terminate, name)

    def _run_guard_action(self, action, name: str) -> None:
        """تنفيذ إجراء حارس مع إبلاغ صادق عن النتيجة"""
        try:
            outcome = action(name)
        except Exception as e:
            logger.error(f"فشل إجراء الحارس على {name}: {e}")
            self.log_event(t('guard.failed', name=name, error=str(e)))
            return
        if outcome.applied:
            self.log_event(t('guard.log_line',
                             kind=t(f'guard.action.{outcome.kind}'), name=name,
                             state=t('guard.applied')))
        else:
            self.log_event(t('guard.refused', name=name,
                             reason=t(f'guard.reason.{outcome.reason}')))
    
    def on_autostart_changed(self, state):
        """معالجة تغيير حالة التشغيل التلقائي"""
        try:
            if state == 2:  # Qt.CheckState.Checked
                success, message = autostart_manager.enable()
                if success:
                    self.log_event(f"{message}")
                    logger.info("تم تفعيل التشغيل التلقائي")
                else:
                    self.log_event(f"فشل التفعيل: {message}")
                    logger.error(f"فشل تفعيل التشغيل التلقائي: {message}")
                    # إلغاء التحديد إذا فشل
                    self.start_on_boot.blockSignals(True)
                    self.start_on_boot.setChecked(False)
                    self.start_on_boot.blockSignals(False)
            else:
                success, message = autostart_manager.disable()
                if success:
                    self.log_event(f"{message}")
                    logger.info("تم إلغاء التشغيل التلقائي")
                else:
                    self.log_event(f"فشل الإلغاء: {message}")
                    logger.error(f"فشل إلغاء التشغيل التلقائي: {message}")
        except Exception as e:
            self.log_event(f"خطأ في التشغيل التلقائي: {e}")
            logger.error(f"خطأ في معالجة التشغيل التلقائي: {e}")
    
    def on_auto_optimization_changed(self, state):
        """معالجة تغيير حالة التحسين التلقائي"""
        try:
            if state == 2:  # Qt.CheckState.Checked
                # تحديد الوضع
                if hasattr(self, 'opt_mode_continuous') and self.opt_mode_continuous.isChecked():
                    mode = 'continuous'
                elif hasattr(self, 'opt_mode_scheduled') and self.opt_mode_scheduled.isChecked():
                    mode = 'scheduled'
                else:
                    mode = 'on_demand'
                
                # تحديد الفترة (بالثواني)
                interval = 300  # افتراضي 5 دقائق
                if hasattr(self, 'opt_interval_slider'):
                    interval = self.opt_interval_slider.value() * 60
                
                # تحديد العتبات
                if hasattr(self, 'opt_cpu_threshold'):
                    self.auto_optimizer.set_threshold('cpu_percent', self.opt_cpu_threshold.value())
                if hasattr(self, 'opt_memory_threshold'):
                    self.auto_optimizer.set_threshold('memory_percent', self.opt_memory_threshold.value())
                if hasattr(self, 'opt_disk_threshold'):
                    self.auto_optimizer.set_threshold('disk_percent', self.opt_disk_threshold.value())
                if hasattr(self, 'opt_power_threshold'):
                    self.auto_optimizer.set_threshold('power_draw', self.opt_power_threshold.value())
                
                # تطبيق الإعدادات
                self.auto_optimizer.set_optimization_mode(mode)
                self.auto_optimizer.set_optimization_interval(interval)
                self.auto_optimizer.auto_optimize_enabled = True
                
                # بدء التحسين التلقائي
                self.auto_optimizer.start()
                
                self.log_event(f"تم تفعيل التحسين التلقائي - الوضع: {mode}")
                logger.info(f"تم تفعيل التحسين التلقائي - الوضع: {mode}, الفترة: {interval}ث")
                
                # بدء مؤقت لتحديث إحصائيات التحسين
                if not hasattr(self, 'auto_opt_stats_timer'):
                    self.auto_opt_stats_timer = QTimer()
                    self.auto_opt_stats_timer.timeout.connect(self.update_auto_optimization_stats)
                self.auto_opt_stats_timer.start(5000)  # تحديث كل 5 ثواني
                
            else:
                # إيقاف التحسين التلقائي
                self.auto_optimizer.auto_optimize_enabled = False
                self.auto_optimizer.stop()
                
                if hasattr(self, 'auto_opt_stats_timer'):
                    self.auto_opt_stats_timer.stop()
                
                self.log_event("تم إيقاف التحسين التلقائي")
                logger.info("تم إيقاف التحسين التلقائي")
                
        except Exception as e:
            self.log_event(f"خطأ في التحسين التلقائي: {e}")
            logger.error(f"خطأ في معالجة التحسين التلقائي: {e}")
    
    def update_auto_optimization_stats(self):
        """تحديث إحصائيات التحسين التلقائي"""
        try:
            stats = self.auto_optimizer.get_statistics()
            system_status = self.auto_optimizer.get_system_status()
            
            # تحديث حالة النظام في السجل
            if stats.get('needs_optimization'):
                priority = stats.get('optimization_priority', 0)
                health = stats.get('system_health_score', 100)
                
                if priority >= 7:
                    self.log_event(f"النظام يحتاج تحسين عاجل - الأولوية: {priority}/10, الصحة: {health}%")
                elif priority >= 4:
                    self.log_event(f"النظام يحتاج تحسين - الأولوية: {priority}/10, الصحة: {health}%")
            
            # تحديث الإحصائيات في الواجهة إذا كانت موجودة
            if hasattr(self, 'auto_opt_count_label'):
                self.auto_opt_count_label.setText(f"{stats.get('optimization_count', 0)}")
            
            if hasattr(self, 'auto_opt_power_saved_label'):
                self.auto_opt_power_saved_label.setText(f"{stats.get('total_power_saved', 0):.1f}%")
            
            if hasattr(self, 'system_health_label'):
                health = stats.get('system_health_score', 100)
                self.system_health_label.setText(f"{health}%")
                
                # تغيير اللون حسب الصحة
                if health >= 80:
                    color = "#10b981"
                elif health >= 60:
                    color = "#3b82f6"
                elif health >= 40:
                    color = "#f59e0b"
                else:
                    color = "#ef4444"
                
                self.system_health_label.setStyleSheet(f"""
                    QLabel {{
                        font-size: 18px;
                        color: {color};
                        background: transparent;
                        font-weight: 700;
                    }}
                """)
            
        except Exception as e:
            logger.error(f"خطأ في تحديث إحصائيات التحسين التلقائي: {e}")
    
    def load_settings(self):
        """تحميل الإعدادات المحفوظة المحسّنة"""
        try:
            # إعدادات الإشعارات الأساسية
            if hasattr(self, 'enable_notifications'):
                self.enable_notifications.setChecked(self.settings.value('enable_notifications', True, type=bool))
            if hasattr(self, 'low_battery_spin'):
                self.low_battery_spin.setValue(self.settings.value('low_battery_threshold', 20, type=int))
            if hasattr(self, 'charge_threshold_spin'):
                self.charge_threshold_spin.setValue(self.settings.value('charge_threshold', 40, type=int))
            if hasattr(self, 'unplug_threshold_spin'):
                self.unplug_threshold_spin.setValue(self.settings.value('unplug_threshold', 80, type=int))
        
            # إعدادات الإشعارات الجديدة
            if hasattr(self, 'enable_sounds'):
                self.enable_sounds.setChecked(self.settings.value('enable_sounds', True, type=bool))
            if hasattr(self, 'enable_reminders'):
                self.enable_reminders.setChecked(self.settings.value('enable_reminders', True, type=bool))
            
            # حدود البطارية المخصصة
            threshold_defaults = {
                'critical_battery_spin': 10,
                'low_battery_spin': 20,
                'optimal_min_spin': 40,
                'optimal_max_spin': 80,
                'high_battery_spin': 90,
                'full_battery_spin': 95
            }
            
            for attr_name, default_value in threshold_defaults.items():
                if hasattr(self, attr_name):
                    setting_key = attr_name.replace('_spin', '_threshold')
                    value = self.settings.value(setting_key, default_value, type=int)
                    getattr(self, attr_name).setValue(value)
            
            # إعدادات التنبيهات الذكية
            smart_alert_defaults = {
                'charger_disconnect_reminder_checkbox': True,
                'optimal_charge_reminder_checkbox': True,
                'health_warnings_checkbox': True,
                'usage_pattern_alerts_checkbox': True,
                'temperature_warnings_checkbox': True,
                'ai_recommendations_checkbox': True
            }
            
            for attr_name, default_value in smart_alert_defaults.items():
                if hasattr(self, attr_name):
                    setting_key = attr_name.replace('_checkbox', '')
                    value = self.settings.value(setting_key, default_value, type=bool)
                    getattr(self, attr_name).setChecked(value)
            
            # فترات التذكير
            reminder_defaults = {
                'battery_critical_interval_spin': 1,
                'battery_low_interval_spin': 5,
                'charge_complete_interval_spin': 10,
                'unplug_charger_interval_spin': 5
            }
            
            for attr_name, default_value in reminder_defaults.items():
                if hasattr(self, attr_name):
                    setting_key = attr_name.replace('_spin', '')
                    value = self.settings.value(setting_key, default_value, type=int)
                    getattr(self, attr_name).setValue(value)
            
            # إعدادات عامة - التحقق من الحالة الفعلية للتشغيل التلقائي
            try:
                actual_autostart_state = autostart_manager.is_enabled()
            except Exception as e:
                logger.warning(f"تعذر التحقق من حالة التشغيل التلقائي: {e}")
                actual_autostart_state = False
                
            if hasattr(self, 'start_on_boot'):
                self.start_on_boot.blockSignals(True)
                self.start_on_boot.setChecked(actual_autostart_state)
                self.start_on_boot.blockSignals(False)
            
            if hasattr(self, 'minimize_to_tray'):
                # متوافق مع default_settings.py (False افتراضياً)
                self.minimize_to_tray.setChecked(self.settings.value('minimize_to_tray', False, type=bool))
            if hasattr(self, 'show_battery_in_tray'):
                self.show_battery_in_tray.setChecked(self.settings.value('show_battery_in_tray', True, type=bool))
            
            # إعدادات التحكم في الشحن
            if hasattr(self, 'auto_charge_control'):
                self.auto_charge_control.setChecked(self.settings.value('auto_charge_control', False, type=bool))
                max_charge = self.settings.value('max_charge_limit', 80, type=int)
                min_charge = self.settings.value('min_charge_limit', 40, type=int)
                if hasattr(self, 'max_charge_slider'):
                    self.max_charge_slider.setValue(max_charge)
                if hasattr(self, 'min_charge_slider'):
                    self.min_charge_slider.setValue(min_charge)
                if hasattr(self, 'max_charge_value_label'):
                    self.max_charge_value_label.setText(f"{max_charge}%")
                if hasattr(self, 'min_charge_value_label'):
                    self.min_charge_value_label.setText(f"{min_charge}%")
            
            # إعدادات التحسين التلقائي
            if hasattr(self, 'enable_auto_optimization'):
                auto_opt_enabled = self.settings.value('auto_optimization_enabled', False, type=bool)
                self.enable_auto_optimization.blockSignals(True)
                self.enable_auto_optimization.setChecked(auto_opt_enabled)
                self.enable_auto_optimization.blockSignals(False)
                
                # تحميل الوضع
                mode = self.settings.value('auto_optimization_mode', 'on_demand', type=str)
                if hasattr(self, 'opt_mode_continuous'):
                    self.opt_mode_continuous.setChecked(mode == 'continuous')
                if hasattr(self, 'opt_mode_on_demand'):
                    self.opt_mode_on_demand.setChecked(mode == 'on_demand')
                if hasattr(self, 'opt_mode_scheduled'):
                    self.opt_mode_scheduled.setChecked(mode == 'scheduled')
                
                # تحميل الفترة
                if hasattr(self, 'opt_interval_slider'):
                    interval = self.settings.value('auto_optimization_interval', 5, type=int)
                    self.opt_interval_slider.setValue(interval)
                
                # تحميل العتبات
                if hasattr(self, 'opt_cpu_threshold'):
                    self.opt_cpu_threshold.setValue(self.settings.value('opt_cpu_threshold', 70, type=int))
                if hasattr(self, 'opt_memory_threshold'):
                    self.opt_memory_threshold.setValue(self.settings.value('opt_memory_threshold', 75, type=int))
                if hasattr(self, 'opt_disk_threshold'):
                    self.opt_disk_threshold.setValue(self.settings.value('opt_disk_threshold', 85, type=int))
                if hasattr(self, 'opt_power_threshold'):
                    self.opt_power_threshold.setValue(self.settings.value('opt_power_threshold', 15, type=int))
                
                # بدء التحسين التلقائي إذا كان مفعلاً
                if auto_opt_enabled:
                    QTimer.singleShot(2000, lambda: self.on_auto_optimization_changed(2))
            
            # تحديث إعدادات الإشعارات بعد التحميل
            self.update_notification_settings()
            
        except Exception as e:
            logger.error(f"خطأ في تحميل الإعدادات: {e}")
            # تحديث إعدادات الإشعارات الأساسية على الأقل
            try:
                self.update_notification_settings()
            except:
                pass
    
    def log_event(self, message: str):
        """تسجيل حدث في السجل"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        # إضافة في البداية بدلاً من النهاية
        cursor = self.events_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.insertText(log_message + "\n")
        
        # الاحتفاظ بآخر 500 سطر فقط
        doc = self.events_log.document()
        if doc.blockCount() > 500:
            # حذف الأسطر الزائدة من النهاية دفعة واحدة
            cursor.movePosition(cursor.MoveOperation.End)
            while doc.blockCount() > 500:
                cursor.movePosition(cursor.MoveOperation.PreviousBlock, cursor.MoveMode.KeepAnchor, 1)
                cursor.removeSelectedText()
                cursor.movePosition(cursor.MoveOperation.End)
        
        # حفظ السجل في ملف
        self._save_log_to_file(log_message)
        
        logger.info(message)
    
    def _save_log_to_file(self, log_message: str):
        """حفظ السجل في ملف (إلحاق سريع بدل إعادة كتابة الملف كاملاً)"""
        try:
            from resource_path import get_data_path
            
            log_file = get_data_path('battery_events.log')
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # إلحاق السطر الجديد فقط (O(1)) بدل قراءة وكتابة كل السجل
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
            
            # تقليم الملف دورياً (كل 200 حدث) للحفاظ على حجمه معقولاً
            self._log_write_count = getattr(self, '_log_write_count', 0) + 1
            if self._log_write_count % 200 == 0:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                if len(lines) > 1000:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.writelines(lines[-1000:])
        except Exception as e:
            logger.error(f"خطأ في حفظ السجل: {e}")
    
    def _load_log_from_file(self):
        """تحميل آخر الأحداث من الملف"""
        try:
            from resource_path import get_data_path
            log_file = get_data_path('battery_events.log')
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # عرض آخر 100 سطر (الملف يُلحق بالترتيب)
                    self.events_log.setPlainText(''.join(lines[-100:]))
        except Exception as e:
            logger.error(f"خطأ في تحميل السجل: {e}")
    
    def clear_log(self):
        """مسح السجل من الواجهة والملف"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            'تأكيد المسح',
            'هل أنت متأكد من مسح سجل الأحداث؟\nلا يمكن التراجع عن هذا الإجراء.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.events_log.clear()
                from resource_path import get_data_path
                log_file = get_data_path('battery_events.log')
                if log_file.exists():
                    log_file.unlink()
                self._log_write_count = 0
                logger.info("تم مسح سجل الأحداث")
            except Exception as e:
                logger.error(f"خطأ في مسح السجل: {e}")
                QMessageBox.warning(self, "خطأ", f"فشل مسح السجل: {e}")
    
    def reset_ai_data(self):
        """إعادة تعيين بيانات الذكاء الاصطناعي"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            'تأكيد إعادة التعيين',
            'هل أنت متأكد من إعادة تعيين بيانات الذكاء الاصطناعي؟\n'
            'سيتم حذف جميع الأنماط المتعلمة والتوصيات.\n'
            'لا يمكن التراجع عن هذا الإجراء.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # تصفير داخل نفس الكائن حتى تبقى مراجع خيط المراقبة
                # والمحسّنات صالحة (استبدال الكائن كان يُحيي البيانات القديمة)
                self.ai.reset()
                # تعلّم الحارس جزء من الذكاء نفسه: تركه يعني بقاء نموذج طاقة
                # وسجل مخالفين مبنيين على بيانات أُعلن مسحها.
                self.guard_service.reset()
                self._last_intelligence = None
                
                # تحديث الواجهة
                if hasattr(self, 'recommendations_text'):
                    self.recommendations_text.setPlainText("تم إعادة التعيين. جارٍ التعلم من جديد...")
                if hasattr(self, 'prediction_text'):
                    self.prediction_text.setText("تم إعادة التعيين. جارٍ جمع بيانات جديدة...")
                
                self.log_event("تم إعادة تعيين بيانات الذكاء الاصطناعي بنجاح")
                logger.info("تم إعادة تعيين بيانات AI")
                QMessageBox.information(self, "نجح", "تم إعادة تعيين بيانات الذكاء الاصطناعي.\nسيبدأ التعلم من جديد.")
            except Exception as e:
                logger.error(f"خطأ في إعادة تعيين AI: {e}")
                QMessageBox.warning(self, "خطأ", f"فشل إعادة تعيين AI: {e}")
    
    def closeEvent(self, event):
        """معالجة إغلاق النافذة"""
        if getattr(self, 'minimize_to_tray', None) and self.minimize_to_tray.isChecked():
            event.ignore()
            self.hide()
            self.tray.show_message(
                "BatteryGuardAI",
                "البرنامج لا يزال يعمل في الخلفية"
            )
        else:
            event.accept()
            self.quit_application()
    
    def _update_advanced_stats(self):
        """تحديث الإحصائيات المتقدمة - يُنفذ فقط عند ظهور تبويب الإحصائيات
        لتجنب مسح سجل كامل (آلاف العينات) كل ثانيتين دون حاجة"""
        if not hasattr(self, 'total_charge_time_label'):
            return
        if not hasattr(self, 'stats_tab') or self.tabs.currentWidget() is not self.stats_tab:
            return
        
        # حساب أوقات الشحن والاستخدام
        charge_time = 0
        discharge_time = 0
        battery_levels = []
        power_draws = []
        
        for i in range(1, len(self.ai.usage_history)):
            prev = self.ai.usage_history[i-1]
            curr = self.ai.usage_history[i]
            
            try:
                time_diff = (datetime.fromisoformat(curr['timestamp']) - 
                           datetime.fromisoformat(prev['timestamp'])).total_seconds() / 60
                
                if time_diff < 30:  # تجاهل الفجوات الكبيرة
                    if curr['is_charging']:
                        charge_time += time_diff
                    else:
                        discharge_time += time_diff
                    
                    battery_levels.append(curr['battery_percent'])
                    
                    if curr.get('power_draw', 0) > 0:
                        power_draws.append(curr['power_draw'])
            except:
                pass
        
        # تحديث الأوقات
        charge_hours = int(charge_time // 60)
        charge_mins = int(charge_time % 60)
        self.total_charge_time_label.setText(f"{charge_hours}س {charge_mins}د")
        
        discharge_hours = int(discharge_time // 60)
        discharge_mins = int(discharge_time % 60)
        self.total_discharge_time_label.setText(f"{discharge_hours}س {discharge_mins}د")
        
        # متوسط مستوى البطارية
        if battery_levels:
            avg_level = sum(battery_levels) / len(battery_levels)
            self.avg_battery_level_label.setText(f"{avg_level:.0f}%")
        
        # دورات الشحن اليوم
        today = datetime.now().date()
        today_cycles = sum(1 for e in self.ai.usage_history 
                          if datetime.fromisoformat(e['timestamp']).date() == today 
                          and e['is_charging'])
        self.charge_cycles_today_label.setText(f"{today_cycles}")
        
        # استهلاك الطاقة
        if power_draws:
            avg_power = sum(power_draws) / len(power_draws)
            peak_power = max(power_draws)
            self.avg_power_draw_label.setText(f"{avg_power:.1f} W")
            self.peak_power_draw_label.setText(f"{peak_power:.1f} W")
        else:
            self.avg_power_draw_label.setText("0 W")
            self.peak_power_draw_label.setText("0 W")
    
    def run_optimization(self):
        """تشغيل التحسين الذكي المتقدم مع الذكاء الاصطناعي"""
        # استخدام الصلاحيات المحفوظة أو طلبها مرة واحدة
        if not self.permission_manager.has_admin_rights:
            if self.permission_manager.request_permissions(self):
                # مزامنة الصلاحيات مع جميع المكونات
                self._sync_permissions()
        
        # تمرير محرك الذكاء الاصطناعي للمحسن
        self.optimizer.ai_engine = self.ai
        
        self.optimize_button.setEnabled(False)
        self.optimize_button.setText("تحليل ذكي جارٍ...")
        self.optimize_status.setText("الذكاء الاصطناعي يحلل أنماط الاستخدام ويحدد أفضل التحسينات...")
        
        # تشغيل التحسين الذكي في خيط منفصل
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class IntelligentOptimizationThread(QThread):
            # ملاحظة: لا نسمّيه finished حتى لا يظلّل إشارة QThread الأصلية
            optimization_done = pyqtSignal(dict)
            progress = pyqtSignal(str)
            
            def __init__(self, optimizer, ai_engine):
                super().__init__()
                self.optimizer = optimizer
                self.ai_engine = ai_engine
            
            def run(self):
                # إرسال تحديثات التقدم
                self.progress.emit("تحليل حالة النظام...")
                
                # تحسين ذكي متقدم
                result = self.optimizer.optimize_battery(
                    use_cached_password=True, 
                    optimization_mode='intelligent'
                )
                
                self.progress.emit("اكتمل التحليل الذكي")
                self.optimization_done.emit(result)
        
        self.opt_thread = IntelligentOptimizationThread(self.optimizer, self.ai)
        self.opt_thread.optimization_done.connect(self._on_intelligent_optimization_complete)
        self.opt_thread.progress.connect(self._on_optimization_progress)
        self.opt_thread.start()
    
    def _on_optimization_progress(self, message):
        """تحديث تقدم التحسين الذكي"""
        self.optimize_status.setText(message)
    
    def _on_intelligent_optimization_complete(self, result):
        """معالجة نتيجة التحسين الذكي المتقدم"""
        self.optimize_button.setEnabled(True)
        self.optimize_button.setText("تحسين ذكي متقدم")
        
        if result['success']:
            power_saved = result.get('power_saved', 0)
            actions_count = len([a for a in result['actions'] if a.get('success', True)])
            intelligence_score = result.get('intelligence_score', 0)
            predicted_improvement = result.get('predicted_improvement', 0)
            ai_recommendations = result.get('ai_recommendations', [])
            personalized_actions = result.get('personalized_actions', [])
            
            # عرض النتائج الذكية
            status_text = f"تم التحسين الذكي بنجاح!\n"
            status_text += f"درجة الذكاء: {intelligence_score}% • تحسين متوقع: {predicted_improvement}%\n"
            status_text += f"توفير فعلي: ~{power_saved:.1f}% • تحسينات مطبقة: {actions_count}\n\n"
            
            # عرض التوصيات الذكية
            if ai_recommendations:
                status_text += "توصيات الذكاء الاصطناعي:\n"
                for rec in ai_recommendations[:3]:  # أول 3 توصيات
                    status_text += f"   • {rec}\n"
                status_text += "\n"
            
            # عرض التحسينات الرئيسية
            status_text += "التحسينات المطبقة:\n"
            for action in result['actions'][:5]:  # أول 5 تحسينات
                if action.get('success', True):
                    power_saved_action = action.get('power_saved', 0)
                    status_text += f"{action['name']}: {action['details']}"
                    if power_saved_action > 0:
                        status_text += f" (~{power_saved_action:.1f}%)"
                    status_text += "\n"
            
            # عرض التحسينات الشخصية
            if personalized_actions:
                status_text += "\n تحسينات شخصية:\n"
                for action in personalized_actions:
                    status_text += f"{action['name']}: {action['details']}\n"
            
            self.optimize_status.setText(status_text)
            self.optimize_status.setStyleSheet("font-size: 12px; color: #8b5cf6; background: transparent;")
            
            # تحديث شريط الحالة
            self.status_label.setText(f"تحسين ذكي مكتمل - توفير ~{power_saved:.1f}%")
            QTimer.singleShot(8000, lambda: self.status_label.setText("جاهز للعمل"))
            
            # تسجيل في السجل
            self.log_event(f"تحسين ذكي مكتمل - درجة الذكاء: {intelligence_score}% - توفير: {power_saved:.1f}%")
            
            # إرسال إشعار ذكي
            if power_saved > 10:
                self.send_notification(
                    "تحسين ذكي مكتمل!",
                    f"تم توفير {power_saved:.1f}% من الطاقة بفضل الذكاء الاصطناعي",
                    "success"
                )
        else:
            errors = result.get('errors', [])
            error_text = "حدث خطأ في التحسين الذكي"
            if errors:
                error_text += f"\nالأخطاء: {', '.join(errors[:2])}"
            
            self.optimize_status.setText(error_text)
            self.optimize_status.setStyleSheet("font-size: 12px; color: #ef4444; background: transparent;")
            self.status_label.setText("فشل التحسين الذكي")
            QTimer.singleShot(3000, lambda: self.status_label.setText("جاهز للعمل"))
    
    def _on_optimization_complete(self, result):
        """معالجة نتيجة التحسين العادي (للتوافق مع النسخة القديمة)"""
        self._on_intelligent_optimization_complete(result)
    
    def export_log(self):
        """تصدير السجل الكامل إلى ملف"""
        try:
            filename = f"battery_log_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            # قراءة السجل الكامل من الملف
            log_file = Path('battery_events.log')
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    full_log = f.read()
            else:
                full_log = self.events_log.toPlainText()
            
            # كتابة السجل المصدر
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("BatteryGuardAI - سجل الأحداث الكامل\n")
                f.write("=" * 70 + "\n")
                f.write(f"تاريخ التصدير: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"إجمالي السجلات: {len(full_log.split(chr(10)))}\n")
                f.write("=" * 70 + "\n\n")
                f.write(full_log)
                
                # إضافة إحصائيات
                f.write("\n\n" + "=" * 70 + "\n")
                f.write("إحصائيات النظام\n")
                f.write("=" * 70 + "\n")
                
                stats = self.ai.get_usage_statistics()
                f.write(f"عدد نقاط البيانات: {stats.get('total_records', 0)}\n")
                f.write(f"درجة الكفاءة: {stats.get('efficiency_score', 100)}%\n")
                f.write(f"معدل الاستنزاف: {stats.get('average_drain_rate', 0):.2f}%/دقيقة\n")
                f.write(f"معدل الشحن: {stats.get('average_charge_rate', 0):.2f}%/دقيقة\n")
                
                health = self.monitor.get_battery_health()
                soh_value = health.get('health_percentage')
                f.write(f"\nصحة البطارية: "
                        f"{soh_value if soh_value is not None else t('health.unknown')}\n")
                f.write(f"دورات الشحن: {health['cycle_count']}\n")
                f.write(f"السعة التصميمية: {health['design_capacity']:.0f} mWh\n")
                f.write(f"السعة الحالية: {health['full_capacity']:.0f} mWh\n")
            
            self.status_label.setText(f"تم تصدير السجل الكامل: {filename}")
            QTimer.singleShot(3000, lambda: self.status_label.setText("جاهز للعمل"))
            self.log_event(f"تم تصدير السجل الكامل إلى {filename}")
        except Exception as e:
            self.status_label.setText(f"خطأ في التصدير: {str(e)}")
            QTimer.singleShot(3000, lambda: self.status_label.setText("جاهز للعمل"))
            logger.error(f"خطأ في تصدير السجل: {e}")
    
    def _auto_save_data(self):
        """حفظ تلقائي دوري لبيانات التعلم فقط.
        ملاحظة: الإعدادات تُحفظ في QSettings عند الضغط على حفظ،
        ولم نعد نكتب battery_settings.json في مجلد العمل لأنه كان
        يتعارض مع ملف الإعدادات الرسمي في مجلد بيانات المستخدم."""
        try:
            self.ai.save_learning_data()
            logger.debug("تم الحفظ التلقائي لبيانات AI")
        except Exception as e:
            logger.error(f"خطأ في الحفظ التلقائي: {e}")
    
    def quit_application(self, interactive: bool = True):
        """
        إنهاء البرنامج بشكل كامل ونظيف.

        `interactive=False` يتخطّى نافذة التقدّم: عند `SIGTERM` من systemd أو
        تسجيل الخروج لا يوجد مستخدم يقرأها، ورسم نافذة أثناء إغلاق الجلسة قد
        يتعلّق حتى تنتهي مهلة النظام فتُقتل العملية بـ SIGKILL قبل التنظيف.
        """
        if getattr(self, '_quitting', False):
            return
        self._quitting = True

        progress = None
        if interactive:
            from PyQt6.QtCore import Qt as QtCore
            from PyQt6.QtWidgets import QProgressDialog

            progress = QProgressDialog("جارٍ إغلاق التطبيق...", None, 0, 5, self)
            progress.setWindowTitle("BatteryGuardAI")
            progress.setWindowModality(QtCore.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()

        def step(value: int, label: str = '') -> None:
            if progress is None:
                return
            progress.setValue(value)
            if label:
                progress.setLabelText(label)
            QApplication.processEvents()

        self.log_event("إيقاف البرنامج...")
        self._shutdown_sequence(step)

        if progress is not None:
            progress.close()
        QApplication.quit()

    def _shutdown_sequence(self, step=lambda value, label='': None):
        """
        خطوات الإغلاق النظيف بترتيبها الملزم.

        الترتيب ليس اعتباطياً: الحارس أولاً لأن الإفراج عن عملية معلّقة يجب أن
        يحدث قبل اختفاء من علّقها، ثم يتوقّف خيط المراقبة حتى لا يكتب أحد على
        ملفات التعلّم بعد حفظها، ثم يُحفظ التعلّم أخيراً.
        """
        step(1)
        for timer_name in ('auto_save_timer', 'ai_timer', 'uptime_timer',
                           'auto_opt_stats_timer'):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                timer.stop()

        step(2, "إيقاف الخدمات الخلفية...")
        # الحارس أولاً: أي عملية معلّقة يجب أن تُفرَج قبل أن يختفي من علّقها،
        # وإلا بقيت متوقفة بلا سبب مفهوم للمستخدم.
        try:
            self.guard_service.shutdown()
        except Exception as e:
            logger.error(f"إيقاف الحارس: {e}")
        try:
            self.auto_optimizer.auto_optimize_enabled = False
            self.auto_optimizer.stop()
        except Exception as e:
            logger.debug(f"إيقاف المحسن التلقائي: {e}")
        try:
            self.notification_manager.stop_all_reminders()
        except Exception as e:
            logger.debug(f"إيقاف التذكيرات: {e}")

        step(3, "إيقاف المراقبة...")
        if getattr(self, 'monitor_thread', None) is not None:
            self.monitor_thread.stop(timeout_ms=4000)

        step(4, "حفظ البيانات...")
        try:
            # `force`: الحفظ الدوري محدود بمهلة لتقليل الكتابة على القرص،
            # وعند الخروج لا يجوز أن تمنع تلك المهلة حفظ ساعة من التعلّم.
            self.ai.save_learning_data(force=True)
        except Exception as e:
            logger.error(f"حفظ نهائي: {e}")

        step(5)
        if getattr(self, 'tray', None) is not None:
            self.tray.hide()
        logger.info("اكتمل الإغلاق النظيف")
    
    def update_notification_settings(self):
        """تحديث إعدادات الإشعارات الذكية"""
        try:
            settings = self.get_current_settings()
            
            # تحديث إعدادات المدير
            if hasattr(self, 'notification_manager'):
                self.notification_manager.enabled = settings.get('enable_notifications', True)
                self.notification_manager.set_sound_settings(
                    settings.get('enable_sounds', True)
                )
                self.notification_manager.reminders_enabled = settings.get('enable_reminders', True)
                
                # تحديث حدود البطارية
                if 'battery_thresholds' in settings:
                    self.notification_manager.update_battery_thresholds(settings['battery_thresholds'])
                
                # تحديث إعدادات التنبيهات الذكية
                if 'smart_alerts' in settings:
                    for alert_type, enabled in settings['smart_alerts'].items():
                        self.notification_manager.toggle_smart_alert(alert_type, enabled)
                
                # تحديث فترات التذكير
                if 'reminder_intervals' in settings:
                    self.notification_manager.update_reminder_intervals(settings['reminder_intervals'])
                
                logger.info("تم تحديث إعدادات الإشعارات الذكية")
            
        except Exception as e:
            logger.error(f"خطأ في تحديث إعدادات الإشعارات: {e}")
    
    def check_battery_alerts(self, battery_status: Dict):
        """فحص وإرسال تنبيهات البطارية الذكية"""
        try:
            current_percent = battery_status['percent']
            is_charging = battery_status['is_charging']

            # بطارية لا تُبلّغ: لا تنبيهات مستوى شحن مبنية على قياس غير صالح
            if not battery_status.get('reporting', True):
                self._last_charging_state = is_charging
                return

            # الصحة قد تكون غير معروفة على عتاد لا يوفّرها؛ لا نخترع 100٪
            health_info = self.monitor.get_battery_health()
            battery_health = health_info.get('health_percentage')

            self.notification_manager.send_battery_threshold_alert(
                current_percent, is_charging,
                battery_health if battery_health is not None else 100
            )
            
            # فحص تغيير حالة الشاحن
            if hasattr(self, '_last_charging_state'):
                if self._last_charging_state != is_charging:
                    self.notification_manager.send_charger_status_alert(
                        self._last_charging_state, is_charging, current_percent
                    )
            
            self._last_charging_state = is_charging
            
            # تنبيهات الاستخدام الذكية
            usage_data = {
                'high_drain_detected': self._detect_high_drain(battery_status),
                # الحرارة غير المتاحة تُمرَّر صفراً لأن المستقبل يقارنها بعتبة
                'temperature': battery_status.get('temperature') or 0,
                'unhealthy_charging_pattern': self._detect_unhealthy_charging()
            }
            
            self.notification_manager.send_smart_usage_alert(usage_data)
            
            # تنبيهات الذكاء الاصطناعي
            if hasattr(self, 'ai') and self.ai:
                ai_alerts = self._get_ai_alerts(battery_status)
                for alert in ai_alerts:
                    self.notification_manager.send_ai_smart_alert(alert)
            
        except Exception as e:
            # الأثر الكامل مطلوب: خطأ يتكرر كل دورتين بلا موضع لا يُصلَح
            logger.error(f"خطأ في فحص تنبيهات البطارية: {e}", exc_info=True)

    def _detect_high_drain(self, battery_status: Dict) -> bool:
        """كشف الاستهلاك المرتفع"""
        try:
            power_draw = battery_status.get('power_draw', 0)
            # اعتبار الاستهلاك مرتفع إذا كان أكثر من 15W
            return power_draw > 15
        except:
            return False
    
    def _detect_unhealthy_charging(self) -> bool:
        """كشف أنماط الشحن غير الصحية"""
        try:
            if not hasattr(self, 'ai') or not self.ai:
                return False
            
            # استخدام الذكاء الاصطناعي لكشف الأنماط غير الصحية
            usage_stats = self.ai.get_usage_statistics()
            efficiency = usage_stats.get('efficiency_score', 100)
            
            # إذا كانت الكفاءة أقل من 70%، قد يكون هناك نمط غير صحي
            return efficiency < 70
        except:
            return False
    
    def _get_ai_alerts(self, battery_status: Dict) -> List[Dict]:
        """الحصول على تنبيهات الذكاء الاصطناعي"""
        alerts = []
        
        try:
            if not hasattr(self, 'ai') or not self.ai:
                return alerts
            
            # الحصول على توصيات التحسين
            recommendations = self.ai.get_optimization_recommendations(
                battery_status['percent'], 
                battery_status['is_charging']
            )
            
            # التوصيات المهيكلة تحمل شدّتها، فلا حاجة لاستنتاجها من نص الرسالة
            health = self.monitor.get_battery_health()
            floor, ceiling = self.current_window()
            for item in self.ai.get_advice(
                    battery_status, health, floor, ceiling,
                    control_available=self.monitor.capability.can_control,
                    control_active=self.monitor.control_verified):
                if item.severity in ('critical', 'warning'):
                    alerts.append({
                        'type': item.id,
                        'message': t(item.key, **item.params),
                        'confidence': 90 if item.evidence == 'measured' else 85,
                    })
            
            # فحص تدهور البطارية
            usage_stats = self.ai.get_usage_statistics()
            health_score = usage_stats.get('health_score', 100)
            
            if health_score < 80:
                alerts.append({
                    'type': 'battery_degradation',
                    'message': f'تدهور في صحة البطارية مكتشف (درجة الصحة: {health_score}%)',
                    'confidence': 90
                })
            
            # اقتراح وقت الشحن الأمثل
            current_hour = datetime.now().hour
            optimal_times = usage_stats.get('optimal_charge_times', [])
            
            if current_hour in optimal_times and not battery_status['is_charging']:
                alerts.append({
                    'type': 'optimal_charge_time',
                    'message': 'الآن وقت مثالي للشحن بناءً على أنماط استخدامك',
                    'confidence': 80
                })
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على تنبيهات AI: {e}")
        
        return alerts