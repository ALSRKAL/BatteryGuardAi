# 📦 دليل التثبيت والتشغيل - BatteryGuard Pro

## 📋 المتطلبات الأساسية

### جميع الأنظمة:
- Python 3.8 أو أحدث
- pip (مدير حزم Python)

### Linux:
- مشغل أصوات MP3 (mpg123 موصى به)
- مكتبات GTK للإشعارات

### Windows:
- لا توجد متطلبات إضافية

---

## 🚀 التثبيت السريع

### 1️⃣ Linux (Ubuntu/Debian)

```bash
# تحديث النظام
sudo apt update

# تثبيت Python و pip
sudo apt install python3 python3-pip python3-venv

# تثبيت مكتبات النظام
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-notify-0.7

# تثبيت مشغل الأصوات
sudo apt install mpg123

# إنشاء بيئة افتراضية
python3 -m venv venv

# تفعيل البيئة
source venv/bin/activate

# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل البرنامج
python3 main.py
```

### 2️⃣ Linux (Fedora/RHEL)

```bash
# تثبيت Python و pip
sudo dnf install python3 python3-pip python3-virtualenv

# تثبيت مكتبات النظام
sudo dnf install python3-gobject gtk3 libnotify

# تثبيت مشغل الأصوات
sudo dnf install mpg123

# إنشاء بيئة افتراضية
python3 -m venv venv

# تفعيل البيئة
source venv/bin/activate

# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل البرنامج
python3 main.py
```

### 3️⃣ Linux (Arch)

```bash
# تثبيت Python و pip
sudo pacman -S python python-pip python-virtualenv

# تثبيت مكتبات النظام
sudo pacman -S python-gobject gtk3 libnotify

# تثبيت مشغل الأصوات
sudo pacman -S mpg123

# إنشاء بيئة افتراضية
python3 -m venv venv

# تفعيل البيئة
source venv/bin/activate

# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل البرنامج
python3 main.py
```

### 4️⃣ Windows

```powershell
# تأكد من تثبيت Python من python.org

# فتح PowerShell أو CMD في مجلد البرنامج

# إنشاء بيئة افتراضية
python -m venv venv

# تفعيل البيئة
venv\Scripts\activate

# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل البرنامج
python main.py
```

---

## 🔧 التثبيت المتقدم

### إنشاء بيئة افتراضية معزولة

#### Linux/macOS:
```bash
# إنشاء البيئة
python3 -m venv batteryguard_env

# تفعيل البيئة
source batteryguard_env/bin/activate

# ترقية pip
pip install --upgrade pip

# تثبيت المتطلبات
pip install -r requirements.txt

# للخروج من البيئة
deactivate
```

#### Windows:
```powershell
# إنشاء البيئة
python -m venv batteryguard_env

# تفعيل البيئة
batteryguard_env\Scripts\activate

# ترقية pip
python -m pip install --upgrade pip

# تثبيت المتطلبات
pip install -r requirements.txt

# للخروج من البيئة
deactivate
```

---

## 📦 تحويل إلى برنامج قابل للتنفيذ

### استخدام PyInstaller

#### 1. تثبيت PyInstaller

```bash
pip install pyinstaller
```

#### 2. إنشاء ملف spec مخصص

قم بإنشاء ملف `batteryguard.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('sounds', 'sounds'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'psutil',
        'sklearn',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BatteryGuardPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # False لإخفاء نافذة الكونسول
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.png',  # أيقونة البرنامج
)
```

#### 3. بناء البرنامج

##### Linux:
```bash
# بناء ملف واحد قابل للتنفيذ
pyinstaller batteryguard.spec

# أو بدون ملف spec
pyinstaller --onefile --windowed --name BatteryGuardPro \
    --add-data "assets:assets" \
    --add-data "sounds:sounds" \
    --icon assets/logo.png \
    main.py

# الملف القابل للتنفيذ سيكون في: dist/BatteryGuardPro
```

##### Windows:
```powershell
# بناء ملف واحد قابل للتنفيذ
pyinstaller batteryguard.spec

# أو بدون ملف spec
pyinstaller --onefile --windowed --name BatteryGuardPro `
    --add-data "assets;assets" `
    --add-data "sounds;sounds" `
    --icon assets/logo.png `
    main.py

# الملف القابل للتنفيذ سيكون في: dist\BatteryGuardPro.exe
```

#### 4. اختبار البرنامج

```bash
# Linux
./dist/BatteryGuardPro

# Windows
dist\BatteryGuardPro.exe
```

---

## 🐧 إنشاء حزمة Linux (.deb)

### 1. تثبيت الأدوات

```bash
sudo apt install dh-make devscripts
```

### 2. إنشاء هيكل الحزمة

```bash
# إنشاء مجلد الحزمة
mkdir -p batteryguard-pro_2.0/DEBIAN
mkdir -p batteryguard-pro_2.0/usr/bin
mkdir -p batteryguard-pro_2.0/usr/share/applications
mkdir -p batteryguard-pro_2.0/usr/share/icons/hicolor/256x256/apps
mkdir -p batteryguard-pro_2.0/opt/batteryguard-pro

# نسخ الملفات
cp -r * batteryguard-pro_2.0/opt/batteryguard-pro/
cp assets/logo.png batteryguard-pro_2.0/usr/share/icons/hicolor/256x256/apps/batteryguard-pro.png
```

