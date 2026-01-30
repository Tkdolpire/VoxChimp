import Foundation
import Accelerate
import AVFoundation

/// Analyzes voice health metrics from audio recordings
/// Calculates pitch (F0), jitter, shimmer, HNR, and speech rate
class AcousticAnalyzer {
    private let sampleRate: Double = 16000
    private let frameSize: Int = 512
    private let hopSize: Int = 256

    private var baselineManager = BaselineManager()

    // MARK: - Analysis

    func analyzeAudio(at url: URL) async throws -> VoiceHealthMetrics {
        let audioData = try loadAudio(from: url)

        // Safety check: ensure we have enough audio data to analyze
        guard audioData.count >= frameSize * 2 else {
            throw AnalysisError.invalidAudio
        }

        // Extract features with error handling
        let pitch = extractPitch(from: audioData)
        let jitter = calculateJitter(pitchValues: pitch.values)
        let shimmer = calculateShimmer(from: audioData)
        let hnr = calculateHNR(from: audioData)
        let speechRate = estimateSpeechRate(from: audioData)

        // Get baseline for comparison
        let baseline = baselineManager.getBaseline()

        // Calculate health scores
        let (fatigueScore, fatigueIndicators) = calculateFatigueScore(
            pitch: pitch.mean,
            jitter: jitter,
            speechRate: speechRate,
            baseline: baseline
        )

        let (illnessScore, illnessIndicators) = calculateIllnessScore(
            pitch: pitch.mean,
            shimmer: shimmer,
            hnr: hnr,
            baseline: baseline
        )

        // Update baseline if we have enough samples
        baselineManager.addSample(
            pitch: pitch.mean,
            jitter: jitter,
            shimmer: shimmer,
            hnr: hnr,
            speechRate: speechRate
        )

        // Generate recommendation
        let recommendation = generateRecommendation(
            fatigueScore: fatigueScore,
            illnessScore: illnessScore,
            indicators: fatigueIndicators + illnessIndicators
        )

        return VoiceHealthMetrics(
            timestamp: Date(),
            pitchHz: pitch.mean,
            jitterPercent: jitter,
            shimmerPercent: shimmer,
            hnrDb: hnr,
            speechRate: speechRate,
            fatigueScore: fatigueScore,
            illnessScore: illnessScore,
            recommendation: recommendation,
            indicators: fatigueIndicators + illnessIndicators
        )
    }

    // MARK: - Audio Loading

