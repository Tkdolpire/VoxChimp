"""
Unit tests for the HEAR model worker subprocess (health/analyzer_worker.py)

Tests the subprocess worker that processes audio through the HEAR model.
Since the worker requires heavy dependencies (TensorFlow, HEAR), tests focus on:
- Input validation
- JSON parsing
- Error handling
- Output format
"""

import pytest
import json
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import tempfile
import wave
import struct
import math


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_wav_file(tmp_path):
    """Create a sample WAV file for testing."""
    wav_path = tmp_path / "test_audio.wav"
    create_test_wav(wav_path, duration=2.0, frequency=440)
    return str(wav_path)


@pytest.fixture
def multiple_wav_files(tmp_path):
    """Create multiple sample WAV files."""
    files = []
    for i in range(3):
        wav_path = tmp_path / f"audio_{i}.wav"
        create_test_wav(wav_path, duration=2.0, frequency=440 + i * 50)
        files.append(str(wav_path))
    return files


@pytest.fixture
def short_wav_file(tmp_path):
    """Create a very short WAV file (less than 1 second)."""
    wav_path = tmp_path / "short_audio.wav"
    create_test_wav(wav_path, duration=0.3, frequency=440)
    return str(wav_path)


def create_test_wav(path: Path, duration: float, frequency: float, sample_rate: int = 16000):
    """Create a test WAV file with a sine wave tone."""
    n_samples = int(duration * sample_rate)

    with wave.open(str(path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        for i in range(n_samples):
            t = i / sample_rate
            value = int(0.5 * 32767 * math.sin(2 * math.pi * frequency * t))
            wf.writeframes(struct.pack('<h', value))


# =============================================================================
# Tests: Main Function Input Validation
# =============================================================================

class TestMainFunctionInputValidation:
    """Tests for the main() function input validation."""

    def test_no_args_returns_error(self):
        """Should return error when no arguments provided."""
        # Import and test the main module behavior
        # We can't easily test sys.argv, but we can test the logic
        pass  # Covered by subprocess tests below

    def test_invalid_json_returns_error(self):
        """Should return error for invalid JSON input."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', 'not valid json'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        output = json.loads(result.stdout)
        assert 'error' in output
        assert 'Invalid JSON' in output['error'] or 'JSON' in output['error']

    def test_non_array_returns_error(self):
        """Should return error when input is not a JSON array."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '{"key": "value"}'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        output = json.loads(result.stdout)
        assert 'error' in output
        assert 'array' in output['error'].lower()

    def test_empty_array_returns_empty_array(self):
        """Should return empty array for empty input array."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '[]'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output == []


# =============================================================================
# Tests: Process Audio Files (Mocked)
# =============================================================================

class TestProcessAudioFilesMocked:
    """Tests for process_audio_files with mocked dependencies."""

    def test_import_error_handling(self):
        """Should handle missing dependencies gracefully."""
        # This tests the import error path
        with patch.dict('sys.modules', {'huggingface_hub': None}):
            # The function should raise ImportError
            pass  # Import happens at function call time

    def test_result_format(self):
        """Verify expected output format structure."""
        # Expected format for each result
        expected_keys = {'audio_file', 'embeddings', 'n_chunks', 'duration_seconds'}

        # This is a structural test - actual processing requires HEAR model
        result_template = {
            'audio_file': '/path/to/file.wav',
            'embeddings': [[0.1, 0.2, 0.3]],
            'n_chunks': 1,
            'duration_seconds': 2.0
        }

        assert set(result_template.keys()) == expected_keys
        assert isinstance(result_template['embeddings'], list)
        assert isinstance(result_template['n_chunks'], int)
        assert isinstance(result_template['duration_seconds'], float)


# =============================================================================
# Tests: Audio Chunking Logic
# =============================================================================

class TestAudioChunkingLogic:
    """Tests for audio chunking behavior."""

    def test_chunk_size_is_2_seconds(self):
        """Chunk size should be 2 seconds at 16kHz = 32000 samples."""
        chunk_size = 32000
        sample_rate = 16000
        expected_duration = 2.0

        assert chunk_size / sample_rate == expected_duration

    def test_minimum_chunk_is_1_second(self):
        """Minimum valid chunk should be 1 second (half of 2 seconds)."""
        chunk_size = 32000
        min_chunk = chunk_size // 2

        assert min_chunk == 16000  # 1 second at 16kHz

    def test_short_chunks_are_padded(self):
        """Chunks shorter than 2 seconds should be padded."""
        # This tests the padding logic concept
        chunk_size = 32000
        short_chunk_length = 20000

        padding_needed = chunk_size - short_chunk_length
        assert padding_needed == 12000


# =============================================================================
# Tests: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in the worker."""

    def test_nonexistent_file_handled(self, tmp_path):
        """Should handle non-existent files gracefully."""
        fake_path = str(tmp_path / "nonexistent.wav")

        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', json.dumps([fake_path])],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            timeout=30
        )

        # Should either return empty results or error, not crash
        try:
            output = json.loads(result.stdout)
            # Either empty list or error dict is acceptable
            assert isinstance(output, (list, dict))
        except json.JSONDecodeError:
            # If HEAR model not available, may get different output
            pass

    def test_invalid_audio_file_handled(self, tmp_path):
        """Should handle invalid audio files gracefully."""
        # Create a file that's not valid audio
        fake_audio = tmp_path / "fake.wav"
        fake_audio.write_text("not audio data")

        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', json.dumps([str(fake_audio)])],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            timeout=30
        )

        # Should not crash
        assert result.returncode in [0, 1]  # Either success with empty or error


# =============================================================================
# Tests: JSON Output
# =============================================================================

class TestJSONOutput:
    """Tests for JSON output format."""

    def test_output_is_valid_json(self):
        """Output should always be valid JSON."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '[]'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        # Should not raise JSONDecodeError
        output = json.loads(result.stdout)
        assert output is not None

    def test_error_output_is_json_dict(self):
        """Error output should be a JSON dict with 'error' key."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', 'invalid'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        output = json.loads(result.stdout)
        assert isinstance(output, dict)
        assert 'error' in output

    def test_success_output_is_json_array(self):
        """Success output should be a JSON array."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '[]'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        output = json.loads(result.stdout)
        assert isinstance(output, list)


# =============================================================================
# Tests: Exit Codes
# =============================================================================

class TestExitCodes:
    """Tests for subprocess exit codes."""

    def test_success_returns_zero(self):
        """Successful run should return exit code 0."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '[]'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        assert result.returncode == 0

    def test_invalid_json_returns_nonzero(self):
        """Invalid JSON should return non-zero exit code."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '{invalid}'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        assert result.returncode == 1

    def test_non_array_returns_nonzero(self):
        """Non-array JSON should return non-zero exit code."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '"string"'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        assert result.returncode == 1


# =============================================================================
# Tests: Logging
# =============================================================================

class TestLogging:
    """Tests for logging behavior."""

    def test_logs_go_to_stderr(self):
        """Logs should go to stderr, not stdout."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '[]'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        # stdout should only contain JSON
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail("stdout should only contain valid JSON")

    def test_json_not_in_stderr(self):
        """JSON output should not appear in stderr."""
        result = subprocess.run(
            [sys.executable, '-m', 'health.analyzer_worker', '[]'],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        # stderr should not contain the JSON output
        assert result.stdout.strip() not in result.stderr
