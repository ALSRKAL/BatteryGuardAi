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

### من يستنزف بطاريتك: نسب القدرة إلى العمليات

سؤال لا تجيب عليه لوحات البطارية عادةً: **من** يستهلك بطاريتك الآن، بالواط.

1. تُقاس القدرة الكلية من العتاد (`power_now`، أو `voltage_now × current_now`).
2. تُقاس أحمال كل عملية من عدّادات النظام: زمن المعالج، بايتات القرص الفعلية
   من طبقة الكتل، وتبديلات السياق كوكيل عن الإيقاظات التي تمنع نوم المعالج.
3. **ينحدر نموذج خطّي غير سالب على قياسات جهازك أنت** ليتعلّم كم واط تكلّف كل
   وحدة حِمل. قبل توفّر 25 عيّنة تُستخدم قيم أولية معلنة وتُعرض الثقة منخفضة.
4. تُوزَّع القدرة المقيسة بنسبة التكلفة، وما لا يُنسب إلى عملية (الشاشة،
   الراديو) يُعرض باسمه بدل توزيعه قسراً.

التدريب يجري **أثناء التفريغ فقط**: على الشاحن يقيس `current_now` تيار الشحن
لا استهلاكك، والتغذية به تفسد المعامل. ومجموع ما يُنسب لا يتجاوز ما قِيس أبداً:
لا تضخيم لبلوغ رقم، لأن ذلك اختراع استهلاك لم يحدث.

الرقم المعروض ليس نسبة معالج بل **كم من سعة بطاريتك تخسر سنوياً**، مشتقاً من
واط مقيسة وساعات عملك المرصودة على البطارية وجدول تآكل الدورة من BU-808.

### السلوكيات التي تُتلف البطارية ولا تظهر في نسبة المعالج

| السلوك | لماذا يضرّ |
|---|---|
| منع الخمول | الأخطر: الشاشة والجهاز لا ينامان أصلاً |
| منع النوم | يبقي العتاد يقظاً |
| إيقاظ متكرر (>400/ث) | يمنع المعالج من حالات النوم العميقة |
| حِمل مستمر (>25% نواة لدقيقتين) | استنزاف ثابت لا قفزة عابرة |
| إرهاق القرص (>6 م.ب/ث) | القرص من أكبر مستهلكي الطاقة |

موانع النوم تُقرأ من `systemd-inhibit`، ويُميَّز المنع الحقيقي (`mode=block`
على هدف نوم أو خمول) من التأجيل الحميد الذي يستخدمه مدير الشبكة عادةً.

### كشف أعمق من العتبات الثابتة

- **شذوذ متين**: الوسيط والانحراف المطلق الوسيطي (MAD) بدل المتوسط، بخط أساس
  مستقل لكل ساعة. استنزاف 2٪/د الظهر عادي، وفي الثالثة فجراً يعني شيئاً يعمل
  بلا إذن. الطريقة القديمة (ضعف المتوسط) كانت القراءة الشاذة نفسها ترفع فيها
  المتوسط فتُسكِت الكشف بعدها.
- **نقاط التغيّر**: CUSUM ثنائي الاتجاه يرصد «صار جهازك يستنزف أسرع منذ كذا»
  بدل انتظار شكوى المستخدم. مُعايَر على معدّل تنبيه كاذب صفري في 100 ألف عيّنة.
- **الدورية الحقيقية**: ارتباط ذاتي عند 24 و168 ساعة يثبت النمط بدل افتراضه.
- **تآكل مقيس**: انحدار خطي على السعة الكاملة المقروءة من العتاد عبر الزمن،
  فيعطي معدل تآكل **هذه الخلية** لا اتجاهاً عاماً من جدول. لا يُعلَن قبل
  عشرة أيام من القراءات: انحدار على ساعات يعطي رقماً هائلاً بلا معنى.
- **الارتباط لا التصادف**: بيرسون بين واط كل عملية ومعدل الاستنزاف، فيُفرَّق
  بين عملية ترفع الاستنزاف فعلاً وأخرى حاضرة بالتزامن فقط.

### الحارس: إجراءات فعلية وقابلة للتراجع

| الإجراء | الآلية | قابل للتراجع؟ |
|---|---|---|
| تنبيه | إشعار فقط | لا ينطبق |
| خفض الأولوية | `ionice` إلى الصنف الخامل | **نعم** |
| خفض أولوية المعالج (اختياري) | `renice` | **لا** بلا صلاحيات |
| تعليق مؤقت | `SIGSTOP` | **نعم** بـ `SIGCONT` |
| إيقاف نهائي | `SIGTERM` ثم `SIGKILL` | **لا** — بطلبك الصريح فقط |

