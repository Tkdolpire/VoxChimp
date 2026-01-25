# Nota

AI-powered voice dictation for macOS, designed for medical note-taking.

Hold a hotkey (or button) to record speech, release to transcribe and auto-paste at your cursor.

## Features

- **Hold-to-record**: Hold the hotkey or button to record, release to transcribe
- **Auto-paste**: Automatically pastes transcribed text at cursor position
- **Local transcription**: Uses faster-whisper (Whisper) locally - no cloud required
- **Grammar fixing**: Basic capitalization and punctuation fixes
- **History**: Saves all transcriptions with timestamps
- **Audio archiving**: Optional saving of audio recordings

## Installation

### From Pre-built App

1. Download `Nota.app` from releases
2. Move to `/Applications/`
3. Double-click to launch
4. Grant required permissions (see below)

### Build from Source

```bash
# Install dependencies
pip install pyobjc pynput pyaudio faster-whisper pyinstaller

# Build the app
pyinstaller Nota.spec

# Install
cp -R dist/Nota.app /Applications/
```

## Required Permissions

Nota requires three macOS permissions to function. Grant these in **System Settings > Privacy & Security**:

| Permission           | Location                   | Purpose                        |
| -------------------- | -------------------------- | ------------------------------ |
| **Microphone**       | Privacy > Microphone       | Record audio for transcription |
| **Input Monitoring** | Privacy > Input Monitoring | Global hotkey detection        |
| **Accessibility**    | Privacy > Accessibility    | Auto-paste via simulated Cmd+V |

After adding Nota to each list, ensure the toggle is **ON**.

## Usage

### Recording Methods

1. **Hotkey** (default: Left Option)
   - Hold the key anywhere on your Mac
   - Speak while holding
   - Release to transcribe and paste

2. **Button**
   - Click and hold the "Hold to Record" button in the Nota window
   - Release to transcribe and paste

### Window Controls

- **Settings**: View current configuration, open config file
- **History**: Open transcription history file
- **Quit**: Close the application

## Configuration

Settings are stored in `~/.nota_config.json`:

```json
{
  "whisper_backend": "small",
  "auto_paste": true,
  "fix_grammar": true,
  "save_audio": false,
  "hotkey": "alt_l"
}
```

### Options

| Setting           | Values                                            | Description                                         |
| ----------------- | ------------------------------------------------- | --------------------------------------------------- |
| `whisper_backend` | `tiny`, `small`, `medium`, `large`                | Whisper model size (larger = more accurate, slower) |
| `auto_paste`      | `true`, `false`                                   | Automatically paste after transcription             |
| `fix_grammar`     | `true`, `false`                                   | Apply basic grammar fixes                           |
| `save_audio`      | `true`, `false`                                   | Archive audio recordings to `~/.nota_audio/`        |
| `hotkey`          | `alt_l`, `alt_r`, `ctrl_l`, `ctrl_r`, `caps_lock` | Global hotkey for recording                         |

**Note**: Changes to `whisper_backend` and `hotkey` require app restart.

## Files

| Path                   | Description                            |
| ---------------------- | -------------------------------------- |
| `~/.nota_config.json`  | Configuration file                     |
| `~/.nota_history.txt`  | Simple text history (timestamp + text) |
| `~/.nota_history.json` | Detailed JSON history with metadata    |
| `~/.nota.log`          | Application log file                   |
| `~/.nota_audio/`       | Audio archive directory (if enabled)   |

## Troubleshooting

### Hotkey not working

1. Open **System Settings > Privacy & Security > Input Monitoring**
2. Add Nota.app (click +, navigate to /Applications/Nota.app)
3. Ensure the toggle is ON
4. Restart Nota

### No audio detected / silent recordings

1. Open **System Settings > Privacy & Security > Microphone**
2. Add Nota.app
3. Ensure the toggle is ON
4. Check that your microphone is not muted

### Auto-paste not working

1. Open **System Settings > Privacy & Security > Accessibility**
2. Add Nota.app
3. Ensure the toggle is ON

### App crashes on launch

Check the log file for errors:

```bash
tail -100 ~/.nota.log
```

### Model download issues

On first launch, Nota downloads the Whisper model from Hugging Face. If this fails:

- Check your internet connection
- The model is cached in `~/.cache/huggingface/`

## Tech Stack

- **Language**: Python 3.9+
- **UI Framework**: PyObjC (native macOS Cocoa)
- **Audio**: PyAudio
- **Transcription**: faster-whisper (CTranslate2-optimized Whisper)
- **Hotkeys**: pynput
- **Build**: PyInstaller

## License

MIT
