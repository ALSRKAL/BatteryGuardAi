#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تثبيت التشغيل الدائم في الخلفية - BatteryGuardAI

الهدف بجملة واحدة: أن يعمل التطبيق بأيقونة في شريط المهام، ويبقى يعمل بعد
إغلاق الطرفية، ويعود وحده بعد إعادة تشغيل الجهاز.

لماذا خدمة systemd للمستخدم لا للنظام
──────────────────────────────────────
النسخة السابقة كانت تكتب وحدة على مستوى النظام في
`/etc/systemd/system/batteryguard.service`، وفيها ثلاثة أخطاء تجعلها لا تعمل:

1. `ProtectHome=read-only` مع كتابة التطبيق إلى `~/.config/batteryguard`:
   الخدمة تبدأ ثم تفشل عند أول حفظ لبيانات التعلّم.
2. `XDG_RUNTIME_DIR=/run/user/$(id -u user)`: systemd لا يشغّل صدفة، فلا
   يُوسَّع `$(...)`، فتصير القيمة نصاً حرفياً ولا يجد التطبيق ناقل الرسائل.
3. `WantedBy=graphical.target` لوحدة نظام: الهدف الرسومي على مستوى النظام لا
   يعرف جلسة مستخدم بعينها، فلا تجد الأيقونة صينية تسكنها.

خدمة **المستخدم** تحلّ الثلاثة معاً: تعمل بهوية المستخدم داخل جلسته، وترث
`DISPLAY` و`DBUS_SESSION_BUS_ADDRESS` من مدير المستخدم، ولا تحتاج `sudo`.

طبقتان بحسب ما يتوفّر
─────────────────────
| الطريقة | متى تُستخدم | ما تضمنه |
|---|---|---|
| خدمة systemd للمستخدم | متوفّر مدير مستخدم يعمل | بقاء بعد إغلاق الطرفية، عودة بعد الإقلاع، إعادة تشغيل تلقائية عند الفشل |
| ملف `.desktop` للتشغيل التلقائي | لا يوجد systemd للمستخدم | عودة بعد الإقلاع فقط، بلا إعادة تشغيل عند الفشل |

`linger`
────────
افتراضياً يتوقّف مدير مستخدم systemd عند آخر خروج للمستخدم. `loginctl
enable-linger` يجعله باقياً، فتعمل الخدمة قبل تسجيل الدخول وبعد الخروج. لا
تُفعّله هذه الوحدة تلقائياً لأنه يحتاج صلاحيات، بل تعرض الأمر ليقرّر المستخدم.

مراجع:
- `systemd.unit(5)` — الأهداف و`WantedBy` وترتيب الوحدات.
  https://www.freedesktop.org/software/systemd/man/systemd.unit.html
- `systemd.service(5)` — `Restart` و`RestartSec` و`Type`.
  https://www.freedesktop.org/software/systemd/man/systemd.service.html
- `loginctl(1)` — `enable-linger`.
  https://www.freedesktop.org/software/systemd/man/loginctl.html
- XDG Desktop Application Autostart Specification — مجلد `autostart`.
  https://specifications.freedesktop.org/autostart-spec/autostart-spec-latest.html
