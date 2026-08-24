#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نظام Single Instance - منع تشغيل نسخ متعددة من البرنامج"""

import sys
import os
import socket
import zlib
import logging
from pathlib import Path

logger = logging.getLogger('BatteryGuard')

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')


def _deterministic_port(app_name: str) -> int:
    """
    منفذ حتمي من اسم التطبيق.
    ملاحظة: دالة hash() في Python تختلف بين الجلسات (PYTHONHASHSEED)،
    لذا استخدمنا CRC32 لضمان ثبات المنفذ عبر عمليات الإعادة التشغيل.
    """
    return 50000 + zlib.crc32(app_name.encode('utf-8')) % 10000


class SingleInstance:
    """نظام لضمان تشغيل نسخة واحدة فقط من البرنامج"""
    
    def __init__(self, app_name='BatteryGuardPro', port=None):
        self.app_name = app_name
        self.socket = None
        self.is_running = False
        
        # تحديد المنفذ
        self.port = port or _deterministic_port(app_name)
        
        # ملف القفل (Lock file)
        if IS_WINDOWS:
            self.lock_file = Path(os.environ.get('TEMP', '.')) / f'{app_name}.lock'
        else:
            self.lock_file = Path(f'/tmp/{app_name}.lock')
        
        # محاولة الحصول على القفل
        self._acquire_lock()
    
    def _acquire_lock(self):
        """محاولة الحصول على القفل"""
        try:
            # الطريقة 1: استخدام Socket (الأفضل)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                # محاولة ربط المنفذ
                self.socket.bind(('127.0.0.1', self.port))
                self.socket.listen(1)
                self.is_running = False
                logger.info(f"✅ تم الحصول على القفل - المنفذ: {self.port}")
                
                # كتابة معلومات العملية في ملف القفل
                self._write_lock_file()
                
            except OSError as e:
                # المنفذ مستخدم - البرنامج يعمل بالفعل
                self.is_running = True
                self.socket.close()
                self.socket = None
                logger.warning(f"⚠️ البرنامج يعمل بالفعل - المنفذ {self.port} مستخدم")
                
                # التحقق من ملف القفل
                if self.lock_file.exists():
                    try:
                        with open(self.lock_file, 'r') as f:
                            info = f.read()
                            logger.info(f"معلومات النسخة العاملة: {info}")
                    except Exception:
                        pass
        
        except Exception as e:
            logger.error(f"خطأ في الحصول على القفل: {e}")
            self.is_running = True
    
    def _write_lock_file(self):
        """كتابة معلومات العملية في ملف القفل"""
        try:
            pid = os.getpid()
            with open(self.lock_file, 'w') as f:
                f.write(f"PID: {pid}\n")
                f.write(f"Port: {self.port}\n")
                f.write(f"App: {self.app_name}\n")
        except Exception as e:
            logger.warning(f"تعذر كتابة ملف القفل: {e}")
    
    def is_already_running(self):
        """التحقق من وجود نسخة أخرى تعمل"""
        return self.is_running
    
    def show_existing_instance(self):
        """محاولة إظهار النسخة العاملة"""
        try:
            # إرسال إشارة للنسخة العاملة لإظهار النافذة
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(2)
            client_socket.connect(('127.0.0.1', self.port))
            client_socket.send(b'SHOW')
            client_socket.close()
            logger.info("✅ تم إرسال إشارة لإظهار النافذة")
            return True
        except Exception as e:
            logger.warning(f"تعذر إرسال إشارة للنسخة العاملة: {e}")
            return False
    
    def start_listening(self, callback=None):
        """بدء الاستماع للإشارات من نسخ أخرى"""
        if not self.socket:
            return
        
        import threading
        
        # إشارة إظهار النافذة (تُستقبل في خيط الاستماع وتُعالج بأمان)
        self.show_requested = False
        self._callback = callback
        
        def listen():
            try:
                while not getattr(self, '_stop_listening', False):
                    try:
                        client, addr = self.socket.accept()
                        data = client.recv(1024)
                        
                        if data == b'SHOW':
                            # لا تستدعي دوال الواجهة من هنا مباشرة؛
                            # ارفع الطلب ليقرر الخيط الرئيسي (انظر main.py)
                            logger.info("📢 تم استقبال طلب لإظهار النافذة")
                            if hasattr(self, 'on_show_request'):
                                try:
                                    self.on_show_request()
                                except Exception as e:
                                    logger.error(f"خطأ في معالج الإظهار: {e}")
                        client.close()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
            except Exception as e:
                logger.error(f"خطأ في الاستماع: {e}")
        
        self.socket.settimeout(1.0)
        listener_thread = threading.Thread(target=listen, daemon=True)
        listener_thread.start()
        self._listener_thread = listener_thread
    
    def release(self):
        """تحرير القفل"""
        try:
            self._stop_listening = True
            if self.socket:
                self.socket.close()
                self.socket = None
            
            # حذف ملف القفل
            if self.lock_file.exists():
                try:
                    self.lock_file.unlink()
                except Exception:
                    pass
            
            logger.info("✅ تم تحرير القفل")
        except Exception as e:
            logger.error(f"خطأ في تحرير القفل: {e}")
    
    def __del__(self):
        """تحرير القفل عند حذف الكائن"""
        self.release()
    
    def __enter__(self):
        """دعم context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """تحرير القفل عند الخروج من context"""
        self.release()


class SingleInstanceChecker:
    """فاحص بسيط للتحقق من وجود نسخة واحدة"""
    
    @staticmethod
    def check_and_prevent_duplicate(app_name='BatteryGuardPro'):
        """
        التحقق من وجود نسخة أخرى ومنع التكرار
        
        Returns:
            tuple: (is_duplicate, instance_manager)
                - is_duplicate: True إذا كانت هناك نسخة أخرى تعمل
                - instance_manager: كائن SingleInstance للإدارة
        """
        instance = SingleInstance(app_name)
        
        if instance.is_already_running():
            return True, instance
        
        return False, instance
    
    @staticmethod
    def get_running_instances_count(app_name='BatteryGuardPro'):
        """الحصول على عدد النسخ العاملة"""
        try:
            if IS_LINUX:
                import subprocess
                result = subprocess.run(
                    ['pgrep', '-f', app_name],
                    capture_output=True,
                    text=True
                )
                pids = result.stdout.strip().split('\n')
                return len([p for p in pids if p])
            
            elif IS_WINDOWS:
                import subprocess
                result = subprocess.run(
                    ['tasklist', '/FI', f'IMAGENAME eq python*', '/FO', 'CSV'],
                    capture_output=True,
                    text=True
                )
                # تقدير تقريبي
                return result.stdout.count('python')
        except:
            return 0
    
    @staticmethod
    def kill_other_instances(app_name='BatteryGuardPro', keep_current=True):
        """إيقاف النسخ الأخرى (استخدم بحذر!)"""
        try:
            current_pid = os.getpid()
            
            if IS_LINUX:
                import subprocess
                result = subprocess.run(
                    ['pgrep', '-f', app_name],
                    capture_output=True,
                    text=True
                )
                pids = result.stdout.strip().split('\n')
                
                killed = 0
                for pid_str in pids:
                    if pid_str:
                        pid = int(pid_str)
                        if not keep_current or pid != current_pid:
                            try:
                                os.kill(pid, 9)  # SIGKILL
                                killed += 1
                            except:
                                pass
                
                return killed
            
            elif IS_WINDOWS:
                # في Windows، يُفضل عدم إيقاف العمليات تلقائياً
                logger.warning("إيقاف العمليات تلقائياً غير مدعوم في Windows")
                return 0
        
        except Exception as e:
            logger.error(f"خطأ في إيقاف النسخ الأخرى: {e}")
            return 0


def test_single_instance():
    """اختبار نظام Single Instance"""
    print("=" * 60)
    print("🧪 اختبار نظام Single Instance")
    print("=" * 60)
    
    # الاختبار 1: إنشاء نسخة أولى
    print("\n1️⃣ إنشاء النسخة الأولى...")
    instance1 = SingleInstance('TestApp')
    
    if instance1.is_already_running():
        print("❌ خطأ: النسخة الأولى تعتقد أن هناك نسخة أخرى!")
    else:
        print("✅ النسخة الأولى تعمل بنجاح")
    
    # الاختبار 2: محاولة إنشاء نسخة ثانية
    print("\n2️⃣ محاولة إنشاء نسخة ثانية...")
    instance2 = SingleInstance('TestApp')
    
    if instance2.is_already_running():
        print("✅ تم اكتشاف النسخة الأولى بنجاح")
        print("   محاولة إظهار النسخة الأولى...")
        instance2.show_existing_instance()
    else:
        print("❌ خطأ: لم يتم اكتشاف النسخة الأولى!")
    
    # الاختبار 3: تحرير القفل
    print("\n3️⃣ تحرير القفل...")
    instance1.release()
    print("✅ تم تحرير القفل")
    
    # الاختبار 4: محاولة إنشاء نسخة بعد التحرير
    print("\n4️⃣ محاولة إنشاء نسخة بعد التحرير...")
    instance3 = SingleInstance('TestApp')
    
    if instance3.is_already_running():
        print("❌ خطأ: لا يزال يعتقد أن هناك نسخة أخرى!")
    else:
        print("✅ تم إنشاء نسخة جديدة بنجاح")
    
    instance3.release()
    
    print("\n" + "=" * 60)
    print("✅ اكتمل الاختبار")
    print("=" * 60)


if __name__ == '__main__':
    # تشغيل الاختبار
    test_single_instance()
