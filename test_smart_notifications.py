#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار نظام الإشعارات الذكي المتقدم"""

import time
import logging
from notification_manager import SmartNotificationManager

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('BatteryGuard')

def test_smart_notifications():
    """اختبار شامل لنظام الإشعارات الذكي"""
    print("🔔 اختبار نظام الإشعارات الذكي المتقدم...")
    
    # إنشاء مدير الإشعارات
    notif_manager = SmartNotificationManager()
    
    print(f"✅ تم تهيئة النظام - الطريقة: {notif_manager.notification_method}")
    print(f"🔊 الأصوات متاحة: {'نعم' if notif_manager.sound_enabled else 'لا'}")
    
    # اختبار الإشعارات الأساسية
    print("\n📢 اختبار الإشعارات الأساسية:")
    
    # إشعار عادي
    notif_manager.send_notification(
        title="🔋 اختبار الإشعار العادي",
        message="هذا اختبار للإشعار العادي مع صوت",
        urgency='normal',
        notification_type='test',
        play_sound=True
    )
    time.sleep(2)
    
    # إشعار حرج
    notif_manager.send_notification(
        title="🚨 اختبار الإشعار الحرج",
        message="هذا اختبار للإشعار الحرج مع صوت قوي",
        urgency='critical',
        notification_type='test_critical',
        play_sound=True,
        persistent=True
    )
    time.sleep(3)
    
    # اختبار تنبيهات البطارية
    print("\n🔋 اختبار تنبيهات البطارية:")
    
    # بطارية منخفضة
    notif_manager.send_battery_threshold_alert(15, False, 85)
    time.sleep(2)
    
    # بطارية حرجة
    notif_manager.send_battery_threshold_alert(8, False, 85)
    time.sleep(2)
    
    # شحن كامل
    notif_manager.send_battery_threshold_alert(95, True, 85)
    time.sleep(2)
    
    # اختبار تغيير حالة الشاحن
    print("\n🔌 اختبار تنبيهات الشاحن:")
    
    # توصيل الشاحن
    notif_manager.send_charger_status_alert(False, True, 25)
    time.sleep(2)
    
    # فصل الشاحن
    notif_manager.send_charger_status_alert(True, False, 85)
    time.sleep(2)
    
    # اختبار التنبيهات الذكية
    print("\n🤖 اختبار التنبيهات الذكية:")
    
    # استهلاك مرتفع
    notif_manager.send_smart_usage_alert({
        'high_drain_detected': True,
        'temperature': 50,
        'unhealthy_charging_pattern': False
    })
    time.sleep(2)
    
    # درجة حرارة مرتفعة
    notif_manager.send_smart_usage_alert({
        'high_drain_detected': False,
        'temperature': 48,
        'unhealthy_charging_pattern': False
    })
    time.sleep(2)
    
    # اختبار تنبيهات الذكاء الاصطناعي
    print("\n🧠 اختبار تنبيهات الذكاء الاصطناعي:")
    
    # تدهور البطارية
    notif_manager.send_ai_smart_alert({
        'type': 'battery_degradation',
        'confidence': 85,
        'message': 'تم اكتشاف تدهور في أداء البطارية'
    })
    time.sleep(2)
    
    # وقت الشحن الأمثل
    notif_manager.send_ai_smart_alert({
        'type': 'optimal_charge_time',
        'confidence': 90,
        'message': 'الآن وقت مثالي للشحن بناءً على أنماطك'
    })
    time.sleep(2)
    
    # اختبار التذكيرات
    print("\n⏰ اختبار التذكيرات:")
    
    # تذكير بطارية منخفضة (لمدة 10 ثواني)
    def battery_low_condition():
        return True  # محاكاة بطارية منخفضة
    
    notif_manager.start_reminder(
        'test_battery_low',
        battery_low_condition,
        {
            'title': '🔋 تذكير اختبار',
            'message': 'هذا تذكير اختبار للبطارية المنخفضة',
            'urgency': 'normal',
            'play_sound': True
        },
        interval=3  # كل 3 ثواني
    )
    
    print("⏳ تشغيل التذكير لمدة 10 ثواني...")
    time.sleep(10)
    
    # إيقاف التذكير
    notif_manager.stop_reminder('test_battery_low')
    print("⏹️ تم إيقاف التذكير")
    
    # عرض الإحصائيات
    print("\n📊 إحصائيات الإشعارات:")
    stats = notif_manager.get_advanced_statistics()
    
    print(f"   • إجمالي الإشعارات المرسلة: {stats['total_sent']}")
    print(f"   • إجمالي الإشعارات المحجوبة: {stats['total_suppressed']}")
    print(f"   • إجمالي التذكيرات: {stats['reminders_sent']}")
    print(f"   • إجمالي الأصوات: {stats['sounds_played']}")
    print(f"   • التذكيرات النشطة: {len(stats['active_reminders'])}")
    
    print("\n📈 إحصائيات حسب النوع:")
    for notification_type, count in stats['by_type'].items():
        print(f"   • {notification_type}: {count}")
    
    print("\n🎯 إحصائيات حسب الأولوية:")
    for priority, count in stats['by_priority'].items():
        print(f"   • {priority}: {count}")
    
    print("\n⚙️ حدود البطارية الحالية:")
    thresholds = stats['battery_thresholds']
    for threshold, value in thresholds.items():
        print(f"   • {threshold}: {value}%")
    
    print("\n🤖 حالة التنبيهات الذكية:")
    smart_alerts = stats['smart_alerts_status']
    for alert_type, enabled in smart_alerts.items():
        status = "مفعّل" if enabled else "معطّل"
        print(f"   • {alert_type}: {status}")
    
    print("\n🎉 انتهى اختبار نظام الإشعارات الذكي!")
    print("💡 تحقق من الإشعارات التي ظهرت على شاشتك والأصوات التي تم تشغيلها")

if __name__ == "__main__":
    test_smart_notifications()