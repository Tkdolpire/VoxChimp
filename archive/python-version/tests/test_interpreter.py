"""
Tests for health/interpreter.py - HEAR embedding interpretation.

Coverage target: 99%+
"""

import pytest
import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from health.interpreter import EmbeddingInterpreter
from health.metrics import VoiceStabilityScore, BaselineResult, TrendResult


class TestEmbeddingInterpreterInit:
    """Tests for EmbeddingInterpreter initialization."""

    def test_init_with_store(self, mock_embedding_store):
        """Test initialization with embedding store."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        assert interp.store == mock_embedding_store
        assert interp.baseline_manager is not None

    def test_similarity_constants(self):
        """Test similarity threshold constants."""
        assert EmbeddingInterpreter.SIMILARITY_EXCELLENT == 0.97
        assert EmbeddingInterpreter.SIMILARITY_GOOD == 0.93
        assert EmbeddingInterpreter.SIMILARITY_MODERATE == 0.88
        assert EmbeddingInterpreter.SIMILARITY_CONCERNING == 0.80


class TestGetVoiceStabilityScore:
    """Tests for get_voice_stability_score method."""

    def test_insufficient_data(self, temp_health_dir, monkeypatch):
        """Test with insufficient data for baseline."""
        from health.embedding_store import EmbeddingStore
        from health.baseline_manager import BaselineManager

        # Patch the baseline file path to use temp directory
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', temp_health_dir / 'baseline.json')

        # Create fresh store with no data
        store = EmbeddingStore(base_path=temp_health_dir)
        interp = EmbeddingInterpreter(store)

        result = interp.get_voice_stability_score()

        assert result.score == 0
        assert result.trend in ["insufficient_data", "no_recent_data"]
        assert result.confidence == 0

    def test_no_recent_data(self, populated_embedding_store):
        """Test with baseline but no recent recordings."""
        interp = EmbeddingInterpreter(populated_embedding_store)

        # Mock get_embeddings_for_period to return empty
        with patch.object(interp.store, 'get_embeddings_for_period', return_value=[]):
            result = interp.get_voice_stability_score()

        assert result.score == 0
        assert result.trend == "no_recent_data"

    def test_returns_valid_score(self, populated_embedding_store):
        """Test returns valid score with baseline and recent data."""
        interp = EmbeddingInterpreter(populated_embedding_store)

        result = interp.get_voice_stability_score()

        assert 0 <= result.score <= 100
        assert result.trend in ["stable", "improving", "declining"]
        assert 0 <= result.confidence <= 1
        assert len(result.message) > 0

    def test_score_is_rounded(self, populated_embedding_store):
        """Test score is rounded to one decimal."""
        interp = EmbeddingInterpreter(populated_embedding_store)

        result = interp.get_voice_stability_score()

        # Score should be rounded to 1 decimal place
        assert result.score == round(result.score, 1)


class TestCosineSimilarity:
    """Tests for _cosine_similarity method."""

    def test_identical_vectors(self, mock_embedding_store):
        """Test similarity of identical vectors is 1."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        vec = [1.0, 2.0, 3.0, 4.0, 5.0]

        result = interp._cosine_similarity(vec, vec)

        assert abs(result - 1.0) < 0.0001

    def test_orthogonal_vectors(self, mock_embedding_store):
        """Test similarity of orthogonal vectors is 0."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        result = interp._cosine_similarity(vec1, vec2)

        assert abs(result) < 0.0001

    def test_opposite_vectors(self, mock_embedding_store):
        """Test similarity of opposite vectors is -1."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]

        result = interp._cosine_similarity(vec1, vec2)

        assert abs(result - (-1.0)) < 0.0001

    def test_empty_vectors(self, mock_embedding_store):
        """Test similarity of empty vectors returns 0."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._cosine_similarity([], [])

        assert result == 0.0

    def test_mismatched_lengths(self, mock_embedding_store):
        """Test vectors of different lengths returns 0."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0]

        result = interp._cosine_similarity(vec1, vec2)

        assert result == 0.0

    def test_zero_vector(self, mock_embedding_store):
        """Test zero vector returns 0."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]

        result = interp._cosine_similarity(vec1, vec2)

        assert result == 0.0


class TestSimilarityToScore:
    """Tests for _similarity_to_score method."""

    def test_perfect_similarity(self, mock_embedding_store):
        """Test perfect similarity maps to high score."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._similarity_to_score(1.0)

        assert result >= 95  # Should be near max

    def test_minimum_similarity(self, mock_embedding_store):
        """Test minimum expected similarity maps to 0."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._similarity_to_score(0.7)

        assert result == 0

    def test_below_minimum_clamps(self, mock_embedding_store):
        """Test similarity below minimum is clamped."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._similarity_to_score(0.5)

        assert result == 0

    def test_above_maximum_clamps(self, mock_embedding_store):
        """Test similarity above 1 is clamped."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._similarity_to_score(1.1)

        assert result <= 100

    def test_mid_range_similarity(self, mock_embedding_store):
        """Test mid-range similarity gives reasonable score."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        # 0.85 is midpoint between 0.7 and 1.0
        result = interp._similarity_to_score(0.85)

        assert 40 <= result <= 60


