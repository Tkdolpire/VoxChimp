"""
Tests for health/embedding_store.py - JSON storage for HEAR embeddings.

Coverage target: 99%+
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from health.embedding_store import EmbeddingStore


class TestEmbeddingStoreInit:
    """Tests for EmbeddingStore initialization."""

    def test_default_path(self, temp_dir, monkeypatch):
        """Test default path uses home directory."""
        monkeypatch.setattr(Path, 'home', lambda: temp_dir)
        store = EmbeddingStore()

        expected_path = temp_dir / '.notta_health'
        assert store.base_path == expected_path
        assert expected_path.exists()

    def test_custom_path(self, temp_health_dir):
        """Test custom base path."""
        store = EmbeddingStore(base_path=temp_health_dir)

        assert store.base_path == temp_health_dir
        assert store.embeddings_file == temp_health_dir / 'embeddings.json'

    def test_creates_directory(self, temp_dir):
        """Test that directory is created if it doesn't exist."""
        new_dir = temp_dir / 'new_health_dir'
        assert not new_dir.exists()

        store = EmbeddingStore(base_path=new_dir)

        assert new_dir.exists()

    def test_creates_embeddings_file(self, temp_health_dir):
        """Test that embeddings file is created with correct schema."""
        store = EmbeddingStore(base_path=temp_health_dir)

        assert store.embeddings_file.exists()

        with open(store.embeddings_file, 'r') as f:
            data = json.load(f)

        assert 'version' in data
        assert data['version'] == EmbeddingStore.SCHEMA_VERSION
        assert 'embeddings' in data
        assert data['embeddings'] == []


class TestEmbeddingStoreReadWrite:
    """Tests for reading and writing embeddings."""

    def test_read_empty_store(self, temp_health_dir):
        """Test reading from empty store."""
        store = EmbeddingStore(base_path=temp_health_dir)
        data = store._read_data()

        assert data['version'] == 1
        assert data['embeddings'] == []

    def test_read_corrupted_file(self, temp_health_dir):
        """Test reading corrupted JSON file."""
        store = EmbeddingStore(base_path=temp_health_dir)

        # Corrupt the file
        with open(store.embeddings_file, 'w') as f:
            f.write("not valid json {{{")

        data = store._read_data()

        # Should return empty structure on error
        assert data['version'] == 1
        assert data['embeddings'] == []

    def test_read_legacy_format(self, temp_health_dir):
        """Test reading legacy format without version."""
        store = EmbeddingStore(base_path=temp_health_dir)

        # Write legacy format (list only)
        with open(store.embeddings_file, 'w') as f:
            json.dump([{'audio_file': 'test.wav', 'embeddings': [[0.1, 0.2]]}], f)

        data = store._read_data()

        assert data['version'] == 1
        assert len(data['embeddings']) == 1

    def test_write_data(self, temp_health_dir):
        """Test writing data to file."""
        store = EmbeddingStore(base_path=temp_health_dir)

        test_data = {'version': 1, 'embeddings': [{'test': 'data'}]}
        store._write_data(test_data)

        with open(store.embeddings_file, 'r') as f:
            loaded = json.load(f)

        assert loaded == test_data


