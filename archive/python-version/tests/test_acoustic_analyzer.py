"""
Tests for health/acoustic_analyzer.py - Parselmouth/Praat acoustic analysis.

Coverage target: 99%+
"""

import pytest
import json
import math
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
from health.acoustic_analyzer import (
    AcousticAnalyzer,
    AcousticFeatures,
    VoiceHealthStatus
)


class TestAcousticFeaturesDataclass:
    """Tests for AcousticFeatures dataclass."""

    def test_default_values(self):
        """Test default field values."""
        features = AcousticFeatures()

        assert features.f0_mean == 0.0
        assert features.f0_std == 0.0
        assert features.jitter_local == 0.0
        assert features.shimmer_local == 0.0
        assert features.hnr == 0.0
        assert features.duration == 0.0
        assert features.timestamp == ""
        assert features.audio_path == ""

    def test_creation_with_values(self, sample_acoustic_features):
        """Test creating with specific values."""
        assert sample_acoustic_features.f0_mean == 150.0
        assert sample_acoustic_features.jitter_local == 1.2
        assert sample_acoustic_features.hnr == 20.0

    def test_all_fields_populated(self, sample_acoustic_features):
        """Test all fields can be populated."""
        assert sample_acoustic_features.f0_min == 100.0
        assert sample_acoustic_features.f0_max == 200.0
        assert sample_acoustic_features.jitter_rap == 0.8
        assert sample_acoustic_features.shimmer_apq3 == 2.5
        assert sample_acoustic_features.f1_mean == 500.0
        assert sample_acoustic_features.f2_mean == 1500.0
        assert sample_acoustic_features.f3_mean == 2500.0
        assert sample_acoustic_features.voiced_fraction == 0.8
        assert sample_acoustic_features.speech_rate == 4.5
        assert sample_acoustic_features.pause_rate == 0.5


class TestVoiceHealthStatusDataclass:
    """Tests for VoiceHealthStatus dataclass."""

    def test_default_values(self):
        """Test default field values."""
        status = VoiceHealthStatus()

        assert status.fatigue_score == 0.0
        assert status.illness_score == 0.0
        assert status.fatigue_indicators == []
        assert status.illness_indicators == []
        assert status.recommendation == ""
        assert status.confidence == 0.0

    def test_with_fatigue(self):
        """Test status with fatigue indicators."""
        status = VoiceHealthStatus(
            fatigue_score=75.0,
            fatigue_indicators=["Voice instability increased (40%)", "Speaking slower (25%)"],
            recommendation="Consider taking a break."
        )

        assert status.fatigue_score == 75.0
        assert len(status.fatigue_indicators) == 2

    def test_with_illness(self):
        """Test status with illness indicators."""
        status = VoiceHealthStatus(
            illness_score=60.0,
            illness_indicators=["Pitch is lower than usual (15%)"],
            recommendation="Rest recommended."
        )

        assert status.illness_score == 60.0
        assert len(status.illness_indicators) == 1


class TestAcousticAnalyzerInit:
    """Tests for AcousticAnalyzer initialization."""

    def test_init_creates_empty_cache(self, temp_health_dir, monkeypatch):
        """Test initialization creates empty feature cache."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        assert analyzer._features_cache == []
        assert analyzer._baseline is None

    def test_loads_existing_features(self, temp_health_dir, monkeypatch):
        """Test initialization loads existing features."""
        features_file = temp_health_dir / 'acoustic_features.json'
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', features_file)
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        # Create existing features file
        features_data = [
            {'f0_mean': 150.0, 'jitter_local': 1.2, 'hnr': 20.0, 'timestamp': '2026-01-25'}
        ]
        with open(features_file, 'w') as f:
            json.dump(features_data, f)

        analyzer = AcousticAnalyzer()

        assert len(analyzer._features_cache) == 1
        assert analyzer._features_cache[0].f0_mean == 150.0

    def test_lazy_loads_parselmouth(self, temp_health_dir, monkeypatch):
        """Test parselmouth is lazily loaded."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        assert analyzer._parselmouth is None


class TestGetParselmouth:
    """Tests for _get_parselmouth method."""

    def test_imports_parselmouth(self, temp_health_dir, monkeypatch):
        """Test successful parselmouth import."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        # Mock successful import
        with patch.dict('sys.modules', {'parselmouth': MagicMock()}):
            pm = analyzer._get_parselmouth()
            assert pm is not None

    def test_handles_import_error(self, temp_health_dir, monkeypatch):
        """Test handles ImportError gracefully."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        # Force ImportError
        with patch('builtins.__import__', side_effect=ImportError("No module")):
            pm = analyzer._get_parselmouth()
            assert pm is None


