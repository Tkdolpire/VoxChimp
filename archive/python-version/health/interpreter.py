"""
EmbeddingInterpreter - Converts HEAR embeddings into meaningful health insights.

This module bridges the gap between raw 512-dimensional embeddings and
actionable health information that users can understand and act upon.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from .metrics import VoiceStabilityScore, DailySummary, TrendResult
from .baseline_manager import BaselineManager

logger = logging.getLogger('Notta.health.interpreter')


class EmbeddingInterpreter:
    """
    Interprets HEAR embeddings to generate meaningful voice health metrics.

    The interpreter computes a personal baseline from historical data and
    measures how current recordings compare to that baseline. Changes in
    voice patterns can indicate various health conditions.
    """

    # Score interpretation thresholds (cosine similarity values)
    # These are based on typical voice variation patterns
    SIMILARITY_EXCELLENT = 0.97   # Very consistent voice
    SIMILARITY_GOOD = 0.93        # Normal variation
    SIMILARITY_MODERATE = 0.88    # Noticeable changes
    SIMILARITY_CONCERNING = 0.80  # Significant changes

    def __init__(self, store):
        """
        Initialize interpreter with an EmbeddingStore.

        Args:
            store: EmbeddingStore instance for accessing embeddings
        """
        self.store = store
        self.baseline_manager = BaselineManager(store)

    def get_voice_stability_score(self) -> VoiceStabilityScore:
        """
        Calculate the main user-facing Voice Stability Score.

        This is the primary metric shown to users, representing how
        consistent their voice patterns are compared to their baseline.

        Returns:
            VoiceStabilityScore with score, trend, confidence, and message
        """
        baseline = self.baseline_manager.get_baseline()

        # Handle insufficient data for baseline
        if not baseline.is_valid:
            current, required = self.baseline_manager.get_sample_progress()
            return VoiceStabilityScore(
                score=0,
                trend="insufficient_data",
                confidence=0,
                message=self._get_cold_start_message(current, required)
            )

        # Get recent embeddings (last 7 days)
        recent_embeddings = self._get_recent_embeddings(days=7)

        if not recent_embeddings:
            return VoiceStabilityScore(
                score=0,
                trend="no_recent_data",
                confidence=0,
                message="No recent recordings. Use Notta to track your voice health."
            )

        # Calculate similarities to baseline
        similarities = [
            self._cosine_similarity(emb, baseline.mean_embedding)
            for emb in recent_embeddings
        ]

        avg_similarity = sum(similarities) / len(similarities)
        score = self._similarity_to_score(avg_similarity)

        # Calculate trend from similarity progression
        trend_result = self._compute_trend(similarities)

        # Confidence based on data quantity
        confidence = min(len(recent_embeddings) / 20, 1.0)

        # Generate meaningful health message
        message = self._generate_health_message(score, avg_similarity, trend_result)

        return VoiceStabilityScore(
            score=round(score, 1),
            trend=trend_result.direction,
            confidence=round(confidence, 2),
            message=message
        )

    def get_daily_summary(self, date: Optional[datetime] = None) -> Optional[DailySummary]:
        """
        Get voice metrics summary for a specific day.

        Args:
            date: Date to summarize (defaults to today)

        Returns:
            DailySummary or None if no data for that day
        """
        if date is None:
            date = datetime.now()

        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        embeddings = self.store.get_embeddings_for_period(start, end)
        if not embeddings:
            return None

        baseline = self.baseline_manager.get_baseline()
        if not baseline.is_valid:
            return DailySummary(
                date=date.strftime('%Y-%m-%d'),
                n_recordings=len(embeddings),
                avg_similarity=0,
                stability_score=0
            )

        mean_embeddings = [e['mean_embedding'] for e in embeddings if e.get('mean_embedding')]
        if not mean_embeddings:
            return None

        similarities = [
            self._cosine_similarity(emb, baseline.mean_embedding)
            for emb in mean_embeddings
        ]

        avg_sim = sum(similarities) / len(similarities)
        score = self._similarity_to_score(avg_sim)

        return DailySummary(
            date=date.strftime('%Y-%m-%d'),
            n_recordings=len(embeddings),
            avg_similarity=round(avg_sim, 4),
            stability_score=round(score, 1)
        )

    def get_detailed_insights(self) -> Dict:
        """
        Get detailed insights about voice patterns for advanced users.

        Returns:
            Dictionary with detailed metrics and insights
        """
        baseline = self.baseline_manager.get_baseline()
        total_recordings = self.store.get_embedding_count()

        insights = {
            'baseline_valid': baseline.is_valid,
            'baseline_samples': baseline.n_samples,
            'total_recordings': total_recordings,
            'recent_recordings': 0,
            'average_similarity': None,
            'similarity_range': None,
            'trend_7day': None,
            'health_indicators': []
        }

        if not baseline.is_valid:
            return insights

        recent = self._get_recent_embeddings(days=7)
        insights['recent_recordings'] = len(recent)

        if recent:
            similarities = [
                self._cosine_similarity(emb, baseline.mean_embedding)
                for emb in recent
            ]
            insights['average_similarity'] = round(sum(similarities) / len(similarities), 4)
            insights['similarity_range'] = {
                'min': round(min(similarities), 4),
                'max': round(max(similarities), 4)
            }

            trend = self._compute_trend(similarities)
            insights['trend_7day'] = {
                'direction': trend.direction,
                'confidence': round(trend.confidence, 2)
            }

            # Generate health indicators
            insights['health_indicators'] = self._generate_health_indicators(
                insights['average_similarity'],
                trend.direction
            )

        return insights

    def _get_recent_embeddings(self, days: int = 7) -> List[List[float]]:
        """Get mean embeddings from the last N days."""
        end = datetime.now()
        start = end - timedelta(days=days)

        entries = self.store.get_embeddings_for_period(start, end)
        return [e['mean_embedding'] for e in entries if e.get('mean_embedding')]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _similarity_to_score(self, similarity: float) -> float:
        """
        Map cosine similarity to a 0-100 score.

        Similarity typically ranges from 0.7 to 1.0 for voice data.
        Maps [0.7, 1.0] -> [0, 100] with slight non-linearity
        to make high scores harder to achieve.
        """
        # Clamp similarity to expected range
        sim = max(0.7, min(1.0, similarity))

        # Linear mapping with bonus for very high similarity
        base_score = (sim - 0.7) / 0.3 * 100

        # Slight adjustment: make it harder to get >95
        if base_score > 90:
            base_score = 90 + (base_score - 90) * 0.5

        return max(0, min(100, base_score))

    def _compute_trend(self, similarities: List[float]) -> TrendResult:
        """
        Compute trend from a sequence of similarities.

        Uses simple linear regression to detect improving/declining patterns.
        """
        n = len(similarities)

        if n < 3:
            return TrendResult(
                direction="stable",
                slope=0,
                confidence=0,
                period_days=n
            )

        # Simple linear regression
        x_mean = (n - 1) / 2
        y_mean = sum(similarities) / n

        numerator = sum((i - x_mean) * (similarities[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        # Calculate R-squared for confidence
        ss_tot = sum((y - y_mean) ** 2 for y in similarities)
        if ss_tot == 0:
            r_squared = 0
        else:
            predictions = [slope * i + (y_mean - slope * x_mean) for i in range(n)]
            ss_res = sum((similarities[i] - predictions[i]) ** 2 for i in range(n))
            r_squared = 1 - (ss_res / ss_tot)

        # Determine direction (threshold for "significant" trend)
        if abs(slope) < 0.005:  # Less than 0.5% change per recording
            direction = "stable"
        elif slope > 0:
            direction = "improving"
        else:
            direction = "declining"

        return TrendResult(
            direction=direction,
            slope=slope,
            confidence=max(0, r_squared),
            period_days=n
        )

    def _get_cold_start_message(self, current: int, required: int) -> str:
        """Generate message during baseline building phase."""
        if current == 0:
            return "Start recording to build your voice baseline. Your personal pattern will be learned over time."
        elif current < 5:
            return f"Building your baseline: {current}/{required} recordings. Keep using Notta to establish your voice pattern."
        else:
            return f"Almost there: {current}/{required} recordings. A few more uses will complete your personal baseline."

    def _generate_health_message(self, score: float, similarity: float,
                                  trend: TrendResult) -> str:
        """
        Generate a meaningful, health-focused message based on the score.

        The message explains what the score means in terms of potential
        health implications and what actions, if any, to consider.
        """
        # Excellent stability (90-100)
        if score >= 90:
            if trend.direction == "improving":
                return "Your voice is very consistent - a sign of good vocal and respiratory health. Keep it up!"
            elif trend.direction == "declining":
                return "Your voice remains stable overall. Minor fluctuations are normal day-to-day."
            else:
                return "Your voice pattern is highly consistent, suggesting good overall vocal health."

        # Good stability (70-89)
        elif score >= 70:
            if trend.direction == "declining":
                return "Your voice shows some variation. This can happen with fatigue, mild congestion, or stress. Monitor if it persists."
            elif trend.direction == "improving":
                return "Your voice patterns are normalizing. Good hydration and rest support vocal health."
            else:
                return "Normal voice variation detected. Factors like time of day, hydration, and energy levels affect your voice."

        # Moderate changes (50-69)
        elif score >= 50:
            messages = [
                "Noticeable voice changes detected. Common causes include:",
                "- Upper respiratory issues (cold, allergies)",
                "- Dehydration or voice strain",
                "- Fatigue or stress",
                "Consider rest and hydration. If changes persist over several days, consult a healthcare provider."
            ]
            return " ".join(messages)

        # Significant changes (<50)
        else:
            messages = [
                "Significant changes in your voice pattern.",
                "This could indicate:",
                "- Active illness (cold, flu, respiratory infection)",
                "- Vocal cord strain or laryngitis",
                "- Allergic reaction",
                "If you're feeling unwell, rest your voice. If changes persist beyond a few days without explanation, consider consulting a doctor."
            ]
            return " ".join(messages)

    def _generate_health_indicators(self, avg_similarity: float,
                                     trend_direction: str) -> List[Dict]:
        """
        Generate specific health indicators based on voice patterns.

        Returns list of indicators with status and descriptions.
        """
        indicators = []

        # Vocal consistency indicator
        if avg_similarity >= 0.95:
            indicators.append({
                'name': 'Vocal Consistency',
                'status': 'excellent',
                'description': 'Voice patterns are highly stable'
            })
        elif avg_similarity >= 0.90:
            indicators.append({
                'name': 'Vocal Consistency',
                'status': 'good',
                'description': 'Normal voice variation'
            })
        elif avg_similarity >= 0.85:
            indicators.append({
                'name': 'Vocal Consistency',
                'status': 'monitor',
                'description': 'Elevated variation - may indicate fatigue or mild illness'
            })
        else:
            indicators.append({
                'name': 'Vocal Consistency',
                'status': 'attention',
                'description': 'Significant changes - consider rest and hydration'
            })

        # Trend indicator
        if trend_direction == "improving":
            indicators.append({
                'name': 'Recovery Trend',
                'status': 'positive',
                'description': 'Voice patterns returning toward baseline'
            })
        elif trend_direction == "declining":
            indicators.append({
                'name': 'Change Trend',
                'status': 'monitor',
                'description': 'Voice patterns diverging from baseline'
            })
        else:
            indicators.append({
                'name': 'Stability Trend',
                'status': 'stable',
                'description': 'Consistent patterns over recent recordings'
            })

        return indicators
