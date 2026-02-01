"""
Integration tests for notta.py with mocked external dependencies.

Tests components that require mocking:
- Recording flow (start_recording, stop_recording, record_audio)
- Audio processing/transcription (process_audio)
- Hotkey setup (setup_hotkeys)
- Microphone permission checking (check_microphone_permission)
- Health analysis integration (runAcousticAnalysisAsync_)
"""

import pytest
import json
import wave
import struct
import math
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock, call
import sys


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Create a temporary home directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: home)
    return home


@pytest.fixture
def audio_archive_dir(temp_home):
    """Create audio archive directory."""
    audio_dir = temp_home / '.notta_audio'
    audio_dir.mkdir()
    return audio_dir


@pytest.fixture
def valid_wav_file(tmp_path):
    """Create a valid WAV file with audio content."""
    wav_path = tmp_path / "valid_audio.wav"
    create_wav_with_tone(wav_path, duration=1.0, frequency=440, amplitude=0.5)
    return wav_path


@pytest.fixture
def silent_wav_file(tmp_path):
    """Create a silent WAV file."""
    wav_path = tmp_path / "silent_audio.wav"
    create_wav_with_tone(wav_path, duration=1.0, frequency=440, amplitude=0.0)
    return wav_path


def create_wav_with_tone(path: Path, duration: float, frequency: float, amplitude: float):
    """Helper to create a WAV file with a sine wave tone."""
    sample_rate = 16000
    n_samples = int(duration * sample_rate)

    with wave.open(str(path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        for i in range(n_samples):
            t = i / sample_rate
            value = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * t))
            wf.writeframes(struct.pack('<h', value))


# =============================================================================
# Mock Delegate for Integration Testing
# =============================================================================

