"""
Data classes for voice health metrics.

Defines the structured data types used throughout the health interpretation system.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VoiceStabilityScore:
    """
    The primary user-facing metric representing voice pattern stability.

    Attributes:
        score: 0-100 scale, where 100 is most stable/consistent
        trend: "stable", "improving", "declining", or "insufficient_data"
        confidence: 0.0-1.0, based on amount of data available
        message: Human-readable interpretation of the score
    """
    score: float
    trend: str
    confidence: float
    message: str


@dataclass
class BaselineResult:
    """
    Personal voice baseline computed from historical embeddings.

    Attributes:
        mean_embedding: 512-dimensional mean vector
        std_embedding: 512-dimensional standard deviation vector
        n_samples: Number of recordings used to compute baseline
        computed_at: ISO timestamp of when baseline was computed
        is_valid: Whether baseline meets minimum sample requirements
    """
    mean_embedding: List[float] = field(default_factory=list)
    std_embedding: List[float] = field(default_factory=list)
    n_samples: int = 0
    computed_at: Optional[str] = None
    is_valid: bool = False


@dataclass
class DailySummary:
    """
    Summary of voice metrics for a single day.

    Attributes:
        date: Date string (YYYY-MM-DD)
        n_recordings: Number of recordings on this day
        avg_similarity: Average cosine similarity to baseline
        stability_score: Calculated stability score for the day
    """
    date: str
    n_recordings: int
    avg_similarity: float
    stability_score: float


@dataclass
class TrendResult:
    """
    Result of trend analysis over a period.

    Attributes:
        direction: "improving", "stable", or "declining"
        slope: Rate of change (positive = improving)
        confidence: Statistical confidence in the trend
        period_days: Number of days analyzed
    """
    direction: str
    slope: float
    confidence: float
    period_days: int
