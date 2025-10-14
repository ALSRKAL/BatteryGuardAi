#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 🔧 مدير خدمة BatteryGuard Pro - Linux
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="batteryguard"
SYSTEMD_SERVICE="/etc/systemd/system/${SERVICE_NAME}.service"

show_menu() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔧 مدير خدمة BatteryGuard Pro"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "1. تثبيت الخدمة (systemd)"
    echo "2. بدء الخدمة"
    echo "3. إيقاف الخدمة"
    echo "4. إعادة تشغيل الخدمة"
    echo "5. حالة الخدمة"
    echo "6. عرض السجل"
    echo "7. تفعيل التشغيل التلقائي"
    echo "8. تعطيل التشغيل التلقائي"
    echo "9. إلغاء تثبيت الخدمة"
    echo "10. خروج"
    echo ""
}

install_service() {
    echo "📦 تثبيت خدمة systemd..."
    echo ""
    
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  يتطلب صلاحيات sudo"
        return 1
    fi
    
    # الحصول على المستخدم الحقيقي
    REAL_USER="${SUDO_USER:-$USER}"
    REAL_HOME=$(eval echo ~$REAL_USER)
    USER_ID=$(id -u $REAL_USER)
    
    # إنشاء ملف الخدمة
    cat > "$SYSTEMD_SERVICE" << EOF
[Unit]
Description=BatteryGuard Pro - Smart Battery Management System
Documentation=https://github.com/your-repo/batteryguard-pro
After=network.target graphical.target
Wants=graphical.target

[Service]
Type=simple
User=$REAL_USER
Group=$REAL_USER
WorkingDirectory=$SCRIPT_DIR
Environment="DISPLAY=:0"
Environment="XAUTHORITY=$REAL_HOME/.Xauthority"
Environment="XDG_RUNTIME_DIR=/run/user/$USER_ID"
Environment="DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$USER_ID/bus"
ExecStart=$(which python3) $SCRIPT_DIR/main.py --background
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$SCRIPT_DIR

[Install]
WantedBy=graphical.target
EOF
    
    # إعادة تحميل systemd
    systemctl daemon-reload
    
    echo "✅ تم تثبيت الخدمة بنجاح"
    echo ""
    echo "💡 استخدم الخيار 7 لتفعيل التشغيل التلقائي"
}

start_service() {
    echo "▶️  بدء الخدمة..."
    sudo systemctl start $SERVICE_NAME
    echo "✅ تم بدء الخدمة"
}

stop_service() {
    echo "⏸️  إيقاف الخدمة..."
    sudo systemctl stop $SERVICE_NAME
    echo "✅ تم إيقاف الخدمة"
}

restart_service() {
    echo "🔄 إعادة تشغيل الخدمة..."
    sudo systemctl restart $SERVICE_NAME
    echo "✅ تم إعادة تشغيل الخدمة"
}

status_service() {
    echo "📊 حالة الخدمة:"
    echo ""
    sudo systemctl status $SERVICE_NAME --no-pager
}

show_logs() {
    echo "📋 سجل الخدمة (اضغط Ctrl+C للخروج):"
    echo ""
    sudo journalctl -u $SERVICE_NAME -f
}

enable_service() {
    echo "✅ تفعيل التشغيل التلقائي..."
    sudo systemctl enable $SERVICE_NAME
    echo "✅ تم تفعيل التشغيل التلقائي"
    echo "💡 سيتم تشغيل الخدمة تلقائياً عند الإقلاع"
}

disable_service() {
    echo "❌ تعطيل التشغيل التلقائي..."
    sudo systemctl disable $SERVICE_NAME
    echo "✅ تم تعطيل التشغيل التلقائي"
}

uninstall_service() {
    echo "🗑️  إلغاء تثبيت الخدمة..."
    echo ""
    
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  يتطلب صلاحيات sudo"
        return 1
    fi
    
    # إيقاف وتعطيل الخدمة
    systemctl stop $SERVICE_NAME 2>/dev/null
    systemctl disable $SERVICE_NAME 2>/dev/null
    
    # حذف ملف الخدمة
    if [ -f "$SYSTEMD_SERVICE" ]; then
        rm "$SYSTEMD_SERVICE"
        echo "✅ تم حذف ملف الخدمة"
    fi
    
    # إعادة تحميل systemd
    systemctl daemon-reload
    
    echo "✅ تم إلغاء التثبيت بنجاح"
}

# البرنامج الرئيسي
while true; do
    show_menu
    read -p "اختيارك (1-10): " choice
    echo ""
    
    case $choice in
        1) install_service ;;
        2) start_service ;;
        3) stop_service ;;
        4) restart_service ;;
        5) status_service ;;
        6) show_logs ;;
        7) enable_service ;;
        8) disable_service ;;
        9) uninstall_service ;;
        10) echo "👋 إلى اللقاء!"; exit 0 ;;
        *) echo "❌ اختيار غير صحيح!" ;;
    esac
    
    echo ""
    read -p "اضغط Enter للمتابعة..."
    clear
done
