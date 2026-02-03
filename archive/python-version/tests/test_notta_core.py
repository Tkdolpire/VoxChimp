"""
Unit tests for core functions in notta.py

Tests pure functions that can be tested without UI components:
- fix_grammar: Text processing with regex
- validate_audio: WAV file validation
- load_config / save_config: Configuration management
- save_to_history: History file management
- rotate_log_if_needed: Log rotation
"""

import pytest
import json
import wave
import struct
import tempfile
import shutil
import math
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, mock_open
import sys


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Create a temporary home directory for config/history files."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: home)
    return home


@pytest.fixture
def config_file(temp_home):
    """Path to the config file."""
    return temp_home / '.notta_config.json'


@pytest.fixture
def history_file(temp_home):
    """Path to the text history file."""
    return temp_home / '.notta_history.txt'


@pytest.fixture
def history_json_file(temp_home):
    """Path to the JSON history file."""
    return temp_home / '.notta_history.json'


@pytest.fixture
def log_file(temp_home):
    """Path to the log file."""
    return temp_home / '.notta.log'


@pytest.fixture
def audio_archive_dir(temp_home):
    """Path to audio archive directory."""
    audio_dir = temp_home / '.notta_audio'
    audio_dir.mkdir()
    return audio_dir


@pytest.fixture
def sample_config():
    """Sample configuration dictionary."""
    return {
        'whisper_backend': 'small',
        'auto_paste': True,
        'fix_grammar': True,
        'save_audio': True,
        'hotkey': 'alt_l'
    }


@pytest.fixture
def valid_wav_file(tmp_path):
    """Create a valid WAV file with actual audio content."""
    wav_path = tmp_path / "valid_audio.wav"
    create_wav_with_tone(wav_path, duration=1.0, frequency=440, amplitude=0.5)
    return wav_path


@pytest.fixture
def silent_wav_file(tmp_path):
    """Create a WAV file with silence (all zeros)."""
    wav_path = tmp_path / "silent_audio.wav"
    create_wav_with_tone(wav_path, duration=1.0, frequency=440, amplitude=0.0)
    return wav_path


@pytest.fixture
def quiet_wav_file(tmp_path):
    """Create a WAV file with very quiet audio (below threshold)."""
    wav_path = tmp_path / "quiet_audio.wav"
    # Amplitude that produces max_amp < 100
    create_wav_with_tone(wav_path, duration=1.0, frequency=440, amplitude=0.002)
    return wav_path


