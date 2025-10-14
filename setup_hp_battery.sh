#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 🔧 إعداد التحكم في البطارية لأجهزة HP
# ═══════════════════════════════════════════════════════════════

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 إعداد التحكم في البطارية - HP ZBook"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# التحقق من الصلاحيات
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  يرجى تشغيل السكريبت بصلاحيات sudo:"
    echo "   sudo bash setup_hp_battery.sh"
    exit 1
fi

echo "✅ صلاحيات sudo متوفرة"
echo ""

# 1. التحقق من TLP
echo "📦 التحقق من TLP..."
if ! command -v tlp &> /dev/null; then
    echo "📥 تثبيت TLP..."
    apt update
    apt install -y tlp tlp-rdw
else
    echo "✅ TLP مثبت بالفعل"
fi

# 2. إعداد TLP لأجهزة HP
echo ""
echo "⚙️  إعداد TLP لأجهزة HP..."

TLP_CONF="/etc/tlp.conf"
TLP_CONF_BAK="/etc/tlp.conf.backup-$(date +%Y%m%d-%H%M%S)"

# نسخ احتياطي
if [ -f "$TLP_CONF" ]; then
    cp "$TLP_CONF" "$TLP_CONF_BAK"
    echo "✅ تم إنشاء نسخة احتياطية: $TLP_CONF_BAK"
fi

# إنشاء إعدادات TLP محسّنة لـ HP
cat > "$TLP_CONF" << 'EOF'
# ═══════════════════════════════════════════════════════════════
# TLP Configuration - Optimized for HP ZBook
# ═══════════════════════════════════════════════════════════════

# Battery Charge Thresholds (BAT0)
START_CHARGE_THRESH_BAT0=40
STOP_CHARGE_THRESH_BAT0=80

# Battery Charge Thresholds (BAT1) - if exists
START_CHARGE_THRESH_BAT1=40
STOP_CHARGE_THRESH_BAT1=80

# Battery Feature Drivers
NATACPI_ENABLE=1
TPACPI_ENABLE=1
TPSMAPI_ENABLE=1

# Radio Device Wizard
DEVICES_TO_DISABLE_ON_STARTUP=""
DEVICES_TO_ENABLE_ON_STARTUP="wifi bluetooth"

# Radio Device Switching on Battery/AC
DEVICES_TO_DISABLE_ON_BAT="bluetooth"
DEVICES_TO_DISABLE_ON_BAT_NOT_IN_USE="bluetooth"
DEVICES_TO_ENABLE_ON_AC="bluetooth wifi"

# CPU Scaling Governor
CPU_SCALING_GOVERNOR_ON_AC=performance
CPU_SCALING_GOVERNOR_ON_BAT=powersave

# CPU Energy Performance Policy
CPU_ENERGY_PERF_POLICY_ON_AC=performance
CPU_ENERGY_PERF_POLICY_ON_BAT=power

# CPU Boost
CPU_BOOST_ON_AC=1
CPU_BOOST_ON_BAT=0

# Platform Profile
PLATFORM_PROFILE_ON_AC=performance
PLATFORM_PROFILE_ON_BAT=low-power

# Disk devices
DISK_DEVICES="nvme0n1 sda"
DISK_APM_LEVEL_ON_AC="254 254"
DISK_APM_LEVEL_ON_BAT="128 128"

# SATA Link Power Management
SATA_LINKPWR_ON_AC="max_performance"
SATA_LINKPWR_ON_BAT="min_power"

# PCI Express Active State Power Management
PCIE_ASPM_ON_AC=performance
PCIE_ASPM_ON_BAT=powersave

# Runtime Power Management
RUNTIME_PM_ON_AC=on
RUNTIME_PM_ON_BAT=auto

# USB Autosuspend
USB_AUTOSUSPEND=1
USB_BLACKLIST_BTUSB=0
USB_BLACKLIST_PHONE=0
USB_BLACKLIST_PRINTER=1
USB_BLACKLIST_WWAN=0

# Audio Power Saving
SOUND_POWER_SAVE_ON_AC=0
SOUND_POWER_SAVE_ON_BAT=1

# WiFi Power Saving
WIFI_PWR_ON_AC=off
WIFI_PWR_ON_BAT=on

# Restore Radio Device State on Startup
RESTORE_DEVICE_STATE_ON_STARTUP=0

# Battery Care (HP specific)
# These settings help preserve battery health
CHARGE_THRESH_BAT0="40 80"
CHARGE_THRESH_BAT1="40 80"
EOF

echo "✅ تم إنشاء ملف إعدادات TLP محسّن"

# 3. إعادة تشغيل TLP
echo ""
echo "🔄 إعادة تشغيل TLP..."
systemctl restart tlp
systemctl enable tlp

# 4. تطبيق الإعدادات
echo ""
echo "⚙️  تطبيق إعدادات البطارية..."
tlp start
tlp setcharge 40 80 BAT0

# 5. التحقق من الحالة
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 حالة البطارية"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tlp-stat -b | head -30

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ تم الإعداد بنجاح!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 ملاحظات:"
echo "   • تم تعيين حد الشحن: 40%-80%"
echo "   • سيتم تطبيق الإعدادات تلقائياً عند كل إقلاع"
echo "   • يمكنك تغيير الحدود من التطبيق"
echo ""
echo "🔧 للتحقق من الحالة في أي وقت:"
echo "   sudo tlp-stat -b"
echo ""
echo "🔄 لتطبيق حدود جديدة يدوياً:"
echo "   sudo tlp setcharge <MIN> <MAX> BAT0"
echo "   مثال: sudo tlp setcharge 40 80 BAT0"
echo ""