class TestAnalyzeAudio:
    """Tests for analyze_audio method."""

    def test_returns_none_without_parselmouth(self, temp_health_dir, monkeypatch):
        """Test returns None when parselmouth not available."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        with patch.object(analyzer, '_get_parselmouth', return_value=None):
            result = analyzer.analyze_audio('/test/audio.wav')
            assert result is None

    def test_extracts_features(self, temp_health_dir, monkeypatch, mock_parselmouth, sample_wav_file):
        """Test extracts acoustic features from audio."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        with patch.object(analyzer, '_get_parselmouth', return_value=mock_parselmouth):
            result = analyzer.analyze_audio(str(sample_wav_file))

        assert result is not None
        assert result.audio_path == str(sample_wav_file)
        assert result.timestamp != ""

    def test_handles_analysis_error(self, temp_health_dir, monkeypatch, mock_parselmouth):
        """Test handles analysis errors gracefully."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        mock_parselmouth.Sound.side_effect = Exception("Audio load error")

        with patch.object(analyzer, '_get_parselmouth', return_value=mock_parselmouth):
            result = analyzer.analyze_audio('/nonexistent.wav')

        assert result is None

    def test_stores_features_in_cache(self, temp_health_dir, monkeypatch, mock_parselmouth, sample_wav_file):
        """Test stores extracted features in cache."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        with patch.object(analyzer, '_get_parselmouth', return_value=mock_parselmouth):
            analyzer.analyze_audio(str(sample_wav_file))

        assert len(analyzer._features_cache) == 1

    def test_updates_baseline_after_min_samples(self, temp_health_dir, monkeypatch, mock_parselmouth, multiple_wav_files):
        """Test updates baseline after minimum samples reached."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        with patch.object(analyzer, '_get_parselmouth', return_value=mock_parselmouth):
            for wav_file in multiple_wav_files[:6]:  # More than MIN_BASELINE_SAMPLES
                analyzer.analyze_audio(str(wav_file))

        assert analyzer._baseline is not None


class TestHelperMethods:
    """Tests for helper methods."""

    def test_safe_call_success(self, temp_health_dir, monkeypatch):
        """Test _safe_call with successful function."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        result = analyzer._safe_call(lambda x: x * 2, 5)

        assert result == 10

    def test_safe_call_error(self, temp_health_dir, monkeypatch):
        """Test _safe_call returns 0 on error."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        def raising_func():
            raise ValueError("Error")

        result = analyzer._safe_call(raising_func)

        assert result == 0.0

    def test_std_calculation(self, temp_health_dir, monkeypatch):
        """Test standard deviation calculation."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        # Known values: std([0, 10]) = 5
        result = analyzer._std([0, 10])

        assert abs(result - 5.0) < 0.001

    def test_std_single_value(self, temp_health_dir, monkeypatch):
        """Test std with single value returns 0."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        result = analyzer._std([5.0])

        assert result == 0.0

    def test_std_empty_list(self, temp_health_dir, monkeypatch):
        """Test std with empty list returns 0."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        result = analyzer._std([])

        assert result == 0.0


