# -*- mode: python ; coding: utf-8 -*-
# BatteryGuard Pro - PyInstaller Spec File

import sys
import os
from pathlib import Path

block_cipher = None

# جمع جميع ملفات الأصوات
sound_files = []
sounds_dir = Path('sounds')
if sounds_dir.exists():
    for sound_file in sounds_dir.glob('*.mp3'):
        sound_files.append((str(sound_file), 'sounds'))
    for sound_file in sounds_dir.glob('*.wav'):
        sound_files.append((str(sound_file), 'sounds'))

# جمع جميع ملفات الأصول
asset_files = []
assets_dir = Path('assets')
if assets_dir.exists():
    for asset_file in assets_dir.rglob('*'):
        if asset_file.is_file():
            rel_path = asset_file.relative_to(assets_dir).parent
            asset_files.append((str(asset_file), str(Path('assets') / rel_path)))

# جمع ملفات JSON
json_files = [
    ('battery_settings.json', '.'),
    ('battery_ai_data.json', '.'),
    ('auto_optimizer_settings.json', '.'),
]

# تجميع كل الملفات
all_datas = sound_files + asset_files
for json_file, dest in json_files:
    if Path(json_file).exists():
        all_datas.append((json_file, dest))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=all_datas,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'psutil',
        'json',
        'pathlib',
        'threading',
        'socket',
        'subprocess',
        'logging',
        'datetime',
        'time',
        'platform',
        'plyer',
        'plyer.platforms.win.notification',
        # وحدات التطبيق
        'storage',
        'battery_ai',
        'monitor_thread',
        'charge_controller',
        'charge_control_advanced',
        'battery_optimizer',
        'battery_optimizer_ai',
        'auto_optimizer',
        'permission_manager',
        'interactive_notification_dialog',
        'actionable_notification_dialog',
        'welcome_dialog',
        'default_settings',
        'app_colors',
        'resource_path',
        'notification_manager',
        'battery_monitor',
        'tray_icon',
        'single_instance',
        'autostart_manager',
        'main_window',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BatteryGuardPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.png' if Path('assets/logo.png').exists() else None,
)
