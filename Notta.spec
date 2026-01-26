# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Notta (PyObjC native macOS dock app)
import os

block_cipher = None

# Get signing identity from environment variable (optional)
codesign_identity = os.environ.get('CODESIGN_IDENTITY', None)

a = Analysis(
    ['notta.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('health', 'health'),  # Include health package
        ('assets', 'assets'),  # Include assets
    ],
    hiddenimports=[
        # Core app dependencies
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
        # Health module
        'health',
        'health.analyzer',
        'health.analyzer_worker',
        'health.embedding_store',
        'health.acoustic_analyzer',
        # Acoustic analysis
        'parselmouth',
        'praat',
        # TensorFlow and HEAR dependencies
        'tensorflow',
        'tensorflow.keras',
        'keras',
        'librosa',
        'librosa.core',
        'librosa.core.audio',
        'soundfile',
        'scipy',
        'scipy.signal',
        'scipy.fft',
        'scipy.fftpack',
        'audioread',
        'resampy',
        'numba',
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
    name='Notta',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=codesign_identity,
    entitlements_file='entitlements.plist' if codesign_identity else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Notta',
)

app = BUNDLE(
    coll,
    name='Notta.app',
    icon='assets/AppIcon.icns',
    bundle_identifier='com.tyrondolpire.notta',
    info_plist={
        'CFBundleName': 'Notta',
        'CFBundleDisplayName': 'Notta',
        'CFBundleVersion': '2.0.0',
        'CFBundleShortVersionString': '2.0.0',
        'LSMinimumSystemVersion': '11.0',
        'NSMicrophoneUsageDescription': 'Notta needs microphone access to record your speech for transcription.',
        'NSAppleEventsUsageDescription': 'Notta needs automation access to paste transcribed text.',
        'NSInputMonitoringUsageDescription': 'Notta needs input monitoring to detect the global hotkey for recording.',
        'NSHighResolutionCapable': True,
        'NSSupportsAutomaticGraphicsSwitching': True,
    },
)
