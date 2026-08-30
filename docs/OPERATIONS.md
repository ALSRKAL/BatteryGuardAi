# التشغيل الدائم في الخلفية

دليل تشغيل BatteryGuardAI كحارس يعمل دائماً: بأيقونة في شريط المهام، يبقى بعد
إغلاق الطرفية، ويعود وحده بعد إعادة تشغيل الجهاز.

[English](#english-operations-guide)

---

## الخلاصة في سطرين

```bash
cd /path/to/BatteryGuardAI
./service_manager.sh install
```

هذا كل شيء. لا `sudo`، ولا تعديل ملفات يدوياً. للتأكد:

```bash
./service_manager.sh check
```

---

## أوضاع التشغيل الثلاثة

| الأمر | ما يفعله | متى تستخدمه |
|---|---|---|
| `python main.py` | لوحة القياس كاملة، ظاهرة | أول مرة، ولضبط الإعدادات |
| `python main.py --background` | أيقونة صينية فقط، **بلا نافذة** | التشغيل الدائم (هذا ما تستخدمه الخدمة) |
| `python main.py --window` | لوحة القياس مبنيّة ومخفيّة | توافق مع الإصدارات القديمة |

الفرق بين `--background` و`--window` ليس شكلياً: في `--background` لا تُبنى
النافذة إطلاقاً ولا تُحمَّل وحدة الواجهة، بل يعمل متحكّم خفيف يملك القياس
والاستدلال والحماية والأيقونة. تُبنى لوحة القياس عند أول نقرة على الأيقونة
فقط، وتتبنّى وقتها نفس بيانات التعلّم وخيط المراقبة العامل بلا أن يبدأ شيء
من الصفر.

---

## التثبيت: ماذا يحدث بالتفصيل

`./service_manager.sh install` يكتب وحدة **خدمة مستخدم** في:

```
~/.config/systemd/user/batteryguard.service
```

ثم يتحقّق من صحتها بـ `systemd-analyze verify` **قبل** أن يعلن أي نجاح، ثم
يُفعّلها ويشغّلها.

### لماذا خدمة مستخدم لا خدمة نظام

خدمة النظام في `/etc/systemd/system/` تحتاج `sudo`، ولا تعرف جلستك الرسومية،
فلا تجد صينية تسكنها الأيقونة، وتحتاج تصريحاً خاصاً للكتابة في مجلد إعداداتك.
خدمة المستخدم تعمل بهويتك داخل جلستك، وترث `DISPLAY` و`DBUS_SESSION_BUS_ADDRESS`
من مدير المستخدم، ولا تحتاج صلاحيات على الإطلاق.

### إن لم يتوفّر systemd

يسقط المثبّت تلقائياً إلى ملف تشغيل تلقائي في
`~/.config/autostart/batteryguard.desktop`. هذا يعيد التشغيل بعد الإقلاع لكنه
**لا** يُعيد تشغيل التطبيق إن توقّف. المثبّت يقول لك أي طريقة استخدم.

ولا تبقى الطريقتان معاً: تثبيت الخدمة يُزيل ملف التشغيل التلقائي، لأن بقاءهما
يعني نسختين تتنافسان على نفس القفل وواحدة تفشل برسالة مربكة.

---

## التحقق أنه يعمل فعلاً

```bash
./service_manager.sh check
```

مثال على مخرَج سليم:

```
  رقم العملية      : 209999
  أبوها            : 2225 (مدير المستخدم، لا الطرفية)
  المجموعة         : /user.slice/user-1000.slice/user@1000.service/app.slice/batteryguard.service
  الذاكرة          : 98 MB
  إعادات التشغيل   : 0
```

**أبوها ليس الطرفية**: هذا هو الدليل على أن إغلاق الطرفية لن يوقفه. لو كان
أبوها رقم عملية صدفتك، لمات معها.

### الأوامر المباشرة

```bash
systemctl --user status batteryguard.service     # الحالة الكاملة
systemctl --user is-active batteryguard.service  # active أو inactive
journalctl --user -u batteryguard.service -f     # السجل الحيّ
```

---

## البقاء بعد إعادة التشغيل وبعد الخروج

| السؤال | الجواب |
|---|---|
| أغلقت الطرفية؟ | يعمل. أبوه مدير المستخدم لا الصدفة. |
| أعدت تشغيل الجهاز؟ | يعود عند تسجيل الدخول (`WantedBy=default.target`). |
| توقّف التطبيق بخطأ؟ | يعود بعد 10 ثوانٍ (`Restart=always`)، بحدّ 5 محاولات كل 5 دقائق. |
| سجّلت الخروج ثم عدت؟ | يعود مع الجلسة الجديدة. |
| تريده يعمل **قبل** تسجيل الدخول؟ | تحتاج `linger`، انظر أدناه. |

### linger: التشغيل قبل تسجيل الدخول

افتراضياً يتوقّف مدير systemd الخاص بك عند آخر خروج، فتتوقّف الخدمة معه.
`linger` يجعله باقياً:

```bash
./service_manager.sh linger
```

يعرض الأمر ويسألك قبل تنفيذه، لأنه الأمر الوحيد الذي يحتاج صلاحيات:

```bash
sudo loginctl enable-linger $USER
```

للتأكد:

```bash
loginctl show-user $USER --property=Linger    # Linger=yes
```

**ملاحظة صادقة**: مع `linger` تعمل الخدمة قبل تسجيل الدخول، لكن الأيقونة لن
تظهر حتى تتوفّر جلسة رسومية. القياس والحماية والإشعارات تعمل، والأيقونة تنتظر
الجلسة.

---

## الإغلاق النظيف: لماذا يهمّ

عند `systemctl stop` أو تسجيل الخروج أو إعادة التشغيل يرسل النظام `SIGTERM`.
التطبيق يستقبلها وينفّذ إغلاقاً نظيفاً بترتيب ملزم:

1. **الإفراج عن أي عملية علّقها الحارس** — الأهمّ. عملية معلّقة بعد اختفاء من
   علّقها مشكلة لا يفهمها المستخدم ولا يعرف كيف يحلّها.
2. إيقاف التذكيرات والمحسّن التلقائي.
3. إيقاف خيط المراقبة تعاونياً.
4. حفظ بيانات التعلّم وحالة نموذج الطاقة.

في السجل يظهر هذا صراحةً:

```
استُقبلت SIGTERM - بدء الإغلاق النظيف
إيقاف وضع الخلفية...
انتهى خيط المراقبة
تم الإغلاق النظيف
انتهى التطبيق برمز 0
```

مهلة `TimeoutStopSec=15` في ملف الوحدة تعطي هذا التسلسل وقته، والتطبيق يخرج
من نفسه بعد 12 ثانية إن تعلّق شيء، فلا يُقتل بـ `SIGKILL` وسط عمله.

---

## الإزالة

```bash
./service_manager.sh uninstall
```

يوقف الخدمة، يُلغي تفعيلها، ويحذف **كل** صور التشغيل الدائم (الوحدة وملف
التشغيل التلقائي معاً). لا يبقى شيء يعيد التطبيق بعد الإقلاع.

---

## استكشاف الأخطاء

### الخدمة تعمل لكن لا أيقونة في الشريط

الأرجح أن بيئتك لا تعرض صينية نظام. GNOME الحديث لا يعرضها بلا إضافة:

```bash
sudo apt install gnome-shell-extension-appindicator
```

ثم أعد تسجيل الدخول وفعّل الإضافة من *Extensions*.

التطبيق لا يستسلم فوراً: يعيد محاولة إظهار الأيقونة 12 مرة بتباعد متزايد،
لأن مضيف الصينية قد يبدأ بعد التطبيق عند بدء الجلسة. وإن لم تتوفّر، يكتب في
السجل أن الأيقونة غائبة **ويواصل** القياس والحماية والإشعارات:

```
صينية النظام غير متاحة - التطبيق يعمل في الخلفية بلا أيقونة.
```

### `Unit batteryguard.service has a bad unit file setting`

المثبّت الحالي يفحص الملف قبل إعلان النجاح، فلا يجب أن تصل إلى هذه الرسالة.
إن وصلت:

```bash
systemd-analyze --user verify ~/.config/systemd/user/batteryguard.service
```

سيقول لك السطر والمفتاح بالتحديد.

### الخدمة تُعاد تشغيلها بلا توقّف

```bash
journalctl --user -u batteryguard.service -n 100 --no-pager
```

`StartLimitBurst=5` مع `StartLimitIntervalSec=300` يوقف الحلقة بعد خمس محاولات
في خمس دقائق، فلا تدور بلا نهاية. بعد إصلاح السبب:

```bash
systemctl --user reset-failed batteryguard.service
./service_manager.sh restart
```

### `Failed to connect to bus`

مدير systemd الخاص بك لا يعمل، وأغلب الحالات داخل حاوية أو جلسة SSH بلا
`XDG_RUNTIME_DIR`. تحقّق:

```bash
echo $XDG_RUNTIME_DIR              # يجب /run/user/<uid>
systemctl --user is-system-running
```

إن لم يعمل، استخدم البديل:

```bash
python3 service_installer.py install --desktop
```

### نسختان تعملان

```bash
pgrep -af "main.py"
```

نظام النسخة الواحدة يمنع هذا (قفل على منفذ محلي)، والنسخة الثانية تطلب إظهار
الأولى ثم تخرج. إن رأيت اثنتين فعلاً فالأرجح وجود ملف تشغيل تلقائي قديم مع
الخدمة معاً — `uninstall` ثم `install` يُصلحه.

### السجل كبير

السجل مُدوَّر: 10 ميغابايت × 4 ملفات كحدّ أقصى. إن وجدت ملفاً ضخماً من إصدار
قديم بلا تدوير:

```bash
ls -lh ~/.config/batteryguard/batteryguard.log*
rm ~/.config/batteryguard/batteryguard.log.1     # بعد التأكد
```

---

## الملفات والمسارات

| المسار | المحتوى |
|---|---|
| `~/.config/systemd/user/batteryguard.service` | وحدة الخدمة |
| `~/.config/autostart/batteryguard.desktop` | التشغيل التلقائي (البديل فقط) |
| `~/.config/batteryguard/battery_settings.json` | إعدادات المستخدم |
| `~/.config/batteryguard/battery_ai_data.json` | سجل الاستخدام والتعلّم |
| `~/.config/batteryguard/battery_guard_state.json` | نموذج الطاقة وسجل المستهلكين |
| `~/.config/batteryguard/batteryguard.log` | السجل (مُدوَّر) |
| `journalctl --user -u batteryguard` | سجل الخدمة |

كل شيء محلي. لا حساب، ولا خدمة سحابية، ولا إرسال قياسات إلى أي جهة.

---

## استهلاك الحارس نفسه

قياس فعلي من `systemd` على جلسة كاملة:

```
Consumed 3.066s CPU time, 51.9M memory peak
```

الوتيرة سبب ذلك: قراءة البطارية رخيصة (ملف أو اثنان) فتجري كل ثانيتين، أما
جولة نسب الطاقة فتقرأ عدّادات مئات العمليات فتجري كل 25 ثانية. الفاصل قابل
للتعديل من الإعدادات (`attribution_interval`)، وأقلّه 10 ثوانٍ بحدّ صلب:
أقصر من ذلك يجعل الحارس نفسه من أكبر مستنزفي البطارية، وهو نقيض غرضه.

`Nice=5` في ملف الوحدة تعني أن التطبيق لا يزاحم عملك على المعالج.

---

## حارس البطارية: الذكاء والإجراءات

الخدمة لا تراقب فقط، بل تُنسب الاستهلاك إلى العمليات وتتصرّف حسب سياستك.

### كيف يُنسب الاستهلاك إلى عملية بالواط

1. تُقاس القدرة الكلية من العتاد (`power_now`، أو `voltage_now × current_now`).
   رقم **مقيس** لا مُخترع.
2. تُقاس أحمال كل عملية من عدّادات النظام: زمن المعالج، بايتات القرص الفعلية،
   وتبديلات السياق (وكيل عن الإيقاظات التي تمنع نوم المعالج العميق).
3. ينحدر نموذج خطّي غير سالب على قياسات **جهازك أنت** ليتعلّم كم واط تكلّف كل
   وحدة حِمل. قبل توفّر 25 عيّنة تُستخدم قيم أولية وتُعلَن الثقة منخفضة صراحةً.
4. تُوزَّع القدرة المقيسة على العمليات بنسبة تكلفتها. ما لا يُنسب إلى عملية
   (الشاشة، الراديو) يُعرض باسمه لا يُوزَّع قسراً.

**التدريب يجري أثناء التفريغ فقط.** أثناء الشحن يقيس `current_now` تيار الشحن
لا استهلاكك، والتغذية به تفسد المعامل. لذلك لن ترى واطاً لكل عملية إلا وأنت
على البطارية، وهذا مذكور في الواجهة لا مخفيّ.

### كم تكلّفك عملية سنوياً

الرقم الذي يهمّك ليس نسبة المعالج، بل كم من سعة بطاريتك تخسر:

```
نسبة/ساعة       = واط منسوبة ÷ سعة البطارية (واط·ساعة) × 100
دورات مكافئة/سنة = نسبة/ساعة × ساعات عملك على البطارية × 365 ÷ 100
فقد السعة/سنة   = دورات مكافئة × تآكل الدورة عند عمق تفريغك المعتاد
```

تآكل الدورة مأخوذ من جدول BU-808 (الجدول 2) الموثّق في `battery_science.py`،
وساعات العمل وعمق التفريغ **مرصودان** من استخدامك لا مفترضان.

### السلوكيات التي تُتلف البطارية ولا تظهر في نسبة المعالج

| السلوك | ما يعنيه | لماذا يضرّ |
|---|---|---|
| `idle_inhibitor` | يمنع الشاشة والجهاز من الخمول | الأخطر: الجهاز لا ينام أصلاً |
| `sleep_inhibitor` | يمنع النوم | يبقي العتاد يقظاً |
| `wakeup_storm` | إيقاظ متكرر (>400/ث) | يمنع المعالج من حالات النوم العميقة |
| `cpu_sustained` | حِمل مستمر (>25% نواة لدقيقتين) | استنزاف ثابت لا قفزة عابرة |
| `disk_thrash` | قراءة/كتابة مكثّفة (>6 م.ب/ث) | القرص من أكبر مستهلكي الطاقة |
| `memory_pressure` | استهلاك ذاكرة عالٍ | يدفع النظام إلى التبديل |

موانع النوم تُقرأ من `systemd-inhibit`، ويُميَّز `mode=block` على هدف نوم أو
خمول (منع حقيقي) من `mode=delay` الحميد الذي يستخدمه مدير الشبكة عادةً.

### الإجراءات وقابلية التراجع

| الإجراء | الآلية | قابل للتراجع؟ |
|---|---|---|
| تنبيه | إشعار فقط، لا لمس للعملية | لا ينطبق |
| خفض الأولوية | `ionice` إلى الصنف الخامل | **نعم** |
| خفض أولوية المعالج (اختياري) | `renice` | **لا** على لينكس بلا صلاحيات |
| تعليق مؤقت | `SIGSTOP` | **نعم** بـ `SIGCONT` |
| إيقاف نهائي | `SIGTERM` ثم `SIGKILL` | **لا** — بطلبك الصريح فقط |

`renice` غير قابل للاستعادة لأن `RLIMIT_NICE` يساوي صفراً على معظم التوزيعات:
تستطيع خفض أولوية عمليتك ولا تستطيع رفعها. لذلك لا يُطبَّق إلا بموافقة صريحة
(`guard_allow_irreversible_nice`)، ويُعلَن عدم إمكان التراجع بدل ادّعائه.

### طوق السلامة

الحارس **لا يلمس** أياً من هذه، ولا يوجد إعداد يتجاوزها:

- عمليات النظام المحمية: `systemd`، `Xorg`، `gnome-shell`، `kwin`، `gdm`،
  `NetworkManager`، `polkitd`، `pipewire`، `dpkg`/`apt`، وغيرها.
- خيوط النواة (تُعرف بأن سطر أوامرها فارغ أو أن أباها `kthreadd`).
- عمليات مستخدم آخر.
- التطبيق نفسه، وأسلافه، والعمليات التي أنشأها.
- عملية أُعيد استخدام رقمها بين لحظة الاستدلال ولحظة التنفيذ (يُفحص الاسم
  مرة ثانية قبل أي إجراء).

وأربع ضمانات إضافية:

1. **مؤقّت إفراج إلزامي**: كل تعليق يُفرَج عنه تلقائياً بعد 5 دقائق، عبر خيط
   مراقبة مستقل، حتى لو انهار التطبيق.
2. **لا إيقاف تلقائي أبداً**: `terminate` لا يصل إليها أي مسار تلقائي، ولا
   تُقبل كسقف سياسة، وتحتاج تأكيداً في نافذة.
3. **إفراج شامل عند الخروج**: أي تعليق يُفرَج عنه قبل أن يختفي التطبيق.
4. **الوضع الافتراضي لا يلمس شيئاً**: `guard_automatic=false` يعني تنبيهات فقط
   حتى تسمح أنت.

### الإعدادات

| المفتاح | الافتراضي | المعنى |
|---|---|---|
| `guard_enabled` | `true` | تشغيل الحارس (مراقبة وتنبيه) |
| `guard_automatic` | `false` | التنفيذ التلقائي بلا سؤال |
| `guard_max_action` | `alert` | أقصى شدّة: `alert`/`throttle`/`suspend` |
| `guard_only_on_battery` | `true` | التصرّف على البطارية فقط |
| `guard_min_damage_score` | `45` | أقل درجة ضرر (0-100) تستدعي إجراءً |
| `guard_min_confidence` | `55` | أقل ثقة للتصرّف التلقائي؛ ما دونها تنبيه |
| `guard_allow_irreversible_nice` | `false` | السماح بـ `renice` غير القابل للاستعادة |
| `guard_allowlist` | `""` | أسماء يُسمح بالتصرّف تجاهها (فارغ = الكل) |
| `guard_blocklist` | `""` | أسماء لا تُلمس نهائياً |
| `attribution_enabled` | `true` | قياس استهلاك كل عملية |
| `attribution_interval` | `25` | ثواني بين جولات القياس (أدناه 10) |

### الفرق بين الوضع اليدوي والتلقائي

الافتراضي (`guard_automatic=false`): الحارس يقيس ويستنتج ويُنبّه، ولا يلمس
عملية واحدة. الإجراءات متاحة من قائمة الأيقونة ومن لوحة التحليل، والقرار لك.

التلقائي (`guard_automatic=true`): ينفّذ ما يوصي به الاستدلال داخل حدود
`guard_max_action`. وحتى في هذا الوضع يتحوّل الإجراء إلى تنبيه إذا كان:

- الجهاز موصولاً بالكهرباء (`on_mains`)
- قياس البطارية غير موثوق (`not_reporting`)
- الثقة أقل من الحدّ (`low_confidence`)
- الاسم خارج قائمة السماح (`not_allowlisted`)

---

## English operations guide

### One command

```bash
cd /path/to/BatteryGuardAI
./service_manager.sh install
./service_manager.sh check
```

No `sudo`, no manual file editing.

### Run modes

| Command | Behaviour |
|---|---|
| `python main.py` | Full dashboard, visible |
| `python main.py --background` | Tray icon only, **no window built at all** |
| `python main.py --window` | Dashboard built but hidden (legacy) |

In `--background` the UI module is never imported. A light controller owns
measurement, inference, protection, and the tray icon. The dashboard is built
on the first click and adopts the already-running monitor thread and learned
data rather than starting over.

### What install does

Writes a **systemd user** unit to `~/.config/systemd/user/batteryguard.service`,
validates it with `systemd-analyze verify` **before** reporting success, then
enables and starts it.

A user service needs no `sudo`, runs inside your graphical session, and
inherits `DISPLAY` and `DBUS_SESSION_BUS_ADDRESS` from your user manager. A
system unit in `/etc` cannot do any of those, which is why the previous
approach did not work.

If no systemd user manager is available, the installer falls back to an XDG
autostart entry and tells you so. Installing the service removes the autostart
entry, because keeping both starts two competing instances.

### Survival guarantees

| Question | Answer |
|---|---|
| Closed the terminal? | Keeps running. Its parent is the user manager, not your shell. |
| Rebooted? | Returns at login (`WantedBy=default.target`). |
| Crashed? | Returns after 10s (`Restart=always`), capped at 5 tries per 5 minutes. |
| Before login? | Needs `loginctl enable-linger` — run `./service_manager.sh linger`. |

### Clean shutdown

On `SIGTERM` (from `systemctl stop`, logout, or reboot) the app runs an ordered
shutdown: release any suspended process **first**, stop reminders, stop the
monitor thread cooperatively, then persist learned data. Without this handler
Python would die instantly and leave a user process frozen with no explanation.

### Per-process power attribution

Total power is measured from hardware. Per-process load comes from CPU time,
real block-layer bytes, and context switches. A non-negative linear regression
learns the watts per unit of load **from your own machine**; before 25 samples
it uses priors and reports low confidence honestly. Training happens only while
discharging, because on mains `current_now` measures charging current, not
consumption.

The number that matters is annual capacity loss, derived from measured watts,
your observed hours on battery, and the cycle-wear table from BU-808.

### Safety

The guard never touches protected system processes, kernel threads, other
users' processes, itself, its ancestors, its own children, or a process whose
PID was reused. Every suspension is released automatically after 5 minutes by
an independent watchdog thread, and `terminate` is never reachable from any
automatic path. The default policy alerts and touches nothing.

### Troubleshooting

**Service runs but no tray icon** — modern GNOME needs an extension:

```bash
sudo apt install gnome-shell-extension-appindicator
```

The app retries showing the icon 12 times with increasing delay, then logs that
the tray is unavailable and **keeps** measuring, protecting, and notifying.

**Bad unit file setting** — the installer validates before claiming success, so
you should not see this. If you do:

```bash
systemd-analyze --user verify ~/.config/systemd/user/batteryguard.service
```

**Restart loop** — `StartLimitBurst=5` over `StartLimitIntervalSec=300` stops
it. After fixing the cause:

```bash
systemctl --user reset-failed batteryguard.service
```

**Failed to connect to bus** — no user manager (common in containers or bare
SSH). Use `python3 service_installer.py install --desktop`.

### Cost of the guard itself

Measured by systemd over a full session: `3.066s CPU time, 51.9M memory peak`.
Battery reads are cheap and run every 2 seconds; the per-process round reads
hundreds of processes and runs every 25 seconds. The interval is configurable
with a hard floor of 10 seconds, because anything shorter would make the guard
one of the biggest drains itself.
