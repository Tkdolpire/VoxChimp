# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Nota (PyObjC native macOS dock app)

block_cipher = None

a = Analysis(
    ['nota.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._darwin',
        'pyaudio',
        'faster_whisper',
        'ctranslate2',
        'tokenizers',
        'huggingface_hub',
        'av',
        'objc',
        'Foundation',
        'AppKit',
        'PyObjCTools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Nota',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Nota',
)

app = BUNDLE(
    coll,
    name='Nota.app',
    icon=None,
    bundle_identifier='com.nota.app',
    info_plist={
        'CFBundleName': 'Nota',
        'CFBundleDisplayName': 'Nota',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSMicrophoneUsageDescription': 'Nota needs microphone access to record your speech for transcription.',
        'NSAppleEventsUsageDescription': 'Nota needs automation access to paste transcribed text.',
    },
)