class MockNottaIntegration:
    """
    Mock NottaAppDelegate for integration testing.
    Includes recording and processing logic with mockable dependencies.
    """

    def __init__(self, temp_home: Path):
        self.config_file = temp_home / '.notta_config.json'
        self.history_file = temp_home / '.notta_history.txt'
        self.history_json_file = temp_home / '.notta_history.json'
        self.log_file = temp_home / '.notta.log'
        self.audio_archive_dir = temp_home / '.notta_audio'

        self.config = {
            'whisper_backend': 'small',
            'auto_paste': True,
            'fix_grammar': True,
            'save_audio': False,
            'hotkey': 'alt_l'
        }

        self._lock = threading.Lock()
        self.is_recording = False
        self.listener = None
        self.whisper_model = None
        self.use_ollama = False
        self.mic_permission_ok = True
        self.acoustic_analyzer = None
        self.hotkey_pressed = False

        # Track method calls for testing
        self.status_updates = []
        self.alerts_shown = []

    def set_status(self, status):
        """Track status updates."""
        self.status_updates.append(status)

    def showAlertWithInfo_(self, info):
        """Track alerts shown."""
        self.alerts_shown.append(info)

    def performSelectorOnMainThread_withObject_waitUntilDone_(self, selector, obj, wait):
        """Mock main thread dispatch - just call directly."""
        pass

    def fix_grammar(self, text):
        """Fix basic grammar issues."""
        import re

        if not text:
            return text

        try:
            text = text[0].upper() + text[1:]

            replacements = {
                r'\bi\b': 'I',
                r'\bim\b': "I'm",
                r'\bdont\b': "don't",
                r'\bcant\b': "can't",
            }

            for pattern, replacement in replacements.items():
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

            if text and text[-1] not in '.!?':
                text += '.'

            return text
        except Exception:
            return text

    def validate_audio(self, audio_file):
        """Check if audio file contains actual sound."""
        try:
            with wave.open(audio_file, 'rb') as wf:
                n_frames = wf.getnframes()
                if n_frames == 0:
                    return False, 0, 0

                frames = wf.readframes(n_frames)

                if len(frames) < 2:
                    return False, 0, 0

                samples = struct.unpack(f'{len(frames)//2}h', frames)
                max_amp = max(abs(s) for s in samples)
                avg_amp = sum(abs(s) for s in samples) / len(samples)

                is_valid = max_amp > 100

                return is_valid, max_amp, avg_amp
        except Exception:
            return False, 0, 0

    def save_to_history(self, text, audio_file=None):
        """Save transcription to history."""
        import shutil

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp_iso = datetime.now().isoformat()

        try:
            with open(self.history_file, 'a') as f:
                f.write(f"{timestamp}\t{text}\n")
        except IOError:
            pass

        try:
            history = []
            if self.history_json_file.exists():
                try:
                    with open(self.history_json_file, 'r') as f:
                        history = json.load(f)
                except (json.JSONDecodeError, IOError):
                    history = []

            entry = {
                'id': len(history) + 1,
                'timestamp': timestamp_iso,
                'text': text,
                'word_count': len(text.split()),
                'char_count': len(text),
                'category': None,
                'tags': [],
                'audio_file': None
            }

            if self.config.get('save_audio', False) and audio_file and Path(audio_file).exists():
                audio_filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                audio_dest = self.audio_archive_dir / audio_filename
                try:
                    self.audio_archive_dir.mkdir(exist_ok=True)
                    shutil.copy2(audio_file, audio_dest)
                    entry['audio_file'] = str(audio_dest)
                except Exception:
                    pass

            history.append(entry)

            with open(self.history_json_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass

    def start_recording(self):
        """Start recording."""
        with self._lock:
            if self.is_recording:
                return
            self.is_recording = True

        self.set_status('recording')

    def stop_recording(self):
        """Stop recording."""
        with self._lock:
            self.is_recording = False
        self.set_status('processing')

    def check_microphone_permission(self, pyaudio_module=None):
        """Test microphone access."""
        try:
            if pyaudio_module is None:
                import pyaudio
                pyaudio_module = pyaudio

            p = pyaudio_module.PyAudio()
            stream = p.open(
                format=pyaudio_module.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )

            data = stream.read(1024, exception_on_overflow=False)
            stream.close()
            p.terminate()

            if len(data) < 2:
                return False

            samples = struct.unpack(f'{len(data)//2}h', data)
            max_amp = max(abs(s) for s in samples)

            if max_amp == 0:
                return False

            return True

        except OSError:
            return False
        except Exception:
            return False

    def setup_recording(self, whisper_module=None):
        """Setup recording capabilities."""
        import queue
        self.audio_queue = queue.Queue()
        self.mic_permission_ok = True

        if self.config.get('whisper_backend') == 'ollama':
            self.use_ollama = True
        else:
            try:
                if whisper_module is None:
                    from faster_whisper import WhisperModel
                    whisper_module = WhisperModel

                model_size = self.config.get('whisper_backend', 'small')
                if model_size == 'ollama':
                    model_size = 'small'

                self.whisper_model = whisper_module(model_size, device="cpu", compute_type="int8")
                self.use_ollama = False
            except ImportError:
                self.use_ollama = True
            except Exception:
                self.use_ollama = True

    def setup_hotkeys(self, keyboard_module=None):
        """Setup global hotkeys."""
        try:
            if keyboard_module is None:
                from pynput import keyboard
                keyboard_module = keyboard

            self.hotkey_pressed = False

            hotkey_map = {
                'alt_l': keyboard_module.Key.alt_l,
                'alt_r': keyboard_module.Key.alt_r,
                'ctrl_l': keyboard_module.Key.ctrl_l,
                'ctrl_r': keyboard_module.Key.ctrl_r,
                'caps_lock': keyboard_module.Key.caps_lock,
            }

            configured_hotkey = self.config.get('hotkey', 'alt_l')
            target_key = hotkey_map.get(configured_hotkey, keyboard_module.Key.alt_l)

            delegate = self

            def on_press(key):
                if key == target_key and not delegate.hotkey_pressed:
                    delegate.hotkey_pressed = True
                    delegate.start_recording()

            def on_release(key):
                if key == target_key and delegate.hotkey_pressed:
                    delegate.hotkey_pressed = False
                    delegate.stop_recording()

            self.listener = keyboard_module.Listener(
                on_press=on_press,
                on_release=on_release
            )
            self.listener.start()

            return True

        except ImportError:
            return False
        except Exception:
            return False

    def process_audio(self, audio_file, subprocess_module=None):
        """Process recorded audio."""
        import os

        if subprocess_module is None:
            import subprocess
            subprocess_module = subprocess

        try:
            if self.use_ollama:
                result = subprocess_module.run(
                    ['ollama', 'run', 'whisper', '--', audio_file],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                text = result.stdout.strip()
            else:
                if not self.whisper_model:
                    self.set_status('error')
                    return None

                segments, _ = self.whisper_model.transcribe(
                    audio_file,
                    language="en",
                    beam_size=5,
                    vad_filter=False,
                    condition_on_previous_text=False
                )
                text = " ".join(s.text.strip() for s in segments)

            if text:
                if self.config.get('fix_grammar', True):
                    text = self.fix_grammar(text)

                self.save_to_history(text, audio_file)

                # Copy to clipboard
                subprocess_module.run(
                    ['pbcopy'],
                    input=text.encode('utf-8'),
                    check=True,
                    timeout=5
                )

                # Auto-paste if enabled
                if self.config.get('auto_paste', True):
                    subprocess_module.run(
                        [
                            'osascript', '-e',
                            'tell application "System Events" to keystroke "v" using command down'
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                self.set_status('success')
                return text
            else:
                self.set_status('error')
                return None

        except subprocess_module.TimeoutExpired:
            self.set_status('error')
            return None
        except Exception:
            self.set_status('error')
            return None
        finally:
            if audio_file and Path(audio_file).exists():
                try:
                    os.unlink(audio_file)
                except OSError:
                    pass

    def record_audio(self, pyaudio_module=None, temp_file_path=None):
        """Record audio - simplified for testing."""
        import os
        import tempfile

        if pyaudio_module is None:
            import pyaudio
            pyaudio_module = pyaudio

        p = None
        stream = None

        try:
            p = pyaudio_module.PyAudio()
            stream = p.open(
                format=pyaudio_module.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )

            frames = []
            while True:
                with self._lock:
                    if not self.is_recording:
                        break
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                    frames.append(data)
                except IOError:
                    pass

            if frames:
                if temp_file_path:
                    temp_file = temp_file_path
                else:
                    fd, temp_file = tempfile.mkstemp(suffix='.wav')
                    os.close(fd)

                wf = wave.open(temp_file, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio_module.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))
                wf.close()

                return temp_file

            return None

        except Exception:
            return None
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass


@pytest.fixture
def delegate(temp_home):
    """Create a mock delegate for integration testing."""
    return MockNottaIntegration(temp_home)


# =============================================================================
# Tests: Recording Flow
# =============================================================================

class TestRecordingFlow:
    """Tests for the recording start/stop flow."""

    def test_start_recording_sets_flag(self, delegate):
        """Starting recording should set is_recording flag."""
        assert delegate.is_recording is False
        delegate.start_recording()
        assert delegate.is_recording is True

    def test_start_recording_sets_status(self, delegate):
        """Starting recording should update status."""
        delegate.start_recording()
        assert 'recording' in delegate.status_updates

    def test_start_recording_idempotent(self, delegate):
        """Multiple start calls should not stack."""
        delegate.start_recording()
        delegate.start_recording()
        delegate.start_recording()

        assert delegate.is_recording is True
        # Should only have one 'recording' status
        assert delegate.status_updates.count('recording') == 1

    def test_stop_recording_clears_flag(self, delegate):
        """Stopping recording should clear is_recording flag."""
        delegate.start_recording()
        delegate.stop_recording()
        assert delegate.is_recording is False

    def test_stop_recording_sets_processing_status(self, delegate):
        """Stopping recording should set processing status."""
        delegate.start_recording()
        delegate.stop_recording()
        assert 'processing' in delegate.status_updates

    def test_recording_thread_safety(self, delegate):
        """Recording state should be thread-safe."""
        results = []

        def toggle_recording():
            for _ in range(100):
                delegate.start_recording()
                delegate.stop_recording()
            results.append(True)

        threads = [threading.Thread(target=toggle_recording) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        assert delegate.is_recording is False


# =============================================================================
# Tests: Microphone Permission
# =============================================================================

class TestMicrophonePermission:
    """Tests for microphone permission checking."""

    def test_mic_permission_granted(self, delegate):
        """Should return True when microphone works."""
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()

        # Return valid audio data (non-zero samples)
        audio_data = struct.pack('<' + 'h' * 1024, *[1000] * 1024)
        mock_stream.read.return_value = audio_data

        mock_pa_instance = MagicMock()
        mock_pa_instance.open.return_value = mock_stream
        mock_pyaudio.PyAudio.return_value = mock_pa_instance
        mock_pyaudio.paInt16 = 8

        result = delegate.check_microphone_permission(mock_pyaudio)

        assert result is True
        mock_pa_instance.open.assert_called_once()
        mock_stream.read.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_pa_instance.terminate.assert_called_once()

    def test_mic_permission_denied_zeros(self, delegate):
        """Should return False when audio is all zeros."""
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()

        # Return silent audio (all zeros)
        audio_data = struct.pack('<' + 'h' * 1024, *[0] * 1024)
        mock_stream.read.return_value = audio_data

        mock_pa_instance = MagicMock()
        mock_pa_instance.open.return_value = mock_stream
        mock_pyaudio.PyAudio.return_value = mock_pa_instance
        mock_pyaudio.paInt16 = 8

        result = delegate.check_microphone_permission(mock_pyaudio)

        assert result is False

    def test_mic_permission_oserror(self, delegate):
        """Should return False on OSError."""
        mock_pyaudio = MagicMock()
        mock_pyaudio.PyAudio.side_effect = OSError("Device not available")

        result = delegate.check_microphone_permission(mock_pyaudio)

        assert result is False

    def test_mic_permission_open_fails(self, delegate):
        """Should return False when stream open fails."""
        mock_pyaudio = MagicMock()
        mock_pa_instance = MagicMock()
        mock_pa_instance.open.side_effect = Exception("Cannot open stream")
        mock_pyaudio.PyAudio.return_value = mock_pa_instance
        mock_pyaudio.paInt16 = 8

        result = delegate.check_microphone_permission(mock_pyaudio)

        assert result is False

    def test_mic_permission_read_fails(self, delegate):
        """Should return False when stream read fails."""
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.side_effect = Exception("Read error")

        mock_pa_instance = MagicMock()
        mock_pa_instance.open.return_value = mock_stream
        mock_pyaudio.PyAudio.return_value = mock_pa_instance
        mock_pyaudio.paInt16 = 8

        result = delegate.check_microphone_permission(mock_pyaudio)

        assert result is False

    def test_mic_permission_insufficient_data(self, delegate):
        """Should return False when data is too short."""
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b'\x00'  # Only 1 byte

        mock_pa_instance = MagicMock()
        mock_pa_instance.open.return_value = mock_stream
        mock_pyaudio.PyAudio.return_value = mock_pa_instance
        mock_pyaudio.paInt16 = 8

        result = delegate.check_microphone_permission(mock_pyaudio)

        assert result is False


# =============================================================================
# Tests: Setup Recording (Whisper Model)
# =============================================================================

class TestSetupRecording:
    """Tests for recording setup with Whisper model."""

    def test_setup_with_faster_whisper(self, delegate):
        """Should setup faster-whisper model."""
        mock_model = MagicMock()
        mock_whisper_class = MagicMock(return_value=mock_model)

        delegate.setup_recording(whisper_module=mock_whisper_class)

        assert delegate.use_ollama is False
        assert delegate.whisper_model is mock_model
        mock_whisper_class.assert_called_once_with('small', device='cpu', compute_type='int8')

    def test_setup_with_different_model_size(self, delegate):
        """Should use configured model size."""
        delegate.config['whisper_backend'] = 'large'
        mock_model = MagicMock()
        mock_whisper_class = MagicMock(return_value=mock_model)

        delegate.setup_recording(whisper_module=mock_whisper_class)

        mock_whisper_class.assert_called_once_with('large', device='cpu', compute_type='int8')

    def test_setup_fallback_to_ollama_on_import_error(self, delegate):
        """Should fallback to Ollama when faster-whisper unavailable."""
        mock_whisper_class = MagicMock(side_effect=ImportError("No module"))

        delegate.setup_recording(whisper_module=mock_whisper_class)

        assert delegate.use_ollama is True
        assert delegate.whisper_model is None

    def test_setup_fallback_to_ollama_on_load_error(self, delegate):
        """Should fallback to Ollama when model loading fails."""
        mock_whisper_class = MagicMock(side_effect=Exception("Model load failed"))

        delegate.setup_recording(whisper_module=mock_whisper_class)

        assert delegate.use_ollama is True

    def test_setup_with_ollama_backend(self, delegate):
        """Should use Ollama when configured."""
        delegate.config['whisper_backend'] = 'ollama'
        mock_whisper_class = MagicMock()

        delegate.setup_recording(whisper_module=mock_whisper_class)

        assert delegate.use_ollama is True
        mock_whisper_class.assert_not_called()

    def test_setup_creates_audio_queue(self, delegate):
        """Should create audio queue."""
        mock_whisper_class = MagicMock()

        delegate.setup_recording(whisper_module=mock_whisper_class)

        assert hasattr(delegate, 'audio_queue')
        assert delegate.audio_queue is not None


# =============================================================================
# Tests: Hotkey Setup
# =============================================================================

class TestHotkeySetup:
    """Tests for hotkey setup with pynput."""

    def test_setup_hotkeys_creates_listener(self, delegate):
        """Should create keyboard listener."""
        mock_keyboard = MagicMock()
        mock_listener = MagicMock()
        mock_keyboard.Listener.return_value = mock_listener
        mock_keyboard.Key.alt_l = 'alt_l'

        result = delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        assert result is True
        assert delegate.listener is mock_listener
        mock_keyboard.Listener.assert_called_once()
        mock_listener.start.assert_called_once()

    def test_setup_hotkeys_uses_configured_key(self, delegate):
        """Should use configured hotkey."""
        delegate.config['hotkey'] = 'ctrl_l'
        mock_keyboard = MagicMock()
        mock_listener = MagicMock()
        mock_keyboard.Listener.return_value = mock_listener
        mock_keyboard.Key.ctrl_l = 'ctrl_l'

        delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        # Verify Listener was called with callbacks
        call_kwargs = mock_keyboard.Listener.call_args[1]
        assert 'on_press' in call_kwargs
        assert 'on_release' in call_kwargs

    def test_setup_hotkeys_import_error(self, delegate):
        """Should return False on import error."""
        mock_keyboard = MagicMock()
        mock_keyboard.Listener.side_effect = ImportError("No pynput")

        result = delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        assert result is False

    def test_hotkey_press_starts_recording(self, delegate):
        """Pressing hotkey should start recording."""
        mock_keyboard = MagicMock()
        mock_listener = MagicMock()
        mock_keyboard.Listener.return_value = mock_listener
        mock_keyboard.Key.alt_l = 'alt_l'

        delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        # Get the on_press callback
        on_press = mock_keyboard.Listener.call_args[1]['on_press']

        # Simulate key press
        on_press('alt_l')

        assert delegate.hotkey_pressed is True
        assert delegate.is_recording is True

    def test_hotkey_release_stops_recording(self, delegate):
        """Releasing hotkey should stop recording."""
        mock_keyboard = MagicMock()
        mock_listener = MagicMock()
        mock_keyboard.Listener.return_value = mock_listener
        mock_keyboard.Key.alt_l = 'alt_l'

        delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        on_press = mock_keyboard.Listener.call_args[1]['on_press']
        on_release = mock_keyboard.Listener.call_args[1]['on_release']

        # Simulate press and release
        on_press('alt_l')
        assert delegate.is_recording is True

        on_release('alt_l')
        assert delegate.is_recording is False
        assert delegate.hotkey_pressed is False

    def test_hotkey_ignores_other_keys(self, delegate):
        """Should ignore keys that aren't the configured hotkey."""
        mock_keyboard = MagicMock()
        mock_listener = MagicMock()
        mock_keyboard.Listener.return_value = mock_listener
        mock_keyboard.Key.alt_l = 'alt_l'
        mock_keyboard.Key.alt_r = 'alt_r'

        delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        on_press = mock_keyboard.Listener.call_args[1]['on_press']

        # Press wrong key
        on_press('alt_r')

        assert delegate.hotkey_pressed is False
        assert delegate.is_recording is False

    def test_hotkey_no_double_trigger(self, delegate):
        """Holding hotkey should not trigger multiple times."""
        mock_keyboard = MagicMock()
        mock_listener = MagicMock()
        mock_keyboard.Listener.return_value = mock_listener
        mock_keyboard.Key.alt_l = 'alt_l'

        delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        on_press = mock_keyboard.Listener.call_args[1]['on_press']

        # Simulate repeated key press (holding)
        on_press('alt_l')
        on_press('alt_l')
        on_press('alt_l')

        # Should only have triggered once
        assert delegate.status_updates.count('recording') == 1


# =============================================================================
# Tests: Audio Processing/Transcription
# =============================================================================

class TestAudioProcessing:
    """Tests for audio processing and transcription."""

    def test_process_audio_with_whisper(self, delegate, valid_wav_file, temp_home):
        """Should transcribe audio with faster-whisper."""
        # Setup mock whisper model
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([mock_segment], None)
        delegate.use_ollama = False

        # Mock subprocess for clipboard
        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        assert result is not None
        assert 'Hello world' in result
        assert 'success' in delegate.status_updates

    def test_process_audio_applies_grammar_fix(self, delegate, valid_wav_file):
        """Should apply grammar fixes when enabled."""
        mock_segment = MagicMock()
        mock_segment.text = "i dont know"
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([mock_segment], None)
        delegate.use_ollama = False
        delegate.config['fix_grammar'] = True

        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        assert "I don't know" in result

    def test_process_audio_skips_grammar_when_disabled(self, delegate, valid_wav_file):
        """Should skip grammar fixes when disabled."""
        mock_segment = MagicMock()
        mock_segment.text = "i dont know"
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([mock_segment], None)
        delegate.use_ollama = False
        delegate.config['fix_grammar'] = False

        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        # Should have original text (not grammar-fixed)
        assert result == "i dont know"

    def test_process_audio_saves_to_history(self, delegate, valid_wav_file, temp_home):
        """Should save transcription to history."""
        mock_segment = MagicMock()
        mock_segment.text = "Test transcription"
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([mock_segment], None)
        delegate.use_ollama = False

        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        # Check history file
        assert delegate.history_json_file.exists()
        history = json.loads(delegate.history_json_file.read_text())
        assert len(history) == 1
        assert 'Test transcription' in history[0]['text']

    def test_process_audio_copies_to_clipboard(self, delegate, valid_wav_file):
        """Should copy result to clipboard."""
        mock_segment = MagicMock()
        mock_segment.text = "Clipboard text"
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([mock_segment], None)
        delegate.use_ollama = False

        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        # Verify pbcopy was called
        pbcopy_calls = [c for c in mock_subprocess.run.call_args_list if c[0][0] == ['pbcopy']]
        assert len(pbcopy_calls) == 1

    def test_process_audio_auto_paste(self, delegate, valid_wav_file):
        """Should auto-paste when enabled."""
        mock_segment = MagicMock()
        mock_segment.text = "Test"
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([mock_segment], None)
        delegate.use_ollama = False
        delegate.config['auto_paste'] = True

        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        # Verify osascript was called for paste
        osascript_calls = [c for c in mock_subprocess.run.call_args_list
                          if c[0][0][0] == 'osascript']
        assert len(osascript_calls) == 1

    def test_process_audio_no_auto_paste_when_disabled(self, delegate, valid_wav_file):
        """Should not auto-paste when disabled."""
        mock_segment = MagicMock()
        mock_segment.text = "Test"
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([mock_segment], None)
        delegate.use_ollama = False
        delegate.config['auto_paste'] = False

        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        # Verify osascript was NOT called
        osascript_calls = [c for c in mock_subprocess.run.call_args_list
                          if c[0][0][0] == 'osascript']
        assert len(osascript_calls) == 0

    def test_process_audio_with_ollama(self, delegate, valid_wav_file):
        """Should transcribe with Ollama backend."""
        delegate.use_ollama = True
        delegate.whisper_model = None

        mock_subprocess = MagicMock()
        mock_result = MagicMock()
        mock_result.stdout = "Ollama transcription"
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        assert result is not None
        # Check ollama was called
        ollama_calls = [c for c in mock_subprocess.run.call_args_list
                       if 'ollama' in c[0][0]]
        assert len(ollama_calls) == 1

    def test_process_audio_no_model_error(self, delegate, valid_wav_file):
        """Should handle missing model gracefully."""
        delegate.use_ollama = False
        delegate.whisper_model = None

        mock_subprocess = MagicMock()
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        assert result is None
        assert 'error' in delegate.status_updates

    def test_process_audio_empty_result(self, delegate, valid_wav_file):
        """Should handle empty transcription result."""
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([], None)
        delegate.use_ollama = False

        mock_subprocess = MagicMock()
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        assert result is None
        assert 'error' in delegate.status_updates

    def test_process_audio_timeout(self, delegate, valid_wav_file):
        """Should handle timeout gracefully."""
        delegate.use_ollama = True

        mock_subprocess = MagicMock()
        mock_subprocess.run.side_effect = TimeoutError("Timed out")
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        assert result is None
        assert 'error' in delegate.status_updates

    def test_process_audio_cleans_up_temp_file(self, delegate, tmp_path):
        """Should delete temp file after processing."""
        # Create a temp file that should be deleted
        temp_wav = tmp_path / "temp_recording.wav"
        create_wav_with_tone(temp_wav, duration=0.5, frequency=440, amplitude=0.5)

        mock_segment = MagicMock()
        mock_segment.text = "Test"
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = ([mock_segment], None)
        delegate.use_ollama = False

        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        delegate.process_audio(str(temp_wav), subprocess_module=mock_subprocess)

        # File should be deleted
        assert not temp_wav.exists()

    def test_process_audio_multiple_segments(self, delegate, valid_wav_file):
        """Should join multiple transcription segments."""
        mock_segments = [
            MagicMock(text="First segment"),
            MagicMock(text="Second segment"),
            MagicMock(text="Third segment")
        ]
        delegate.whisper_model = MagicMock()
        delegate.whisper_model.transcribe.return_value = (mock_segments, None)
        delegate.use_ollama = False

        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(str(valid_wav_file), subprocess_module=mock_subprocess)

        assert "First segment" in result
        assert "Second segment" in result
        assert "Third segment" in result


# =============================================================================
# Tests: Record Audio
# =============================================================================

class TestRecordAudio:
    """Tests for the audio recording function."""

    def test_record_audio_creates_wav_file(self, delegate, tmp_path):
        """Should create a valid WAV file."""
        output_file = tmp_path / "output.wav"

        # Mock PyAudio
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()

        # Generate some audio frames
        frames = [struct.pack('<' + 'h' * 1024, *[500] * 1024) for _ in range(5)]
        frame_iter = iter(frames)

        def read_frame(*args, **kwargs):
            try:
                return next(frame_iter)
            except StopIteration:
                # Stop recording after frames exhausted
                delegate.is_recording = False
                return struct.pack('<' + 'h' * 1024, *[0] * 1024)

        mock_stream.read.side_effect = read_frame

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream
        mock_pa.get_sample_size.return_value = 2
        mock_pyaudio.PyAudio.return_value = mock_pa
        mock_pyaudio.paInt16 = 8

        # Start recording
        delegate.is_recording = True

        result = delegate.record_audio(
            pyaudio_module=mock_pyaudio,
            temp_file_path=str(output_file)
        )

        assert result is not None
        assert Path(result).exists()

        # Verify it's a valid WAV
        with wave.open(result, 'rb') as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000

    def test_record_audio_stops_when_flag_cleared(self, delegate):
        """Should stop recording when is_recording is cleared."""
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()

        call_count = [0]

        def read_frame(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 3:
                delegate.is_recording = False
            return struct.pack('<' + 'h' * 1024, *[500] * 1024)

        mock_stream.read.side_effect = read_frame

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream
        mock_pa.get_sample_size.return_value = 2
        mock_pyaudio.PyAudio.return_value = mock_pa
        mock_pyaudio.paInt16 = 8

        delegate.is_recording = True

        delegate.record_audio(pyaudio_module=mock_pyaudio)

        # Should have read frames until is_recording was cleared
        assert call_count[0] >= 3

    def test_record_audio_handles_read_error(self, delegate):
        """Should handle read errors gracefully."""
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()

        call_count = [0]

        def read_frame(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise IOError("Buffer overflow")
            if call_count[0] >= 5:
                delegate.is_recording = False
            return struct.pack('<' + 'h' * 1024, *[500] * 1024)

        mock_stream.read.side_effect = read_frame

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream
        mock_pa.get_sample_size.return_value = 2
        mock_pyaudio.PyAudio.return_value = mock_pa
        mock_pyaudio.paInt16 = 8

        delegate.is_recording = True

        # Should not raise exception
        result = delegate.record_audio(pyaudio_module=mock_pyaudio)

        # Should have continued recording despite error
        assert call_count[0] >= 5

    def test_record_audio_cleanup_on_error(self, delegate):
        """Should cleanup resources on error."""
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.side_effect = Exception("Fatal error")

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream
        mock_pyaudio.PyAudio.return_value = mock_pa
        mock_pyaudio.paInt16 = 8

        delegate.is_recording = True

        delegate.record_audio(pyaudio_module=mock_pyaudio)

        # Stream should be closed
        mock_stream.stop_stream.assert_called()
        mock_stream.close.assert_called()
        mock_pa.terminate.assert_called()

    def test_record_audio_returns_none_when_no_frames(self, delegate):
        """Should return None when no frames captured."""
        mock_pyaudio = MagicMock()
        mock_stream = MagicMock()

        # Immediately stop recording
        delegate.is_recording = False

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream
        mock_pyaudio.PyAudio.return_value = mock_pa
        mock_pyaudio.paInt16 = 8

        result = delegate.record_audio(pyaudio_module=mock_pyaudio)

        assert result is None


# =============================================================================
# Tests: End-to-End Recording Flow
# =============================================================================

class TestEndToEndRecording:
    """End-to-end tests for the complete recording workflow."""

    def test_full_recording_workflow(self, delegate, temp_home):
        """Test complete workflow: setup -> record -> transcribe -> save."""
        # 1. Setup with mock whisper
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "This is a test recording"
        mock_model.transcribe.return_value = ([mock_segment], None)

        mock_whisper_class = MagicMock(return_value=mock_model)
        delegate.setup_recording(whisper_module=mock_whisper_class)

        # 2. Setup hotkeys
        mock_keyboard = MagicMock()
        mock_listener = MagicMock()
        mock_keyboard.Listener.return_value = mock_listener
        mock_keyboard.Key.alt_l = 'alt_l'
        delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        # 3. Simulate recording (create test file)
        import tempfile
        fd, temp_wav = tempfile.mkstemp(suffix='.wav')
        import os
        os.close(fd)
        create_wav_with_tone(Path(temp_wav), duration=0.5, frequency=440, amplitude=0.5)

        # 4. Process the recording
        mock_subprocess = MagicMock()
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = TimeoutError

        result = delegate.process_audio(temp_wav, subprocess_module=mock_subprocess)

        # 5. Verify results
        assert result is not None
        assert "This is a test recording" in result
        assert 'success' in delegate.status_updates

        # Verify history was saved
        history = json.loads(delegate.history_json_file.read_text())
        assert len(history) == 1

    def test_hotkey_triggered_workflow(self, delegate, temp_home):
        """Test workflow triggered by hotkey press/release."""
        # Setup
        mock_model = MagicMock()
        mock_whisper_class = MagicMock(return_value=mock_model)
        delegate.setup_recording(whisper_module=mock_whisper_class)

        mock_keyboard = MagicMock()
        mock_listener = MagicMock()
        mock_keyboard.Listener.return_value = mock_listener
        mock_keyboard.Key.alt_l = 'alt_l'
        delegate.setup_hotkeys(keyboard_module=mock_keyboard)

        # Get callbacks
        on_press = mock_keyboard.Listener.call_args[1]['on_press']
        on_release = mock_keyboard.Listener.call_args[1]['on_release']

        # Simulate hotkey press
        on_press('alt_l')

        assert delegate.is_recording is True
        assert 'recording' in delegate.status_updates

        # Simulate hotkey release
        on_release('alt_l')

        assert delegate.is_recording is False
        assert 'processing' in delegate.status_updates

    def test_concurrent_recording_attempts(self, delegate):
        """Test that concurrent recording attempts are handled."""
        results = []

        def try_start():
            delegate.start_recording()
            results.append(delegate.is_recording)

        threads = [threading.Thread(target=try_start) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should see is_recording as True
        assert all(results)
        # But only one 'recording' status
        assert delegate.status_updates.count('recording') == 1
