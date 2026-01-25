# Nota - AI Voice Dictation for Medical Notes

## Overview

Nota is a macOS dock application that provides AI-powered voice dictation. Users hold a hotkey (or button) to record speech, and the app transcribes it using Whisper, then automatically pastes the text at the cursor position.

## Tech Stack

- **Language**: Python 3.9+
- **UI Framework**: PyObjC (native macOS Cocoa)
- **Audio**: PyAudio for recording
- **Transcription**: faster-whisper (local Whisper model)
- **Hotkeys**: pynput for global keyboard hooks
- **Build**: PyInstaller for macOS .app bundle

## Project Structure

```
nota.py           # Main application (single-file app)
Nota.spec         # PyInstaller build configuration
README.md         # User documentation
ARCHITECTURE.md   # Technical architecture documentation
build/            # PyInstaller build artifacts
dist/             # Built application output
archive/          # Legacy versions and experiments
```

## Key Features

- **Hold-to-record**: Hold configurable hotkey (default: Left Option) to record
- **Button recording**: Click and hold the UI button to record
- **Auto-paste**: Automatically pastes transcribed text at cursor
- **Grammar fixing**: Basic capitalization and punctuation fixes
- **History**: Saves transcriptions to ~/.nota_history.json
- **Audio archiving**: Optional saving of audio recordings
- **Model selection**: Supports tiny/small/medium/large Whisper models

## Configuration

Config stored at `~/.nota_config.json`:

- `whisper_backend`: Model size (tiny/small/medium/large)
- `auto_paste`: Auto-paste transcribed text (bool)
- `fix_grammar`: Apply grammar fixes (bool)
- `save_audio`: Archive audio files (bool)
- `hotkey`: Recording hotkey (alt_l/alt_r/ctrl_l/ctrl_r/caps_lock)

## Development Commands

```bash
# Run directly (requires system Python with PyObjC)
/usr/bin/python3 nota.py

# Build macOS app
/usr/bin/python3 -m PyInstaller Nota.spec --noconfirm

# Install to Applications
cp -R dist/Nota.app /Applications/

# View logs
tail -f ~/.nota.log
```

## macOS Permissions Required

The app requires THREE permissions in System Settings > Privacy & Security:

1. **Microphone**: For audio recording
2. **Input Monitoring**: For global hotkey detection (pynput)
3. **Accessibility**: For auto-paste (simulating Cmd+V via AppleScript)

## Critical Implementation Notes

### PyObjC Method Naming

**IMPORTANT**: Avoid underscores in method names exposed to Objective-C. PyObjC interprets underscores as selector argument separators.

```python
# BAD - will cause "expects N arguments" error
def _update_status_(self, text): ...

# GOOD - use camelCase
def updateStatusText_(self, text): ...
```

### Thread Safety

All UI updates must happen on the main thread:

```python
self.performSelectorOnMainThread_withObject_waitUntilDone_(
    objc.selector(self.updateStatusText_, signature=b'v@:@'),
    text,
    False
)
```

### Why PyObjC (not Tkinter or rumps)

- **Tkinter**: Crashes on macOS due to Tcl/Tk 8.5.9 incompatibility with PyInstaller bundling
- **rumps**: Menu bar apps have unreliable icon visibility on modern macOS
- **PyObjC**: Native macOS, reliable, bundles correctly

### PyInstaller Build Notes

- Use system Python (`/usr/bin/python3`) which has PyObjC
- pyenv Python may lack Tkinter/PyObjC
- Hidden imports must include all PyObjC and pynput submodules
- No `LSUIElement: True` in info_plist (app should show in Dock)

## Code Style

- Single-file architecture for simplicity
- Uses threading for non-blocking audio recording
- Thread-safe state management with locks
- Comprehensive logging to ~/.nota.log
- UI updates always dispatched to main thread

## Files Created by App

- `~/.nota_config.json` - Configuration
- `~/.nota_history.txt` - Simple text history
- `~/.nota_history.json` - Detailed JSON history
- `~/.nota.log` - Application logs
- `~/.nota_audio/` - Audio archive (if enabled)
