#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مكونات الواجهة الرسومية"""

from typing import Dict
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QSlider, QSpinBox, QCheckBox, QGroupBox, QGridLayout, 
                             QProgressBar, QTextEdit, QFrame)
from PyQt6.QtCore import Qt
from battery_widget import AnimatedBatteryWidget


class StatusTab:
    """تبويب الحالة"""
    
    @staticmethod
    def create(parent) -> QWidget:
        tab = QWidget()
        tab.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # صف البطارية والمعلومات
        main_row = QHBoxLayout()
        main_row.setSpacing(20)
        
        # ويدجت البطارية المتحرك
        battery_container = QFrame()
        battery_container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(59, 130, 246, 0.15), stop:1 rgba(37, 99, 235, 0.05));
                border: 2px solid rgba(59, 130, 246, 0.3);
                border-radius: 20px;
                padding: 30px;
            }
        """)
        battery_container.setMinimumWidth(300)
        battery_container.setMaximumWidth(450)
        battery_layout = QVBoxLayout(battery_container)
        
        parent.battery_widget = AnimatedBatteryWidget()
        battery_layout.addWidget(parent.battery_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        
        parent.charging_status = QLabel("غير متصل بالشاحن")
        parent.charging_status.setStyleSheet("""
            font-size: 16px;
            color: #ffffff;
            margin-top: 15px;
            background: transparent;
            font-weight: 600;
        """)
        parent.charging_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        battery_layout.addWidget(parent.charging_status)
        
        main_row.addWidget(battery_container)
        
        # بطاقات المعلومات
        info_container = QWidget()
        info_container.setStyleSheet("background: transparent;")
        info_container.setMinimumWidth(300)
        info_layout = QVBoxLayout(info_container)
        info_layout.setSpacing(12)
        
        # إنشاء بطاقات معلومات
        def create_info_card(icon_text, title_text, value_text):
            card = QFrame()
            card.setMinimumHeight(95)
            card.setMaximumHeight(110)
            card.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(30, 41, 59, 0.9), stop:1 rgba(15, 23, 42, 0.7));
                    border: 2px solid rgba(71, 85, 105, 0.6);
                    border-radius: 16px;
                }
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setSpacing(15)
            card_layout.setContentsMargins(20, 16, 20, 16)
            
            # الأيقونة
            icon_label = QLabel(icon_text)
            icon_label.setStyleSheet("font-size: 36px; background: transparent;")
            icon_label.setFixedSize(50, 50)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(icon_label)
            
            # النصوص
            text_container = QWidget()
            text_container.setStyleSheet("background: transparent;")
            text_layout = QVBoxLayout(text_container)
            text_layout.setSpacing(6)
            text_layout.setContentsMargins(0, 0, 0, 0)
            
            title_label = QLabel(title_text)
            title_label.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    color: #94a3b8;
                    background: transparent;
                    font-weight: 600;
                }
            """)
            
            value_label = QLabel(value_text)
            value_label.setObjectName(f"value_{title_text}")
            value_label.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    color: #ffffff;
                    background: transparent;
                    font-weight: 700;
                }
            """)
            
            text_layout.addWidget(title_label)
            text_layout.addWidget(value_label)
            text_layout.addStretch()
            
            card_layout.addWidget(text_container, 1)
            
            return card, value_label
        
        # إنشاء البطاقات
        card1, parent.time_remaining_label = create_info_card("⏱️", "الوقت المتبقي", "جارٍ الحساب...")
        card2, parent.health_label = create_info_card("❤️", "صحة البطارية", "100%")
        card3, parent.cycle_count_label = create_info_card("🔄", "دورات الشحن", "0 دورة")
        card4, parent.power_draw_label = create_info_card("⚡", "استهلاك الطاقة", "0 واط")
        
        info_layout.addWidget(card1)
        info_layout.addWidget(card2)
        info_layout.addWidget(card3)
        info_layout.addWidget(card4)
        info_layout.addStretch()
        
        main_row.addWidget(info_container, 1)
        layout.addLayout(main_row)
        
        return tab


class SettingsTab:
    """تبويب الإعدادات"""
    
    @staticmethod
    def create(parent) -> QWidget:
        tab = QWidget()
        tab.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        notif_group = QGroupBox("⏰ إعدادات الإشعارات")
        notif_layout = QVBoxLayout(notif_group)
        notif_layout.setSpacing(12)
        
        parent.enable_notifications = QCheckBox("تفعيل الإشعارات")
        parent.enable_notifications.setChecked(True)
        parent.enable_notifications.setStyleSheet("""
            QCheckBox {
                font-size: 15px;
                color: #ffffff;
                background: transparent;
                padding: 8px;
            }
        """)
        notif_layout.addWidget(parent.enable_notifications)
        
        low_battery_layout = QHBoxLayout()
        low_label = QLabel("إشعار عند انخفاض البطارية إلى:")
        low_label.setStyleSheet("color: #ffffff; background: transparent;")
        low_battery_layout.addWidget(low_label)
        parent.low_battery_spin = QSpinBox()
        parent.low_battery_spin.setRange(5, 30)
        parent.low_battery_spin.setValue(20)
        parent.low_battery_spin.setSuffix("%")
        parent.low_battery_spin.setMinimumWidth(100)
        low_battery_layout.addWidget(parent.low_battery_spin)
        low_battery_layout.addStretch()
        notif_layout.addLayout(low_battery_layout)
        
        charge_layout = QHBoxLayout()
        charge_label = QLabel("اقتراح توصيل الشاحن عند:")
        charge_label.setStyleSheet("color: #ffffff; background: transparent;")
        charge_layout.addWidget(charge_label)
        parent.charge_threshold_spin = QSpinBox()
        parent.charge_threshold_spin.setRange(20, 60)
        parent.charge_threshold_spin.setValue(40)
        parent.charge_threshold_spin.setSuffix("%")
        parent.charge_threshold_spin.setMinimumWidth(100)
        charge_layout.addWidget(parent.charge_threshold_spin)
        charge_layout.addStretch()
        notif_layout.addLayout(charge_layout)
        
        unplug_layout = QHBoxLayout()
        unplug_label = QLabel("اقتراح فصل الشاحن عند:")
        unplug_label.setStyleSheet("color: #ffffff; background: transparent;")
        unplug_layout.addWidget(unplug_label)
        parent.unplug_threshold_spin = QSpinBox()
        parent.unplug_threshold_spin.setRange(70, 95)
        parent.unplug_threshold_spin.setValue(80)
        parent.unplug_threshold_spin.setSuffix("%")
        parent.unplug_threshold_spin.setMinimumWidth(100)
        unplug_layout.addWidget(parent.unplug_threshold_spin)
        unplug_layout.addStretch()
        notif_layout.addLayout(unplug_layout)
        
        layout.addWidget(notif_group)
        
        general_group = QGroupBox("🔧 إعدادات عامة")
        general_layout = QVBoxLayout(general_group)
        general_layout.setContentsMargins(16, 20, 16, 16)
        general_layout.setSpacing(12)
        
        parent.start_on_boot = QCheckBox("بدء التشغيل مع النظام")
        parent.minimize_to_tray = QCheckBox("التصغير إلى صينية النظام")
        parent.show_battery_in_tray = QCheckBox("عرض نسبة البطارية في الأيقونة")
        
        for checkbox in [parent.start_on_boot, parent.minimize_to_tray, parent.show_battery_in_tray]:
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 15px;
                    color: #ffffff;
                    background: transparent;
                    padding: 8px;
                }
            """)
            general_layout.addWidget(checkbox)
        
        layout.addWidget(general_group)
        
        if parent.monitor.can_control_charging:
            charge_control_group = QGroupBox("⚡ التحكم المتقدم في الشحن")
            charge_control_layout = QVBoxLayout(charge_control_group)
            charge_control_layout.setContentsMargins(16, 20, 16, 16)
            charge_control_layout.setSpacing(12)
            
            support_label = QLabel("✓ جهازك يدعم التحكم في حد الشحن")
            support_label.setStyleSheet("font-size: 14px; color: #10b981; background: transparent; padding: 8px;")
            charge_control_layout.addWidget(support_label)
            
            limit_layout = QHBoxLayout()
            limit_label = QLabel("حد الشحن الأقصى:")
            limit_label.setStyleSheet("font-size: 15px; color: #ffffff; background: transparent;")
            limit_layout.addWidget(limit_label)
            
            parent.charge_limit_slider = QSlider(Qt.Orientation.Horizontal)
            parent.charge_limit_slider.setRange(60, 100)
            parent.charge_limit_slider.setValue(80)
            parent.charge_limit_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            parent.charge_limit_slider.setTickInterval(10)
            limit_layout.addWidget(parent.charge_limit_slider)
            
            parent.charge_limit_value = QLabel("80%")
            parent.charge_limit_value.setStyleSheet("font-size: 18px; color: #3b82f6; background: transparent; font-weight: 700; min-width: 60px;")
            parent.charge_limit_slider.valueChanged.connect(
                lambda v: parent.charge_limit_value.setText(f"{v}%")
            )
            limit_layout.addWidget(parent.charge_limit_value)
            charge_control_layout.addLayout(limit_layout)
            
            apply_limit_btn = QPushButton("تطبيق الحد")
            apply_limit_btn.clicked.connect(parent.apply_charge_limit)
            charge_control_layout.addWidget(apply_limit_btn)
            
            layout.addWidget(charge_control_group)
        
        save_button = QPushButton("💾 حفظ الإعدادات")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        save_button.clicked.connect(parent.save_settings)
        layout.addWidget(save_button)
        
        layout.addStretch()
        
        return tab


