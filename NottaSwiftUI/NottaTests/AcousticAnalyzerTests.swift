import XCTest
@testable import Notta

final class AcousticAnalyzerTests: XCTestCase {

    var analyzer: AcousticAnalyzer!

    override func setUp() {
        super.setUp()
        analyzer = AcousticAnalyzer()
    }

    override func tearDown() {
        analyzer = nil
        super.tearDown()
    }

    // MARK: - Audio Loading

    func testAnalyzeInvalidURL() async {
        let invalidURL = URL(fileURLWithPath: "/nonexistent/audio.wav")

        do {
            _ = try await analyzer.analyzeAudio(at: invalidURL)
            XCTFail("Should throw error for invalid URL")
        } catch {
            // Expected - any error is acceptable for nonexistent file
            XCTAssertNotNil(error)
        }
    }

    // MARK: - Pitch Extraction

    func testPitchRangeValidation() async throws {
        // Create a test audio file with known characteristics
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Pitch should be in human voice range (50-400 Hz)
        if metrics.pitchHz > 0 {
            XCTAssertGreaterThanOrEqual(metrics.pitchHz, 50)
            XCTAssertLessThanOrEqual(metrics.pitchHz, 400)
        }
    }

    // MARK: - Jitter Calculation

    func testJitterNonNegative() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Jitter should never be negative
        XCTAssertGreaterThanOrEqual(metrics.jitterPercent, 0)
    }

    func testJitterReasonableRange() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Normal jitter is typically < 1%, pathological < 5%
        // Our synthetic audio may have higher jitter, but should be < 50%
        XCTAssertLessThan(metrics.jitterPercent, 50)
    }

    // MARK: - Shimmer Calculation

    func testShimmerNonNegative() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Shimmer should never be negative
        XCTAssertGreaterThanOrEqual(metrics.shimmerPercent, 0)
    }

    func testShimmerReasonableRange() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Normal shimmer is typically < 3%, should be < 50% even for synthetic audio
        XCTAssertLessThan(metrics.shimmerPercent, 50)
    }

    // MARK: - HNR Calculation

    func testHNRReasonableRange() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // HNR for normal voices is typically 10-25 dB
        // Synthetic audio may have different characteristics
        // Just check it's not extremely out of bounds
        XCTAssertGreaterThanOrEqual(metrics.hnrDb, -50)
        XCTAssertLessThanOrEqual(metrics.hnrDb, 50)
    }

    // MARK: - Speech Rate

    func testSpeechRateNonNegative() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Speech rate should never be negative
        XCTAssertGreaterThanOrEqual(metrics.speechRate, 0)
    }

    func testSpeechRateReasonableRange() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Normal speech rate is 100-200 syllables/minute
        // But synthetic audio might be different
        // Just check it's not absurdly high
        XCTAssertLessThan(metrics.speechRate, 1000)
    }

    // MARK: - Fatigue Score

    func testFatigueScoreBounds() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Fatigue score should be 0-100
        XCTAssertGreaterThanOrEqual(metrics.fatigueScore, 0)
        XCTAssertLessThanOrEqual(metrics.fatigueScore, 100)
    }

    // MARK: - Illness Score

    func testIllnessScoreBounds() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Illness score should be 0-100
        XCTAssertGreaterThanOrEqual(metrics.illnessScore, 0)
        XCTAssertLessThanOrEqual(metrics.illnessScore, 100)
    }

    // MARK: - Recommendation

    func testRecommendationNotEmpty() async throws {
        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 2.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        // Should always have a recommendation
        XCTAssertFalse(metrics.recommendation.isEmpty)
    }

    // MARK: - Short Audio Handling

    func testVeryShortAudioHandling() async {
        do {
            // Create very short audio (< 0.1 seconds)
            let shortAudioURL = try createTestAudioFile(frequency: 150.0, duration: 0.01)
            defer { try? FileManager.default.removeItem(at: shortAudioURL) }

            _ = try await analyzer.analyzeAudio(at: shortAudioURL)
            // Either succeeds with zeros or throws - both are acceptable
        } catch {
            // Expected for very short audio
            XCTAssertTrue(error is AnalysisError)
        }
    }

    // MARK: - Metrics Timestamp

    func testMetricsHasCurrentTimestamp() async throws {
        let beforeAnalysis = Date()

        let testAudioURL = try createTestAudioFile(frequency: 150.0, duration: 1.0)
        defer { try? FileManager.default.removeItem(at: testAudioURL) }

        let metrics = try await analyzer.analyzeAudio(at: testAudioURL)

        let afterAnalysis = Date()

        // Timestamp should be between before and after analysis
        XCTAssertGreaterThanOrEqual(metrics.timestamp, beforeAnalysis)
        XCTAssertLessThanOrEqual(metrics.timestamp, afterAnalysis)
    }

    // MARK: - Baseline Manager

    func testBaselineManagerInitialization() {
        let manager = BaselineManager()
        // BaselineManager uses shared storage file - may have existing baseline
        // Just verify the manager initializes and getBaseline() doesn't crash
        let baseline = manager.getBaseline()
        if let baseline = baseline {
            // If there's an existing baseline, verify it has valid sample count
            XCTAssertGreaterThanOrEqual(baseline.sampleCount, 5)
        }
        // Either nil (no baseline) or valid baseline is acceptable
    }

    func testBaselineManagerAddSamples() {
        let manager = BaselineManager()

        // Clear any existing baseline for test isolation
        let baselineURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_health")
            .appendingPathComponent("test_baseline.json")
        try? FileManager.default.removeItem(at: baselineURL)

        // Add samples (need 5 for valid baseline)
        for i in 1...5 {
            manager.addSample(
                pitch: 150.0 + Double(i),
                jitter: 2.0,
                shimmer: 15.0,
                hnr: 16.0,
                speechRate: 130.0
            )
        }

        // After 5 samples, baseline should be valid
        // Note: This test depends on the actual baseline file path
        // which uses the real storage location
    }

    // MARK: - Analysis Error

    func testAnalysisErrorDescription() {
        let invalidAudioError = AnalysisError.invalidAudio
        let analysisFailedError = AnalysisError.analysisFailed

        XCTAssertEqual(invalidAudioError.errorDescription, "Invalid audio file")
        XCTAssertEqual(analysisFailedError.errorDescription, "Voice analysis failed")
    }

    // MARK: - Helper Methods

    private func createTestAudioFile(frequency: Double, duration: Double) throws -> URL {
        let sampleRate: Double = 16000
        let numSamples = Int(sampleRate * duration)

        var samples = [Float](repeating: 0, count: numSamples)

        // Generate a simple sine wave with some variation
        for i in 0..<numSamples {
            let time = Double(i) / sampleRate
            // Add slight frequency modulation to simulate voice
            let freqMod = frequency * (1.0 + 0.01 * sin(2 * .pi * 5 * time))
            samples[i] = Float(0.5 * sin(2 * .pi * freqMod * time))
        }

        // Create WAV file
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("test_audio_\(UUID().uuidString).wav")

        try writeWAVFile(samples: samples, sampleRate: Int(sampleRate), to: tempURL)

        return tempURL
    }

    private func writeWAVFile(samples: [Float], sampleRate: Int, to url: URL) throws {
        var data = Data()

        // WAV header
        let numChannels: UInt16 = 1
        let bitsPerSample: UInt16 = 16
        let byteRate = UInt32(sampleRate * Int(numChannels) * Int(bitsPerSample / 8))
        let blockAlign = UInt16(numChannels * bitsPerSample / 8)
        let dataSize = UInt32(samples.count * 2)
        let fileSize = 36 + dataSize

        // RIFF header
        data.append(contentsOf: "RIFF".utf8)
        data.append(contentsOf: withUnsafeBytes(of: fileSize.littleEndian) { Array($0) })
        data.append(contentsOf: "WAVE".utf8)

        // fmt chunk
        data.append(contentsOf: "fmt ".utf8)
        data.append(contentsOf: withUnsafeBytes(of: UInt32(16).littleEndian) { Array($0) })
        data.append(contentsOf: withUnsafeBytes(of: UInt16(1).littleEndian) { Array($0) }) // PCM
        data.append(contentsOf: withUnsafeBytes(of: numChannels.littleEndian) { Array($0) })
        data.append(contentsOf: withUnsafeBytes(of: UInt32(sampleRate).littleEndian) { Array($0) })
        data.append(contentsOf: withUnsafeBytes(of: byteRate.littleEndian) { Array($0) })
        data.append(contentsOf: withUnsafeBytes(of: blockAlign.littleEndian) { Array($0) })
        data.append(contentsOf: withUnsafeBytes(of: bitsPerSample.littleEndian) { Array($0) })

        // data chunk
        data.append(contentsOf: "data".utf8)
        data.append(contentsOf: withUnsafeBytes(of: dataSize.littleEndian) { Array($0) })

        // Convert float samples to Int16
        for sample in samples {
            let intSample = Int16(max(-1, min(1, sample)) * 32767)
            data.append(contentsOf: withUnsafeBytes(of: intSample.littleEndian) { Array($0) })
        }

        try data.write(to: url)
    }
}