class TestComputeTrend:
    """Tests for _compute_trend method."""

    def test_insufficient_data(self, mock_embedding_store):
        """Test with fewer than 3 data points."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._compute_trend([0.9, 0.91])

        assert result.direction == "stable"
        assert result.slope == 0
        assert result.confidence == 0

    def test_stable_trend(self, mock_embedding_store):
        """Test stable pattern detected correctly."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        similarities = [0.95, 0.95, 0.95, 0.95, 0.95]

        result = interp._compute_trend(similarities)

        assert result.direction == "stable"

    def test_improving_trend(self, mock_embedding_store):
        """Test improving pattern detected correctly."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        # Clear upward trend
        similarities = [0.80, 0.84, 0.88, 0.92, 0.96]

        result = interp._compute_trend(similarities)

        assert result.direction == "improving"
        assert result.slope > 0

    def test_declining_trend(self, mock_embedding_store):
        """Test declining pattern detected correctly."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        # Clear downward trend
        similarities = [0.96, 0.92, 0.88, 0.84, 0.80]

        result = interp._compute_trend(similarities)

        assert result.direction == "declining"
        assert result.slope < 0

    def test_returns_period_days(self, mock_embedding_store):
        """Test period_days matches input length."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        similarities = [0.9] * 7

        result = interp._compute_trend(similarities)

        assert result.period_days == 7


class TestGetColdStartMessage:
    """Tests for _get_cold_start_message method."""

    def test_zero_recordings(self, mock_embedding_store):
        """Test message with no recordings."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._get_cold_start_message(0, 10)

        assert "start" in result.lower() or "recording" in result.lower()

    def test_few_recordings(self, mock_embedding_store):
        """Test message with few recordings."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._get_cold_start_message(3, 10)

        assert "3/10" in result or "3" in result

    def test_almost_complete(self, mock_embedding_store):
        """Test message when almost complete."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._get_cold_start_message(8, 10)

        assert "8/10" in result or "almost" in result.lower()


class TestGenerateHealthMessage:
    """Tests for _generate_health_message method."""

    def test_excellent_score(self, mock_embedding_store):
        """Test message for excellent score."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        trend = TrendResult("stable", 0, 0.5, 7)

        result = interp._generate_health_message(95, 0.98, trend)

        assert "consistent" in result.lower() or "stable" in result.lower() or "healthy" in result.lower()

    def test_good_score(self, mock_embedding_store):
        """Test message for good score."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        trend = TrendResult("stable", 0, 0.5, 7)

        result = interp._generate_health_message(75, 0.92, trend)

        assert len(result) > 0

    def test_moderate_score(self, mock_embedding_store):
        """Test message for moderate score."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        trend = TrendResult("declining", -0.01, 0.5, 7)

        result = interp._generate_health_message(55, 0.86, trend)

        assert "change" in result.lower() or "variation" in result.lower()

    def test_low_score(self, mock_embedding_store):
        """Test message for low score."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        trend = TrendResult("declining", -0.02, 0.7, 7)

        result = interp._generate_health_message(35, 0.79, trend)

        assert "significant" in result.lower() or "illness" in result.lower()

    def test_improving_trend_message(self, mock_embedding_store):
        """Test message reflects improving trend."""
        interp = EmbeddingInterpreter(mock_embedding_store)
        trend = TrendResult("improving", 0.02, 0.8, 7)

        result = interp._generate_health_message(75, 0.92, trend)

        # Message should be positive for improving trend
        assert len(result) > 0


