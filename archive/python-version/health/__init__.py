"""
Notta Health Analysis Module

Provides voice health analysis through:
1. Acoustic analysis (Parselmouth/Praat) - Validated biomarkers for fatigue/illness detection
2. HEAR embeddings - Research/experimental health representations
"""

from .analyzer import HealthAnalyzer
from .embedding_store import EmbeddingStore
from .interpreter import EmbeddingInterpreter
from .baseline_manager import BaselineManager
from .metrics import VoiceStabilityScore, BaselineResult, DailySummary, TrendResult
from .acoustic_analyzer import AcousticAnalyzer, AcousticFeatures, VoiceHealthStatus

__all__ = [
    # Acoustic analysis (primary)
    'AcousticAnalyzer',
    'AcousticFeatures',
    'VoiceHealthStatus',
    # HEAR embeddings (research)
    'HealthAnalyzer',
    'EmbeddingStore',
    'EmbeddingInterpreter',
    'BaselineManager',
    'VoiceStabilityScore',
    'BaselineResult',
    'DailySummary',
    'TrendResult'
]
