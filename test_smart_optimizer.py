#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار سريع للمحسن الذكي"""

import sys
import logging
from battery_optimizer import BatteryOptimizer
from battery_ai import BatteryAI

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('BatteryGuard')

def test_smart_optimizer():
    """اختبار المحسن الذكي"""
    print("🤖 اختبار المحسن الذكي المتقدم...")
    
    # إنشاء محرك الذكاء الاصطناعي
    ai_engine = BatteryAI()
    
    # إنشاء المحسن مع الذكاء الاصطناعي
    optimizer = BatteryOptimizer(ai_engine)
    
    # تشغيل التحسين الذكي
    print("🔍 بدء التحسين الذكي...")
    result = optimizer.optimize_battery(optimization_mode='intelligent')
    
    # عرض النتائج
    print("\n" + "="*60)
    print("🎯 نتائج التحسين الذكي:")
    print("="*60)
    
    if result['success']:
        print(f"✅ نجح التحسين!")
        print(f"🧠 درجة الذكاء: {result.get('intelligence_score', 0)}%")
        print(f"📊 تحسين متوقع: {result.get('predicted_improvement', 0)}%")
        print(f"⚡ توفير فعلي: {result.get('power_saved', 0):.1f}%")
        print(f"🔧 عدد التحسينات: {len(result.get('actions', []))}")
        
        # عرض التوصيات الذكية
        ai_recs = result.get('ai_recommendations', [])
        if ai_recs:
            print(f"\n🤖 توصيات الذكاء الاصطناعي:")
            for i, rec in enumerate(ai_recs, 1):
                print(f"   {i}. {rec}")
        
        # عرض التحسينات المطبقة
        print(f"\n🚀 التحسينات المطبقة:")
        for action in result.get('actions', []):
            status = "✅" if action.get('success', True) else "❌"
            power_saved = action.get('power_saved', 0)
            print(f"   {status} {action['name']}: {action['details']} (~{power_saved:.1f}%)")
        
        # عرض التحسينات الشخصية
        personalized = result.get('personalized_actions', [])
        if personalized:
            print(f"\n🎯 تحسينات شخصية:")
            for action in personalized:
                print(f"   ⭐ {action['name']}: {action['details']}")
    
    else:
        print("❌ فشل التحسين")
        errors = result.get('errors', [])
        if errors:
            print(f"الأخطاء: {', '.join(errors)}")
    
    print("\n" + "="*60)
    
    # عرض إحصائيات المحسن
    stats = optimizer.get_optimization_stats()
    print("📊 إحصائيات المحسن:")
    print(f"   • إجمالي التحسينات: {stats['total_optimizations']}")
    print(f"   • معدل النجاح: {stats['success_rate']}%")
    print(f"   • إجمالي الطاقة الموفرة: {stats['total_power_saved']:.1f}%")
    print(f"   • متوسط التوفير: {stats['average_power_saved']:.1f}%")
    
    print("\n🎉 انتهى الاختبار!")

if __name__ == "__main__":
    test_smart_optimizer()