### 3. إنشاء ملف control

```bash
cat > batteryguard-pro_2.0/DEBIAN/control << EOF
Package: batteryguard-pro
Version: 2.0
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-pyqt6, python3-psutil, mpg123
Maintainer: Your Name <your.email@example.com>
Description: نظام إدارة البطارية الذكي
 BatteryGuard Pro - نظام متقدم لإدارة البطارية مع ذكاء اصطناعي
 يوفر مراقبة ذكية، تحسين تلقائي، وإشعارات متقدمة.
EOF
```

### 4. إنشاء ملف .desktop

```bash
cat > batteryguard-pro_2.0/usr/share/applications/batteryguard-pro.desktop << EOF
[Desktop Entry]
Name=BatteryGuard Pro
Comment=نظام إدارة البطارية الذكي
Exec=/opt/batteryguard-pro/main.py
Icon=batteryguard-pro
Terminal=false
Type=Application
Categories=System;Utility;
EOF
```

### 5. بناء الحزمة

```bash
dpkg-deb --build batteryguard-pro_2.0
```

### 6. تثبيت الحزمة

```bash
sudo dpkg -i batteryguard-pro_2.0.deb
```

---

## 🪟 إنشاء مثبت Windows (.msi)

### استخدام cx_Freeze

#### 1. تثبيت cx_Freeze

```powershell
pip install cx_Freeze
```

#### 2. إنشاء ملف setup.py

```python
from cx_Freeze import setup, Executable
import sys

# تحديد الملفات الإضافية
include_files = [
    ('assets', 'assets'),
    ('sounds', 'sounds'),
]

# تحديد الحزم المطلوبة
packages = [
    'PyQt6',
    'psutil',
    'sklearn',
    'numpy',
]

# خيارات البناء
build_exe_options = {
    'packages': packages,
    'include_files': include_files,
    'excludes': ['tkinter'],
}

# خيارات MSI
bdist_msi_options = {
    'upgrade_code': '{12345678-1234-1234-1234-123456789012}',
    'add_to_path': False,
    'initial_target_dir': r'[ProgramFilesFolder]\BatteryGuard Pro',
}

# تحديد الملف القابل للتنفيذ
base = None
if sys.platform == 'win32':
    base = 'Win32GUI'  # لإخفاء نافذة الكونسول

executables = [
    Executable(
        'main.py',
        base=base,
        target_name='BatteryGuardPro.exe',
        icon='assets/logo.png',
        shortcut_name='BatteryGuard Pro',
        shortcut_dir='DesktopFolder',
    )
]

setup(
    name='BatteryGuard Pro',
    version='2.0',
    description='نظام إدارة البطارية الذكي',
    options={
        'build_exe': build_exe_options,
        'bdist_msi': bdist_msi_options,
    },
    executables=executables,
)
```

#### 3. بناء المثبت

```powershell
# بناء ملف exe
python setup.py build

# بناء مثبت MSI
python setup.py bdist_msi
```

---

## 🔍 استكشاف الأخطاء

### مشكلة: ModuleNotFoundError

```bash
# تأكد من تثبيت جميع المتطلبات
pip install -r requirements.txt

# تحقق من البيئة الافتراضية
which python  # Linux
where python  # Windows
```

### مشكلة: لا تعمل الإشعارات على Linux

```bash
# تثبيت مكتبات الإشعارات
sudo apt install python3-gi gir1.2-notify-0.7

# أو استخدام plyer
pip install plyer
```

### مشكلة: لا تعمل الأصوات

```bash
# Linux - تثبيت mpg123
sudo apt install mpg123

# أو استخدام pygame
pip install pygame
```

### مشكلة: خطأ في الصلاحيات

```bash
# Linux - منح صلاحيات التنفيذ
chmod +x main.py

# تشغيل مع sudo للتحسينات المتقدمة
sudo python3 main.py
```

---

## 📝 ملاحظات مهمة

### الأداء:
- استخدم البيئة الافتراضية لعزل المكتبات
- PyInstaller ينتج ملفات كبيرة (~100MB) لكنها مستقلة
- cx_Freeze أصغر حجماً لكن قد يحتاج مكتبات إضافية

### الأمان:
- لا تشارك ملف .exe/.deb قبل فحصه
- استخدم توقيع رقمي للحزم
- اختبر على أنظمة نظيفة

### التوافق:
- PyQt6 يتطلب Python 3.8+
- بعض الميزات تحتاج صلاحيات إدارية
- الإشعارات تختلف بين الأنظمة

---

## 🆘 الدعم

### الموارد:
- **التوثيق**: راجع ملفات README و GUIDE
- **الاختبارات**: استخدم ملفات test_*.py
- **السجلات**: تحقق من battery_events.log

### المشاكل الشائعة:
1. **البرنامج لا يبدأ**: تحقق من Python و المتطلبات
2. **لا توجد إشعارات**: تحقق من مكتبات النظام
3. **لا توجد أصوات**: ثبت mpg123 أو pygame
4. **أخطاء الصلاحيات**: شغل مع sudo/admin

---

**BatteryGuard Pro v2.0** - نظام إدارة البطارية الذكي 🔋⚡
