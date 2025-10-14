#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""النافذة الرئيسية للتطبيق"""

import sys
import logging
import statistics
from typing import Dict, List
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTabWidget, QSystemTrayIcon, QMenu, QApplication, QFrame)
from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtGui import QAction
import json
from pathlib import Path

from battery_monitor import BatteryMonitor
from battery_ai import BatteryAI
from notification_manager import SmartNotificationManager
from monitor_thread import MonitorThread
from ui_components_fixed import StatusTab, SettingsTab, AITab, StatsTab
from tray_icon import BatteryTrayIcon
from battery_optimizer import BatteryOptimizer
from permission_manager import PermissionManager
from autostart_manager import autostart_manager
from auto_optimizer import AutoOptimizer

logger = logging.getLogger('BatteryGuard')


class ModernUI(QMainWindow):
    """الواجهة الرسومية العصرية"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings('BatteryGuard', 'Pro')
        self.permission_manager = PermissionManager()
        self.monitor = BatteryMonitor()
        self.ai = BatteryAI()
        self.notification_manager = SmartNotificationManager()
        self.optimizer = BatteryOptimizer(ai_engine=self.ai)
        self.auto_optimizer = AutoOptimizer(self.optimizer, self.ai)
        self.is_dark_mode = True
        
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
        
    def init_ui(self):
        """تهيئة الواجهة الرسومية"""
        self.setWindowTitle("BatteryGuard Pro")
        self.setMinimumSize(900, 650)
        self.resize(1100, 800)
        
        # تعيين أيقونة النافذة
        from PyQt6.QtGui import QIcon
        icon_path = Path('assets/logo.png')
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        self.setStyleSheet(self.get_modern_stylesheet())
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # شريط العنوان المحسّن
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e3a8a, stop:0.5 #2563eb, stop:1 #3b82f6);
                border-radius: 0;
            }
        """)
        header.setFixedHeight(90)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(35, 0, 35, 0)
        
        # أيقونة وعنوان
        title_container = QHBoxLayout()
        title_container.setSpacing(15)
        
        icon_label = QLabel("⚡")
        icon_label.setStyleSheet("font-size: 42px; background: transparent; color: #fbbf24;")
        title_container.addWidget(icon_label)
        
        text_container = QVBoxLayout()
        text_container.setSpacing(2)
        title = QLabel("BatteryGuard Pro")
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #ffffff; background: transparent;")
        subtitle = QLabel("نظام إدارة البطارية الذكي")
        subtitle.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.8); background: transparent;")
        title_container.addWidget(title)
        title_container.addWidget(subtitle)
        header_layout.addLayout(title_container)
        header_layout.addStretch()
        

        
        main_layout.addWidget(header)
        
        # حاوية التبويبات المحسّنة
        tabs_container = QWidget()
        tabs_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #0f0f1e);
                color: #ffffff;
            }
        """)
        tabs_layout = QVBoxLayout(tabs_container)
        tabs_layout.setContentsMargins(25, 25, 25, 25)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
                margin-top: 5px;
            }
            QTabBar::tab {
                background: rgba(59, 130, 246, 0.08);
                color: #94a3b8;
                border: 2px solid transparent;
                padding: 16px 32px;
                margin-right: 6px;
                border-radius: 14px;
                font-size: 15px;
                font-weight: 700;
                min-width: 110px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: #ffffff;
                border: 2px solid rgba(59, 130, 246, 0.5);
            }
            QTabBar::tab:hover:!selected {
                background: rgba(59, 130, 246, 0.15);
                color: #e2e8f0;
                border: 2px solid rgba(59, 130, 246, 0.3);
            }
        """)
        
        self.status_tab = StatusTab.create(self)
        self.tabs.addTab(self.status_tab, "📊 الحالة")
        
        self.settings_tab = SettingsTab.create(self)
        self.tabs.addTab(self.settings_tab, "⚙️ الإعدادات")
        
        self.ai_tab = AITab.create(self)
        self.tabs.addTab(self.ai_tab, "🤖 الذكاء الاصطناعي")
        
        self.stats_tab = StatsTab.create(self)
        self.tabs.addTab(self.stats_tab, "📈 الإحصائيات")
        
        tabs_layout.addWidget(self.tabs)
        main_layout.addWidget(tabs_container)
        
        # شريط الحالة المحسّن
        status_bar = QWidget()
        status_bar.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0f172a, stop:1 #1e293b);
                border-top: 2px solid #334155;
            }
        """)
        status_bar.setFixedHeight(45)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(25, 0, 25, 0)
        
        # أيقونة الحالة
        status_icon = QLabel("●")
        status_icon.setStyleSheet("color: #10b981; font-size: 16px; background: transparent;")
        status_layout.addWidget(status_icon)
        
        self.status_label = QLabel("جاهز للعمل")
        self.status_label.setStyleSheet("""
            color: #ffffff;
            font-size: 13px;
            background: transparent;
            font-weight: 600;
        """)
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # معلومات إضافية
        self.uptime_label = QLabel("وقت التشغيل: 0د")
        self.uptime_label.setStyleSheet("color: #64748b; font-size: 11px; background: transparent;")
        status_layout.addWidget(self.uptime_label)
        
        separator = QLabel("•")
        separator.setStyleSheet("color: #475569; font-size: 11px; background: transparent; padding: 0 8px;")
        status_layout.addWidget(separator)
        
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet("color: #64748b; font-size: 11px; background: transparent; font-weight: 600;")
        status_layout.addWidget(version_label)
        
        main_layout.addWidget(status_bar)
        
        # مؤقت لتحديث وقت التشغيل
        self.start_time = datetime.now()
        self.uptime_timer = QTimer()
        self.uptime_timer.timeout.connect(self._update_uptime)
        self.uptime_timer.start(60000)  # كل دقيقة
        
        self.tray = BatteryTrayIcon(self)
    
    def get_modern_stylesheet(self) -> str:
        """الحصول على تنسيق عصري للواجهة"""
        return """
                QMainWindow { 
                    background-color: #0f172a;
                    color: #ffffff;
                }
                QWidget { 
                    background-color: #1a1a2e;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 2px solid rgba(59, 130, 246, 0.2);
                    border-radius: 18px;
                    margin-top: 22px;
                    padding-top: 32px;
                    padding-bottom: 22px;
                    padding-left: 22px;
                    padding-right: 22px;
                    font-weight: 700;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(30, 41, 59, 0.95), stop:1 rgba(15, 23, 42, 0.9));
                    color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    left: 22px;
                    top: 12px;
                    padding: 0 12px;
                    font-size: 17px;
                    color: #ffffff;
                    font-weight: 800;
                    letter-spacing: 0.5px;
                }
                QLabel { 
                    color: #ffffff;
                }
                QLabel[objectName^="value_"] {
                    color: #ffffff;
                    font-weight: 700;
                }
                QCheckBox {
                    spacing: 10px;
                    font-size: 14px;
                    padding: 10px;
                    color: #ffffff;
                    background: transparent;
                }
                QCheckBox::indicator {
                    width: 22px;
                    height: 22px;
                    border-radius: 6px;
                    border: 2px solid #475569;
                    background-color: #1e293b;
                }
                QCheckBox::indicator:checked {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #3b82f6, stop:1 #2563eb);
                    border-color: #3b82f6;
                }
                QCheckBox::indicator:hover {
                    border-color: #3b82f6;
                }
                QSpinBox {
                    padding: 10px 12px;
                    border: 2px solid #334155;
                    border-radius: 8px;
                    background-color: #1e293b;
                    color: #ffffff;
                    font-size: 14px;
                    min-width: 90px;
                }
                QSpinBox:focus {
                    border-color: #3b82f6;
                    background-color: #0f172a;
                }
                QSpinBox::up-button {
                    subcontrol-origin: border;
                    subcontrol-position: top right;
                    background: #334155;
                    border-radius: 4px;
                    width: 20px;
                    border-left: 1px solid #475569;
                }
                QSpinBox::down-button {
                    subcontrol-origin: border;
                    subcontrol-position: bottom right;
                    background: #334155;
                    border-radius: 4px;
                    width: 20px;
                    border-left: 1px solid #475569;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background: #3b82f6;
                }
                QSpinBox::up-arrow {
                    image: none;
                    border: 2px solid #ffffff;
                    width: 6px;
                    height: 6px;
                    border-bottom: none;
                    border-right: none;
                }
                QSpinBox::down-arrow {
                    image: none;
                    border: 2px solid #ffffff;
                    width: 6px;
                    height: 6px;
                    border-top: none;
                    border-left: none;
                }
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3b82f6, stop:1 #2563eb);
                    color: #ffffff;
                    border: none;
                    border-radius: 12px;
                    padding: 14px 28px;
                    font-size: 15px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2563eb, stop:1 #1d4ed8);
                    padding: 14px 30px;
                }
                QPushButton:pressed {
                    background: #1e40af;
                    padding: 14px 26px;
                }
                QSlider::groove:horizontal {
                    border: none;
                    height: 6px;
                    background: #334155;
                    border-radius: 3px;
                }
                QSlider::handle:horizontal {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #3b82f6, stop:1 #2563eb);
                    border: 2px solid #1e40af;
                    width: 18px;
                    height: 18px;
                    margin: -7px 0;
                    border-radius: 9px;
                }
                QSlider::handle:horizontal:hover {
                    background: #60a5fa;
                    border-color: #3b82f6;
                }
                QScrollBar:vertical {
                    background: #1e293b;
                    width: 10px;
                    border-radius: 5px;
                    margin: 0;
                }
                QScrollBar::handle:vertical {
                    background: #475569;
                    border-radius: 5px;
                    min-height: 30px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #64748b;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
        """
    
    def show_window(self):
        """عرض النافذة وتفعيلها"""
        self.show()
        self.activateWindow()
        self.raise_()
    
    def start_monitoring(self):
        """بدء المراقبة الخلفية"""
        self.monitor_thread = MonitorThread(
            self.monitor,
            self.ai,
            self.get_current_settings()
        )
        
        self.monitor_thread.battery_updated.connect(self.update_battery_display)
        self.monitor_thread.notification_requested.connect(self.send_notification)
        
        self.monitor_thread.start()
        
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
        """تحديث عرض حالة البطارية مع التنبيهات الذكية"""
        percent = battery_status['percent']
        is_charging = battery_status['is_charging']
        
        # فحص وإرسال التنبيهات الذكية
        self.check_battery_alerts(battery_status)
        
        # تحديث ويدجت البطارية المتحرك
        self.battery_widget.set_battery_level(percent, is_charging)
        
        # تحديث البطارية في الهيدر
        if hasattr(self, 'header_battery_label'):
            self.header_battery_percent = percent
            self.header_battery_charging = is_charging
            
            # تحديث النص
            status_text = "⚡" if is_charging else ""
            self.header_battery_label.setText(f"{percent}% {status_text}")
            
            # تغيير اللون حسب المستوى
            if percent >= 80:
                color = "#10b981"
            elif percent >= 40:
                color = "#3b82f6"
            elif percent >= 20:
                color = "#f59e0b"
            else:
                color = "#ef4444"
            
            self.header_battery_label.setStyleSheet(f"""
                font-size: 18px;
                font-weight: 800;
                color: {color};
                background: transparent;
            """)
            
            # إعادة رسم البطارية
            if hasattr(self, 'header_battery_widget'):
                self.header_battery_widget.update()
        
        # تحديث أيقونة الصينية مع الصحة
        health_info = self.monitor.get_battery_health()
        health_percent = health_info['health_percentage']
        self.tray.update_icon(percent, is_charging, health_percent)
        
        if is_charging:
            self.charging_status.setText("⚡ متصل بالشاحن - جارٍ الشحن")
            self.charging_status.setStyleSheet("""
                font-size: 16px;
                color: #10b981;
                margin-top: 15px;
                background: transparent;
                font-weight: 600;
            """)
        else:
            self.charging_status.setText("🔋 يعمل على البطارية")
            self.charging_status.setStyleSheet("""
                font-size: 16px;
                color: #ffffff;
                margin-top: 15px;
                background: transparent;
                font-weight: 600;
            """)
        
        # تحديث الوقت المتبقي
        time_left = battery_status.get('time_left')
        prediction = None
        
        if time_left and time_left > 0:
            hours = time_left // 3600
            minutes = (time_left % 3600) // 60
            time_text = f"{hours}س {minutes}د"
            self.time_remaining_label.setText(time_text)
            self.time_remaining_label.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    color: #10b981;
                    background: transparent;
                    font-weight: 700;
                }
            """)
            # تحديث الأيقونة
            self.tray.update_time_remaining(time_text)
        else:
            prediction = self.ai.predict_time_remaining(percent, is_charging)
            if prediction:
                self.time_remaining_label.setText(prediction)
                # تحديث الأيقونة
                self.tray.update_time_remaining(prediction)
                self.time_remaining_label.setStyleSheet("""
                    QLabel {
                        font-size: 18px;
                        color: #3b82f6;
                        background: transparent;
                        font-weight: 700;
                    }
                """)
            else:
                self.time_remaining_label.setText("جارٍ الحساب..." if is_charging else "غير محدد")
                self.time_remaining_label.setStyleSheet("""
                    QLabel {
                        font-size: 18px;
                        color: #ffffff;
                        background: transparent;
                        font-weight: 700;
                    }
                """)
        
        # تحديث معلومات الصحة
        health_info = self.monitor.get_battery_health()
        health_percent = health_info['health_percentage']
        self.health_label.setText(f"{health_percent}%")
        
        # لون حسب الصحة
        if health_percent >= 80:
            health_color = "#10b981"
        elif health_percent >= 60:
            health_color = "#3b82f6"
        elif health_percent >= 40:
            health_color = "#f59e0b"
        else:
            health_color = "#ef4444"
        
        self.health_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                color: {health_color};
                background: transparent;
                font-weight: 700;
            }}
        """)
        
        cycle_count = health_info['cycle_count']
        self.cycle_count_label.setText(f"{cycle_count} دورة")
        self.cycle_count_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                color: #ffffff;
                background: transparent;
                font-weight: 700;
            }
        """)
        
        # تحديث استهلاك الطاقة
        power_draw = battery_status.get('power_draw', 0)
        
        if power_draw > 0.1:
            self.power_draw_label.setText(f"{power_draw:.1f}W")
            power_color = "#f59e0b"
        elif is_charging:
            self.power_draw_label.setText("جارٍ الشحن")
            power_color = "#10b981"
        else:
            self.power_draw_label.setText("منخفض")
            power_color = "#ffffff"
        
        self.power_draw_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                color: {power_color};
                background: transparent;
                font-weight: 700;
            }}
        """)
        
        # تحديث تبويب الإحصائيات
        self.health_progress.setValue(health_info['health_percentage'])
        # تحديث معلومات الصحة في تبويب الإحصائيات
        self.design_capacity_label.setText(f"{health_info['design_capacity']:.0f} mWh")
        self.current_capacity_label.setText(f"{health_info['full_capacity']:.0f} mWh")
        wear_level = 100 - health_info['health_percentage']
        self.wear_level_label.setText(f"{wear_level}%")
        
        # تحديث حالة الصحة
        if hasattr(self, 'health_status_label'):
            if health_info['health_percentage'] >= 90:
                self.health_status_label.setText("حالة ممتازة 🌟")
                self.health_status_label.setStyleSheet("font-size: 13px; color: #10b981; font-weight: 700; background: transparent;")
            elif health_info['health_percentage'] >= 80:
                self.health_status_label.setText("حالة جيدة جداً ✅")
                self.health_status_label.setStyleSheet("font-size: 13px; color: #3b82f6; font-weight: 700; background: transparent;")
            elif health_info['health_percentage'] >= 70:
                self.health_status_label.setText("حالة جيدة ⚡")
                self.health_status_label.setStyleSheet("font-size: 13px; color: #f59e0b; font-weight: 700; background: transparent;")
            else:
                self.health_status_label.setText("يحتاج صيانة ⚠️")
                self.health_status_label.setStyleSheet("font-size: 13px; color: #ef4444; font-weight: 700; background: transparent;")
        
        # تحديث دورات الشحن
        if hasattr(self, 'cycle_count_stats_label'):
            self.cycle_count_stats_label.setText(f"{health_info['cycle_count']}")
        
        # حساب وتحديث الإحصائيات المتقدمة
        self._update_advanced_stats()
    
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
        """تحديث تحليل الذكاء الاصطناعي المتقدم"""
        battery_status = self.monitor.get_battery_status()
        if not battery_status['available']:
            return
        
        # الحصول على التوصيات الذكية
        recommendations = self.ai.get_smart_recommendations(
            battery_status['percent'],
            battery_status['is_charging']
        )
        
        # إرسال توصية ذكية إذا كانت مهمة
        if recommendations and hasattr(self, 'notification_manager'):
            first_rec = recommendations[0]
            if '🚨' in first_rec or '⚠️' in first_rec:
                self.notification_manager.send_ai_recommendation(first_rec, priority=8)
        
        if recommendations:
            text = "🎯 التوصيات الذكية:\n\n"
            for i, rec in enumerate(recommendations, 1):
                text += f"{i}. {rec}\n\n"
            self.recommendations_text.setPlainText(text)
        else:
            self.recommendations_text.setPlainText("جارٍ تحليل أنماط الاستخدام...\nسيتم عرض التوصيات بعد جمع بيانات كافية.")
        
        # التنبؤ بالوقت المتبقي
        prediction = self.ai.predict_time_remaining(
            battery_status['percent'],
            battery_status['is_charging']
        )
        
        # الحصول على الإحصائيات المتقدمة
        stats = self.ai.get_usage_statistics()
        
        # تحديث بطاقات الإحصائيات
        self.data_points_label.setText(f"{stats.get('total_records', 0)}")
        self.patterns_found_label.setText(f"{stats.get('patterns_found', 0)}")
        
        efficiency = stats.get('efficiency_score', 100)
        self.efficiency_score_label.setText(f"{efficiency}%")
        
        # الإحصائيات الجديدة
        if hasattr(self, 'health_score_label'):
            health = stats.get('health_score', 100)
            self.health_score_label.setText(f"{health}%")
        
        if hasattr(self, 'drain_rate_label'):
            drain_rate = stats.get('average_drain_rate', 0)
            self.drain_rate_label.setText(f"{drain_rate:.2f}")
        
        if hasattr(self, 'charge_rate_label'):
            charge_rate = stats.get('average_charge_rate', 0)
            self.charge_rate_label.setText(f"{charge_rate:.2f}")
        
        # إحصائيات التعلم المتقدمة
        if hasattr(self, 'learning_iterations_label'):
            iterations = self.ai.learning_data.get('learning_iterations', 0)
            self.learning_iterations_label.setText(f"{iterations}")
        
        if hasattr(self, 'prediction_accuracy_label'):
            if self.ai.prediction_accuracy:
                avg_accuracy = statistics.mean(self.ai.prediction_accuracy[-20:])
                self.prediction_accuracy_label.setText(f"{int(avg_accuracy)}%")
            else:
                self.prediction_accuracy_label.setText("جارٍ التعلم...")
        
        if hasattr(self, 'confidence_label'):
            confidence = self.ai._calculate_confidence()
            self.confidence_label.setText(f"{confidence}%")
        
        # الإحصائيات المتقدمة الجديدة
        if hasattr(self, 'learning_progress_label'):
            progress = stats.get('learning_progress', 0)
            self.learning_progress_label.setText(f"{progress}%")
        
        if hasattr(self, 'ai_maturity_label'):
            maturity = stats.get('ai_maturity_level', 'مبتدئ')
            self.ai_maturity_label.setText(maturity)
        
        if hasattr(self, 'personalization_label'):
            personalization = stats.get('personalization_score', 0)
            self.personalization_label.setText(f"{personalization}%")
        
        # تحديث نص التنبؤات المفصل
        if hasattr(self, 'prediction_text'):
            prediction_text = ""
            
            if prediction:
                prediction_text += f"⏱️ الوقت المتبقي: {prediction}\n\n"
            
            drain_rate = stats.get('average_drain_rate', 0)
            charge_rate = stats.get('average_charge_rate', 0)
            peak_drain = stats.get('peak_drain_rate', 0)
            
            if drain_rate > 0:
                prediction_text += f"📉 معدل الاستنزاف: {drain_rate:.2f}%/د"
                if peak_drain > 0:
                    prediction_text += f" (الذروة: {peak_drain:.2f}%/د)"
                prediction_text += "\n"
            
            if charge_rate > 0:
                prediction_text += f"📈 معدل الشحن: {charge_rate:.2f}%/د\n"
            
            heavy_hours = stats.get('heavy_usage_hours', [])
            if heavy_hours:
                prediction_text += f"\n🕐 ساعات الاستخدام المكثف:\n   {', '.join(f'{h}:00' for h in heavy_hours)}\n"
            
            optimal_times = stats.get('optimal_charge_times', [])
            if optimal_times:
                prediction_text += f"\n⚡ أوقات الشحن المثالية:\n   {', '.join(f'{h}:00' for h in optimal_times)}\n"
            
            cycles = stats.get('charge_cycle_count', 0)
            if cycles > 0:
                prediction_text += f"\n🔄 دورات الشحن: {cycles}"
                avg_duration = stats.get('avg_charge_duration', 0)
                if avg_duration > 0:
                    prediction_text += f" (~{int(avg_duration)} دقيقة/دورة)"
            
            power_draw = stats.get('average_power_draw', 0)
            if power_draw > 0:
                prediction_text += f"\n⚡ متوسط استهلاك الطاقة: {power_draw:.1f}W"
                peak_power = stats.get('peak_power_draw', 0)
                if peak_power > 0:
                    prediction_text += f" (الذروة: {peak_power:.1f}W)"
            
            if prediction_text:
                self.prediction_text.setText(prediction_text)
            else:
                self.prediction_text.setText("جارٍ جمع البيانات للتنبؤ الدقيق...")
    
    def _sync_permissions(self):
        """مزامنة الصلاحيات مع جميع المكونات"""
        if self.permission_manager.sudo_password:
            if self.monitor.charge_controller:
                self.monitor.charge_controller.sudo_password = self.permission_manager.sudo_password
            self.optimizer.set_sudo_password(self.permission_manager.sudo_password)
            logger.info("✅ تم مزامنة الصلاحيات مع جميع المكونات")
    
    def save_all_settings(self):
        """حفظ جميع الإعدادات (موحد)"""
        # حفظ إعدادات الإشعارات
        settings = self.get_current_settings()
        for key, value in settings.items():
            self.settings.setValue(key, value)
        
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
                    self.log_event(f"✅ تم تفعيل التحكم التلقائي: {min_charge}%-{max_charge}%")
                    self.status_label.setText("✅ تم حفظ الإعدادات وتفعيل التحكم")
                else:
                    self.log_event("⚠️ تم حفظ الإعدادات - سيتم استخدام الإشعارات فقط")
                    self.status_label.setText("⚠️ تم الحفظ - إشعارات فقط")
            else:
                # إيقاف التحكم
                self.monitor.disable_charge_control()
                self.log_event("تم إيقاف التحكم التلقائي")
                self.status_label.setText("✅ تم حفظ الإعدادات")
        else:
            self.status_label.setText("✅ تم حفظ الإعدادات")
        
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
        
        return settings
    
    def on_autostart_changed(self, state):
        """معالجة تغيير حالة التشغيل التلقائي"""
        try:
            if state == 2:  # Qt.CheckState.Checked
                success, message = autostart_manager.enable()
                if success:
                    self.log_event(f"✅ {message}")
                    logger.info("✅ تم تفعيل التشغيل التلقائي")
                else:
                    self.log_event(f"❌ فشل التفعيل: {message}")
                    logger.error(f"فشل تفعيل التشغيل التلقائي: {message}")
                    # إلغاء التحديد إذا فشل
                    self.start_on_boot.blockSignals(True)
                    self.start_on_boot.setChecked(False)
                    self.start_on_boot.blockSignals(False)
            else:
                success, message = autostart_manager.disable()
                if success:
                    self.log_event(f"✅ {message}")
                    logger.info("✅ تم إلغاء التشغيل التلقائي")
                else:
                    self.log_event(f"❌ فشل الإلغاء: {message}")
                    logger.error(f"فشل إلغاء التشغيل التلقائي: {message}")
        except Exception as e:
            self.log_event(f"❌ خطأ في التشغيل التلقائي: {e}")
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
                
                self.log_event(f"✅ تم تفعيل التحسين التلقائي - الوضع: {mode}")
                logger.info(f"✅ تم تفعيل التحسين التلقائي - الوضع: {mode}, الفترة: {interval}ث")
                
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
                
                self.log_event("✅ تم إيقاف التحسين التلقائي")
                logger.info("✅ تم إيقاف التحسين التلقائي")
                
        except Exception as e:
            self.log_event(f"❌ خطأ في التحسين التلقائي: {e}")
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
                    self.log_event(f"⚠️ النظام يحتاج تحسين عاجل - الأولوية: {priority}/10, الصحة: {health}%")
                elif priority >= 4:
                    self.log_event(f"📊 النظام يحتاج تحسين - الأولوية: {priority}/10, الصحة: {health}%")
            
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
                self.minimize_to_tray.setChecked(self.settings.value('minimize_to_tray', True, type=bool))
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
        current_text = self.events_log.toPlainText()
        if current_text:
            self.events_log.setPlainText(log_message + "\n" + current_text)
        else:
            self.events_log.setPlainText(log_message)
        
        # الاحتفاظ بآخر 500 سطر فقط
        lines = self.events_log.toPlainText().split('\n')
        if len(lines) > 500:
            self.events_log.setPlainText('\n'.join(lines[:500]))
        
        # حفظ السجل في ملف
        self._save_log_to_file(log_message)
        
        logger.info(message)
    
    def _save_log_to_file(self, log_message: str):
        """حفظ السجل في ملف"""
        try:
            log_file = Path('battery_events.log')
            
            # قراءة السجل الحالي
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            # إضافة السجل الجديد في البداية
            lines.insert(0, log_message + '\n')
            
            # الاحتفاظ بآخر 1000 سطر
            if len(lines) > 1000:
                lines = lines[:1000]
            
            # حفظ السجل
            with open(log_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception as e:
            logger.error(f"خطأ في حفظ السجل: {e}")
    
    def _load_log_from_file(self):
        """تحميل السجل من الملف"""
        try:
            log_file = Path('battery_events.log')
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # عرض آخر 100 سطر فقط
                    self.events_log.setPlainText(''.join(lines[:100]))
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
                log_file = Path('battery_events.log')
                if log_file.exists():
                    log_file.unlink()
                self.log_event("✅ تم مسح السجل بنجاح")
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
                ai_file = Path('battery_ai_data.json')
                if ai_file.exists():
                    ai_file.unlink()
                from battery_ai import BatteryAI
                self.ai = BatteryAI()
                
                # تحديث الواجهة
                if hasattr(self, 'recommendations_text'):
                    self.recommendations_text.setPlainText("تم إعادة التعيين. جارٍ التعلم من جديد...")
                if hasattr(self, 'prediction_text'):
                    self.prediction_text.setText("تم إعادة التعيين. جارٍ جمع بيانات جديدة...")
                
                self.log_event("✅ تم إعادة تعيين بيانات الذكاء الاصطناعي بنجاح")
                logger.info("تم إعادة تعيين بيانات AI")
                QMessageBox.information(self, "نجح", "تم إعادة تعيين بيانات الذكاء الاصطناعي.\nسيبدأ التعلم من جديد.")
            except Exception as e:
                logger.error(f"خطأ في إعادة تعيين AI: {e}")
                QMessageBox.warning(self, "خطأ", f"فشل إعادة تعيين AI: {e}")
            try:
                # حذف ملف بيانات AI
                ai_file = Path('battery_ai_data.json')
                if ai_file.exists():
                    ai_file.unlink()
                
                # إعادة تهيئة AI
                from battery_ai import BatteryAI
                self.ai = BatteryAI()
                
                # تحديث الواجهة
                if hasattr(self, 'recommendations_text'):
                    self.recommendations_text.setPlainText("تم إعادة التعيين. جارٍ التعلم من جديد...")
                if hasattr(self, 'prediction_text'):
                    self.prediction_text.setText("تم إعادة التعيين. جارٍ جمع بيانات جديدة...")
                
                self.log_event("✅ تم إعادة تعيين بيانات الذكاء الاصطناعي بنجاح")
                logger.info("تم إعادة تعيين بيانات AI")
                
                QMessageBox.information(
                    self,
                    "نجح",
                    "تم إعادة تعيين بيانات الذكاء الاصطناعي.\nسيبدأ التعلم من جديد."
                )
            except Exception as e:
                logger.error(f"خطأ في إعادة تعيين AI: {e}")
                QMessageBox.warning(self, "خطأ", f"فشل إعادة تعيين AI: {e}")
    
    def closeEvent(self, event):
        """معالجة إغلاق النافذة"""
        if self.minimize_to_tray.isChecked():
            event.ignore()
            self.hide()
            self.tray.show_message(
                "BatteryGuard Pro",
                "البرنامج لا يزال يعمل في الخلفية"
            )
        else:
            self.quit_application()
    
    def _update_advanced_stats(self):
        """تحديث الإحصائيات المتقدمة"""
        if not hasattr(self, 'total_charge_time_label'):
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
        self.optimize_button.setText("🤖 تحليل ذكي جارٍ...")
        self.optimize_status.setText("🧠 الذكاء الاصطناعي يحلل أنماط الاستخدام ويحدد أفضل التحسينات...")
        
        # تشغيل التحسين الذكي في خيط منفصل
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class IntelligentOptimizationThread(QThread):
            finished = pyqtSignal(dict)
            progress = pyqtSignal(str)
            
            def __init__(self, optimizer, ai_engine):
                super().__init__()
                self.optimizer = optimizer
                self.ai_engine = ai_engine
            
            def run(self):
                # إرسال تحديثات التقدم
                self.progress.emit("🔍 تحليل حالة النظام...")
                
                # تحسين ذكي متقدم
                result = self.optimizer.optimize_battery(
                    use_cached_password=True, 
                    optimization_mode='intelligent'
                )
                
                self.progress.emit("✅ اكتمل التحليل الذكي")
                self.finished.emit(result)
        
        self.opt_thread = IntelligentOptimizationThread(self.optimizer, self.ai)
        self.opt_thread.finished.connect(self._on_intelligent_optimization_complete)
        self.opt_thread.progress.connect(self._on_optimization_progress)
        self.opt_thread.start()
    
    def _on_optimization_progress(self, message):
        """تحديث تقدم التحسين الذكي"""
        self.optimize_status.setText(message)
    
    def _on_intelligent_optimization_complete(self, result):
        """معالجة نتيجة التحسين الذكي المتقدم"""
        self.optimize_button.setEnabled(True)
        self.optimize_button.setText("🤖 تحسين ذكي متقدم")
        
        if result['success']:
            power_saved = result.get('power_saved', 0)
            actions_count = len([a for a in result['actions'] if a.get('success', True)])
            intelligence_score = result.get('intelligence_score', 0)
            predicted_improvement = result.get('predicted_improvement', 0)
            ai_recommendations = result.get('ai_recommendations', [])
            personalized_actions = result.get('personalized_actions', [])
            
            # عرض النتائج الذكية
            status_text = f"🤖 تم التحسين الذكي بنجاح!\n"
            status_text += f"🎯 درجة الذكاء: {intelligence_score}% • 📊 تحسين متوقع: {predicted_improvement}%\n"
            status_text += f"⚡ توفير فعلي: ~{power_saved:.1f}% • 🔧 تحسينات مطبقة: {actions_count}\n\n"
            
            # عرض التوصيات الذكية
            if ai_recommendations:
                status_text += "🧠 توصيات الذكاء الاصطناعي:\n"
                for rec in ai_recommendations[:3]:  # أول 3 توصيات
                    status_text += f"   • {rec}\n"
                status_text += "\n"
            
            # عرض التحسينات الرئيسية
            status_text += "🚀 التحسينات المطبقة:\n"
            for action in result['actions'][:5]:  # أول 5 تحسينات
                if action.get('success', True):
                    power_saved_action = action.get('power_saved', 0)
                    status_text += f"   ✓ {action['name']}: {action['details']}"
                    if power_saved_action > 0:
                        status_text += f" (~{power_saved_action:.1f}%)"
                    status_text += "\n"
            
            # عرض التحسينات الشخصية
            if personalized_actions:
                status_text += "\n🎯 تحسينات شخصية:\n"
                for action in personalized_actions:
                    status_text += f"   ⭐ {action['name']}: {action['details']}\n"
            
            self.optimize_status.setText(status_text)
            self.optimize_status.setStyleSheet("font-size: 12px; color: #8b5cf6; background: transparent;")
            
            # تحديث شريط الحالة
            self.status_label.setText(f"🤖 تحسين ذكي مكتمل - توفير ~{power_saved:.1f}%")
            QTimer.singleShot(8000, lambda: self.status_label.setText("🟢 جاهز للعمل"))
            
            # تسجيل في السجل
            self.log_event(f"🤖 تحسين ذكي مكتمل - درجة الذكاء: {intelligence_score}% - توفير: {power_saved:.1f}%")
            
            # إرسال إشعار ذكي
            if power_saved > 10:
                self.send_notification(
                    "تحسين ذكي مكتمل! 🤖",
                    f"تم توفير {power_saved:.1f}% من الطاقة بفضل الذكاء الاصطناعي",
                    "success"
                )
        else:
            errors = result.get('errors', [])
            error_text = "❌ حدث خطأ في التحسين الذكي"
            if errors:
                error_text += f"\nالأخطاء: {', '.join(errors[:2])}"
            
            self.optimize_status.setText(error_text)
            self.optimize_status.setStyleSheet("font-size: 12px; color: #ef4444; background: transparent;")
            self.status_label.setText("❌ فشل التحسين الذكي")
            QTimer.singleShot(3000, lambda: self.status_label.setText("🟢 جاهز للعمل"))
    
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
                f.write("BatteryGuard Pro - سجل الأحداث الكامل\n")
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
                f.write(f"\nصحة البطارية: {health['health_percentage']}%\n")
                f.write(f"دورات الشحن: {health['cycle_count']}\n")
                f.write(f"السعة التصميمية: {health['design_capacity']:.0f} mWh\n")
                f.write(f"السعة الحالية: {health['full_capacity']:.0f} mWh\n")
            
            self.status_label.setText(f"✅ تم تصدير السجل الكامل: {filename}")
            QTimer.singleShot(3000, lambda: self.status_label.setText("🟢 جاهز للعمل"))
            self.log_event(f"تم تصدير السجل الكامل إلى {filename}")
        except Exception as e:
            self.status_label.setText(f"❌ خطأ في التصدير: {str(e)}")
            QTimer.singleShot(3000, lambda: self.status_label.setText("🟢 جاهز للعمل"))
            logger.error(f"خطأ في تصدير السجل: {e}")
    
    def _auto_save_data(self):
        """حفظ تلقائي للبيانات المهمة"""
        try:
            # حفظ بيانات AI
            self.ai.save_learning_data()
            
            # حفظ الإعدادات
            settings_data = {
                'last_save': datetime.now().isoformat(),
                'settings': self.get_current_settings(),
                'battery_health': self.monitor.get_battery_health(),
                'total_runtime': getattr(self, 'total_runtime', 0)
            }
            
            with open('battery_settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=2)
            
            logger.debug("تم الحفظ التلقائي للبيانات")
        except Exception as e:
            logger.error(f"خطأ في الحفظ التلقائي: {e}")
    
    def quit_application(self):
        """إنهاء البرنامج بشكل كامل بسرعة"""
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        
        # عرض مؤشر الإغلاق
        progress = QProgressDialog("جارٍ إغلاق التطبيق...", None, 0, 4, self)
        progress.setWindowTitle("BatteryGuard Pro")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        
        self.log_event("إيقاف البرنامج...")
        
        # إيقاف المؤقتات
        progress.setValue(1)
        QApplication.processEvents()
        if hasattr(self, 'auto_save_timer'):
            self.auto_save_timer.stop()
        if hasattr(self, 'ai_timer'):
            self.ai_timer.stop()
        if hasattr(self, 'uptime_timer'):
            self.uptime_timer.stop()
        
        # إيقاف المراقبة بسرعة
        progress.setValue(2)
        progress.setLabelText("إيقاف المراقبة...")
        QApplication.processEvents()
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.running = False
            # عدم الانتظار طويلاً
            self.monitor_thread.wait(1000)  # انتظار ثانية واحدة فقط
            if self.monitor_thread.isRunning():
                self.monitor_thread.terminate()
        
        # حفظ سريع للبيانات
        progress.setValue(3)
        progress.setLabelText("حفظ البيانات...")
        QApplication.processEvents()
        try:
            self.ai.save_learning_data()
            self._auto_save_data()
        except:
            pass
        
        # إخفاء الصينية
        progress.setValue(4)
        if hasattr(self, 'tray'):
            self.tray.hide()
        
        progress.close()
        QApplication.quit()
    
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
            
            # الحصول على صحة البطارية
            health_info = self.monitor.get_battery_health()
            battery_health = health_info.get('health_percentage', 100)
            
            # إرسال تنبيهات حدود البطارية
            self.notification_manager.send_battery_threshold_alert(
                current_percent, is_charging, battery_health
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
                'temperature': battery_status.get('temperature', 0),
                'unhealthy_charging_pattern': self._detect_unhealthy_charging()
            }
            
            self.notification_manager.send_smart_usage_alert(usage_data)
            
            # تنبيهات الذكاء الاصطناعي
            if hasattr(self, 'ai') and self.ai:
                ai_alerts = self._get_ai_alerts(battery_status)
                for alert in ai_alerts:
                    self.notification_manager.send_ai_smart_alert(alert)
            
        except Exception as e:
            logger.error(f"خطأ في فحص تنبيهات البطارية: {e}")
    
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
            
            # تحويل التوصيات المهمة إلى تنبيهات
            for rec in recommendations:
                if '🚨' in rec or '⚠️' in rec:
                    alerts.append({
                        'type': 'usage_prediction',
                        'message': rec,
                        'confidence': 85
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