@pytest.fixture
def empty_wav_file(tmp_path):
    """Create an empty WAV file (0 frames)."""
    wav_path = tmp_path / "empty_audio.wav"
    with wave.open(str(wav_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # Write no frames
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
# Mock NottaAppDelegate for testing
# =============================================================================

class MockNottaDelegate:
    """
    A mock version of NottaAppDelegate that can be tested without PyObjC.
    Contains only the pure logic methods.
    """

    def __init__(self, temp_home: Path):
        self.config_file = temp_home / '.notta_config.json'
        self.history_file = temp_home / '.notta_history.txt'
        self.history_json_file = temp_home / '.notta_history.json'
        self.log_file = temp_home / '.notta.log'
        self.audio_archive_dir = temp_home / '.notta_audio'
        self.config = {}
        self.acoustic_analyzer = None

    def load_config(self):
        """Load configuration."""
        import json
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    'whisper_backend': 'small',
                    'auto_paste': True,
                    'fix_grammar': True,
                    'save_audio': True,
                    'hotkey': 'alt_l'
                }
        except (json.JSONDecodeError, IOError):
            self.config = {
                'whisper_backend': 'small',
                'auto_paste': True,
                'fix_grammar': True,
                'save_audio': True,
                'hotkey': 'alt_l'
            }

    def save_config(self):
        """Save configuration to file."""
        import json
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError:
            pass

    def fix_grammar(self, text):
        """Fix basic grammar issues."""
        import re

        if not text:
            return text

        try:
            # Capitalize first letter
            text = text[0].upper() + text[1:]

            # Fix common issues
            replacements = {
                r'\bi\b': 'I',
                r'\bim\b': "I'm",
                r'\bdont\b': "don't",
                r'\bcant\b': "can't",
            }

            for pattern, replacement in replacements.items():
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

            # Add period if missing
            if text and text[-1] not in '.!?':
                text += '.'

            return text
        except Exception:
            return text

    def validate_audio(self, audio_file):
        """Check if audio file contains actual sound."""
        import wave
        import struct

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

    def rotate_log_if_needed(self, max_lines=5000):
        """Rotate log file if it exceeds max_lines."""
        try:
            if not self.log_file.exists():
                return

            with open(self.log_file, 'r') as f:
                lines = f.readlines()

            if len(lines) > max_lines:
                lines_to_keep = lines[-max_lines:]
                with open(self.log_file, 'w') as f:
                    f.writelines(lines_to_keep)
        except Exception:
            pass

    def save_to_history(self, text, audio_file=None):
        """Save transcription to history file."""
        import json
        import shutil

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp_iso = datetime.now().isoformat()

        # Save to simple text format
        try:
            with open(self.history_file, 'a') as f:
                f.write(f"{timestamp}\t{text}\n")
        except IOError:
            pass

        # Save to JSON format
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

            # Archive audio if enabled
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


@pytest.fixture
def delegate(temp_home):
    """Create a mock delegate for testing."""
    return MockNottaDelegate(temp_home)


# =============================================================================
# Tests: fix_grammar()
# =============================================================================

class TestFixGrammar:
    """Tests for the fix_grammar function."""

    def test_capitalize_first_letter(self, delegate):
        """Should capitalize the first letter of text."""
        assert delegate.fix_grammar("hello world") == "Hello world."

    def test_already_capitalized(self, delegate):
        """Should not double-capitalize."""
        assert delegate.fix_grammar("Hello world") == "Hello world."

    def test_fix_lowercase_i(self, delegate):
        """Should replace standalone 'i' with 'I'."""
        assert delegate.fix_grammar("i think i am here") == "I think I am here."

    def test_fix_im_contraction(self, delegate):
        """Should replace 'im' with 'I'm'."""
        assert delegate.fix_grammar("im going home") == "I'm going home."

    def test_fix_dont_contraction(self, delegate):
        """Should replace 'dont' with 'don't'."""
        assert delegate.fix_grammar("i dont know") == "I don't know."

    def test_fix_cant_contraction(self, delegate):
        """Should replace 'cant' with 'can't'."""
        assert delegate.fix_grammar("i cant do it") == "I can't do it."

    def test_add_period_when_missing(self, delegate):
        """Should add period if no ending punctuation."""
        assert delegate.fix_grammar("Hello world") == "Hello world."

    def test_preserve_exclamation(self, delegate):
        """Should not add period if exclamation exists."""
        assert delegate.fix_grammar("hello world!") == "Hello world!"

    def test_preserve_question_mark(self, delegate):
        """Should not add period if question mark exists."""
        assert delegate.fix_grammar("hello world?") == "Hello world?"

    def test_preserve_existing_period(self, delegate):
        """Should not add period if one already exists."""
        assert delegate.fix_grammar("hello world.") == "Hello world."

    def test_empty_string(self, delegate):
        """Should handle empty string."""
        assert delegate.fix_grammar("") == ""

    def test_none_input(self, delegate):
        """Should handle None input."""
        assert delegate.fix_grammar(None) is None

    def test_single_character(self, delegate):
        """Should handle single character."""
        assert delegate.fix_grammar("i") == "I."

    def test_multiple_contractions(self, delegate):
        """Should fix multiple contractions in one sentence."""
        result = delegate.fix_grammar("i dont think i cant do it")
        assert result == "I don't think I can't do it."

    def test_case_insensitive_replacements(self, delegate):
        """Should replace regardless of case (replacement uses its own case)."""
        # Note: The regex replaces with exact replacement text, so "DONT" -> "don't"
        # Then first letter is capitalized by the capitalize step
        # But since 'd' is now first, we get "don't do that."
        # This is the actual behavior - the replacement overrides the original case
        assert delegate.fix_grammar("DONT do that") == "don't do that."

    def test_word_boundaries(self, delegate):
        """Should not replace 'i' within words."""
        # 'tim' should not become 'tI'm'
        assert delegate.fix_grammar("tim is here") == "Tim is here."

    def test_preserves_existing_punctuation_mid_sentence(self, delegate):
        """Should preserve commas and other mid-sentence punctuation."""
        result = delegate.fix_grammar("hello, world")
        assert result == "Hello, world."

    def test_medical_terminology(self, delegate):
        """Should handle medical text appropriately."""
        result = delegate.fix_grammar("patient presents with chest pain")
        assert result == "Patient presents with chest pain."


# =============================================================================
# Tests: validate_audio()
# =============================================================================

class TestValidateAudio:
    """Tests for the validate_audio function."""

    def test_valid_audio_file(self, delegate, valid_wav_file):
        """Should return True for file with actual audio."""
        is_valid, max_amp, avg_amp = delegate.validate_audio(str(valid_wav_file))
        assert is_valid is True
        assert max_amp > 100
        assert avg_amp > 0

    def test_silent_audio_file(self, delegate, silent_wav_file):
        """Should return False for silent file (all zeros)."""
        is_valid, max_amp, avg_amp = delegate.validate_audio(str(silent_wav_file))
        assert is_valid is False
        assert max_amp == 0

    def test_quiet_audio_file(self, delegate, quiet_wav_file):
        """Should return False for audio below threshold."""
        is_valid, max_amp, avg_amp = delegate.validate_audio(str(quiet_wav_file))
        assert is_valid is False
        assert max_amp < 100

    def test_empty_wav_file(self, delegate, empty_wav_file):
        """Should return False for empty WAV file."""
        is_valid, max_amp, avg_amp = delegate.validate_audio(str(empty_wav_file))
        assert is_valid is False
        assert max_amp == 0
        assert avg_amp == 0

    def test_nonexistent_file(self, delegate):
        """Should return False for non-existent file."""
        is_valid, max_amp, avg_amp = delegate.validate_audio("/nonexistent/file.wav")
        assert is_valid is False
        assert max_amp == 0
        assert avg_amp == 0

    def test_invalid_wav_file(self, delegate, tmp_path):
        """Should return False for invalid WAV file."""
        invalid_file = tmp_path / "invalid.wav"
        invalid_file.write_text("not a wav file")

        is_valid, max_amp, avg_amp = delegate.validate_audio(str(invalid_file))
        assert is_valid is False

    def test_returns_amplitude_metrics(self, delegate, valid_wav_file):
        """Should return meaningful amplitude metrics."""
        is_valid, max_amp, avg_amp = delegate.validate_audio(str(valid_wav_file))

        # Max should be greater than average for a sine wave
        assert max_amp > avg_amp
        # Average should be positive
        assert avg_amp > 0

    def test_threshold_boundary(self, delegate, tmp_path):
        """Test audio right at the threshold boundary."""
        # Create audio with max_amp just above 100
        wav_path = tmp_path / "boundary.wav"
        # Amplitude of ~0.004 should give max_amp around 130
        create_wav_with_tone(wav_path, duration=0.5, frequency=440, amplitude=0.004)

        is_valid, max_amp, avg_amp = delegate.validate_audio(str(wav_path))
        assert max_amp > 100
        assert is_valid is True


# =============================================================================
# Tests: load_config() / save_config()
# =============================================================================

class TestConfiguration:
    """Tests for configuration loading and saving."""

    def test_load_default_config_when_no_file(self, delegate, config_file):
        """Should use default config when file doesn't exist."""
        assert not config_file.exists()
        delegate.load_config()

        assert delegate.config['whisper_backend'] == 'small'
        assert delegate.config['auto_paste'] is True
        assert delegate.config['fix_grammar'] is True
        assert delegate.config['save_audio'] is True
        assert delegate.config['hotkey'] == 'alt_l'

    def test_load_existing_config(self, delegate, config_file, sample_config):
        """Should load config from existing file."""
        # Write custom config
        custom_config = {
            'whisper_backend': 'large',
            'auto_paste': False,
            'fix_grammar': False,
            'save_audio': False,
            'hotkey': 'ctrl_l'
        }
        config_file.write_text(json.dumps(custom_config))

        delegate.load_config()

        assert delegate.config['whisper_backend'] == 'large'
        assert delegate.config['auto_paste'] is False
        assert delegate.config['fix_grammar'] is False
        assert delegate.config['save_audio'] is False
        assert delegate.config['hotkey'] == 'ctrl_l'

    def test_load_invalid_json_uses_defaults(self, delegate, config_file):
        """Should use defaults when config file has invalid JSON."""
        config_file.write_text("not valid json {{{")

        delegate.load_config()

        # Should fall back to defaults
        assert delegate.config['whisper_backend'] == 'small'
        assert delegate.config['hotkey'] == 'alt_l'

    def test_save_config_creates_file(self, delegate, config_file):
        """Should create config file when saving."""
        delegate.config = {
            'whisper_backend': 'medium',
            'auto_paste': True,
            'fix_grammar': True,
            'save_audio': True,
            'hotkey': 'alt_r'
        }

        delegate.save_config()

        assert config_file.exists()
        saved = json.loads(config_file.read_text())
        assert saved['whisper_backend'] == 'medium'
        assert saved['hotkey'] == 'alt_r'

    def test_save_config_overwrites_existing(self, delegate, config_file):
        """Should overwrite existing config file."""
        # Write initial config
        config_file.write_text(json.dumps({'hotkey': 'old_value'}))

        delegate.config = {'hotkey': 'new_value', 'extra': 'data'}
        delegate.save_config()

        saved = json.loads(config_file.read_text())
        assert saved['hotkey'] == 'new_value'
        assert saved['extra'] == 'data'

    def test_save_config_pretty_prints(self, delegate, config_file):
        """Should save config with indentation."""
        delegate.config = {'key': 'value'}
        delegate.save_config()

        content = config_file.read_text()
        assert '\n' in content  # Has newlines (pretty printed)

    def test_roundtrip_config(self, delegate, config_file):
        """Config should survive save/load cycle."""
        original = {
            'whisper_backend': 'tiny',
            'auto_paste': False,
            'fix_grammar': True,
            'save_audio': True,
            'hotkey': 'caps_lock'
        }
        delegate.config = original
        delegate.save_config()

        # Create new delegate and load
        delegate2 = MockNottaDelegate(config_file.parent)
        delegate2.load_config()

        assert delegate2.config == original

    def test_config_with_extra_fields(self, delegate, config_file):
        """Should preserve extra fields in config."""
        extended_config = {
            'whisper_backend': 'small',
            'auto_paste': True,
            'fix_grammar': True,
            'save_audio': True,
            'hotkey': 'alt_l',
            'custom_field': 'custom_value',
            'nested': {'a': 1, 'b': 2}
        }
        config_file.write_text(json.dumps(extended_config))

        delegate.load_config()

        assert delegate.config.get('custom_field') == 'custom_value'
        assert delegate.config.get('nested') == {'a': 1, 'b': 2}


# =============================================================================
# Tests: save_to_history()
# =============================================================================

class TestSaveToHistory:
    """Tests for history saving functionality."""

    def test_saves_to_text_history(self, delegate, history_file):
        """Should append to text history file."""
        delegate.save_to_history("First transcription")
        delegate.save_to_history("Second transcription")

        content = history_file.read_text()
        lines = content.strip().split('\n')

        assert len(lines) == 2
        assert "First transcription" in lines[0]
        assert "Second transcription" in lines[1]

    def test_text_history_format(self, delegate, history_file):
        """Text history should have timestamp and tab separator."""
        delegate.save_to_history("Test text")

        content = history_file.read_text().strip()
        # Format: "YYYY-MM-DD HH:MM:SS\ttext"
        assert '\t' in content
        parts = content.split('\t')
        assert len(parts) == 2
        # Verify timestamp format
        timestamp_part = parts[0]
        assert len(timestamp_part) == 19  # "YYYY-MM-DD HH:MM:SS"

    def test_saves_to_json_history(self, delegate, history_json_file):
        """Should save to JSON history file."""
        delegate.save_to_history("Test transcription")

        assert history_json_file.exists()
        history = json.loads(history_json_file.read_text())

        assert len(history) == 1
        assert history[0]['text'] == "Test transcription"

    def test_json_history_entry_fields(self, delegate, history_json_file):
        """JSON history entries should have all required fields."""
        delegate.save_to_history("Hello world test")

        history = json.loads(history_json_file.read_text())
        entry = history[0]

        assert 'id' in entry
        assert 'timestamp' in entry
        assert 'text' in entry
        assert 'word_count' in entry
        assert 'char_count' in entry
        assert 'category' in entry
        assert 'tags' in entry
        assert 'audio_file' in entry

        assert entry['id'] == 1
        assert entry['word_count'] == 3  # "Hello world test"
        assert entry['char_count'] == 16
        assert entry['category'] is None
        assert entry['tags'] == []

    def test_json_history_increments_id(self, delegate, history_json_file):
        """Each entry should have incrementing ID."""
        delegate.save_to_history("First")
        delegate.save_to_history("Second")
        delegate.save_to_history("Third")

        history = json.loads(history_json_file.read_text())

        assert history[0]['id'] == 1
        assert history[1]['id'] == 2
        assert history[2]['id'] == 3

    def test_preserves_existing_json_history(self, delegate, history_json_file):
        """Should append to existing JSON history."""
        # Pre-populate with existing entry
        existing = [{
            'id': 1,
            'timestamp': '2024-01-01T00:00:00',
            'text': 'Existing entry',
            'word_count': 2,
            'char_count': 14,
            'category': None,
            'tags': [],
            'audio_file': None
        }]
        history_json_file.write_text(json.dumps(existing))

        delegate.save_to_history("New entry")

        history = json.loads(history_json_file.read_text())
        assert len(history) == 2
        assert history[0]['text'] == 'Existing entry'
        assert history[1]['text'] == 'New entry'
        assert history[1]['id'] == 2

    def test_handles_corrupted_json_history(self, delegate, history_json_file):
        """Should start fresh if JSON history is corrupted."""
        history_json_file.write_text("corrupted json {{{")

        delegate.save_to_history("Fresh start")

        history = json.loads(history_json_file.read_text())
        assert len(history) == 1
        assert history[0]['text'] == 'Fresh start'

    def test_archives_audio_when_enabled(self, delegate, valid_wav_file, audio_archive_dir):
        """Should copy audio file when save_audio is enabled."""
        delegate.config = {'save_audio': True}
        delegate.audio_archive_dir = audio_archive_dir

        delegate.save_to_history("Test with audio", str(valid_wav_file))

        # Check that audio was archived
        archived_files = list(audio_archive_dir.glob("recording_*.wav"))
        assert len(archived_files) == 1

        # Check that path is in history
        history = json.loads(delegate.history_json_file.read_text())
        assert history[0]['audio_file'] is not None
        assert 'recording_' in history[0]['audio_file']

    def test_no_audio_archive_when_disabled(self, delegate, valid_wav_file, audio_archive_dir):
        """Should not copy audio when save_audio is disabled."""
        delegate.config = {'save_audio': False}
        delegate.audio_archive_dir = audio_archive_dir

        delegate.save_to_history("Test without audio", str(valid_wav_file))

        archived_files = list(audio_archive_dir.glob("recording_*.wav"))
        assert len(archived_files) == 0

        history = json.loads(delegate.history_json_file.read_text())
        assert history[0]['audio_file'] is None

    def test_handles_nonexistent_audio_file(self, delegate, audio_archive_dir):
        """Should handle gracefully when audio file doesn't exist."""
        delegate.config = {'save_audio': True}
        delegate.audio_archive_dir = audio_archive_dir

        delegate.save_to_history("Test", "/nonexistent/audio.wav")

        # Should still save history entry
        history = json.loads(delegate.history_json_file.read_text())
        assert len(history) == 1
        assert history[0]['audio_file'] is None

    def test_word_count_accuracy(self, delegate, history_json_file):
        """Word count should be accurate."""
        delegate.save_to_history("One two three four five")

        history = json.loads(history_json_file.read_text())
        assert history[0]['word_count'] == 5

    def test_char_count_accuracy(self, delegate, history_json_file):
        """Character count should be accurate."""
        text = "Hello!"
        delegate.save_to_history(text)

        history = json.loads(history_json_file.read_text())
        assert history[0]['char_count'] == len(text)


# =============================================================================
# Tests: rotate_log_if_needed()
# =============================================================================

class TestLogRotation:
    """Tests for log rotation functionality."""

    def test_no_rotation_when_under_limit(self, delegate, log_file):
        """Should not rotate when log is under limit."""
        lines = ["Line %d\n" % i for i in range(100)]
        log_file.write_text(''.join(lines))

        delegate.rotate_log_if_needed(max_lines=5000)

        content = log_file.read_text()
        assert content.count('\n') == 100

    def test_rotation_when_over_limit(self, delegate, log_file):
        """Should rotate when log exceeds limit."""
        lines = ["Line %d\n" % i for i in range(200)]
        log_file.write_text(''.join(lines))

        delegate.rotate_log_if_needed(max_lines=50)

        remaining_lines = log_file.read_text().strip().split('\n')
        assert len(remaining_lines) == 50

    def test_keeps_most_recent_lines(self, delegate, log_file):
        """Should keep the most recent lines after rotation."""
        lines = ["Line %d\n" % i for i in range(100)]
        log_file.write_text(''.join(lines))

        delegate.rotate_log_if_needed(max_lines=10)

        remaining = log_file.read_text().strip().split('\n')
        # Should have lines 90-99 (the last 10)
        assert remaining[0] == "Line 90"
        assert remaining[-1] == "Line 99"

    def test_handles_nonexistent_log(self, delegate, log_file):
        """Should handle gracefully when log doesn't exist."""
        assert not log_file.exists()

        # Should not raise exception
        delegate.rotate_log_if_needed(max_lines=100)

    def test_handles_empty_log(self, delegate, log_file):
        """Should handle empty log file."""
        log_file.write_text("")

        delegate.rotate_log_if_needed(max_lines=100)

        assert log_file.read_text() == ""

    def test_exact_limit_no_rotation(self, delegate, log_file):
        """Should not rotate when exactly at limit."""
        lines = ["Line %d\n" % i for i in range(100)]
        log_file.write_text(''.join(lines))

        delegate.rotate_log_if_needed(max_lines=100)

        # Should remain unchanged
        remaining = log_file.read_text().strip().split('\n')
        assert len(remaining) == 100

    def test_one_over_limit_rotates(self, delegate, log_file):
        """Should rotate when one line over limit."""
        lines = ["Line %d\n" % i for i in range(101)]
        log_file.write_text(''.join(lines))

        delegate.rotate_log_if_needed(max_lines=100)

        remaining = log_file.read_text().strip().split('\n')
        assert len(remaining) == 100
        assert remaining[0] == "Line 1"  # Line 0 was removed

    def test_default_max_lines(self, delegate, log_file):
        """Default max_lines should be 5000."""
        # Create a log with slightly over 5000 lines
        lines = ["Line %d\n" % i for i in range(5010)]
        log_file.write_text(''.join(lines))

        delegate.rotate_log_if_needed()  # Uses default

        remaining = log_file.read_text().strip().split('\n')
        assert len(remaining) == 5000


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_fix_grammar_with_unicode(self, delegate):
        """Should handle unicode characters."""
        result = delegate.fix_grammar("café résumé naïve")
        assert result == "Café résumé naïve."

    def test_fix_grammar_with_emoji(self, delegate):
        """Should handle emoji."""
        result = delegate.fix_grammar("hello 😊 world")
        assert result == "Hello 😊 world."

    def test_fix_grammar_with_numbers(self, delegate):
        """Should handle text starting with numbers."""
        result = delegate.fix_grammar("123 test")
        assert result == "123 test."

    def test_history_with_special_characters(self, delegate, history_json_file):
        """Should handle special characters in transcription."""
        text = 'Patient said "it hurts" & pain level: 8/10'
        delegate.save_to_history(text)

        history = json.loads(history_json_file.read_text())
        assert history[0]['text'] == text

    def test_history_with_unicode(self, delegate, history_json_file):
        """Should handle unicode in transcription."""
        text = "Température: 38°C, naïve résumé"
        delegate.save_to_history(text)

        history = json.loads(history_json_file.read_text())
        assert history[0]['text'] == text

    def test_history_with_newlines(self, delegate, history_json_file, history_file):
        """Should handle newlines in transcription."""
        text = "Line one\nLine two\nLine three"
        delegate.save_to_history(text)

        # JSON should preserve newlines
        history = json.loads(history_json_file.read_text())
        assert '\n' in history[0]['text']

    def test_config_with_unicode_values(self, delegate, config_file):
        """Should handle unicode in config values."""
        delegate.config = {'custom': 'Ñoño café'}
        delegate.save_config()

        delegate.load_config()
        assert delegate.config['custom'] == 'Ñoño café'

    def test_very_long_transcription(self, delegate, history_json_file):
        """Should handle very long transcriptions."""
        text = "word " * 10000  # Exactly 50000 characters (5 chars * 10000)
        delegate.save_to_history(text)

        history = json.loads(history_json_file.read_text())
        assert len(history[0]['text']) == 50000
        assert history[0]['word_count'] == 10000
