#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# مدير التشغيل الدائم - BatteryGuardAI (لينكس)
#
# غلاف رفيع فوق `service_installer.py`. المنطق كله هناك، وهذا الملف اختصار
# للطرفية لمن يفضّل أمراً واحداً على قائمة تفاعلية.
#
# لا `sudo` في أي أمر: الخدمة خدمة **مستخدم** لا خدمة نظام. النسخة السابقة
# كانت تكتب وحدة في /etc تحتاج sudo وتفشل عند أول حفظ لبيانات التعلّم بسبب
# ProtectHome=read-only، وترسل متغيّرات بيئة لا تُوسَّع لأن systemd لا يشغّل صدفة.
#
# الاستخدام:
#   ./service_manager.sh                 قائمة تفاعلية
#   ./service_manager.sh install         تثبيت وتشغيل
#   ./service_manager.sh status          الحالة
#   ./service_manager.sh start|stop|restart
#   ./service_manager.sh logs [-f]       السجل (‎-f للمتابعة الحيّة)
#   ./service_manager.sh uninstall       إزالة كل صور التشغيل الدائم
#   ./service_manager.sh linger          تشغيل قبل تسجيل الدخول (يحتاج sudo)
# ═══════════════════════════════════════════════════════════════
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="batteryguard.service"
PY="${PYTHON:-python3}"
RULE="──────────────────────────────────────────────────────────"

cd "$SCRIPT_DIR" || exit 1

installer() { "$PY" service_installer.py "$@"; }

require_systemd() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl غير موجود على هذا النظام."
    return 1
  fi
  if ! systemctl --user is-system-running >/dev/null 2>&1; then
    echo "تحذير: مدير systemd للمستخدم لا يستجيب."
    echo "سيُستخدم التشغيل التلقائي للجلسة كبديل عند التثبيت."
  fi
  return 0
}

cmd_status()    { installer status; }
cmd_install()   { require_systemd; installer install; }
cmd_uninstall() { installer uninstall; }

cmd_start()   { installer start; }
cmd_stop()    { installer stop; }
cmd_restart() { installer restart; }

cmd_logs() {
  if [ "${1:-}" = "-f" ]; then
    echo "متابعة السجل الحيّة (Ctrl+C للخروج):"
    journalctl --user -u "$SERVICE" -f
  else
    installer logs
  fi
}

cmd_linger() {
  # linger يجعل مدير المستخدم باقياً بعد الخروج، فتعمل الخدمة قبل تسجيل
  # الدخول وبعده. هذا الأمر الوحيد الذي يحتاج صلاحيات، ولا يُنفَّذ بلا إذن.
  local user="${USER:-$(id -un)}"
  local state
  state="$(loginctl show-user "$user" --property=Linger 2>/dev/null || echo 'Linger=unknown')"
  echo "الحالة الحالية: $state"
  if [ "$state" = "Linger=yes" ]; then
    echo "مفعّل بالفعل: الخدمة تعمل قبل تسجيل الدخول وبعد الخروج."
    return 0
  fi
  echo
  echo "الأمر المطلوب (يحتاج صلاحيات المسؤول):"
  echo "    sudo loginctl enable-linger $user"
  echo
  read -r -p "تنفيذه الآن؟ [y/N] " answer
  case "$answer" in
    y | Y | yes)
      sudo loginctl enable-linger "$user" &&
        echo "تم. الحالة: $(loginctl show-user "$user" --property=Linger)"
      ;;
    *) echo "لم يُنفَّذ. يمكنك تشغيل الأمر أعلاه يدوياً لاحقاً." ;;
  esac
}

cmd_check() {
  # فحص سريع يجيب على السؤال الفعلي: هل يعمل الآن، ومستقلاً عن الطرفية؟
  echo "فحص التشغيل الدائم"
  echo "$RULE"
  local pid ppid
  pid="$(systemctl --user show "$SERVICE" -p MainPID --value 2>/dev/null || echo 0)"
  if [ -z "$pid" ] || [ "$pid" = "0" ]; then
    echo "  الخدمة لا تعمل الآن."
    echo "  شغّلها بـ: ./service_manager.sh install"
    return 1
  fi
  ppid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
  echo "  رقم العملية      : $pid"
  echo "  أبوها            : $ppid (مدير المستخدم، لا الطرفية)"
  echo "  المجموعة         : $(cut -d: -f3 </proc/"$pid"/cgroup 2>/dev/null | head -1)"
  echo "  الذاكرة          : $(awk '/VmRSS/{print $2" "$3}' /proc/"$pid"/status 2>/dev/null)"
  echo "  إعادات التشغيل   : $(systemctl --user show "$SERVICE" -p NRestarts --value 2>/dev/null)"
  echo "  زمن المعالج      : $(systemctl --user show "$SERVICE" -p CPUUsageNSec --value 2>/dev/null | awk '{printf "%.1f ثانية\n", $1/1e9}')"
  echo
  echo "  إغلاق هذه الطرفية لن يوقف الخدمة: أبوها مدير المستخدم لا الصدفة."
}

show_menu() {
  echo "$RULE"
  echo "  مدير التشغيل الدائم - BatteryGuardAI"
  echo "$RULE"
  echo
  echo "  1. تثبيت التشغيل الدائم (بلا sudo)"
  echo "  2. عرض الحالة"
  echo "  3. فحص سريع (هل يعمل ومستقل عن الطرفية؟)"
  echo "  4. بدء"
  echo "  5. إيقاف"
  echo "  6. إعادة تشغيل"
  echo "  7. عرض السجل"
  echo "  8. متابعة السجل الحيّة"
  echo "  9. التشغيل قبل تسجيل الدخول (linger)"
  echo " 10. إزالة التشغيل الدائم"
  echo " 11. خروج"
  echo
}

interactive() {
  while true; do
    show_menu
    read -r -p "  اختيارك (1-11): " choice
    echo
    case "$choice" in
      1) cmd_install ;;
      2) cmd_status ;;
      3) cmd_check ;;
      4) cmd_start ;;
      5) cmd_stop ;;
      6) cmd_restart ;;
      7) cmd_logs ;;
      8) cmd_logs -f ;;
      9) cmd_linger ;;
      10) cmd_uninstall ;;
      11)
        echo "إلى اللقاء"
        exit 0
        ;;
      *) echo "اختيار غير صحيح" ;;
    esac
    echo
    read -r -p "اضغط Enter للمتابعة..." _
    clear
  done
}

case "${1:-}" in
  '') interactive ;;
  install) cmd_install ;;
  uninstall | remove) cmd_uninstall ;;
  status) cmd_status ;;
  check) cmd_check ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_restart ;;
  logs) cmd_logs "${2:-}" ;;
  linger) cmd_linger ;;
  -h | --help | help)
    sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)
    echo "أمر غير معروف: $1"
    echo "الأوامر: install | uninstall | status | check | start | stop | restart | logs [-f] | linger"
    exit 2
    ;;
esac