`renice` غير قابل للاستعادة لأن `RLIMIT_NICE` يساوي صفراً على معظم التوزيعات،
وهذا يُعلَن في النتيجة بدل ادّعاء تراجع لا يحدث.

**طوق السلامة**: لا يُلمس أبداً مدير الجلسة ولا خادم العرض ولا مدير النوافذ
ولا ناقل الرسائل ولا مدير الحزم، ولا خيوط النواة، ولا عمليات مستخدم آخر، ولا
التطبيق نفسه وأسلافه وذرّيته، ولا عملية أُعيد استخدام رقمها بين لحظة الاستدلال
ولحظة التنفيذ. كل تعليق يُفرَج عنه تلقائياً بعد خمس دقائق عبر خيط مراقبة
مستقل، ولا مسار تلقائي يصل إلى الإيقاف النهائي.

**الافتراضي لا يلمس شيئاً**: الحارس يقيس ويُنبّه، والتنفيذ التلقائي معطّل حتى
تسمح به. راجع [docs/OPERATIONS.md](docs/OPERATIONS.md).

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

### المحسّن: يخفض السحب، ويستعيد كل ما غيّره، ويعلن ما امتنع عنه

كل تغيير يجريه التطبيق على النظام خارج حدود الشحن يمرّ من `system_tuning.py`
وحده، بقواعد ملزمة:

| المبدأ | التطبيق |
|---|---|
| لا تغيير بلا طريق رجوع | كل قيمة تُغيَّر تُحفَظ قبلها في لقطة على القرص، فيبقى التراجع ممكناً بعد إعادة التشغيل |
| السطوع يُخفَض ولا يُرفَع | إن أنزلته أنت فلن يرفعه التطبيق، ولا ينزل تحت 30٪، واللقطة تُكتب بعد نجاح الكتابة وحده |
| اللوحة الداخلية فقط | eDP / LVDS / DSI. أي `backlight` خارجي (ddcci) ليس ملك التطبيق |
| الشاشة الخارجية خط أحمر | عند وصل شاشة خارجية تُلغى كل إجراءات إدارة طاقة الرسوم |
| لا صلاحيات لما لا يحتاجها | السطوع عبر مسار الجلسة المصرّح به (GNOME ثم logind)، بلا كلمة مرور |
| لا رقم بلا قياس | التوفير يُقرأ من العتاد قبل وبعد، أو يُعلَن أنه غير قابل للقياس |

**ما لا يفعله التطبيق أبداً، ويقوله في نتيجة كل جولة**: التعليق الشامل لأجهزة
USB (يفصل محطات الإرساء ولوحة المفاتيح والفأرة)، وحجب البلوتوث (يُسقط الفأرة)،
وإجبار مستوى أداء الرسوم على منخفض (يُسقط الشاشة الخارجية)، وإفراغ ذاكرة القرص
المخبّأة (يُجبر إعادة القراءة من القرص فيزيد السحب لا يقلّله)، وتغيير
`swappiness` أو مجدول القرص (تغيير دائم بلا مكسب مثبت)، وخفض أولوية المعالج
بـ `renice` (غير قابل للاستعادة بلا صلاحيات).

الامتناع نتيجة معلنة لا صمت: كل ما لم يُنفَّذ يظهر مع سببه، ولا يُزعم نجاحه.

### الواجهة

