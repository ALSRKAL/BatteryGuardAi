#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إشارات الإغلاق - BatteryGuardAI

يجعل التطبيق يُغلق نظيفاً عند `SIGTERM` و`SIGINT`، لا أن يُقتل في منتصف عمله.

لماذا هذا ضروري ولا يجوز إهماله
────────────────────────────────
`systemctl stop` وتسجيل الخروج وإعادة تشغيل الجهاز كلها ترسل `SIGTERM`.
سلوك بايثون الافتراضي معه هو الموت الفوري بلا تنفيذ أي تنظيف، وأثر ذلك في
تطبيق يعمل في الخلفية دائماً ثلاثة أضرار حقيقية:

1. **عملية معلّقة تبقى معلّقة**: إن كان الحارس قد أوقف عملية بـ `SIGSTOP`،
   فإفراجها يجري في مسار الإغلاق. الموت الفوري يترك عملية المستخدم متوقفة
   بلا سبب مفهوم وبلا من يُفرج عنها.
2. **يُفقد ما تعلّمه اليوم**: بيانات التعلّم وحالة نموذج الطاقة تُحفظ دورياً
   وعند الخروج. الموت الفوري يُلغي كل ما جُمع بعد آخر حفظ.
3. **الحدود المكتوبة في العتاد** لا يُعاد ضبطها كما يتوقّع المستخدم.

عقبة Qt
───────
معالِج إشارة في بايثون لا يُنفَّذ إلا حين يُشغّل المفسّر شيفرة بايثون، وحلقة
أحداث Qt تنتظر داخل C++ فلا تعود إلى المفسّر. الحلّ المستخدم هنا هو
`signal.set_wakeup_fd` مع `QSocketNotifier`: تكتب النواة بايتاً في مقبس عند
الإشارة، فتستيقظ حلقة Qt وتعطي المفسّر فرصة تنفيذ المعالِج على الخيط الرئيسي.
هذا أدقّ من مؤقّت يستفيق دورياً، ولا يوقظ المعالج بلا داعٍ — وهو فرق مهمّ في
تطبيق غرضه توفير البطارية.

المراجع:
- `signal.set_wakeup_fd` — كتابة رقم الإشارة في واصف ملف.
  https://docs.python.org/3/library/signal.html#signal.set_wakeup_fd
- `systemd.kill(5)` — `SIGTERM` ثم `SIGKILL` بعد `TimeoutStopSec`.
  https://www.freedesktop.org/software/systemd/man/systemd.kill.html
