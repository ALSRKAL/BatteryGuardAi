#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مكونات الواجهة الرسومية المحسّنة"""

from typing import Dict
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QSlider, QSpinBox, QCheckBox, QGroupBox, QGridLayout, 
                             QProgressBar, QTextEdit, QFrame, QSizePolicy, QScrollArea)
from PyQt6.QtCore import Qt
from battery_widget import AnimatedBatteryWidget


def create_styled_label(text, font_size=15, color="#ffffff", bold=False):
    """إنشاء label منسق"""
    label = QLabel(text)
    weight = "700" if bold else "400"
    label.setStyleSheet(f"""
        QLabel {{
            font-size: {font_size}px;
            color: {color};
            background: transparent;
            font-weight: {weight};
        }}
    """)
    return label


class StatusTab:
    """تبويب الحالة"""
    
    @staticmethod
    def create(parent) -> QWidget:
        # Scroll Area للتعامل مع التصغير
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #1e293b;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 5px;
                min-height: 30px;
            }
        """)
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # صف البطارية والمعلومات
        main_row = QHBoxLayout()
        main_row.setSpacing(20)
        
        # ويدجت البطارية
        battery_container = QFrame()
        battery_container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(59, 130, 246, 0.15), stop:1 rgba(37, 99, 235, 0.05));
                border: 2px solid rgba(59, 130, 246, 0.3);
                border-radius: 20px;
            }
        """)
        battery_container.setMinimumWidth(280)
        battery_container.setMinimumHeight(400)
        battery_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        battery_layout = QVBoxLayout(battery_container)
        battery_layout.setContentsMargins(30, 30, 30, 30)
        
        parent.battery_widget = AnimatedBatteryWidget()
        parent.battery_widget.setMinimumSize(180, 280)
        battery_layout.addWidget(parent.battery_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
        parent.charging_status = create_styled_label("غير متصل بالشاحن", 16, "#ffffff", True)
        parent.charging_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent.charging_status.setWordWrap(True)
        parent.charging_status.setContentsMargins(0, 15, 0, 0)
        battery_layout.addWidget(parent.charging_status)
        
        main_row.addWidget(battery_container, 0)
        
        # بطاقات المعلومات
        info_container = QWidget()
        info_container.setStyleSheet("background: transparent;")
        info_container.setMinimumWidth(280)
        info_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        info_layout = QVBoxLayout(info_container)
        info_layout.setSpacing(12)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # إنشاء البطاقات
        parent.time_remaining_label = create_styled_label("جارٍ الحساب...", 16, "#ffffff", True)
        parent.health_label = create_styled_label("100%", 16, "#ffffff", True)
        parent.cycle_count_label = create_styled_label("0 دورة", 16, "#ffffff", True)
        parent.power_draw_label = create_styled_label("0 واط", 16, "#ffffff", True)
        
        for label in [parent.time_remaining_label, parent.health_label, 
                     parent.cycle_count_label, parent.power_draw_label]:
            label.setWordWrap(True)
        
        info_layout.addWidget(StatusTab._create_info_card("⏱️", "الوقت المتبقي", parent.time_remaining_label))
        info_layout.addWidget(StatusTab._create_info_card("❤️", "صحة البطارية", parent.health_label))
        info_layout.addWidget(StatusTab._create_info_card("🔄", "دورات الشحن", parent.cycle_count_label))
        info_layout.addWidget(StatusTab._create_info_card("⚡", "استهلاك الطاقة", parent.power_draw_label))
        info_layout.addStretch()
        
        main_row.addWidget(info_container, 1)
        layout.addLayout(main_row)
        
        # زر التحسين الذكي
        optimize_container = QFrame()
        optimize_container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, 0.15), stop:1 rgba(5, 150, 105, 0.1));
                border: 2px solid rgba(16, 185, 129, 0.3);
                border-radius: 20px;
                padding: 25px;
            }
        """)
        optimize_layout = QVBoxLayout(optimize_container)
        optimize_layout.setSpacing(15)
        
        optimize_title = create_styled_label("🤖 محرك التحسين الذكي المتقدم", 22, "#8b5cf6", True)
        optimize_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        optimize_layout.addWidget(optimize_title)
        
        optimize_desc = create_styled_label(
            "🧠 تحسين ذكي بالذكاء الاصطناعي • 🚀 تحليل أنماط الاستخدام • ⚡ تحسين شخصي متقدم • 🎯 توفير طاقة أقصى",
            14, "#a78bfa"
        )
        optimize_desc.setWordWrap(True)
        optimize_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        optimize_layout.addWidget(optimize_desc)
        
        parent.optimize_button = QPushButton("🤖 تحسين ذكي متقدم")
        parent.optimize_button.setMinimumHeight(70)
        # ملاحظة: صيغة Qt الصحيحة qlineargradient (كانت CSS قياسية لا يعملها Qt)
        parent.optimize_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #8b5cf6, stop:0.25 #7c3aed, stop:0.5 #6d28d9,
                    stop:0.75 #5b21b6, stop:1 #4c1d95);
                color: #ffffff;
                border: 3px solid rgba(139, 92, 246, 0.5);
                border-radius: 18px;
                font-size: 19px;
                font-weight: 900;
                letter-spacing: 1.2px;
                padding: 20px 40px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7c3aed, stop:0.25 #6d28d9, stop:0.5 #5b21b6,
                    stop:0.75 #4c1d95, stop:1 #3730a3);
                border: 3px solid rgba(139, 92, 246, 0.8);
                padding: 20px 42px;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6d28d9, stop:0.5 #5b21b6, stop:1 #4c1d95);
                padding: 20px 38px;
            }
            QPushButton:disabled {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #374151, stop:1 #4b5563);
                color: #9ca3af;
                border: 3px solid #6b7280;
            }
        """)
        parent.optimize_button.clicked.connect(parent.run_optimization)
        optimize_layout.addWidget(parent.optimize_button)
        
        parent.optimize_status = create_styled_label("", 12, "#94a3b8")
        parent.optimize_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent.optimize_status.setWordWrap(True)
        optimize_layout.addWidget(parent.optimize_status)
        
        layout.addWidget(optimize_container)
        layout.addStretch()
        
        scroll.setWidget(content)
        
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll)
        
        return wrapper
    
    @staticmethod
    def _create_info_card(icon, title, value_label):
        """إنشاء بطاقة معلومات"""
        card = QFrame()
        card.setMinimumHeight(85)
        card.setMinimumWidth(250)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 41, 59, 0.9), stop:1 rgba(15, 23, 42, 0.7));
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 16px;
            }
        """)
        
        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(16, 14, 16, 14)
        
        # الأيقونة
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 32px; background: transparent;")
        icon_label.setFixedSize(45, 45)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label, 0)
        
        # النصوص
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_label = create_styled_label(title, 12, "#94a3b8", True)
        title_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(value_label)
        text_layout.addStretch()
        
        card_layout.addLayout(text_layout, 1)
        
        return card



class SettingsTab:
    """تبويب الإعدادات"""
    
    @staticmethod
    def create(parent) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background: transparent; 
            }
            QScrollBar:vertical {
                background: #1e293b;
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #475569, stop:1 #64748b);
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #64748b, stop:1 #94a3b8);
            }
        """)
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(25)
        
        # إعدادات الإشعارات الذكية المتقدمة
        notif_group = QGroupBox("🔔 إعدادات الإشعارات الذكية")
        notif_layout = QVBoxLayout()
        notif_layout.setSpacing(20)
        notif_layout.setContentsMargins(25, 35, 25, 25)
        notif_group.setLayout(notif_layout)
        
        # الإعدادات الأساسية
        basic_settings = QHBoxLayout()
        
        parent.enable_notifications = QCheckBox("🔔 تفعيل الإشعارات")
        parent.enable_notifications.setChecked(True)
        parent.enable_notifications.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                color: #ffffff;
                padding: 10px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }
        """)
        basic_settings.addWidget(parent.enable_notifications)
        
        parent.enable_sounds = QCheckBox("🔊 تفعيل الأصوات")
        parent.enable_sounds.setChecked(True)
        parent.enable_sounds.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                color: #ffffff;
                padding: 10px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }
        """)
        basic_settings.addWidget(parent.enable_sounds)
        
        parent.enable_reminders = QCheckBox("🔄 تفعيل التذكيرات")
        parent.enable_reminders.setChecked(True)
        parent.enable_reminders.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                color: #ffffff;
                padding: 10px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }
        """)
        basic_settings.addWidget(parent.enable_reminders)
        
        notif_layout.addLayout(basic_settings)
        
        # فاصل
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: rgba(71, 85, 105, 0.3); max-height: 1px;")
        notif_layout.addWidget(separator)
        
        # حدود البطارية القابلة للتخصيص
        thresholds_title = create_styled_label("⚙️ حدود التنبيهات المخصصة", 18, "#8b5cf6", True)
        notif_layout.addWidget(thresholds_title)
        
        # الحقول بتصميم محسّن
        for label_text, spin_attr, min_val, max_val, default_val, icon, description in [
            ("حرج - بطارية منخفضة جداً", "critical_battery_spin", 5, 15, 10, "🚨", "تنبيه حرج مع تذكير مستمر"),
            ("منخفض - يحتاج شحن", "low_battery_spin", 15, 30, 20, "⚠️", "تنبيه عادي مع تذكير دوري"),
            ("الحد الأدنى الأمثل", "optimal_min_spin", 30, 50, 40, "📊", "أقل مستوى صحي للبطارية"),
            ("الحد الأعلى الأمثل", "optimal_max_spin", 70, 90, 80, "⚡", "أعلى مستوى صحي للبطارية"),
            ("مرتفع - اقتراح الفصل", "high_battery_spin", 85, 95, 90, "🔋", "تنبيه لفصل الشاحن"),
            ("ممتلئ - فصل فوري", "full_battery_spin", 90, 100, 95, "✅", "تذكير مستمر لفصل الشاحن")
        ]:
            container = QWidget()
            container.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(139, 92, 246, 0.1), stop:1 rgba(30, 41, 59, 0.3));
                    border: 1px solid rgba(139, 92, 246, 0.2);
                    border-radius: 14px;
                }
                QLabel {
                    background: transparent;
                }
            """)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(15, 12, 15, 12)
            container_layout.setSpacing(8)
            
            # الصف الأول - الأيقونة والعنوان والقيمة
            row = QHBoxLayout()
            row.setSpacing(15)
            
            icon_label = create_styled_label(icon, 24)
            icon_label.setFixedWidth(40)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(icon_label)
            
            label = create_styled_label(label_text, 16, "#ffffff", True)
            row.addWidget(label)
            
            row.addStretch()
            
            spin = QSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(default_val)
            spin.setSuffix("%")
            spin.setMinimumWidth(100)
            spin.setMinimumHeight(42)
            spin.setStyleSheet("""
                QSpinBox {
                    padding: 10px 14px;
                    border: 2px solid rgba(139, 92, 246, 0.3);
                    border-radius: 10px;
                    background: rgba(15, 23, 42, 0.8);
                    color: #ffffff;
                    font-size: 15px;
                    font-weight: 700;
                }
                QSpinBox:focus {
                    border-color: #8b5cf6;
                    background: rgba(15, 23, 42, 1);
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    background: rgba(139, 92, 246, 0.2);
                    border: none;
                    border-radius: 4px;
                    width: 20px;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background: rgba(139, 92, 246, 0.4);
                }
            """)
            
            setattr(parent, spin_attr, spin)
            row.addWidget(spin)
            
            container_layout.addLayout(row)
            
            # الصف الثاني - الوصف
            desc_label = create_styled_label(description, 12, "#a78bfa")
            desc_label.setWordWrap(True)
            container_layout.addWidget(desc_label)
            
            notif_layout.addWidget(container)
        
        layout.addWidget(notif_group)
        
        # إعدادات عامة
        general_group = QGroupBox("⚙️ إعدادات عامة")
        general_layout = QVBoxLayout()
        general_layout.setSpacing(15)
        general_layout.setContentsMargins(25, 35, 25, 25)
        general_group.setLayout(general_layout)
        
        parent.start_on_boot = QCheckBox("🚀 بدء التشغيل مع النظام")
        parent.start_on_boot.stateChanged.connect(parent.on_autostart_changed)
        parent.minimize_to_tray = QCheckBox("📥 التصغير إلى صينية النظام")
        parent.show_battery_in_tray = QCheckBox("📊 عرض نسبة البطارية في الأيقونة")
        
        for checkbox in [parent.start_on_boot, parent.minimize_to_tray, parent.show_battery_in_tray]:
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 15px;
                    color: #e2e8f0;
                    padding: 12px;
                    font-weight: 500;
                }
                QCheckBox::indicator {
                    width: 22px;
                    height: 22px;
                }
                QCheckBox:hover {
                    color: #ffffff;
                }
            """)
            general_layout.addWidget(checkbox)
        
        layout.addWidget(general_group)
        
        # إعدادات التحكم في الشحن
        charge_control_group = QGroupBox("⚡ التحكم الذكي في الشحن")
        charge_control_layout = QVBoxLayout()
        charge_control_layout.setSpacing(20)
        charge_control_layout.setContentsMargins(25, 35, 25, 25)
        charge_control_group.setLayout(charge_control_layout)
        
        # تفعيل التحكم التلقائي
        parent.auto_charge_control = QCheckBox("🔋 تفعيل التحكم التلقائي")
        parent.auto_charge_control.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                color: #ffffff;
                padding: 10px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }
        """)
        parent.auto_charge_control.setChecked(False)
        charge_control_layout.addWidget(parent.auto_charge_control)
        
        # وصف مختصر
        desc = create_styled_label("يتحكم تلقائياً في إيقاف/بدء الشحن للحفاظ على صحة البطارية", 13, "#94a3b8")
        desc.setWordWrap(True)
        charge_control_layout.addWidget(desc)
        
        # فاصل
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setStyleSheet("background: rgba(71, 85, 105, 0.3); max-height: 1px;")
        charge_control_layout.addWidget(separator2)
        
        # الحد الأقصى للشحن
        max_container = QWidget()
        max_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(59, 130, 246, 0.1), stop:1 rgba(37, 99, 235, 0.05));
                border: 2px solid rgba(59, 130, 246, 0.3);
                border-radius: 12px;
                padding: 5px;
            }
        """)
        max_layout = QVBoxLayout(max_container)
        max_layout.setContentsMargins(20, 15, 20, 15)
        max_layout.setSpacing(12)
        
        max_header = QHBoxLayout()
        max_icon = create_styled_label("🛑", 18)
        max_header.addWidget(max_icon)
        max_label = create_styled_label("إيقاف الشحن عند", 15, "#e2e8f0", True)
        max_header.addWidget(max_label)
        max_header.addStretch()
        parent.max_charge_value_label = create_styled_label("80%", 20, "#3b82f6", True)
        max_header.addWidget(parent.max_charge_value_label)
        max_layout.addLayout(max_header)
        
        parent.max_charge_slider = QSlider(Qt.Orientation.Horizontal)
        parent.max_charge_slider.setRange(60, 100)
        parent.max_charge_slider.setValue(80)
        parent.max_charge_slider.setMinimumHeight(35)
        parent.max_charge_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 8px;
                background: #1e293b;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                border: 3px solid #1e40af;
                width: 22px;
                height: 22px;
                margin: -8px 0;
                border-radius: 11px;
            }
            QSlider::handle:horizontal:hover {
                background: #60a5fa;
                border-color: #3b82f6;
            }
        """)
        parent.max_charge_slider.valueChanged.connect(
            lambda v: parent.max_charge_value_label.setText(f"{v}%")
        )
        max_layout.addWidget(parent.max_charge_slider)
        
        charge_control_layout.addWidget(max_container)
        
        # الحد الأدنى للشحن
        min_container = QWidget()
        min_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, 0.1), stop:1 rgba(5, 150, 105, 0.05));
                border: 2px solid rgba(16, 185, 129, 0.3);
                border-radius: 12px;
                padding: 5px;
            }
        """)
        min_layout = QVBoxLayout(min_container)
        min_layout.setContentsMargins(20, 15, 20, 15)
        min_layout.setSpacing(12)
        
        min_header = QHBoxLayout()
        min_icon = create_styled_label("▶️", 18)
        min_header.addWidget(min_icon)
        min_label = create_styled_label("بدء الشحن عند", 15, "#e2e8f0", True)
        min_header.addWidget(min_label)
        min_header.addStretch()
        parent.min_charge_value_label = create_styled_label("40%", 20, "#10b981", True)
        min_header.addWidget(parent.min_charge_value_label)
        min_layout.addLayout(min_header)
        
        parent.min_charge_slider = QSlider(Qt.Orientation.Horizontal)
        parent.min_charge_slider.setRange(20, 60)
        parent.min_charge_slider.setValue(40)
        parent.min_charge_slider.setMinimumHeight(35)
        parent.min_charge_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 8px;
                background: #1e293b;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #10b981, stop:1 #059669);
                border: 3px solid #047857;
                width: 22px;
                height: 22px;
                margin: -8px 0;
                border-radius: 11px;
            }
            QSlider::handle:horizontal:hover {
                background: #34d399;
                border-color: #10b981;
            }
        """)
        parent.min_charge_slider.valueChanged.connect(
            lambda v: parent.min_charge_value_label.setText(f"{v}%")
        )
        min_layout.addWidget(parent.min_charge_slider)
        
        charge_control_layout.addWidget(min_container)
        
        layout.addWidget(charge_control_group)
        
        # إعدادات التحسين التلقائي الذكي
        auto_opt_group = QGroupBox("🚀 التحسين التلقائي الذكي")
        auto_opt_layout = QVBoxLayout()
        auto_opt_layout.setSpacing(20)
        auto_opt_layout.setContentsMargins(25, 35, 25, 25)
        auto_opt_group.setLayout(auto_opt_layout)
        
        # تفعيل التحسين التلقائي
        parent.enable_auto_optimization = QCheckBox("⚡ تفعيل التحسين التلقائي")
        parent.enable_auto_optimization.setStyleSheet("""
            QCheckBox {
                font-size: 16px;
                color: #ffffff;
                padding: 10px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }
        """)
        parent.enable_auto_optimization.setChecked(False)
        parent.enable_auto_optimization.stateChanged.connect(parent.on_auto_optimization_changed)
        auto_opt_layout.addWidget(parent.enable_auto_optimization)
        
        # وصف مختصر
        desc_opt = create_styled_label(
            "يراقب موارد النظام بشكل مستمر ويقوم بالتحسين تلقائياً عند الحاجة لتوفير الطاقة وتحسين الأداء",
            13, "#94a3b8"
        )
        desc_opt.setWordWrap(True)
        auto_opt_layout.addWidget(desc_opt)
        
        # فاصل
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.Shape.HLine)
        separator3.setStyleSheet("background: rgba(71, 85, 105, 0.3); max-height: 1px;")
        auto_opt_layout.addWidget(separator3)
        
        # وضع التحسين
        mode_container = QWidget()
        mode_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(251, 191, 36, 0.1), stop:1 rgba(245, 158, 11, 0.05));
                border: 2px solid rgba(251, 191, 36, 0.3);
                border-radius: 12px;
                padding: 5px;
            }
        """)
        mode_layout = QVBoxLayout(mode_container)
        mode_layout.setContentsMargins(20, 15, 20, 15)
        mode_layout.setSpacing(15)
        
        mode_title = create_styled_label("🎯 وضع التحسين", 16, "#fbbf24", True)
        mode_layout.addWidget(mode_title)
        
        # خيارات الوضع
        parent.opt_mode_continuous = QCheckBox("🔄 مستمر - تحسين دوري كل فترة محددة")
        parent.opt_mode_on_demand = QCheckBox("🎯 عند الحاجة - تحسين ذكي عند ارتفاع الاستهلاك (موصى به)")
        parent.opt_mode_scheduled = QCheckBox("⏰ مجدول - تحسين في أوقات محددة")
        
        for checkbox in [parent.opt_mode_continuous, parent.opt_mode_on_demand, parent.opt_mode_scheduled]:
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 14px;
                    color: #e2e8f0;
                    padding: 10px;
                    font-weight: 500;
                }
                QCheckBox::indicator {
                    width: 20px;
                    height: 20px;
                }
                QCheckBox:hover {
                    color: #ffffff;
                }
            """)
            mode_layout.addWidget(checkbox)
        
        # تعيين الوضع الافتراضي
        parent.opt_mode_on_demand.setChecked(True)
        
        # ربط الخيارات لتكون حصرية
        def on_mode_changed(state):
            if state:
                sender = parent.sender()
                if sender == parent.opt_mode_continuous:
                    parent.opt_mode_on_demand.setChecked(False)
                    parent.opt_mode_scheduled.setChecked(False)
                elif sender == parent.opt_mode_on_demand:
                    parent.opt_mode_continuous.setChecked(False)
                    parent.opt_mode_scheduled.setChecked(False)
                elif sender == parent.opt_mode_scheduled:
                    parent.opt_mode_continuous.setChecked(False)
                    parent.opt_mode_on_demand.setChecked(False)
        
        parent.opt_mode_continuous.stateChanged.connect(on_mode_changed)
        parent.opt_mode_on_demand.stateChanged.connect(on_mode_changed)
        parent.opt_mode_scheduled.stateChanged.connect(on_mode_changed)
        
        auto_opt_layout.addWidget(mode_container)
        
        # فترة التحسين (للوضع المستمر)
        interval_container = QWidget()
        interval_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(139, 92, 246, 0.1), stop:1 rgba(124, 58, 237, 0.05));
                border: 2px solid rgba(139, 92, 246, 0.3);
                border-radius: 12px;
                padding: 5px;
            }
        """)
        interval_layout = QVBoxLayout(interval_container)
        interval_layout.setContentsMargins(20, 15, 20, 15)
        interval_layout.setSpacing(12)
        
        interval_header = QHBoxLayout()
        interval_icon = create_styled_label("⏱️", 18)
        interval_header.addWidget(interval_icon)
        interval_label = create_styled_label("فترة التحسين (للوضع المستمر)", 15, "#e2e8f0", True)
        interval_header.addWidget(interval_label)
        interval_header.addStretch()
        parent.opt_interval_value_label = create_styled_label("5 دقائق", 16, "#a78bfa", True)
        interval_header.addWidget(parent.opt_interval_value_label)
        interval_layout.addLayout(interval_header)
        
        parent.opt_interval_slider = QSlider(Qt.Orientation.Horizontal)
        parent.opt_interval_slider.setRange(1, 60)  # 1-60 دقيقة
        parent.opt_interval_slider.setValue(5)
        parent.opt_interval_slider.setMinimumHeight(35)
        parent.opt_interval_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 8px;
                background: #1e293b;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #8b5cf6, stop:1 #7c3aed);
                border: 3px solid #6d28d9;
                width: 22px;
                height: 22px;
                margin: -8px 0;
                border-radius: 11px;
            }
            QSlider::handle:horizontal:hover {
                background: #a78bfa;
                border-color: #8b5cf6;
            }
        """)
        
        def update_interval_label(v):
            if v == 1:
                parent.opt_interval_value_label.setText("دقيقة واحدة")
            elif v == 2:
                parent.opt_interval_value_label.setText("دقيقتان")
            elif 3 <= v <= 10:
                parent.opt_interval_value_label.setText(f"{v} دقائق")
            else:
                parent.opt_interval_value_label.setText(f"{v} دقيقة")
        
        parent.opt_interval_slider.valueChanged.connect(update_interval_label)
        interval_layout.addWidget(parent.opt_interval_slider)
        
        auto_opt_layout.addWidget(interval_container)
        
        # عتبات التحسين المتقدمة
        thresholds_container = QWidget()
        thresholds_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(239, 68, 68, 0.1), stop:1 rgba(220, 38, 38, 0.05));
                border: 2px solid rgba(239, 68, 68, 0.3);
                border-radius: 12px;
                padding: 5px;
            }
        """)
        thresholds_layout = QVBoxLayout(thresholds_container)
        thresholds_layout.setContentsMargins(20, 15, 20, 15)
        thresholds_layout.setSpacing(15)
        
        thresholds_title = create_styled_label("⚙️ عتبات التحسين (للوضع عند الحاجة)", 16, "#ef4444", True)
        thresholds_layout.addWidget(thresholds_title)
        
        thresholds_desc = create_styled_label(
            "يتم التحسين تلقائياً عند تجاوز أي من هذه العتبات",
            12, "#fca5a5"
        )
        thresholds_desc.setWordWrap(True)
        thresholds_layout.addWidget(thresholds_desc)
        
        # شبكة العتبات
        thresholds_grid = QGridLayout()
        thresholds_grid.setSpacing(15)
        
        threshold_items = [
            ("💻 CPU", "opt_cpu_threshold", 70, "%", "استخدام المعالج"),
            ("🧠 الذاكرة", "opt_memory_threshold", 75, "%", "استخدام الذاكرة"),
            ("💾 القرص", "opt_disk_threshold", 85, "%", "استخدام القرص"),
            ("⚡ الطاقة", "opt_power_threshold", 15, "W", "استهلاك الطاقة")
        ]
        
        for i, (label_text, spin_attr, default_val, suffix, tooltip) in enumerate(threshold_items):
            row = i // 2
            col = (i % 2) * 2
            
            label = create_styled_label(label_text, 14, "#fca5a5", True)
            label.setToolTip(tooltip)
            thresholds_grid.addWidget(label, row, col)
            
            spin = QSpinBox()
            spin.setRange(10, 100 if suffix == "%" else 50)
            spin.setValue(default_val)
            spin.setSuffix(suffix)
            spin.setMinimumWidth(90)
            spin.setMinimumHeight(38)
            spin.setStyleSheet("""
                QSpinBox {
                    padding: 8px 12px;
                    border: 2px solid rgba(239, 68, 68, 0.3);
                    border-radius: 8px;
                    background: rgba(15, 23, 42, 0.8);
                    color: #ffffff;
                    font-size: 14px;
                    font-weight: 700;
                }
                QSpinBox:focus {
                    border-color: #ef4444;
                    background: rgba(15, 23, 42, 1);
                }
            """)
            setattr(parent, spin_attr, spin)
            thresholds_grid.addWidget(spin, row, col + 1)
        
        thresholds_layout.addLayout(thresholds_grid)
        auto_opt_layout.addWidget(thresholds_container)
        
        layout.addWidget(auto_opt_group)
        
        # زر الحفظ الموحد
        save_button = QPushButton("💾 حفظ جميع الإعدادات")
        save_button.setMinimumHeight(55)
        save_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                border: none;
                border-radius: 14px;
                padding: 16px 32px;
                font-size: 17px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #047857);
                padding: 16px 34px;
            }
            QPushButton:pressed {
                background: #047857;
                padding: 16px 30px;
            }
        """)
        save_button.clicked.connect(parent.save_all_settings)
        layout.addWidget(save_button)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        return scroll


