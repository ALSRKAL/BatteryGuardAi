#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نظام التحسين التلقائي المتكرر الذكي"""

import sys
import os
import logging
import psutil
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json

logger = logging.getLogger('BatteryGuard')

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')


class AutoOptimizer:
    """محسّن تلقائي ذكي يعمل بالخلفية"""
    
    def __init__(self, optimizer, ai_engine=None):
        self.optimizer = optimizer
        self.ai_engine = ai_engine
        self.is_running = False
        self.thread = None
        
        # إعدادات التحسين التلقائي
        self.auto_optimize_enabled = False
        self.optimization_mode = 'on_demand'  # 'continuous', 'on_demand', 'scheduled'
        self.optimization_interval = 300  # 5 دقائق افتراضياً
        self.last_optimization_time = None
        
        # عتبات التحسين الذكية
        self.thresholds = {
            'cpu_percent': 70,
            'memory_percent': 75,
            'disk_percent': 85,
            'process_count': 200,
            'network_connections': 100,
            'power_draw': 15.0  # واط
        }
        
        # إحصائيات التحسين
        self.optimization_count = 0
        self.total_power_saved = 0
        self.optimization_history = []
        self.system_health_score = 100
        
        # حالة النظام
        self.system_status = {}
        self.needs_optimization = False
        self.optimization_priority = 0  # 0-10
        
        # تهيئة عداد CPU (القراءة الأولى لـ cpu_percent(interval=None) تعيد 0)
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass
        
        # تحميل الإعدادات
        self._load_settings()
    
    def start(self):
        """بدء التحسين التلقائي"""
        if self.is_running:
            logger.warning("التحسين التلقائي يعمل بالفعل")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._optimization_loop, daemon=True)
        self.thread.start()
        logger.info("تم بدء التحسين التلقائي الذكي")
    
    def stop(self):
        """إيقاف التحسين التلقائي"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("تم إيقاف التحسين التلقائي")
    
    def _optimization_loop(self):
        """حلقة التحسين الرئيسية"""
        logger.info(f"بدء حلقة التحسين - الوضع: {self.optimization_mode}")
        
        while self.is_running:
            try:
                # قياس حالة النظام
                self._measure_system_status()
                
                # تحديد الحاجة للتحسين
                self._analyze_optimization_need()
                
                # تنفيذ التحسين حسب الوضع
                if self.optimization_mode == 'continuous':
                    # تحسين مستمر كل فترة
                    if self._should_optimize_continuous():
                        self._perform_optimization('continuous')
                
                elif self.optimization_mode == 'on_demand':
                    # تحسين عند الحاجة فقط
                    if self.needs_optimization:
                        self._perform_optimization('on_demand')
                
                elif self.optimization_mode == 'scheduled':
                    # تحسين مجدول
                    if self._should_optimize_scheduled():
                        self._perform_optimization('scheduled')
                
                # انتظار قبل الفحص التالي
                time.sleep(30)  # فحص كل 30 ثانية
                
            except Exception as e:
                logger.error(f"خطأ في حلقة التحسين: {e}")
                time.sleep(60)
    
    def _measure_system_status(self):
        """قياس حالة النظام الحالية"""
        try:
            self.system_status = {
                # قراءة غير مانعة (interval=1 كانت تحجب الخيط ثانية كاملة)
                'cpu_percent': psutil.cpu_percent(interval=None),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'process_count': len(psutil.pids()),
                'network_connections': len(psutil.net_connections()),
                'timestamp': datetime.now().isoformat()
            }
            
            # قياس استهلاك الطاقة
            try:
                battery = psutil.sensors_battery()
                if battery:
                    self.system_status['battery_percent'] = battery.percent
                    self.system_status['is_charging'] = battery.power_plugged
                    
                    # تقدير استهلاك الطاقة
                    if hasattr(battery, 'power_plugged') and not battery.power_plugged:
                        # تقدير تقريبي بناءً على استخدام CPU والذاكرة
                        cpu_power = self.system_status['cpu_percent'] * 0.15
                        memory_power = self.system_status['memory_percent'] * 0.05
                        self.system_status['power_draw'] = cpu_power + memory_power + 5
                    else:
                        self.system_status['power_draw'] = 0
            except:
                self.system_status['battery_percent'] = 50
                self.system_status['is_charging'] = False
                self.system_status['power_draw'] = 0
            
            # حساب درجة صحة النظام
            self._calculate_system_health()
            
        except Exception as e:
            logger.error(f"خطأ في قياس حالة النظام: {e}")
    
    def _calculate_system_health(self):
        """حساب درجة صحة النظام (0-100)"""
        try:
            health = 100
            
            # خصم نقاط بناءً على الاستخدام
            cpu = self.system_status.get('cpu_percent', 0)
            if cpu > 80:
                health -= 20
            elif cpu > 60:
                health -= 10
            elif cpu > 40:
                health -= 5
            
            memory = self.system_status.get('memory_percent', 0)
            if memory > 85:
                health -= 20
            elif memory > 70:
                health -= 10
            elif memory > 50:
                health -= 5
            
            disk = self.system_status.get('disk_percent', 0)
            if disk > 90:
                health -= 15
            elif disk > 80:
                health -= 8
            
            processes = self.system_status.get('process_count', 0)
            if processes > 250:
                health -= 10
            elif processes > 200:
                health -= 5
            
            power = self.system_status.get('power_draw', 0)
            if power > 20:
                health -= 15
            elif power > 15:
                health -= 8
            
            self.system_health_score = max(0, health)
            self.system_status['health_score'] = self.system_health_score
            
        except Exception as e:
            logger.error(f"خطأ في حساب صحة النظام: {e}")
            self.system_health_score = 50
    
    def _analyze_optimization_need(self):
        """تحليل الحاجة للتحسين"""
        try:
            self.needs_optimization = False
            self.optimization_priority = 0
            reasons = []
            
            # فحص العتبات
            cpu = self.system_status.get('cpu_percent', 0)
            if cpu > self.thresholds['cpu_percent']:
                self.needs_optimization = True
                self.optimization_priority += 3
                reasons.append(f"CPU عالي ({cpu:.1f}%)")
            
            memory = self.system_status.get('memory_percent', 0)
            if memory > self.thresholds['memory_percent']:
                self.needs_optimization = True
                self.optimization_priority += 3
                reasons.append(f"ذاكرة عالية ({memory:.1f}%)")
            
            disk = self.system_status.get('disk_percent', 0)
            if disk > self.thresholds['disk_percent']:
                self.needs_optimization = True
                self.optimization_priority += 2
                reasons.append(f"قرص ممتلئ ({disk:.1f}%)")
            
            processes = self.system_status.get('process_count', 0)
            if processes > self.thresholds['process_count']:
                self.needs_optimization = True
                self.optimization_priority += 2
                reasons.append(f"عمليات كثيرة ({processes})")
            
            power = self.system_status.get('power_draw', 0)
            if power > self.thresholds['power_draw']:
                self.needs_optimization = True
                self.optimization_priority += 2
                reasons.append(f"استهلاك طاقة عالي ({power:.1f}W)")
            
            # فحص صحة النظام
            if self.system_health_score < 60:
                self.needs_optimization = True
                self.optimization_priority += 2
                reasons.append(f"صحة النظام منخفضة ({self.system_health_score}%)")
            
            # استخدام الذكاء الاصطناعي للتحليل
            if self.ai_engine and self.needs_optimization:
                ai_priority = self._get_ai_priority()
                self.optimization_priority += ai_priority
                if ai_priority > 0:
                    reasons.append("توصية الذكاء الاصطناعي")
            
            # تحديد الأولوية النهائية
            self.optimization_priority = min(10, self.optimization_priority)
            
            if self.needs_optimization:
                logger.info(f"يحتاج النظام للتحسين - الأولوية: {self.optimization_priority}/10")
                logger.info(f"الأسباب: {', '.join(reasons)}")
            
        except Exception as e:
            logger.error(f"خطأ في تحليل الحاجة للتحسين: {e}")
    
    def _get_ai_priority(self) -> int:
        """الحصول على أولوية التحسين من الذكاء الاصطناعي"""
        try:
            if not self.ai_engine:
                return 0
            
            battery_percent = self.system_status.get('battery_percent', 50)
            is_charging = self.system_status.get('is_charging', False)
            
            # الأولوية من الشدّة المهيكلة، لا من نص الرسالة
            if hasattr(self.ai_engine, 'get_advice'):
                advice = self.ai_engine.get_advice(
                    {'percent': battery_percent, 'is_charging': is_charging,
                     'reporting': True})
                weights = {'critical': 2, 'warning': 1}
                return min(3, sum(weights.get(item.severity, 0) for item in advice))

            # مسار احتياطي: عدد توصيات التحسين المتاحة
            recommendations = self.ai_engine.get_optimization_recommendations(
                battery_percent, is_charging
            )
            return min(3, len(recommendations))
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على أولوية الذكاء الاصطناعي: {e}")
            return 0
    
    def _should_optimize_continuous(self) -> bool:
        """فحص إذا كان يجب التحسين في الوضع المستمر"""
        if not self.last_optimization_time:
            return True
        
        elapsed = (datetime.now() - self.last_optimization_time).total_seconds()
        return elapsed >= self.optimization_interval
    
    def _should_optimize_scheduled(self) -> bool:
        """فحص إذا كان يجب التحسين في الوضع المجدول"""
        # تحسين في أوقات محددة (مثلاً كل ساعة في الدقيقة 0)
        now = datetime.now()
        if now.minute == 0 and now.second < 30:
            if not self.last_optimization_time:
                return True
            
            elapsed = (now - self.last_optimization_time).total_seconds()
            return elapsed >= 3600  # ساعة واحدة على الأقل
        
        return False
    
    def _perform_optimization(self, trigger_mode: str):
        """تنفيذ التحسين"""
        try:
            logger.info(f"بدء التحسين التلقائي - الوضع: {trigger_mode}, الأولوية: {self.optimization_priority}")
            
            # تحديد مستوى التحسين بناءً على الأولوية
            if self.optimization_priority >= 7:
                optimization_level = 'intelligent'
            elif self.optimization_priority >= 4:
                optimization_level = 'advanced'
            else:
                optimization_level = 'basic'
            
            # تنفيذ التحسين
            results = self.optimizer.optimize_battery(
                use_cached_password=True,
                optimization_mode=optimization_level
            )
            
            # تسجيل النتائج
            self.optimization_count += 1
            self.last_optimization_time = datetime.now()
            
            if results.get('success'):
                power_saved = results.get('power_saved', 0)
                self.total_power_saved += power_saved
                
                # حفظ في السجل
                record = {
                    'timestamp': self.last_optimization_time.isoformat(),
                    'trigger_mode': trigger_mode,
                    'optimization_level': optimization_level,
                    'priority': self.optimization_priority,
                    'power_saved': power_saved,
                    'system_health_before': self.system_health_score,
                    'actions_count': len(results.get('actions', [])),
                    'success': True
                }
                
                self.optimization_history.append(record)
                
                # الاحتفاظ بآخر 100 تحسين
                if len(self.optimization_history) > 100:
                    self.optimization_history = self.optimization_history[-100:]
                
                logger.info(f"التحسين ناجح - توفير: {power_saved:.1f}% طاقة")
                
                # إعادة قياس صحة النظام
                time.sleep(2)
                self._measure_system_status()
                record['system_health_after'] = self.system_health_score
                
                # حفظ الإعدادات
                self._save_settings()
            else:
                logger.error(f"فشل التحسين: {results.get('errors', [])}")
            
        except Exception as e:
            logger.error(f"خطأ في تنفيذ التحسين: {e}")
    
    def set_optimization_mode(self, mode: str):
        """تعيين وضع التحسين"""
        if mode in ['continuous', 'on_demand', 'scheduled']:
            self.optimization_mode = mode
            logger.info(f"تم تغيير وضع التحسين إلى: {mode}")
            self._save_settings()
        else:
            logger.error(f"وضع تحسين غير صحيح: {mode}")
    
    def set_optimization_interval(self, interval: int):
        """تعيين فترة التحسين (بالثواني)"""
        if interval >= 60:  # دقيقة واحدة على الأقل
            self.optimization_interval = interval
            logger.info(f"تم تغيير فترة التحسين إلى: {interval} ثانية")
            self._save_settings()
    
    def set_threshold(self, key: str, value: float):
        """تعيين عتبة معينة"""
        if key in self.thresholds:
            self.thresholds[key] = value
            logger.info(f"تم تغيير عتبة {key} إلى: {value}")
            self._save_settings()
    
    def get_statistics(self) -> Dict:
        """الحصول على إحصائيات التحسين"""
        return {
            'enabled': self.auto_optimize_enabled,
            'mode': self.optimization_mode,
            'interval': self.optimization_interval,
            'optimization_count': self.optimization_count,
            'total_power_saved': self.total_power_saved,
            'average_power_saved': self.total_power_saved / max(1, self.optimization_count),
            'system_health_score': self.system_health_score,
            'last_optimization': self.last_optimization_time.isoformat() if self.last_optimization_time else None,
            'needs_optimization': self.needs_optimization,
            'optimization_priority': self.optimization_priority,
            'thresholds': self.thresholds,
            'recent_history': self.optimization_history[-10:]
        }
    
    def get_system_status(self) -> Dict:
        """الحصول على حالة النظام الحالية"""
        return self.system_status.copy()
    
    def _load_settings(self):
        """تحميل الإعدادات من مجلد بيانات المستخدم (قراءة ذرية)"""
        try:
            from storage import load_json_data
            data = load_json_data('auto_optimizer_settings.json', None)
            if isinstance(data, dict):
                self.auto_optimize_enabled = data.get('enabled', False)
                self.optimization_mode = data.get('mode', 'on_demand')
                self.optimization_interval = data.get('interval', 300)
                self.thresholds = {**self.thresholds, **data.get('thresholds', {})}
                self.optimization_count = data.get('optimization_count', 0)
                self.total_power_saved = data.get('total_power_saved', 0)
                logger.info("تم تحميل إعدادات التحسين التلقائي")
        except Exception as e:
            logger.error(f"خطأ في تحميل إعدادات التحسين: {e}")
    
    def _save_settings(self):
        """حفظ الإعدادات في مجلد بيانات المستخدم (كتابة ذرية)"""
        try:
            from storage import save_json_data
            save_json_data('auto_optimizer_settings.json', {
                'enabled': self.auto_optimize_enabled,
                'mode': self.optimization_mode,
                'interval': self.optimization_interval,
                'thresholds': self.thresholds,
                'optimization_count': self.optimization_count,
                'total_power_saved': self.total_power_saved,
                'last_updated': datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error(f"خطأ في حفظ إعدادات التحسين: {e}")
