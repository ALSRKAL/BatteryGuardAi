#!/bin/bash
# BatteryGuard Pro - Build Script for Linux

echo "======================================"
echo "🚀 BatteryGuard Pro - Build Script"
echo "======================================"

# التحقق من Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 غير مثبت!"
    exit 1
fi

echo "✅ Python 3 موجود"

# التحقق من pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 غير مثبت!"
    exit 1
fi

echo "✅ pip3 موجود"

# إنشاء بيئة افتراضية
echo ""
echo "📦 إنشاء بيئة افتراضية..."
python3 -m venv build_env

# تفعيل البيئة
source build_env/bin/activate

# ترقية pip
echo ""
echo "⬆️  ترقية pip..."
pip install --upgrade pip

# تثبيت المتطلبات
echo ""
echo "📥 تثبيت المتطلبات..."
pip install -r requirements.txt

# تثبيت PyInstaller
echo ""
echo "📥 تثبيت PyInstaller..."
pip install pyinstaller

# تنظيف البناء السابق
echo ""
echo "🧹 تنظيف البناء السابق..."
rm -rf build dist

# بناء البرنامج
echo ""
echo "🔨 بناء البرنامج..."
pyinstaller --clean batteryguard.spec

# التحقق من النجاح
if [ -f "dist/BatteryGuardPro" ]; then
    echo ""
    echo "======================================"
    echo "✅ تم البناء بنجاح!"
    echo "======================================"
    echo ""
    echo "📁 الملف القابل للتنفيذ: dist/BatteryGuardPro"
    echo ""
    
    # منح صلاحيات التنفيذ
    chmod +x dist/BatteryGuardPro
    
    # اختبار التشغيل
    echo "🧪 اختبار التشغيل..."
    if ./dist/BatteryGuardPro --help 2>/dev/null; then
        echo "✅ الاختبار نجح"
    else
        echo "⚠️ تحذير: قد تكون هناك مشكلة في التشغيل"
    fi
    
    # إنشاء ملف .desktop
    echo ""
    echo "📝 إنشاء ملف .desktop..."
    cat > dist/batteryguard-pro.desktop << EOF
[Desktop Entry]
Name=BatteryGuard Pro
Comment=نظام إدارة البطارية الذكي
Exec=$(pwd)/dist/BatteryGuardPro
Icon=$(pwd)/assets/logo.png
Terminal=false
Type=Application
Categories=System;Utility;
StartupNotify=true
EOF
    
    echo "✅ تم إنشاء ملف .desktop"
    echo ""
    echo "📋 لإضافة اختصار للقائمة:"
    echo "   cp dist/batteryguard-pro.desktop ~/.local/share/applications/"
    echo ""
    echo "🚀 للتشغيل:"
    echo "   ./dist/BatteryGuardPro"
    echo ""
    echo "🔄 للتشغيل في الخلفية:"
    echo "   ./dist/BatteryGuardPro --background"
    
else
    echo ""
    echo "======================================"
    echo "❌ فشل البناء!"
    echo "======================================"
    echo ""
    echo "📝 تحقق من ملف السجل للمزيد من التفاصيل"
    exit 1
fi

# تنظيف
echo ""
read -p "🗑️  هل تريد حذف ملفات البناء المؤقتة؟ (y/n): " cleanup
if [ "$cleanup" = "y" ]; then
    rm -rf build
    rm -rf build_env
    echo "✅ تم التنظيف"
fi

echo ""
echo "======================================"
echo "🎉 اكتمل البناء بنجاح!"
echo "======================================"