class TestGenerateHealthIndicators:
    """Tests for _generate_health_indicators method."""

    def test_excellent_similarity(self, mock_embedding_store):
        """Test indicators for excellent similarity."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._generate_health_indicators(0.96, "stable")

        assert len(result) >= 1
        vocal_indicator = [i for i in result if i['name'] == 'Vocal Consistency'][0]
        assert vocal_indicator['status'] == 'excellent'

    def test_good_similarity(self, mock_embedding_store):
        """Test indicators for good similarity."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._generate_health_indicators(0.92, "stable")

        vocal_indicator = [i for i in result if i['name'] == 'Vocal Consistency'][0]
        assert vocal_indicator['status'] == 'good'

    def test_monitor_similarity(self, mock_embedding_store):
        """Test indicators for monitor-level similarity."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._generate_health_indicators(0.87, "stable")

        vocal_indicator = [i for i in result if i['name'] == 'Vocal Consistency'][0]
        assert vocal_indicator['status'] == 'monitor'

    def test_attention_similarity(self, mock_embedding_store):
        """Test indicators for attention-level similarity."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._generate_health_indicators(0.80, "declining")

        vocal_indicator = [i for i in result if i['name'] == 'Vocal Consistency'][0]
        assert vocal_indicator['status'] == 'attention'

    def test_trend_indicator_improving(self, mock_embedding_store):
        """Test trend indicator for improving."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._generate_health_indicators(0.92, "improving")

        trend_indicators = [i for i in result if 'Trend' in i['name']]
        assert len(trend_indicators) == 1
        assert trend_indicators[0]['status'] == 'positive'

    def test_trend_indicator_declining(self, mock_embedding_store):
        """Test trend indicator for declining."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp._generate_health_indicators(0.92, "declining")

        trend_indicators = [i for i in result if 'Trend' in i['name']]
        assert len(trend_indicators) == 1
        assert trend_indicators[0]['status'] == 'monitor'


class TestGetDailySummary:
    """Tests for get_daily_summary method."""

    def test_no_data_for_day(self, mock_embedding_store):
        """Test with no data for the specified day."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        result = interp.get_daily_summary()

        assert result is None

    def test_with_data(self, populated_embedding_store):
        """Test with data for the day."""
        interp = EmbeddingInterpreter(populated_embedding_store)

        result = interp.get_daily_summary()

        if result is not None:  # If there's data for today
            assert result.date == datetime.now().strftime('%Y-%m-%d')
            assert result.n_recordings > 0

    def test_specific_date(self, mock_embedding_store, sample_embedding):
        """Test with specific date."""
        interp = EmbeddingInterpreter(mock_embedding_store)

        # Store embedding for today
        mock_embedding_store.store_embedding('/test.wav', [sample_embedding], 1, 2.0)

        result = interp.get_daily_summary(datetime.now())

        assert result is not None
        assert result.n_recordings == 1


class TestGetDetailedInsights:
    """Tests for get_detailed_insights method."""

    def test_no_baseline(self, temp_health_dir, monkeypatch):
        """Test insights without valid baseline."""
        from health.embedding_store import EmbeddingStore
        from health.baseline_manager import BaselineManager

        # Patch the baseline file path to use temp directory
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', temp_health_dir / 'baseline.json')

        # Create fresh store with no data
        store = EmbeddingStore(base_path=temp_health_dir)
        interp = EmbeddingInterpreter(store)

        result = interp.get_detailed_insights()

        assert result['baseline_valid'] is False
        assert result['total_recordings'] == 0

    def test_with_baseline(self, populated_embedding_store):
        """Test insights with valid baseline."""
        interp = EmbeddingInterpreter(populated_embedding_store)

        result = interp.get_detailed_insights()

        assert result['baseline_valid'] is True
        assert result['baseline_samples'] >= 10
        assert result['total_recordings'] >= 10

    def test_includes_recent_recordings(self, populated_embedding_store):
        """Test insights include recent recording count."""
        interp = EmbeddingInterpreter(populated_embedding_store)

        result = interp.get_detailed_insights()

        assert 'recent_recordings' in result

    def test_includes_similarity_stats(self, populated_embedding_store):
        """Test insights include similarity statistics."""
        interp = EmbeddingInterpreter(populated_embedding_store)

        result = interp.get_detailed_insights()

        if result['recent_recordings'] > 0:
            assert 'average_similarity' in result
            assert 'similarity_range' in result

    def test_includes_health_indicators(self, populated_embedding_store):
        """Test insights include health indicators."""
        interp = EmbeddingInterpreter(populated_embedding_store)

        result = interp.get_detailed_insights()

        assert 'health_indicators' in result