أربعة مجالات: الحالة، التحكم، التفاصيل، الإعدادات. القراءة الأساسية وما
يستدعي تدخّلاً في الأول، والتحكّم فيما يدعمه العتاد في الثاني، والتحليل والسجل
والتشخيص في أقسام تُفتح بالطلب في الثالث. ما لا يدعمه جهازك يُطوى ولا يُعرض
كزر جاهز لا يعمل. عربية بالكامل باتجاه من اليمين إلى اليسار، مع طبقة ترجمة في
`locales/` وأيقونات مرسومة بمسارات (بلا إيموجي)، ونظام تصميم واحد في `theme.py`
لا قيم لونية متفرقة، وطبقة حوارات واحدة في `dialogs.py` (لا `QMessageBox` يرسمه
النظام بخلفية فاتحة وأزرار لاتينية داخل واجهة عربية داكنة).

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
python main.py               # لوحة القياس كاملة
python main.py --background   # أيقونة الصينية فقط، بلا نافذة
python main.py --window       # اللوحة مبنيّة ومخفيّة (توافق مع القديم)
```

### التشغيل الدائم في الخلفية

```bash
./service_manager.sh install    # بلا sudo
./service_manager.sh check      # للتأكد أنه يعمل ومستقل عن الطرفية
```

يكتب خدمة **مستخدم** في `~/.config/systemd/user/batteryguard.service`، ويتحقّق
من صحتها بـ `systemd-analyze verify` قبل إعلان أي نجاح. النتيجة:

| السؤال | الجواب |
|---|---|
| أغلقت الطرفية؟ | يعمل. أبوه مدير المستخدم لا الصدفة. |
| أعدت تشغيل الجهاز؟ | يعود عند تسجيل الدخول. |
| توقّف بخطأ؟ | يعود بعد 10 ثوانٍ، بحدّ 5 محاولات كل 5 دقائق. |
| قبل تسجيل الدخول؟ | يحتاج `loginctl enable-linger` (يعرضه المدير ويسألك). |

في وضع `--background` **لا تُبنى النافذة إطلاقاً** ولا تُحمَّل وحدة الواجهة، بل
يعمل متحكّم خفيف يملك القياس والاستدلال والحماية والأيقونة. تُبنى لوحة القياس
عند أول نقرة، وتتبنّى وقتها نفس بيانات التعلّم وخيط المراقبة العامل.

عند `SIGTERM` (من systemd أو تسجيل الخروج أو إعادة التشغيل) يجري إغلاق نظيف
بترتيب ملزم: الإفراج عن أي عملية علّقها الحارس أولاً، ثم إيقاف الخيط، ثم حفظ
التعلّم. بلا هذا المعالِج كان بايثون يموت فوراً ويترك عملية المستخدم معلّقة.

الاستهلاك المقيس على جلسة كاملة: `3.066s CPU time, 51.9M memory peak`.

راجع [docs/OPERATIONS.md](docs/OPERATIONS.md) للتفاصيل واستكشاف الأخطاء.

### بناء نسخة تنفيذية

راجع [docs/BUILDING.md](docs/BUILDING.md). يستخدم PyInstaller عبر `build.sh`
على لينكس أو `build.bat` على ويندوز، ويضمّن `locales/` و`sounds/` و`assets/`.

### هيكل المشروع

```
main.py                  نقطة الدخول: اللغة، النسخة الواحدة، الأوضاع الثلاثة
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

power_attribution.py     نسب القدرة المقيسة إلى العمليات + نموذج طاقة متعلَّم
battery_intelligence.py  شذوذ متين، نقاط تغيّر، دورية، تآكل مقيس، درجة ضرر
guard_actions.py         الإجراءات الفعلية وطوق السلامة وقابلية التراجع
guard_service.py         منسّق الخطّ: الوتيرة والسياسة والتخزين (بلا Qt)

service_runner.py        وضع الخلفية بلا نافذة (البناء التأخيري للوحة)
service_installer.py     وحدة systemd للمستخدم + التحقق منها + الإزالة
lifecycle.py             الإغلاق النظيف عند SIGTERM/SIGINT/SIGHUP
settings_bridge.py       مصدر واحد لقراءة الإعدادات (بواجهة وبلا واجهة)

