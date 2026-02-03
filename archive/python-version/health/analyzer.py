"""
HealthAnalyzer - Coordinator for HEAR health analysis

Manages the analysis workflow:
1. Finds unanalyzed audio recordings
2. Spawns subprocess to run TensorFlow/HEAR
3. Stores results in EmbeddingStore
"""

import subprocess
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Callable

from .embedding_store import EmbeddingStore

logger = logging.getLogger('Notta.health.analyzer')


class HealthAnalyzer:
    """Coordinates HEAR health analysis of voice recordings."""

    def __init__(self, audio_dir: Optional[Path] = None):
        """
        Initialize the health analyzer.

        Args:
            audio_dir: Directory containing audio recordings.
                      Defaults to ~/.nota_audio
        """
        self.audio_dir = Path(audio_dir or Path.home() / '.notta_audio')
        self.store = EmbeddingStore()

    def get_status(self) -> Dict:
        """
        Get current status for UI display.

        Returns:
            Dict with keys:
                - total_analyzed: Number of recordings analyzed
                - unanalyzed_count: Number of recordings pending analysis
                - last_analysis: ISO timestamp of most recent analysis
        """
        analyzed_count = self.store.get_embedding_count()
        unanalyzed = self.store.get_unanalyzed_recordings(self.audio_dir)
        last_analysis = self.store.get_last_analysis_time()

        return {
            'total_analyzed': analyzed_count,
            'unanalyzed_count': len(unanalyzed),
            'last_analysis': last_analysis
        }

    def analyze_pending(self, callback: Optional[Callable[[str], None]] = None,
                        batch_size: int = 10) -> Dict:
        """
        Analyze all unanalyzed recordings.

        Args:
            callback: Optional function to call with status updates
            batch_size: Maximum files to process in one subprocess call

        Returns:
            Dict with keys:
                - analyzed: Number of recordings processed
                - message: Human-readable status message
                - errors: List of any errors encountered
        """
        pending = self.store.get_unanalyzed_recordings(self.audio_dir)

        if not pending:
            return {
                'analyzed': 0,
                'message': 'No new recordings to analyze',
                'errors': []
            }

        if callback:
            callback(f"Found {len(pending)} recordings to analyze...")

        logger.info(f"Starting analysis of {len(pending)} recordings")

        total_analyzed = 0
        errors = []

        # Process in batches to avoid memory issues
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i + batch_size]

            if callback:
                callback(f"Processing batch {i // batch_size + 1}...")

            try:
                results = self._run_worker(batch)

                # Store each result
                for result in results:
                    self.store.store_embedding(
                        audio_file=result['audio_file'],
                        embeddings=result['embeddings'],
                        n_chunks=result['n_chunks'],
                        duration_seconds=result.get('duration_seconds')
                    )
                    total_analyzed += 1

            except Exception as e:
                logger.error(f"Batch analysis failed: {e}")
                errors.append(str(e))

        message = f"Analyzed {total_analyzed} recording{'s' if total_analyzed != 1 else ''}"
        if errors:
            message += f" ({len(errors)} error{'s' if len(errors) != 1 else ''})"

        logger.info(message)

        return {
            'analyzed': total_analyzed,
            'message': message,
            'errors': errors
        }

    def _run_worker(self, audio_paths: list) -> list:
        """
        Run the analyzer worker subprocess.

        Args:
            audio_paths: List of audio file paths to process

        Returns:
            List of result dicts from worker

        Raises:
            RuntimeError: If worker fails
        """
        # Determine the correct way to invoke the worker
        # When running from source: python -m health.analyzer_worker
        # When bundled: need to handle PyInstaller paths

        worker_module = 'health.analyzer_worker'

        # Find the project root (parent of health package)
        project_root = Path(__file__).parent.parent

        logger.debug(f"Running worker with {len(audio_paths)} files")
        logger.debug(f"Project root: {project_root}")

        try:
            result = subprocess.run(
                [sys.executable, '-m', worker_module, json.dumps(audio_paths)],
                capture_output=True,
                timeout=600,  # 10 minute timeout
                cwd=str(project_root),
                text=True
            )

            if result.returncode != 0:
                logger.error(f"Worker stderr: {result.stderr}")
                raise RuntimeError(f"Analysis worker failed: {result.stderr}")

            # Parse JSON output
            try:
                output = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.error(f"Worker output: {result.stdout}")
                raise RuntimeError(f"Worker returned invalid JSON: {e}")

            # Check for error response
            if isinstance(output, dict) and 'error' in output:
                raise RuntimeError(output['error'])

            return output

        except subprocess.TimeoutExpired:
            raise RuntimeError("Analysis timed out after 10 minutes")

    def check_dependencies(self) -> Dict:
        """
        Check if required dependencies are installed.

        Returns:
            Dict with keys:
                - ok: Boolean indicating all deps available
                - missing: List of missing package names
        """
        missing = []

        try:
            import tensorflow
        except ImportError:
            missing.append('tensorflow')

        try:
            import librosa
        except ImportError:
            missing.append('librosa')

        try:
            from huggingface_hub import from_pretrained_keras
        except ImportError:
            missing.append('huggingface-hub')

        return {
            'ok': len(missing) == 0,
            'missing': missing
        }
