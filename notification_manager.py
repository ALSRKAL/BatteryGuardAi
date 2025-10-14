#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مدير الإشعارات الذكي المتقدم عبر المنصات مع الأصوات والتذكيرات"""

import sys
import logging
import time
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

logger = logging.getLogger('BatteryGuard')

# استيراد المكتبات حسب النظام
if IS_WINDOWS:
    try:
        from plyer import notification as plyer_notification
        import winsound
        PLYER_AVAILABLE = True
        SOUND_AVAILABLE = True
    except ImportError:
        PLYER_AVAILABLE = False
        SOUND_AVAILABLE = False
        logger.warning("plyer not available - using fallback")
elif IS_LINUX:
    try:
        import gi
        gi.require_version('Notify', '0.7')
        from gi.repository import Notify
        NOTIFY_AVAILABLE = True
    except (ImportError, ValueError):
        NOTIFY_AVAILABLE = False
        try:
            from plyer import notification as plyer_notification
            PLYER_AVAILABLE = True
        except ImportError:
            PLYER_AVAILABLE = False
            logger.warning("No notification system available")
    
    # التحقق من وجود أدوات الصوت في Linux
    try:
        subprocess.run(['which', 'paplay'], check=True, capture_output=True)
        SOUND_AVAILABLE = True
    except:
        try:
            subprocess.run(['which', 'aplay'], check=True, capture_output=True)
            SOUND_AVAILABLE = True
        except:
            SOUND_AVAILABLE = False


