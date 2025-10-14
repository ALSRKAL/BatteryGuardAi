#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار الأصوات في نظام الإشعارات"""

import sys
import time
import logging
from notification_manager import SmartNotificationManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_all_sounds():
    """اختبار جميع الأصوات"""
    print("=" * 60)
    print("🔊 اختبار الأصوات - BatteryGuard Pro")
    print("=" * 60)
    
    # إنشاء مدير الإشعارات
    notif_manager = SmartNotificationManager()
    
    # التأكد من تفعيل الأصوات
    notif_manager.sound_enabled = True
    
    print("\n📋 الأصوات المتاحة:")
    for sound_type, sound_file in notif_manager.sound_files.items():
        print(f"   {sound_type}: {sound_file}")
    
    # اختبار كل صوت
    sounds_to_test = [
        ('critical', '🚨 صوت حرج - بطارية منخفضة جداً'),
        ('warning', '⚠️ صوت تحذير - بطارية منخفضة'),
        ('info', 'ℹ️ صوت معلومات - إشعارات عامة'),
        ('success', '✅ صوت نجاح - اكتمال الشحن'),
        ('optimization', '🚀 صوت تحسين - عمليات التحسين')
    ]
    
    print("\n" + "=" * 60)
    print("🎵 بدء اختبار الأصوات...")
    print("=" * 60)
    
    for sound_type, description in sounds_to_test:
        print(f"\n▶️  {description}")
        print(f"   النوع: {sound_type}")
        print(f"   الملف: {notif_manager.sound_files.get(sound_type, 'غير موجود')}")
        
        # تشغيل الصوت
        notif_manager.play_sound(sound_type)
        
        # انتظار 2 ثانية بين الأصوات
        time.sleep(2)
    
    print("\n" + "=" * 60)
    print("✅ اكتمل اختبار الأصوات")
    print("=" * 60)


def test_notifications_with_sounds():
    """اختبار الإشعارات مع الأصوات"""
    print("\n" + "=" * 60)
    print("📢 اختبار الإشعارات مع الأصوات")
    print("=" * 60)
    
    notif_manager = SmartNotificationManager()
    notif_manager.sound_enabled = True
    
    # اختبار إشعارات مختلفة
    notifications = [
        {
            'title': '🚨 تحذير حرج',
            'message': 'البطارية 5%! وصّل الشاحن فوراً',
            'urgency': 'critical',
            'type': 'battery_critical'
        },
        {
            'title': '⚠️ بطارية منخفضة',
            'message': 'البطارية 15% - يُنصح بالشحن',
            'urgency': 'high',
            'type': 'battery_low'
        },
        {
            'title': 'ℹ️ معلومة',
            'message': 'البطارية في المستوى الأمثل 60%',
            'urgency': 'normal',
            'type': 'battery_info'
        },
        {
            'title': '✅ اكتمل الشحن',
            'message': 'البطارية 95% - يمكن فصل الشاحن',
            'urgency': 'normal',
            'type': 'battery_full'
        },
        {
            'title': '🚀 تحسين ناجح',
            'message': 'تم التحسين بنجاح! توفير: 15.3% طاقة',
            'urgency': 'normal',
            'type': 'optimization'
        }
    ]
    
    for i, notif in enumerate(notifications, 1):
        print(f"\n{i}. {notif['title']}")
        print(f"   {notif['message']}")
        
        notif_manager.send_notification(
            title=notif['title'],
            message=notif['message'],
            urgency=notif['urgency'],
            notification_type=notif['type'],
            play_sound=True
        )
        
        time.sleep(3)
    
    print("\n" + "=" * 60)
    print("✅ اكتمل اختبار الإشعارات")
    print("=" * 60)


def test_optimization_notifications():
    """اختبار إشعارات التحسين"""
    print("\n" + "=" * 60)
    print("🚀 اختبار إشعارات التحسين")
    print("=" * 60)
    
    notif_manager = SmartNotificationManager()
    notif_manager.sound_enabled = True
    
    # اختبار أنواع مختلفة من إشعارات التحسين
    optimization_types = [
        ('started', 0),
        ('completed', 12.5),
        ('auto_started', 0),
        ('auto_completed', 18.7)
    ]
    
    for opt_type, power_saved in optimization_types:
        print(f"\n▶️  نوع التحسين: {opt_type}")
        if power_saved > 0:
            print(f"   الطاقة الموفرة: {power_saved}%")
        
        notif_manager.send_optimization_notification(opt_type, power_saved)
        time.sleep(3)
    
    print("\n" + "=" * 60)
    print("✅ اكتمل اختبار إشعارات التحسين")
    print("=" * 60)


def main():
    """الدالة الرئيسية"""
    print("\n🎵 اختبار نظام الأصوات - BatteryGuard Pro\n")
    
    try:
        # اختبار 1: الأصوات فقط
        test_all_sounds()
        
        # انتظار قليلاً
        time.sleep(2)
        
        # اختبار 2: الإشعارات مع الأصوات
        response = input("\n❓ هل تريد اختبار الإشعارات مع الأصوات؟ (y/n): ")
        if response.lower() == 'y':
            test_notifications_with_sounds()
        
        # اختبار 3: إشعارات التحسين
        response = input("\n❓ هل تريد اختبار إشعارات التحسين؟ (y/n): ")
        if response.lower() == 'y':
            test_optimization_notifications()
        
        print("\n" + "=" * 60)
        print("🎉 اكتملت جميع الاختبارات بنجاح!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ تم إيقاف الاختبار بواسطة المستخدم")
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
