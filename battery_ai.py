#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محرك الذكاء الاصطناعي المتقدم - الجيل الثاني"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics
import math

logger = logging.getLogger('BatteryGuard')


class BatteryAI:
    """محرك الذكاء الاصطناعي المتقدم - الجيل الرابع"""
    
    def __init__(self):
        self.usage_history: List[Dict] = []
        self.learning_data = self.load_learning_data()
        self.predictions = {}
        self.charge_cycles = []
        self.discharge_cycles = []
        self.last_analysis_time = None
        self.behavior_model = {}
        self.anomaly_detector = AnomalyDetector()
        self.pattern_predictor = PatternPredictor()
        self.learning_rate = 0.1
        self.confidence_scores = {}
        self.prediction_accuracy = []
        self.adaptive_thresholds = {}
        
        # ميزات متقدمة جديدة
        self.battery_degradation_model = {}  # نموذج تدهور البطارية
        self.optimal_charge_windows = []  # نوافذ الشحن المثالية
        self.usage_forecasting = {}  # التنبؤ بالاستخدام المستقبلي
        self.health_tracking = []  # تتبع الصحة عبر الزمن
        self.temperature_correlation = {}  # علاقة الحرارة بالأداء
        self.learning_progress = 0  # تقدم التعلم (0-100%)
        self.ai_maturity_level = 'beginner'  # مستوى نضج الذكاء
        self.personalization_score = 0  # درجة التخصيص
        self.optimization_suggestions = []  # اقتراحات التحسين المتقدمة
        
        # تحسينات جديدة للتحسين الذكي
        self.optimization_intelligence = {}  # ذكاء التحسين
        self.smart_recommendations = []  # توصيات ذكية للتحسين
        
    def load_learning_data(self) -> Dict:
        """تحميل بيانات التعلم المحفوظة"""
        try:
            if Path('battery_ai_data.json').exists():
                with open('battery_ai_data.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # تحميل سجل الاستخدام
                    if 'usage_history' in data:
                        self.usage_history = data['usage_history'][-1000:]
                    
                    # دمج البيانات المحفوظة مع القيم الافتراضية
                    default_data = self._get_default_learning_data()
                    
                    # تحديث القيم الافتراضية بالبيانات المحفوظة
                    for key, value in data.items():
                        if key != 'usage_history':  # تم تحميله بالفعل
                            default_data[key] = value
                    
                    logger.info(f"تم تحميل بيانات AI بنجاح - الأنماط: {len(default_data.get('patterns', []))}, التوصيات: {len(default_data.get('recommendations', []))}")
                    return default_data
        except Exception as e:
            logger.error(f"خطأ في تحميل بيانات AI: {e}")
        
        return self._get_default_learning_data()
    
    def _get_default_learning_data(self) -> Dict:
        """البيانات الافتراضية المحسّنة"""
        return {
            'patterns': [],
            'recommendations': [],
            'efficiency_score': 100,
            'health_score': 100,
            'heavy_usage_hours': [],
            'optimal_charge_times': [],
            'average_drain_rate': 0,
            'average_charge_rate': 0,
            'peak_drain_rate': 0,
            'usage_statistics': {},
            'behavior_profile': {},
            'anomalies_detected': [],
            'charge_cycle_count': 0,
            'total_charge_time': 0,
            'total_discharge_time': 0,
            'battery_age_estimate': 0,
            'learning_iterations': 0,
            'prediction_accuracy_history': [],
            'user_behavior_fingerprint': {},
            'seasonal_patterns': {},
            'weekly_patterns': {},
            'correlation_matrix': {},
            
            # بيانات متقدمة جديدة
            'degradation_rate': 0,  # معدل التدهور
            'optimal_soc_range': [40, 80],  # النطاق الأمثل لحالة الشحن
            'charge_efficiency': 100,  # كفاءة الشحن
            'discharge_efficiency': 100,  # كفاءة التفريغ
            'temperature_impact': {},  # تأثير الحرارة
            'usage_intensity_score': 0,  # درجة كثافة الاستخدام
            'battery_longevity_score': 100,  # درجة طول عمر البطارية
            'smart_charging_enabled': False,  # الشحن الذكي
            'learning_milestones': [],  # معالم التعلم
            'ai_confidence_level': 0,  # مستوى ثقة الذكاء
            'personalization_level': 0,  # مستوى التخصيص
            'optimization_history': [],  # تاريخ التحسينات
            'predictive_maintenance': {},  # الصيانة التنبؤية
        }

    def save_learning_data(self):
        """حفظ بيانات التعلم بشكل دائم"""
        try:
            # تحديث سجل الاستخدام
            self.learning_data['usage_history'] = self.usage_history[-1000:]
            self.learning_data['last_updated'] = datetime.now().isoformat()
            
            # حفظ البيانات في ملف JSON
            with open('battery_ai_data.json', 'w', encoding='utf-8') as f:
                json.dump(self.learning_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"تم حفظ بيانات AI - الأنماط: {len(self.learning_data.get('patterns', []))}, درجة الكفاءة: {self.learning_data.get('efficiency_score', 0)}")
        except Exception as e:
            logger.error(f"خطأ في حفظ بيانات AI: {e}")
    
    def analyze_usage_pattern(self, battery_data: Dict):
        """تحليل متقدم لنمط الاستخدام مع التعلم المستمر"""
        current_time = datetime.now()
        
        usage_entry = {
            'timestamp': current_time.isoformat(),
            'battery_percent': battery_data['percent'],
            'is_charging': battery_data['is_charging'],
            'power_draw': battery_data.get('power_draw', 0),
            'voltage': battery_data.get('voltage', 0),
            'current': battery_data.get('current', 0),
            'hour': current_time.hour,
            'day_of_week': current_time.weekday(),
            'is_weekend': current_time.weekday() >= 5,
            'minute': current_time.minute,
            'week_of_year': current_time.isocalendar()[1],
            'month': current_time.month
        }
        
        # التحقق من دقة التنبؤات السابقة
        self._validate_predictions(usage_entry)
        
        self.usage_history.append(usage_entry)
        
        if len(self.usage_history) > 3000:
            self.usage_history = self.usage_history[-3000:]
        
        # تحليل فوري للتغيرات المفاجئة
        if len(self.usage_history) >= 2:
            self._detect_instant_anomalies(usage_entry)
        
        # تعلم تكيفي مستمر
        if len(self.usage_history) % 10 == 0:
            self._adaptive_learning()
        
        # تحليل عميق دوري
        if len(self.usage_history) % 30 == 0:
            self._perform_deep_analysis()
        
        # حفظ دوري أكثر تكراراً لضمان عدم فقدان البيانات
        if len(self.usage_history) % 50 == 0:
            self.save_learning_data()
    
    def _detect_instant_anomalies(self, current_entry: Dict):
        """كشف الشذوذ الفوري"""
        if len(self.usage_history) < 10:
            return
        
        try:
            recent = self.usage_history[-10:]
            power_values = [e.get('power_draw', 0) for e in recent if e.get('power_draw', 0) > 0]
            
            if not power_values:
                return
            
            avg_power = statistics.mean(power_values)
            current_power = current_entry.get('power_draw', 0)
            
            # كشف استهلاك غير طبيعي
            if current_power > avg_power * 2 and current_power > 10:
                anomaly = {
                    'type': 'high_power_consumption',
                    'timestamp': current_entry['timestamp'],
                    'value': current_power,
                    'average': avg_power,
                    'message': f'استهلاك طاقة مرتفع: {current_power:.1f}W (المتوسط: {avg_power:.1f}W)'
                }
                self.anomaly_detector.add_anomaly(anomaly)
        except Exception as e:
            logger.debug(f"خطأ في كشف الشذوذ: {e}")
    
    def _perform_deep_analysis(self):
        """تحليل عميق شامل"""
        if len(self.usage_history) < 50:
            return
        
        # 1. تحليل معدلات الشحن والتفريغ المتقدم
        self._analyze_advanced_rates()
        
        # 2. تحليل الأنماط الزمنية المعقدة
        self._analyze_complex_time_patterns()
        
        # 3. بناء نموذج السلوك
        self._build_behavior_model()
        
        # 4. حساب درجات الصحة والكفاءة
        self._calculate_health_efficiency_scores()
        
        # 5. اكتشاف الأنماط المتكررة المتقدمة
        self._detect_advanced_patterns()
        
        # 6. التنبؤ بالمستقبل
        self._predict_future_behavior()
        
        # 7. تحليل دورات الشحن
        self._analyze_charge_cycles()
        
        # 8. تحليل تدهور البطارية (جديد)
        self._analyze_battery_degradation()
        
        # 9. إيجاد نوافذ الشحن المثالية (جديد)
        self._find_optimal_charge_windows()
        
        # 10. التنبؤ بالاستخدام المستقبلي (جديد)
        self._forecast_usage()
        
        # 11. تتبع الصحة عبر الزمن (جديد)
        self._track_health_over_time()
        
        # 12. توليد اقتراحات التحسين (جديد)
        self._generate_optimization_suggestions()
        
        # 13. حساب درجة التخصيص (جديد)
        self._calculate_personalization_score()
        
        self.last_analysis_time = datetime.now()
        
        # حفظ البيانات بعد التحليل العميق
        self.save_learning_data()
        
        logger.info("تم إجراء تحليل عميق متقدم للبيانات وحفظها")
    
    def _analyze_advanced_rates(self):
        """تحليل متقدم للمعدلات"""
        drain_rates = []
        charge_rates = []
        power_levels = []
        
        for i in range(1, len(self.usage_history)):
            prev = self.usage_history[i-1]
            curr = self.usage_history[i]
            
            try:
                time_diff = (datetime.fromisoformat(curr['timestamp']) - 
                            datetime.fromisoformat(prev['timestamp'])).total_seconds() / 60
                
                if 0 < time_diff < 30:
                    percent_diff = curr['battery_percent'] - prev['battery_percent']
                    rate = abs(percent_diff) / time_diff
                    
                    if curr['is_charging'] and percent_diff > 0:
                        charge_rates.append(rate)
                    elif not curr['is_charging'] and percent_diff < 0:
                        drain_rates.append(rate)
                    
                    power = curr.get('power_draw', 0)
                    if power > 0:
                        power_levels.append(power)
            except:
                continue
        
        # حساب الإحصائيات المتقدمة
        if drain_rates:
            self.learning_data['average_drain_rate'] = statistics.mean(drain_rates)
            self.learning_data['median_drain_rate'] = statistics.median(drain_rates)
            self.learning_data['peak_drain_rate'] = max(drain_rates)
            self.learning_data['min_drain_rate'] = min(drain_rates)
            if len(drain_rates) > 1:
                self.learning_data['drain_rate_std'] = statistics.stdev(drain_rates)
        
        if charge_rates:
            self.learning_data['average_charge_rate'] = statistics.mean(charge_rates)
            self.learning_data['median_charge_rate'] = statistics.median(charge_rates)
            self.learning_data['peak_charge_rate'] = max(charge_rates)
            if len(charge_rates) > 1:
                self.learning_data['charge_rate_std'] = statistics.stdev(charge_rates)
        
        if power_levels:
            self.learning_data['average_power_draw'] = statistics.mean(power_levels)
            self.learning_data['peak_power_draw'] = max(power_levels)

    def _analyze_complex_time_patterns(self):
        """تحليل الأنماط الزمنية المعقدة"""
        hourly_data = defaultdict(lambda: {'drain': [], 'charge': [], 'power': []})
        daily_data = defaultdict(lambda: {'drain': [], 'charge': []})
        
        for i in range(1, len(self.usage_history)):
            prev = self.usage_history[i-1]
            curr = self.usage_history[i]
            
            hour = curr['hour']
            day = curr['day_of_week']
            
            time_diff = (datetime.fromisoformat(curr['timestamp']) - 
                        datetime.fromisoformat(prev['timestamp'])).total_seconds() / 60
            
            if 0 < time_diff < 30:
                percent_diff = curr['battery_percent'] - prev['battery_percent']
                
                if curr['is_charging'] and percent_diff > 0:
                    hourly_data[hour]['charge'].append(abs(percent_diff) / time_diff)
                    daily_data[day]['charge'].append(abs(percent_diff) / time_diff)
                elif not curr['is_charging'] and percent_diff < 0:
                    hourly_data[hour]['drain'].append(abs(percent_diff) / time_diff)
                    daily_data[day]['drain'].append(abs(percent_diff) / time_diff)
                
                power = curr.get('power_draw', 0)
                if power > 0:
                    hourly_data[hour]['power'].append(power)
        
        # تحديد ساعات الاستخدام المكثف (متقدم)
        heavy_hours = []
        moderate_hours = []
        light_hours = []
        
        for hour, data in hourly_data.items():
            if data['drain']:
                avg_drain = statistics.mean(data['drain'])
                if avg_drain > 1.5:
                    heavy_hours.append(hour)
                elif avg_drain > 0.8:
                    moderate_hours.append(hour)
                else:
                    light_hours.append(hour)
        
        self.learning_data['heavy_usage_hours'] = sorted(heavy_hours)
        self.learning_data['moderate_usage_hours'] = sorted(moderate_hours)
        self.learning_data['light_usage_hours'] = sorted(light_hours)
        
        # تحديد أوقات الشحن المثالية (متقدم)
        charging_patterns = defaultdict(lambda: {'count': 0, 'avg_rate': 0})
        
        for entry in self.usage_history:
            if entry['is_charging']:
                hour = entry['hour']
                charging_patterns[hour]['count'] += 1
        
        optimal_times = sorted(charging_patterns.items(), 
                              key=lambda x: x[1]['count'], reverse=True)[:5]
        self.learning_data['optimal_charge_times'] = [h for h, _ in optimal_times]
        
        # تحليل أنماط نهاية الأسبوع
        weekend_drain = []
        weekday_drain = []
        
        for entry in self.usage_history:
            if not entry['is_charging']:
                if entry['is_weekend']:
                    weekend_drain.append(entry['battery_percent'])
                else:
                    weekday_drain.append(entry['battery_percent'])
        
        if weekend_drain and weekday_drain:
            self.learning_data['weekend_usage_pattern'] = statistics.mean(weekend_drain)
            self.learning_data['weekday_usage_pattern'] = statistics.mean(weekday_drain)
    
    def _build_behavior_model(self):
        """بناء نموذج سلوك المستخدم"""
        if len(self.usage_history) < 100:
            return
        
        recent = self.usage_history[-200:]
        
        # نمط الشحن
        charge_sessions = []
        current_session = []
        
        for entry in recent:
            if entry['is_charging']:
                current_session.append(entry)
            elif current_session:
                charge_sessions.append(current_session)
                current_session = []
        
        if charge_sessions:
            avg_session_length = statistics.mean([len(s) for s in charge_sessions])
            self.behavior_model['avg_charge_session_length'] = avg_session_length
            
            # متوسط نسبة البدء والانتهاء
            start_percentages = [s[0]['battery_percent'] for s in charge_sessions if s]
            end_percentages = [s[-1]['battery_percent'] for s in charge_sessions if s]
            
            if start_percentages:
                self.behavior_model['typical_charge_start'] = statistics.mean(start_percentages)
            if end_percentages:
                self.behavior_model['typical_charge_end'] = statistics.mean(end_percentages)
        
        # نمط الاستخدام
        usage_intensity = []
        for i in range(1, len(recent)):
            if not recent[i]['is_charging']:
                time_diff = (datetime.fromisoformat(recent[i]['timestamp']) - 
                           datetime.fromisoformat(recent[i-1]['timestamp'])).total_seconds() / 60
                if 0 < time_diff < 30:
                    percent_diff = abs(recent[i]['battery_percent'] - recent[i-1]['battery_percent'])
                    usage_intensity.append(percent_diff / time_diff)
        
        if usage_intensity:
            self.behavior_model['usage_intensity'] = statistics.mean(usage_intensity)
            self.behavior_model['usage_variability'] = statistics.stdev(usage_intensity) if len(usage_intensity) > 1 else 0

    def _calculate_health_efficiency_scores(self):
        """حساب درجات الصحة والكفاءة المتقدمة"""
        if len(self.usage_history) < 100:
            return
        
        recent = self.usage_history[-200:]
        
        # عوامل الكفاءة (محسّنة)
        optimal_range = sum(1 for e in recent if 40 <= e['battery_percent'] <= 80)
        good_range = sum(1 for e in recent if 30 <= e['battery_percent'] <= 90)
        overcharge = sum(1 for e in recent if e['battery_percent'] > 90 and e['is_charging'])
        deep_discharge = sum(1 for e in recent if e['battery_percent'] < 20)
        critical_discharge = sum(1 for e in recent if e['battery_percent'] < 10)
        full_cycles = sum(1 for e in recent if e['battery_percent'] > 95 and e['is_charging'])
        
        total = len(recent)
        
        # حساب درجة الكفاءة (0-100)
        efficiency = 100
        efficiency += (optimal_range / total) * 20  # مكافأة للنطاق الأمثل
        efficiency += (good_range / total) * 10     # مكافأة للنطاق الجيد
        efficiency -= (overcharge / total) * 30     # عقوبة للشحن الزائد
        efficiency -= (deep_discharge / total) * 40 # عقوبة للتفريغ العميق
        efficiency -= (critical_discharge / total) * 60  # عقوبة شديدة
        efficiency -= (full_cycles / total) * 25    # عقوبة للدورات الكاملة
        
        self.learning_data['efficiency_score'] = max(0, min(100, int(efficiency)))
        
        # حساب درجة الصحة (0-100)
        health = 100
        
        # عوامل الصحة
        charge_cycles = self.learning_data.get('charge_cycle_count', 0)
        if charge_cycles > 0:
            health -= min(30, charge_cycles / 10)  # تأثير دورات الشحن
        
        # تأثير الشحن الزائد المتكرر
        if overcharge > total * 0.2:
            health -= 15
        
        # تأثير التفريغ العميق المتكرر
        if deep_discharge > total * 0.15:
            health -= 20
        
        # تأثير التقلبات الشديدة
        if self.behavior_model.get('usage_variability', 0) > 2:
            health -= 10
        
        self.learning_data['health_score'] = max(0, min(100, int(health)))
    
    def _detect_advanced_patterns(self):
        """اكتشاف الأنماط المتقدمة"""
        patterns = []
        
        if len(self.usage_history) < 50:
            return
        
        # نمط الشحن الليلي
        night_charging = sum(1 for e in self.usage_history 
                           if e['is_charging'] and (22 <= e['hour'] or e['hour'] <= 6))
        if night_charging > len(self.usage_history) * 0.25:
            patterns.append({
                'type': 'night_charging',
                'confidence': min(100, int(night_charging / len(self.usage_history) * 400)),
                'description': 'شحن ليلي منتظم'
            })
        
        # نمط الاستخدام المكثف
        heavy_hours = self.learning_data.get('heavy_usage_hours', [])
        if heavy_hours:
            patterns.append({
                'type': 'heavy_usage',
                'confidence': 85,
                'description': f'استخدام مكثف: {", ".join(map(str, heavy_hours))}:00',
                'hours': heavy_hours
            })
        
        # نمط الشحن السريع المتكرر
        quick_charges = sum(1 for e in self.usage_history 
                          if e['is_charging'] and e['battery_percent'] < 40)
        if quick_charges > len(self.usage_history) * 0.15:
            patterns.append({
                'type': 'quick_charging',
                'confidence': 75,
                'description': 'شحن سريع متكرر من مستويات منخفضة'
            })
        
        # نمط الشحن الجزئي (صحي)
        partial_charges = sum(1 for e in self.usage_history 
                            if e['is_charging'] and 40 <= e['battery_percent'] <= 80)
        if partial_charges > len(self.usage_history) * 0.3:
            patterns.append({
                'type': 'partial_charging',
                'confidence': 90,
                'description': 'شحن جزئي صحي (40-80%)'
            })
        
        # نمط الاستخدام المستمر
        continuous_use = 0
        for i in range(1, min(50, len(self.usage_history))):
            if not self.usage_history[-i]['is_charging']:
                continuous_use += 1
            else:
                break
        
        if continuous_use > 30:
            patterns.append({
                'type': 'continuous_use',
                'confidence': 80,
                'description': f'استخدام مستمر لـ {continuous_use} قراءة'
            })
        
        # نمط نهاية الأسبوع
        weekend_avg = self.learning_data.get('weekend_usage_pattern', 0)
        weekday_avg = self.learning_data.get('weekday_usage_pattern', 0)
        
        if weekend_avg and weekday_avg and abs(weekend_avg - weekday_avg) > 15:
            if weekend_avg > weekday_avg:
                patterns.append({
                    'type': 'weekend_heavy',
                    'confidence': 70,
                    'description': 'استخدام أكثر في نهاية الأسبوع'
                })
            else:
                patterns.append({
                    'type': 'weekday_heavy',
                    'confidence': 70,
                    'description': 'استخدام أكثر في أيام العمل'
                })
        
        self.learning_data['patterns'] = patterns
    
    def _predict_future_behavior(self):
        """التنبؤ بالسلوك المستقبلي"""
        if len(self.usage_history) < 100:
            return
        
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()
        
        # التنبؤ بالاستخدام في الساعة القادمة
        similar_times = [e for e in self.usage_history 
                        if e['hour'] == current_hour and e['day_of_week'] == current_day]
        
        if similar_times:
            avg_battery = statistics.mean([e['battery_percent'] for e in similar_times])
            self.predictions['expected_battery_next_hour'] = avg_battery
        
        # التنبؤ بوقت الشحن التالي
        charge_starts = [e['battery_percent'] for e in self.usage_history 
                        if e['is_charging'] and 
                        (not self.usage_history[max(0, self.usage_history.index(e)-1)]['is_charging'])]
        
        if charge_starts:
            self.predictions['typical_charge_start_level'] = statistics.mean(charge_starts)

    def _analyze_charge_cycles(self):
        """تحليل دورات الشحن"""
        charge_cycles = []
        current_cycle = {'start': None, 'end': None, 'duration': 0}
        
        for i, entry in enumerate(self.usage_history):
            if entry['is_charging']:
                if current_cycle['start'] is None:
                    current_cycle['start'] = entry
                current_cycle['end'] = entry
            elif current_cycle['start'] is not None:
                # انتهت دورة شحن
                start_time = datetime.fromisoformat(current_cycle['start']['timestamp'])
                end_time = datetime.fromisoformat(current_cycle['end']['timestamp'])
                duration = (end_time - start_time).total_seconds() / 60
                
                charge_cycles.append({
                    'start_percent': current_cycle['start']['battery_percent'],
                    'end_percent': current_cycle['end']['battery_percent'],
                    'duration_minutes': duration,
                    'gain': current_cycle['end']['battery_percent'] - current_cycle['start']['battery_percent']
                })
                
                current_cycle = {'start': None, 'end': None, 'duration': 0}
        
        if charge_cycles:
            self.learning_data['charge_cycle_count'] = len(charge_cycles)
            self.learning_data['avg_charge_duration'] = statistics.mean([c['duration_minutes'] for c in charge_cycles])
            self.learning_data['avg_charge_gain'] = statistics.mean([c['gain'] for c in charge_cycles])
    
    def _validate_predictions(self, current_entry: Dict):
        """التحقق من دقة التنبؤات السابقة والتعلم منها"""
        if not self.predictions:
            return
        
        try:
            # التحقق من التنبؤ بمستوى البطارية
            if 'expected_battery_next_hour' in self.predictions:
                expected = self.predictions['expected_battery_next_hour']
                actual = current_entry['battery_percent']
                error = abs(expected - actual)
                
                # حساب دقة التنبؤ
                accuracy = max(0, 100 - error)
                self.prediction_accuracy.append(accuracy)
                
                # الاحتفاظ بآخر 100 تنبؤ
                if len(self.prediction_accuracy) > 100:
                    self.prediction_accuracy = self.prediction_accuracy[-100:]
                
                # تحديث معدل التعلم بناءً على الدقة
                if len(self.prediction_accuracy) > 0:
                    avg_accuracy = statistics.mean(self.prediction_accuracy)
                    if avg_accuracy < 70:
                        self.learning_rate = min(0.3, self.learning_rate * 1.1)
                    elif avg_accuracy > 90:
                        self.learning_rate = max(0.05, self.learning_rate * 0.9)
                
                self.learning_data['prediction_accuracy_history'] = self.prediction_accuracy[-50:]
        except Exception as e:
            logger.debug(f"خطأ في التحقق من التنبؤات: {e}")
    
    def _adaptive_learning(self):
        """التعلم التكيفي المستمر"""
        if len(self.usage_history) < 20:
            return
        
        recent = self.usage_history[-20:]
        
        # تحديث بصمة سلوك المستخدم
        self._update_behavior_fingerprint(recent)
        
        # تحديث العتبات التكيفية
        self._update_adaptive_thresholds(recent)
        
        # تحديث الأنماط الأسبوعية
        self._update_weekly_patterns()
        
        # زيادة عداد التعلم
        self.learning_data['learning_iterations'] = self.learning_data.get('learning_iterations', 0) + 1
    
    def _update_behavior_fingerprint(self, recent_data: List[Dict]):
        """تحديث بصمة سلوك المستخدم الفريدة"""
        if not recent_data or len(recent_data) < 2:
            return
        
        try:
            fingerprint = {
                'avg_session_length': 0,
                'preferred_charge_level': 0,
                'typical_usage_intensity': 0,
                'charge_frequency': 0,
                'night_owl_score': 0,
                'power_user_score': 0
            }
            
            # حساب متوسط طول الجلسة
            charging_sessions = []
            current_session = []
            
            for entry in recent_data:
                if entry['is_charging']:
                    current_session.append(entry)
                elif current_session:
                    charging_sessions.append(len(current_session))
                    current_session = []
            
            if charging_sessions:
                fingerprint['avg_session_length'] = statistics.mean(charging_sessions)
            
            # مستوى الشحن المفضل
            charge_levels = [e['battery_percent'] for e in recent_data if e['is_charging']]
            if charge_levels:
                fingerprint['preferred_charge_level'] = statistics.mean(charge_levels)
            
            # كثافة الاستخدام
            power_draws = [e.get('power_draw', 0) for e in recent_data if e.get('power_draw', 0) > 0]
            if power_draws:
                fingerprint['typical_usage_intensity'] = statistics.mean(power_draws)
            
            # نقاط الاستخدام الليلي
            night_usage = sum(1 for e in recent_data if 22 <= e['hour'] or e['hour'] <= 6)
            fingerprint['night_owl_score'] = (night_usage / len(recent_data)) * 100
            
            # نقاط المستخدم القوي
            high_power = sum(1 for e in recent_data if e.get('power_draw', 0) > 15)
            fingerprint['power_user_score'] = (high_power / len(recent_data)) * 100
            
            self.learning_data['user_behavior_fingerprint'] = fingerprint
        except Exception as e:
            logger.debug(f"خطأ في تحديث بصمة السلوك: {e}")
    
    def _update_adaptive_thresholds(self, recent_data: List[Dict]):
        """تحديث العتبات التكيفية بناءً على السلوك"""
        if not recent_data or len(recent_data) < 2:
            return
        
        # عتبة الاستنزاف السريع
        drain_rates = []
        for i in range(1, len(recent_data)):
            try:
                if not recent_data[i]['is_charging']:
                    time_diff = (datetime.fromisoformat(recent_data[i]['timestamp']) - 
                               datetime.fromisoformat(recent_data[i-1]['timestamp'])).total_seconds() / 60
                    if 0 < time_diff < 10:
                        percent_diff = recent_data[i-1]['battery_percent'] - recent_data[i]['battery_percent']
                        if percent_diff > 0:
                            drain_rates.append(percent_diff / time_diff)
            except:
                continue
        
        if drain_rates:
            avg_drain = statistics.mean(drain_rates)
            self.adaptive_thresholds['fast_drain'] = avg_drain * 1.5
        
        # عتبة الاستخدام المكثف
        power_levels = [e.get('power_draw', 0) for e in recent_data if e.get('power_draw', 0) > 0]
        if power_levels:
            avg_power = statistics.mean(power_levels)
            self.adaptive_thresholds['heavy_usage'] = avg_power * 1.3
    
    def _update_weekly_patterns(self):
        """تحديث الأنماط الأسبوعية"""
        if len(self.usage_history) < 100:
            return
        
        weekly_data = defaultdict(lambda: {'drain': [], 'charge': [], 'usage': []})
        
        for entry in self.usage_history[-500:]:
            day = entry['day_of_week']
            
            if entry['is_charging']:
                weekly_data[day]['charge'].append(entry['battery_percent'])
            else:
                weekly_data[day]['drain'].append(entry['battery_percent'])
            
            power = entry.get('power_draw', 0)
            if power > 0:
                weekly_data[day]['usage'].append(power)
        
        # تحليل كل يوم
        patterns = {}
        for day, data in weekly_data.items():
            day_name = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد'][day]
            
            pattern = {
                'day': day_name,
                'avg_drain': statistics.mean(data['drain']) if data['drain'] else 0,
                'avg_charge': statistics.mean(data['charge']) if data['charge'] else 0,
                'avg_usage': statistics.mean(data['usage']) if data['usage'] else 0,
                'intensity': 'high' if data['usage'] and statistics.mean(data['usage']) > 15 else 'normal'
            }
            
            patterns[day] = pattern
        
        self.learning_data['weekly_patterns'] = patterns
    
    def get_smart_recommendations(self, current_battery: int, is_charging: bool) -> List[str]:
        """توصيات ذكية متقدمة مع التعلم المستمر"""
        recommendations = []
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()
        
        # حساب درجة الثقة للتوصيات
        confidence_base = self._calculate_confidence()
        
        # توصيات حرجة (أولوية قصوى)
        if current_battery < 10 and not is_charging:
            recommendations.append("🚨 حرج جداً! البطارية أقل من 10% - وصّل الشاحن فوراً!")
            return recommendations
        
        # توصيات حسب المستوى
        if current_battery < 15 and not is_charging:
            recommendations.append("⚠️ تحذير: البطارية منخفضة جداً! وصّل الشاحن الآن")
        elif current_battery < 20 and not is_charging:
            drain_rate = self.learning_data.get('average_drain_rate', 0)
            if drain_rate > 0:
                remaining_time = current_battery / drain_rate
                recommendations.append(f"⚠️ البطارية منخفضة! متبقي ~{int(remaining_time)} دقيقة")
        
        # توصيات الشحن الأمثل
        if current_battery > 85 and is_charging:
            recommendations.append("✅ مستوى ممتاز! يمكن فصل الشاحن الآن (85%+)")
        elif current_battery > 95 and is_charging:
            recommendations.append("⚡ شحن زائد! افصل الشاحن فوراً - يضر بصحة البطارية")
        elif 40 <= current_battery <= 80 and not is_charging:
            recommendations.append("✨ النطاق الصحي المثالي! استمر هكذا")
        
        # توصيات بناءً على الأنماط
        patterns = self.learning_data.get('patterns', [])
        for pattern in patterns:
            if isinstance(pattern, dict):
                if pattern.get('type') == 'heavy_usage' and current_hour in pattern.get('hours', []):
                    if current_battery < 60 and not is_charging:
                        recommendations.append(f"📊 AI: ساعة استخدام مكثف ({current_hour}:00) - يُنصح بالشحن")
        
        # توصيات بناءً على معدل الاستنزاف
        drain_rate = self.learning_data.get('average_drain_rate', 0)
        peak_drain = self.learning_data.get('peak_drain_rate', 0)
        
        if drain_rate > 1.5 and not is_charging:
            recommendations.append(f"⚡ استنزاف مرتفع ({drain_rate:.2f}%/د) - قلل الاستخدام المكثف")
        elif drain_rate > 0 and drain_rate < 0.5:
            recommendations.append(f"💚 استنزاف منخفض ({drain_rate:.2f}%/د) - استخدام مثالي!")
        
        # توصيات بناءً على الكفاءة
        efficiency = self.learning_data.get('efficiency_score', 100)
        health = self.learning_data.get('health_score', 100)
        
        if efficiency < 60:
            recommendations.append(f"⚠️ كفاءة منخفضة ({efficiency}%) - حافظ على 40-80%")
        elif efficiency > 85:
            recommendations.append(f"🌟 كفاءة ممتازة ({efficiency}%)! استمر")
        
        if health < 70:
            recommendations.append(f"💊 صحة البطارية ({health}%) - تجنب الشحن الكامل والتفريغ العميق")
        elif health > 90:
            recommendations.append(f"💪 صحة ممتازة ({health}%)!")
        
        # توصيات بناءً على نموذج السلوك
        typical_start = self.behavior_model.get('typical_charge_start', 0)
        if typical_start > 0 and current_battery < typical_start - 10 and not is_charging:
            confidence = min(95, confidence_base + 10)
            recommendations.append(f"💡 عادةً تشحن عند {int(typical_start)}% - حان الوقت؟ (ثقة: {confidence}%)")
        
        # توصيات بناءً على التنبؤات المحسّنة
        expected_next = self.predictions.get('expected_battery_next_hour', 0)
        if expected_next > 0 and expected_next < 20 and current_battery > 30:
            confidence = self._get_prediction_confidence()
            recommendations.append(f"🔮 AI: متوقع انخفاض لـ {int(expected_next)}% خلال ساعة (ثقة: {confidence}%)")
        
        # توصيات الشذوذ
        anomalies = self.anomaly_detector.get_recent_anomalies()
        if anomalies:
            latest = anomalies[-1]
            if latest['type'] == 'high_power_consumption':
                recommendations.append(f"⚠️ {latest['message']}")
        
        # توصيات بناءً على الأنماط الأسبوعية
        weekly_pattern = self.learning_data.get('weekly_patterns', {}).get(current_day)
        if weekly_pattern and weekly_pattern.get('intensity') == 'high':
            if current_battery < 60 and not is_charging:
                recommendations.append(f"📅 {weekly_pattern['day']}: يوم استخدام مكثف - يُنصح بالشحن")
        
        # توصيات بناءً على بصمة السلوك
        fingerprint = self.learning_data.get('user_behavior_fingerprint', {})
        if fingerprint:
            night_owl = fingerprint.get('night_owl_score', 0)
            if night_owl > 50 and 22 <= current_hour or current_hour <= 6:
                if current_battery < 50 and not is_charging:
                    recommendations.append(f"🌙 استخدام ليلي متوقع - يُنصح بالشحن الآن")
        
        # توصيات عامة ذكية
        if not is_charging and current_battery > 90:
            recommendations.append("💡 استخدم البطارية حتى 40% قبل الشحن التالي")
        
        if is_charging and current_battery < 30:
            charge_rate = self.learning_data.get('average_charge_rate', 0)
            if charge_rate > 0:
                time_to_80 = (80 - current_battery) / charge_rate
                recommendations.append(f"⏱️ متبقي ~{int(time_to_80)} دقيقة للوصول لـ 80%")
        
        # توصية تكيفية بناءً على دقة التنبؤات
        if self.prediction_accuracy:
            avg_accuracy = statistics.mean(self.prediction_accuracy[-20:])
            if avg_accuracy > 85:
                recommendations.append(f"🎯 دقة التنبؤ عالية ({int(avg_accuracy)}%) - التوصيات موثوقة")
        
        # حفظ التوصيات في البيانات
        final_recommendations = recommendations[:7]  # أفضل 7 توصيات
        self.learning_data['recommendations'] = final_recommendations
        self.learning_data['last_recommendation_time'] = datetime.now().isoformat()
        
        return final_recommendations
    
    def get_optimization_recommendations(self, current_battery: int, is_charging: bool) -> List[str]:
        """الحصول على توصيات التحسين للنظام"""
        recommendations = []
        
        try:
            # توصيات بناءً على مستوى البطارية
            if current_battery < 20 and not is_charging:
                recommendations.append("🔋 البطارية منخفضة - يُنصح بتحسين النظام لتوفير الطاقة")
            elif current_battery < 40 and not is_charging:
                recommendations.append("⚡ تحسين النظام سيساعد في إطالة عمر البطارية")
            
            # توصيات بناءً على معدل الاستنزاف
            drain_rate = self.learning_data.get('average_drain_rate', 0)
            if drain_rate > 1.5:
                recommendations.append("📊 معدل استنزاف مرتفع - التحسين سيقلل الاستهلاك")
            
            # توصيات بناءً على الكفاءة
            efficiency = self.learning_data.get('efficiency_score', 100)
            if efficiency < 70:
                recommendations.append("🎯 كفاءة منخفضة - التحسين سيحسن الأداء")
            
            return recommendations[:3]  # أفضل 3 توصيات
            
        except Exception as e:
            logger.error(f"خطأ في الحصول على توصيات التحسين: {e}")
            return []
    
    def predict_time_remaining(self, current_battery: int, is_charging: bool) -> Optional[str]:
        """تنبؤ دقيق جداً بالوقت المتبقي"""
        if len(self.usage_history) < 20:
            return "جارٍ جمع البيانات..."
        
        if is_charging:
            rate = self.learning_data.get('average_charge_rate', 0)
            target = 80  # الهدف الأمثل
            
            if rate > 0 and current_battery < target:
                remaining = target - current_battery
                minutes = remaining / rate
                
                # تعديل بناءً على الأنماط
                if current_battery > 80:
                    minutes *= 1.3  # الشحن يبطئ فوق 80%
                
                return self._format_time(minutes)
            elif current_battery >= target:
                return "وصلت للمستوى الأمثل"
        else:
            rate = self.learning_data.get('average_drain_rate', 0)
            
            if rate > 0:
                # التنبؤ حتى 20% (الحد الآمن)
                safe_level = 20
                remaining = current_battery - safe_level
                minutes = remaining / rate
                
                # تعديل بناءً على الوقت
                current_hour = datetime.now().hour
                if current_hour in self.learning_data.get('heavy_usage_hours', []):
                    minutes *= 0.8  # استنزاف أسرع في ساعات الذروة
                
                return self._format_time(minutes)
        
        return None
    
    def _format_time(self, minutes: float) -> str:
        """تنسيق الوقت"""
        if minutes < 1:
            return "أقل من دقيقة"
        elif minutes < 60:
            return f"~{int(minutes)} دقيقة"
        else:
            hours = int(minutes // 60)
            mins = int(minutes % 60)
            if hours > 24:
                days = hours // 24
                hours = hours % 24
                return f"~{days} يوم {hours}س"
            return f"~{hours}س {mins}د"

    def _analyze_battery_degradation(self):
        """تحليل تدهور البطارية"""
        if len(self.usage_history) < 100:
            return
        
        try:
            full_cycles = 0
            for i in range(1, min(len(self.usage_history), 500)):
                prev = self.usage_history[i-1]
                curr = self.usage_history[i]
                
                if prev['is_charging'] and not curr['is_charging']:
                    if curr['battery_percent'] > 80:
                        full_cycles += 1
            
            if full_cycles > 0:
                degradation_rate = full_cycles * 0.1
                self.learning_data['degradation_rate'] = degradation_rate
        except:
            pass
    
    def _find_optimal_charge_windows(self):
        """إيجاد نوافذ الشحن المثالية"""
        if len(self.usage_history) < 100:
            return
        
        try:
            hourly_drain = defaultdict(list)
            
            for i in range(1, len(self.usage_history)):
                curr = self.usage_history[i]
                if not curr['is_charging']:
                    hourly_drain[curr['hour']].append(1)
            
            idle_hours = [h for h, v in hourly_drain.items() if len(v) < 10]
            self.optimal_charge_windows = sorted(idle_hours)[:5]
        except:
            pass
    
    def _forecast_usage(self):
        """التنبؤ بالاستخدام"""
        if len(self.usage_history) < 50:
            return
        
        try:
            current_hour = datetime.now().hour
            forecast = {}
            
            for next_hour in range(1, 4):
                target_hour = (current_hour + next_hour) % 24
                similar = [e for e in self.usage_history[-200:] if e['hour'] == target_hour]
                
                if similar:
                    avg_battery = statistics.mean([e['battery_percent'] for e in similar])
                    forecast[f'hour_{next_hour}'] = {
                        'expected_battery': int(avg_battery),
                        'confidence': min(90, len(similar) * 5)
                    }
            
            self.usage_forecasting = forecast
        except:
            pass
    
    def _track_health_over_time(self):
        """تتبع الصحة"""
        try:
            health_entry = {
                'timestamp': datetime.now().isoformat(),
                'health_score': self.learning_data.get('health_score', 100),
                'efficiency_score': self.learning_data.get('efficiency_score', 100)
            }
            
            self.health_tracking.append(health_entry)
            if len(self.health_tracking) > 100:
                self.health_tracking = self.health_tracking[-100:]
        except:
            pass
    
    def _generate_optimization_suggestions(self):
        """توليد اقتراحات التحسين"""
        try:
            suggestions = []
            
            efficiency = self.learning_data.get('efficiency_score', 100)
            if efficiency < 70:
                suggestions.append({
                    'type': 'efficiency',
                    'priority': 'high',
                    'suggestion': 'حافظ على البطارية بين 40-80%',
                    'impact': 'تحسين 20-30%'
                })
            
            health = self.learning_data.get('health_score', 100)
            if health < 80:
                suggestions.append({
                    'type': 'health',
                    'priority': 'critical',
                    'suggestion': 'تجنب الشحن الكامل والتفريغ العميق',
                    'impact': 'إبطاء التدهور 40%'
                })
            
            self.optimization_suggestions = suggestions
        except:
            pass
    
    def _calculate_personalization_score(self):
        """حساب درجة التخصيص"""
        try:
            factors = []
            
            if self.learning_data.get('user_behavior_fingerprint'):
                factors.append(100)
            
            if self.learning_data.get('weekly_patterns'):
                factors.append(80)
            
            if self.optimal_charge_windows:
                factors.append(min(100, len(self.optimal_charge_windows) * 20))
            
            if factors:
                self.personalization_score = int(statistics.mean(factors))
        except:
            pass
    
    def _calculate_learning_progress(self):
        """حساب تقدم التعلم"""
        try:
            factors = []
            
            data_factor = min(100, (len(self.usage_history) / 2000) * 100)
            factors.append(data_factor)
            
            iterations = self.learning_data.get('learning_iterations', 0)
            iteration_factor = min(100, (iterations / 500) * 100)
            factors.append(iteration_factor)
            
            if self.prediction_accuracy:
                accuracy_factor = statistics.mean(self.prediction_accuracy[-50:])
                factors.append(accuracy_factor)
            
            patterns_count = len(self.learning_data.get('patterns', []))
            pattern_factor = min(100, (patterns_count / 10) * 100)
            factors.append(pattern_factor)
            
            if factors:
                self.learning_progress = int(statistics.mean(factors))
                
                if self.learning_progress < 20:
                    self.ai_maturity_level = 'مبتدئ'
                elif self.learning_progress < 40:
                    self.ai_maturity_level = 'يتعلم'
                elif self.learning_progress < 60:
                    self.ai_maturity_level = 'متوسط'
                elif self.learning_progress < 80:
                    self.ai_maturity_level = 'متقدم'
                else:
                    self.ai_maturity_level = 'خبير'
                
                self.learning_data['learning_progress'] = self.learning_progress
                self.learning_data['ai_maturity_level'] = self.ai_maturity_level
        except:
            pass
    
    def get_usage_statistics(self) -> Dict:
        """إحصائيات شاملة ومتقدمة"""
        if not self.usage_history:
            return {}
        
        # حساب تقدم التعلم
        self._calculate_learning_progress()
        
        total = len(self.usage_history)
        charging = sum(1 for e in self.usage_history if e['is_charging'])
        
        return {
            'total_records': total,
            'charging_percentage': (charging / total * 100) if total > 0 else 0,
            'average_drain_rate': self.learning_data.get('average_drain_rate', 0),
            'median_drain_rate': self.learning_data.get('median_drain_rate', 0),
            'peak_drain_rate': self.learning_data.get('peak_drain_rate', 0),
            'average_charge_rate': self.learning_data.get('average_charge_rate', 0),
            'peak_charge_rate': self.learning_data.get('peak_charge_rate', 0),
            'efficiency_score': self.learning_data.get('efficiency_score', 100),
            'health_score': self.learning_data.get('health_score', 100),
            'patterns_found': len(self.learning_data.get('patterns', [])),
            'heavy_usage_hours': self.learning_data.get('heavy_usage_hours', []),
            'optimal_charge_times': self.learning_data.get('optimal_charge_times', []),
            'charge_cycle_count': self.learning_data.get('charge_cycle_count', 0),
            'avg_charge_duration': self.learning_data.get('avg_charge_duration', 0),
            'average_power_draw': self.learning_data.get('average_power_draw', 0),
            'peak_power_draw': self.learning_data.get('peak_power_draw', 0),
            
            # إحصائيات متقدمة جديدة
            'learning_progress': self.learning_progress,
            'ai_maturity_level': self.ai_maturity_level,
            'personalization_score': self.personalization_score,
            'degradation_rate': self.learning_data.get('degradation_rate', 0),
            'battery_longevity_score': self.learning_data.get('battery_longevity_score', 100),
            'optimal_charge_windows': self.optimal_charge_windows,
            'usage_forecast': self.usage_forecasting
        }
    
    def get_detailed_analysis(self) -> Dict:
        """تحليل مفصل للعرض"""
        return {
            'behavior_model': self.behavior_model,
            'predictions': self.predictions,
            'patterns': self.learning_data.get('patterns', []),
            'anomalies': self.anomaly_detector.get_recent_anomalies(),
            'efficiency_score': self.learning_data.get('efficiency_score', 100),
            'health_score': self.learning_data.get('health_score', 100)
        }
    
    def _calculate_confidence(self) -> int:
        """حساب درجة الثقة الأساسية للتوصيات"""
        if len(self.usage_history) < 50:
            return 50
        
        data_factor = min(100, (len(self.usage_history) / 1000) * 100)
        
        accuracy_factor = 0
        if self.prediction_accuracy:
            accuracy_factor = statistics.mean(self.prediction_accuracy[-20:])
        
        iterations = self.learning_data.get('learning_iterations', 0)
        learning_factor = min(100, (iterations / 100) * 100)
        
        confidence = (data_factor * 0.3 + accuracy_factor * 0.5 + learning_factor * 0.2)
        
        return int(confidence)
    
    def _get_prediction_confidence(self) -> int:
        """حساب درجة الثقة للتنبؤ الحالي"""
        if not self.prediction_accuracy:
            return 60
        
        recent_accuracy = self.prediction_accuracy[-10:]
        avg = statistics.mean(recent_accuracy)
        
        if len(recent_accuracy) > 1:
            std_dev = statistics.stdev(recent_accuracy)
            if std_dev < 10:
                avg += 5
        
        return int(min(99, avg))


class AnomalyDetector:
    """كاشف الشذوذ"""
    
    def __init__(self):
        self.anomalies = []
        self.max_anomalies = 50
    
    def add_anomaly(self, anomaly: Dict):
        """إضافة شذوذ"""
        self.anomalies.append(anomaly)
        if len(self.anomalies) > self.max_anomalies:
            self.anomalies = self.anomalies[-self.max_anomalies:]
    
    def get_recent_anomalies(self, count: int = 5) -> List[Dict]:
        """الحصول على آخر الشذوذات"""
        return self.anomalies[-count:]
    
    def clear_old_anomalies(self, hours: int = 24):
        """مسح الشذوذات القديمة"""
        cutoff = datetime.now() - timedelta(hours=hours)
        self.anomalies = [a for a in self.anomalies 
                         if datetime.fromisoformat(a['timestamp']) > cutoff]


class PatternPredictor:
    """متنبئ الأنماط المتقدم"""
    
    def __init__(self):
        self.patterns = []
        self.confidence_threshold = 0.7
        self.pattern_weights = {}
    
    def predict_next_action(self, current_state: Dict) -> Optional[Dict]:
        """التنبؤ بالإجراء التالي بناءً على الأنماط"""
        if not self.patterns:
            return None
        
        # البحث عن أنماط مشابهة
        similar_patterns = []
        for pattern in self.patterns:
            similarity = self._calculate_similarity(current_state, pattern)
            if similarity > self.confidence_threshold:
                similar_patterns.append((pattern, similarity))
        
        if similar_patterns:
            # اختيار النمط الأكثر تشابهاً
            best_pattern = max(similar_patterns, key=lambda x: x[1])
            return {
                'predicted_action': best_pattern[0],
                'confidence': best_pattern[1]
            }
        
        return None
    
    def _calculate_similarity(self, state1: Dict, state2: Dict) -> float:
        """حساب التشابه بين حالتين"""
        if not isinstance(state2, dict):
            return 0.0
        
        similarity = 0.0
        factors = 0
        
        # مقارنة الساعة
        if 'hour' in state1 and 'hour' in state2:
            hour_diff = abs(state1['hour'] - state2['hour'])
            similarity += max(0, 1 - (hour_diff / 12))
            factors += 1
        
        # مقارنة اليوم
        if 'day_of_week' in state1 and 'day_of_week' in state2:
            if state1['day_of_week'] == state2['day_of_week']:
                similarity += 1
            factors += 1
        
        # مقارنة مستوى البطارية
        if 'battery_percent' in state1 and 'battery_percent' in state2:
            percent_diff = abs(state1['battery_percent'] - state2['battery_percent'])
            similarity += max(0, 1 - (percent_diff / 100))
            factors += 1
        
        return similarity / factors if factors > 0 else 0.0
    
    def learn_pattern(self, pattern: Dict):
        """تعلم نمط جديد مع الأوزان"""
        self.patterns.append(pattern)
        
        # الاحتفاظ بآخر 200 نمط
        if len(self.patterns) > 200:
            self.patterns = self.patterns[-200:]
        
        # تحديث أوزان الأنماط
        pattern_key = f"{pattern.get('hour', 0)}_{pattern.get('day_of_week', 0)}"
        self.pattern_weights[pattern_key] = self.pattern_weights.get(pattern_key, 0) + 1
    
    def get_optimization_recommendations(self, current_battery_percent: int, is_charging: bool) -> List[str]:
        """الحصول على توصيات التحسين الذكية"""
        recommendations = []
        
        try:
            # تحليل الحالة الحالية
            current_hour = datetime.now().hour
            usage_stats = self.get_usage_statistics()
            
            # توصيات بناءً على مستوى البطارية
            if current_battery_percent < 20 and not is_charging:
                recommendations.append("🚨 البطارية منخفضة - يُنصح بتحسين فوري لتوفير الطاقة")
                recommendations.append("⚡ تفعيل وضع توفير الطاقة المتقدم")
            elif current_battery_percent > 80 and is_charging:
                recommendations.append("🔋 البطارية مشحونة جيداً - يمكن فصل الشاحن لحماية البطارية")
            
            # توصيات بناءً على أنماط الاستخدام
            heavy_hours = usage_stats.get('heavy_usage_hours', [])
            if current_hour in heavy_hours:
                recommendations.append("🎯 وقت استخدام مكثف - تحسين العمليات والذاكرة مُوصى به")
                recommendations.append("🧠 تطبيق تحسينات شخصية لوقت الذروة")
            
            # توصيات بناءً على الكفاءة
            efficiency = usage_stats.get('efficiency_score', 100)
            if efficiency < 70:
                recommendations.append("📊 كفاءة البطارية منخفضة - تحسين شامل مطلوب")
                recommendations.append("🔧 تنظيف عميق للنظام والذاكرة")
            elif efficiency < 85:
                recommendations.append("⚙️ تحسين متوسط للحفاظ على الأداء")
            
            # توصيات بناءً على الصحة
            health = usage_stats.get('health_score', 100)
            if health < 80:
                recommendations.append("❤️ صحة البطارية تحتاج عناية - تجنب الشحن الكامل")
                recommendations.append("🌡️ مراقبة درجة الحرارة أثناء الاستخدام")
            
            # توصيات ذكية متقدمة
            if len(self.usage_history) > 100:
                # تحليل الأنماط المتقدمة
                recent_drain = self._calculate_recent_drain_rate()
                if recent_drain > 2:
                    recommendations.append("📈 معدل استنزاف مرتفع - تحسين العمليات ضروري")
                
                # تحليل دورات الشحن
                cycles = usage_stats.get('charge_cycle_count', 0)
                if cycles > 500:
                    recommendations.append("🔄 عدد دورات شحن مرتفع - تحسين نمط الشحن مُوصى")
            
            # إضافة توصيات عامة إذا لم توجد توصيات محددة
            if not recommendations:
                recommendations.append("✨ النظام يعمل بكفاءة جيدة")
                recommendations.append("🚀 تحسين دوري للحفاظ على الأداء الأمثل")
            
        except Exception as e:
            logger.error(f"خطأ في توصيات التحسين: {e}")
            recommendations = ["🔧 تحسين أساسي للنظام مُوصى به"]
        
        return recommendations[:5]  # أقصى 5 توصيات
    
    def _calculate_recent_drain_rate(self) -> float:
        """حساب معدل الاستنزاف الحديث"""
        if len(self.usage_history) < 10:
            return 0
        
        recent = self.usage_history[-10:]
        drain_rates = []
        
        for i in range(1, len(recent)):
            prev = recent[i-1]
            curr = recent[i]
            
            if not curr['is_charging']:
                try:
                    time_diff = (datetime.fromisoformat(curr['timestamp']) - 
                               datetime.fromisoformat(prev['timestamp'])).total_seconds() / 60
                    
                    if 0 < time_diff < 30:
                        percent_diff = abs(curr['battery_percent'] - prev['battery_percent'])
                        if percent_diff > 0:
                            drain_rates.append(percent_diff / time_diff)
                except:
                    continue
        
        return statistics.mean(drain_rates) if drain_rates else 0
    
    def _calculate_confidence(self) -> int:
        """حساب درجة ثقة الذكاء الاصطناعي"""
        confidence = 0
        
        # بناءً على كمية البيانات
        data_points = len(self.usage_history)
        if data_points > 1000:
            confidence += 40
        elif data_points > 500:
            confidence += 30
        elif data_points > 100:
            confidence += 20
        else:
            confidence += 10
        
        # بناءً على دقة التنبؤات
        if self.prediction_accuracy:
            avg_accuracy = statistics.mean(self.prediction_accuracy[-20:])
            confidence += int(avg_accuracy * 0.4)
        
        # بناءً على عدد الأنماط المكتشفة
        patterns = len(self.learning_data.get('patterns', []))
        confidence += min(20, patterns * 5)
        
        return min(100, confidence)