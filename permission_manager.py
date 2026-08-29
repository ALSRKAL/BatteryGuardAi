#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مدير الصلاحيات - طلب الصلاحيات من داخل التطبيق"""

import sys
import os
import subprocess
import logging
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

logger = logging.getLogger('BatteryGuard')


class PermissionManager:
    """مدير الصلاحيات"""
    
    def __init__(self):
        self.has_admin_rights = False
        self.sudo_password = None
        self.permission_requested = False  # علامة لتتبع طلب الصلاحيات
        self._check_current_permissions()
    
    def _check_current_permissions(self):
        """التحقق من الصلاحيات الحالية"""
        if IS_WINDOWS:
            try:
                import ctypes
                self.has_admin_rights = ctypes.windll.shell32.IsUserAnAdmin() != 0
                if self.has_admin_rights:
                    logger.info("يعمل بصلاحيات المسؤول (Windows)")
            except:
                self.has_admin_rights = False
        
        elif IS_LINUX:
            # التحقق من متغير البيئة أولاً
            if os.environ.get('BATTERYGUARD_SUDO_VERIFIED') == '1':
                self.has_admin_rights = True
                logger.info("صلاحيات sudo محفوظة في الجلسة")
                return
            
            # التحقق من إمكانية الكتابة إلى ملفات النظام
            threshold_path = Path('/sys/class/power_supply/BAT0/charge_control_end_threshold')
            if threshold_path.exists():
                try:
                    with open(threshold_path, 'r') as f:
                        f.read()
                    # محاولة الكتابة
                    test_value = threshold_path.read_text().strip()
                    with open(threshold_path, 'w') as f:
                        f.write(test_value)
                    self.has_admin_rights = True
                    logger.info("صلاحيات كتابة متاحة مباشرة")
                except PermissionError:
                    self.has_admin_rights = False
                except:
                    self.has_admin_rights = False
    
    def request_permissions(self, parent_widget=None) -> bool:
        """طلب الصلاحيات من المستخدم (مرة واحدة فقط)"""
        # إذا تم طلب الصلاحيات من قبل، لا نطلبها مرة أخرى
        if self.permission_requested:
            return self.has_admin_rights
        
        self.permission_requested = True
        
        if self.has_admin_rights:
            return True
        
        if IS_WINDOWS:
            return self._request_windows_admin(parent_widget)
        elif IS_LINUX:
            return self._request_linux_sudo(parent_widget)
        
        return False
    
    def _request_windows_admin(self, parent_widget) -> bool:
        """طلب صلاحيات المسؤول في Windows"""
        msg = QMessageBox(parent_widget)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("صلاحيات المسؤول")
        msg.setText("للتحكم الكامل في الشحن، يحتاج التطبيق إلى صلاحيات المسؤول")
        msg.setInformativeText("هل تريد إعادة تشغيل التطبيق كمسؤول؟")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            try:
                import ctypes
                # إعادة تشغيل التطبيق بصلاحيات المسؤول
                script = os.path.abspath(sys.argv[0])
                params = ' '.join(sys.argv[1:])
                
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, f'"{script}" {params}', None, 1
                )
                
                # إغلاق التطبيق الحالي
                sys.exit(0)
            except Exception as e:
                logger.error(f"فشل طلب صلاحيات المسؤول: {e}")
                QMessageBox.warning(
                    parent_widget,
                    "خطأ",
                    "فشل الحصول على صلاحيات المسؤول. سيعمل التطبيق بصلاحيات محدودة."
                )
                return False
        
        return False
    
    def _request_linux_sudo(self, parent_widget) -> bool:
        """طلب كلمة مرور sudo في Linux"""
        logger.info("عرض نافذة طلب صلاحيات sudo...")
        
        dialog = SudoPasswordDialog(parent_widget)
        dialog.show()  # إظهار النافذة أولاً
        dialog.raise_()  # رفعها للأمام
        dialog.activateWindow()  # تفعيلها
        
        result = dialog.exec()
        logger.info(f"نتيجة نافذة sudo: {result}")
        
        if result == QDialog.DialogCode.Accepted:
            password = dialog.get_password()
            
            if not password:
                # المستخدم لم يدخل كلمة مرور
                return False
            
            # اختبار كلمة المرور
            if self._test_sudo_password(password):
                self.sudo_password = password
                self.has_admin_rights = True
                logger.info("تم الحصول على صلاحيات sudo بنجاح")
                
                # حفظ في متغير بيئة الجلسة (آمن)
                os.environ['BATTERYGUARD_SUDO_VERIFIED'] = '1'
                
                return True
            else:
                QMessageBox.warning(
                    parent_widget,
                    "خطأ",
                    "كلمة المرور غير صحيحة أو لا تملك صلاحيات sudo"
                )
                self.permission_requested = False  # السماح بالمحاولة مرة أخرى
                return False
        
        return False
    
    def _test_sudo_password(self, password: str) -> bool:
        """اختبار كلمة مرور sudo"""
        try:
            # اختبار بسيط: تشغيل أمر sudo echo
            # استخدام -S لقراءة كلمة المرور من stdin
            # استخدام -p '' لإخفاء prompt
            process = subprocess.Popen(
                ['sudo', '-S', '-p', '', 'echo', 'test'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, 'SUDO_ASKPASS': '/bin/false'}  # منع أي GUI prompts
            )
            
            # إرسال كلمة المرور مع newline
            stdout, stderr = process.communicate(input=f"{password}\n", timeout=5)
            
            # التحقق من النجاح
            success = process.returncode == 0
            
            if not success:
                logger.debug(f"فشل اختبار sudo: stderr={stderr}")
            
            return success
        
        except Exception as e:
            logger.error(f"خطأ في اختبار sudo: {e}")
            return False
    
    def get_sudo_password(self) -> str:
        """الحصول على كلمة مرور sudo المحفوظة"""
        return self.sudo_password


class SudoPasswordDialog(QDialog):
    """نافذة طلب كلمة مرور sudo"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("صلاحيات المسؤول")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)
        
        # جعل النافذة دائماً في المقدمة
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        self.setup_ui()
        
        # وضع النافذة في وسط الشاشة
        self.center_on_screen()
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # العنوان
        title = QLabel("صلاحيات المسؤول")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: 700;
            color: #ffffff;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # الوصف
        desc = QLabel("للتحكم الكامل في الشحن، يحتاج التطبيق إلى صلاحيات sudo.\nالرجاء إدخال كلمة المرور:")
        desc.setStyleSheet("""
            font-size: 14px;
            color: #cbd5e1;
        """)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        
        # حقل كلمة المرور
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("كلمة المرور")
        self.password_input.setMinimumHeight(45)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 15px;
                border: 2px solid #334155;
                border-radius: 8px;
                background-color: #1e293b;
                color: #ffffff;
                font-size: 15px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.password_input.returnPressed.connect(self.accept)
        layout.addWidget(self.password_input)
        
        # الأزرار
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        ok_button = QPushButton("تأكيد")
        ok_button.setMinimumHeight(45)
        ok_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #047857);
            }
        """)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("إلغاء")
        cancel_button.setMinimumHeight(45)
        cancel_button.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #475569;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # تطبيق النمط العام
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e293b, stop:1 #0f172a);
            }
        """)
    
    def center_on_screen(self):
        """وضع النافذة في وسط الشاشة"""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def get_password(self) -> str:
        """الحصول على كلمة المرور المدخلة"""
        return self.password_input.text()
