#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مدير الإشعارات الذكي عبر المنصات مع الأصوات والتذكيرات

تصميم هذا الإصدار:
- التذكيرات تعمل عبر مجدول QTimer على خيط الواجهة الرئيسي بدلاً من خيوط
  Python المنفصلة، فتُلغى جميع مشاكل إنشاء الحوارات خارج الخيط الرئيسي.
- كشف أدوات الصوت بشكل متأخر (Lazy) وذاكرة مؤقتة، بدلاً من فحص عند الاستيراد.
- تشغيل MP3 فعلي على Windows عبر pygame.mixer.music (كان Sound لا يدعمه).
- مراجع محفوظة للحوارات لمنع جمعها من جامع النفايات أثناء العرض.
"""

import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

try:
    from resource_path import get_resource_path
except ImportError:  # pragma: no cover
    def get_resource_path(path):
        return Path(path)

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

logger = logging.getLogger('BatteryGuard')

try:
    from interactive_notification_dialog import InteractiveNotificationDialog
    INTERACTIVE_DIALOG_AVAILABLE = True
except ImportError:
    INTERACTIVE_DIALOG_AVAILABLE = False
    logger.warning("Interactive dialog not available")

PLYER_AVAILABLE = False
NOTIFY_AVAILABLE = False

if IS_WINDOWS:
    try:
        from plyer import notification as plyer_notification  # type: ignore
        PLYER_AVAILABLE = True
    except ImportError:
        logger.warning("Plyer غير متاح")
elif IS_LINUX:
    try:
        import gi
        gi.require_version('Notify', '0.7')
        from gi.repository import Notify  # type: ignore
        NOTIFY_AVAILABLE = True
    except (ImportError, ValueError) as e:
        logger.warning(f"Notify غير متاح: {e}")
    if not NOTIFY_AVAILABLE:
        try:
            from plyer import notification as plyer_notification  # type: ignore
            PLYER_AVAILABLE = True
        except ImportError:
            pass


class DialogDispatcher(QObject):
    """
    جسر آمن بين الخيوط لإنشاء الحوارات: يمكن إطلاق الإشارة من أي خيط،
    وسيُنشئ الحوار Qt على خيط الواجهة الرئيسي تلقائياً.
    """

    show_interactive = pyqtSignal(str, str, str, str)  # title, message, urgency, reminder_type

    def __init__(self):
        super().__init__()
        self.active_dialogs = set()
        self.show_interactive.connect(self._on_show_interactive)

    def request(self, title: str, message: str, urgency: str, reminder_type: str):
        """طلب عرض حوار (آمن من أي خيط)"""
        from PyQt6.QtWidgets import QApplication
        if QApplication.instance() is None:
            return False
        self.show_interactive.emit(title, message, urgency, reminder_type)
        return True

    def _on_show_interactive(self, title: str, message: str, urgency: str,
                             reminder_type: str):
        """التنفيذ على الخيط الرئيسي"""
        if not INTERACTIVE_DIALOG_AVAILABLE:
            return
        try:
            manager = SmartNotificationManager.instance()
            dialog = InteractiveNotificationDialog(
                title=title, message=message,
                reminder_type=reminder_type, urgency=urgency,
            )
            dialog.stop_clicked.connect(manager.mute_reminder)
            dialog.snooze_clicked.connect(manager.snooze_reminder)
            dialog.mute_clicked.connect(manager.mute_sound_only)

            # حفظ مرجع حتى لا يُجمع الحوار أثناء ظهوره
            self.active_dialogs.add(dialog)
            dialog.destroyed.connect(lambda *_: self.active_dialogs.discard(dialog))
            dialog.show()
            logger.info(f"نافذة تفاعلية: {title}")
        except Exception as e:
            logger.error(f"خطأ في إنشاء النافذة التفاعلية: {e}")


class SmartNotificationManager:
    """مدير الإشعارات الذكي مع أصوات وتذكيرات قائمة على QTimer"""

    _singleton: Optional['SmartNotificationManager'] = None

    def __init__(self):
        SmartNotificationManager._singleton = self

        self.enabled = True
        self.notification_history = []
        self.last_notification_time: Dict[str, float] = {}
        self.notification_cooldown = 300
        self.smart_timing_enabled = True
        self.ai_recommendations_enabled = True

        # التذكيرات
        self.reminders_enabled = True
        self.reminder_intervals = {
            'battery_low': 300,
            'battery_critical': 60,
            'charge_complete': 600,
            'unplug_charger': 300,
        }
        self.reminder_conditions: Dict[str, Callable] = {}
        self.reminder_data: Dict[str, Dict] = {}
        self.reminder_interactive: Dict[str, bool] = {}
        self.snoozed_reminders: Dict[str, float] = {}
        self.muted_reminders = set()
        self.snooze_duration = 600
        self._reminder_timers: Dict[str, QTimer] = {}

        # إعدادات الإشعارات القابلة للتنفيذ
        self.actionable_notifications_enabled = True
        self.auto_dismiss_time = 15
        self.dismissed_notifications: Dict[str, float] = {}
        self.dismiss_duration = 3600

        # الأصوات
        self.sound_enabled = True
        self.sound_volume = 0.7
        base = str(get_resource_path('sounds'))
        self.sound_files = {
            'critical': f'{base}/new-notification-010-352755.mp3',
            'warning': f'{base}/new-notification-05-352453.mp3',
            'info': f'{base}/new-notification-021-370045.mp3',
            'success': f'{base}/new-notification-022-370046.mp3',
            'optimization': f'{base}/new-notification-024-370048.mp3',
        }
        self.sound_files = {k: v for k, v in self.sound_files.items() if Path(v).exists()}
        missing = {'critical', 'warning', 'info', 'success', 'optimization'} - set(self.sound_files)
        if missing:
            logger.warning(f"ملفات أصوات مفقودة: {missing}")

        self._sound_player_cache: Optional[Optional[str]] = None  # None = لم يُفحص بعد
        self._pygame_ready = False

        # حدود البطارية القابلة للتخصيص
        self.battery_thresholds = {
            'critical_low': 10,
            'low': 20,
            'optimal_min': 40,
            'optimal_max': 80,
            'high': 90,
            'full': 95,
        }

        # التنبيهات الذكية
        self.smart_alerts = {
            'charger_disconnect_reminder': True,
            'optimal_charge_reminder': True,
            'health_warnings': True,
            'usage_pattern_alerts': True,
            'temperature_warnings': True,
        }

        self._initialize_notifications()
        self.dispatcher = DialogDispatcher()

        self.stats = {
            'total_sent': 0,
            'total_suppressed': 0,
            'reminders_sent': 0,
            'sounds_played': 0,
            'by_type': {},
            'by_priority': {},
        }

    @classmethod
    def instance(cls) -> 'SmartNotificationManager':
        assert cls._singleton is not None, "SmartNotificationManager غير مهيأ بعد"
        return cls._singleton

    # ──────────────────────────────────────────────────────────────
    # تهيئة أنظمة الإشعارات
    # ──────────────────────────────────────────────────────────────

    def _initialize_notifications(self):
        if IS_LINUX and NOTIFY_AVAILABLE:
            try:
                Notify.init("BatteryGuardAI")
                self.notification_method = 'notify'
                logger.info("نظام الإشعارات: Notify (Linux)")
                return
            except Exception as e:
                logger.warning(f"فشل تهيئة Notify: {e}")
        if PLYER_AVAILABLE:
            self.notification_method = 'plyer'
            logger.info("نظام الإشعارات: Plyer")
        else:
            self.notification_method = 'none'
            logger.warning("لا يوجد نظام إشعارات مدمج - سيُستخدم notify-send عند توفره")

    # ──────────────────────────────────────────────────────────────
    # الأصوات
    # ──────────────────────────────────────────────────────────────

    def play_sound(self, sound_type: str = 'info'):
        """تشغيل صوت الإشعار (MP3/WAV) بغير مانع"""
        if not self.sound_enabled or not self.sound_files:
            return
        try:
            sound_file = self.sound_files.get(sound_type) or next(iter(self.sound_files.values()))
            path = Path(sound_file)
            if not path.exists():
                return

            if IS_WINDOWS:
                self._play_sound_windows(path)
            elif IS_LINUX:
                self._play_sound_linux(path)

            self.stats['sounds_played'] += 1
        except Exception as e:
            logger.debug(f"تعذر تشغيل الصوت {sound_type}: {e}")

    def _play_sound_windows(self, path: Path):
        """Windows: pygame.mixer.music يدعم MP3 فعلياً"""
        try:
            import pygame
            if not self._pygame_ready:
                pygame.mixer.init()
                self._pygame_ready = True
            pygame.mixer.music.set_volume(max(0.0, min(1.0, self.sound_volume)))
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            return
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"pygame sound failed: {e}")

        if path.suffix.lower() == '.wav':
            try:
                import winsound
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                logger.debug(f"winsound failed: {e}")
        else:
            try:
                import winsound
                winsound.MessageBeep()
            except Exception:
                pass

    def _play_sound_linux(self, path: Path):
        """Linux: اختيار مشغل متاح مرة واحدة وتخزينه مؤقتاً"""
        if self._sound_player_cache is None:
            self._sound_player_cache = ''
            for candidate in ('paplay', 'ffplay', 'mpg123', 'aplay'):
                try:
                    result = subprocess.run(
                        ['which', candidate], capture_output=True, timeout=2)
                    if result.returncode == 0:
                        self._sound_player_cache = candidate
                        break
                except Exception:
                    continue
            if not self._sound_player_cache:
                logger.warning("لا توجد أدوات صوت متاحة (Linux)")

        player = self._sound_player_cache
        if not player:
            return
        try:
            vol = max(0.0, min(1.0, self.sound_volume))
            if player == 'paplay':
                subprocess.Popen(
                    ['paplay', f'--volume={vol}', str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif player == 'ffplay':
                subprocess.Popen(
                    ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet',
                     '-volume', str(int(vol * 100)), str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif player == 'mpg123':
                subprocess.Popen(
                    ['mpg123', '-q', str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif player == 'aplay' and path.suffix.lower() == '.wav':
                subprocess.Popen(
                    ['aplay', '-q', str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            self._sound_player_cache = ''

    # ──────────────────────────────────────────────────────────────
    # نظام التذكيرات (QTimer على الخيط الرئيسي)
    # ──────────────────────────────────────────────────────────────

    def start_reminder(self, reminder_type: str, condition_check: Callable,
                       notification_data: Dict, interval: Optional[int] = None,
                       interactive: bool = True):
        """بدء تذكير يتكرر عبر QTimer (خيط الواجهة الرئيسي)"""
        if not self.reminders_enabled:
            return

        self.stop_reminder(reminder_type, log=False)
        reminder_interval = interval or self.reminder_intervals.get(reminder_type, 300)

        self.reminder_conditions[reminder_type] = condition_check
        self.reminder_data[reminder_type] = notification_data
        self.reminder_interactive[reminder_type] = interactive
        self.snoozed_reminders.pop(reminder_type, None)
        self.muted_reminders.discard(reminder_type)

        timer = QTimer()
        timer.setInterval(int(reminder_interval * 1000))
        timer.timeout.connect(lambda: self._reminder_tick(reminder_type))
        timer.start()
        self._reminder_timers[reminder_type] = timer

        # إرسال أول تنبيه فوراً
        self._reminder_tick(reminder_type)
        logger.info(f"بدء تذكير: {reminder_type} (كل {reminder_interval} ثانية)")

    def _reminder_tick(self, reminder_type: str):
        """نبضة تذكير واحدة"""
        try:
            if reminder_type in self.muted_reminders:
                self.stop_reminder(reminder_type, log=False)
                return

            snooze_until = self.snoozed_reminders.get(reminder_type, 0)
            if time.time() < snooze_until:
                return

            condition = self.reminder_conditions.get(reminder_type)
            data = self.reminder_data.get(reminder_type)
            if condition is None or data is None or not condition():
                self.stop_reminder(reminder_type, log=False)
                return

            if self.reminder_interactive.get(reminder_type, True):
                shown = self.dispatcher.request(
                    data['title'], data['message'],
                    data.get('urgency', 'normal'), reminder_type,
                )
                if shown and data.get('play_sound', True):
                    self.play_sound(self._get_sound_type(
                        data.get('urgency', 'normal'), reminder_type))
                if not shown:
                    self.send_notification(
                        data['title'], data['message'],
                        data.get('urgency', 'normal'),
                        f"reminder_{reminder_type}",
                        play_sound=data.get('play_sound', True),
                    )
            else:
                self.send_notification(
                    data['title'], data['message'],
                    data.get('urgency', 'normal'),
                    f"reminder_{reminder_type}",
                    play_sound=data.get('play_sound', True),
                )

            self.stats['reminders_sent'] += 1
        except Exception as e:
            logger.error(f"خطأ في نبضة تذكير {reminder_type}: {e}")
            self.stop_reminder(reminder_type, log=False)

    def stop_reminder(self, reminder_type: str, log: bool = True):
        """إيقاف تذكير محدد فوراً"""
        timer = self._reminder_timers.pop(reminder_type, None)
        if timer is not None:
            timer.stop()
        self.reminder_conditions.pop(reminder_type, None)
        self.reminder_data.pop(reminder_type, None)
        self.reminder_interactive.pop(reminder_type, None)
        self.snoozed_reminders.pop(reminder_type, None)
        if log and timer is not None:
            logger.info(f"إيقاف تذكير: {reminder_type}")

    def stop_all_reminders(self):
        """إيقاف جميع التذكيرات"""
        for reminder_type in list(self._reminder_timers.keys()):
            self.stop_reminder(reminder_type, log=False)
        logger.info("تم إيقاف جميع التذكيرات")

    def snooze_reminder(self, reminder_type: str, duration: Optional[int] = None):
        """غفوة تذكير لفترة محددة ثم استئنافه إذا ظل الشرط صحيحاً"""
        snooze_time = duration or self.snooze_duration
        self.snoozed_reminders[reminder_type] = time.time() + snooze_time
        logger.info(f"غفوة تذكير {reminder_type} لمدة {snooze_time // 60} دقيقة")

    def mute_reminder(self, reminder_type: str):
        """كتم تذكير نهائياً"""
        self.muted_reminders.add(reminder_type)
        self.stop_reminder(reminder_type, log=False)
        logger.info(f"تم كتم تذكير: {reminder_type}")

    def unmute_reminder(self, reminder_type: str):
        """إلغاء كتم تذكير"""
        self.muted_reminders.discard(reminder_type)

    def mute_sound_only(self, reminder_type: str):
        """كتم الصوت فقط دون إيقاف التذكير"""
        self.sound_enabled = False
        logger.info("تم كتم صوت التذكيرات")

    # ──────────────────────────────────────────────────────────────
    # الإرسال الأساسي
    # ──────────────────────────────────────────────────────────────

    def send_notification(self, title: str, message: str, urgency: str = 'normal',
                          notification_type: str = 'general', ai_priority: int = 5,
                          play_sound: bool = True, persistent: bool = False) -> bool:
        """إرسال إشعار ذكي مع تحكم بالتوقيت والأصوات"""
        if not self.enabled:
            return False

        if not self._should_send_notification(notification_type, urgency):
            self.stats['total_suppressed'] += 1
            logger.debug(f"تم منع الإشعار: {title} (توقيت/تهدئة)")
            return False

        notification = {
            'title': title,
            'message': message,
            'urgency': urgency,
            'type': notification_type,
            'ai_priority': ai_priority,
            'play_sound': play_sound,
            'persistent': persistent,
            'timestamp': datetime.now().isoformat(),
        }
        return self._send_immediate(notification)

    def _should_send_notification(self, notification_type: str, urgency: str) -> bool:
        """قرار ذكي: الحرجة دائماً، والباقي بعد فترة هدئة وخارج ساعات الهدوء"""
        if urgency == 'critical':
            return True

        last_time = self.last_notification_time.get(notification_type, 0)
        if time.time() - last_time < self.notification_cooldown:
            return False

        if self.smart_timing_enabled:
            current_hour = datetime.now().hour
            if current_hour in (1, 2, 3, 4, 5, 6):
                return False
        return True

    def _send_immediate(self, notification: Dict) -> bool:
        """تنفيذ الإرسال الفوري مع الصوت"""
        try:
            title = notification['title']
            message = notification['message']
            urgency = notification['urgency']
            notification_type = notification['type']
            play_sound = notification.get('play_sound', True)
            persistent = notification.get('persistent', False)

            if play_sound:
                self.play_sound(self._get_sound_type(urgency, notification_type))

            icon = self._get_icon_for_type(notification_type, urgency)
            sent = False

            if self.notification_method == 'notify' and IS_LINUX:
                try:
                    notif = Notify.Notification.new(title, message, icon)
                    if urgency == 'critical':
                        notif.set_urgency(Notify.Urgency.CRITICAL)
                    elif urgency == 'low':
                        notif.set_urgency(Notify.Urgency.LOW)
                    else:
                        notif.set_urgency(Notify.Urgency.NORMAL)

                    if persistent or urgency == 'critical':
                        notif.set_timeout(Notify.EXPIRES_NEVER)
                    else:
                        notif.set_timeout(7000)

                    notif.show()
                    sent = True
                except Exception as e:
                    logger.warning(f"فشل Notify، محاولة notify-send: {e}")
                    sent = self._send_via_notify_send(title, message, urgency, icon)

            elif self.notification_method == 'plyer':
                try:
                    timeout = 15 if urgency == 'critical' else 7
                    plyer_notification.notify(
                        title=title, message=message,
                        app_name='BatteryGuardAI',
                        timeout=timeout,
                        app_icon=icon if Path(icon).exists() else None,
                    )
                    sent = True
                except Exception as e:
                    logger.warning(f"فشل Plyer: {e}")
                    if IS_LINUX:
                        sent = self._send_via_notify_send(title, message, urgency, icon)

            elif IS_LINUX:
                sent = self._send_via_notify_send(title, message, urgency, icon)

            if not sent and not (self.enabled and self.notification_method != 'none'):
                logger.debug("لم يُرسل الإشعار عبر أي قناة")

            # إحصائيات وسجل
            self.stats['total_sent'] += 1
            self.stats['by_type'][notification_type] = \
                self.stats['by_type'].get(notification_type, 0) + 1
            self.stats['by_priority'][urgency] = \
                self.stats['by_priority'].get(urgency, 0) + 1
            self.last_notification_time[notification_type] = time.time()

            self.notification_history.append(dict(notification))
            if len(self.notification_history) > 100:
                del self.notification_history[:-100]

            logger.info(f"إشعار: {title}")
            return True

        except Exception as e:
            logger.error(f"خطأ في إرسال الإشعار: {e}")
            return False

    def _send_via_notify_send(self, title: str, message: str, urgency: str,
                              icon: str) -> bool:
        """بديل notify-send غير مانع (Popen بدل subprocess.run المانع)"""
        if not IS_LINUX:
            return False
        try:
            urgency_level = 'critical' if urgency == 'critical' else 'normal'
            expire = '0' if urgency == 'critical' else '7000'
            subprocess.Popen(
                [
                    'notify-send',
                    '--app-name=BatteryGuardAI',
                    f'--urgency={urgency_level}',
                    f'--expire-time={expire}',
                    f'--icon={icon}',
                    title, message,
                ],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"إشعار notify-send: {title}")
            return True
        except FileNotFoundError:
            logger.info("ثبّت libnotify: sudo apt install libnotify-bin")
            return False
        except Exception as e:
            logger.error(f"خطأ في notify-send: {e}")
            return False

    @staticmethod
    def _get_sound_type(urgency: str, notification_type: str) -> str:
        """تحديد الصوت المناسب لنوع الإشعار"""
        if urgency == 'critical' or 'critical' in notification_type:
            return 'critical'
        if urgency == 'high' or 'warning' in notification_type or 'low' in notification_type:
            return 'warning'
        if ('success' in notification_type or 'complete' in notification_type
                or 'full' in notification_type):
            return 'success'
        if ('optimization' in notification_type or 'optimizer' in notification_type
                or 'improve' in notification_type):
            return 'optimization'
        return 'info'

    @staticmethod
    def _get_icon_for_type(notification_type: str, urgency: str) -> str:
        """الأيقونة المناسبة حسب النوع"""
        if urgency == 'critical':
            return 'dialog-warning'
        if notification_type == 'battery_low':
            return 'battery-caution'
        if notification_type == 'battery_full':
            return 'battery-full'
        if notification_type == 'charging':
            return 'battery-charging'
        return 'dialog-information'

    # ──────────────────────────────────────────────────────────────
    # تنبيهات البطارية الذكية
    # ──────────────────────────────────────────────────────────────

    def send_battery_threshold_alert(self, current_percent: int, is_charging: bool,
                                     battery_health: int = 100) -> bool:
        """تنبيه ذكي بناءً على حدود البطارية مع تذكيرات متكررة"""
        t = self.battery_thresholds

        if current_percent <= t['critical_low'] and not is_charging:
            self.send_notification(
                title="تحذير حرج - البطارية منخفضة جداً!",
                message=f"البطارية {current_percent}%! وصّل الشاحن فوراً لتجنب إيقاف الجهاز",
                urgency='critical', notification_type='battery_critical',
                play_sound=True, persistent=True)
            self.start_reminder(
                'battery_critical',
                lambda: self._get_current_battery() <= t['critical_low'] and not self._is_charging(),
                {
                    'title': 'تحذير متكرر - البطارية حرجة!',
                    'message': f'البطارية لا تزال {current_percent}%! وصّل الشاحن الآن!',
                    'urgency': 'critical',
                    'play_sound': True,
                },
                interval=self.reminder_intervals.get('battery_critical', 60))
            return True

        if current_percent <= t['low'] and not is_charging:
            self.send_notification(
                title="بطارية منخفضة",
                message=f"البطارية {current_percent}% - يُنصح بالشحن قريباً",
                urgency='normal', notification_type='battery_low', play_sound=True)
            self.start_reminder(
                'battery_low',
                lambda: self._get_current_battery() <= t['low'] and not self._is_charging(),
                {
                    'title': 'تذكير - البطارية منخفضة',
                    'message': f'البطارية {current_percent}% - فكر في الشحن',
                    'urgency': 'normal',
                    'play_sound': False,
                })
            return True

        if current_percent >= t['full'] and is_charging:
            self.send_notification(
                title="اكتمل الشحن",
                message=f"البطارية {current_percent}% - يمكن فصل الشاحن لحماية البطارية",
                urgency='low', notification_type='charge_complete', play_sound=True)
            if self.smart_alerts['charger_disconnect_reminder']:
                self.start_reminder(
                    'unplug_charger',
                    lambda: self._get_current_battery() >= t['full'] and self._is_charging(),
                    {
                        'title': 'تذكير - فصل الشاحن',
                        'message': f'البطارية ممتلئة {current_percent}% - افصل الشاحن لحماية البطارية',
                        'urgency': 'normal',
                        'play_sound': True,
                    })
            return True

        if (t['optimal_min'] <= current_percent <= t['optimal_max']
                and is_charging and self.smart_alerts['optimal_charge_reminder']):
            self.send_notification(
                title="الشحن الأمثل",
                message=f"البطارية {current_percent}% - في النطاق الأمثل للصحة",
                urgency='low', notification_type='optimal_charge', play_sound=False)
            return True

        if battery_health < 80 and self.smart_alerts['health_warnings']:
            self.send_notification(
                title="تحذير صحة البطارية",
                message=f"صحة البطارية {battery_health}% - تجنب الشحن الكامل والتفريغ العميق",
                urgency='normal', notification_type='health_warning', play_sound=True)
            return True

        return False

    def send_charger_status_alert(self, was_charging: bool, is_charging: bool,
                                  battery_percent: int):
        """تنبيه تغيّر حالة الشاحن"""
        t = self.battery_thresholds

        if was_charging and not is_charging:
            if battery_percent < t['optimal_min']:
                self.send_notification(
                    title="تم فصل الشاحن",
                    message=f"البطارية {battery_percent}% - أقل من المستوى الأمثل",
                    urgency='normal', notification_type='charger_disconnected',
                    play_sound=True)
            else:
                self.send_notification(
                    title="تم فصل الشاحن",
                    message=f"البطارية {battery_percent}% - مستوى جيد",
                    urgency='low', notification_type='charger_disconnected',
                    play_sound=False)

        elif not was_charging and is_charging:
            if battery_percent <= t['critical_low']:
                self.send_notification(
                    title="تم توصيل الشاحن",
                    message=f"البطارية {battery_percent}% - شحن سريع مطلوب",
                    urgency='normal', notification_type='charger_connected',
                    play_sound=True)
                # إيقاف تذكيرات البطارية المنخفضة
                self.stop_reminder('battery_critical')
                self.stop_reminder('battery_low')
            else:
                self.send_notification(
                    title="بدء الشحن",
                    message=f"البطارية {battery_percent}% - جارٍ الشحن",
                    urgency='low', notification_type='charger_connected',
                    play_sound=False)

    def send_smart_usage_alert(self, usage_data: Dict):
        """تنبيهات ذكية بناءً على أنماط الاستخدام"""
        if not self.smart_alerts['usage_pattern_alerts']:
            return

        if usage_data.get('high_drain_detected', False):
            self.send_notification(
                title="استهلاك مرتفع مكتشف",
                message="استهلاك البطارية أعلى من المعتاد - تحقق من التطبيقات",
                urgency='normal', notification_type='high_usage_alert',
                play_sound=True)

        if usage_data.get('temperature', 0) > 45 and self.smart_alerts['temperature_warnings']:
            self.send_notification(
                title="تحذير درجة الحرارة",
                message=f"درجة حرارة البطارية {usage_data['temperature']}°C - قلل الاستخدام",
                urgency='high', notification_type='temperature_warning',
                play_sound=True)

        if usage_data.get('unhealthy_charging_pattern', False):
            self.send_notification(
                title="نمط شحن غير صحي",
                message="تم اكتشاف نمط شحن قد يضر بالبطارية - راجع عاداتك",
                urgency='normal', notification_type='charging_pattern_warning',
                play_sound=True)

    def send_ai_smart_alert(self, ai_data: Dict):
        """تنبيهات من الذكاء الاصطناعي (الثقة العالية فقط)"""
        alert_type = ai_data.get('type', 'general')
        confidence = ai_data.get('confidence', 0)
        if confidence < 70:
            return

        alerts = {
            'battery_degradation': {
                'title': 'تدهور البطارية مكتشف',
                'message': f'الذكاء الاصطناعي يشير لتدهور في الأداء (ثقة: {confidence}%)',
                'urgency': 'normal'},
            'optimal_charge_time': {
                'title': '⏰ وقت الشحن الأمثل',
                'message': f'الآن وقت مثالي للشحن بناءً على أنماطك (ثقة: {confidence}%)',
                'urgency': 'low'},
            'usage_prediction': {
                'title': 'توقع الاستخدام',
                'message': ai_data.get('message', 'توقع ذكي للاستخدام'),
                'urgency': 'low'},
            'maintenance_reminder': {
                'title': 'تذكير صيانة ذكي',
                'message': ai_data.get('message', 'حان وقت صيانة البطارية'),
                'urgency': 'normal'},
        }
        alert = alerts.get(alert_type)
        if alert:
            self.send_notification(
                title=alert['title'], message=alert['message'],
                urgency=alert['urgency'], notification_type=f'ai_{alert_type}',
                play_sound=True)

    def send_ai_recommendation(self, recommendation: str, priority: int = 5) -> bool:
        """إرسال توصية من الذكاء الاصطناعي"""
        if not self.ai_recommendations_enabled:
            return False
        return self.send_notification(
            title="توصية ذكية", message=recommendation,
            urgency='normal', notification_type='ai_recommendation',
            ai_priority=priority)

    def send_optimization_notification(self, optimization_type: str,
                                       power_saved: float = 0) -> bool:
        """إشعار التحسين مع الصوت المناسب"""
        messages = {
            'started': {'title': 'بدء التحسين',
                        'message': 'جارٍ تحسين النظام لتوفير الطاقة...',
                        'urgency': 'low'},
            'completed': {'title': 'اكتمل التحسين',
                          'message': f'تم التحسين بنجاح! توفير: {power_saved:.1f}% طاقة',
                          'urgency': 'normal'},
            'auto_started': {'title': 'تحسين تلقائي',
                             'message': 'تم اكتشاف حاجة للتحسين - جارٍ التحسين...',
                             'urgency': 'low'},
            'auto_completed': {'title': 'تحسين تلقائي ناجح',
                               'message': f'تم التحسين التلقائي! توفير: {power_saved:.1f}% طاقة',
                               'urgency': 'normal'},
        }
        d = messages.get(optimization_type, messages['completed'])
        return self.send_notification(
            title=d['title'], message=d['message'], urgency=d['urgency'],
            notification_type='optimization', play_sound=True)

    def send_optimization_complete_alert(self, power_saved: float) -> bool:
        """إشعار اكتمال التحسين"""
        return self.send_notification(
            title="اكتمل التحسين",
            message=f"تم تحسين النظام بنجاح!\nتوفير متوقع: {power_saved:.0f}% من الطاقة",
            urgency='normal', notification_type='optimization_complete',
            play_sound=True)

    # ──────────────────────────────────────────────────────────────
    # الإعدادات والإحصائيات
    # ──────────────────────────────────────────────────────────────

    def get_statistics(self) -> Dict:
        return {
            'total_sent': self.stats['total_sent'],
            'total_suppressed': self.stats['total_suppressed'],
            'by_type': dict(self.stats['by_type']),
            'by_priority': dict(self.stats['by_priority']),
            'recent_notifications': list(self.notification_history[-10:]),
        }

    def get_advanced_statistics(self) -> Dict:
        return {
            **self.get_statistics(),
            'reminders_sent': self.stats['reminders_sent'],
            'sounds_played': self.stats['sounds_played'],
            'active_reminders': list(self._reminder_timers.keys()),
            'muted_reminders': sorted(self.muted_reminders),
            'battery_thresholds': dict(self.battery_thresholds),
            'smart_alerts_status': dict(self.smart_alerts),
        }

    def set_smart_timing(self, enabled: bool):
        self.smart_timing_enabled = bool(enabled)

    def set_ai_recommendations(self, enabled: bool):
        self.ai_recommendations_enabled = bool(enabled)

    def set_sound_settings(self, enabled: bool, volume: float = 0.7):
        """تعيين إعدادات الصوت"""
        self.sound_enabled = bool(enabled)
        self.sound_volume = max(0.0, min(1.0, volume))

    def clear_history(self):
        self.notification_history.clear()

    def update_battery_thresholds(self, thresholds: Dict):
        self.battery_thresholds.update(thresholds)
        logger.info(f"تم تحديث حدود البطارية: {thresholds}")

    def update_reminder_intervals(self, intervals: Dict):
        """تحديث فترات التذكير (قيم بالثواني من الواجهة)"""
        self.reminder_intervals.update({
            k: max(30, int(v)) for k, v in intervals.items()
        })

    def toggle_smart_alert(self, alert_type: str, enabled: bool):
        if alert_type in self.smart_alerts:
            self.smart_alerts[alert_type] = bool(enabled)

    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_current_battery() -> int:
        """مستوى البطارية الحالي (لشروط التذكير)"""
        try:
            import psutil
            battery = psutil.sensors_battery()
            return int(battery.percent) if battery else 50
        except Exception:
            return 50

    @staticmethod
    def _is_charging() -> bool:
        """حالة الشحن الحالية (لشروط التذكير)"""
        try:
            import psutil
            battery = psutil.sensors_battery()
            return bool(battery.power_plugged) if battery else False
        except Exception:
            return False


class NotificationManager(SmartNotificationManager):
    """اسم بديل للتوافق مع الكود القديم"""
    pass
