# Changelog

All notable changes to Notta will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-02-01

### Added

- **Post-transcription translation** using Apple Translation framework
- **WhisperKit integration** for on-device transcription with model selection
- **Apple Speech fallback** when Whisper model is not yet downloaded
- **Menu bar status item** with chimp mascot for quick access
- **Model loading indicator** with progress feedback during downloads
- **Voice health dashboard** with real-time acoustic analysis (HEAR integration)
- **Health notifications** for voice biomarker alerts
- **Audio level indicator** showing microphone input in real-time
- **Comprehensive test suite** with 286 tests covering core functionality
- **Licensing system** supporting App Store and Direct distribution builds
- **Sparkle update framework** for automatic updates (Direct distribution)

### Changed

- **Complete UI redesign** with warm theme and modern aesthetics
- **New app icon** featuring the chimp mascot
- **Modernized interface** with vibrancy effects and SF Symbols
- **Improved error recovery** with graceful degradation on failures

### Fixed

- Race conditions in model download flow
- WhisperKit model naming and cache scanning issues
- Toolbar button functionality
- Health window crash on launch
- Baseline accumulation bug in health analysis

## [1.0.0] - 2026-01-15

### Added

- Initial release of Notta voice dictation
- Hold-to-record with configurable hotkey (Option, Control, Caps Lock)
- Local Whisper transcription (tiny/small/medium/large models)
- Auto-paste transcribed text at cursor position
- Basic grammar fixing (capitalization, punctuation)
- Transcription history with JSON export
- Optional audio archiving
- Native macOS UI with PyObjC
- Comprehensive logging with rotation

[2.0.0]: https://github.com/tyrondolpire/notta/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/tyrondolpire/notta/releases/tag/v1.0.0
