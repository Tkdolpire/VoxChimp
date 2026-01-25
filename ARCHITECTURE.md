# Nota Architecture

This document describes the technical architecture of Nota for developers making future improvements.

## Overview

Nota is a native macOS application built with Python and PyObjC. It provides voice-to-text transcription using the Whisper model, with a floating window UI and global hotkey support.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Nota Application                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   PyObjC    │  │   pynput    │  │    faster-whisper       │ │
│  │  (UI/App)   │  │  (Hotkeys)  │  │   (Transcription)       │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
│         │                │                      │               │
│         └────────────────┼──────────────────────┘               │
│                          │                                      │
│                 ┌────────┴────────┐                            │
│                 │ NotaAppDelegate │                            │
│                 │  (Main Class)   │                            │
│                 └─────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
Nota/
├── nota.py           # Main application (single-file)
├── Nota.spec         # PyInstaller build configuration
├── README.md         # User documentation
├── ARCHITECTURE.md   # This file
├── CLAUDE.md         # AI assistant instructions
├── build/            # PyInstaller build artifacts
├── dist/             # Built application output
│   └── Nota.app/     # Final macOS application bundle
└── archive/          # Legacy versions
```

## Core Components

### 1. Application Framework (PyObjC)

The app uses PyObjC to create a native macOS Cocoa application. This was chosen over alternatives because:

- **Tkinter**: Crashes on macOS due to Tcl/Tk version incompatibility with PyInstaller
- **rumps**: Menu bar apps have unreliable icon visibility on modern macOS
- **PyObjC**: Native, reliable, bundles correctly with PyInstaller

Key PyObjC components:

- `NSApplication` - Application lifecycle
- `NSWindow` - Main floating window
- `NSButton`, `NSTextField` - UI controls
- `NSAlert` - Dialog boxes
- `NSEvent` - Mouse event monitoring

### 2. Main Class: NotaAppDelegate

```python
class NotaAppDelegate(NSObject):
    # Instance variables (must be declared as objc.ivar)
    window = objc.ivar()
    record_button = objc.ivar()
    status_label = objc.ivar()
    hotkey_label = objc.ivar()
```

**Important PyObjC Patterns:**

1. **Method naming**: Avoid underscores in method names that will be called from Objective-C. PyObjC interprets underscores as selector argument separators.

   ```python
   # BAD - PyObjC interprets as "_update:status:" (2 arguments)
   def _update_status_(self, text): ...

   # GOOD - Single argument selector
   def updateStatusText_(self, text): ...
   ```

2. **Main thread UI updates**: All UI modifications must happen on the main thread.

   ```python
   self.performSelectorOnMainThread_withObject_waitUntilDone_(
       objc.selector(self.updateStatusText_, signature=b'v@:@'),
       text,
       False
   )
   ```

3. **Selector signatures**: The signature `b'v@:@'` means:
   - `v` = void return
   - `@` = self (object)
   - `:` = selector
   - `@` = one object argument

### 3. Threading Model

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Main Thread   │     │ Recording Thread│     │  pynput Thread  │
│                 │     │                 │     │                 │
│  - UI updates   │     │  - PyAudio      │     │  - Keyboard     │
│  - Event loop   │◄────│  - WAV writing  │     │    listener     │
│  - Alerts       │     │  - Transcription│     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        ▲                       │                       │
        │                       │                       │
        └───────────────────────┴───────────────────────┘
              performSelectorOnMainThread
```

**Thread Safety:**

- `self._lock` (threading.Lock) protects `self.is_recording`
- UI updates use `performSelectorOnMainThread_withObject_waitUntilDone_`
- pynput listener runs in its own daemon thread

### 4. Audio Recording Pipeline

```
User holds hotkey/button
        │
        ▼
┌───────────────────┐
│  start_recording  │
│  - Set is_recording = True
│  - Start recording thread
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   record_audio    │  (Background thread)
│  - PyAudio stream │
│  - Collect frames │
│  - Write WAV file │
└─────────┬─────────┘
          │
User releases hotkey/button
          │
          ▼
┌───────────────────┐
│  stop_recording   │
│  - Set is_recording = False
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  validate_audio   │
│  - Check amplitude│
│  - Detect silence │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  process_audio    │
│  - Whisper transcribe
│  - Fix grammar    │
│  - Copy to clipboard
│  - Auto-paste     │
└───────────────────┘
```

### 5. Transcription Backend

faster-whisper is used for local transcription:

```python
self.whisper_model = WhisperModel(
    model_size,      # tiny/small/medium/large
    device="cpu",    # CPU inference
    compute_type="int8"  # Quantized for speed
)

segments, _ = self.whisper_model.transcribe(
    audio_file,
    language="en",
    beam_size=5,
    vad_filter=False,
    condition_on_previous_text=False
)
```

Model sizes and trade-offs:
| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | 75MB | Fastest | Basic |
| small | 500MB | Fast | Good |
| medium | 1.5GB | Medium | Better |
| large | 3GB | Slow | Best |

