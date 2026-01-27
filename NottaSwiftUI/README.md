# Notta SwiftUI

Native macOS voice dictation app built with SwiftUI.

## Requirements

- macOS 14.0 (Sonoma) or later
- Xcode 15.0 or later
- Apple Developer account (for App Store distribution)

## Project Structure

```
Notta/
├── NottaApp.swift           # App entry point & scenes
├── AppState.swift           # Global app state management
├── Models/
│   ├── Transcription.swift  # History entry model
│   ├── Settings.swift       # App settings & persistence
│   └── VoiceHealth.swift    # Health metrics models
├── Views/
│   ├── MainView.swift       # Main recording interface
│   ├── HistoryView.swift    # Searchable history list
│   ├── SettingsView.swift   # Native settings tabs
│   └── HealthDashboardView.swift  # Health charts & metrics
├── Services/
│   ├── AudioRecorder.swift      # AVFoundation recording
│   ├── WhisperService.swift     # Transcription engine
│   ├── HotkeyManager.swift      # Global hotkey handling
│   └── AcousticAnalyzer.swift   # Voice health analysis
├── Resources/
│   └── Assets.xcassets/     # App icons & colors
├── Info.plist               # App configuration
└── Notta.entitlements       # App capabilities
```

## Building

### Option 1: Xcode (Recommended)

1. Create a new Xcode project:
   - File > New > Project
   - Choose "App" under macOS
   - Product Name: Notta
   - Interface: SwiftUI
   - Language: Swift

2. Replace the generated files with these source files

3. Configure signing & capabilities:
   - Add "Audio Input" capability
   - Add "App Sandbox" with necessary permissions
   - Or disable sandbox for development

4. Build and run (⌘R)

### Option 2: Swift Package Manager

```bash
cd NottaSwiftUI
swift build
swift run
```

### Option 3: xcodebuild

```bash
# Generate Xcode project from Package.swift
swift package generate-xcodeproj

# Build
xcodebuild -project Notta.xcodeproj -scheme Notta -configuration Release
```

## Permissions Required

The app requires these permissions in System Settings > Privacy & Security:

1. **Microphone** - For audio recording
2. **Accessibility** - For global hotkey detection
3. **Automation** - For auto-paste functionality (System Events)
4. **Speech Recognition** - For fallback transcription

## Features

### Main Window

- Hold-to-record with animated button
- Real-time status display
- Last transcription preview with copy

### History

- Searchable list of all transcriptions
- Sort by date or length
- Swipe to copy or delete
- Audio playback (if saved)
- Full text detail view

### Settings

- Native macOS Settings window
- Whisper model selection
- Hotkey configuration
- Auto-paste toggle
- Audio saving options
- Health notification thresholds

### Voice Health

- Fatigue & illness scoring
- SwiftUI Charts for trends
- Metrics comparison table
- Health indicators
- Personalized recommendations

## Transcription Engines

The app supports multiple transcription backends:

1. **whisper.cpp** (preferred) - Install via Homebrew:

   ```bash
   brew install whisper-cpp
   ```

2. **Python faster-whisper** - If already installed from PyObjC version

3. **Apple Speech** (fallback) - Uses built-in macOS speech recognition

## Migration from PyObjC Version

Settings are automatically migrated from `~/.notta_config.json` on first launch.

History is read from `~/.notta_history.json`.

## App Store Submission

1. Enable App Sandbox in entitlements
2. Add required privacy descriptions to Info.plist
3. Archive and upload via Xcode Organizer
4. Complete App Store Connect listing