class SmartNotificationManager:
    """مدير الإشعارات الذكي المتقدم مع الأصوات والتذكيرات"""
    
    def __init__(self):
        self.enabled = True
        self.notification_history = []
        self.last_notification_time = {}
        self.notification_cooldown = 300  # 5 دقائق افتراضياً
        self.smart_timing_enabled = True
        self.ai_recommendations_enabled = True
        self.priority_queue = []
        
        # إعدادات التذكيرات الذكية
        self.reminders_enabled = True
        self.reminder_intervals = {
            'battery_low': 300,      # 5 دقائق
            'battery_critical': 60,  # دقيقة واحدة
            'charge_complete': 600,  # 10 دقائق
            'unplug_charger': 300    # 5 دقائق
        }
        self.active_reminders = {}
        self.reminder_threads = {}
        
        # إعدادات الأصوات
        self.sound_enabled = True
        self.sound_volume = 0.7
        self.sound_files = {
            'critical': 'sounds/new-notification-010-352755.mp3',      # صوت حرج - بطارية منخفضة جداً
            'warning': 'sounds/new-notification-05-352453.mp3',        # صوت تحذير - بطارية منخفضة
            'info': 'sounds/new-notification-021-370045.mp3',          # صوت معلومات - إشعارات عامة
            'success': 'sounds/new-notification-022-370046.mp3',       # صوت نجاح - اكتمال الشحن
            'optimization': 'sounds/new-notification-024-370048.mp3'   # صوت تحسين - عمليات التحسين
        }
        
        # إعدادات الحدود القابلة للتخصيص
        self.battery_thresholds = {
            'critical_low': 10,      # حرج
            'low': 20,              # منخفض
            'optimal_min': 40,      # الحد الأدنى الأمثل
            'optimal_max': 80,      # الحد الأعلى الأمثل
            'high': 90,             # مرتفع
            'full': 95              # ممتلئ
        }
        
        # إعدادات التنبيهات الذكية
        self.smart_alerts = {
            'charger_disconnect_reminder': True,
            'optimal_charge_reminder': True,
            'health_warnings': True,
            'usage_pattern_alerts': True,
            'temperature_warnings': True
        }
        
        # تهيئة النظام
        self._initialize_system()
        self._create_sound_files()
        
        # إحصائيات
        self.stats = {
            'total_sent': 0,
            'total_suppressed': 0,
            'reminders_sent': 0,
            'sounds_played': 0,
            'by_type': {},
            'by_priority': {}
        }
    
    def _initialize_system(self):
        """تهيئة نظام الإشعارات"""
        if IS_LINUX and NOTIFY_AVAILABLE:
            try:
                Notify.init("BatteryGuard Pro")
                self.notification_method = 'notify'
                logger.info("✅ نظام الإشعارات: Notify (Linux)")
            except:
                self.notification_method = 'plyer' if PLYER_AVAILABLE else 'none'
        elif PLYER_AVAILABLE:
            self.notification_method = 'plyer'
            logger.info("✅ نظام الإشعارات: Plyer")
        else:
            self.notification_method = 'none'
            self.enabled = False
            logger.warning("⚠️ لا يوجد نظام إشعارات متاح")
        
        # تهيئة نظام الأصوات
        if SOUND_AVAILABLE:
            logger.info("✅ نظام الأصوات: متاح")
        else:
            logger.warning("⚠️ نظام الأصوات غير متاح")
    
    def _create_sound_files(self):
        """إنشاء ملفات الأصوات الافتراضية"""
        sounds_dir = Path('sounds')
        sounds_dir.mkdir(exist_ok=True)
        
        # تم تعطيل توليد أصوات النظام - نستخدم الأصوات المخصصة MP3
        # جميع الأصوات موجودة في مجلد sounds/ كملفات MP3
        pass
    
    def _generate_system_sound(self, sound_type: str):
        """توليد أصوات النظام"""
        try:
            if IS_WINDOWS and SOUND_AVAILABLE:
                # استخدام أصوات Windows المدمجة
                sounds = {
                    'critical': 'SystemHand',
                    'warning': 'SystemExclamation', 
                    'info': 'SystemAsterisk',
                    'success': 'SystemDefault'
                }
                # حفظ مرجع للصوت
                self.sound_files[sound_type] = sounds.get(sound_type, 'SystemDefault')
            
            elif IS_LINUX:
                # استخدام أصوات Linux المدمجة
                sounds = {
                    'critical': '/usr/share/sounds/alsa/Front_Left.wav',
                    'warning': '/usr/share/sounds/alsa/Front_Right.wav',
                    'info': '/usr/share/sounds/alsa/Rear_Left.wav',
                    'success': '/usr/share/sounds/alsa/Rear_Right.wav'
                }
                
                # البحث عن أصوات النظام
                system_sounds = [
                    '/usr/share/sounds/freedesktop/stereo/',
                    '/usr/share/sounds/gnome/default/alerts/',
                    '/usr/share/sounds/ubuntu/stereo/'
                ]
                
                for sound_dir in system_sounds:
                    if Path(sound_dir).exists():
                        sound_files = list(Path(sound_dir).glob('*.ogg')) + list(Path(sound_dir).glob('*.wav'))
                        if sound_files:
                            self.sound_files[sound_type] = str(sound_files[0])
                            break
        except Exception as e:
            logger.debug(f"تعذر إنشاء صوت {sound_type}: {e}")
    
    def play_sound(self, sound_type: str = 'info'):
        """تشغيل صوت الإشعار - يدعم MP3 و WAV"""
        if not self.sound_enabled:
            return
        
        try:
            sound_file = self.sound_files.get(sound_type)
            if not sound_file:
                logger.debug(f"لا يوجد ملف صوت لـ {sound_type}")
                return
            
            sound_path = Path(sound_file)
            if not sound_path.exists():
                logger.debug(f"ملف الصوت غير موجود: {sound_file}")
                return
            
            if IS_WINDOWS:
                # تشغيل أصوات Windows (MP3 و WAV)
                try:
                    # استخدام pygame للـ MP3
                    try:
                        import pygame
                        if not pygame.mixer.get_init():
                            pygame.mixer.init()
                        sound = pygame.mixer.Sound(str(sound_path))
                        sound.set_volume(self.sound_volume)
                        sound.play()
                    except ImportError:
                        # استخدام winsound للـ WAV فقط
                        if sound_file.endswith('.wav'):
                            import winsound
                            winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                        else:
                            # استخدام Windows Media Player كبديل
                            subprocess.Popen(['powershell', '-c', 
                                            f'(New-Object Media.SoundPlayer "{sound_path}").PlaySync()'],
                                           stdout=subprocess.DEVNULL, 
                                           stderr=subprocess.DEVNULL)
                except Exception as e:
                    logger.debug(f"خطأ في تشغيل الصوت على Windows: {e}")
            
            elif IS_LINUX:
                # تشغيل أصوات Linux (MP3 و WAV و OGG)
                # محاولة استخدام mpg123 للـ MP3
                if sound_file.endswith('.mp3'):
                    try:
                        subprocess.Popen(['mpg123', '-q', str(sound_path)], 
                                       stdout=subprocess.DEVNULL, 
                                       stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        # استخدام ffplay كبديل
                        try:
                            subprocess.Popen(['ffplay', '-nodisp', '-autoexit', '-v', 'quiet', str(sound_path)], 
                                           stdout=subprocess.DEVNULL, 
                                           stderr=subprocess.DEVNULL)
                        except FileNotFoundError:
                            # استخدام paplay مع تحويل
                            try:
                                subprocess.Popen(['paplay', str(sound_path)], 
                                               stdout=subprocess.DEVNULL, 
                                               stderr=subprocess.DEVNULL)
                            except:
                                logger.debug("لم يتم العثور على مشغل صوت مناسب")
                else:
                    # WAV أو OGG
                    try:
                        subprocess.Popen(['paplay', str(sound_path)], 
                                       stdout=subprocess.DEVNULL, 
                                       stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        try:
                            subprocess.Popen(['aplay', str(sound_path)], 
                                           stdout=subprocess.DEVNULL, 
                                           stderr=subprocess.DEVNULL)
                        except:
                            pass
            
            self.stats['sounds_played'] += 1
            logger.debug(f"✅ تم تشغيل الصوت: {sound_type}")
            
        except Exception as e:
            logger.debug(f"تعذر تشغيل الصوت {sound_type}: {e}")
    
    def start_reminder(self, reminder_type: str, condition_check: Callable, 
                      notification_data: Dict, interval: Optional[int] = None):
        """بدء تذكير ذكي مع شرط"""
        if not self.reminders_enabled:
            return
        
        # إيقاف التذكير السابق إن وجد
        self.stop_reminder(reminder_type)
        
        # تحديد الفترة الزمنية
        reminder_interval = interval or self.reminder_intervals.get(reminder_type, 300)
        
        # إنشاء خيط التذكير
        def reminder_loop():
            while reminder_type in self.active_reminders:
                try:
                    # التحقق من الشرط
                    if condition_check():
                        # إرسال التذكير
                        self.send_notification(
                            title=notification_data['title'],
                            message=notification_data['message'],
                            urgency=notification_data.get('urgency', 'normal'),
                            notification_type=f"reminder_{reminder_type}",
                            play_sound=notification_data.get('play_sound', True)
                        )
                        self.stats['reminders_sent'] += 1
                    else:
                        # الشرط لم يعد صحيحاً، إيقاف التذكير
                        break
                    
                    # انتظار الفترة المحددة
                    time.sleep(reminder_interval)
                    
                except Exception as e:
                    logger.error(f"خطأ في تذكير {reminder_type}: {e}")
                    break
            
            # تنظيف التذكير
            if reminder_type in self.active_reminders:
                del self.active_reminders[reminder_type]
            if reminder_type in self.reminder_threads:
                del self.reminder_threads[reminder_type]
        
        # بدء التذكير
        self.active_reminders[reminder_type] = True
        thread = threading.Thread(target=reminder_loop, daemon=True)
        thread.start()
        self.reminder_threads[reminder_type] = thread
        
        logger.info(f"🔔 بدء تذكير: {reminder_type} (كل {reminder_interval} ثانية)")
    
    def stop_reminder(self, reminder_type: str):
        """إيقاف تذكير محدد"""
        if reminder_type in self.active_reminders:
            del self.active_reminders[reminder_type]
            logger.info(f"⏹️ إيقاف تذكير: {reminder_type}")
    
    def stop_all_reminders(self):
        """إيقاف جميع التذكيرات"""
        for reminder_type in list(self.active_reminders.keys()):
            self.stop_reminder(reminder_type)
        logger.info("⏹️ تم إيقاف جميع التذكيرات")
    
    def send_notification(self, title: str, message: str, urgency: str = 'normal', 
                         notification_type: str = 'general', ai_priority: int = 5,
                         play_sound: bool = True, persistent: bool = False):
        """إرسال إشعار ذكي مع تحكم متقدم وأصوات"""
        if not self.enabled:
            return False
        
        # التحقق من التوقيت الذكي
        if not self._should_send_notification(notification_type, urgency):
            self.stats['total_suppressed'] += 1
            logger.debug(f"تم منع الإشعار: {title} (توقيت غير مناسب)")
            return False
        
        # إضافة إلى قائمة الأولوية
        notification = {
            'title': title,
            'message': message,
            'urgency': urgency,
            'type': notification_type,
            'ai_priority': ai_priority,
            'play_sound': play_sound,
            'persistent': persistent,
            'timestamp': datetime.now().isoformat()
        }
        
        # إرسال فوري للإشعارات الحرجة
        if urgency == 'critical':
            return self._send_immediate(notification)
        
        # إضافة للقائمة والإرسال
        self.priority_queue.append(notification)
        return self._send_immediate(notification)
    
    def _should_send_notification(self, notification_type: str, urgency: str) -> bool:
        """تحديد ما إذا كان يجب إرسال الإشعار (ذكي)"""
        # الإشعارات الحرجة دائماً
        if urgency == 'critical':
            return True
        
        # التحقق من الفترة الزمنية
        last_time = self.last_notification_time.get(notification_type, 0)
        current_time = time.time()
        
        if current_time - last_time < self.notification_cooldown:
            return False
        
        # التوقيت الذكي (تجنب الإزعاج)
        if self.smart_timing_enabled:
            current_hour = datetime.now().hour
            # تجنب الإشعارات في ساعات النوم (1-6 صباحاً)
            if 1 <= current_hour <= 6 and urgency != 'critical':
                return False
        
        return True
    
    def _send_immediate(self, notification: Dict) -> bool:
        """إرسال الإشعار فوراً مع الصوت"""
        try:
            title = notification['title']
            message = notification['message']
            urgency = notification['urgency']
            notification_type = notification['type']
            play_sound = notification.get('play_sound', True)
            persistent = notification.get('persistent', False)
            
            # تشغيل الصوت أولاً
            if play_sound:
                sound_type = self._get_sound_type(urgency, notification_type)
                self.play_sound(sound_type)
            
            # اختيار الأيقونة المناسبة
            icon = self._get_icon_for_type(notification_type, urgency)
            
            # الإرسال حسب النظام
            if self.notification_method == 'notify' and IS_LINUX:
                notif = Notify.Notification.new(title, message, icon)
                
                # تعيين الأولوية
                if urgency == 'critical':
                    notif.set_urgency(Notify.Urgency.CRITICAL)
                elif urgency == 'low':
                    notif.set_urgency(Notify.Urgency.LOW)
                else:
                    notif.set_urgency(Notify.Urgency.NORMAL)
                
                # تعيين المدة
                if persistent or urgency == 'critical':
                    notif.set_timeout(0)  # دائم حتى النقر
                elif urgency == 'critical':
                    notif.set_timeout(15000)  # 15 ثانية
                else:
                    notif.set_timeout(7000)   # 7 ثواني
                
                # إضافة أزرار للإشعارات المهمة
                if urgency == 'critical' and 'battery' in notification_type:
                    notif.add_action('dismiss', 'تم', lambda *args: None)
                
                notif.show()
            
            elif self.notification_method == 'plyer':
                timeout = 15 if urgency == 'critical' else 7
                if persistent:
                    timeout = 0
                
                plyer_notification.notify(
                    title=title,
                    message=message,
                    app_name='BatteryGuard Pro',
                    timeout=timeout,
                    app_icon=icon if Path(icon).exists() else None
                )
            
            # تحديث الإحصائيات
            self.stats['total_sent'] += 1
            self.stats['by_type'][notification_type] = self.stats['by_type'].get(notification_type, 0) + 1
            self.stats['by_priority'][urgency] = self.stats['by_priority'].get(urgency, 0) + 1
            
            # تحديث وقت آخر إشعار
            self.last_notification_time[notification_type] = time.time()
            
            # حفظ في السجل
            self.notification_history.append(notification)
            if len(self.notification_history) > 100:
                self.notification_history = self.notification_history[-100:]
            
            logger.info(f"✅ إشعار: {title} (صوت: {'نعم' if play_sound else 'لا'})")
            return True
        
        except Exception as e:
            logger.error(f"❌ خطأ في إرسال الإشعار: {e}")
            return False
    
    def _get_sound_type(self, urgency: str, notification_type: str) -> str:
        """تحديد نوع الصوت المناسب - توزيع ذكي للأصوات الخمسة"""
        # صوت حرج (new-notification-010-352755.mp3)
        if urgency == 'critical' or 'critical' in notification_type:
            return 'critical'
        
        # صوت تحذير (new-notification-05-352453.mp3)
        elif urgency == 'high' or 'warning' in notification_type or 'low' in notification_type:
            return 'warning'
        
        # صوت نجاح (new-notification-022-370046.mp3)
        elif 'success' in notification_type or 'complete' in notification_type or 'full' in notification_type:
            return 'success'
        
        # صوت تحسين (new-notification-024-370048.mp3)
        elif 'optimization' in notification_type or 'optimizer' in notification_type or 'improve' in notification_type:
            return 'optimization'
        
        # صوت معلومات (new-notification-021-370045.mp3) - الافتراضي
        else:
            return 'info'
    
    def _get_icon_for_type(self, notification_type: str, urgency: str) -> str:
        """الحصول على الأيقونة المناسبة"""
        if urgency == 'critical':
            return 'dialog-warning'
        elif notification_type == 'battery_low':
            return 'battery-caution'
        elif notification_type == 'battery_full':
            return 'battery-full'
        elif notification_type == 'charging':
            return 'battery-charging'
        else:
            return 'dialog-information'
    
    def send_ai_recommendation(self, recommendation: str, priority: int = 5):
        """إرسال توصية من الذكاء الاصطناعي"""
        if not self.ai_recommendations_enabled:
            return False
        
        return self.send_notification(
            title="🤖 توصية ذكية",
            message=recommendation,
            urgency='normal',
            notification_type='ai_recommendation',
            ai_priority=priority
        )
    
    def send_optimization_notification(self, optimization_type: str, power_saved: float = 0):
        """إرسال إشعار التحسين مع الصوت المناسب"""
        messages = {
            'started': {
                'title': '🚀 بدء التحسين',
                'message': 'جارٍ تحسين النظام لتوفير الطاقة...',
                'urgency': 'low'
            },
            'completed': {
                'title': '✅ اكتمل التحسين',
                'message': f'تم التحسين بنجاح! توفير: {power_saved:.1f}% طاقة',
                'urgency': 'normal'
            },
            'auto_started': {
                'title': '🤖 تحسين تلقائي',
                'message': 'تم اكتشاف حاجة للتحسين - جارٍ التحسين...',
                'urgency': 'low'
            },
            'auto_completed': {
                'title': '✅ تحسين تلقائي ناجح',
                'message': f'تم التحسين التلقائي! توفير: {power_saved:.1f}% طاقة',
                'urgency': 'normal'
            }
        }
        
        notification_data = messages.get(optimization_type, messages['completed'])
        
        return self.send_notification(
            title=notification_data['title'],
            message=notification_data['message'],
            urgency=notification_data['urgency'],
            notification_type='optimization',
            play_sound=True
        )
    
    def send_smart_alert(self, alert_type: str, data: Dict):
        """إرسال تنبيه ذكي متقدم"""
        alerts = {
            'battery_critical': {
                'title': '🚨 تحذير حرج',
                'message': f"البطارية {data.get('percent', 0)}%! وصّل الشاحن فوراً",
                'urgency': 'critical'
            },
            'battery_low': {
                'title': '⚠️ بطارية منخفضة',
                'message': f"البطارية {data.get('percent', 0)}% - يُنصح بالشحن",
                'urgency': 'normal'
            },
            'charge_complete': {
                'title': '✅ اكتمل الشحن',
                'message': f"البطارية {data.get('percent', 0)}% - يمكن فصل الشاحن",
                'urgency': 'low'
            },
            'optimal_charge': {
                'title': '⚡ الشحن الأمثل',
                'message': f"وصلت للمستوى الأمثل {data.get('percent', 0)}%",
                'urgency': 'normal'
            },
            'health_warning': {
                'title': '💊 تحذير الصحة',
                'message': data.get('message', 'صحة البطارية تحتاج انتباه'),
                'urgency': 'normal'
            }
        }
        
        alert = alerts.get(alert_type)
        if alert:
            return self.send_notification(
                title=alert['title'],
                message=alert['message'],
                urgency=alert['urgency'],
                notification_type=alert_type
            )
        
        return False
    
    def get_statistics(self) -> Dict:
        """الحصول على إحصائيات الإشعارات"""
        return {
            'total_sent': self.stats['total_sent'],
            'total_suppressed': self.stats['total_suppressed'],
            'by_type': self.stats['by_type'],
            'by_priority': self.stats['by_priority'],
            'recent_notifications': self.notification_history[-10:]
        }
    
    def set_smart_timing(self, enabled: bool):
        """تفعيل/إيقاف التوقيت الذكي"""
        self.smart_timing_enabled = enabled
        logger.info(f"التوقيت الذكي: {'مفعّل' if enabled else 'معطّل'}")
    
    def set_ai_recommendations(self, enabled: bool):
        """تفعيل/إيقاف توصيات الذكاء الاصطناعي"""
        self.ai_recommendations_enabled = enabled
        logger.info(f"توصيات AI: {'مفعّلة' if enabled else 'معطّلة'}")
    
    def set_sound_settings(self, enabled: bool, volume: float = 0.7):
        """تعيين إعدادات الصوت"""
        self.sound_enabled = enabled
        self.sound_volume = max(0.0, min(1.0, volume))
        logger.info(f"الأصوات: {'مفعّلة' if enabled else 'معطّلة'}, المستوى: {self.sound_volume}")
    
    def clear_history(self):
        """مسح سجل الإشعارات"""
        self.notification_history.clear()
        logger.info("تم مسح سجل الإشعارات")
    
    def send_battery_threshold_alert(self, current_percent: int, is_charging: bool, 
                                   battery_health: int = 100):
        """إرسال تنبيه ذكي بناءً على حدود البطارية"""
        
        # تنبيه حرج - بطارية منخفضة جداً
        if current_percent <= self.battery_thresholds['critical_low'] and not is_charging:
            self.send_notification(
                title="🚨 تحذير حرج - البطارية منخفضة جداً!",
                message=f"البطارية {current_percent}%! وصّل الشاحن فوراً لتجنب إيقاف الجهاز",
                urgency='critical',
                notification_type='battery_critical',
                play_sound=True,
                persistent=True
            )
            
            # بدء تذكير حرج
            self.start_reminder(
                'battery_critical',
                lambda: self._get_current_battery() <= self.battery_thresholds['critical_low'] and not self._is_charging(),
                {
                    'title': '🚨 تحذير متكرر - البطارية حرجة!',
                    'message': f'البطارية لا تزال {current_percent}%! وصّل الشاحن الآن!',
                    'urgency': 'critical',
                    'play_sound': True
                },
                interval=60  # كل دقيقة
            )
            return True
        
        # تنبيه منخفض
        elif current_percent <= self.battery_thresholds['low'] and not is_charging:
            self.send_notification(
                title="⚠️ بطارية منخفضة",
                message=f"البطارية {current_percent}% - يُنصح بالشحن قريباً",
                urgency='normal',
                notification_type='battery_low',
                play_sound=True
            )
            
            # بدء تذكير للبطارية المنخفضة
            self.start_reminder(
                'battery_low',
                lambda: self._get_current_battery() <= self.battery_thresholds['low'] and not self._is_charging(),
                {
                    'title': '🔋 تذكير - البطارية منخفضة',
                    'message': f'البطارية {current_percent}% - فكر في الشحن',
                    'urgency': 'normal',
                    'play_sound': False
                }
            )
            return True
        
        # تنبيه الشحن الكامل
        elif current_percent >= self.battery_thresholds['full'] and is_charging:
            self.send_notification(
                title="✅ اكتمل الشحن",
                message=f"البطارية {current_percent}% - يمكن فصل الشاحن لحماية البطارية",
                urgency='low',
                notification_type='charge_complete',
                play_sound=True
            )
            
            # بدء تذكير لفصل الشاحن
            if self.smart_alerts['charger_disconnect_reminder']:
                self.start_reminder(
                    'unplug_charger',
                    lambda: self._get_current_battery() >= self.battery_thresholds['full'] and self._is_charging(),
                    {
                        'title': '🔌 تذكير - فصل الشاحن',
                        'message': f'البطارية ممتلئة {current_percent}% - افصل الشاحن لحماية البطارية',
                        'urgency': 'normal',
                        'play_sound': True
                    }
                )
            return True
        
        # تنبيه الشحن الأمثل
        elif (self.battery_thresholds['optimal_min'] <= current_percent <= self.battery_thresholds['optimal_max'] 
              and is_charging and self.smart_alerts['optimal_charge_reminder']):
            self.send_notification(
                title="⚡ الشحن الأمثل",
                message=f"البطارية {current_percent}% - في النطاق الأمثل للصحة",
                urgency='low',
                notification_type='optimal_charge',
                play_sound=False
            )
            return True
        
        # تنبيه صحة البطارية
        if battery_health < 80 and self.smart_alerts['health_warnings']:
            self.send_notification(
                title="💊 تحذير صحة البطارية",
                message=f"صحة البطارية {battery_health}% - تجنب الشحن الكامل والتفريغ العميق",
                urgency='normal',
                notification_type='health_warning',
                play_sound=True
            )
            return True
        
        return False
    
    def send_charger_status_alert(self, was_charging: bool, is_charging: bool, 
                                battery_percent: int):
        """تنبيه تغيير حالة الشاحن"""
        
        if was_charging and not is_charging:
            # تم فصل الشاحن
            if battery_percent < self.battery_thresholds['optimal_min']:
                self.send_notification(
                    title="🔌 تم فصل الشاحن",
                    message=f"البطارية {battery_percent}% - أقل من المستوى الأمثل",
                    urgency='normal',
                    notification_type='charger_disconnected',
                    play_sound=True
                )
            else:
                self.send_notification(
                    title="✅ تم فصل الشاحن",
                    message=f"البطارية {battery_percent}% - مستوى جيد",
                    urgency='low',
                    notification_type='charger_disconnected',
                    play_sound=False
                )
        
        elif not was_charging and is_charging:
            # تم توصيل الشاحن
            if battery_percent <= self.battery_thresholds['critical_low']:
                self.send_notification(
                    title="⚡ تم توصيل الشاحن",
                    message=f"البطارية {battery_percent}% - شحن سريع مطلوب",
                    urgency='normal',
                    notification_type='charger_connected',
                    play_sound=True
                )
                # إيقاف تذكيرات البطارية المنخفضة
                self.stop_reminder('battery_critical')
                self.stop_reminder('battery_low')
            else:
                self.send_notification(
                    title="🔋 بدء الشحن",
                    message=f"البطارية {battery_percent}% - جارٍ الشحن",
                    urgency='low',
                    notification_type='charger_connected',
                    play_sound=False
                )
    
    def send_smart_usage_alert(self, usage_data: Dict):
        """تنبيهات ذكية بناءً على أنماط الاستخدام"""
        if not self.smart_alerts['usage_pattern_alerts']:
            return
        
        # استهلاك مرتفع غير عادي
        if usage_data.get('high_drain_detected', False):
            self.send_notification(
                title="📈 استهلاك مرتفع مكتشف",
                message="استهلاك البطارية أعلى من المعتاد - تحقق من التطبيقات",
                urgency='normal',
                notification_type='high_usage_alert',
                play_sound=True
            )
        
        # درجة حرارة مرتفعة
        if usage_data.get('temperature', 0) > 45 and self.smart_alerts['temperature_warnings']:
            self.send_notification(
                title="🌡️ تحذير درجة الحرارة",
                message=f"درجة حرارة البطارية {usage_data['temperature']}°C - قلل الاستخدام",
                urgency='high',
                notification_type='temperature_warning',
                play_sound=True
            )
        
        # نمط شحن غير صحي
        if usage_data.get('unhealthy_charging_pattern', False):
            self.send_notification(
                title="⚠️ نمط شحن غير صحي",
                message="تم اكتشاف نمط شحن قد يضر بالبطارية - راجع عاداتك",
                urgency='normal',
                notification_type='charging_pattern_warning',
                play_sound=True
            )
    
    def send_ai_smart_alert(self, ai_data: Dict):
        """تنبيهات ذكية من الذكاء الاصطناعي"""
        alert_type = ai_data.get('type', 'general')
        confidence = ai_data.get('confidence', 0)
        
        # تنبيهات عالية الثقة فقط
        if confidence < 70:
            return
        
        alerts = {
            'battery_degradation': {
                'title': '🔋 تدهور البطارية مكتشف',
                'message': f'الذكاء الاصطناعي يشير لتدهور في الأداء (ثقة: {confidence}%)',
                'urgency': 'normal'
            },
            'optimal_charge_time': {
                'title': '⏰ وقت الشحن الأمثل',
                'message': f'الآن وقت مثالي للشحن بناءً على أنماطك (ثقة: {confidence}%)',
                'urgency': 'low'
            },
            'usage_prediction': {
                'title': '🔮 توقع الاستخدام',
                'message': ai_data.get('message', 'توقع ذكي للاستخدام'),
                'urgency': 'low'
            },
            'maintenance_reminder': {
                'title': '🔧 تذكير صيانة ذكي',
                'message': ai_data.get('message', 'حان وقت صيانة البطارية'),
                'urgency': 'normal'
            }
        }
        
        alert = alerts.get(alert_type)
        if alert:
            self.send_notification(
                title=alert['title'],
                message=alert['message'],
                urgency=alert['urgency'],
                notification_type=f'ai_{alert_type}',
                play_sound=True
            )
    
    def update_battery_thresholds(self, thresholds: Dict):
        """تحديث حدود البطارية"""
        self.battery_thresholds.update(thresholds)
        logger.info(f"تم تحديث حدود البطارية: {thresholds}")
    
    def update_reminder_intervals(self, intervals: Dict):
        """تحديث فترات التذكير"""
        self.reminder_intervals.update(intervals)
        logger.info(f"تم تحديث فترات التذكير: {intervals}")
    
    def toggle_smart_alert(self, alert_type: str, enabled: bool):
        """تفعيل/إيقاف تنبيه ذكي محدد"""
        if alert_type in self.smart_alerts:
            self.smart_alerts[alert_type] = enabled
            logger.info(f"تنبيه {alert_type}: {'مفعّل' if enabled else 'معطّل'}")
    
    def set_sound_settings(self, enabled: bool, volume: float = 0.7):
        """تحديث إعدادات الصوت"""
        self.sound_enabled = enabled
        self.sound_volume = max(0.0, min(1.0, volume))
        logger.info(f"الأصوات: {'مفعّلة' if enabled else 'معطّلة'} - مستوى الصوت: {self.sound_volume}")
    
    def _get_current_battery(self) -> int:
        """الحصول على مستوى البطارية الحالي (للتذكيرات)"""
        try:
            import psutil
            battery = psutil.sensors_battery()
            return battery.percent if battery else 50
        except:
            return 50
    
    def _is_charging(self) -> bool:
        """التحقق من حالة الشحن (للتذكيرات)"""
        try:
            import psutil
            battery = psutil.sensors_battery()
            return battery.power_plugged if battery else False
        except:
            return False
    
    def get_advanced_statistics(self) -> Dict:
        """إحصائيات متقدمة للإشعارات"""
        return {
            'total_sent': self.stats['total_sent'],
            'total_suppressed': self.stats['total_suppressed'],
            'reminders_sent': self.stats['reminders_sent'],
            'sounds_played': self.stats['sounds_played'],
            'by_type': self.stats['by_type'],
            'by_priority': self.stats['by_priority'],
            'active_reminders': list(self.active_reminders.keys()),
            'recent_notifications': self.notification_history[-10:],
            'battery_thresholds': self.battery_thresholds,
            'smart_alerts_status': self.smart_alerts
        }


# للتوافق مع الكود القديم
class NotificationManager(SmartNotificationManager):
    """اسم بديل للتوافق مع الكود القديم"""
    pass
