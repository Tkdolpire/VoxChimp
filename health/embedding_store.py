"""
EmbeddingStore - JSON storage for HEAR embeddings

Stores embeddings linked to audio files with metadata for tracking
which files have been analyzed and retrieving historical data.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional

logger = logging.getLogger('Notta.health.store')


class EmbeddingStore:
    """Manages persistent storage of HEAR embeddings."""

    SCHEMA_VERSION = 1

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize the embedding store.

        Args:
            base_path: Directory for storing health data. Defaults to ~/.nota_health
        """
        self.base_path = Path(base_path or Path.home() / '.notta_health')
        self.base_path.mkdir(exist_ok=True)
        self.embeddings_file = self.base_path / 'embeddings.json'
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create embeddings file if it doesn't exist."""
        if not self.embeddings_file.exists():
            self._write_data({'version': self.SCHEMA_VERSION, 'embeddings': []})

    def _read_data(self) -> Dict:
        """Read and parse the embeddings file."""
        try:
            with open(self.embeddings_file, 'r') as f:
                data = json.load(f)
            # Handle legacy format
            if 'version' not in data:
                data = {'version': self.SCHEMA_VERSION, 'embeddings': data if isinstance(data, list) else []}
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read embeddings file: {e}")
            return {'version': self.SCHEMA_VERSION, 'embeddings': []}

    def _write_data(self, data: Dict):
        """Write data to embeddings file."""
        try:
            with open(self.embeddings_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to write embeddings file: {e}")
            raise

    def get_analyzed_files(self) -> Set[str]:
        """
        Return set of audio file paths that have already been analyzed.

        Returns:
            Set of absolute file paths as strings
        """
        data = self._read_data()
        return {entry['audio_file'] for entry in data['embeddings'] if 'audio_file' in entry}

    def get_unanalyzed_recordings(self, audio_dir: Path) -> List[str]:
        """
        Return WAV files in audio_dir that haven't been analyzed yet.

        Args:
            audio_dir: Directory containing audio recordings

        Returns:
            List of absolute file paths for unanalyzed WAV files
        """
        if not audio_dir.exists():
            return []

        analyzed = self.get_analyzed_files()
        unanalyzed = []

        for wav_file in audio_dir.glob('*.wav'):
            abs_path = str(wav_file.absolute())
            if abs_path not in analyzed:
                unanalyzed.append(abs_path)

        # Sort by filename (which includes timestamp) for consistent ordering
        unanalyzed.sort()
        return unanalyzed

    def store_embedding(self, audio_file: str, embeddings: List[List[float]],
                        n_chunks: int, duration_seconds: Optional[float] = None):
        """
        Store embedding entry linked to an audio file.

        Args:
            audio_file: Path to the source audio file
            embeddings: List of 512-dimensional embedding vectors (one per chunk)
            n_chunks: Number of 2-second chunks processed
            duration_seconds: Total duration of audio in seconds
        """
        data = self._read_data()

        # Generate unique ID
        timestamp = datetime.now()
        entry_id = f"emb_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        # Calculate mean embedding across all chunks
        if embeddings:
            n_dims = len(embeddings[0])
            mean_embedding = [
                sum(emb[i] for emb in embeddings) / len(embeddings)
                for i in range(n_dims)
            ]
        else:
            mean_embedding = []

        # Build chunks list with timing info
        chunks = []
        for i, emb in enumerate(embeddings):
            chunks.append({
                'start_ms': i * 2000,
                'end_ms': (i + 1) * 2000,
                'embedding': emb
            })

        entry = {
            'id': entry_id,
            'audio_file': audio_file,
            'timestamp': timestamp.isoformat(),
            'duration_seconds': duration_seconds,
            'n_chunks': n_chunks,
            'chunks': chunks,
            'mean_embedding': mean_embedding,
            'analyzed_at': timestamp.isoformat()
        }

        data['embeddings'].append(entry)
        self._write_data(data)
        logger.info(f"Stored embedding {entry_id} for {audio_file}")

    def get_all_embeddings(self) -> List[Dict]:
        """
        Get all stored embeddings.

        Returns:
            List of embedding entries with full metadata
        """
        data = self._read_data()
        return data['embeddings']

    def get_embedding_count(self) -> int:
        """Return the total number of stored embeddings."""
        data = self._read_data()
        return len(data['embeddings'])

    def get_last_analysis_time(self) -> Optional[str]:
        """Return ISO timestamp of most recent analysis, or None."""
        data = self._read_data()
        if not data['embeddings']:
            return None

        # Find most recent by analyzed_at
        latest = max(data['embeddings'], key=lambda e: e.get('analyzed_at', ''))
        return latest.get('analyzed_at')

    def get_embeddings_for_period(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get embeddings within a date range.

        Args:
            start_date: Start of period (inclusive)
            end_date: End of period (inclusive)

        Returns:
            List of embedding entries within the period
        """
        data = self._read_data()
        results = []

        for entry in data['embeddings']:
            try:
                entry_time = datetime.fromisoformat(entry['timestamp'])
                if start_date <= entry_time <= end_date:
                    results.append(entry)
            except (KeyError, ValueError):
                continue

        return results