"""

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger('BatteryGuard')

IS_LINUX = sys.platform.startswith('linux')
IS_WINDOWS = sys.platform == 'win32'

#: اسم الوحدة والمهمة، مصدر واحد لكل من يشير إليهما
SERVICE_NAME = 'batteryguard.service'
DESKTOP_NAME = 'batteryguard.desktop'
WINDOWS_TASK_NAME = 'BatteryGuardAI'

#: مهلة أوامر systemd. أوامرها محلية وسريعة، والتعليق يعني مشكلة لا بطئاً.
COMMAND_TIMEOUT = 12

METHOD_SYSTEMD = 'systemd_user'
METHOD_DESKTOP = 'desktop_autostart'
METHOD_TASK = 'windows_task'
METHOD_NONE = 'none'


def _run(command: List[str], timeout: int = COMMAND_TIMEOUT) -> Tuple[int, str, str]:
    """تشغيل أمر بمهلة، وإرجاع نتيجته كاملة بلا رفع استثناء"""
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=timeout)
        return (completed.returncode, (completed.stdout or '').strip(),
                (completed.stderr or '').strip())
    except FileNotFoundError:
        return 127, '', f'الأمر غير موجود: {command[0]}'
    except subprocess.TimeoutExpired:
        return 124, '', f'انتهت مهلة الأمر: {" ".join(command[:3])}'
    except OSError as e:
        return 1, '', str(e)


# ═══════════════════════════════════════════════════════════
# مسار التشغيل
# ═══════════════════════════════════════════════════════════

@dataclass
class LaunchTarget:
    """كيف يُشغَّل التطبيق على هذا الجهاز بالتحديد"""
    executable: str
    arguments: List[str] = field(default_factory=list)
    working_dir: str = ''
    frozen: bool = False

    @property
    def exec_line(self) -> str:
        """سطر `ExecStart` مع اقتباس سليم للمسارات ذات الفراغات"""
        parts = [_quote(self.executable)] + [_quote(a) for a in self.arguments]
        return ' '.join(parts)

    @property
    def command(self) -> List[str]:
        return [self.executable] + list(self.arguments)


def _quote(value: str) -> str:
    """
    اقتباس قيمة لسطر أوامر systemd أو `.desktop`.

    مسار هذا المشروع نفسه يحتوي فراغات وحروفاً عربية، وترك الاقتباس يعني
    خدمة تفشل عند أول تشغيل برسالة مضلّلة عن ملف غير موجود.
    """
    text = str(value)
    if not text:
        return '""'
    if any(ch in text for ch in ' \t"\\\'$%'):
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return text


def detect_launch_target(background: bool = True) -> LaunchTarget:
    """
    كيف نشغّل التطبيق: ملف مبني بـ PyInstaller أم مفسّر بايثون وسكربت.

    يُستخدم `sys.executable` لا `python3` المجرّد حتى تعمل الخدمة داخل بيئة
    افتراضية: الخدمة لا ترث `PATH` الخاص بصدفة المستخدم.
    """
    arguments = ['--background'] if background else []
    if getattr(sys, 'frozen', False):
        executable = str(Path(sys.executable).resolve())
        return LaunchTarget(executable=executable, arguments=arguments,
                            working_dir=str(Path(executable).parent), frozen=True)

    project = Path(__file__).resolve().parent
    return LaunchTarget(
        executable=str(Path(sys.executable).resolve()),
        arguments=[str(project / 'main.py')] + arguments,
        working_dir=str(project), frozen=False)


# ═══════════════════════════════════════════════════════════
# الحالة
# ═══════════════════════════════════════════════════════════

@dataclass
class ServiceStatus:
    """حالة التشغيل الدائم كما هي فعلاً، لا كما نتمنّاها"""
    method: str = METHOD_NONE
    installed: bool = False
    enabled: bool = False
    running: bool = False
    linger: bool = False
    unit_path: str = ''
    detail: str = ''
    systemd_available: bool = False
    desktop_entry: bool = False
    conflicts: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            'method': self.method, 'installed': self.installed,
            'enabled': self.enabled, 'running': self.running,
            'linger': self.linger, 'unit_path': self.unit_path,
            'detail': self.detail, 'systemd_available': self.systemd_available,
            'desktop_entry': self.desktop_entry,
            'conflicts': list(self.conflicts),
        }


def systemd_user_available() -> bool:
    """
    هل يوجد مدير systemd للمستخدم يستقبل الأوامر؟

    وجود `systemctl` لا يكفي: داخل حاوية أو جلسة بلا مدير مستخدم يفشل الأمر
    برسالة عن ناقل الرسائل، والتثبيت وقتها يكتب وحدة لا تعمل.
    """
    if not IS_LINUX or not shutil.which('systemctl'):
        return False
    code, out, _ = _run(['systemctl', '--user', 'is-system-running'], timeout=8)
    # `degraded` يعني وحدة أخرى فاشلة، والمدير نفسه يعمل ويستقبل الأوامر
    return code == 0 or out in ('running', 'degraded', 'starting')


def _user_unit_dir() -> Path:
    base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    return Path(base) / 'systemd' / 'user'


def _autostart_dir() -> Path:
    base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    return Path(base) / 'autostart'


def _linger_enabled() -> bool:
    """هل مدير المستخدم باقٍ بعد الخروج (فيعمل قبل تسجيل الدخول)"""
    if not IS_LINUX or not shutil.which('loginctl'):
        return False
    user = os.environ.get('USER') or os.environ.get('LOGNAME') or ''
    if not user:
        return False
    code, out, _ = _run(['loginctl', 'show-user', user, '--property=Linger'])
    return code == 0 and out.strip().endswith('=yes')


def status() -> ServiceStatus:
    """الحالة الحقيقية المقروءة من النظام، لا من ملف إعدادات"""
    if IS_WINDOWS:
        return _windows_status()
    if not IS_LINUX:
        return ServiceStatus(detail='نظام غير مدعوم')

    result = ServiceStatus(systemd_available=systemd_user_available())
    unit = _user_unit_dir() / SERVICE_NAME
    desktop = _autostart_dir() / DESKTOP_NAME
    result.desktop_entry = desktop.exists()

    if unit.exists():
        result.method = METHOD_SYSTEMD
        result.installed = True
        result.unit_path = str(unit)
        if result.systemd_available:
            code, out, _ = _run(['systemctl', '--user', 'is-enabled', SERVICE_NAME])
            result.enabled = (out == 'enabled')
            code, out, _ = _run(['systemctl', '--user', 'is-active', SERVICE_NAME])
            result.running = (out == 'active')
            result.detail = out or 'unknown'
        else:
            result.detail = 'الوحدة موجودة لكن مدير المستخدم لا يستجيب'
        # وجود الطريقتين معاً يعني محاولتين لتشغيل نفس التطبيق
        if result.desktop_entry:
            result.conflicts.append(str(desktop))
    elif result.desktop_entry:
        result.method = METHOD_DESKTOP
        result.installed = True
        result.enabled = 'X-GNOME-Autostart-enabled=false' not in \
            desktop.read_text(encoding='utf-8', errors='replace')
        result.unit_path = str(desktop)
        result.detail = 'تشغيل تلقائي عبر ملف سطح المكتب'

    result.linger = _linger_enabled()
    return result


# ═══════════════════════════════════════════════════════════
# بناء ملف الوحدة
# ═══════════════════════════════════════════════════════════

def build_unit(target: LaunchTarget) -> str:
    """
    وحدة systemd للمستخدم.

    قرارات مقصودة، كل واحدة تُصلح خطأ في النسخة السابقة:

    - `WantedBy=default.target` لا `graphical.target`: هدف المستخدم الافتراضي
      يُبلغ عند تسجيل الدخول، ومع `linger` يُبلغ عند الإقلاع. `graphical.target`
      هدف نظام لا معنى له في مدير المستخدم.
    - `After=graphical-session.target` ترتيب لا اشتراط: لو لم تصل البيئة إلى
      هذا الهدف تبقى الخدمة تعمل بلا أيقونة بدل ألّا تعمل أبداً.
    - لا `ProtectHome` ولا `ProtectSystem=strict`: التطبيق يكتب بيانات تعلّمه
      في `~/.config/batteryguard`، ومنعه من ذلك يعني خدمة تفشل عند أول حفظ.
    - `Restart=always` مع `RestartSec=10`: التطبيق مراقِب، وتوقّفه الصامت يعني
      بطارية بلا حماية. `StartLimitIntervalSec` يمنع حلقة إعادة تشغيل محمومة.
    - `TimeoutStopSec=15`: الإغلاق النظيف يُفرج عن العمليات المعلّقة ويحفظ
      التعلّم، وقطعه قبل ذلك يترك عمليات موقوفة.
    - لا `Environment=DISPLAY`: مدير المستخدم يملك هذه المتغيّرات أصلاً في
      الجلسات الرسومية الحديثة، وتثبيتها في الملف يكسر التشغيل على Wayland
      أو عند تغيّر رقم الشاشة.
    """
    working = target.working_dir or str(Path.home())
    # `WorkingDirectory` ليس سطر أوامر بل مسار واحد يمتد إلى آخر السطر، فلا
    # يُقتبس. اقتباسه يجعل systemd يعدّ علامتي التنصيص جزءاً من المسار فيرفضه
    # بأنه «ليس مطلقاً» — وهذا ما كان يحدث فعلاً على مسار فيه فراغات.
    return f"""[Unit]