class AITab:
    """تبويب الذكاء الاصطناعي"""
    
    @staticmethod
    def create(parent) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        title = create_styled_label("🤖 محرك الذكاء الاصطناعي", 20, "#ffffff", True)
        layout.addWidget(title)
        
        desc = create_styled_label("يقوم الذكاء الاصطناعي بتحليل أنماط استخدامك وتقديم توصيات مخصصة", 14, "#cbd5e1")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # التوصيات
        recommendations_group = QGroupBox("💡 التوصيات الذكية")
        recommendations_layout = QVBoxLayout()
        recommendations_layout.setContentsMargins(20, 30, 20, 20)
        recommendations_group.setLayout(recommendations_layout)
        
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
            }
        """)
        parent.recommendations_text.setPlainText("جارٍ تحليل أنماط الاستخدام...\nسيتم عرض التوصيات بعد جمع بيانات كافية.")
        recommendations_layout.addWidget(parent.recommendations_text)
        
        layout.addWidget(recommendations_group)
        
        # التنبؤات
        predictions_group = QGroupBox("🔮 التنبؤات والإحصائيات")
        predictions_layout = QVBoxLayout()
        predictions_layout.setContentsMargins(20, 30, 20, 20)
        predictions_group.setLayout(predictions_layout)
        
        parent.prediction_text = QLabel("جارٍ جمع البيانات للتنبؤ الدقيق...")
        parent.prediction_text.setWordWrap(True)
        parent.prediction_text.setMinimumHeight(80)
        parent.prediction_text.setStyleSheet("""
            QLabel {
                padding: 16px;
                font-size: 14px;
                color: #ffffff;
                background: rgba(30, 41, 59, 0.5);
                border-radius: 8px;
            }
        """)
        predictions_layout.addWidget(parent.prediction_text)
        
        layout.addWidget(predictions_group)
        
        # الإحصائيات المتقدمة
        stats_group = QGroupBox("📊 إحصائيات التعلم المتقدمة")
        stats_layout = QVBoxLayout()
        stats_layout.setContentsMargins(20, 30, 20, 20)
        stats_layout.setSpacing(15)
        stats_group.setLayout(stats_layout)
        
        # الصف الأول
        stats_row1 = QHBoxLayout()
        stats_row1.setSpacing(15)
        
        parent.data_points_label = create_styled_label("0", 24, "#3b82f6", True)
        parent.patterns_found_label = create_styled_label("0", 24, "#10b981", True)
        parent.efficiency_score_label = create_styled_label("100%", 24, "#f59e0b", True)
        
        stats_row1.addWidget(AITab._create_stat_card("نقاط البيانات", parent.data_points_label))
        stats_row1.addWidget(AITab._create_stat_card("الأنماط المكتشفة", parent.patterns_found_label))
        stats_row1.addWidget(AITab._create_stat_card("درجة الكفاءة", parent.efficiency_score_label))
        
        stats_layout.addLayout(stats_row1)
        
        # الصف الثاني - إحصائيات جديدة
        stats_row2 = QHBoxLayout()
        stats_row2.setSpacing(15)
        
        parent.health_score_label = create_styled_label("100%", 24, "#10b981", True)
        parent.drain_rate_label = create_styled_label("0.0", 24, "#ef4444", True)
        parent.charge_rate_label = create_styled_label("0.0", 24, "#3b82f6", True)
        
        stats_row2.addWidget(AITab._create_stat_card("درجة الصحة", parent.health_score_label))
        stats_row2.addWidget(AITab._create_stat_card("معدل الاستنزاف %/د", parent.drain_rate_label))
        stats_row2.addWidget(AITab._create_stat_card("معدل الشحن %/د", parent.charge_rate_label))
        
        stats_layout.addLayout(stats_row2)
        
        # الصف الثالث - إحصائيات التعلم
        stats_row3 = QHBoxLayout()
        stats_row3.setSpacing(15)
        
        parent.learning_iterations_label = create_styled_label("0", 24, "#a855f7", True)
        parent.prediction_accuracy_label = create_styled_label("0%", 24, "#f59e0b", True)
        parent.confidence_label = create_styled_label("0%", 24, "#06b6d4", True)
        
        stats_row3.addWidget(AITab._create_stat_card("تكرارات التعلم", parent.learning_iterations_label))
        stats_row3.addWidget(AITab._create_stat_card("دقة التنبؤ", parent.prediction_accuracy_label))
        stats_row3.addWidget(AITab._create_stat_card("درجة الثقة", parent.confidence_label))
        
        stats_layout.addLayout(stats_row3)
        
        # الصف الرابع - إحصائيات متقدمة جديدة
        stats_row4 = QHBoxLayout()
        stats_row4.setSpacing(15)
        
        parent.learning_progress_label = create_styled_label("0%", 24, "#10b981", True)
        parent.ai_maturity_label = create_styled_label("مبتدئ", 20, "#3b82f6", True)
        parent.personalization_label = create_styled_label("0%", 24, "#f59e0b", True)
        
        stats_row4.addWidget(AITab._create_stat_card("تقدم التعلم", parent.learning_progress_label))
        stats_row4.addWidget(AITab._create_stat_card("مستوى الذكاء", parent.ai_maturity_label))
        stats_row4.addWidget(AITab._create_stat_card("درجة التخصيص", parent.personalization_label))
        
        stats_layout.addLayout(stats_row4)
        
        # أزرار التحكم
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(15)
        
        refresh_btn = QPushButton("🔄 تحديث التحليل")
        refresh_btn.setMinimumHeight(45)
        refresh_btn.clicked.connect(parent.refresh_ai_analysis)
        buttons_row.addWidget(refresh_btn)
        
        reset_btn = QPushButton("🗑️ إعادة تعيين البيانات")
        reset_btn.setMinimumHeight(45)
        reset_btn.clicked.connect(parent.reset_ai_data)
        buttons_row.addWidget(reset_btn)
        
        stats_layout.addLayout(buttons_row)
        
        layout.addWidget(stats_group)
        layout.addStretch()
        
        scroll.setWidget(content)
        return scroll
    
    @staticmethod
    def _create_stat_card(title, value_label):
        """إنشاء بطاقة إحصائية"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.8);
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
            }
        """)
        card.setMinimumHeight(100)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(8)
        
        title_label = create_styled_label(title, 12, "#94a3b8", True)
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card_layout.addStretch()
        
        return card


class StatsTab:
    """تبويب الإحصائيات المتقدم"""
    
    @staticmethod
    def create(parent) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # صحة البطارية
        health_group = QGroupBox("❤️ صحة البطارية")
        health_layout = QVBoxLayout()
        health_layout.setContentsMargins(20, 30, 20, 20)
        health_layout.setSpacing(15)
        health_group.setLayout(health_layout)
        
        # شريط الصحة مع النسبة
        health_container = QWidget()
        health_container.setStyleSheet("background: transparent;")
        health_container_layout = QVBoxLayout(health_container)
        health_container_layout.setSpacing(8)
        
        parent.health_progress = QProgressBar()
        parent.health_progress.setMinimumHeight(45)
        parent.health_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #334155;
                border-radius: 12px;
                background-color: #1e293b;
                color: #ffffff;
                text-align: center;
                font-weight: bold;
                font-size: 18px;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
            }
        """)
        health_container_layout.addWidget(parent.health_progress)
        
        parent.health_status_label = create_styled_label("حالة ممتازة", 13, "#10b981", True)
        parent.health_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        health_container_layout.addWidget(parent.health_status_label)
        
        health_layout.addWidget(health_container)
        
        # بطاقات السعة
        capacity_row = QHBoxLayout()
        capacity_row.setSpacing(12)
        
        parent.design_capacity_label = create_styled_label("-- mWh", 20, "#ffffff", True)
        parent.current_capacity_label = create_styled_label("-- mWh", 20, "#ffffff", True)
        
        capacity_row.addWidget(StatsTab._create_capacity_card("السعة التصميمية", parent.design_capacity_label, "📐"))
        capacity_row.addWidget(StatsTab._create_capacity_card("السعة الحالية", parent.current_capacity_label, "🔋"))
        
        health_layout.addLayout(capacity_row)
        
        # صف التآكل ودورات الشحن
        wear_row = QHBoxLayout()
        wear_row.setSpacing(12)
        
        parent.wear_level_label = create_styled_label("--%", 20, "#ef4444", True)
        parent.cycle_count_stats_label = create_styled_label("0", 20, "#3b82f6", True)
        
        wear_row.addWidget(StatsTab._create_capacity_card("مستوى التآكل", parent.wear_level_label, "⚠️"))
        wear_row.addWidget(StatsTab._create_capacity_card("دورات الشحن", parent.cycle_count_stats_label, "🔄"))
        
        health_layout.addLayout(wear_row)
        
        layout.addWidget(health_group)
        
        # إحصائيات الاستخدام
        usage_group = QGroupBox("📊 إحصائيات الاستخدام")
        usage_layout = QVBoxLayout()
        usage_layout.setContentsMargins(20, 30, 20, 20)
        usage_layout.setSpacing(15)
        usage_group.setLayout(usage_layout)
        
        # صف الإحصائيات الأول
        stats_row1 = QHBoxLayout()
        stats_row1.setSpacing(12)
        
        parent.total_charge_time_label = create_styled_label("0س 0د", 18, "#10b981", True)
        parent.total_discharge_time_label = create_styled_label("0س 0د", 18, "#f59e0b", True)
        
        stats_row1.addWidget(StatsTab._create_stat_card("إجمالي وقت الشحن", parent.total_charge_time_label, "⚡"))
        stats_row1.addWidget(StatsTab._create_stat_card("إجمالي وقت الاستخدام", parent.total_discharge_time_label, "🔋"))
        
        usage_layout.addLayout(stats_row1)
        
        # صف الإحصائيات الثاني
        stats_row2 = QHBoxLayout()
        stats_row2.setSpacing(12)
        
        parent.avg_battery_level_label = create_styled_label("--%", 18, "#3b82f6", True)
        parent.charge_cycles_today_label = create_styled_label("0", 18, "#8b5cf6", True)
        
        stats_row2.addWidget(StatsTab._create_stat_card("متوسط مستوى البطارية", parent.avg_battery_level_label, "📈"))
        stats_row2.addWidget(StatsTab._create_stat_card("دورات الشحن اليوم", parent.charge_cycles_today_label, "🔁"))
        
        usage_layout.addLayout(stats_row2)
        
        # معلومات الطاقة
        power_row = QHBoxLayout()
        power_row.setSpacing(12)
        
        parent.avg_power_draw_label = create_styled_label("0 W", 18, "#f59e0b", True)
        parent.peak_power_draw_label = create_styled_label("0 W", 18, "#ef4444", True)
        
        power_row.addWidget(StatsTab._create_stat_card("متوسط استهلاك الطاقة", parent.avg_power_draw_label, "⚡"))
        power_row.addWidget(StatsTab._create_stat_card("ذروة الاستهلاك", parent.peak_power_draw_label, "🔥"))
        
        usage_layout.addLayout(power_row)
        
        layout.addWidget(usage_group)
        
        # سجل الأحداث
        events_group = QGroupBox("📜 سجل الأحداث")
        events_layout = QVBoxLayout()
        events_layout.setContentsMargins(20, 30, 20, 20)
        events_layout.setSpacing(12)
        events_group.setLayout(events_layout)
        
        # أزرار التحكم في السجل
        log_controls = QHBoxLayout()
        log_controls.setSpacing(10)
        
        clear_log_btn = QPushButton("🗑️ مسح السجل")
        clear_log_btn.setMinimumHeight(40)
        clear_log_btn.clicked.connect(parent.clear_log)
        log_controls.addWidget(clear_log_btn)
        
        export_log_btn = QPushButton("💾 تصدير السجل")
        export_log_btn.setMinimumHeight(40)
        export_log_btn.clicked.connect(parent.export_log)
        log_controls.addWidget(export_log_btn)
        
        reset_ai_btn = QPushButton("🔄 إعادة تعيين AI")
        reset_ai_btn.setMinimumHeight(40)
        reset_ai_btn.setToolTip("إعادة تعيين بيانات الذكاء الاصطناعي والأنماط المتعلمة")
        reset_ai_btn.clicked.connect(parent.reset_ai_data)
        log_controls.addWidget(reset_ai_btn)
        
        log_controls.addStretch()
        events_layout.addLayout(log_controls)
        
        parent.events_log = QTextEdit()
        parent.events_log.setReadOnly(True)
        parent.events_log.setMinimumHeight(200)
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
        
        layout.addWidget(events_group)
        
        scroll.setWidget(content)
        return scroll
    
    @staticmethod
    def _create_capacity_card(title, value_label, icon):
        """إنشاء بطاقة سعة"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 41, 59, 0.9), stop:1 rgba(15, 23, 42, 0.7));
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
            }
        """)
        card.setMinimumHeight(90)
        
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)
        
        # الأيقونة
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 32px; background: transparent;")
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        
        # النصوص
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_label = create_styled_label(title, 12, "#94a3b8", True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(value_label)
        
        card_layout.addLayout(text_layout, 1)
        
        return card
    
    @staticmethod
    def _create_stat_card(title, value_label, icon):
        """إنشاء بطاقة إحصائية"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(30, 41, 59, 0.8);
                border: 2px solid rgba(71, 85, 105, 0.6);
                border-radius: 12px;
            }
        """)
        card.setMinimumHeight(85)
        
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)
        
        # الأيقونة
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 28px; background: transparent;")
        icon_label.setFixedSize(35, 35)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        
        # النصوص
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_label = create_styled_label(title, 11, "#94a3b8", True)
        title_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(value_label)
        
        card_layout.addLayout(text_layout, 1)
        
        return card