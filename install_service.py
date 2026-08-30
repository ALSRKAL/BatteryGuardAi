#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مثبّت خدمة BatteryGuardAI - واجهة تفاعلية

المنطق كله في `service_installer.py`؛ هذا الملف قائمة تفاعلية فوقه ويُحتفظ به
لأن التوثيق القديم والاختصارات تشير إليه بالاسم.

النسخة السابقة كانت تكتب وحدة systemd على مستوى النظام تحتاج `sudo` ولا تعمل
(تمنع الكتابة إلى مجلد المستخدم، ولا توسّع متغيّرات الصدفة، وتربط نفسها بهدف
نظام لا يعرف جلسة رسومية). صارت الآن خدمة **مستخدم** لا تحتاج `sudo` إطلاقاً.
"""

import sys

import service_installer as installer


def _header() -> None:
    print('─' * 62)
    print('  مثبّت التشغيل الدائم - BatteryGuardAI')
    print('─' * 62)
    print()


def _menu() -> str:
    print('1. تثبيت التشغيل الدائم (خدمة مستخدم، بلا sudo)')
    print('2. عرض الحالة')
    print('3. إزالة التشغيل الدائم')
    print('4. عرض سجل الخدمة')
    print('5. إعادة تشغيل الخدمة')
    print('6. خروج')
    print()
    try:
        return input('اختيارك (1-6): ').strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return '6'


def main() -> int:
    _header()
    installer._print_status()
    print()

    while True:
        choice = _menu()
        print()
        if choice == '1':
            result = installer.install()
            installer._print_result(result)
            print()
            installer._print_status()
        elif choice == '2':
            installer._print_status()
        elif choice == '3':
            installer._print_result(installer.uninstall())
        elif choice == '4':
            print(installer.logs())
        elif choice == '5':
            ok, message = installer.control('restart')
            print(('نجح: ' if ok else 'فشل: ') + message)
        elif choice == '6':
            print('إلى اللقاء')
            return 0
        else:
            print('اختيار غير صحيح')
        print()


if __name__ == '__main__':
    sys.exit(main())
