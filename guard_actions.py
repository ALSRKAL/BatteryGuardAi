#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
حارس البطارية: الإجراءات الفعلية - BatteryGuardAI

هذه الوحدة هي الوحيدة في التطبيق التي تلمس عمليات نظام التشغيل. لذلك قاعدتها
الأولى ليست الفعّالية بل **ألّا تُعطِّل جهاز المستخدم**.

ما تفعله فعلاً
──────────────
| الإجراء | الآلية | قابل للتراجع؟ |
|---|---|---|
| `alert` | إشعار فقط، لا لمس للعملية | لا ينطبق |
| `throttle` | `ionice` إلى الصنف الخامل | نعم، تراجع كامل |
| `throttle` (اختياري) | `renice` إلى أولوية أدنى | **لا** على هذا النظام |
| `suspend` | `SIGSTOP` | نعم، بـ `SIGCONT` |
| `terminate` | `SIGTERM` ثم `SIGKILL` | **لا** — بطلب صريح فقط |

حقيقة مهمة عن `renice`: المستخدم غير المميّز يستطيع خفض أولوية عمليته ولا
يستطيع رفعها مرة أخرى، لأن `RLIMIT_NICE` يساوي صفراً على معظم التوزيعات.
لذلك لا يُطبَّق `renice` إلا بموافقة صريحة (`allow_irreversible_nice`)، ويُعلَن
عدم إمكان التراجع بدل ادّعائه. أما `ionice` فقابل للتراجع فعلاً، وهو المستخدم
افتراضياً في الخفض.

طوق السلامة
───────────
1. **قائمة محمية صارمة**: مدير الجلسة، خادم العرض، مدير النوافذ، ناقل
   الرسائل، مدير الشبكة، مدير الصلاحيات، وكل ما يوقف إيقافه الجهاز.
2. **خيوط النواة لا تُلمس**: تُعرف بأن سطر أوامرها فارغ أو أن أباها
   `kthreadd`. إشارة إليها بلا معنى وقد تكون ضارة.
3. **عمليات المستخدم الحالي فقط**: إشارة إلى عملية مستخدم آخر سترفضها النواة،
   وطلب صلاحيات لذلك تجاوز لا يخدم البطارية.
4. **حرّاس ذاتيون**: التطبيق لا يوقف نفسه ولا مجموعة عملياته.
5. **مؤقّت إفراج إلزامي**: كل تعليق بـ `SIGSTOP` يُفرَج عنه تلقائياً بعد
   `SUSPEND_MAX_SECONDS` حتى لو انهار التطبيق، عبر خيط مراقبة مستقل.
6. **لا إيقاف تلقائي أبداً**: `terminate` لا تُنفَّذ إلا باستدعاء صريح من
   المستخدم، ولا تصل إليها أي سياسة تلقائية.
7. **إفراج شامل عند الخروج**: `release_all()` تُستدعى في مسار الإغلاق حتى لا
   تبقى عملية معلّقة بعد إغلاق التطبيق.

مراجع الآليات:
- `signal(7)` — دلالة SIGSTOP/SIGCONT وأنهما لا يمكن اعتراضهما.
  https://man7.org/linux/man-pages/man7/signal.7.html
- `getrlimit(2)` — `RLIMIT_NICE` وحدّه على رفع الأولوية.
  https://man7.org/linux/man-pages/man2/getrlimit.2.html
- `ioprio_set(2)` — أصناف أولوية الإدخال/الإخراج ومن يملك ضبطها.
  https://man7.org/linux/man-pages/man2/ioprio_set.2.html