"""

import logging
import signal
import socket
from typing import Callable, List, Optional

from PyQt6.QtCore import QObject, QSocketNotifier, QTimer

logger = logging.getLogger('BatteryGuard')

#: الإشارات التي تعني «أغلق نظيفاً الآن»
SHUTDOWN_SIGNALS = ('SIGTERM', 'SIGINT', 'SIGHUP')

#: مهلة قصوى للإغلاق النظيف قبل الخروج القسري (مللي ثانية).
#: أقصر من `TimeoutStopSec=15` في ملف الوحدة حتى نُغلق نحن قبل أن يقتلنا
#: systemd، فيبقى الإغلاق نظيفاً لا مقطوعاً.
FORCED_EXIT_MS = 12_000


class ShutdownHandler(QObject):
    """
    يحوّل إشارات نظام التشغيل إلى نداء إغلاق واحد على الخيط الرئيسي.

    الإغلاق يجري مرة واحدة فقط: إشارة ثانية أثناء الإغلاق تعني أن المستخدم
    أو النظام مستعجل، فنخرج قسراً بدل تجاهلها.
    """

    def __init__(self, on_shutdown: Callable[[], None]):
        super().__init__()
        self._on_shutdown = on_shutdown
        self._shutting_down = False
        self._notifier: Optional[QSocketNotifier] = None
        self._read_socket: Optional[socket.socket] = None
        self._write_socket: Optional[socket.socket] = None
        self._previous: List[tuple] = []
        self._installed: List[str] = []

    # ── التركيب ─────────────────────────────────────────────

    def install(self) -> List[str]:
        """
        تركيب المعالِج. يعيد أسماء الإشارات التي رُكّبت فعلاً.

        الفشل هنا لا يمنع التطبيق من العمل: يبقى يعمل بلا إغلاق نظيف، وهذا
        يُسجَّل بوضوح بدل أن يُخفى.
        """
        try:
            self._read_socket, self._write_socket = socket.socketpair()
            self._read_socket.setblocking(False)
            self._write_socket.setblocking(False)
            signal.set_wakeup_fd(self._write_socket.fileno())
            self._notifier = QSocketNotifier(
                self._read_socket.fileno(), QSocketNotifier.Type.Read, self)
            self._notifier.activated.connect(self._drain)
        except (OSError, ValueError) as e:
            logger.error(f"تعذّر تركيب موقظ الإشارات: {e} - "
                         f"الإغلاق عند SIGTERM لن يكون نظيفاً")
            return []

        for name in SHUTDOWN_SIGNALS:
            number = getattr(signal, name, None)
            if number is None:
                continue
            try:
                self._previous.append((number, signal.getsignal(number)))
                signal.signal(number, self._handle)
                self._installed.append(name)
            except (OSError, ValueError, RuntimeError) as e:
                logger.debug(f"تعذّر تركيب معالِج {name}: {e}")

        logger.info(f"معالِج الإغلاق النظيف مركّب: {', '.join(self._installed)}")
        return list(self._installed)

    def uninstall(self) -> None:
        """إرجاع المعالِجات الأصلية وإغلاق المقابس"""
        for number, handler in self._previous:
            try:
                signal.signal(number, handler)
            except (OSError, ValueError, RuntimeError):
                pass
        self._previous.clear()
        try:
            signal.set_wakeup_fd(-1)
        except (OSError, ValueError):
            pass
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier = None
        for sock in (self._read_socket, self._write_socket):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        self._read_socket = self._write_socket = None

    # ── الاستقبال ───────────────────────────────────────────

    def _drain(self) -> None:
        """
        تفريغ المقبس. القراءة نفسها هي الغرض: مجرّد استيقاظ حلقة Qt يكفي
        لأن المفسّر ينفّذ معالِج الإشارة قبل أن يعود إلى الحلقة.
        """
        if self._read_socket is None:
            return
        try:
            self._read_socket.recv(64)
        except (BlockingIOError, InterruptedError, OSError):
            pass

    def _handle(self, signum, _frame) -> None:
        """معالِج الإشارة نفسه: يُجدول الإغلاق ولا ينفّذه داخل المعالِج"""
        name = signal.Signals(signum).name if signum in iter(signal.Signals) \
            else str(signum)
        if self._shutting_down:
            logger.warning(f"{name} أثناء الإغلاق - خروج قسري")
            self.uninstall()
            # الخروج القسري بعد إشارة ثانية: النظام أو المستخدم مستعجل، وإطالة
            # الانتظار تعني قتلاً بـ SIGKILL يفقد كل شيء بدل بعضه.
            import os
            os._exit(1)
        self._shutting_down = True
        logger.info(f"استُقبلت {name} - بدء الإغلاق النظيف")

        # حبل نجاة: لو تعلّق الإغلاق (عتاد لا يستجيب مثلاً) نخرج قبل SIGKILL
        QTimer.singleShot(FORCED_EXIT_MS, self._force_exit)
        # التنفيذ على الخيط الرئيسي بعد عودة السيطرة من معالِج الإشارة:
        # استدعاء شيفرة Qt داخل المعالِج نفسه سلوك غير معرَّف.
        QTimer.singleShot(0, self._run_shutdown)

    def _run_shutdown(self) -> None:
        try:
            self._on_shutdown()
        except Exception as e:
            logger.error(f"فشل الإغلاق النظيف: {e}", exc_info=True)
            self._force_exit()

    @staticmethod
    def _force_exit() -> None:
        """خروج قسري: يُستدعى فقط إن تجاوز الإغلاق النظيف مهلته"""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            import os
            os._exit(1)
            return
        # إن كانت الحلقة قد انتهت أصلاً فهذا النداء بلا أثر، وهو المطلوب
        logger.warning("تجاوز الإغلاق مهلته - إنهاء حلقة الأحداث قسراً")
        app.quit()


def install_shutdown_handler(on_shutdown: Callable[[], None]) -> ShutdownHandler:
    """
    تركيب معالِج الإغلاق وإرجاعه.

    يجب الاحتفاظ بالمرجع المُعاد: `QSocketNotifier` يتوقّف عن العمل إن جمعه
    جامع النفايات، فيصير التطبيق كأنه بلا معالِج بلا أي رسالة خطأ.
    """
    handler = ShutdownHandler(on_shutdown)
    handler.install()
    return handler
