#!/bin/bash
# اختبار نظام Single Instance

echo "======================================"
echo "🧪 اختبار نظام Single Instance"
echo "======================================"

echo ""
echo "1️⃣ اختبار الوحدة الأساسية..."
python3 single_instance.py

echo ""
echo "======================================"
echo "2️⃣ اختبار التطبيق الفعلي..."
echo "======================================"

echo ""
echo "▶️  تشغيل النسخة الأولى في الخلفية..."
python3 main.py --background &
FIRST_PID=$!
echo "   PID: $FIRST_PID"

sleep 3

echo ""
echo "▶️  محاولة تشغيل نسخة ثانية..."
python3 main.py

echo ""
echo "🛑 إيقاف النسخة الأولى..."
kill $FIRST_PID 2>/dev/null

sleep 1

echo ""
echo "======================================"
echo "✅ اكتمل الاختبار"
echo "======================================"
