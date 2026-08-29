# 🔨 تعليمات البناء والتشغيل - BatteryGuardAI

## 📋 المتطلبات الأساسية

### Windows
- Python 3.8 أو أحدث
- pip (مدير حزم Python)
- 500 MB مساحة حرة

### Linux
- Python 3.8 أو أحدث
- pip3
- 500 MB مساحة حرة

---

## 🚀 البناء السريع

### Windows
```cmd
build.bat
```

### Linux
```bash
chmod +x build.sh
./build.sh
```

---

## 📦 البناء اليدوي

### 1. تثبيت المتطلبات
```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 2. البناء
```bash
pyinstaller --clean batteryguard.spec
```

### 3. الملف المبني
- **Windows**: `dist/BatteryGuardPro.exe`
- **Linux**: `dist/BatteryGuardPro`

---

## ✅ التحقق من البناء

### اختبار التشغيل
```bash
# Windows
dist\BatteryGuardPro.exe

# Linux
./dist/BatteryGuardPro
```

### اختبار وضع الخلفية
```bash
# Windows
dist\BatteryGuardPro.exe --background

# Linux
./dist/BatteryGuardPro --background
```

---

## 🔧 حل المشاكل الشائعة

### المشكلة: الأصوات لا تعمل
**الحل:**
- تأكد من وجود مجلد `sounds/` مع ملفات MP3
- تحقق من أن ملف `.spec` يتضمن الأصوات في `datas`

### المشكلة: الأيقونات لا تظهر
**الحل:**
- تأكد من وجود مجلد `assets/` مع الأيقونات
- تحقق من أن ملف `.spec` يتضمن الأصول في `datas`

### المشكلة: البرنامج لا يعمل في الخلفية
**الحل:**
- استخدم `--background` عند التشغيل
- تحقق من إعدادات التشغيل التلقائي

### المشكلة: لا يحفظ الإعدادات
**الحل:**
- الإعدادات تُحفظ في:
  - **Windows**: `%APPDATA%\BatteryGuardPro\`
  - **Linux**: `~/.config/batteryguard/`

---

## 📁 هيكل الملفات المبنية

```
dist/
├── BatteryGuardPro(.exe)    # الملف التنفيذي
├── _internal/               # الملفات الداخلية (PyInstaller)
│   ├── sounds/             # ملفات الأصوات
│   ├── assets/             # الأيقونات والصور
│   └── ...                 # مكتبات Python
```

---

## 🔄 التشغيل التلقائي

### تفعيل التشغيل التلقائي
1. شغّل البرنامج
2. اذهب إلى الإعدادات
3. فعّل "التشغيل التلقائي عند بدء النظام"

### يدوياً (Windows)
```cmd
schtasks /Create /TN "BatteryGuardPro" /TR "C:\path\to\BatteryGuardPro.exe --background" /SC ONLOGON /RL HIGHEST /F
```

### يدوياً (Linux)
```bash
# إنشاء ملف autostart
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/batteryguard.desktop << EOF
[Desktop Entry]
Type=Application
Name=BatteryGuardAI
Exec=/path/to/BatteryGuardPro --background
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
```

---

## 🎯 نصائح للأداء الأفضل

### Windows
- شغّل كمسؤول للحصول على جميع الميزات
- تأكد من تثبيت Visual C++ Redistributable

### Linux
- ثبّت `tlp` للتحكم الأفضل في الشحن:
  ```bash
  sudo apt install tlp tlp-rdw
  ```
- ثبّت `mpg123` لتشغيل الأصوات:
  ```bash
  sudo apt install mpg123
  ```

---

## 📊 اختبار الميزات

### اختبار الأصوات
```bash
python test_sounds.py
```

### اختبار الإشعارات
```bash
python test_smart_notifications.py
```

### اختبار التحسين
```bash
python test_smart_optimizer.py
```

---

## 🐛 تصحيح الأخطاء

### تفعيل وضع التصحيح
```bash
# Windows
dist\BatteryGuardPro.exe --debug

# Linux
./dist/BatteryGuardPro --debug
```

### ملفات السجل
- **Windows**: `%APPDATA%\BatteryGuardPro\batteryguard.log`
- **Linux**: `~/.config/batteryguard/batteryguard.log`

---

## 📞 الدعم

إذا واجهت مشاكل:
1. تحقق من ملف السجل
2. تأكد من تثبيت جميع المتطلبات
3. جرب إعادة البناء بعد حذف `build/` و `dist/`

---

## ✨ الميزات المتاحة بعد البناء

✅ مراقبة البطارية في الوقت الفعلي
✅ إشعارات ذكية مع أصوات
✅ التحكم في حدود الشحن
✅ التحسين التلقائي
✅ التشغيل في الخلفية
✅ التشغيل التلقائي عند بدء النظام
✅ أيقونة صينية النظام
✅ حفظ الإعدادات

---

**تم التحديث:** 2024
**الإصدار:** 2.0
