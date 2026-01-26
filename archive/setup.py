"""
Setup script for building Voice Dictation as a macOS app bundle.
Run: python setup.py py2app
"""
from setuptools import setup

APP = ['voice_dictation_menubar.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': None,  # Add icon file path here if you have one
    'plist': {
        'CFBundleName': 'Voice Dictation',
        'CFBundleDisplayName': 'Voice Dictation',
        'CFBundleIdentifier': 'com.voicedictation.menubar',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,  # Menu bar app (no dock icon)
        'NSMicrophoneUsageDescription': 'Voice Dictation needs microphone access to record your speech for transcription.',
        'NSAppleEventsUsageDescription': 'Voice Dictation needs automation access to paste transcribed text.',
    },
    'packages': [
        'rumps',
        'pynput',
        'pyaudio',
        'faster_whisper',
        'ctranslate2',
        'tokenizers',
        'huggingface_hub',
    ],
    'includes': [
        'queue',
        'threading',
        'json',
        'logging',
        'tempfile',
        'wave',
    ],
}

setup(
    app=APP,
    name='Voice Dictation',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