    private func loadAudio(from url: URL) throws -> [Float] {
        let file = try AVAudioFile(forReading: url)
        let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1)!

        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: UInt32(file.length)) else {
            throw AnalysisError.invalidAudio
        }

        try file.read(into: buffer)

        guard let channelData = buffer.floatChannelData?[0] else {
            throw AnalysisError.invalidAudio
        }

        return Array(UnsafeBufferPointer(start: channelData, count: Int(buffer.frameLength)))
    }

    // MARK: - Pitch Extraction (Autocorrelation)

    private func extractPitch(from samples: [Float]) -> (mean: Double, values: [Double]) {
        var pitchValues: [Double] = []

        // Safety check: need enough samples
        guard samples.count > frameSize else {
            return (0, [])
        }

        let minLag = Int(sampleRate / 400) // Max F0 = 400 Hz
        let maxLag = Int(sampleRate / 50)  // Min F0 = 50 Hz

        // Pre-compute window once
        var window = [Float](repeating: 0, count: frameSize)
        vDSP_hann_window(&window, vDSP_Length(frameSize), Int32(vDSP_HANN_NORM))

        for frameStart in stride(from: 0, to: samples.count - frameSize, by: hopSize) {
            let frame = Array(samples[frameStart..<frameStart + frameSize])

            // Apply Hanning window
            var windowedFrame = [Float](repeating: 0, count: frameSize)
            vDSP_vmul(frame, 1, window, 1, &windowedFrame, 1, vDSP_Length(frameSize))

            // Autocorrelation using safe method
            let autocorr = safeAutocorrelation(windowedFrame, maxLag: maxLag)

            // Safety check for search range
            guard maxLag <= autocorr.count, minLag < maxLag else { continue }

            // Find peak in valid lag range
            let searchRange = Array(autocorr[minLag..<min(maxLag, autocorr.count)])
            if let maxIdx = searchRange.indices.max(by: { searchRange[$0] < searchRange[$1] }) {
                let lag = minLag + maxIdx
                let f0 = sampleRate / Double(lag)

                // Filter unrealistic values
                if f0 > 50 && f0 < 400 {
                    pitchValues.append(f0)
                }
            }
        }

        let mean = pitchValues.isEmpty ? 0 : pitchValues.reduce(0, +) / Double(pitchValues.count)
        return (mean, pitchValues)
    }

    /// Safe autocorrelation computation that avoids buffer overflows
    /// Uses vDSP_dotpr for each lag which is safer than vDSP_conv
    private func safeAutocorrelation(_ signal: [Float], maxLag: Int) -> [Float] {
        let n = signal.count
        guard n > 0 else { return [] }

        let effectiveMaxLag = min(maxLag, n - 1)
        var result = [Float](repeating: 0, count: effectiveMaxLag + 1)

        for lag in 0...effectiveMaxLag {
            let overlapLength = n - lag
            guard overlapLength > 0 else { break }

            var dotProduct: Float = 0
            signal.withUnsafeBufferPointer { signalPtr in
                vDSP_dotpr(signalPtr.baseAddress!, 1,
                          signalPtr.baseAddress!.advanced(by: lag), 1,
                          &dotProduct,
                          vDSP_Length(overlapLength))
            }
            result[lag] = dotProduct
        }

        return result
    }

    // MARK: - Jitter (Pitch Variability)

    private func calculateJitter(pitchValues: [Double]) -> Double {
        guard pitchValues.count > 1 else { return 0 }

        // Calculate period from pitch
        let periods = pitchValues.map { 1.0 / $0 }

        // Mean period
        let meanPeriod = periods.reduce(0, +) / Double(periods.count)

        // Average absolute difference between consecutive periods
        var totalDiff = 0.0
        for i in 1..<periods.count {
            totalDiff += abs(periods[i] - periods[i-1])
        }
        let avgDiff = totalDiff / Double(periods.count - 1)

        // Jitter as percentage
        return (avgDiff / meanPeriod) * 100
    }

    // MARK: - Shimmer (Amplitude Variability)

    private func calculateShimmer(from samples: [Float]) -> Double {
        // Safety check
        guard samples.count > frameSize else { return 0 }

        var amplitudes: [Float] = []

        for frameStart in stride(from: 0, to: samples.count - frameSize, by: hopSize) {
            let endIndex = frameStart + frameSize
            guard endIndex <= samples.count else { break }

            let frame = Array(samples[frameStart..<endIndex])

            // RMS amplitude
            var sumSquares: Float = 0
            vDSP_svesq(frame, 1, &sumSquares, vDSP_Length(frameSize))
            let rms = sqrt(sumSquares / Float(frameSize))

            if rms > 0.001 { // Filter silence
                amplitudes.append(rms)
            }
        }

        guard amplitudes.count > 1 else { return 0 }

        let meanAmp = amplitudes.reduce(0, +) / Float(amplitudes.count)
        guard meanAmp > 0 else { return 0 }

        // Average absolute difference between consecutive amplitudes
        var totalDiff: Float = 0
        for i in 1..<amplitudes.count {
            totalDiff += abs(amplitudes[i] - amplitudes[i-1])
        }
        let avgDiff = totalDiff / Float(amplitudes.count - 1)

        return Double((avgDiff / meanAmp) * 100)
    }

    // MARK: - HNR (Harmonics-to-Noise Ratio)

    private func calculateHNR(from samples: [Float]) -> Double {
        // Safety checks
        guard samples.count > frameSize else {
            return 0
        }

        let minLag = Int(sampleRate / 400) // Max F0 = 400 Hz
        let maxLag = Int(sampleRate / 50)  // Min F0 = 50 Hz

        guard maxLag > minLag, minLag > 0 else {
            return 0
        }

        // For HNR, we analyze a limited segment to avoid memory issues with large files
        // Use up to 2 seconds of audio from the middle of the recording
        let maxSamples = Int(sampleRate * 2) // 2 seconds
        let segmentSamples: [Float]

        if samples.count > maxSamples {
            let start = (samples.count - maxSamples) / 2
            segmentSamples = Array(samples[start..<(start + maxSamples)])
        } else {
            segmentSamples = samples
        }

        // Use safe autocorrelation method
        let autocorr = safeAutocorrelation(segmentSamples, maxLag: maxLag)

        // Safety check for valid results
        guard autocorr.count > maxLag,
              let r0 = autocorr.first, r0 > 0,
              minLag < autocorr.count else {
            return 0
        }

        // Find max in pitch range
        let searchEndIndex = min(maxLag, autocorr.count)
        guard minLag < searchEndIndex else {
            return 0
        }

        let searchRange = Array(autocorr[minLag..<searchEndIndex])
        guard let maxVal = searchRange.max() else {
            return 0
        }

        // HNR in dB
        let ratio = maxVal / r0
        if ratio > 0 && ratio < 1 {
            return 10 * log10(Double(ratio) / (1 - Double(ratio)))
        }

        return 0
    }

    // MARK: - Speech Rate

    private func estimateSpeechRate(from samples: [Float]) -> Double {
        // Safety check
        guard samples.count > frameSize else { return 0 }

        // Estimate syllables per minute using energy envelope

        // Calculate energy envelope
        var energyEnvelope: [Float] = []
        for frameStart in stride(from: 0, to: samples.count - frameSize, by: hopSize) {
            let endIndex = frameStart + frameSize
            guard endIndex <= samples.count else { break }

            let frame = Array(samples[frameStart..<endIndex])
            var energy: Float = 0
            vDSP_svesq(frame, 1, &energy, vDSP_Length(frameSize))
            energyEnvelope.append(energy)
        }

        guard !energyEnvelope.isEmpty else { return 0 }

        // Smooth envelope
        let smoothedEnvelope = smoothArray(energyEnvelope, windowSize: 5)

        // Find peaks (syllable nuclei)
        guard let maxEnergy = smoothedEnvelope.max(), maxEnergy > 0 else { return 0 }
        let threshold = maxEnergy * 0.3
        var peakCount = 0
        var inPeak = false

        for energy in smoothedEnvelope {
            if energy > threshold && !inPeak {
                peakCount += 1
                inPeak = true
            } else if energy < threshold {
                inPeak = false
            }
        }

        // Convert to syllables per minute
        let durationSeconds = Double(samples.count) / sampleRate
        guard durationSeconds > 0 else { return 0 }
        let syllablesPerMinute = (Double(peakCount) / durationSeconds) * 60

        return syllablesPerMinute
    }

    private func smoothArray(_ array: [Float], windowSize: Int) -> [Float] {
        guard array.count > windowSize else { return array }

        var result = [Float](repeating: 0, count: array.count)
        for i in 0..<array.count {
            let start = max(0, i - windowSize/2)
            let end = min(array.count, i + windowSize/2 + 1)
            let window = array[start..<end]
            result[i] = window.reduce(0, +) / Float(window.count)
        }
        return result
    }

    // MARK: - Health Scoring

    private func calculateFatigueScore(
        pitch: Double,
        jitter: Double,
        speechRate: Double,
        baseline: BaselineMetrics?
    ) -> (Int, [HealthIndicator]) {
        var score = 0
        var indicators: [HealthIndicator] = []

        guard let baseline = baseline else {
            return (0, [HealthIndicator(name: "Baseline", status: .stable, description: "Building baseline data")])
        }

        // Lower pitch indicates fatigue
        if baseline.pitchHz > 0 {
            let pitchChange = (pitch - baseline.pitchHz) / baseline.pitchHz * 100
            if pitchChange < -10 {
                score += 30
                indicators.append(HealthIndicator(
                    name: "Pitch",
                    status: .monitor,
                    description: "Lower than usual",
                    changePercent: pitchChange
                ))
            } else if pitchChange < -5 {
                score += 15
                indicators.append(HealthIndicator(
                    name: "Pitch",
                    status: .stable,
                    description: "Slightly lower",
                    changePercent: pitchChange
                ))
            }
        }

        // Higher jitter indicates fatigue
        if baseline.jitterPercent > 0 {
            let jitterChange = (jitter - baseline.jitterPercent) / baseline.jitterPercent * 100
            if jitterChange > 30 {
                score += 25
                indicators.append(HealthIndicator(
                    name: "Voice Stability",
                    status: .monitor,
                    description: "More variable than usual",
                    changePercent: jitterChange
                ))
            }
        }

        // Slower speech rate indicates fatigue
        if baseline.speechRate > 0 {
            let rateChange = (speechRate - baseline.speechRate) / baseline.speechRate * 100
            if rateChange < -15 {
                score += 25
                indicators.append(HealthIndicator(
                    name: "Speech Rate",
                    status: .monitor,
                    description: "Slower than usual",
                    changePercent: rateChange
                ))
            }
        }

        return (min(100, score), indicators)
    }

    private func calculateIllnessScore(
        pitch: Double,
        shimmer: Double,
        hnr: Double,
        baseline: BaselineMetrics?
    ) -> (Int, [HealthIndicator]) {
        var score = 0
        var indicators: [HealthIndicator] = []

        guard let baseline = baseline else {
            return (0, [])
        }

        // Lower HNR (more noise) indicates illness
        if baseline.hnrDb > 0 {
            let hnrChange = (hnr - baseline.hnrDb) / baseline.hnrDb * 100
            if hnrChange < -20 {
                score += 35
                indicators.append(HealthIndicator(
                    name: "Voice Clarity",
                    status: .attention,
                    description: "Reduced clarity detected",
                    changePercent: hnrChange
                ))
            } else if hnrChange < -10 {
                score += 20
                indicators.append(HealthIndicator(
                    name: "Voice Clarity",
                    status: .monitor,
                    description: "Slightly reduced",
                    changePercent: hnrChange
                ))
            }
        }

        // Higher shimmer indicates illness
        if baseline.shimmerPercent > 0 {
            let shimmerChange = (shimmer - baseline.shimmerPercent) / baseline.shimmerPercent * 100
            if shimmerChange > 40 {
                score += 30
                indicators.append(HealthIndicator(
                    name: "Voice Amplitude",
                    status: .attention,
                    description: "Unstable amplitude",
                    changePercent: shimmerChange
                ))
            }
        }

        // Significant pitch drop can indicate illness
        if baseline.pitchHz > 0 {
            let pitchChange = (pitch - baseline.pitchHz) / baseline.pitchHz * 100
            if pitchChange < -15 {
                score += 20
            }
        }

        return (min(100, score), indicators)
    }

    private func generateRecommendation(fatigueScore: Int, illnessScore: Int, indicators: [HealthIndicator]) -> String {
        if fatigueScore < 20 && illnessScore < 20 {
            return "Your voice sounds healthy. Keep up the good work!"
        }

        if illnessScore >= 50 {
            return "Some changes in your voice could indicate early illness. Take it easy and stay hydrated."
        }

        if fatigueScore >= 50 {
            return "Your voice shows signs of fatigue. Consider taking a break and resting your voice."
        }

        if fatigueScore >= 30 || illnessScore >= 30 {
            return "Minor changes detected in your voice. Stay hydrated and monitor how you feel."
        }

        return "Voice metrics are within normal range."
    }
}

