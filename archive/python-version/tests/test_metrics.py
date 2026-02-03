"""
Tests for health/metrics.py - Data classes for voice health metrics.

Coverage target: 100%
"""

import pytest
from dataclasses import asdict
from health.metrics import (
    VoiceStabilityScore,
    BaselineResult,
    DailySummary,
    TrendResult
)


class TestVoiceStabilityScore:
    """Tests for VoiceStabilityScore dataclass."""

    def test_creation_with_all_fields(self):
        """Test creating VoiceStabilityScore with all fields."""
        score = VoiceStabilityScore(
            score=85.5,
            trend="stable",
            confidence=0.9,
            message="Your voice is stable"
        )

        assert score.score == 85.5
        assert score.trend == "stable"
        assert score.confidence == 0.9
        assert score.message == "Your voice is stable"

    def test_score_range_values(self):
        """Test with various score values."""
        # Minimum score
        low_score = VoiceStabilityScore(score=0, trend="declining", confidence=0, message="Low")
        assert low_score.score == 0

        # Maximum score
        high_score = VoiceStabilityScore(score=100, trend="improving", confidence=1.0, message="High")
        assert high_score.score == 100

        # Decimal score
        decimal_score = VoiceStabilityScore(score=72.35, trend="stable", confidence=0.5, message="Mid")
        assert decimal_score.score == 72.35

    def test_trend_values(self):
        """Test various trend values."""
        trends = ["stable", "improving", "declining", "insufficient_data", "no_recent_data"]

        for trend in trends:
            score = VoiceStabilityScore(score=50, trend=trend, confidence=0.5, message="Test")
            assert score.trend == trend

    def test_to_dict(self):
        """Test conversion to dictionary."""
        score = VoiceStabilityScore(
            score=75.0,
            trend="stable",
            confidence=0.8,
            message="Normal variation"
        )

        d = asdict(score)
        assert d['score'] == 75.0
        assert d['trend'] == "stable"
        assert d['confidence'] == 0.8
        assert d['message'] == "Normal variation"


class TestBaselineResult:
    """Tests for BaselineResult dataclass."""

    def test_default_values(self):
        """Test default field values."""
        result = BaselineResult()

        assert result.mean_embedding == []
        assert result.std_embedding == []
        assert result.n_samples == 0
        assert result.computed_at is None
        assert result.is_valid is False

    def test_creation_with_embeddings(self):
        """Test creating with embedding data."""
        mean_emb = [0.1, 0.2, 0.3]
        std_emb = [0.01, 0.02, 0.03]

        result = BaselineResult(
            mean_embedding=mean_emb,
            std_embedding=std_emb,
            n_samples=20,
            computed_at="2026-01-25T10:30:00",
            is_valid=True
        )

        assert result.mean_embedding == mean_emb
        assert result.std_embedding == std_emb
        assert result.n_samples == 20
        assert result.computed_at == "2026-01-25T10:30:00"
        assert result.is_valid is True

    def test_invalid_baseline(self):
        """Test invalid baseline state."""
        result = BaselineResult(
            n_samples=5,
            is_valid=False
        )

        assert result.n_samples == 5
        assert result.is_valid is False
        assert result.mean_embedding == []

    def test_512_dimensional_embeddings(self):
        """Test with realistic 512-dimensional embeddings."""
        mean_emb = [0.01 * i for i in range(512)]
        std_emb = [0.001 * i for i in range(512)]

        result = BaselineResult(
            mean_embedding=mean_emb,
            std_embedding=std_emb,
            n_samples=100,
            is_valid=True
        )

        assert len(result.mean_embedding) == 512
        assert len(result.std_embedding) == 512


class TestDailySummary:
    """Tests for DailySummary dataclass."""

    def test_creation(self):
        """Test creating DailySummary."""
        summary = DailySummary(
            date="2026-01-25",
            n_recordings=5,
            avg_similarity=0.95,
            stability_score=85.0
        )

        assert summary.date == "2026-01-25"
        assert summary.n_recordings == 5
        assert summary.avg_similarity == 0.95
        assert summary.stability_score == 85.0

    def test_zero_recordings(self):
        """Test with zero recordings."""
        summary = DailySummary(
            date="2026-01-25",
            n_recordings=0,
            avg_similarity=0,
            stability_score=0
        )

        assert summary.n_recordings == 0
        assert summary.avg_similarity == 0
        assert summary.stability_score == 0

    def test_high_activity_day(self):
        """Test with many recordings."""
        summary = DailySummary(
            date="2026-01-25",
            n_recordings=50,
            avg_similarity=0.92,
            stability_score=73.3
        )

        assert summary.n_recordings == 50
        assert summary.avg_similarity == 0.92


class TestTrendResult:
    """Tests for TrendResult dataclass."""

    def test_creation(self):
        """Test creating TrendResult."""
        trend = TrendResult(
            direction="improving",
            slope=0.02,
            confidence=0.85,
            period_days=7
        )

        assert trend.direction == "improving"
        assert trend.slope == 0.02
        assert trend.confidence == 0.85
        assert trend.period_days == 7

    def test_declining_trend(self):
        """Test declining trend."""
        trend = TrendResult(
            direction="declining",
            slope=-0.015,
            confidence=0.7,
            period_days=14
        )

        assert trend.direction == "declining"
        assert trend.slope < 0

    def test_stable_trend(self):
        """Test stable trend."""
        trend = TrendResult(
            direction="stable",
            slope=0.001,
            confidence=0.3,
            period_days=7
        )

        assert trend.direction == "stable"
        assert abs(trend.slope) < 0.005

    def test_low_confidence(self):
        """Test low confidence trend."""
        trend = TrendResult(
            direction="stable",
            slope=0,
            confidence=0,
            period_days=2
        )

        assert trend.confidence == 0
        assert trend.period_days == 2
