# Notta Architecture

Technical architecture documentation for developers working on Notta.

## Overview

Notta is a native macOS voice dictation application with two parallel implementations:

1. **Python/PyObjC** (`notta.py`) - Original implementation, single-file architecture
2. **Swift/SwiftUI** (`NottaSwiftUI/`) - Modern native implementation

Both provide AI-powered voice-to-text transcription using local Whisper models, with additional voice health analysis capabilities.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Notta Application                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │   PyObjC /   │  │    pynput    │  │   Whisper    │  │  Health Module   │ │
│  │   SwiftUI    │  │   (Hotkeys)  │  │ (Transcribe) │  │  (HEAR Analysis) │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘ │
│         │                 │                 │                    │          │
│         └─────────────────┴─────────────────┴────────────────────┘          │
│                                    │                                         │
│                         ┌──────────┴──────────┐                             │
│                         │   NottaAppDelegate  │                             │
│                         │    (Main Class)     │                             │
│                         └─────────────────────┘                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
Notta/
├── notta.py                 # Python app (2000+ lines, single-file)
├── Notta.spec               # PyInstaller build configuration
├── build.sh                 # Python app build script
├── entitlements.plist       # macOS code signing entitlements
│
├── NottaSwiftUI/            # Swift/SwiftUI implementation
│   ├── Notta/               # Source code
│   │   ├── NottaApp.swift   # App entry point
│   │   ├── Models/          # Data models
│   │   ├── Views/           # SwiftUI views
│   │   ├── Services/        # Business logic
│   │   └── Resources/       # Assets, localization
│   ├── NottaTests/          # Unit tests
│   └── Scripts/
│       └── build-release.sh # Release build with notarization
│
├── health/                  # Voice health analysis module
│   ├── __init__.py
│   ├── acoustic_analyzer.py # Praat-based feature extraction
│   ├── analyzer.py          # Main analysis orchestrator
│   ├── analyzer_worker.py   # Background processing
│   ├── baseline_manager.py  # User baseline tracking
│   ├── embedding_store.py   # Vector storage for embeddings
│   ├── interpreter.py       # Health metric interpretation
│   └── metrics.py           # Metric definitions
│
├── tests/                   # Test suite (286 tests)
│   ├── conftest.py          # Pytest fixtures
│   ├── test_notta_core.py   # Core functionality tests
│   ├── test_notta_integration.py
│   └── test_*.py            # Module-specific tests
│
├── docs/                    # Documentation
│   ├── STYLE_GUIDE.md       # Brand and design specs
│   └── BRAND-STYLE-GUIDE.md
│
├── assets/                  # App icons and images
├── dist/                    # Built application output
├── build/                   # Build artifacts
└── archive/                 # Legacy versions
```

## Core Components

### 1. Application Framework

#### Python Implementation (PyObjC)

Chosen over alternatives for reliability:

| Framework | Issue                                                      |
| --------- | ---------------------------------------------------------- |
| Tkinter   | Crashes on macOS with PyInstaller (Tcl/Tk incompatibility) |
| rumps     | Menu bar icon visibility unreliable on modern macOS        |
| PyObjC    | Native, reliable, bundles correctly                        |

Key PyObjC components:

- `NSApplication` - Application lifecycle
- `NSWindow` - Main floating window
- `NSStatusBar` - Menu bar status item (chimp mascot)
- `NSButton`, `NSTextField` - UI controls
- `NSEvent` - Mouse/keyboard event monitoring

#### Swift Implementation (SwiftUI)

Modern native implementation using:

- SwiftUI for declarative UI
- WhisperKit for on-device transcription
- Apple Translation framework for post-transcription translation
- Combine for reactive data flow
- Sparkle for auto-updates

### 2. Main Class: NottaAppDelegate

```python
class NottaAppDelegate(NSObject):
    # Instance variables (objc.ivar required)
    window = objc.ivar()
    record_button = objc.ivar()
    status_label = objc.ivar()
    status_item = objc.ivar()  # Menu bar
