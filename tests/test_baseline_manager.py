"""
Tests for health/baseline_manager.py - Personal voice baseline computation and storage.

Coverage target: 99%+
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch
from health.baseline_manager import BaselineManager
from health.metrics import BaselineResult


class TestBaselineManagerInit:
    """Tests for BaselineManager initialization."""

    def test_init_with_store(self, mock_embedding_store):
        """Test initialization with embedding store."""
        manager = BaselineManager(mock_embedding_store)

        assert manager.store == mock_embedding_store
        assert manager._cached_baseline is None
        assert manager._cache_valid is False

    def test_baseline_file_path(self, mock_embedding_store, monkeypatch, temp_dir):
        """Test baseline file path is set correctly."""
        monkeypatch.setattr(Path, 'home', lambda: temp_dir)

        # Access class constant
        expected = temp_dir / '.notta_health' / 'baseline.json'
        assert BaselineManager.BASELINE_FILE.name == 'baseline.json'

    def test_min_samples_constant(self):
        """Test minimum samples constant."""
        assert BaselineManager.MIN_SAMPLES == 10


class TestGetBaseline:
    """Tests for get_baseline method."""

    def test_insufficient_data(self, temp_health_dir, monkeypatch):
        """Test with insufficient data for baseline."""
        from health.embedding_store import EmbeddingStore

        # Patch the baseline file path to use temp directory
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', temp_health_dir / 'baseline.json')

        # Create fresh store with no data
        store = EmbeddingStore(base_path=temp_health_dir)
        manager = BaselineManager(store)

        result = manager.get_baseline()

        assert result.is_valid is False
        assert result.n_samples == 0

    def test_returns_valid_baseline(self, populated_embedding_store):
        """Test returns valid baseline with enough data."""
        manager = BaselineManager(populated_embedding_store)

        result = manager.get_baseline()

        assert result.is_valid is True
        assert result.n_samples >= BaselineManager.MIN_SAMPLES
        assert len(result.mean_embedding) == 512

    def test_caching(self, populated_embedding_store):
        """Test that baseline is cached."""
        manager = BaselineManager(populated_embedding_store)

        result1 = manager.get_baseline()
        result2 = manager.get_baseline()

        # Should be same object (cached)
        assert manager._cache_valid is True
        assert result1 == result2

    def test_force_recompute(self, populated_embedding_store):
        """Test force_recompute bypasses cache."""
        manager = BaselineManager(populated_embedding_store)

        result1 = manager.get_baseline()
        manager._cache_valid = True

        result2 = manager.get_baseline(force_recompute=True)

        # Should have recomputed
        assert result2.is_valid is True

    def test_loads_from_file(self, populated_embedding_store, temp_health_dir, monkeypatch):
        """Test loading baseline from file."""
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', temp_health_dir / 'baseline.json')

        manager = BaselineManager(populated_embedding_store)

        # First call computes and saves
        result1 = manager.get_baseline()
        assert result1.is_valid is True

        # Create new manager to test loading
        manager2 = BaselineManager(populated_embedding_store)
        result2 = manager2.get_baseline()

        assert result2.is_valid is True
        assert result2.n_samples == result1.n_samples

    def test_recomputes_with_more_data(self, populated_embedding_store, temp_health_dir, monkeypatch, sample_embedding):
        """Test recomputes when significantly more data is available."""
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', temp_health_dir / 'baseline.json')

        manager = BaselineManager(populated_embedding_store)
        result1 = manager.get_baseline()

        # Add more embeddings (>20% more)
        for i in range(10):
            populated_embedding_store.store_embedding(
                f'/new_audio_{i}.wav',
                [sample_embedding],
                1
            )

        # New manager should detect more data and recompute
        manager2 = BaselineManager(populated_embedding_store)
        manager2._cache_valid = False
        result2 = manager2.get_baseline()

        assert result2.n_samples > result1.n_samples


class TestComputeBaseline:
    """Tests for compute_baseline method."""

    def test_insufficient_samples(self, mock_embedding_store):
        """Test with fewer samples than minimum."""
        manager = BaselineManager(mock_embedding_store)

        # Store only 5 embeddings (less than MIN_SAMPLES)
        for i in range(5):
            mock_embedding_store.store_embedding(
                f'/audio{i}.wav',
                [[0.1] * 512],
                1
            )

        result = manager.compute_baseline()

        assert result.is_valid is False
        assert result.n_samples == 5

    def test_computes_mean_correctly(self, mock_embedding_store):
        """Test mean embedding is computed correctly."""
        manager = BaselineManager(mock_embedding_store)

        # Store 10 embeddings with known values
        for i in range(10):
            emb = [float(i)] * 512
            mock_embedding_store.store_embedding(f'/audio{i}.wav', [emb], 1)

        result = manager.compute_baseline()

        # Mean of 0,1,2,3,4,5,6,7,8,9 = 4.5
        expected_mean = 4.5
        assert abs(result.mean_embedding[0] - expected_mean) < 0.001

    def test_computes_std_correctly(self, mock_embedding_store):
        """Test standard deviation is computed correctly."""
        manager = BaselineManager(mock_embedding_store)

        # Store 10 embeddings with known values
        values = [0, 0, 0, 0, 0, 10, 10, 10, 10, 10]  # std = 5
        for i, val in enumerate(values):
            emb = [float(val)] * 512
            mock_embedding_store.store_embedding(f'/audio{i}.wav', [emb], 1)

        result = manager.compute_baseline()

        # Check standard deviation
        expected_std = 5.0
        assert abs(result.std_embedding[0] - expected_std) < 0.001

    def test_no_valid_embeddings(self, mock_embedding_store):
        """Test with embeddings that have no mean_embedding."""
        manager = BaselineManager(mock_embedding_store)

        # Manually insert entries without mean_embedding
        data = mock_embedding_store._read_data()
        for i in range(10):
            data['embeddings'].append({
                'audio_file': f'/audio{i}.wav',
                # No mean_embedding field
            })
        mock_embedding_store._write_data(data)

        result = manager.compute_baseline()

        assert result.is_valid is False

    def test_sets_timestamp(self, populated_embedding_store):
        """Test that computed_at timestamp is set."""
        manager = BaselineManager(populated_embedding_store)

        result = manager.compute_baseline()

        assert result.computed_at is not None
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(result.computed_at)


class TestSaveLoadBaseline:
    """Tests for _save_baseline and _load_baseline methods."""

    def test_save_baseline(self, mock_embedding_store, temp_health_dir, monkeypatch):
        """Test saving baseline to file."""
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', temp_health_dir / 'baseline.json')

        manager = BaselineManager(mock_embedding_store)

        baseline = BaselineResult(
            mean_embedding=[0.1, 0.2, 0.3],
            std_embedding=[0.01, 0.02, 0.03],
            n_samples=20,
            computed_at="2026-01-25T10:30:00",
            is_valid=True
        )

        manager._save_baseline(baseline)

        # Verify file was created
        assert (temp_health_dir / 'baseline.json').exists()

        with open(temp_health_dir / 'baseline.json', 'r') as f:
            data = json.load(f)

        assert data['version'] == 1
        assert data['mean_embedding'] == [0.1, 0.2, 0.3]
        assert data['n_samples'] == 20
        assert data['is_valid'] is True

    def test_load_baseline(self, mock_embedding_store, temp_health_dir, monkeypatch):
        """Test loading baseline from file."""
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', temp_health_dir / 'baseline.json')

        # Create baseline file
        baseline_data = {
            'version': 1,
            'mean_embedding': [0.5] * 512,
            'std_embedding': [0.1] * 512,
            'n_samples': 30,
            'computed_at': '2026-01-25T10:30:00',
            'is_valid': True
        }
        with open(temp_health_dir / 'baseline.json', 'w') as f:
            json.dump(baseline_data, f)

        manager = BaselineManager(mock_embedding_store)
        result = manager._load_baseline()

        assert result is not None
        assert result.is_valid is True
        assert result.n_samples == 30
        assert len(result.mean_embedding) == 512

    def test_load_nonexistent_file(self, mock_embedding_store, temp_health_dir, monkeypatch):
        """Test loading when file doesn't exist."""
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', temp_health_dir / 'nonexistent.json')

        manager = BaselineManager(mock_embedding_store)
        result = manager._load_baseline()

        assert result is None

    def test_load_corrupted_file(self, mock_embedding_store, temp_health_dir, monkeypatch):
        """Test loading corrupted baseline file."""
        baseline_file = temp_health_dir / 'baseline.json'
        monkeypatch.setattr(BaselineManager, 'BASELINE_FILE', baseline_file)

        # Write corrupted JSON
        with open(baseline_file, 'w') as f:
            f.write("not valid json")

        manager = BaselineManager(mock_embedding_store)
        result = manager._load_baseline()

        assert result is None


