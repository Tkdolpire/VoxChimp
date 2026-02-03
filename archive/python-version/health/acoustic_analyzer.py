"""
AcousticAnalyzer - Extracts validated voice biomarkers using Parselmouth (Praat).

This module measures scientifically validated acoustic features that correlate with:
- Fatigue: increased jitter, shimmer, slower speech rate, more pauses
- Illness (cold/flu): lower pitch, increased noise, changed formants, reduced HNR

References:
- Krajewski et al. (2009): Acoustic sleepiness detection
- Schuller et al. (2021): Voice analysis for COVID-19 detection
- Dibazar et al. (2002): Vocal disorders and HNR
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import json

logger = logging.getLogger('Notta.health.acoustic')


@dataclass
class AcousticFeatures:
    """
    Core acoustic biomarkers extracted from voice recordings.

    All values are raw measurements that can be compared against
    personal baselines to detect changes.
    """
    # Pitch features
    f0_mean: float = 0.0          # Mean fundamental frequency (Hz)
    f0_std: float = 0.0           # Pitch variability (Hz)
    f0_min: float = 0.0           # Minimum pitch (Hz)
    f0_max: float = 0.0           # Maximum pitch (Hz)

    # Voice quality features
    jitter_local: float = 0.0     # Cycle-to-cycle pitch variation (%)
    jitter_rap: float = 0.0       # Relative average perturbation (%)
    shimmer_local: float = 0.0    # Cycle-to-cycle amplitude variation (%)
    shimmer_apq3: float = 0.0     # Amplitude perturbation quotient (%)
    hnr: float = 0.0              # Harmonic-to-noise ratio (dB)

    # Formants (vocal tract resonances)
    f1_mean: float = 0.0          # First formant - jaw opening (Hz)
    f2_mean: float = 0.0          # Second formant - tongue position (Hz)
    f3_mean: float = 0.0          # Third formant - lip rounding (Hz)

    # Temporal features
    duration: float = 0.0         # Total duration (seconds)
    voiced_fraction: float = 0.0  # Fraction of voiced segments
    speech_rate: float = 0.0      # Estimated syllables per second
    pause_rate: float = 0.0       # Pauses per second

    # Metadata
    timestamp: str = ""
    audio_path: str = ""


@dataclass
class VoiceHealthStatus:
    """
    Interpreted health status from acoustic analysis.
    """
    fatigue_score: float = 0.0        # 0-100, higher = more fatigued
    illness_score: float = 0.0        # 0-100, higher = more likely ill
    fatigue_indicators: List[str] = field(default_factory=list)
    illness_indicators: List[str] = field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.0


class AcousticAnalyzer:
    """
    Extracts acoustic biomarkers from voice recordings using Parselmouth/Praat.

    Parselmouth is the gold-standard for acoustic voice analysis, providing
    clinically validated measurements of voice quality.
    """

    # Feature storage
    ACOUSTIC_FILE = Path.home() / '.notta_health' / 'acoustic_features.json'
    ACOUSTIC_BASELINE_FILE = Path.home() / '.notta_health' / 'acoustic_baseline.json'

    # Minimum samples for baseline
    MIN_BASELINE_SAMPLES = 5

    # Thresholds based on literature (percentage change from baseline)
    FATIGUE_JITTER_INCREASE = 0.3      # 30% increase suggests fatigue
    FATIGUE_SHIMMER_INCREASE = 0.25    # 25% increase suggests fatigue
    FATIGUE_HNR_DECREASE = 0.15        # 15% decrease suggests fatigue
    FATIGUE_SPEECH_RATE_DECREASE = 0.2 # 20% slower suggests fatigue

    ILLNESS_F0_CHANGE = 0.1            # 10% change in pitch
    ILLNESS_HNR_DECREASE = 0.2         # 20% decrease in voice clarity
    ILLNESS_FORMANT_CHANGE = 0.15      # 15% change (nasality)

    def __init__(self):
        self._parselmouth = None
        self._features_cache: List[AcousticFeatures] = []
        self._baseline: Optional[AcousticFeatures] = None
        self._load_features()
        self._load_baseline()

    def _get_parselmouth(self):
        """Lazy load parselmouth to avoid import errors if not installed."""
        if self._parselmouth is None:
            try:
                import parselmouth
                self._parselmouth = parselmouth
                logger.info("Parselmouth loaded successfully")
            except ImportError:
                logger.warning("Parselmouth not installed - acoustic analysis unavailable")
                logger.warning("Install with: pip install praat-parselmouth")
                return None
        return self._parselmouth

    def analyze_audio(self, audio_path: str) -> Optional[AcousticFeatures]:
        """
        Extract acoustic features from an audio file.

        Args:
            audio_path: Path to WAV audio file

        Returns:
            AcousticFeatures or None if analysis fails
        """
        pm = self._get_parselmouth()
        if pm is None:
            return None

        try:
            # Load audio
            sound = pm.Sound(audio_path)

            # Extract pitch
            pitch = sound.to_pitch()
            pitch_values = pitch.selected_array['frequency']
            pitch_values = [p for p in pitch_values if p > 0]  # Filter unvoiced

            if not pitch_values:
                logger.warning(f"No voiced segments found in {audio_path}")
                return None

            # Extract point process for jitter/shimmer
            point_process = pm.praat.call(sound, "To PointProcess (periodic, cc)",
                                          75, 600)  # F0 range

            # Extract formants
            formant = sound.to_formant_burg()

            features = AcousticFeatures(
                # Pitch features
                f0_mean=sum(pitch_values) / len(pitch_values),
                f0_std=self._std(pitch_values),
                f0_min=min(pitch_values),
                f0_max=max(pitch_values),

                # Voice quality - using Praat commands
                jitter_local=self._safe_call(pm.praat.call, point_process,
                    "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100,
                jitter_rap=self._safe_call(pm.praat.call, point_process,
                    "Get jitter (rap)", 0, 0, 0.0001, 0.02, 1.3) * 100,
                shimmer_local=self._safe_call(pm.praat.call,
                    [sound, point_process], "Get shimmer (local)",
                    0, 0, 0.0001, 0.02, 1.3, 1.6) * 100,
                shimmer_apq3=self._safe_call(pm.praat.call,
                    [sound, point_process], "Get shimmer (apq3)",
                    0, 0, 0.0001, 0.02, 1.3, 1.6) * 100,
                hnr=self._get_hnr(sound, pm),

                # Formants (averaged over voiced regions)
                f1_mean=self._get_mean_formant(formant, 1, sound.duration),
                f2_mean=self._get_mean_formant(formant, 2, sound.duration),
                f3_mean=self._get_mean_formant(formant, 3, sound.duration),

                # Temporal features
                duration=sound.duration,
                voiced_fraction=len(pitch_values) / len(pitch.selected_array['frequency']),
                speech_rate=self._estimate_speech_rate(sound, pm),
                pause_rate=self._estimate_pause_rate(sound, pm),

                # Metadata
                timestamp=datetime.now().isoformat(),
                audio_path=audio_path
            )

            # Store features
            self._features_cache.append(features)
            self._save_features()

            # Update baseline if we have enough samples
            if len(self._features_cache) >= self.MIN_BASELINE_SAMPLES:
                self._update_baseline()

            logger.info(f"Extracted acoustic features from {audio_path}")
            return features

        except Exception as e:
            logger.error(f"Acoustic analysis failed: {e}")
            return None

    def _safe_call(self, func, *args):
        """Safely call a Praat function, returning 0 on error."""
        try:
            return func(*args)
        except Exception as e:
            logger.debug(f"Praat call failed: {e}")
            return 0.0

    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)

    def _get_hnr(self, sound, pm) -> float:
        """Extract harmonics-to-noise ratio."""
        try:
            harmonicity = pm.praat.call(sound, "To Harmonicity (cc)",
                                        0.01, 75, 0.1, 1.0)
            return pm.praat.call(harmonicity, "Get mean", 0, 0)
        except Exception as e:
            logger.debug(f"HNR extraction failed: {e}")
            return 0.0

    def _get_mean_formant(self, formant, formant_num: int, duration: float) -> float:
        """Get mean formant frequency over the recording."""
        try:
            import parselmouth
            return parselmouth.praat.call(formant, "Get mean",
                                          formant_num, 0, duration, "Hertz")
        except Exception as e:
            logger.debug(f"Formant extraction failed: {e}")
            return 0.0

    def _estimate_speech_rate(self, sound, pm) -> float:
        """
        Estimate speech rate using intensity peaks as syllable proxies.
        This is a simplified estimate - actual syllable detection is complex.
        """
        try:
            intensity = sound.to_intensity()
            # Count peaks above threshold as syllable estimates
            intensity_values = intensity.values[0]
            threshold = max(intensity_values) * 0.5

            peaks = 0
            prev_above = False
            for val in intensity_values:
                above = val > threshold
                if above and not prev_above:
                    peaks += 1
                prev_above = above

            return peaks / sound.duration if sound.duration > 0 else 0
        except Exception as e:
            logger.debug(f"Speech rate estimation failed: {e}")
            return 0.0

    def _estimate_pause_rate(self, sound, pm) -> float:
        """Estimate number of pauses per second."""
        try:
            intensity = sound.to_intensity()
            intensity_values = intensity.values[0]
            threshold = max(intensity_values) * 0.3  # Below 30% = pause

            pauses = 0
            in_pause = False
            for val in intensity_values:
                if val < threshold and not in_pause:
                    pauses += 1
                    in_pause = True
                elif val >= threshold:
                    in_pause = False

            return pauses / sound.duration if sound.duration > 0 else 0
        except Exception as e:
            logger.debug(f"Pause rate estimation failed: {e}")
            return 0.0

    def get_health_status(self, features: Optional[AcousticFeatures] = None) -> VoiceHealthStatus:
        """
        Analyze acoustic features to determine health status.

        Compares current features against personal baseline to detect
        signs of fatigue or illness.

        Args:
            features: Features to analyze (uses latest if None)

        Returns:
            VoiceHealthStatus with fatigue/illness scores and recommendations
        """
        if features is None:
            if not self._features_cache:
                return VoiceHealthStatus(
                    recommendation="Record some voice samples to establish your baseline.",
                    confidence=0
                )
            features = self._features_cache[-1]

        if self._baseline is None:
            current = len(self._features_cache)
            return VoiceHealthStatus(
                recommendation=f"Building baseline: {current}/{self.MIN_BASELINE_SAMPLES} recordings. "
                              f"Keep recording to establish your personal voice profile.",
                confidence=0
            )

        # Calculate deviations from baseline
        fatigue_score, fatigue_indicators = self._assess_fatigue(features)
        illness_score, illness_indicators = self._assess_illness(features)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            fatigue_score, illness_score, fatigue_indicators, illness_indicators
        )

        # Confidence based on baseline quality
        confidence = min(len(self._features_cache) / 20, 1.0)

        return VoiceHealthStatus(
            fatigue_score=fatigue_score,
            illness_score=illness_score,
            fatigue_indicators=fatigue_indicators,
            illness_indicators=illness_indicators,
            recommendation=recommendation,
            confidence=confidence
        )

    def _assess_fatigue(self, features: AcousticFeatures) -> Tuple[float, List[str]]:
        """
        Assess fatigue level from acoustic features.

        Fatigue typically shows:
        - Increased jitter and shimmer (voice instability)
        - Decreased HNR (more noise in voice)
        - Slower speech rate
        - More pauses
        """
        if self._baseline is None:
            return 0, []

        indicators = []
        scores = []

        # Check jitter increase
        if self._baseline.jitter_local > 0:
            jitter_change = (features.jitter_local - self._baseline.jitter_local) / self._baseline.jitter_local
            if jitter_change > self.FATIGUE_JITTER_INCREASE:
                indicators.append(f"Voice instability increased ({jitter_change*100:.0f}%)")
                scores.append(min(jitter_change / 0.5 * 100, 100))

        # Check shimmer increase
        if self._baseline.shimmer_local > 0:
            shimmer_change = (features.shimmer_local - self._baseline.shimmer_local) / self._baseline.shimmer_local
            if shimmer_change > self.FATIGUE_SHIMMER_INCREASE:
                indicators.append(f"Voice amplitude varies more ({shimmer_change*100:.0f}%)")
                scores.append(min(shimmer_change / 0.5 * 100, 100))

        # Check HNR decrease
        if self._baseline.hnr > 0:
            hnr_change = (self._baseline.hnr - features.hnr) / self._baseline.hnr
            if hnr_change > self.FATIGUE_HNR_DECREASE:
                indicators.append(f"Voice clarity reduced ({hnr_change*100:.0f}%)")
                scores.append(min(hnr_change / 0.3 * 100, 100))

        # Check speech rate decrease
        if self._baseline.speech_rate > 0:
            rate_change = (self._baseline.speech_rate - features.speech_rate) / self._baseline.speech_rate
            if rate_change > self.FATIGUE_SPEECH_RATE_DECREASE:
                indicators.append(f"Speaking slower ({rate_change*100:.0f}%)")
                scores.append(min(rate_change / 0.4 * 100, 100))

        # Check pause rate increase
        if self._baseline.pause_rate > 0 and features.pause_rate > 0:
            pause_change = (features.pause_rate - self._baseline.pause_rate) / self._baseline.pause_rate
            if pause_change > 0.3:  # 30% more pauses
                indicators.append(f"More pauses in speech ({pause_change*100:.0f}%)")
                scores.append(min(pause_change / 0.5 * 100, 100))

        fatigue_score = sum(scores) / len(scores) if scores else 0
        return round(fatigue_score, 1), indicators

    def _assess_illness(self, features: AcousticFeatures) -> Tuple[float, List[str]]:
        """
        Assess likelihood of illness from acoustic features.

        Cold/flu typically shows:
        - Changed pitch (often lower)
        - Decreased HNR (congestion adds noise)
        - Changed formants (nasality)
        """
        if self._baseline is None:
            return 0, []

        indicators = []
        scores = []

        # Check F0 change (either direction)
        if self._baseline.f0_mean > 0:
            f0_change = abs(features.f0_mean - self._baseline.f0_mean) / self._baseline.f0_mean
            if f0_change > self.ILLNESS_F0_CHANGE:
                direction = "lower" if features.f0_mean < self._baseline.f0_mean else "higher"
                indicators.append(f"Pitch is {direction} than usual ({f0_change*100:.0f}%)")
                scores.append(min(f0_change / 0.2 * 100, 100))

        # Check HNR decrease (significant for illness)
        if self._baseline.hnr > 0:
            hnr_change = (self._baseline.hnr - features.hnr) / self._baseline.hnr
            if hnr_change > self.ILLNESS_HNR_DECREASE:
                indicators.append(f"Voice sounds less clear ({hnr_change*100:.0f}%)")
                scores.append(min(hnr_change / 0.4 * 100, 100))

        # Check F1 change (nasality indicator)
        if self._baseline.f1_mean > 0:
            f1_change = abs(features.f1_mean - self._baseline.f1_mean) / self._baseline.f1_mean
            if f1_change > self.ILLNESS_FORMANT_CHANGE:
                indicators.append(f"Voice resonance changed ({f1_change*100:.0f}%)")
                scores.append(min(f1_change / 0.3 * 100, 100))

        # Check F2 change (another congestion indicator)
        if self._baseline.f2_mean > 0:
            f2_change = abs(features.f2_mean - self._baseline.f2_mean) / self._baseline.f2_mean
            if f2_change > self.ILLNESS_FORMANT_CHANGE:
                indicators.append("Vocal tract changes detected")
                scores.append(min(f2_change / 0.3 * 100, 100))

        illness_score = sum(scores) / len(scores) if scores else 0
        return round(illness_score, 1), indicators

    def _generate_recommendation(self, fatigue_score: float, illness_score: float,
                                  fatigue_indicators: List[str],
                                  illness_indicators: List[str]) -> str:
        """Generate actionable recommendation based on scores."""

        # High fatigue and illness
        if fatigue_score >= 60 and illness_score >= 60:
            return ("Your voice shows signs of both fatigue and possible illness. "
                   "Consider taking a break and resting. If symptoms persist, "
                   "consult a healthcare provider.")

        # High fatigue
        if fatigue_score >= 60:
            return ("Your voice shows signs of fatigue. Consider taking a break, "
                   "staying hydrated, and resting your voice for a bit.")

        if fatigue_score >= 40:
            return ("Mild fatigue detected in your voice. A short break might help.")

        # High illness
        if illness_score >= 60:
            return ("Your voice patterns suggest you may be coming down with something. "
                   "Rest and hydration are recommended. Monitor how you feel.")

        if illness_score >= 40:
            return ("Some changes in your voice could indicate early illness. "
                   "Take it easy and stay hydrated.")

        # Normal
        if fatigue_score < 20 and illness_score < 20:
            return "Your voice sounds healthy and well-rested!"

        return "Your voice shows minor variations - this is normal."

    def _update_baseline(self):
        """Update baseline from recent recordings."""
        if len(self._features_cache) < self.MIN_BASELINE_SAMPLES:
            return

        # Use all features to compute baseline
        features = self._features_cache
        n = len(features)

        self._baseline = AcousticFeatures(
            f0_mean=sum(f.f0_mean for f in features) / n,
            f0_std=sum(f.f0_std for f in features) / n,
            f0_min=sum(f.f0_min for f in features) / n,
            f0_max=sum(f.f0_max for f in features) / n,
            jitter_local=sum(f.jitter_local for f in features) / n,
            jitter_rap=sum(f.jitter_rap for f in features) / n,
            shimmer_local=sum(f.shimmer_local for f in features) / n,
            shimmer_apq3=sum(f.shimmer_apq3 for f in features) / n,
            hnr=sum(f.hnr for f in features) / n,
            f1_mean=sum(f.f1_mean for f in features) / n,
            f2_mean=sum(f.f2_mean for f in features) / n,
            f3_mean=sum(f.f3_mean for f in features) / n,
            duration=sum(f.duration for f in features) / n,
            voiced_fraction=sum(f.voiced_fraction for f in features) / n,
            speech_rate=sum(f.speech_rate for f in features) / n,
            pause_rate=sum(f.pause_rate for f in features) / n,
            timestamp=datetime.now().isoformat()
        )

        self._save_baseline()
        logger.info(f"Updated acoustic baseline from {n} samples")

    def _save_features(self):
        """Save features to JSON file."""
        try:
            self.ACOUSTIC_FILE.parent.mkdir(exist_ok=True)
            data = []
            for f in self._features_cache[-100:]:  # Keep last 100
                data.append({
                    'f0_mean': f.f0_mean,
                    'f0_std': f.f0_std,
                    'f0_min': f.f0_min,
                    'f0_max': f.f0_max,
                    'jitter_local': f.jitter_local,
                    'jitter_rap': f.jitter_rap,
                    'shimmer_local': f.shimmer_local,
                    'shimmer_apq3': f.shimmer_apq3,
                    'hnr': f.hnr,
                    'f1_mean': f.f1_mean,
                    'f2_mean': f.f2_mean,
                    'f3_mean': f.f3_mean,
                    'duration': f.duration,
                    'voiced_fraction': f.voiced_fraction,
                    'speech_rate': f.speech_rate,
                    'pause_rate': f.pause_rate,
                    'timestamp': f.timestamp,
                    'audio_path': f.audio_path
                })
            with open(self.ACOUSTIC_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save acoustic features: {e}")

    def _load_features(self):
        """Load features from JSON file."""
        try:
            if self.ACOUSTIC_FILE.exists():
                with open(self.ACOUSTIC_FILE, 'r') as f:
                    data = json.load(f)
                for item in data:
                    self._features_cache.append(AcousticFeatures(
                        f0_mean=item.get('f0_mean', 0),
                        f0_std=item.get('f0_std', 0),
                        f0_min=item.get('f0_min', 0),
                        f0_max=item.get('f0_max', 0),
                        jitter_local=item.get('jitter_local', 0),
                        jitter_rap=item.get('jitter_rap', 0),
                        shimmer_local=item.get('shimmer_local', 0),
                        shimmer_apq3=item.get('shimmer_apq3', 0),
                        hnr=item.get('hnr', 0),
                        f1_mean=item.get('f1_mean', 0),
                        f2_mean=item.get('f2_mean', 0),
                        f3_mean=item.get('f3_mean', 0),
                        duration=item.get('duration', 0),
                        voiced_fraction=item.get('voiced_fraction', 0),
                        speech_rate=item.get('speech_rate', 0),
                        pause_rate=item.get('pause_rate', 0),
                        timestamp=item.get('timestamp', ''),
                        audio_path=item.get('audio_path', '')
                    ))
                logger.info(f"Loaded {len(self._features_cache)} acoustic feature sets")
        except Exception as e:
            logger.warning(f"Failed to load acoustic features: {e}")

    def _save_baseline(self):
        """Save baseline to JSON file."""
        if self._baseline is None:
            return
        try:
            self.ACOUSTIC_BASELINE_FILE.parent.mkdir(exist_ok=True)
            data = {
                'f0_mean': self._baseline.f0_mean,
                'f0_std': self._baseline.f0_std,
                'jitter_local': self._baseline.jitter_local,
                'shimmer_local': self._baseline.shimmer_local,
                'hnr': self._baseline.hnr,
                'f1_mean': self._baseline.f1_mean,
                'f2_mean': self._baseline.f2_mean,
                'f3_mean': self._baseline.f3_mean,
                'speech_rate': self._baseline.speech_rate,
                'pause_rate': self._baseline.pause_rate,
                'timestamp': self._baseline.timestamp,
                'n_samples': len(self._features_cache)
            }
            with open(self.ACOUSTIC_BASELINE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save baseline: {e}")

    def _load_baseline(self):
        """Load baseline from JSON file."""
        try:
            if self.ACOUSTIC_BASELINE_FILE.exists():
                with open(self.ACOUSTIC_BASELINE_FILE, 'r') as f:
                    data = json.load(f)
                self._baseline = AcousticFeatures(
                    f0_mean=data.get('f0_mean', 0),
                    f0_std=data.get('f0_std', 0),
                    jitter_local=data.get('jitter_local', 0),
                    shimmer_local=data.get('shimmer_local', 0),
                    hnr=data.get('hnr', 0),
                    f1_mean=data.get('f1_mean', 0),
                    f2_mean=data.get('f2_mean', 0),
                    f3_mean=data.get('f3_mean', 0),
                    speech_rate=data.get('speech_rate', 0),
                    pause_rate=data.get('pause_rate', 0),
                    timestamp=data.get('timestamp', '')
                )
                logger.info("Loaded acoustic baseline")
        except Exception as e:
            logger.warning(f"Failed to load baseline: {e}")

    def get_feature_count(self) -> int:
        """Get number of stored feature sets."""
        return len(self._features_cache)

    def get_baseline_progress(self) -> Tuple[int, int]:
        """Get progress toward baseline."""
        return (len(self._features_cache), self.MIN_BASELINE_SAMPLES)

    def get_latest_features(self) -> Optional[AcousticFeatures]:
        """Get most recent features."""
        return self._features_cache[-1] if self._features_cache else None

    def get_detailed_report(self) -> Dict:
        """Get detailed report of current voice status."""
        features = self.get_latest_features()
        status = self.get_health_status(features)

        report = {
            'has_baseline': self._baseline is not None,
            'baseline_samples': len(self._features_cache),
            'fatigue_score': status.fatigue_score,
            'illness_score': status.illness_score,
            'fatigue_indicators': status.fatigue_indicators,
            'illness_indicators': status.illness_indicators,
            'recommendation': status.recommendation,
            'confidence': status.confidence
        }

        if features:
            report['current_metrics'] = {
                'pitch_hz': round(features.f0_mean, 1),
                'pitch_variability': round(features.f0_std, 1),
                'jitter_percent': round(features.jitter_local, 2),
                'shimmer_percent': round(features.shimmer_local, 2),
                'hnr_db': round(features.hnr, 1),
                'speech_rate': round(features.speech_rate, 1),
                'pause_rate': round(features.pause_rate, 2)
            }

        if self._baseline:
            report['baseline_metrics'] = {
                'pitch_hz': round(self._baseline.f0_mean, 1),
                'jitter_percent': round(self._baseline.jitter_local, 2),
                'shimmer_percent': round(self._baseline.shimmer_local, 2),
                'hnr_db': round(self._baseline.hnr, 1),
                'speech_rate': round(self._baseline.speech_rate, 1)
            }

        return report