```

**Critical PyObjC Patterns:**

1. **Method naming** - Avoid underscores (parsed as argument separators):

   ```python
   # BAD - interpreted as "_update:status:" (2 args)
   def _update_status_(self, text): ...

   # GOOD - single argument selector
   def updateStatusText_(self, text): ...
   ```

2. **Main thread UI updates**:

   ```python
   self.performSelectorOnMainThread_withObject_waitUntilDone_(
       objc.selector(self.updateStatusText_, signature=b'v@:@'),
       text,
       False
   )
   ```

3. **Selector signatures** (`b'v@:@'`):
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
- UI updates via `performSelectorOnMainThread_withObject_waitUntilDone_`
- pynput listener runs in daemon thread
- Health analysis runs in background worker thread

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
          ├──────────────────────────────┐
          ▼                              ▼
┌───────────────────┐          ┌───────────────────┐
│  process_audio    │          │  health_analysis  │
│  - Whisper transcribe        │  - Extract features│
│  - Fix grammar    │          │  - Generate embeddings
│  - Translate (opt)│          │  - Compare baseline│
│  - Copy clipboard │          │  - Store results  │
│  - Auto-paste     │          └───────────────────┘
└───────────────────┘
```

### 5. Transcription Backend

**Primary: faster-whisper (Python) / WhisperKit (Swift)**

```python
self.whisper_model = WhisperModel(
    model_size,           # tiny/small/medium/large
    device="cpu",         # CPU inference
    compute_type="int8"   # Quantized for speed
)

segments, _ = self.whisper_model.transcribe(
    audio_file,
    language="en",
    beam_size=5,
    vad_filter=False,
    condition_on_previous_text=False
)
```

**Fallback: Apple Speech Recognition**

When Whisper model is downloading or unavailable, falls back to system speech recognition.

**Model Comparison:**

| Model  | Size  | Speed   | Accuracy | Use Case              |
| ------ | ----- | ------- | -------- | --------------------- |
| tiny   | 75MB  | Fastest | Basic    | Quick notes           |
| small  | 500MB | Fast    | Good     | General use (default) |
| medium | 1.5GB | Medium  | Better   | Important docs        |
| large  | 3GB   | Slow    | Best     | Medical/legal         |

### 6. Voice Health Analysis (HEAR Module)

The health module provides voice biomarker analysis:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Health Analysis Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Audio Input                                                     │
│      │                                                           │
│      ▼                                                           │
│  ┌──────────────────┐                                           │
│  │ acoustic_analyzer │  Praat/Parselmouth feature extraction    │
│  │  - Pitch (F0)     │  - Jitter, shimmer, HNR                  │
│  │  - Formants       │  - Voice quality metrics                 │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │ embedding_store  │  TensorFlow embeddings for comparison     │
│  │  - HEAR model    │  - Vector similarity matching             │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │ baseline_manager │  Track user's normal voice patterns       │
│  │  - Rolling avg   │  - Detect deviations                      │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │   interpreter    │  Convert metrics to health insights       │
│  │  - Fatigue       │  - Stress, illness detection              │
│  └──────────────────┘                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Metrics:**

- **Jitter**: Pitch variation (voice stability)
- **Shimmer**: Amplitude variation
- **HNR**: Harmonics-to-noise ratio (voice clarity)
- **F0**: Fundamental frequency (pitch)
- **Formants**: Resonance frequencies (articulation)

### 7. Global Hotkey System

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