Description=BatteryGuardAI - حارس البطارية الذكي
Documentation=https://github.com/ALSRKAL/BatteryGuardAi
# ترتيب لا اشتراط: نفضّل البدء بعد الجلسة الرسومية، ونعمل بدونها إن غابت
After=graphical-session.target
PartOf=graphical-session.target
# سقف إعادة المحاولة يمنع حلقة محمومة عند خطأ دائم. موضعه [Unit] لا [Service]:
# هذان المفتاحان من خصائص الوحدة، وكتابتهما في [Service] تجعل systemd يتجاهلهما
# صامتاً فيبقى التطبيق يُعاد تشغيله بلا حدّ إن كان خطؤه دائماً.
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
WorkingDirectory={working}
ExecStart={target.exec_line}
# التطبيق مراقِب: توقّفه الصامت يعني بطارية بلا حماية
Restart=always
RestartSec=10
# مهلة كافية للإفراج عن العمليات المعلّقة وحفظ التعلّم قبل القطع
TimeoutStopSec=15
KillMode=mixed
# التطبيق مساعد لا حِمل رئيسي: لا يزاحم عمل المستخدم على المعالج
Nice=5
# لا حماية مسارات هنا: التطبيق يكتب بيانات تعلّمه في مجلد إعدادات المستخدم
StandardOutput=journal
StandardError=journal
SyslogIdentifier=batteryguard

