# BatteryGuardAI

[![Tests](https://github.com/ALSRKAL/BatteryGuardAi/actions/workflows/tests.yml/badge.svg)](https://github.com/ALSRKAL/BatteryGuardAi/actions)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue)](#)
[![Python](https://img.shields.io/badge/python-3.10%2B-green)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

**العربية | [English](#english)**

---

## العربية

BatteryGuardAI تطبيق مكتبي مفتوح المصدر يحمي بطارية حاسوبك المحمول ويرفع عمرها الافتراضي عبر مراقبة ذكية، تنبؤات زمنية، تحكم فعلي في حدود الشحن (حيث يدعمه العتاد)، وإشعارات تفاعلية قابلة للتخصيص.

### المزايا الرئيسية

- **مراقبة لحظية**: نسبة الشحن، الاستهلاك الفعلي بالواط (على لينكس)، حالة الشاحن.
- **ذكاء اصطناعي خفيف**: يتعلّم أنماط استخدامك (ساعات الذروة، عادة الشحن، الشحن الليلي) ويتنبأ بالوقت المتبقي بانحدار خطي على آخر القياسات مع مرشّح EWMA — بدون مكتبات تعلم آلي ثقيلة.
- **تحكم فعلي في الشحن**: ضبط حد شحن أقصى/أدنى (مثال 40–80%) عبر:
  - **لينكس**: `charge_control_end_threshold` / `charge_start_threshold` (ASUS، ThinkPad، ...) وTLP.
  - **ويندوز**: أدوات المصنّعين حيث تتوفر (Lenovo Conservation Mode، Dell cctk، HP، ASUS).
- **إشعارات ذكية**: حدود قابلة للتخصيص، تذكيرات متكررة مع (إيقاف/غفوة/كتم)، ساعات هدوء ليلية، أصوات مخصصة MP3 لكل نوع.
- **محسّن النظام**: تنظيف الذاكرة والملفات المؤقتة وخفض السطوع عند الحاجة، مع وضع تلقائي أو مجدول.
- **لوحة إحصائيات**: صحة البطارية الحقيقية من العتاد، دورات الشحن، أوقات الشحن/التفريغ التراكمية.

### المتطلبات

| | |
|---|---|
| نظام التشغيل | Windows 10/11 أو Linux (X11/Wayland مع بيئة تدعم الإشعارات) |
| بايثون | 3.10 أو أحدث |
| الحزم | `PyQt6`، `psutil` (+ اختيارياً `pygame`، `plyer`) |

### التثبيت والتشغيل

```bash
git clone https://github.com/ALSRKAL/BatteryGuardAi.git
cd BatteryGuardAi
pip install -r requirements.txt
python main.py            # تشغيل عادي
python main.py --background   # تشغيل في الخلفية (أيقونة الصينية فقط)
```

### بناء نسخة تنفيذية

راجع [docs/BUILDING.md](docs/BUILDING.md) — يستخدم PyInstaller عبر `build.sh` (لينكس) أو `build.bat` (ويندوز).

### هيكل المشروع

```
├── main.py                     # نقطة الدخول
├── main_window.py              # النافذة الرئيسية والتنسيق بين الوحدات
├── battery_ai.py               # محرك التحليل والتنبؤ (EWMA + انحدار خطي)
├── monitor_thread.py           # خيط المراقبة (فاصل تكيفي + إيقاف تعاوني)
├── battery_monitor.py          # قراءة حالة البطارية وصحتها عبر المنصات
├── notification_manager.py     # الإشعارات والتذكيرات والأصوات
├── charge_controller.py        # واجهة التحكم في الشحن
├── charge_control_advanced.py  # التنفيذ الفعلي لحدود الشحن
├── battery_optimizer.py        # تحسينات النظام اليدوية/التلقائية
├── auto_optimizer.py           # المحسّن التلقائي في الخلفية
├── storage.py                  # تخزين JSON ذري آمن بين الخيوط
├── ui_components.py            # تبويبات الواجهة الأربعة
└── tests/                      # حزمة اختبارات pytest (75 اختباراً)
```

### الاختبارات

```bash
pip install pytest pytest-timeout
pytest                # كل الاختبارات (تعمل بلا شاشة عبر offscreen)
```

تغطي الاختبارات محرك AI (المعدلات، التنبؤ، دورات الشحن)، منطق الإشعارات (التهدئة، الغفوة، الكتم)، التخزين الذري والاسترجاع من ملف تالف، اكتشاف النسخة الواحدة، ودورة حياة كاملة للنافذة.

### ملاحظة عن دعم العتاد

ضبط حدود الشحن يعتمد على دعم الشركة المصنعة. إن لم يتوفر مسار تحكم في جهازك سيعمل التطبيق بوضع الإشعارات فقط ويخبرك بذلك بدلاً من ادعاء نجاح زائف.

## English

BatteryGuardAI is an open-source desktop app that protects your laptop battery and extends its lifespan through intelligent monitoring, time-to-empty forecasting, real charge-threshold control (where hardware supports it), and customizable interactive notifications.

### Key Features

- **Live monitoring**: charge level, actual power draw in watts (Linux), charger state.
- **Lightweight AI**: learns your usage patterns (peak hours, charging habits, night usage) and predicts remaining time with linear regression over recent samples plus EWMA smoothing — no heavy ML dependencies.
- **Real charge control**: set a max/min charge window (e.g. 40–80%) via:
  - **Linux**: `charge_control_end_threshold` / `charge_start_threshold` (ASUS, ThinkPad, ...) and TLP.
  - **Windows**: vendor tools where available (Lenovo Conservation Mode, Dell cctk, HP, ASUS).
- **Smart notifications**: customizable thresholds, recurring reminders with Stop/Snooze/Mute, quiet hours, per-type custom MP3 sounds.
- **System optimizer**: memory/temp-file cleanup and brightness reduction when needed, manual or automatic.
- **Statistics dashboard**: real hardware battery health, cycle count, cumulative charge/discharge times.

### Requirements

| | |
|---|---|
| OS | Windows 10/11 or Linux (X11/Wayland with a notification daemon) |
| Python | 3.10+ |
| Packages | `PyQt6`, `psutil` (+ optional `pygame`, `plyer`) |

### Install & Run

```bash
git clone https://github.com/ALSRKAL/BatteryGuardAi.git
cd BatteryGuardAi
pip install -r requirements.txt
python main.py                 # normal start
python main.py --background    # tray-only background start
```

### Building a Binary

See [docs/BUILDING.md](docs/BUILDING.md) — PyInstaller via `build.sh` (Linux) or `build.bat` (Windows).

### Project Layout

```
├── main.py                     # Entry point
├── main_window.py              # Main window & module wiring
├── battery_ai.py               # Analysis/prediction engine (EWMA + linear regression)
├── monitor_thread.py           # Monitor loop (adaptive interval, cooperative stop)
├── battery_monitor.py          # Cross-platform battery status & health reader
├── notification_manager.py     # Notifications, reminders & sounds
├── charge_controller.py        # Charge-control facade
├── charge_control_advanced.py  # Actual threshold implementations
├── battery_optimizer.py        # Manual system optimizations
├── auto_optimizer.py           # Background automatic optimizer
├── storage.py                  # Thread-safe atomic JSON storage
├── ui_components.py            # The four UI tabs
└── tests/                      # pytest suite (75 tests)
```

### Running Tests

```bash
pip install pytest pytest-timeout
pytest    # runs fully headless (Qt offscreen)
```

Coverage includes the AI engine (rates, predictions, cycle counting), notification logic (cooldowns, snooze, mute), atomic storage & corrupt-file recovery, single-instance detection, and a full window lifecycle smoke test.

### Hardware Support Note

Charge-limit control depends on vendor support. If your device exposes no control path, the app falls back to notifications-only mode and tells you so instead of pretending success.

## License

MIT — see [LICENSE](LICENSE).
