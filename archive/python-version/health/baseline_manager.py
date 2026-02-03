"""
BaselineManager - Manages personal voice baseline computation and storage.

The baseline represents the user's "normal" voice pattern, computed from
historical recordings. Deviations from this baseline may indicate changes
in vocal health or wellness.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from .metrics import BaselineResult

logger = logging.getLogger('Notta.health.baseline')


class BaselineManager:
    """
    Manages the computation and persistence of personal voice baselines.

    The baseline is computed from mean embeddings of all analyzed recordings,
    creating a personalized reference point for detecting changes.
    """

    BASELINE_FILE = Path.home() / '.notta_health' / 'baseline.json'
    MIN_SAMPLES = 10  # Minimum recordings needed for valid baseline

    def __init__(self, store):
        """
        Initialize with an EmbeddingStore instance.

        Args:
            store: EmbeddingStore for accessing embedding data
        """
        self.store = store
        self._cached_baseline: Optional[BaselineResult] = None
        self._cache_valid = False

    def get_baseline(self, force_recompute: bool = False) -> BaselineResult:
        """
        Get the current baseline, computing if needed.

        Args:
            force_recompute: If True, recompute even if cached

        Returns:
            BaselineResult with baseline data or invalid flag if insufficient data
        """
        # Return cached if available and not forcing recompute
        if self._cache_valid and not force_recompute and self._cached_baseline:
            return self._cached_baseline

        # Try to load from file
        if not force_recompute and self.BASELINE_FILE.exists():
            loaded = self._load_baseline()
            if loaded and loaded.is_valid:
                # Check if we have significantly more data now
                current_count = self.store.get_embedding_count()
                if current_count > loaded.n_samples * 1.2:  # 20% more data
                    logger.info(f"Recomputing baseline: {current_count} samples vs {loaded.n_samples} stored")
                else:
                    self._cached_baseline = loaded
                    self._cache_valid = True
                    return loaded

        # Compute fresh baseline
        baseline = self.compute_baseline()
        self._cached_baseline = baseline
        self._cache_valid = True
        return baseline

    def compute_baseline(self) -> BaselineResult:
        """
        Compute baseline from all stored embeddings.

        Returns:
            BaselineResult with computed baseline or invalid flag
        """
        embeddings = self.store.get_all_embeddings()

        if len(embeddings) < self.MIN_SAMPLES:
            logger.info(f"Insufficient data for baseline: {len(embeddings)}/{self.MIN_SAMPLES}")
            return BaselineResult(
                n_samples=len(embeddings),
                is_valid=False
            )

        # Extract mean embeddings from each recording
        mean_embeddings = []
        for entry in embeddings:
            if 'mean_embedding' in entry and entry['mean_embedding']:
                mean_embeddings.append(entry['mean_embedding'])

        if not mean_embeddings:
            logger.warning("No valid embeddings found")
            return BaselineResult(is_valid=False)

        # Compute mean and std across all recordings
        n_dims = len(mean_embeddings[0])
        n_samples = len(mean_embeddings)

        # Mean: average of each dimension
        mean = [
            sum(emb[i] for emb in mean_embeddings) / n_samples
            for i in range(n_dims)
        ]

        # Std: standard deviation of each dimension
        std = [
            (sum((emb[i] - mean[i]) ** 2 for emb in mean_embeddings) / n_samples) ** 0.5
            for i in range(n_dims)
        ]

        result = BaselineResult(
            mean_embedding=mean,
            std_embedding=std,
            n_samples=n_samples,
            computed_at=datetime.now().isoformat(),
            is_valid=True
        )

        # Persist to file
        self._save_baseline(result)
        logger.info(f"Computed baseline from {n_samples} recordings")

        return result

    def _save_baseline(self, baseline: BaselineResult):
        """Save baseline to JSON file."""
        try:
            self.BASELINE_FILE.parent.mkdir(exist_ok=True)
            data = {
                'version': 1,
                'mean_embedding': baseline.mean_embedding,
                'std_embedding': baseline.std_embedding,
                'n_samples': baseline.n_samples,
                'computed_at': baseline.computed_at,
                'is_valid': baseline.is_valid
            }
            with open(self.BASELINE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Baseline saved to {self.BASELINE_FILE}")
        except IOError as e:
            logger.error(f"Failed to save baseline: {e}")

    def _load_baseline(self) -> Optional[BaselineResult]:
        """Load baseline from JSON file."""
        try:
            with open(self.BASELINE_FILE, 'r') as f:
                data = json.load(f)
            return BaselineResult(
                mean_embedding=data.get('mean_embedding', []),
                std_embedding=data.get('std_embedding', []),
                n_samples=data.get('n_samples', 0),
                computed_at=data.get('computed_at'),
                is_valid=data.get('is_valid', False)
            )
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load baseline: {e}")
            return None

    def invalidate_cache(self):
        """Invalidate cached baseline, forcing recompute on next access."""
        self._cache_valid = False
        self._cached_baseline = None

    def get_sample_progress(self) -> tuple:
        """
        Get progress toward minimum baseline samples.

        Returns:
            Tuple of (current_count, min_required)
        """
        current = self.store.get_embedding_count()
        return (current, self.MIN_SAMPLES)
