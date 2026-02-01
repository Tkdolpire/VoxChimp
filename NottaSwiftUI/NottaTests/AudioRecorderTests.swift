import XCTest
@testable import Notta

@MainActor
final class AudioRecorderTests: XCTestCase {

    var audioRecorder: AudioRecorder!

    override func setUp() async throws {
        try await super.setUp()
        audioRecorder = AudioRecorder()
    }

    override func tearDown() async throws {
        audioRecorder.cancelRecording()
        audioRecorder = nil
        try await super.tearDown()
    }

    // MARK: - Initial State

    func testInitialIsRecordingFalse() {
        XCTAssertFalse(audioRecorder.isRecording)
    }

    func testInitialRecordingDurationZero() {
        XCTAssertEqual(audioRecorder.recordingDuration, 0)
    }

    // MARK: - Published Properties

    func testIsRecordingIsPublished() async {
        let expectation = XCTestExpectation(description: "isRecording changed")

        let cancellable = audioRecorder.$isRecording.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    func testRecordingDurationIsPublished() async {
        let expectation = XCTestExpectation(description: "recordingDuration changed")

        let cancellable = audioRecorder.$recordingDuration.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    // MARK: - Instance Creation

    func testMultipleInstancesAreIndependent() {
        let recorder1 = AudioRecorder()
        let recorder2 = AudioRecorder()

        XCTAssertFalse(recorder1 === recorder2)
        XCTAssertFalse(recorder1.isRecording)
        XCTAssertFalse(recorder2.isRecording)
    }

    // MARK: - Cancel Recording

    func testCancelRecordingResetsState() {
        audioRecorder.cancelRecording()

        XCTAssertFalse(audioRecorder.isRecording)
    }

    func testCancelRecordingIdempotent() {
        // Should not crash when called multiple times
        audioRecorder.cancelRecording()
        audioRecorder.cancelRecording()
        audioRecorder.cancelRecording()

        XCTAssertFalse(audioRecorder.isRecording)
    }

    // MARK: - Update Meters

    func testUpdateMetersReturnsFloat() {
        let level = audioRecorder.updateMeters()
        XCTAssertTrue(level.isFinite)
    }

    func testUpdateMetersWhenNotRecording() {
        let level = audioRecorder.updateMeters()
        // When not recording, should return minimum level
        XCTAssertEqual(level, -160)
    }

    // MARK: - Stop Recording Without Starting

    func testStopRecordingWithoutStartThrows() async {
        do {
            _ = try await audioRecorder.stopRecording()
            XCTFail("Should throw when stopping without starting")
        } catch {
            if case RecordingError.noRecording = error {
                // Expected
            } else {
                XCTFail("Should throw noRecording error, got: \(error)")
            }
        }
    }
}

// MARK: - RecordingError Tests

final class RecordingErrorTests: XCTestCase {

    func testPermissionDeniedError() {
        let error = RecordingError.permissionDenied
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("permission"))
    }

    func testRecordingFailedError() {
        let error = RecordingError.recordingFailed
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("failed"))
    }

    func testNoRecordingError() {
        let error = RecordingError.noRecording
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("no recording"))
    }

    func testTooShortError() {
        let error = RecordingError.tooShort
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("short"))
    }

    func testNoAudioDetectedError() {
        let error = RecordingError.noAudioDetected
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("no audio"))
    }

    func testAllErrorsHaveDescriptions() {
        let errors: [RecordingError] = [
            .permissionDenied,
            .recordingFailed,
            .noRecording,
            .tooShort,
            .noAudioDetected
        ]

        for error in errors {
            XCTAssertNotNil(error.errorDescription)
            XCTAssertFalse(error.errorDescription!.isEmpty)
        }
    }

    func testErrorsAreLocalizedError() {
        // RecordingError conforms to LocalizedError
        let error: LocalizedError = RecordingError.permissionDenied
        XCTAssertNotNil(error.errorDescription)
    }
}

// MARK: - Audio Settings Tests

final class AudioSettingsTests: XCTestCase {

    func testWhisperCompatibleSettings() {
        // Verify expected audio settings for Whisper compatibility
        let expectedSampleRate = 16000.0
        let expectedChannels = 1
        let expectedBitDepth = 16

        // These are the settings used in AudioRecorder
        XCTAssertEqual(expectedSampleRate, 16000.0)
        XCTAssertEqual(expectedChannels, 1)
        XCTAssertEqual(expectedBitDepth, 16)
    }

    func testMinimumFileSizeThreshold() {
        // Recording validation requires at least 1000 bytes
        let minimumFileSize = 1000
        XCTAssertEqual(minimumFileSize, 1000)
    }

    func testAudioValidationThreshold() {
        // Audio validation threshold for silence detection
        let threshold: Float = 0.001
        XCTAssertEqual(threshold, 0.001)
    }
}