charge_controller.py     واجهة التحكم
charge_control_advanced.py  التنفيذ الفعلي لحدود الشحن
notification_manager.py  الإشعارات والتذكيرات والأصوات
system_tuning.py         محرك الضبط الآمن: لقطة، استعادة، وبوابات سلامة
battery_optimizer.py     المحسّن: إجراءات مقيسة قابلة للتراجع وامتناعات معلنة
auto_optimizer.py        المحسن التلقائي في الخلفية (معطّل افتراضياً)
dialogs.py               طبقة الحوارات الموحدة (لا QMessageBox في المشروع)
storage.py               تخزين JSON ذري آمن بين الخيوط
tests/                   حزمة pytest (357 اختباراً)
docs/OPERATIONS.md       دليل التشغيل الدائم واستكشاف الأخطاء
```

### الاختبارات

```bash
pip install pytest pytest-timeout
pytest
```

تعمل الحزمة كاملة بلا شاشة عبر `QT_QPA_PLATFORM=offscreen` (357 اختباراً في
نحو 36 ثانية)، وتغطي محرك التآكل والنصائح، وكشف البطارية غير المبلّغة، وملف
الاستخدام وأعماق التفريغ، ومنطق الإشعارات والتهدئة، والتخزين الذري والاسترجاع
من ملف تالف، واكتشاف النسخة الواحدة، ودورة حياة النافذة كاملة.

وتغطي في المحسّن ما يلي، وكلّه انحدارات على أعطال حقيقية أصابت أجهزة مستخدمين:

- أن السطوع **لا يُرفع** أبداً بعد أن ينزله المستخدم، ولا ينزل تحت الحدّ
  الأدنى، وأن الاستعادة تعيد القيمة الأصلية بالضبط.
- أن الامتناع لا يُنشئ «تغييراً ينتظر الاستعادة»، وأن اللقطة تبقى على القرص
  عند فشل الاستعادة ولا تُحذف.
- أن بوابة الرسوم تمنع التصرّف عند وصل شاشة خارجية، وعند تعذّر قراءة حالة
  الشاشات (الجهل ليس إذناً بالتصرف).
- أن أجهزة `backlight` الخارجية (ddcci) مستبعدة، واللوحة الداخلية وحدها هي
  ملك التطبيق.
- أن أياً من الأوامر التي أعطبت أجهزة لا يعود إلى الشيفرة: تعليق USB الشامل،
  و`rfkill`، و`power_dpm_force_performance_level`، و`card0` المثبّت،
  و`drop_caches`، و`swappiness`، ومجدول القرص، و`cpupower`، و`sudo`.
  الفحص يجري على شيفرة الوحدة بعد استثناء التوثيق بـ `ast`.
- أن لا رقم توفير يُعلَن بلا قياس من العتاد قبل وبعد.

وتغطي في طبقات الحارس ما يلي، وأكثره يقيس أن التطبيق **يمتنع** حيث يجب:

- استعادة معاملات معروفة من بيانات مصنوعة، ورفض المعاملات السالبة، ورفض
  العيّنات غير الفيزيائية.
- متانة كشف الشذوذ أمام خط أساس ملوَّث، مع إثبات أن الطريقة القديمة تفشل هناك.
- معدّل التنبيه الكاذب لكشف نقاط التغيّر (حرس على المعايرة).
- تطابق سلسلة درجة الضرر مع الحساب اليدوي خطوة بخطوة.
- امتناع الحارس عن عمليات النظام وخيوط النواة وعمليات مستخدم آخر وذرّية
  التطبيق وأرقام العمليات المُعاد استخدامها، بعمليات حقيقية على النظام.
- الإفراج عن التعليق: يدوياً، وعند الإغلاق، وبالمؤقّت الإلزامي.
- أن `terminate` لا يُبلَغ من أي مسار تلقائي، ولا يُقبل كسقف سياسة.
- أن ملف وحدة systemd المُولَّد يقبله `systemd-analyze verify` فعلاً، وأن
  الأخطاء الأربعة التي كانت تُعطّل الخدمة السابقة لا تعود.
- أن `SIGTERM` حقيقية إلى العملية تُنتج إغلاقاً نظيفاً.

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

### Which process is draining your battery

Total power is measured from hardware. Per-process load comes from CPU time,
real block-layer bytes, and context switches (a proxy for the wakeups that keep
the CPU out of deep sleep states). A **non-negative linear regression learns the
watts per unit of load from your own machine**; before 25 samples it uses
declared priors and reports low confidence. Training runs only while
discharging, because on mains `current_now` measures charging current rather
than consumption. Attributed watts never exceed what was measured — power that
cannot be attributed to a process (display, radio) is shown as such rather than
forced onto processes.

The figure shown is not a CPU percentage but **how much battery capacity a
process costs you per year**, derived from measured watts, your observed hours
on battery, and the cycle-wear table from BU-808.

### Damage that never shows up as CPU usage

Idle inhibitors (the machine never sleeps), sleep inhibitors, wakeup storms
above 400/s, sustained load above 25% of a core, and disk thrashing. Inhibitors
are read from `systemd-inhibit`, distinguishing a real block on a sleep or idle
target from the benign delay that NetworkManager normally holds.

### Detection beyond fixed thresholds

Median and MAD-based anomaly detection with a separate baseline per hour of day;
two-sided CUSUM for sustained regressions, calibrated to zero false alarms over
100k samples; autocorrelation at 24 and 168 hours to prove a rhythm rather than
assume one; linear regression on hardware-reported full capacity for wear
measured on **this** cell, withheld until at least ten days of readings; and
Pearson correlation between each process's watts and the drain rate, to separate
causation from coincidence.

### Actions, and what can be undone

Alert (no touch), `ionice` throttling (reversible), `renice` (**not** reversible
without privileges, so opt-in only and declared as such), `SIGSTOP` suspension
(reversible, auto-released after five minutes by an independent watchdog), and
termination (explicit request only, never reachable from an automatic path).

The guard never touches the session manager, display server, window manager,
message bus, package manager, kernel threads, other users' processes, itself,
its ancestors, its own children, or a process whose PID was reused between
inference and action. By default it measures and alerts and changes nothing.
See [docs/OPERATIONS.md](docs/OPERATIONS.md).

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

### The optimizer: it lowers draw, restores everything it changed, and declares what it refused

Every system change outside charge limits goes through `system_tuning.py` alone:

| Principle | How it is enforced |
|---|---|
| No change without a way back | Every value is snapshotted to disk before it is changed, so undo survives a restart |
| Brightness is lowered, never raised | If you lowered it, the app will not raise it; it never goes below 30%; the snapshot is written only after a successful write |
| Internal panel only | eDP / LVDS / DSI. Any external `backlight` (ddcci) is not the app's business |
| An external display is a red line | While one is connected, all graphics power-management actions are cancelled |
| No privileges for work that needs none | Brightness goes through the permitted session path (GNOME, then logind) with no password |
| No figure without a measurement | Savings are read from hardware before and after, or declared unmeasurable |

**What it never does, and says so in every result**: blanket USB autosuspend
(disconnects docks, keyboards and mice), Bluetooth blocking (drops your mouse),
forcing the GPU performance level low (drops the external display), dropping the
page cache (forces re-reads from disk, raising draw rather than lowering it),
changing `swappiness` or the disk scheduler (permanent, with no proven gain), and
lowering CPU priority with `renice` (not reversible without privileges).

A refusal is a declared result, not silence: everything not applied is shown with
its reason, and never reported as success.

### Interface

Four areas: Status, Control, Details, Settings. The primary reading and anything
that calls for action live in the first; control over what the hardware supports
in the second; analysis, record and diagnostics in on-demand sections in the
third. What your machine does not support is folded away instead of being shown
as a ready button that cannot work. Fully Arabic and right-to-left, with a
translation layer in `locales/`, path-drawn icons and no emoji, one design system
in `theme.py` rather than scattered colour values, and one dialog layer in
`dialogs.py` (no OS-drawn `QMessageBox` with a light background and Latin buttons
inside a dark Arabic interface).

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
python main.py               # full dashboard
python main.py --background  # tray icon only, no window built at all
python main.py --window      # dashboard built but hidden (legacy)
```