// MARK: - Baseline Manager

class BaselineManager {
    private let storageURL: URL

    init() {
        storageURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_health")
            .appendingPathComponent("baseline.json")
    }

    func getBaseline() -> BaselineMetrics? {
        guard let baseline = getRawBaseline(), baseline.isValid else {
            return nil
        }
        return baseline
    }

    /// Returns baseline data regardless of validity (for accumulating samples)
    private func getRawBaseline() -> BaselineMetrics? {
        guard let data = try? Data(contentsOf: storageURL),
              let baseline = try? JSONDecoder().decode(BaselineMetrics.self, from: data) else {
            return nil
        }
        return baseline
    }

    func addSample(pitch: Double, jitter: Double, shimmer: Double, hnr: Double, speechRate: Double) {
        let baseline = getRawBaseline() ?? BaselineMetrics(
            pitchHz: 0,
            jitterPercent: 0,
            shimmerPercent: 0,
            hnrDb: 0,
            speechRate: 0,
            sampleCount: 0,
            lastUpdated: Date()
        )

        // Running average
        let n = Double(baseline.sampleCount)
        let newBaseline = BaselineMetrics(
            pitchHz: (baseline.pitchHz * n + pitch) / (n + 1),
            jitterPercent: (baseline.jitterPercent * n + jitter) / (n + 1),
            shimmerPercent: (baseline.shimmerPercent * n + shimmer) / (n + 1),
            hnrDb: (baseline.hnrDb * n + hnr) / (n + 1),
            speechRate: (baseline.speechRate * n + speechRate) / (n + 1),
            sampleCount: baseline.sampleCount + 1,
            lastUpdated: Date()
        )

        // Save
        try? FileManager.default.createDirectory(
            at: storageURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )

        if let data = try? JSONEncoder().encode(newBaseline) {
            try? data.write(to: storageURL)
        }
    }
}

// MARK: - Errors

enum AnalysisError: LocalizedError {
    case invalidAudio
    case analysisFailed

    var errorDescription: String? {
        switch self {
        case .invalidAudio:
            return "Invalid audio file"
        case .analysisFailed:
            return "Voice analysis failed"
        }
    }
}