class TestGetHealthStatus:
    """Tests for get_health_status method."""

    def test_no_features(self, temp_health_dir, monkeypatch):
        """Test with no features returns message about baseline."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        result = analyzer.get_health_status()

        assert result.confidence == 0
        assert "record" in result.recommendation.lower() or "baseline" in result.recommendation.lower()

    def test_no_baseline(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test with features but no baseline."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        analyzer._features_cache = [sample_acoustic_features]

        result = analyzer.get_health_status()

        assert "baseline" in result.recommendation.lower()

    def test_with_baseline_healthy(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test with baseline and healthy features."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        # Add enough samples for baseline
        for _ in range(10):
            analyzer._features_cache.append(sample_acoustic_features)
        analyzer._update_baseline()

        result = analyzer.get_health_status(sample_acoustic_features)

        assert result.fatigue_score < 30
        assert result.illness_score < 30

    def test_detects_fatigue(self, temp_health_dir, monkeypatch, sample_acoustic_features, fatigued_acoustic_features):
        """Test detects fatigue indicators."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        # Set up baseline with healthy features
        for _ in range(10):
            analyzer._features_cache.append(sample_acoustic_features)
        analyzer._update_baseline()

        result = analyzer.get_health_status(fatigued_acoustic_features)

        assert result.fatigue_score > 40
        assert len(result.fatigue_indicators) > 0

    def test_detects_illness(self, temp_health_dir, monkeypatch, sample_acoustic_features, illness_acoustic_features):
        """Test detects illness indicators."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        # Set up baseline with healthy features
        for _ in range(10):
            analyzer._features_cache.append(sample_acoustic_features)
        analyzer._update_baseline()

        result = analyzer.get_health_status(illness_acoustic_features)

        assert result.illness_score > 40
        assert len(result.illness_indicators) > 0


class TestAssessFatigue:
    """Tests for _assess_fatigue method."""

    def test_no_baseline(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test returns 0 with no baseline."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        score, indicators = analyzer._assess_fatigue(sample_acoustic_features)

        assert score == 0
        assert indicators == []

    def test_detects_jitter_increase(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test detects jitter increase as fatigue indicator."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        analyzer._baseline = sample_acoustic_features

        # Create features with high jitter
        high_jitter = AcousticFeatures(
            jitter_local=sample_acoustic_features.jitter_local * 1.5,  # 50% increase
            shimmer_local=sample_acoustic_features.shimmer_local,
            hnr=sample_acoustic_features.hnr,
            speech_rate=sample_acoustic_features.speech_rate,
            pause_rate=sample_acoustic_features.pause_rate
        )

        score, indicators = analyzer._assess_fatigue(high_jitter)

        assert score > 0
        assert any("instability" in i.lower() for i in indicators)

    def test_detects_speech_rate_decrease(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test detects slower speech as fatigue indicator."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        analyzer._baseline = sample_acoustic_features

        slow_speech = AcousticFeatures(
            jitter_local=sample_acoustic_features.jitter_local,
            shimmer_local=sample_acoustic_features.shimmer_local,
            hnr=sample_acoustic_features.hnr,
            speech_rate=sample_acoustic_features.speech_rate * 0.7,  # 30% slower
            pause_rate=sample_acoustic_features.pause_rate
        )

        score, indicators = analyzer._assess_fatigue(slow_speech)

        assert any("slower" in i.lower() for i in indicators)


class TestAssessIllness:
    """Tests for _assess_illness method."""

    def test_no_baseline(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test returns 0 with no baseline."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        score, indicators = analyzer._assess_illness(sample_acoustic_features)

        assert score == 0
        assert indicators == []

    def test_detects_pitch_change(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test detects pitch change as illness indicator."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        analyzer._baseline = sample_acoustic_features

        low_pitch = AcousticFeatures(
            f0_mean=sample_acoustic_features.f0_mean * 0.85,  # 15% lower
            hnr=sample_acoustic_features.hnr,
            f1_mean=sample_acoustic_features.f1_mean,
            f2_mean=sample_acoustic_features.f2_mean
        )

        score, indicators = analyzer._assess_illness(low_pitch)

        assert score > 0
        assert any("pitch" in i.lower() for i in indicators)

    def test_detects_hnr_decrease(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test detects HNR decrease as illness indicator."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        analyzer._baseline = sample_acoustic_features

        low_hnr = AcousticFeatures(
            f0_mean=sample_acoustic_features.f0_mean,
            hnr=sample_acoustic_features.hnr * 0.7,  # 30% decrease
            f1_mean=sample_acoustic_features.f1_mean,
            f2_mean=sample_acoustic_features.f2_mean
        )

        score, indicators = analyzer._assess_illness(low_hnr)

        assert any("clear" in i.lower() for i in indicators)


class TestGenerateRecommendation:
    """Tests for _generate_recommendation method."""

    def test_both_high(self, temp_health_dir, monkeypatch):
        """Test recommendation when both fatigue and illness are high."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        result = analyzer._generate_recommendation(70, 70, ["indicator1"], ["indicator2"])

        assert "fatigue" in result.lower()
        assert "illness" in result.lower()

    def test_high_fatigue(self, temp_health_dir, monkeypatch):
        """Test recommendation for high fatigue only."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        result = analyzer._generate_recommendation(70, 20, ["indicator1"], [])

        assert "fatigue" in result.lower() or "break" in result.lower()

    def test_high_illness(self, temp_health_dir, monkeypatch):
        """Test recommendation for high illness only."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        result = analyzer._generate_recommendation(20, 70, [], ["indicator1"])

        assert "illness" in result.lower() or "rest" in result.lower()

    def test_healthy(self, temp_health_dir, monkeypatch):
        """Test recommendation for healthy state."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        result = analyzer._generate_recommendation(10, 10, [], [])

        assert "healthy" in result.lower() or "well" in result.lower()


class TestPersistence:
    """Tests for save/load functionality."""

    def test_save_features(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test saving features to JSON."""
        features_file = temp_health_dir / 'acoustic_features.json'
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', features_file)
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        analyzer._features_cache = [sample_acoustic_features]
        analyzer._save_features()

        assert features_file.exists()
        with open(features_file, 'r') as f:
            data = json.load(f)
        assert len(data) == 1

    def test_load_features(self, temp_health_dir, monkeypatch):
        """Test loading features from JSON."""
        features_file = temp_health_dir / 'acoustic_features.json'
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', features_file)
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        # Create features file
        data = [{'f0_mean': 150.0, 'jitter_local': 1.2, 'hnr': 20.0}]
        with open(features_file, 'w') as f:
            json.dump(data, f)

        analyzer = AcousticAnalyzer()

        assert len(analyzer._features_cache) == 1
        assert analyzer._features_cache[0].f0_mean == 150.0

    def test_save_baseline(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test saving baseline to JSON."""
        baseline_file = temp_health_dir / 'acoustic_baseline.json'
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', baseline_file)

        analyzer = AcousticAnalyzer()
        analyzer._baseline = sample_acoustic_features
        analyzer._features_cache = [sample_acoustic_features] * 10
        analyzer._save_baseline()

        assert baseline_file.exists()
        with open(baseline_file, 'r') as f:
            data = json.load(f)
        assert data['f0_mean'] == 150.0

    def test_load_baseline(self, temp_health_dir, monkeypatch):
        """Test loading baseline from JSON."""
        baseline_file = temp_health_dir / 'acoustic_baseline.json'
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', baseline_file)

        # Create baseline file
        data = {'f0_mean': 150.0, 'jitter_local': 1.2, 'hnr': 20.0}
        with open(baseline_file, 'w') as f:
            json.dump(data, f)

        analyzer = AcousticAnalyzer()

        assert analyzer._baseline is not None
        assert analyzer._baseline.f0_mean == 150.0


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_feature_count(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test get_feature_count returns correct count."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        analyzer._features_cache = [sample_acoustic_features] * 5

        assert analyzer.get_feature_count() == 5

    def test_get_baseline_progress(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test get_baseline_progress returns correct values."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        analyzer._features_cache = [sample_acoustic_features] * 3

        current, required = analyzer.get_baseline_progress()

        assert current == 3
        assert required == AcousticAnalyzer.MIN_BASELINE_SAMPLES

    def test_get_latest_features(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test get_latest_features returns most recent."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        feature1 = AcousticFeatures(f0_mean=100.0)
        feature2 = AcousticFeatures(f0_mean=200.0)
        analyzer._features_cache = [feature1, feature2]

        latest = analyzer.get_latest_features()

        assert latest.f0_mean == 200.0

    def test_get_latest_features_empty(self, temp_health_dir, monkeypatch):
        """Test get_latest_features with empty cache."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()

        latest = analyzer.get_latest_features()

        assert latest is None

    def test_get_detailed_report(self, temp_health_dir, monkeypatch, sample_acoustic_features):
        """Test get_detailed_report returns comprehensive data."""
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_FILE', temp_health_dir / 'acoustic_features.json')
        monkeypatch.setattr(AcousticAnalyzer, 'ACOUSTIC_BASELINE_FILE', temp_health_dir / 'acoustic_baseline.json')

        analyzer = AcousticAnalyzer()
        for _ in range(10):
            analyzer._features_cache.append(sample_acoustic_features)
        analyzer._update_baseline()

        report = analyzer.get_detailed_report()

        assert 'has_baseline' in report
        assert report['has_baseline'] is True
        assert 'baseline_samples' in report
        assert 'fatigue_score' in report
        assert 'illness_score' in report
        assert 'current_metrics' in report
        assert 'baseline_metrics' in report
