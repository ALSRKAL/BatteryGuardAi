# BatteryGuardAI

[![Tests](https://github.com/ALSRKAL/BatteryGuardAi/actions/workflows/tests.yml/badge.svg)](https://github.com/ALSRKAL/BatteryGuardAi/actions)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue)](#)
[![Python](https://img.shields.io/badge/python-3.10%2B-green)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

**العربية | [English](#english)**

---

## العربية

تطبيق مكتبي يقيس الإجهاد الفعلي على بطارية اللابتوب، ويتدخّل لتقليله حيث يسمح
العتاد، ويقول صراحةً ما لا يستطيع فعله على جهازك بدل ادّعاء نجاح غير متحقَّق منه.

### ثلاث طبقات قدرة، والتطبيق يعلن طبقته

توفّر ضبط حدود الشحن يعتمد على المصنّع والطراز وسوّاقة النواة، لا على التطبيق.
لذلك يفحص BatteryGuardAI العتاد عند التشغيل ويضع نفسه في واحدة من ثلاث طبقات:

| الطبقة | المعنى | ما يفعله التطبيق |
|---|---|---|
| تحكم فعلي | يوجد مسار كتابة لعتبات الشحن في `/sys/class/power_supply/*/charge_control_*` | يكتب الحدّ، ثم **يقرأه من العتاد** ولا يعلن النجاح إلا إذا طابق المطلوب |
| إعداد في البيوس | الحدّ موجود في BIOS/UEFI ولا يملكه نظام التشغيل (مثل HP Battery Health Manager) | يرشدك إلى مساره خطوة بخطوة، ولا يزعم أنه ضبطه |
| مراقبة وتنبيه | لا مسار على الإطلاق | يقيس ويتنبّأ وينبّه، ويقول ذلك صراحةً |

عند فشل التطبيق يعرض السبب المحدد: لا مسار، أو رُفضت الصلاحية، أو العتاد أعاد
قيمة مختلفة عمّا كُتب، أو لم يستجب داخل المهلة. مع كل سبب خطوة معالجة قابلة
للتنفيذ خاصة بمصنّع جهازك.

### القياس والتحليل

- **قراءة مباشرة من العتاد**: النسبة، حالة الشاحن، الجهد، التيار، القدرة
  (على لينكس)، حرارة البطارية إن وفّرها العتاد، السعة الكاملة والتصميمية،
  وعدد الدورات. كل قراءة محدودة بمهلة حتى لا يتجمّد خيط المراقبة على عتاد
  لا يستجيب.
- **كشف البطارية غير المبلّغة**: بطارية تعرض صفر شحن وصفر جهد ليست بطارية
  فارغة بل بطارية لا تُبلّغ. في هذه الحالة تُوقف تنبيهات مستوى الشحن، ولا
  تُعرض صحة مطمئنة كاذبة، ويُعرض تشخيص بما قُرئ فعلاً.
- **تقدير التآكل**: تآكل تقويمي بدلالة الحرارة ومستوى الشحن، وتآكل دوري
  بدلالة أعماق التفريغ المرصودة، ومنه الفقد السنوي المتوقّع والزمن المتبقي
  حتى حدّ نهاية العمر الافتراضي (80% من السعة التصميمية).
- **مؤشر إجهاد لحظي** مع بيان مضاعف مستوى الشحن ومضاعف الحرارة.
- **تعلّم من الاستخدام**: معدلات الشحن والتفريغ بمرشح EWMA، تنبؤ الوقت
  المتبقي بانحدار خطي، ساعات الاستخدام المكثف، وزمن البقاء فوق السقف الصحي.
  بلا numpy وبلا scikit-learn.
- **كل توصية بسندها**: قياس من جهازك، أو مرجع منشور مع رابطه.

### الأساس المرجعي للأرقام

الثوابت مأخوذة من مراجع منشورة ومُسمّاة في `battery_science.py`:

- Battery University, BU-808: جدول الدورات بدلالة عمق التفريغ، وجدول السعة
  المستردة بعد سنة بدلالة الحرارة ومستوى الشحن.
  https://batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries
- Battery University, BU-502: أثر التشغيل فوق الحرارة المعتدلة على عمر الدورات.
  https://www.batteryuniversity.com/article/bu-502-discharging-at-high-and-low-temperatures
- USABC / Sandia: 80% من السعة الابتدائية كحدّ نهاية العمر الافتراضي.
  https://www.sandia.gov/files/ess/uploads/2021/ESSRF/Preger_Yuliya.pdf
- TLP, Battery Care Vendor Specifics: العتاد المدعوم وسوّاقات النواة اللازمة.
  https://linrunner.de/tlp/settings/bc-vendors.html
- HP, Battery Health Manager: إعداد BIOS الذي يحدّ الشحن الأقصى.
  https://support.hp.com/emea_africa-en/document/ish_4449597-3519507-16

هذه الجداول تصف اتجاهاً عاماً لخلايا ليثيوم تجارية، والبطاريات لا تتصرف كلها
بنفس الشكل. لذلك كل ناتج مبني على قيمة غير مقروءة من العتاد يُعلَم بأنه مفترض.

### الواجهة

خمسة مجالات مستقلة: الحالة، التحكم، التحليل، السجل، الإعدادات. عربية بالكامل
باتجاه من اليمين إلى اليسار، مع طبقة ترجمة في `locales/` وأيقونات مرسومة
بمسارات (بلا إيموجي)، ونظام تصميم واحد في `theme.py` لا قيم لونية متفرقة.

### المتطلبات

| | |
|---|---|
| نظام التشغيل | Windows 10/11 أو Linux (X11/Wayland مع خدمة إشعارات) |
| بايثون | 3.10 أو أحدث |
| الحزم | `PyQt6`، `psutil` (واختيارياً `pygame`، `plyer`) |

### التثبيت والتشغيل

```bash
git clone https://github.com/ALSRKAL/BatteryGuardAi.git
cd BatteryGuardAi
pip install -r requirements.txt
python main.py              # تشغيل عادي
python main.py --background  # تشغيل في الخلفية بأيقونة الصينية فقط
```

### بناء نسخة تنفيذية

راجع [docs/BUILDING.md](docs/BUILDING.md). يستخدم PyInstaller عبر `build.sh`
على لينكس أو `build.bat` على ويندوز، ويضمّن `locales/` و`sounds/` و`assets/`.

### هيكل المشروع

```
main.py                  نقطة الدخول: اللغة، النسخة الواحدة، وضع الخلفية
main_window.py           لوحة القياس والربط بين الطبقات
ui_components.py         المجالات الخمسة
panel_widgets.py         عناصر اللوحة: الحقل، الأثر، القدرات، فك نافذة الشحن
theme.py                 نظام التصميم: الألوان والمقاسات والخطوط والأنماط
icons.py                 الأيقونات المرسومة بمسارات
i18n.py + locales/       طبقة الترجمة ومفاتيحها
battery_science.py       محرك التآكل والإجهاد والنصائح المهيكلة (وحدة نقية)
hardware_capability.py   فحص قدرات العتاد وكتالوج المعالجة والقراءة بمهلة
battery_monitor.py       القراءة عبر المنصات والتحقق بعد الكتابة
battery_ai.py            التعلم من الاستخدام والتنبؤ وملف الاستخدام
monitor_thread.py        خيط المراقبة بفاصل تكيفي وإيقاف تعاوني
charge_controller.py     واجهة التحكم
charge_control_advanced.py  التنفيذ الفعلي لحدود الشحن
notification_manager.py  الإشعارات والتذكيرات والأصوات
battery_optimizer.py     تحسينات النظام اليدوية
auto_optimizer.py        المحسن التلقائي في الخلفية
storage.py               تخزين JSON ذري آمن بين الخيوط
tests/                   حزمة pytest (85 اختباراً)
```

### الاختبارات

```bash
pip install pytest pytest-timeout
pytest
```

تعمل الحزمة كاملة بلا شاشة عبر `QT_QPA_PLATFORM=offscreen`، وتغطي محرك
التآكل والنصائح، وكشف البطارية غير المبلّغة، وملف الاستخدام وأعماق التفريغ،
ومنطق الإشعارات والتهدئة، والتخزين الذري والاسترجاع من ملف تالف، واكتشاف
النسخة الواحدة، ودورة حياة النافذة كاملة.

### الخصوصية

كل البيانات محلية على جهازك: لا حساب، ولا خدمة سحابية، ولا إرسال قياسات إلى
أي جهة. ملفات البيانات والسجل في مجلد إعدادات المستخدم.

## English

A desktop application that measures the real stress on a laptop battery,
intervenes to reduce it where the hardware allows, and states plainly what it
cannot do on your machine instead of claiming unverified success.

### Three capability tiers, and the app declares its own

Whether charge limits can be set depends on the vendor, the model, and the
kernel driver, not on this application. BatteryGuardAI probes the hardware at
startup and places itself in one of three tiers:

| Tier | Meaning | What the app does |
|---|---|---|
| Real hardware control | A writable threshold path exists under `/sys/class/power_supply/*/charge_control_*` | Writes the limit, then **reads it back** and only reports success on a match |
| Firmware setting | The limit lives in BIOS/UEFI and the OS does not own it (for example HP Battery Health Manager) | Guides you there step by step and never claims it applied it |
| Monitoring and alerts | No path at all | Measures, forecasts, and warns, and says so plainly |

On failure the app names the specific cause: no path, permission denied, the
hardware returned a different value than written, or no response within the
timeout. Each cause comes with an actionable remediation step for your vendor.

### Measurement and analysis

- **Direct hardware reads**: level, charger state, voltage, current, power
  (Linux), battery temperature when exposed, full and design capacity, and
  cycle count. Every read is time-bounded so the monitor thread cannot hang on
  unresponsive hardware.
- **Non-reporting battery detection**: a battery reporting zero charge and zero
  voltage is not an empty battery, it is a battery that is not reporting.
  Charge-level alerts stop, no reassuring false health figure is shown, and a
  diagnostic view lists exactly what was read.
- **Wear estimation**: calendar wear as a function of temperature and state of
  charge, cyclic wear from observed discharge depths, and from those the
  projected annual loss and the time remaining to the conventional end-of-life
  mark (80% of design capacity).
- **Instant stress index** with the state-of-charge and temperature multipliers
  shown separately.
- **Learning from use**: charge and discharge rates with an EWMA filter,
  time-remaining prediction by linear regression, heavy-usage hours, and dwell
  time above the healthy ceiling. No numpy, no scikit-learn.
- **Every recommendation carries its evidence**: a measurement from your
  machine, or a published reference with its link.

### Reference basis for the numbers

Constants come from published references, all named in `battery_science.py`:

- Battery University, BU-808: cycles by depth of discharge, and recoverable
  capacity after one year by temperature and state of charge.
  https://batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries
- Battery University, BU-502: the effect of running above moderate temperature
  on cycle life.
  https://www.batteryuniversity.com/article/bu-502-discharging-at-high-and-low-temperatures
- USABC / Sandia: 80% of initial capacity as the end-of-life mark.
  https://www.sandia.gov/files/ess/uploads/2021/ESSRF/Preger_Yuliya.pdf
- TLP, Battery Care Vendor Specifics: supported hardware and required drivers.
  https://linrunner.de/tlp/settings/bc-vendors.html
- HP, Battery Health Manager: the BIOS setting that caps maximum charge.
  https://support.hp.com/emea_africa-en/document/ish_4449597-3519507-16

These tables describe a general trend for commercial lithium cells, and not all
batteries behave the same. Any result built on a value that was not read from
the hardware is labelled as assumed.

### Interface

Five separate areas: Status, Control, Analysis, Record, Settings. Fully Arabic
and right-to-left, with a translation layer in `locales/`, path-drawn icons and
no emoji, and one design system in `theme.py` rather than scattered colour
values.

### Requirements

| | |
|---|---|
| OS | Windows 10/11 or Linux (X11/Wayland with a notification service) |
| Python | 3.10 or newer |
| Packages | `PyQt6`, `psutil` (optionally `pygame`, `plyer`) |

### Install and run

```bash
git clone https://github.com/ALSRKAL/BatteryGuardAi.git
cd BatteryGuardAi
pip install -r requirements.txt
python main.py               # normal start
python main.py --background  # tray-only background start
```

### Building a binary

See [docs/BUILDING.md](docs/BUILDING.md). PyInstaller via `build.sh` on Linux
or `build.bat` on Windows; the spec bundles `locales/`, `sounds/`, `assets/`.

### Tests

```bash
pip install pytest pytest-timeout
pytest
```

The suite runs fully headless with `QT_QPA_PLATFORM=offscreen` and covers the
wear and advice engine, non-reporting battery detection, the usage profile and
discharge depths, notification cooldown logic, atomic storage and corrupt-file
recovery, single-instance detection, and a full window lifecycle.

### Privacy

All data stays on your machine: no account, no cloud service, no telemetry.
Data and log files live in the user configuration directory.

## License

MIT, see [LICENSE](LICENSE).
