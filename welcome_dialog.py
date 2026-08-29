#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نافذة الترحيب - تظهر عند التشغيل الأول
"""

import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QCheckBox, QScrollArea, QWidget,
                             QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap


class WelcomeDialog(QDialog):
    """نافذة الترحيب عند التشغيل الأول"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("مرحباً بك في BatteryGuardAI")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        
        self.setup_ui()
        
        # جعل النافذة في المنتصف
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
    
    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # العنوان الرئيسي
        title = QLabel("مرحباً بك في BatteryGuardAI!")
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2563eb; padding: 10px;")
        layout.addWidget(title)
        
        # نص الترحيب
        welcome_text = QLabel("نظام إدارة البطارية الذكي مع ذكاء اصطناعي")
        welcome_text.setFont(QFont('Arial', 12))
        welcome_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_text.setStyleSheet("color: #666; padding-bottom: 10px;")
        layout.addWidget(welcome_text)
        
        # خط فاصل
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(separator)
        
        # منطقة التمرير للمحتوى
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f9fafb;
            }
        """)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # الإعدادات الافتراضية
        self.add_section(content_layout, "الإعدادات الافتراضية", [
            ("مفعّل افتراضياً:", [
                "الإشعارات - جميع أنواع التنبيهات (بطارية منخفضة، حرجة، اكتمال الشحن، تحذيرات الصحة، التحسين)",
                "الأصوات - 5 أصوات مخصصة (حرج، تحذير، معلومات، نجاح، تحسين) بمستوى صوت 70%",
                "⏰ التذكيرات المتكررة - مع خيارات التحكم (إيقاف، غفوة، كتم، استمرار)",
                "توصيات الذكاء الاصطناعي - تحليل ذكي لأنماط الاستخدام",
                "التعلم من الاستخدام - تحسين مستمر بناءً على عاداتك",
                "التوقيت الذكي للإشعارات - تجنب الإزعاج في الأوقات غير المناسبة",
                "ساعات الهدوء - عدم إرسال إشعارات من 1-6 صباحاً",
                "أيقونة الصينية - للوصول السريع والعمل في الخلفية"
            ]),
            ("معطّل افتراضياً (يمكنك تفعيله من الإعدادات):", [
                "التشغيل التلقائي - عند بدء النظام (يحتاج تفعيل يدوي)",
                "وضع الخلفية - البدء مصغراً في الصينية",
                "التحكم في حدود الشحن - ضبط حدود 40%-80% (يحتاج صلاحيات مسؤول)",
                "التحسين التلقائي - تحسين تلقائي للنظام (قد يؤثر على الأداء)",
                "التصغير إلى الصينية - عند إغلاق النافذة"
            ])
        ])
        
        # الأصوات المخصصة
        self.add_section(content_layout, "الأصوات المخصصة (5 أصوات احترافية)", [
            ("كل صوت مخصص لحالة معينة:", [
                "صوت حرج - بطارية حرجة 8% (إيقاف وشيك، تحذيرات عاجلة)",
                "صوت تحذير - بطارية منخفضة 18% (يُنصح بالشحن، تحذيرات مهمة)",
                "صوت معلومات - توصيات الذكاء الاصطناعي (معلومات عامة، نصائح وإرشادات)",
                "صوت نجاح - اكتمل الشحن 82% (عملية ناجحة، تم الحفظ)",
                "صوت تحسين - بدء/اكتمال التحسين (توفير الطاقة)"
            ])
        ])
        
        # الإشعارات التفاعلية
        self.add_section(content_layout, "الإشعارات التفاعلية والتذكيرات الذكية", [
            ("فترات التذكير الافتراضية:", [
                "بطارية حرجة (أقل من 10%) - كل دقيقة واحدة",
                "بطارية منخفضة (أقل من 20%) - كل 5 دقائق",
                "اكتمل الشحن (أكثر من 80%) - كل 10 دقائق"
            ]),
            ("عند ظهور إشعار متكرر، يمكنك التحكم به:", [
                "⏹ إيقاف نهائي - يوقف التذكير تماماً لهذه الحالة",
                "غفوة 10 دقائق - يؤجل التذكير (افتراضي: 10 دقائق)",
                "كتم الصوت - يوقف الصوت فقط ويستمر الإشعار المرئي",
                "استمرار - يستمر التذكير حسب الفترة المحددة"
            ]),
            ("فترة التهدئة بين الإشعارات:", [
                "⏱ 5 دقائق - لتجنب الإزعاج المتكرر من نفس النوع"
            ])
        ])
        
        # نصائح سريعة
        self.add_section(content_layout, "نصائح سريعة للبدء", [
            ("للحصول على أفضل عمر للبطارية:", [
                "1. فعّل 'التحكم في الشحن' من الإعدادات (يحتاج صلاحيات مسؤول)",
                "2. اضبط الحدود الموصى بها: 40% حد أدنى - 80% حد أقصى",
                "3. سيتوقف الشحن تلقائياً عند 80% ويبدأ عند 40%"
            ]),
            ("للعمل في الخلفية بشكل دائم:", [
                "1. فعّل 'التشغيل التلقائي' من الإعدادات",
                "2. فعّل 'وضع الخلفية' للبدء مصغراً",
                "3. فعّل 'التصغير إلى الصينية' عند إغلاق النافذة"
            ]),
            ("وضع الطاقة الافتراضي:", [
                "متوازن (Balanced) - توازن بين الأداء وعمر البطارية",
                "يمكنك تغييره إلى: موفر للطاقة أو أداء عالي"
            ]),
            ("الذكاء الاصطناعي:", [
                "التوصيات الذكية مفعّلة - تحليل أنماط الاستخدام",
                "التعلم التلقائي مفعّل - تحسين مستمر بناءً على عاداتك",
                "كلما استخدمت التطبيق أكثر، أصبحت التوصيات أدق"
            ])
        ])
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll, 1)
        
        # خط فاصل
        separator2 = QWidget()
        separator2.setFixedHeight(2)
        separator2.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(separator2)
        
        # خيار عدم الإظهار مرة أخرى
        self.dont_show_again = QCheckBox("لا تظهر هذه الرسالة مرة أخرى")
        self.dont_show_again.setFont(QFont('Arial', 10))
        layout.addWidget(self.dont_show_again)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        # زر الإعدادات
        settings_btn = QPushButton("فتح الإعدادات")
        settings_btn.setFont(QFont('Arial', 11))
        settings_btn.setMinimumHeight(40)
        settings_btn.setMinimumWidth(150)
        settings_btn.clicked.connect(self.open_settings)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        buttons_layout.addWidget(settings_btn)
        
        # زر البدء
        start_btn = QPushButton("ابدأ الآن")
        start_btn.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        start_btn.setMinimumHeight(40)
        start_btn.setMinimumWidth(150)
        start_btn.clicked.connect(self.accept)
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        buttons_layout.addWidget(start_btn)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def add_section(self, layout, title, items):
        """إضافة قسم"""
        # عنوان القسم
        section_title = QLabel(title)
        section_title.setFont(QFont('Arial', 13, QFont.Weight.Bold))
        section_title.setStyleSheet("color: #1f2937; padding: 10px 0 5px 0;")
        layout.addWidget(section_title)
        
        # محتوى القسم
        for subtitle, points in items:
            if subtitle:
                subtitle_label = QLabel(subtitle)
                subtitle_label.setFont(QFont('Arial', 11, QFont.Weight.Bold))
                subtitle_label.setStyleSheet("color: #4b5563; padding: 5px 0;")
                layout.addWidget(subtitle_label)
            
            for point in points:
                point_label = QLabel(f"  • {point}")
                point_label.setFont(QFont('Arial', 10))
                point_label.setStyleSheet("color: #6b7280; padding: 2px 0 2px 20px;")
                point_label.setWordWrap(True)
                layout.addWidget(point_label)
    
    def open_settings(self):
        """فتح الإعدادات"""
        self.done(2)  # رمز خاص لفتح الإعدادات
    
    def should_show_again(self):
        """هل يجب إظهار النافذة مرة أخرى"""
        return not self.dont_show_again.isChecked()


# اختبار سريع
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    dialog = WelcomeDialog()
    result = dialog.exec()
    
    if result == 2:
        print("المستخدم اختار فتح الإعدادات")
    elif result == 1:
        print("المستخدم اختار البدء")
    else:
        print("المستخدم أغلق النافذة")
    
    print(f"إظهار مرة أخرى: {dialog.should_show_again()}")
    
    sys.exit(0)
