#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعدادات مشتركة لاختبارات BatteryGuardAI"""

import os
import shutil
import sys
from pathlib import Path

# إضافة جذر المشروع لمسار الاستيراد
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# تشغيل Qt بلا شاشة في بيئة CI
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# عزل إعدادات Qt (QSettings) عن إعدادات المستخدم الحقيقية -
# بدونه قد تقرأ الاختبارات تفضيلات حقيقية (مثل تفعيل التحكم بالشحن)
# وتحاول طلب صلاحيات sudo أثناء الاختبار!
_QT_ISOLATED_CONFIG = ROOT / '.qt-test-config'
if _QT_ISOLATED_CONFIG.exists():
    shutil.rmtree(_QT_ISOLATED_CONFIG, ignore_errors=True)
_QT_ISOLATED_CONFIG.mkdir(parents=True, exist_ok=True)
os.environ['XDG_CONFIG_HOME'] = str(_QT_ISOLATED_CONFIG)

import pytest


@pytest.fixture(scope='session')
def qapp():
    """تطبيق Qt واحد لكل جلسة اختبار"""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """
    عزل مجلد بيانات المستخدم لكل اختبار حتى لا تتلوث
    بيانات ~/.config/batteryguard الحقيقية.
    """
    data_dir = tmp_path / 'batteryguard-data'
    data_dir.mkdir(parents=True, exist_ok=True)

    import storage
    import resource_path

    monkeypatch.setattr(storage, 'get_data_path', lambda f: data_dir / f)
    monkeypatch.setattr(resource_path, 'get_data_path', lambda f: data_dir / f)
    yield data_dir


@pytest.fixture
def clean_qsettings():
    """مسح إعدادات QSettings المعزولة قبل الاختبار"""
    from PyQt6.QtCore import QSettings
    settings = QSettings('BatteryGuard', 'Pro')
    settings.clear()
    settings.sync()
    yield settings
    settings.clear()
    settings.sync()