### 6. Global Hotkey System

pynput provides cross-application keyboard monitoring:

```python
from pynput import keyboard

def on_press(key):
    if key == target_key and not self.hotkey_pressed:
        self.hotkey_pressed = True
        self.start_recording()

def on_release(key):
    if key == target_key and self.hotkey_pressed:
        self.hotkey_pressed = False
        self.stop_recording()

self.listener = keyboard.Listener(
    on_press=on_press,
    on_release=on_release
)
self.listener.start()  # Runs in background thread
```

**Critical**: Requires **Input Monitoring** permission in macOS Privacy settings.

### 7. Auto-Paste Mechanism

Uses AppleScript via osascript to simulate Cmd+V:

```python
subprocess.run([
    'osascript', '-e',
    'tell application "System Events" to keystroke "v" using command down'
])
```

**Critical**: Requires **Accessibility** permission in macOS Privacy settings.

## Build System

### PyInstaller Configuration (Nota.spec)

Key settings:

```python
# Hidden imports - modules not detected by static analysis
hiddenimports=[
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._darwin',  # macOS-specific
    'pyaudio',
    'faster_whisper',
    'ctranslate2',
    'objc',
    'Foundation',
    'AppKit',
    'PyObjCTools',
]

# Info.plist settings
info_plist={
    'CFBundleName': 'Nota',
    'CFBundleIdentifier': 'com.nota.app',
    'NSMicrophoneUsageDescription': '...',  # Required for mic access
    'NSAppleEventsUsageDescription': '...',  # Required for automation
}
```

**Important**: No `LSUIElement: True` - this makes the app appear in Dock (not menu bar).

### Build Commands

```bash
# Build with system Python (has PyObjC)
/usr/bin/python3 -m PyInstaller Nota.spec --noconfirm

# Install to Applications
cp -R dist/Nota.app /Applications/

# Run directly for testing
/usr/bin/python3 nota.py
```

## Configuration System

### File: ~/.nota_config.json

```json
{
  "whisper_backend": "small",
  "auto_paste": true,
  "fix_grammar": true,
  "save_audio": false,
  "hotkey": "alt_l"
}
```

### Loading Order

1. Check if `~/.nota_config.json` exists
2. If yes, load and parse JSON
3. If no (or parse error), use defaults
4. Settings are read at startup; some require restart to take effect

## History System

### Text Format (~/.nota_history.txt)

Simple tab-separated format:

```
2026-01-25 15:10:14	Testing to see if this works.
```

### JSON Format (~/.nota_history.json)

Rich format with metadata:

```json
{
  "id": 1,
  "timestamp": "2026-01-25T15:10:14.142",
  "text": "Testing to see if this works.",
  "word_count": 6,
  "char_count": 31,
  "category": null,
  "tags": [],
  "audio_file": "/Users/.../.nota_audio/recording_20260125_151014.wav"
}
```

## Error Handling

### Audio Validation

Before transcription, audio is validated:

- `max_amp == 0`: Likely permission issue (silent input)
- `max_amp < 100`: Audio too quiet to transcribe

### Permission Checks

At startup:

1. Test microphone by reading a short sample
2. Check if samples are all zeros (permission denied)
3. Show warning dialog if issues detected

### Logging

All operations logged to `~/.nota.log`:

```python
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
```

Log rotation keeps last 5000 lines.

## Known Limitations

1. **Single language**: Hardcoded to English (`language="en"`)
2. **CPU only**: No GPU acceleration (device="cpu")
3. **No real-time transcription**: Processes after recording completes
4. **macOS only**: PyObjC and pynput.\_darwin are macOS-specific

## Common Issues When Modifying

### PyObjC Method Names

```python
# This will FAIL - PyObjC parses underscores as argument separators
def _my_method_(self, arg): ...

# This works - camelCase naming
def myMethod_(self, arg): ...
```

### Thread Safety

```python
# WRONG - UI update from background thread
def record_audio(self):
    self.status_label.setStringValue_("Recording")  # CRASH

# RIGHT - dispatch to main thread
def record_audio(self):
    self.performSelectorOnMainThread_withObject_waitUntilDone_(
        objc.selector(self.updateStatusText_, signature=b'v@:@'),
        "Recording",
        False
    )
```

### PyInstaller Hidden Imports

If adding new dependencies, add them to `hiddenimports` in Nota.spec:

```python
hiddenimports=[
    'new_module',
    'new_module.submodule',
]
```

## Future Improvement Areas

1. **Settings UI**: Replace "edit config file" with proper settings window
2. **Multiple languages**: Add language selection
3. **GPU support**: Metal/CoreML acceleration on Apple Silicon
4. **Real-time transcription**: Stream audio to model
5. **Custom vocabulary**: Medical terminology dictionary
6. **Keyboard shortcuts**: In-app shortcuts for common actions