class TestStoreEmbedding:
    """Tests for store_embedding method."""

    def test_store_single_embedding(self, temp_health_dir, sample_embedding):
        """Test storing a single embedding."""
        store = EmbeddingStore(base_path=temp_health_dir)

        store.store_embedding(
            audio_file='/path/to/audio.wav',
            embeddings=[sample_embedding],
            n_chunks=1,
            duration_seconds=2.0
        )

        embeddings = store.get_all_embeddings()
        assert len(embeddings) == 1

        entry = embeddings[0]
        assert entry['audio_file'] == '/path/to/audio.wav'
        assert entry['n_chunks'] == 1
        assert entry['duration_seconds'] == 2.0
        assert 'mean_embedding' in entry
        assert len(entry['mean_embedding']) == 512

    def test_store_multiple_chunks(self, temp_health_dir):
        """Test storing embedding with multiple chunks."""
        store = EmbeddingStore(base_path=temp_health_dir)

        # Create 3 chunks of embeddings
        chunks = [
            [0.1 * i for i in range(512)],
            [0.2 * i for i in range(512)],
            [0.3 * i for i in range(512)]
        ]

        store.store_embedding(
            audio_file='/path/to/audio.wav',
            embeddings=chunks,
            n_chunks=3,
            duration_seconds=6.0
        )

        embeddings = store.get_all_embeddings()
        entry = embeddings[0]

        assert entry['n_chunks'] == 3
        assert len(entry['chunks']) == 3
        assert entry['chunks'][0]['start_ms'] == 0
        assert entry['chunks'][0]['end_ms'] == 2000
        assert entry['chunks'][1]['start_ms'] == 2000
        assert entry['chunks'][2]['start_ms'] == 4000

    def test_mean_embedding_calculated(self, temp_health_dir):
        """Test that mean embedding is correctly calculated."""
        store = EmbeddingStore(base_path=temp_health_dir)

        # Two chunks with known values
        chunk1 = [1.0] * 512
        chunk2 = [3.0] * 512

        store.store_embedding(
            audio_file='/path/to/audio.wav',
            embeddings=[chunk1, chunk2],
            n_chunks=2
        )

        embeddings = store.get_all_embeddings()
        mean_emb = embeddings[0]['mean_embedding']

        # Mean should be 2.0 for each dimension
        assert all(abs(v - 2.0) < 0.001 for v in mean_emb)

    def test_store_empty_embeddings(self, temp_health_dir):
        """Test storing with empty embeddings."""
        store = EmbeddingStore(base_path=temp_health_dir)

        store.store_embedding(
            audio_file='/path/to/audio.wav',
            embeddings=[],
            n_chunks=0
        )

        embeddings = store.get_all_embeddings()
        assert embeddings[0]['mean_embedding'] == []

    def test_store_generates_unique_id(self, temp_health_dir, sample_embedding):
        """Test that each stored embedding gets a unique ID."""
        import time
        store = EmbeddingStore(base_path=temp_health_dir)

        store.store_embedding('/audio1.wav', [sample_embedding], 1)
        time.sleep(1.1)  # Ensure different timestamp
        store.store_embedding('/audio2.wav', [sample_embedding], 1)

        embeddings = store.get_all_embeddings()
        ids = [e['id'] for e in embeddings]

        assert len(set(ids)) == 2  # All unique


class TestGetAnalyzedFiles:
    """Tests for get_analyzed_files method."""

    def test_empty_store(self, temp_health_dir):
        """Test with empty store."""
        store = EmbeddingStore(base_path=temp_health_dir)
        files = store.get_analyzed_files()

        assert files == set()

    def test_with_analyzed_files(self, temp_health_dir, sample_embedding):
        """Test with multiple analyzed files."""
        store = EmbeddingStore(base_path=temp_health_dir)

        files = ['/path/audio1.wav', '/path/audio2.wav', '/path/audio3.wav']
        for f in files:
            store.store_embedding(f, [sample_embedding], 1)

        analyzed = store.get_analyzed_files()

        assert analyzed == set(files)


class TestGetUnanalyzedRecordings:
    """Tests for get_unanalyzed_recordings method."""

    def test_nonexistent_directory(self, temp_health_dir):
        """Test with non-existent directory."""
        store = EmbeddingStore(base_path=temp_health_dir)
        nonexistent = Path('/nonexistent/path')

        result = store.get_unanalyzed_recordings(nonexistent)

        assert result == []

    def test_empty_directory(self, temp_health_dir, temp_audio_dir):
        """Test with empty audio directory."""
        store = EmbeddingStore(base_path=temp_health_dir)

        result = store.get_unanalyzed_recordings(temp_audio_dir)

        assert result == []

    def test_all_unanalyzed(self, temp_health_dir, multiple_wav_files):
        """Test when all files are unanalyzed."""
        store = EmbeddingStore(base_path=temp_health_dir)
        audio_dir = multiple_wav_files[0].parent

        result = store.get_unanalyzed_recordings(audio_dir)

        assert len(result) == len(multiple_wav_files)

    def test_some_analyzed(self, temp_health_dir, multiple_wav_files, sample_embedding):
        """Test when some files are already analyzed."""
        store = EmbeddingStore(base_path=temp_health_dir)
        audio_dir = multiple_wav_files[0].parent

        # Analyze first 5 files
        for f in multiple_wav_files[:5]:
            store.store_embedding(str(f.absolute()), [sample_embedding], 1)

        result = store.get_unanalyzed_recordings(audio_dir)

        assert len(result) == len(multiple_wav_files) - 5

    def test_all_analyzed(self, temp_health_dir, multiple_wav_files, sample_embedding):
        """Test when all files are analyzed."""
        store = EmbeddingStore(base_path=temp_health_dir)
        audio_dir = multiple_wav_files[0].parent

        for f in multiple_wav_files:
            store.store_embedding(str(f.absolute()), [sample_embedding], 1)

        result = store.get_unanalyzed_recordings(audio_dir)

        assert result == []

    def test_sorted_output(self, temp_health_dir, multiple_wav_files):
        """Test that output is sorted."""
        store = EmbeddingStore(base_path=temp_health_dir)
        audio_dir = multiple_wav_files[0].parent

        result = store.get_unanalyzed_recordings(audio_dir)

        assert result == sorted(result)