### Running permanently in the background

```bash
./service_manager.sh install    # no sudo
./service_manager.sh check      # confirm it runs independently of the terminal
```

Writes a **systemd user** unit to `~/.config/systemd/user/batteryguard.service`
and validates it with `systemd-analyze verify` before reporting success. It then
survives closing the terminal (its parent is the user manager, not your shell),
returns at login after a reboot, and restarts itself after a crash with a cap of
5 attempts per 5 minutes. Running before login additionally needs
`loginctl enable-linger`, which the manager offers rather than doing silently.

In `--background` the UI module is never imported; a light controller owns
measurement, inference, protection, and the tray icon, and the dashboard is
built on first click, adopting the already-running monitor thread and learned
data. On `SIGTERM` an ordered clean shutdown releases any suspended process
first, then stops the thread, then persists what was learned.

Measured cost over a full session: `3.066s CPU time, 51.9M memory peak`.
See [docs/OPERATIONS.md](docs/OPERATIONS.md).

### Building a binary

See [docs/BUILDING.md](docs/BUILDING.md). PyInstaller via `build.sh` on Linux
or `build.bat` on Windows; the spec bundles `locales/`, `sounds/`, `assets/`.

### Tests

```bash
pip install pytest pytest-timeout
pytest
```

The suite runs fully headless with `QT_QPA_PLATFORM=offscreen` (357 tests in
about 36 seconds) and covers the wear and advice engine, non-reporting battery
detection, the usage profile and discharge depths, notification cooldown logic,
atomic storage and corrupt-file recovery, single-instance detection, and a full
window lifecycle.

For the guard layers most tests assert that the app **refuses** to act where it
must: recovering known coefficients from synthetic data and rejecting negative
ones, anomaly-detection robustness against a poisoned baseline (including proof
that the previous mean-based method fails there), a false-alarm-rate guard on the
change-point calibration, the damage-score chain matching a manual calculation
step by step, the guard declining to touch system processes, kernel threads,
other users' processes, its own children, and reused PIDs against real processes,
suspension release by hand and on shutdown and by the mandatory timer, that
`terminate` is unreachable from any automatic path, that the generated systemd
unit is actually accepted by `systemd-analyze verify` with the four previous
service-breaking bugs pinned as regressions, and that a real `SIGTERM` to the
process produces a clean shutdown.

### Privacy

All data stays on your machine: no account, no cloud service, no telemetry.
Data and log files live in the user configuration directory.

## License

MIT, see [LICENSE](LICENSE).
