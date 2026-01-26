#!/usr/bin/env python3
"""
HEAR Model Worker Subprocess

This script runs in a separate process to isolate TensorFlow from the main
Nota application (which uses faster-whisper). This prevents library conflicts
and ensures memory is freed after analysis completes.

Usage:
    python -m health.analyzer_worker '["path1.wav", "path2.wav"]'

Output:
    JSON array of results to stdout
"""

import sys
import json
import logging

# Configure logging to stderr so it doesn't interfere with JSON output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger('Notta.health.worker')


def process_audio_files(audio_paths: list) -> list:
    """
    Process audio files through the HEAR model.

    Args:
        audio_paths: List of absolute paths to WAV files

    Returns:
        List of result dicts with embeddings
    """
    # Import heavy dependencies only when needed
    import numpy as np

    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import GatedRepoError
        import librosa
        import keras
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install with: pip install tensorflow huggingface-hub librosa")
        raise

    # Load HEAR model (downloads on first use, ~1GB)
    logger.info("Loading HEAR model from Hugging Face...")
    try:
        # Download the model files
        model_path = snapshot_download("google/hear")
        logger.info(f"Model downloaded to: {model_path}")

        # Load as TFSMLayer (Keras 3 compatible way to load SavedModel)
        model = keras.layers.TFSMLayer(model_path, call_endpoint='serving_default')
        logger.info("HEAR model loaded successfully")
    except GatedRepoError as e:
        logger.error("HEAR model requires authentication.")
        logger.error("Steps to fix:")
        logger.error("1. Visit https://huggingface.co/google/hear and request access")
        logger.error("2. Run: hf auth login")
        raise RuntimeError(
            "HEAR model access denied. Visit https://huggingface.co/google/hear "
            "to request access, then run 'hf auth login' in terminal."
        ) from e
    except Exception as e:
        logger.error(f"Failed to load HEAR model: {e}")
        raise

    results = []

    for path in audio_paths:
        try:
            logger.info(f"Processing: {path}")

            # Load audio at 16kHz mono (HEAR requirement)
            audio, sr = librosa.load(path, sr=16000, mono=True)
            duration_seconds = len(audio) / sr

            # Split into 2-second chunks (32000 samples at 16kHz)
            chunk_size = 32000
            chunks = []

            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i + chunk_size]
                # Only process chunks that are at least 1 second (16000 samples)
                if len(chunk) >= chunk_size // 2:
                    # Pad short chunks to exactly 2 seconds
                    if len(chunk) < chunk_size:
                        chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                    chunks.append(chunk)

            if not chunks:
                logger.warning(f"No valid chunks in {path} (too short?)")
                continue

            # Batch process all chunks
            batch = np.array(chunks, dtype=np.float32)

            # Run HEAR inference
            import tensorflow as tf
            tensor = tf.constant(batch)
            output = model(tensor)

            # Handle different output formats
            if isinstance(output, dict):
                # Get the first output key
                key = list(output.keys())[0]
                embeddings = output[key].numpy()
            else:
                embeddings = output.numpy()

            results.append({
                'audio_file': path,
                'embeddings': embeddings.tolist(),
                'n_chunks': len(chunks),
                'duration_seconds': duration_seconds
            })

            logger.info(f"Generated {len(chunks)} embeddings for {path}")

        except Exception as e:
            logger.error(f"Error processing {path}: {e}")
            # Continue with other files
            continue

    return results


def main():
    """Main entry point for subprocess."""
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'No audio paths provided'}))
        sys.exit(1)

    try:
        audio_paths = json.loads(sys.argv[1])

        if not isinstance(audio_paths, list):
            print(json.dumps({'error': 'Expected JSON array of paths'}))
            sys.exit(1)

        if not audio_paths:
            print(json.dumps([]))
            sys.exit(0)

        results = process_audio_files(audio_paths)
        print(json.dumps(results))

    except json.JSONDecodeError as e:
        print(json.dumps({'error': f'Invalid JSON: {e}'}))
        sys.exit(1)
    except Exception as e:
        logger.exception("Worker failed")
        print(json.dumps({'error': str(e)}))
        sys.exit(1)


if __name__ == '__main__':
    main()