[Install]
WantedBy=default.target
"""


def build_desktop_entry(target: LaunchTarget) -> str:
    """
    ملف تشغيل تلقائي للجلسة، للحالات التي لا يوجد فيها مدير مستخدم systemd.

    `X-GNOME-Autostart-Delay` يمنح البيئة وقتاً لتشغيل مضيف الصينية قبل أن
    يطلبها التطبيق. بلا هذا التأخير تُهمل الأيقونة صامتةً على بعض البيئات.
    """
    icon = Path(target.working_dir or '.') / 'icon.png'
    return f"""[Desktop Entry]
Type=Application
Name=BatteryGuardAI
Comment=حارس البطارية الذكي
Exec={target.exec_line}
Icon={icon}
Terminal=false
Categories=Utility;System;
StartupNotify=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=8
"""


# ═══════════════════════════════════════════════════════════
# التثبيت والإزالة
# ═══════════════════════════════════════════════════════════

@dataclass
class InstallResult:
    """نتيجة التثبيت: ما نجح، وأين كُتب، وما بقي على المستخدم فعله"""
    success: bool
    method: str
    path: str = ''
    messages: List[str] = field(default_factory=list)
    follow_up: List[str] = field(default_factory=list)
    error: str = ''

    def as_dict(self) -> Dict[str, object]:
        return {
            'success': self.success, 'method': self.method, 'path': self.path,
            'messages': list(self.messages), 'follow_up': list(self.follow_up),
            'error': self.error,
        }


def install(prefer_systemd: bool = True,
            start_now: bool = True) -> InstallResult:
    """
    تثبيت التشغيل الدائم. يختار أفضل طريقة متوفّرة ويقول أيّها اختار.
    """
    if IS_WINDOWS:
        return _install_windows(start_now)
    if not IS_LINUX:
        return InstallResult(False, METHOD_NONE, error='نظام غير مدعوم')

    if prefer_systemd and systemd_user_available():
        return _install_systemd(start_now)
    return _install_desktop(
        note='مدير systemd للمستخدم غير متوفّر، فاستُخدم التشغيل التلقائي للجلسة'
        if prefer_systemd else '')


def verify_unit(unit_path: Path) -> List[str]:
    """
    مشاكل ملف الوحدة كما يراها systemd نفسه، أو قائمة فارغة إن كان سليماً.

    `systemd-analyze verify` هو الحكم الوحيد المعتبر: قواعد التحليل لديه
    تفاصيل لا تُحاكى (المسارات المطلقة، صلاحية المفاتيح، الاعتماديات).
    تُستثنى الملاحظات التي لا تمنع التشغيل حتى لا نُفشل تثبيتاً صالحاً.
    """
    if not shutil.which('systemd-analyze'):
        return []
    code, out, err = _run(['systemd-analyze', '--user', 'verify', str(unit_path)],
                          timeout=20)
    if code == 0 and not err:
        return []

    #: ملاحظات لا تمنع التشغيل (وحدات نظام غير مرئية لمدير المستخدم مثلاً)
    benign = ('command not found', 'Unit configuration file is marked',
              'not found.', 'is deprecated')
    problems: List[str] = []
    for line in (err or out).splitlines():
        text = line.strip()
        if not text or any(hint in text for hint in benign):
            continue
        problems.append(text)
    return problems


def _install_systemd(start_now: bool) -> InstallResult:
    """كتابة وحدة المستخدم وتفعيلها وتشغيلها"""
    target = detect_launch_target(background=True)
    unit_dir = _user_unit_dir()
    unit_path = unit_dir / SERVICE_NAME
    result = InstallResult(True, METHOD_SYSTEMD, str(unit_path))

    try:
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(build_unit(target), encoding='utf-8')
        result.messages.append(f'كُتبت الوحدة: {unit_path}')
    except OSError as e:
        return InstallResult(False, METHOD_SYSTEMD, str(unit_path),
                             error=f'تعذّرت كتابة ملف الوحدة: {e}')

    # فحص الملف قبل إعلان أي نجاح: خطأ إعداد واحد (مسار بفراغ، مفتاح مكتوب
    # خطأ) يجعل systemd يرفض الوحدة، والإعلان عن «تثبيت ناجح» وقتها كذب
    # يكتشفه المستخدم بعد إعادة تشغيل الجهاز وقد فقد الحماية طوال الوقت.
    problems = verify_unit(unit_path)
    if problems:
        result.success = False
        result.error = 'رفض systemd ملف الوحدة: ' + problems[0]
        result.follow_up.extend(problems[1:4])
        return result
    result.messages.append('تحقّق systemd من صحة ملف الوحدة')

    code, _, err = _run(['systemctl', '--user', 'daemon-reload'])
    if code != 0:
        result.success = False
        result.error = f'فشل daemon-reload: {err}'
        return result
    result.messages.append('أُعيد تحميل مدير المستخدم')

    code, _, err = _run(['systemctl', '--user', 'enable', SERVICE_NAME])
    if code != 0:
        result.success = False
        result.error = f'فشل التفعيل: {err}'
        return result
    result.messages.append('فُعّلت الخدمة لتبدأ مع الجلسة')

    # التشغيل التلقائي عبر ملف سطح المكتب يصير تكراراً بعد تثبيت الخدمة:
    # نسختان تتنافسان على نفس القفل، وواحدة تفشل برسالة مربكة.
    desktop = _autostart_dir() / DESKTOP_NAME
    if desktop.exists():
        try:
            desktop.unlink()
            result.messages.append(f'أُزيل التشغيل التلقائي المتكرر: {desktop}')
        except OSError as e:
            result.follow_up.append(f'أزل يدوياً {desktop} ({e})')

    if start_now:
        code, _, err = _run(['systemctl', '--user', 'restart', SERVICE_NAME])
        if code == 0:
            result.messages.append('بدأت الخدمة الآن')
        else:
            result.follow_up.append(f'شغّلها يدوياً: systemctl --user start '
                                    f'{SERVICE_NAME} ({err})')

    if not _linger_enabled():
        user = os.environ.get('USER') or '$USER'
        result.follow_up.append(
            f'لتعمل قبل تسجيل الدخول وبعد الخروج: '
            f'sudo loginctl enable-linger {user}')
    return result


def _install_desktop(note: str = '') -> InstallResult:
    """كتابة ملف التشغيل التلقائي للجلسة"""
    target = detect_launch_target(background=True)
    directory = _autostart_dir()
    path = directory / DESKTOP_NAME
    result = InstallResult(True, METHOD_DESKTOP, str(path))
    if note:
        result.messages.append(note)

    try:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(build_desktop_entry(target), encoding='utf-8')
        os.chmod(path, 0o755)
        result.messages.append(f'كُتب ملف التشغيل التلقائي: {path}')
    except OSError as e:
        return InstallResult(False, METHOD_DESKTOP, str(path),
                             error=f'تعذّرت الكتابة: {e}')

    result.follow_up.append('يبدأ التطبيق عند تسجيل الدخول القادم. '
                            'هذه الطريقة لا تُعيد تشغيله إن توقّف.')
    return result


def uninstall() -> InstallResult:
    """
    إزالة كل صور التشغيل الدائم، وإيقاف الخدمة إن كانت تعمل.

    تُزال الطريقتان معاً بلا شرط: بقاء إحداهما بعد «إزالة» يعني تطبيقاً يعود
    بعد الإقلاع بعد أن أُخبر المستخدم أنه أُزيل.
    """
    if IS_WINDOWS:
        return _uninstall_windows()
    if not IS_LINUX:
        return InstallResult(False, METHOD_NONE, error='نظام غير مدعوم')

    result = InstallResult(True, METHOD_NONE)
    unit_path = _user_unit_dir() / SERVICE_NAME

    if systemd_user_available():
        for arguments, label in ((['stop', SERVICE_NAME], 'إيقاف'),
                                 (['disable', SERVICE_NAME], 'إلغاء تفعيل')):
            code, _, err = _run(['systemctl', '--user'] + arguments)
            if code == 0:
                result.messages.append(f'{label} الخدمة')
            elif 'not loaded' not in err and 'not found' not in err.lower():
                logger.debug(f"{label} الخدمة: {err}")

    if unit_path.exists():
        try:
            unit_path.unlink()
            result.messages.append(f'حُذفت الوحدة: {unit_path}')
        except OSError as e:
            result.success = False
            result.error = f'تعذّر حذف {unit_path}: {e}'

    if systemd_user_available():
        _run(['systemctl', '--user', 'daemon-reload'])
        _run(['systemctl', '--user', 'reset-failed', SERVICE_NAME])

    desktop = _autostart_dir() / DESKTOP_NAME
    if desktop.exists():
        try:
            desktop.unlink()
            result.messages.append(f'حُذف ملف التشغيل التلقائي: {desktop}')
        except OSError as e:
            result.success = False
            result.error = f'تعذّر حذف {desktop}: {e}'

    if not result.messages:
        result.messages.append('لم يكن هناك تشغيل دائم مثبّت')
    return result


def control(action: str) -> Tuple[bool, str]:
    """تشغيل/إيقاف/إعادة تشغيل الخدمة. يعيد (نجح، رسالة صادقة)."""
    if action not in ('start', 'stop', 'restart'):
        return False, f'إجراء غير معروف: {action}'
    if not IS_LINUX:
        return False, 'مدعوم على لينكس فقط'
    if not systemd_user_available():
        return False, 'مدير systemd للمستخدم غير متوفّر'
    if not (_user_unit_dir() / SERVICE_NAME).exists():
        return False, 'الخدمة غير مثبّتة'
    code, out, err = _run(['systemctl', '--user', action, SERVICE_NAME])
    if code == 0:
        return True, f'تم {action}'
    return False, err or out or f'فشل {action}'


def logs(lines: int = 60) -> str:
    """آخر سطور سجل الخدمة من journal"""
    if not IS_LINUX or not shutil.which('journalctl'):
        return 'journalctl غير متوفّر'
    code, out, err = _run(['journalctl', '--user', '-u', SERVICE_NAME,
                           '-n', str(max(1, min(1000, lines))),
                           '--no-pager'], timeout=20)
    return out if code == 0 else (err or 'لا سجل')


# ═══════════════════════════════════════════════════════════
# ويندوز
# ═══════════════════════════════════════════════════════════

def _windows_status() -> ServiceStatus:
    """حالة مهمة Task Scheduler"""
    result = ServiceStatus(method=METHOD_TASK)
    if not shutil.which('schtasks'):
        result.detail = 'schtasks غير متوفّر'
        return result
    code, out, _ = _run(['schtasks', '/Query', '/TN', WINDOWS_TASK_NAME,
                         '/FO', 'LIST'])
    result.installed = result.enabled = (code == 0)
    if code == 0:
        result.unit_path = WINDOWS_TASK_NAME
        result.running = 'Running' in out
        result.detail = 'مهمة مجدولة عند تسجيل الدخول'
    else:
        result.detail = 'المهمة غير موجودة'
    return result


def _install_windows(start_now: bool) -> InstallResult:
    """
    مهمة تبدأ عند تسجيل الدخول.

    `/RL LIMITED` عن قصد: التطبيق لا يحتاج صلاحيات مرتفعة لعمله اليومي، ومهمة
    مرتفعة الصلاحيات تُظهر تحذيرات وتوسّع أثر أي خطأ بلا مقابل.
    """
    target = detect_launch_target(background=True)
    result = InstallResult(True, METHOD_TASK, WINDOWS_TASK_NAME)
    if not shutil.which('schtasks'):
        return InstallResult(False, METHOD_TASK, error='schtasks غير متوفّر')

    _run(['schtasks', '/Delete', '/TN', WINDOWS_TASK_NAME, '/F'])
    code, _, err = _run([
        'schtasks', '/Create', '/TN', WINDOWS_TASK_NAME,
        '/TR', target.exec_line, '/SC', 'ONLOGON', '/RL', 'LIMITED', '/F'])
    if code != 0:
        return InstallResult(False, METHOD_TASK, WINDOWS_TASK_NAME,
                             error=err or 'فشل إنشاء المهمة')
    result.messages.append('أُنشئت مهمة تبدأ عند تسجيل الدخول')

    if start_now:
        code, _, err = _run(['schtasks', '/Run', '/TN', WINDOWS_TASK_NAME])
        if code == 0:
            result.messages.append('بدأت المهمة الآن')
        else:
            result.follow_up.append(f'شغّلها يدوياً من Task Scheduler ({err})')
    return result


def _uninstall_windows() -> InstallResult:
    result = InstallResult(True, METHOD_TASK, WINDOWS_TASK_NAME)
    code, _, err = _run(['schtasks', '/Delete', '/TN', WINDOWS_TASK_NAME, '/F'])
    result.messages.append('حُذفت المهمة' if code == 0
                           else f'لم توجد مهمة لحذفها ({err})')
    return result


# ═══════════════════════════════════════════════════════════
# واجهة سطر الأوامر
# ═══════════════════════════════════════════════════════════

def _print_status() -> None:
    state = status()
    print('حالة التشغيل الدائم')
    print('─' * 58)
    labels = {
        METHOD_SYSTEMD: 'خدمة systemd للمستخدم',
        METHOD_DESKTOP: 'تشغيل تلقائي للجلسة',
        METHOD_TASK: 'مهمة مجدولة (ويندوز)',
        METHOD_NONE: 'غير مثبّت',
    }
    print(f"  الطريقة       : {labels.get(state.method, state.method)}")
    print(f"  مثبّت         : {'نعم' if state.installed else 'لا'}")
    print(f"  يبدأ تلقائياً : {'نعم' if state.enabled else 'لا'}")
    print(f"  يعمل الآن     : {'نعم' if state.running else 'لا'}")
    print(f"  يعمل قبل الدخول: {'نعم' if state.linger else 'لا (بلا linger)'}")
    if state.unit_path:
        print(f"  الملف         : {state.unit_path}")
    if state.detail:
        print(f"  التفصيل       : {state.detail}")
    if state.conflicts:
        print("  تحذير: توجد طريقتان تشغيل معاً، وهذا يشغّل نسختين:")
        for item in state.conflicts:
            print(f"    - {item}")


def _print_result(result: InstallResult) -> None:
    print('نجح' if result.success else 'فشل')
    print('─' * 58)
    for message in result.messages:
        print(f'  • {message}')
    if result.error:
        print(f'  خطأ: {result.error}')
    if result.follow_up:
        print('\n  ما بقي عليك:')
        for item in result.follow_up:
            print(f'    - {item}')


def main(argv: Optional[List[str]] = None) -> int:
    """`python service_installer.py [status|install|uninstall|start|stop|restart|logs]`"""
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    arguments = list(argv if argv is not None else sys.argv[1:])
    command = arguments[0] if arguments else 'status'

    if command in ('status', '--status'):
        _print_status()
        return 0
    if command in ('install', '--install'):
        result = install(prefer_systemd='--desktop' not in arguments)
        _print_result(result)
        print()
        _print_status()
        return 0 if result.success else 1
    if command in ('uninstall', '--uninstall', 'remove'):
        result = uninstall()
        _print_result(result)
        return 0 if result.success else 1
    if command in ('start', 'stop', 'restart'):
        ok, message = control(command)
        print(('نجح: ' if ok else 'فشل: ') + message)
        return 0 if ok else 1
    if command in ('logs', '--logs'):
        print(logs())
        return 0

    print(__doc__)
    print('الأوامر: status | install [--desktop] | uninstall | '
          'start | stop | restart | logs')
    return 2


if __name__ == '__main__':
    sys.exit(main())