self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
self.listener.start()  # Background thread
```

**Supported Hotkeys:**

- `alt_l` (Left Option) - Default
- `alt_r` (Right Option)
- `ctrl_l` / `ctrl_r` (Control keys)
- `caps_lock`

**Requires:** Input Monitoring permission in System Settings.

### 8. Auto-Paste Mechanism

Uses AppleScript via osascript:

```python
subprocess.run([
    'osascript', '-e',
    'tell application "System Events" to keystroke "v" using command down'
])
```

**Requires:** Accessibility permission in System Settings.

### 9. Translation (v2.0+)

Post-transcription translation using Apple Translation framework (Swift implementation):

```swift
let session = TranslationSession(
    source: .english,
    target: selectedLanguage
)
let result = try await session.translate(transcribedText)
```

## Configuration System

### File: ~/.notta_config.json

```json
{
  "whisper_backend": "small",
  "auto_paste": true,
  "fix_grammar": true,
  "save_audio": false,
  "hotkey": "alt_l"
}
```

### Runtime Files

| File                    | Purpose                                  |
| ----------------------- | ---------------------------------------- |
| `~/.notta_config.json`  | User settings                            |
| `~/.notta_history.txt`  | Simple text history                      |
| `~/.notta_history.json` | Detailed JSON history with metadata      |
| `~/.notta.log`          | Application logs (rotates at 5000 lines) |
| `~/.notta_audio/`       | Audio archive (if enabled)               |
| `~/.notta_health/`      | Health embeddings and baselines          |

## Build System

### Python Build (PyInstaller)

```bash
# Build with system Python (has PyObjC)
/usr/bin/python3 -m PyInstaller Notta.spec --noconfirm

# With code signing
CODESIGN_IDENTITY="Developer ID Application: ..." ./build.sh
```

Key Notta.spec settings:

- Hidden imports for all dependencies
- Bundle identifier: `com.tyrondolpire.notta`
- Entitlements for microphone, accessibility, automation
- No `LSUIElement` (shows in Dock, not menu bar only)

### Swift Build

```bash
# Development
xcodebuild -scheme Notta -configuration Debug

# Release with notarization
./NottaSwiftUI/Scripts/build-release.sh
```

## macOS Permissions

Three permissions required (System Settings > Privacy & Security):

| Permission       | Purpose                       | Check Method                |
| ---------------- | ----------------------------- | --------------------------- |
| Microphone       | Audio recording               | Test audio stream for zeros |
| Input Monitoring | Global hotkey detection       | pynput listener status      |
| Accessibility    | Auto-paste (Cmd+V simulation) | osascript execution         |

## Error Handling

### Audio Validation

```python
if max_amp == 0:
    # Microphone permission denied (silent input)
    show_permission_warning()
elif max_amp < 100:
    # Audio too quiet
    show_volume_warning()
```

### Graceful Degradation

1. **Whisper not ready** → Fall back to Apple Speech
2. **Model download fails** → Retry with exponential backoff
3. **Health analysis fails** → Continue with transcription only
4. **Auto-paste fails** → Copy to clipboard only

### Logging

```python
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('~/.notta.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
```

Log rotation at 5000 lines preserves recent history.

## Security Considerations

- **Local processing only** - No data sent to external servers
- **No API keys** - Uses local models
- **User data in home directory** - Standard macOS sandboxing
- **Optional audio archiving** - User-controlled
- **Code signing** - Developer ID for Gatekeeper
- **Notarization** - Apple security scan required

## Known Limitations

1. **Single language default** - English (`language="en"`), translation available
2. **CPU inference** - No GPU acceleration (Metal support planned)
3. **Post-recording transcription** - Not real-time streaming
4. **macOS only** - PyObjC/SwiftUI are platform-specific

## Common Development Issues

### PyObjC Method Names

```python
# WRONG - underscores parsed as argument separators
def _my_method_(self, arg): ...

# RIGHT - camelCase
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

### Adding Dependencies

Add to `hiddenimports` in Notta.spec:

```python
hiddenimports=[
    'new_module',
    'new_module.submodule',
]
```

## Future Roadmap

- [ ] Real-time streaming transcription
- [ ] Metal/CoreML GPU acceleration
- [ ] Custom medical vocabulary
- [ ] Multi-speaker diarization
- [ ] Cloud sync (optional, encrypted)
- [ ] iOS companion app
