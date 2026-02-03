"""
Pytest fixtures and configuration for Notta tests.
"""

import pytest
import tempfile
import shutil
import json
import wave
import struct
import math
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def temp_health_dir(temp_dir):
    """Create a temporary health data directory."""
    health_dir = temp_dir / '.notta_health'
    health_dir.mkdir(exist_ok=True)
    return health_dir


@pytest.fixture
def temp_audio_dir(temp_dir):
    """Create a temporary audio directory."""
    audio_dir = temp_dir / '.notta_audio'
    audio_dir.mkdir(exist_ok=True)
    return audio_dir


@pytest.fixture
def sample_wav_file(temp_audio_dir):
    """Create a sample WAV file with synthetic audio."""
    wav_path = temp_audio_dir / 'test_recording.wav'
    create_test_wav(wav_path, duration=2.0, frequency=440)
    return wav_path


@pytest.fixture
def multiple_wav_files(temp_audio_dir):
    """Create multiple sample WAV files."""
    files = []
    for i in range(15):
        wav_path = temp_audio_dir / f'recording_{i:04d}.wav'
        # Vary frequency slightly to simulate different recordings
        create_test_wav(wav_path, duration=2.0, frequency=440 + i * 10)
        files.append(wav_path)
    return files


def create_test_wav(path: Path, duration: float = 2.0, frequency: float = 440,
                    sample_rate: int = 16000, amplitude: float = 0.5):
    """
    Create a test WAV file with a sine wave.

    Args:
        path: Output file path
        duration: Duration in seconds
        frequency: Tone frequency in Hz
        sample_rate: Sample rate in Hz
        amplitude: Amplitude (0.0 to 1.0)
    """
    n_samples = int(duration * sample_rate)

    with wave.open(str(path), 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Generate sine wave
        for i in range(n_samples):
            t = i / sample_rate
            value = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * t))
            wav_file.writeframes(struct.pack('<h', value))


@pytest.fixture
def sample_embedding():
    """Create a sample 512-dimensional embedding."""
    import random
    random.seed(42)
    return [random.gauss(0, 1) for _ in range(512)]


@pytest.fixture
def sample_embeddings_list():
    """Create multiple sample embeddings for baseline testing."""
    import random
    embeddings = []
    for seed in range(15):
        random.seed(seed)
        # Create similar embeddings with small variations
        base = [random.gauss(0, 1) for _ in range(512)]
        embeddings.append(base)
    return embeddings


@pytest.fixture
def mock_embedding_store(temp_health_dir):
    """Create a mock embedding store with test data."""
    from health.embedding_store import EmbeddingStore

    store = EmbeddingStore(base_path=temp_health_dir)
    return store


@pytest.fixture
def populated_embedding_store(mock_embedding_store, sample_embeddings_list, temp_audio_dir):
    """Create an embedding store populated with test data."""
    store = mock_embedding_store

    for i, emb in enumerate(sample_embeddings_list):
        audio_file = str(temp_audio_dir / f'recording_{i:04d}.wav')
        store.store_embedding(
            audio_file=audio_file,
            embeddings=[emb],
            n_chunks=1,
            duration_seconds=2.0
        )

    return store


@pytest.fixture
def sample_acoustic_features():
    """Create sample acoustic features for testing."""
    from health.acoustic_analyzer import AcousticFeatures

    return AcousticFeatures(
        f0_mean=150.0,
        f0_std=20.0,
        f0_min=100.0,
        f0_max=200.0,
        jitter_local=1.2,
        jitter_rap=0.8,
        shimmer_local=3.5,
        shimmer_apq3=2.5,
        hnr=20.0,
        f1_mean=500.0,
        f2_mean=1500.0,
        f3_mean=2500.0,
        duration=2.0,
        voiced_fraction=0.8,
        speech_rate=4.5,
        pause_rate=0.5,
        timestamp=datetime.now().isoformat(),
        audio_path='/test/audio.wav'
    )


