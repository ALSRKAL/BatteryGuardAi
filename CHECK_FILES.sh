#!/bin/bash
# BatteryGuard Pro - التحقق من الملفات

echo "======================================"
echo "✅ BatteryGuard Pro - فحص الملفات"
echo "======================================"
echo ""

# عداد الملفات
total=0
found=0

# الملفات الرئيسية
echo "📦 الملفات الرئيسية:"
files=(
    "requirements.txt"
    "build.sh"
    "build.bat"
    "batteryguard.spec"
)

for file in "${files[@]}"; do
    total=$((total + 1))
    if [ -f "$file" ]; then
        echo "  ✅ $file"
        found=$((found + 1))
    else
        echo "  ❌ $file - مفقود!"
    fi
done

echo ""
echo "📚 ملفات التوثيق:"
docs=(
    "README.md"
    "INSTALLATION_GUIDE.md"
    "BUILD_README.md"
    "PROJECT_COMPLETE.md"
    "QUICK_REFERENCE.md"
    "الملخص_النهائي.md"
)

for file in "${docs[@]}"; do
    total=$((total + 1))
    if [ -f "$file" ]; then
        echo "  ✅ $file"
        found=$((found + 1))
    else
        echo "  ❌ $file - مفقود!"
    fi
done

echo ""
echo "🎵 ملفات الأصوات:"
sound_count=$(ls sounds/*.mp3 2>/dev/null | wc -l)
if [ $sound_count -eq 5 ]; then
    echo "  ✅ جميع الأصوات موجودة (5 ملفات)"
    found=$((found + 1))
else
    echo "  ⚠️  عدد الأصوات: $sound_count (متوقع: 5)"
fi
total=$((total + 1))

echo ""
echo "🎨 ملفات الأصول:"
if [ -f "assets/logo.png" ]; then
    echo "  ✅ assets/logo.png"
    found=$((found + 1))
else
    echo "  ❌ assets/logo.png - مفقود!"
fi
total=$((total + 1))

echo ""
echo "======================================"
echo "📊 النتيجة: $found/$total ملف موجود"
if [ $found -eq $total ]; then
    echo "✅ جميع الملفات موجودة!"
    echo "🚀 المشروع جاهز للاستخدام!"
else
    echo "⚠️  بعض الملفات مفقودة"
fi
echo "======================================"
