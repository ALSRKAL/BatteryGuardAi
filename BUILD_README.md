# 🏗️ دليل البناء السريع - BatteryGuard Pro

## 📦 الملفات المهمة

- `requirements.txt` - قائمة المكتبات المطلوبة
- `INSTALLATION_GUIDE.md` - دليل التثبيت الشامل
- `batteryguard.spec` - ملف PyInstaller
- `build.sh` - سكريبت البناء لـ Linux
- `build.bat` - سكريبت البناء لـ Windows

---

## 🚀 البناء السريع

### Linux

```bash
# منح صلاحيات التنفيذ
chmod +x build.sh

# تشغيل سكريبت البناء
./build.sh

# الملف القابل للتنفيذ سيكون في:
# dist/BatteryGuardPro
```

### Windows

```powershell
# تشغيل سكريبت البناء
build.bat

# الملف القابل للتنفيذ سيكون في:
# dist\BatteryGuardPro.exe
```

---

## 📋 خطوات البناء اليدوي

### 1. تثبيت المتطلبات

```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 2. بناء البرنامج

#### Linux:
```bash
pyinstaller batteryguard.spec
```

#### Windows:
```powershell
pyinstaller batteryguard.spec
```

### 3. اختبار البرنامج

```bash
# Linux
./dist/BatteryGuardPro

# Windows
dist\BatteryGuardPro.exe
```

---

## 🎯 البناء المخصص

### تغيير الأيقونة

عدّل في `batteryguard.spec`:
```python
icon='path/to/your/icon.png'
```

### إضافة ملفات إضافية

عدّل في `batteryguard.spec`:
```python
datas=[
    ('assets', 'assets'),
    ('sounds', 'sounds'),
    ('your_folder', 'your_folder'),  # أضف هنا
],
```

### تقليل حجم الملف

```bash
# استخدم UPX للضغط
pyinstaller --upx-dir=/path/to/upx batteryguard.spec
```

---

## 📦 إنشاء حزم التوزيع

### Linux (.deb)

```bash
# راجع INSTALLATION_GUIDE.md للتفاصيل
# القسم: "إنشاء حزمة Linux (.deb)"
```

### Windows (.msi)

```bash
# راجع INSTALLATION_GUIDE.md للتفاصيل
# القسم: "إنشاء مثبت Windows (.msi)"
```

---

## 🔍 استكشاف أخطاء البناء

### خطأ: ModuleNotFoundError

```bash
# تأكد من تثبيت جميع المتطلبات
pip install -r requirements.txt
```

### خطأ: PyInstaller not found

```bash
pip install pyinstaller
```

### خطأ: Icon file not found

```bash
# تأكد من وجود ملف الأيقونة
ls assets/logo.png  # Linux
dir assets\logo.png  # Windows
```

### الملف كبير جداً

```bash
# استخدم --onefile بدون UPX
pyinstaller --onefile --windowed main.py

# أو استبعد مكتبات غير مستخدمة
# عدّل excludes في batteryguard.spec
```

---

## 📊 حجم الملفات المتوقع

| النظام | الحجم التقريبي |
|--------|----------------|
| Linux (onefile) | ~80-120 MB |
| Windows (onefile) | ~100-150 MB |
| Linux (.deb) | ~50-80 MB |
| Windows (.msi) | ~80-120 MB |

---

## ✅ قائمة التحقق

قبل التوزيع، تأكد من:

- [ ] البرنامج يعمل بدون أخطاء
- [ ] جميع الأصوات تعمل
- [ ] الأيقونة تظهر بشكل صحيح
- [ ] الإشعارات تعمل
- [ ] التحسين التلقائي يعمل
- [ ] Single Instance يعمل
- [ ] الملفات المطلوبة موجودة (assets, sounds)
- [ ] تم اختبار البرنامج على نظام نظيف

---

## 🆘 الدعم

للمزيد من المساعدة:
- راجع `INSTALLATION_GUIDE.md`
- راجع `README.md`
- تحقق من السجلات في `battery_events.log`

---

**BatteryGuard Pro v2.0** 🔋⚡