@pytest.fixture
def fatigued_acoustic_features(sample_acoustic_features):
    """Create acoustic features showing fatigue indicators."""
    from health.acoustic_analyzer import AcousticFeatures

    # Increase jitter/shimmer, decrease HNR and speech rate
    return AcousticFeatures(
        f0_mean=sample_acoustic_features.f0_mean,
        f0_std=sample_acoustic_features.f0_std * 1.5,
        f0_min=sample_acoustic_features.f0_min,
        f0_max=sample_acoustic_features.f0_max,
        jitter_local=sample_acoustic_features.jitter_local * 1.5,  # 50% increase
        jitter_rap=sample_acoustic_features.jitter_rap * 1.5,
        shimmer_local=sample_acoustic_features.shimmer_local * 1.4,  # 40% increase
        shimmer_apq3=sample_acoustic_features.shimmer_apq3 * 1.4,
        hnr=sample_acoustic_features.hnr * 0.7,  # 30% decrease
        f1_mean=sample_acoustic_features.f1_mean,
        f2_mean=sample_acoustic_features.f2_mean,
        f3_mean=sample_acoustic_features.f3_mean,
        duration=sample_acoustic_features.duration,
        voiced_fraction=sample_acoustic_features.voiced_fraction,
        speech_rate=sample_acoustic_features.speech_rate * 0.7,  # 30% slower
        pause_rate=sample_acoustic_features.pause_rate * 1.5,  # 50% more pauses
        timestamp=datetime.now().isoformat(),
        audio_path='/test/fatigued_audio.wav'
    )


@pytest.fixture
def illness_acoustic_features(sample_acoustic_features):
    """Create acoustic features showing illness indicators."""
    from health.acoustic_analyzer import AcousticFeatures

    # Lower pitch, reduced HNR, changed formants
    return AcousticFeatures(
        f0_mean=sample_acoustic_features.f0_mean * 0.85,  # 15% lower pitch
        f0_std=sample_acoustic_features.f0_std,
        f0_min=sample_acoustic_features.f0_min * 0.85,
        f0_max=sample_acoustic_features.f0_max * 0.85,
        jitter_local=sample_acoustic_features.jitter_local * 1.2,
        jitter_rap=sample_acoustic_features.jitter_rap * 1.2,
        shimmer_local=sample_acoustic_features.shimmer_local * 1.2,
        shimmer_apq3=sample_acoustic_features.shimmer_apq3 * 1.2,
        hnr=sample_acoustic_features.hnr * 0.6,  # 40% decrease
        f1_mean=sample_acoustic_features.f1_mean * 1.2,  # 20% change (nasality)
        f2_mean=sample_acoustic_features.f2_mean * 1.18,  # 18% change
        f3_mean=sample_acoustic_features.f3_mean,
        duration=sample_acoustic_features.duration,
        voiced_fraction=sample_acoustic_features.voiced_fraction * 0.9,
        speech_rate=sample_acoustic_features.speech_rate * 0.9,
        pause_rate=sample_acoustic_features.pause_rate * 1.3,
        timestamp=datetime.now().isoformat(),
        audio_path='/test/illness_audio.wav'
    )


@pytest.fixture
def mock_parselmouth():
    """Create a mock parselmouth module for testing without actual Praat."""
    mock_pm = MagicMock()

    # Mock Sound
    mock_sound = MagicMock()
    mock_sound.duration = 2.0
    mock_sound.to_pitch.return_value.selected_array = {'frequency': [150.0] * 100}
    mock_sound.to_intensity.return_value.values = [[50.0] * 100]

    mock_pm.Sound.return_value = mock_sound

    # Mock praat.call
    def mock_praat_call(*args):
        command = args[1] if len(args) > 1 else ''
        if 'jitter' in command.lower():
            return 0.012
        elif 'shimmer' in command.lower():
            return 0.035
        elif 'harmonicity' in command.lower():
            return MagicMock()
        elif 'mean' in command.lower():
            return 20.0  # HNR or formant
        elif 'formant' in command.lower():
            return MagicMock()
        return 0.0

    mock_pm.praat.call = mock_praat_call

    return mock_pm