class TestGetEmbeddingCount:
    """Tests for get_embedding_count method."""

    def test_empty_store(self, temp_health_dir):
        """Test count on empty store."""
        store = EmbeddingStore(base_path=temp_health_dir)

        assert store.get_embedding_count() == 0

    def test_with_embeddings(self, populated_embedding_store):
        """Test count with embeddings."""
        count = populated_embedding_store.get_embedding_count()

        assert count == 15


class TestGetLastAnalysisTime:
    """Tests for get_last_analysis_time method."""

    def test_empty_store(self, temp_health_dir):
        """Test with empty store."""
        store = EmbeddingStore(base_path=temp_health_dir)

        result = store.get_last_analysis_time()

        assert result is None

    def test_with_embeddings(self, populated_embedding_store):
        """Test with embeddings."""
        result = populated_embedding_store.get_last_analysis_time()

        assert result is not None
        # Should be a valid ISO timestamp
        datetime.fromisoformat(result)


class TestGetEmbeddingsForPeriod:
    """Tests for get_embeddings_for_period method."""

    def test_empty_store(self, temp_health_dir):
        """Test with empty store."""
        store = EmbeddingStore(base_path=temp_health_dir)
        start = datetime.now() - timedelta(days=7)
        end = datetime.now()

        result = store.get_embeddings_for_period(start, end)

        assert result == []

    def test_all_in_period(self, populated_embedding_store):
        """Test when all embeddings are in period."""
        start = datetime.now() - timedelta(days=1)
        end = datetime.now() + timedelta(days=1)

        result = populated_embedding_store.get_embeddings_for_period(start, end)

        assert len(result) == 15

    def test_none_in_period(self, populated_embedding_store):
        """Test when no embeddings are in period."""
        # Use a past period
        start = datetime.now() - timedelta(days=30)
        end = datetime.now() - timedelta(days=20)

        result = populated_embedding_store.get_embeddings_for_period(start, end)

        assert result == []

    def test_partial_period(self, temp_health_dir, sample_embedding):
        """Test with some embeddings in period."""
        store = EmbeddingStore(base_path=temp_health_dir)

        # Store 3 embeddings (all with current timestamps)
        for i in range(3):
            store.store_embedding(f'/audio{i}.wav', [sample_embedding], 1)

        # Query for embeddings in last hour
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now() + timedelta(hours=1)

        result = store.get_embeddings_for_period(start, end)

        assert len(result) == 3

    def test_handles_invalid_timestamps(self, temp_health_dir):
        """Test handling of entries with invalid timestamps."""
        store = EmbeddingStore(base_path=temp_health_dir)

        # Manually write entry with invalid timestamp
        data = store._read_data()
        data['embeddings'].append({
            'audio_file': '/test.wav',
            'timestamp': 'invalid-timestamp'
        })
        store._write_data(data)

        start = datetime.now() - timedelta(days=1)
        end = datetime.now() + timedelta(days=1)

        # Should not raise, should skip invalid entry
        result = store.get_embeddings_for_period(start, end)

        assert result == []