class AITab:
    """تبويب الذكاء الاصطناعي"""
    
    @staticmethod
    def create(parent) -> QWidget:
        tab = QWidget()
        tab.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        title = QLabel("🤖 محرك الذكاء الاصطناعي")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff; margin-bottom: 10px; background: transparent;")
        layout.addWidget(title)
        
        desc = QLabel("يقوم الذكاء الاصطناعي بتحليل أنماط استخدامك وتقديم توصيات مخصصة لإطالة عمر البطارية")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #cbd5e1; margin-bottom: 20px; background: transparent;")
        layout.addWidget(desc)
        
        recommendations_group = QGroupBox("💡 التوصيات الذكية")
        recommendations_layout = QVBoxLayout(recommendations_group)
        recommendations_layout.setContentsMargins(16, 20, 16, 16)
        
        parent.recommendations_text = QTextEdit()
        parent.recommendations_text.setReadOnly(True)
        parent.recommendations_text.setMinimumHeight(200)
        parent.recommendations_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #334155;
                border-radius: 12px;
                padding: 16px;
                background-color: #1e293b;
                color: #ffffff;
                font-size: 15px;
                line-height: 1.8;
            }
        """)
        parent.recommendations_text.setPlainText("جارٍ تحليل أنماط الاستخدام...\nسيتم عرض التوصيات بعد جمع بيانات كافية.")
        recommendations_layout.addWidget(parent.recommendations_text)
        
        layout.addWidget(recommendations_group)
        
        predictions_group = QGroupBox("🔮 التنبؤات")
        predictions_layout = QVBoxLayout(predictions_group)
        predictions_layout.setContentsMargins(16, 20, 16, 16)
        
        parent.prediction_text = QLabel("جارٍ التنبؤ بأنماط الاستخدام...")
        parent.prediction_text.setWordWrap(True)
        parent.prediction_text.setMinimumHeight(60)
        parent.prediction_text.setStyleSheet("""
            QLabel {
                padding: 16px;
                font-size: 15px;
                color: #ffffff;
                background: transparent;
            }
        """)
        predictions_layout.addWidget(parent.prediction_text)
        
        layout.addWidget(predictions_group)
        
        learning_group = QGroupBox("📊 إحصائيات التعلم")
        learning_layout = QVBoxLayout(learning_group)
        learning_layout.setContentsMargins(16, 20, 16, 16)
        learning_layout.setSpacing(12)
        
        # بطاقات الإحصائيات
        stats_row1 = QHBoxLayout()
        stats_row1.setSpacing(12)
        
        data_card = QFrame()
        data_card.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.8);
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        data_layout = QVBoxLayout(data_card)
        data_title = QLabel("نقاط البيانات")
        data_title.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        parent.data_points_label = QLabel("0")
        parent.data_points_label.setStyleSheet("font-size: 24px; color: #3b82f6; background: transparent; font-weight: 700;")
        data_layout.addWidget(data_title)
        data_layout.addWidget(parent.data_points_label)
        stats_row1.addWidget(data_card)
        
        patterns_card = QFrame()
        patterns_card.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.8);
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        patterns_layout = QVBoxLayout(patterns_card)
        patterns_title = QLabel("الأنماط المكتشفة")
        patterns_title.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        parent.patterns_found_label = QLabel("0")
        parent.patterns_found_label.setStyleSheet("font-size: 24px; color: #10b981; background: transparent; font-weight: 700;")
        patterns_layout.addWidget(patterns_title)
        patterns_layout.addWidget(parent.patterns_found_label)
        stats_row1.addWidget(patterns_card)
        
        learning_layout.addLayout(stats_row1)
        
        efficiency_card = QFrame()
        efficiency_card.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.8);
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        efficiency_layout = QVBoxLayout(efficiency_card)
        efficiency_title = QLabel("درجة الكفاءة")
        efficiency_title.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        parent.efficiency_score_label = QLabel("100%")
        parent.efficiency_score_label.setStyleSheet("font-size: 24px; color: #f59e0b; background: transparent; font-weight: 700;")
        efficiency_layout.addWidget(efficiency_title)
        efficiency_layout.addWidget(parent.efficiency_score_label)
        learning_layout.addWidget(efficiency_card)
        
        layout.addWidget(learning_group)
        
        buttons_layout = QHBoxLayout()
        
        refresh_ai_btn = QPushButton("🔄 تحديث التحليل")
        refresh_ai_btn.clicked.connect(parent.refresh_ai_analysis)
        buttons_layout.addWidget(refresh_ai_btn)
        
        reset_ai_btn = QPushButton("🗑️ إعادة تعيين البيانات")
        reset_ai_btn.clicked.connect(parent.reset_ai_data)
        buttons_layout.addWidget(reset_ai_btn)
        
        layout.addLayout(buttons_layout)
        
        layout.addStretch()
        
        return tab


class StatsTab:
    """تبويب الإحصائيات"""
    
    @staticmethod
    def create(parent) -> QWidget:
        tab = QWidget()
        tab.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        health_group = QGroupBox("❤️ صحة البطارية")
        health_layout = QVBoxLayout(health_group)
        health_layout.setSpacing(12)
        
        parent.health_progress = QProgressBar()
        parent.health_progress.setMinimumHeight(40)
        parent.health_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #334155;
                border-radius: 12px;
                background-color: #1e293b;
                color: #ffffff;
                text-align: center;
                font-weight: bold;
                font-size: 16px;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
            }
        """)
        health_layout.addWidget(parent.health_progress)
        
        health_details = QVBoxLayout()
        health_details.setSpacing(12)
        
        # بطاقات السعة
        capacity_row = QHBoxLayout()
        capacity_row.setSpacing(12)
        
        design_card = QFrame()
        design_card.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.8);
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        design_layout = QVBoxLayout(design_card)
        design_title = QLabel("السعة التصميمية")
        design_title.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        parent.design_capacity_label = QLabel("-- mWh")
        parent.design_capacity_label.setStyleSheet("font-size: 18px; color: #ffffff; background: transparent; font-weight: 700;")
        design_layout.addWidget(design_title)
        design_layout.addWidget(parent.design_capacity_label)
        capacity_row.addWidget(design_card)
        
        current_card = QFrame()
        current_card.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.8);
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        current_layout = QVBoxLayout(current_card)
        current_title = QLabel("السعة الحالية")
        current_title.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        parent.current_capacity_label = QLabel("-- mWh")
        parent.current_capacity_label.setStyleSheet("font-size: 18px; color: #ffffff; background: transparent; font-weight: 700;")
        current_layout.addWidget(current_title)
        current_layout.addWidget(parent.current_capacity_label)
        capacity_row.addWidget(current_card)
        
        health_details.addLayout(capacity_row)
        
        wear_card = QFrame()
        wear_card.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.8);
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        wear_layout = QVBoxLayout(wear_card)
        wear_title = QLabel("مستوى التآكل")
        wear_title.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        parent.wear_level_label = QLabel("--%")
        parent.wear_level_label.setStyleSheet("font-size: 18px; color: #ef4444; background: transparent; font-weight: 700;")
        wear_layout.addWidget(wear_title)
        wear_layout.addWidget(parent.wear_level_label)
        health_details.addWidget(wear_card)
        
        health_layout.addLayout(health_details)
        layout.addWidget(health_group)
        
        events_group = QGroupBox("📜 سجل الأحداث")
        events_layout = QVBoxLayout(events_group)
        
        parent.events_log = QTextEdit()
        parent.events_log.setReadOnly(True)
        parent.events_log.setMinimumHeight(250)
        parent.events_log.setStyleSheet("""
            QTextEdit {
                border: 2px solid #334155;
                border-radius: 12px;
                padding: 16px;
                background-color: #1e293b;
                color: #ffffff;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        events_layout.addWidget(parent.events_log)
        
        clear_log_btn = QPushButton("🗑️ مسح السجل")
        clear_log_btn.clicked.connect(lambda: parent.events_log.clear())
        events_layout.addWidget(clear_log_btn)
        
        layout.addWidget(events_group)
        
        return tab