class TestInvalidateCache:
    """Tests for invalidate_cache method."""

    def test_invalidates_cache(self, populated_embedding_store):
        """Test that invalidate_cache clears the cache."""
        manager = BaselineManager(populated_embedding_store)

        # Build cache
        manager.get_baseline()
        assert manager._cache_valid is True
        assert manager._cached_baseline is not None

        # Invalidate
        manager.invalidate_cache()

        assert manager._cache_valid is False
        assert manager._cached_baseline is None


class TestGetSampleProgress:
    """Tests for get_sample_progress method."""

    def test_empty_store(self, mock_embedding_store):
        """Test progress with empty store."""
        manager = BaselineManager(mock_embedding_store)

        current, required = manager.get_sample_progress()

        assert current == 0
        assert required == BaselineManager.MIN_SAMPLES

    def test_partial_progress(self, mock_embedding_store, sample_embedding):
        """Test progress with some recordings."""
        manager = BaselineManager(mock_embedding_store)

        for i in range(5):
            mock_embedding_store.store_embedding(f'/audio{i}.wav', [sample_embedding], 1)

        current, required = manager.get_sample_progress()

        assert current == 5
        assert required == 10

    def test_complete_progress(self, populated_embedding_store):
        """Test progress with enough recordings."""
        manager = BaselineManager(populated_embedding_store)

        current, required = manager.get_sample_progress()

        assert current >= required
