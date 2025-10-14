#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 🚀 BatteryGuard Pro - ملف التشغيل السريع (Linux)
# ═══════════════════════════════════════════════════════════════

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔋 BatteryGuard Pro - نظام إدارة البطارية الذكي"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# التحقق من Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 غير مثبت!"
    echo "📦 قم بتثبيته أولاً: sudo apt install python3 python3-pip"
    exit 1
fi

echo "✅ تم العثور على Python: $(python3 --version)"
echo ""

# التحقق من pip
if ! command -v pip3 &> /dev/null; then
    echo "📦 تثبيت pip..."
    sudo apt install -y python3-pip
fi

# التحقق من venv
echo "🔍 التحقق من البيئة الافتراضية..."
if [ ! -d "venv" ]; then
    echo "📦 إنشاء البيئة الافتراضية..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "📦 تثبيت python3-venv..."
        sudo apt install -y python3-venv
        python3 -m venv venv
    fi
fi

# تفعيل البيئة الافتراضية
echo "🔄 تفعيل البيئة الافتراضية..."
source venv/bin/activate

# تثبيت المتطلبات
echo "📦 تثبيت المتطلبات..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

if [ $? -ne 0 ]; then
    echo "⚠️ فشل تثبيت بعض المكتبات، محاولة التثبيت اليدوي..."
    pip install PyQt6 psutil -q
fi

# تثبيت أدوات التحكم في الشحن (اختياري)
echo ""
echo "🔧 التحقق من أدوات التحكم في الشحن..."

# TLP
if ! command -v tlp &> /dev/null; then
    echo "📦 TLP غير مثبت (اختياري للتحكم المتقدم)"
    read -p "هل تريد تثبيت TLP؟ (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo apt install -y tlp tlp-rdw
        sudo tlp start
        echo "✅ تم تثبيت TLP"
    fi
else
    echo "✅ TLP مثبت بالفعل"
fi

# acpi-call (لأجهزة ThinkPad وغيرها)
if [ ! -f "/proc/acpi/call" ]; then
    echo "📦 acpi-call غير مثبت (اختياري لبعض الأجهزة)"
    read -p "هل تريد تثبيت acpi-call؟ (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo apt install -y acpi-call-dkms
        sudo modprobe acpi_call
        echo "✅ تم تثبيت acpi-call"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 تشغيل BatteryGuard Pro..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# تشغيل التطبيق
python3 main.py

# إلغاء تفعيل البيئة الافتراضية عند الإغلاق
deactivate