"""

import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import psutil

from battery_intelligence import (ACTION_ALERT, ACTION_NONE, ACTION_SUSPEND,
                                  ACTION_THROTTLE, IntelligenceReport, Offender)

logger = logging.getLogger('BatteryGuard')

IS_LINUX = sys.platform.startswith('linux')
IS_WINDOWS = sys.platform == 'win32'

ACTION_TERMINATE = 'terminate'
ACTION_RESUME = 'resume'
ACTION_RESTORE = 'restore'

#: ترتيب شدّة الإجراءات، يُستخدم لتقييد السياسة بسقف أعلى
ACTION_SEVERITY = {
    ACTION_NONE: 0, ACTION_ALERT: 1, ACTION_THROTTLE: 2,
    ACTION_SUSPEND: 3, ACTION_TERMINATE: 4,
}

#: أقصى مدة تعليق قبل الإفراج الإلزامي (ثانية). خمس دقائق تكفي لتخفيف
#: الاستنزاف، ولا تكفي لأن يظنّ المستخدم أن تطبيقه تعطّل بلا سبب.
SUSPEND_MAX_SECONDS = 300.0

#: كم مرة يُفحص المعلَّقون للإفراج عنهم (ثانية)
WATCHDOG_INTERVAL = 5.0

#: مهلة انتظار الإيقاف اللطيف قبل اللجوء إلى الإيقاف القسري
TERMINATE_GRACE_SECONDS = 5.0

# ═══════════════════════════════════════════════════════════
# القائمة المحمية
# ═══════════════════════════════════════════════════════════

#: عمليات إيقافها أو خفضها يُعطّل الجلسة أو النظام. القائمة تُطابق بالاسم
#: المجرّد كما يعرضه `/proc/<pid>/comm`، وبالبادئة لما يحمل لواحق متغيّرة.
PROTECTED_NAMES: Set[str] = {
    # مدير النظام والجلسة
    'systemd', 'init', 'systemd-journald', 'systemd-logind', 'systemd-udevd',
    'systemd-oomd', 'systemd-resolved', 'systemd-timesyn', 'systemd-timesyncd',
    'dbus-daemon', 'dbus-broker', 'dbus-broker-lau', 'polkitd', 'polkit',
    'accounts-daemon', 'elogind', 'seatd',
    # خوادم العرض ومديرو النوافذ والأصداف
    'Xorg', 'X', 'Xwayland', 'wayland', 'weston', 'sway', 'labwc', 'river',
    'gnome-shell', 'gnome-session-b', 'gnome-session', 'mutter',
    'plasmashell', 'kwin_x11', 'kwin_wayland', 'ksmserver', 'kded5', 'kded6',
    'xfwm4', 'xfce4-session', 'cinnamon', 'muffin', 'marco', 'openbox',
    'i3', 'hyprland', 'Hyprland', 'awesome', 'bspwm', 'xmonad',
    # مديرو الدخول
    'gdm', 'gdm3', 'gdm-session-wor', 'sddm', 'sddm-helper', 'lightdm',
    'lxdm', 'greetd', 'ly',
    # الشبكة والصلاحيات والعتاد
    'NetworkManager', 'wpa_supplicant', 'ModemManager', 'connmand',
    'systemd-network', 'dhclient', 'dhcpcd', 'iwd', 'avahi-daemon',
    'upowerd', 'thermald', 'irqbalance', 'udisksd', 'bluetoothd',
    'sudo', 'pkexec', 'su', 'doas', 'agetty', 'login', 'sshd',
    # مدير الحزم: إيقافه في منتصف تحديث يُفسد النظام
    'dpkg', 'apt', 'apt-get', 'rpm', 'dnf', 'yum', 'pacman', 'zypper',
    'packagekitd', 'snapd', 'flatpak', 'unattended-upgr',
    # ملفات وأقراص وتشفير
    'mount', 'umount', 'fsck', 'cryptsetup', 'systemd-cryptse', 'lvmetad',
    # الصوت: إيقافه يُصمت الجهاز ويُربك التطبيقات
    'pulseaudio', 'pipewire', 'pipewire-pulse', 'wireplumber',
    # التطبيق نفسه وأدواته
    'batteryguard', 'BatteryGuardAI',
    # ويندوز
    'System', 'csrss.exe', 'wininit.exe', 'winlogon.exe', 'services.exe',
    'lsass.exe', 'smss.exe', 'dwm.exe', 'explorer.exe', 'svchost.exe',
    'fontdrvhost.exe', 'sihost.exe', 'ctfmon.exe', 'audiodg.exe',
}

#: بادئات أسماء محمية (عمليات تحمل لواحق متغيّرة)
PROTECTED_PREFIXES: Tuple[str, ...] = (
    'systemd-', 'gnome-keyring', 'gvfs', 'xdg-desktop-por', 'xdg-document',
    'at-spi', 'gsd-', 'plasma_session', 'kwallet', 'kglobalaccel',
    'kscreenlocker', 'gnome-shell-cal', 'ibus-', 'fcitx',
)


def is_kernel_thread(process: psutil.Process) -> bool:
    """
    خيط نواة لا عملية مستخدم. لا تُرسل إليه إشارات ولا تُغيَّر أولويته.

    العلامة الموثوقة: سطر أوامر فارغ (النواة لا تحمل سطر أوامر)، أو أن أباه
    هو `kthreadd` (رقم 2)، أو أنه أحد الرقمين الأولين.
    """
    try:
        if process.pid <= 2:
            return True
        if process.ppid() == 2:
            return True
        return not process.cmdline()
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return True
    except psutil.AccessDenied:
        # لا نعرف: نتعامل معه كمحمي. الحذر هنا أرخص من تعطيل جهاز.
        return True


def is_protected_name(name: str) -> bool:
    """هل الاسم في القائمة المحمية أو يبدأ ببادئة محمية"""
    if not name:
        return True
    if name in PROTECTED_NAMES:
        return True
    return name.startswith(PROTECTED_PREFIXES)


@dataclass
class SafetyVerdict:
    """حكم السلامة على عملية بعينها، مع سببه الثابت للترجمة"""
    allowed: bool
    reason: str = 'ok'
    detail: str = ''


class SafetyGate:
    """
    البوابة التي تمرّ منها كل عملية قبل أي إجراء. لا مسار يتجاوزها.
    """

    #: أقصى عمق صعود في شجرة الأبوّة عند فحص الانتماء (حماية من حلقة)
    MAX_ANCESTRY_DEPTH = 40

    def __init__(self, extra_protected: Optional[Set[str]] = None):
        self.extra_protected = {str(n) for n in (extra_protected or set())}
        self._own_pid = os.getpid()
        try:
            self._own_user = psutil.Process(self._own_pid).username()
        except (psutil.Error, OSError):
            self._own_user = None
        #: أسلاف التطبيق: إيقاف أب التطبيق (الطرفية أو الصدفة) يقتل التطبيق
        self._ancestors = self._collect_ancestors()

    def _collect_ancestors(self) -> Set[int]:
        pids: Set[int] = set()
        try:
            current = psutil.Process(self._own_pid)
            for parent in current.parents():
                pids.add(parent.pid)
        except (psutil.Error, OSError) as e:
            logger.debug(f"تعذّر جمع أسلاف التطبيق: {e}")
        return pids

    def _is_own_descendant(self, pid: int) -> bool:
        """
        هل هذه العملية من ذرّية التطبيق (عملية مساعدة أنشأها هو)؟

        نصعد شجرة الأبوّة بدل مقارنة مجموعة العمليات: مقارنة المجموعة تحمي
        كل ما أُطلق من نفس الطرفية، بما فيه متصفّح المستخدم، فتمتنع عن
        التصرّف تجاه مخالف حقيقي بلا سبب وجيه.
        """
        try:
            current = psutil.Process(pid)
            for _ in range(self.MAX_ANCESTRY_DEPTH):
                parent = current.parent()
                if parent is None:
                    return False
                if parent.pid == self._own_pid:
                    return True
                if parent.pid <= 1:
                    return False
                current = parent
        except (psutil.Error, OSError):
            return False
        return False

    def check(self, pid: int, name: str = '') -> SafetyVerdict:
        """هل يجوز التصرّف تجاه هذه العملية؟ الرفض هو الافتراضي عند الشك."""
        if pid <= 0:
            return SafetyVerdict(False, 'invalid_pid')
        if pid == self._own_pid:
            return SafetyVerdict(False, 'self')
        if pid in self._ancestors:
            return SafetyVerdict(False, 'ancestor',
                                 'إيقافها يقتل التطبيق نفسه')
        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return SafetyVerdict(False, 'gone')
        except psutil.Error as e:
            return SafetyVerdict(False, 'unreadable', str(e))

        try:
            actual_name = process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return SafetyVerdict(False, 'unreadable')

        if name and actual_name != name:
            # رقم العملية أُعيد استخدامه بين الاستدلال والتنفيذ. التصرّف الآن
            # يعني إيقاف عملية بريئة، وهو أسوأ من عدم التصرّف.
            return SafetyVerdict(False, 'pid_reused',
                                 f'{name} ← {actual_name}')

        if is_protected_name(actual_name) or actual_name in self.extra_protected:
            return SafetyVerdict(False, 'protected', actual_name)
        if is_kernel_thread(process):
            return SafetyVerdict(False, 'kernel_thread', actual_name)

        if self._is_own_descendant(pid):
            return SafetyVerdict(False, 'own_descendant', actual_name)

        try:
            if self._own_user and process.username() != self._own_user:
                return SafetyVerdict(False, 'other_user', process.username())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return SafetyVerdict(False, 'unreadable')

        return SafetyVerdict(True, 'ok', actual_name)


# ═══════════════════════════════════════════════════════════
# السياسة
# ═══════════════════════════════════════════════════════════

@dataclass
class GuardPolicy:
    """
    ما يُسمح للحارس بفعله. الافتراضات محافظة عن قصد: يعمل، لكنه لا يوقف
    شيئاً حتى يطلب المستخدم ذلك صراحةً.
    """
    enabled: bool = True
    #: هل ينفّذ تلقائياً أم يقترح فقط ويترك القرار للمستخدم
    automatic: bool = False
    #: أقصى شدّة مسموحة، حتى لو أوصى الاستدلال بأكثر
    max_action: str = ACTION_ALERT
    #: لا يتصرّف إلا حين يعمل الجهاز على البطارية
    only_on_battery: bool = True
    #: مستوى شحن يبدأ عنده التصرّف التلقائي (فوقه: التنبيه فقط)
    act_below_percent: int = 100
    #: أسماء يسمح المستخدم صراحةً بالتصرّف تجاهها
    allowlist: List[str] = field(default_factory=list)
    #: أسماء يمنع المستخدم لمسها (تُضاف إلى القائمة المحمية)
    blocklist: List[str] = field(default_factory=list)
    #: السماح بـ renice غير القابل للتراجع على هذا النظام
    allow_irreversible_nice: bool = False
    #: أقل درجة ضرر تستدعي إجراءً
    min_damage_score: float = 45.0
    #: أقل ثقة تستدعي إجراءً تلقائياً (الثقة المنخفضة تُنبِّه ولا تتصرّف)
    min_confidence: int = 55

    def cap(self, action: str) -> str:
        """تقييد إجراء موصى به بسقف السياسة"""
        allowed = ACTION_SEVERITY.get(self.max_action, 1)
        if ACTION_SEVERITY.get(action, 0) <= allowed:
            return action
        for name in (ACTION_SUSPEND, ACTION_THROTTLE, ACTION_ALERT, ACTION_NONE):
            if ACTION_SEVERITY[name] <= allowed:
                return name
        return ACTION_NONE

    def as_dict(self) -> Dict[str, object]:
        return {
            'enabled': self.enabled, 'automatic': self.automatic,
            'max_action': self.max_action, 'only_on_battery': self.only_on_battery,
            'act_below_percent': self.act_below_percent,
            'allowlist': list(self.allowlist), 'blocklist': list(self.blocklist),
            'allow_irreversible_nice': self.allow_irreversible_nice,
            'min_damage_score': self.min_damage_score,
            'min_confidence': self.min_confidence,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> 'GuardPolicy':
        """بناء سياسة من إعدادات محفوظة، مع تجاهل أي قيمة غير صالحة"""
        policy = cls()
        if not isinstance(data, dict):
            return policy
        policy.enabled = bool(data.get('enabled', policy.enabled))
        policy.automatic = bool(data.get('automatic', policy.automatic))
        candidate = str(data.get('max_action', policy.max_action))
        if candidate in ACTION_SEVERITY and candidate != ACTION_TERMINATE:
            # `terminate` غير مسموح كسقف سياسة: لا إيقاف تلقائي أبداً
            policy.max_action = candidate
        policy.only_on_battery = bool(data.get('only_on_battery',
                                               policy.only_on_battery))
        try:
            policy.act_below_percent = max(1, min(100, int(
                data.get('act_below_percent', policy.act_below_percent))))
        except (TypeError, ValueError):
            pass
        for key in ('allowlist', 'blocklist'):
            values = data.get(key)
            if isinstance(values, list):
                setattr(policy, key, [str(v) for v in values if str(v).strip()])
        policy.allow_irreversible_nice = bool(
            data.get('allow_irreversible_nice', policy.allow_irreversible_nice))
        try:
            policy.min_damage_score = max(0.0, min(100.0, float(
                data.get('min_damage_score', policy.min_damage_score))))
        except (TypeError, ValueError):
            pass
        try:
            policy.min_confidence = max(0, min(99, int(
                data.get('min_confidence', policy.min_confidence))))
        except (TypeError, ValueError):
            pass
        return policy


# ═══════════════════════════════════════════════════════════
# نتيجة الإجراء
# ═══════════════════════════════════════════════════════════

@dataclass
class GuardOutcome:
    """
    ما حدث فعلاً. `applied=False` مع `reason` صريح أصدق من ادّعاء نجاح.
    """
    kind: str
    name: str
    pids: List[int] = field(default_factory=list)
    applied: bool = False
    reason: str = ''
    detail: str = ''
    reversible: bool = True
    affected: int = 0
    skipped: Dict[str, int] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def as_dict(self) -> Dict[str, object]:
        return {
            'kind': self.kind, 'name': self.name, 'pids': list(self.pids),
            'applied': self.applied, 'reason': self.reason, 'detail': self.detail,
            'reversible': self.reversible, 'affected': self.affected,
            'skipped': dict(self.skipped), 'timestamp': self.timestamp,
        }


@dataclass
class _Intervention:
    """تدخّل نشط يجب التراجع عنه"""
    name: str
    kind: str
    pids: List[int]
    started: float
    #: أولويات الإدخال/الإخراج الأصلية {pid: (class, value)}
    original_ionice: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    #: قيم nice الأصلية {pid: nice}؛ استعادتها قد تفشل بلا صلاحيات
    original_nice: Dict[int, int] = field(default_factory=dict)
    expires_at: Optional[float] = None


# ═══════════════════════════════════════════════════════════
# الحارس
# ═══════════════════════════════════════════════════════════

class BatteryGuard:
    """
    ينفّذ ما يوصي به `battery_intelligence`، داخل حدود `GuardPolicy` وطوق
    `SafetyGate`، ويُبلّغ عن كل ما لم يفعله وسببه.
    """

    def __init__(self, policy: Optional[GuardPolicy] = None,
                 dry_run: bool = False,
                 notifier=None):
        self.policy = policy or GuardPolicy()
        #: وضع التجربة: يقرّر ولا ينفّذ. تستخدمه الاختبارات والعرض المسبق.
        self.dry_run = bool(dry_run)
        #: دالة تُستدعى لإبلاغ المستخدم: notifier(kind, offender, outcome)
        self.notifier = notifier

        self._lock = threading.RLock()
        self._gate = SafetyGate(set(self.policy.blocklist))
        self._interventions: Dict[str, _Intervention] = {}
        self.history: List[GuardOutcome] = []

        self._watchdog_stop = threading.Event()
        self._watchdog: Optional[threading.Thread] = None
        if not self.dry_run:
            self._start_watchdog()

    # ── السياسة ─────────────────────────────────────────────

    def update_policy(self, policy: GuardPolicy) -> None:
        """تحديث السياسة وإعادة بناء البوابة (قائمة المنع قد تغيّرت)"""
        with self._lock:
            self.policy = policy
            self._gate = SafetyGate(set(policy.blocklist))
        logger.info(f"سياسة الحارس: مفعّل={policy.enabled} تلقائي={policy.automatic} "
                    f"سقف={policy.max_action}")

    # ── التقييم ─────────────────────────────────────────────

    def plan(self, report: IntelligenceReport, battery_status: Dict) -> List[Tuple[Offender, str, str]]:
        """
        ماذا يجب فعله، بلا تنفيذ. يعيد (المخالف، الإجراء، سبب القرار).
        الإجراء `none` يعني «لا تفعل شيئاً»، والسبب يقول لماذا.
        """
        decisions: List[Tuple[Offender, str, str]] = []
        if not self.policy.enabled:
            return decisions

        charging = bool(battery_status.get('is_charging'))
        percent = int(battery_status.get('percent') or 0)
        reporting = bool(battery_status.get('reporting', True))

        for offender in report.offenders:
            if offender.damage_score < self.policy.min_damage_score:
                continue
            if offender.name in self.policy.blocklist:
                decisions.append((offender, ACTION_NONE, 'blocklisted'))
                continue

            action = self.policy.cap(offender.recommended_action)
            if action == ACTION_NONE:
                continue

            # قياس غير موثوق: ننبّه ولا نتصرّف بناءً على رقم مشكوك فيه
            if not reporting:
                action = ACTION_ALERT
                decisions.append((offender, action, 'not_reporting'))
                continue
            if self.policy.only_on_battery and charging:
                decisions.append((offender, ACTION_ALERT, 'on_mains'))
                continue
            if percent >= self.policy.act_below_percent and action != ACTION_ALERT:
                decisions.append((offender, ACTION_ALERT, 'above_threshold'))
                continue
            if offender.confidence < self.policy.min_confidence and action != ACTION_ALERT:
                decisions.append((offender, ACTION_ALERT, 'low_confidence'))
                continue
            if (action in (ACTION_THROTTLE, ACTION_SUSPEND)
                    and self.policy.allowlist
                    and offender.name not in self.policy.allowlist):
                decisions.append((offender, ACTION_ALERT, 'not_allowlisted'))
                continue

            decisions.append((offender, action, 'policy'))
        return decisions

    def enforce(self, report: IntelligenceReport,
                battery_status: Dict) -> List[GuardOutcome]:
        """
        تنفيذ الخطة. في الوضع غير التلقائي تُنفَّذ التنبيهات فقط ويُترك
        ما فوقها للمستخدم، فلا يجد جهازه تغيّر بلا إذنه.
        """
        outcomes: List[GuardOutcome] = []
        for offender, action, reason in self.plan(report, battery_status):
            if action == ACTION_NONE:
                continue
            if action != ACTION_ALERT and not self.policy.automatic:
                outcomes.append(self._alert(offender, 'manual_mode'))
                continue
            if action == ACTION_ALERT:
                outcomes.append(self._alert(offender, reason))
            elif action == ACTION_THROTTLE:
                outcomes.append(self.throttle(offender.name, offender.pids))
            elif action == ACTION_SUSPEND:
                outcomes.append(self.suspend(offender.name, offender.pids))
        return outcomes

    def _alert(self, offender: Offender, reason: str) -> GuardOutcome:
        outcome = GuardOutcome(
            kind=ACTION_ALERT, name=offender.name, pids=list(offender.pids),
            applied=True, reason=reason,
            detail=f"{offender.watts:.1f}W · درجة {offender.damage_score:.0f}",
            reversible=True, affected=0)
        self._record(outcome, offender)
        return outcome

    # ── الإجراءات ───────────────────────────────────────────

    def _eligible(self, name: str, pids: List[int]) -> Tuple[List[psutil.Process], Dict[str, int]]:
        """تصفية العمليات عبر بوابة السلامة، مع إحصاء أسباب الرفض"""
        allowed: List[psutil.Process] = []
        skipped: Dict[str, int] = {}
        for pid in pids:
            verdict = self._gate.check(pid, name)
            if not verdict.allowed:
                skipped[verdict.reason] = skipped.get(verdict.reason, 0) + 1
                continue
            try:
                allowed.append(psutil.Process(pid))
            except psutil.Error:
                skipped['gone'] = skipped.get('gone', 0) + 1
        return allowed, skipped

    def throttle(self, name: str, pids: List[int]) -> GuardOutcome:
        """
        خفض أولوية الإدخال/الإخراج إلى الصنف الخامل (قابل للتراجع)، وخفض
        أولوية المعالج فقط إن سمح المستخدم بذلك صراحةً (غير قابل للتراجع).
        """
        processes, skipped = self._eligible(name, pids)
        outcome = GuardOutcome(kind=ACTION_THROTTLE, name=name, pids=list(pids),
                               skipped=skipped, reversible=True)
        if not processes:
            outcome.reason = 'no_eligible_process'
            return outcome
        if self.dry_run:
            outcome.applied = True
            outcome.reason = 'dry_run'
            outcome.affected = len(processes)
            return outcome

        with self._lock:
            intervention = self._interventions.get(name)
            if intervention is None:
                intervention = self._interventions[name] = _Intervention(
                    name=name, kind=ACTION_THROTTLE, pids=[], started=time.time())

            affected = 0
            for process in processes:
                try:
                    if hasattr(process, 'ionice'):
                        current = process.ionice()
                        if process.pid not in intervention.original_ionice:
                            intervention.original_ionice[process.pid] = (
                                int(getattr(current, 'ioclass', current)),
                                int(getattr(current, 'value', 0)))
                        process.ionice(psutil.IOPRIO_CLASS_IDLE)
                        affected += 1
                    if self.policy.allow_irreversible_nice:
                        if process.pid not in intervention.original_nice:
                            intervention.original_nice[process.pid] = process.nice()
                        process.nice(19)
                        outcome.reversible = False
                    if process.pid not in intervention.pids:
                        intervention.pids.append(process.pid)
                except (psutil.NoSuchProcess, psutil.ZombieProcess):
                    skipped['gone'] = skipped.get('gone', 0) + 1
                except psutil.AccessDenied:
                    skipped['denied'] = skipped.get('denied', 0) + 1
                except (OSError, ValueError) as e:
                    skipped['error'] = skipped.get('error', 0) + 1
                    logger.debug(f"تعذّر خفض أولوية {name}/{process.pid}: {e}")

            if not intervention.pids:
                self._interventions.pop(name, None)

        outcome.affected = affected
        outcome.applied = affected > 0
        outcome.reason = 'throttled' if affected else 'all_failed'
        if not outcome.reversible:
            outcome.detail = 'أولوية المعالج غير قابلة للاستعادة بلا صلاحيات'
        self._record(outcome, None)
        return outcome

    def suspend(self, name: str, pids: List[int]) -> GuardOutcome:
        """
        تعليق العملية بـ `SIGSTOP`. قابل للتراجع تماماً، ومحدود بمؤقّت إفراج
        إلزامي حتى لا تبقى معلّقة إن انهار التطبيق.
        """
        processes, skipped = self._eligible(name, pids)
        outcome = GuardOutcome(kind=ACTION_SUSPEND, name=name, pids=list(pids),
                               skipped=skipped, reversible=True)
        if not processes:
            outcome.reason = 'no_eligible_process'
            return outcome
        if self.dry_run:
            outcome.applied = True
            outcome.reason = 'dry_run'
            outcome.affected = len(processes)
            return outcome

        stop_signal = getattr(signal, 'SIGSTOP', None)
        if stop_signal is None:
            outcome.reason = 'unsupported_platform'
            return outcome

        with self._lock:
            intervention = self._interventions.get(name)
            if intervention is None or intervention.kind != ACTION_SUSPEND:
                intervention = self._interventions[name] = _Intervention(
                    name=name, kind=ACTION_SUSPEND, pids=[], started=time.time())
            intervention.expires_at = time.time() + SUSPEND_MAX_SECONDS

            affected = 0
            for process in processes:
                try:
                    process.send_signal(stop_signal)
                    if process.pid not in intervention.pids:
                        intervention.pids.append(process.pid)
                    affected += 1
                except (psutil.NoSuchProcess, psutil.ZombieProcess):
                    skipped['gone'] = skipped.get('gone', 0) + 1
                except psutil.AccessDenied:
                    skipped['denied'] = skipped.get('denied', 0) + 1
                except OSError as e:
                    skipped['error'] = skipped.get('error', 0) + 1
                    logger.debug(f"تعذّر تعليق {name}/{process.pid}: {e}")

            if not intervention.pids:
                self._interventions.pop(name, None)

        outcome.affected = affected
        outcome.applied = affected > 0
        outcome.reason = 'suspended' if affected else 'all_failed'
        outcome.detail = f'إفراج إلزامي بعد {int(SUSPEND_MAX_SECONDS)} ثانية'
        self._record(outcome, None)
        if affected:
            logger.info(f"عُلِّقت {affected} عملية من {name} "
                        f"(إفراج تلقائي بعد {int(SUSPEND_MAX_SECONDS)}ث)")
        return outcome

    def resume(self, name: str) -> GuardOutcome:
        """الإفراج عن عملية معلّقة بـ `SIGCONT`"""
        with self._lock:
            intervention = self._interventions.get(name)
            if intervention is None or intervention.kind != ACTION_SUSPEND:
                return GuardOutcome(kind=ACTION_RESUME, name=name,
                                    reason='not_suspended')
            pids = list(intervention.pids)

        outcome = GuardOutcome(kind=ACTION_RESUME, name=name, pids=pids)
        continue_signal = getattr(signal, 'SIGCONT', None)
        if continue_signal is None:
            outcome.reason = 'unsupported_platform'
            return outcome

        affected = 0
        for pid in pids:
            try:
                psutil.Process(pid).send_signal(continue_signal)
                affected += 1
            except psutil.NoSuchProcess:
                continue  # انتهت وهي معلّقة: لا شيء لنفعله
            except (psutil.Error, OSError) as e:
                outcome.skipped['error'] = outcome.skipped.get('error', 0) + 1
                logger.warning(f"تعذّر الإفراج عن {name}/{pid}: {e}")

        with self._lock:
            self._interventions.pop(name, None)
        outcome.affected = affected
        outcome.applied = True
        outcome.reason = 'resumed'
        self._record(outcome, None)
        logger.info(f"أُفرج عن {affected} عملية من {name}")
        return outcome

    def restore(self, name: str) -> GuardOutcome:
        """
        إرجاع الأولويات إلى ما كانت. استعادة `nice` قد تفشل بلا صلاحيات،
        وهذا يُعلَن في `skipped` بدل تجاهله.
        """
        with self._lock:
            intervention = self._interventions.get(name)
            if intervention is None or intervention.kind != ACTION_THROTTLE:
                return GuardOutcome(kind=ACTION_RESTORE, name=name,
                                    reason='not_throttled')
            ionice_map = dict(intervention.original_ionice)
            nice_map = dict(intervention.original_nice)

        outcome = GuardOutcome(kind=ACTION_RESTORE, name=name,
                               pids=sorted(set(ionice_map) | set(nice_map)))
        affected = 0
        for pid, (ioclass, value) in ionice_map.items():
            try:
                process = psutil.Process(pid)
                if ioclass == int(psutil.IOPRIO_CLASS_NONE):
                    process.ionice(psutil.IOPRIO_CLASS_BE, 4)
                else:
                    process.ionice(ioclass, value)
                affected += 1
            except psutil.NoSuchProcess:
                continue
            except (psutil.Error, OSError, ValueError) as e:
                outcome.skipped['ionice_failed'] = outcome.skipped.get('ionice_failed', 0) + 1
                logger.debug(f"تعذّرت استعادة ionice لـ {name}/{pid}: {e}")

        for pid, nice_value in nice_map.items():
            try:
                psutil.Process(pid).nice(nice_value)
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                # حقيقة النظام: رفع الأولوية يحتاج صلاحيات لا نملكها
                outcome.skipped['nice_needs_privilege'] = \
                    outcome.skipped.get('nice_needs_privilege', 0) + 1
                outcome.reversible = False
            except (psutil.Error, OSError, ValueError) as e:
                outcome.skipped['nice_failed'] = outcome.skipped.get('nice_failed', 0) + 1
                logger.debug(f"تعذّرت استعادة nice لـ {name}/{pid}: {e}")

        with self._lock:
            self._interventions.pop(name, None)
        outcome.affected = affected
        outcome.applied = True
        outcome.reason = 'restored'
        self._record(outcome, None)
        return outcome

    def terminate(self, name: str, pids: List[int]) -> GuardOutcome:
        """
        إيقاف العملية: `SIGTERM` ثم `SIGKILL` لمن لم يستجب.

        **لا تُستدعى تلقائياً أبداً.** لا مسار من `enforce` أو `plan` يصل
        إليها، والسبب واضح: خسارة عمل المستخدم غير المحفوظ أغلى من أي واط.
        """
        processes, skipped = self._eligible(name, pids)
        outcome = GuardOutcome(kind=ACTION_TERMINATE, name=name, pids=list(pids),
                               skipped=skipped, reversible=False)
        if not processes:
            outcome.reason = 'no_eligible_process'
            return outcome
        if self.dry_run:
            outcome.applied = True
            outcome.reason = 'dry_run'
            outcome.affected = len(processes)
            return outcome

        # عملية معلّقة لا تستجيب لـ SIGTERM: يجب الإفراج عنها أولاً
        self.resume(name)

        for process in processes:
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                continue
            except (psutil.Error, OSError) as e:
                skipped['error'] = skipped.get('error', 0) + 1
                logger.debug(f"تعذّر إيقاف {name}/{process.pid}: {e}")

        gone, alive = psutil.wait_procs(processes, timeout=TERMINATE_GRACE_SECONDS)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                continue
            except (psutil.Error, OSError) as e:
                skipped['kill_failed'] = skipped.get('kill_failed', 0) + 1
                logger.warning(f"تعذّر الإيقاف القسري لـ {name}/{process.pid}: {e}")
        killed, still_alive = psutil.wait_procs(alive, timeout=2.0)

        outcome.affected = len(gone) + len(killed)
        outcome.applied = outcome.affected > 0
        outcome.reason = 'terminated' if not still_alive else 'partial'
        if still_alive:
            outcome.detail = f'{len(still_alive)} عملية لم تتوقف'
        self._record(outcome, None)
        logger.warning(f"أُوقفت {outcome.affected} عملية من {name} بطلب المستخدم")
        return outcome

    # ── التدخّلات النشطة ────────────────────────────────────

    def active_interventions(self) -> Dict[str, Dict[str, object]]:
        """ما هو مُعلَّق أو مخفوض الآن، وكم بقي قبل الإفراج الإلزامي"""
        now = time.time()
        with self._lock:
            return {
                name: {
                    'kind': item.kind,
                    'pids': list(item.pids),
                    'seconds_active': round(now - item.started, 1),
                    'seconds_left': (None if item.expires_at is None
                                     else max(0.0, round(item.expires_at - now, 1))),
                }
                for name, item in self._interventions.items()
            }

    def release_all(self) -> List[GuardOutcome]:
        """
        الإفراج عن كل تدخّل نشط. تُستدعى في مسار الإغلاق، ولا يجوز أن يُغلق
        التطبيق دونها: عملية معلّقة بعد اختفاء من علّقها مشكلة لا يفهمها أحد.
        """
        with self._lock:
            names = [(name, item.kind) for name, item in self._interventions.items()]
        outcomes: List[GuardOutcome] = []
        for name, kind in names:
            try:
                if kind == ACTION_SUSPEND:
                    outcomes.append(self.resume(name))
                else:
                    outcomes.append(self.restore(name))
            except Exception as e:  # الإغلاق لا يجوز أن يفشل بسبب عملية واحدة
                logger.error(f"تعذّر الإفراج عن {name}: {e}")
        return outcomes

    def stop(self) -> None:
        """إيقاف خيط المراقبة والإفراج عن كل شيء"""
        self._watchdog_stop.set()
        watchdog = self._watchdog
        if watchdog is not None and watchdog.is_alive():
            watchdog.join(timeout=WATCHDOG_INTERVAL * 2)
        self.release_all()

    # ── خيط الإفراج الإلزامي ────────────────────────────────

    def _start_watchdog(self) -> None:
        self._watchdog = threading.Thread(
            target=self._watchdog_loop, name='guard-watchdog', daemon=True)
        self._watchdog.start()

    def _watchdog_loop(self) -> None:
        """
        يُفرج عن كل تعليق تجاوز مدّته، ويُنظّف التدخّلات على عمليات انتهت.
        خيط مستقل حتى لا يعتمد الإفراج على سلامة خيط الواجهة.
        """
        while not self._watchdog_stop.wait(WATCHDOG_INTERVAL):
            try:
                now = time.time()
                with self._lock:
                    expired = [name for name, item in self._interventions.items()
                               if item.expires_at is not None and item.expires_at <= now]
                    stale = [name for name, item in self._interventions.items()
                             if not any(psutil.pid_exists(pid) for pid in item.pids)]
                for name in expired:
                    logger.info(f"انتهت مدة تعليق {name} - إفراج تلقائي")
                    self.resume(name)
                for name in stale:
                    if name in expired:
                        continue
                    with self._lock:
                        self._interventions.pop(name, None)
            except Exception as e:  # الخيط لا يجوز أن يموت
                logger.error(f"خطأ في خيط إفراج الحارس: {e}")

    # ── السجل ───────────────────────────────────────────────

    def _record(self, outcome: GuardOutcome, offender: Optional[Offender]) -> None:
        self.history.append(outcome)
        if len(self.history) > 200:
            del self.history[:len(self.history) - 200]
        if self.notifier is not None:
            try:
                self.notifier(outcome, offender)
            except Exception as e:
                logger.debug(f"مُبلِّغ الحارس أخفق: {e}")

    def recent_history(self, count: int = 20) -> List[Dict[str, object]]:
        return [item.as_dict() for item in self.history[-count:]]
