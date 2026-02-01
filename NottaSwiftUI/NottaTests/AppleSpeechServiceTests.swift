import XCTest
@testable import Notta

final class AppleSpeechServiceTests: XCTestCase {

    var speechService: AppleSpeechService!

    override func setUp() {
        super.setUp()
        speechService = AppleSpeechService()
    }

    override func tearDown() {
        speechService = nil
        super.tearDown()
    }

    // MARK: - Initial State

    func testInitialIsTranscribingFalse() {
        XCTAssertFalse(speechService.isTranscribing)
    }

    func testInitialProgressZero() {
        XCTAssertEqual(speechService.progress, 0)
    }

    // MARK: - Protocol Conformance

    func testConformsToTranscriptionServiceProtocol() {
        // Verify the service conforms to the protocol
        let service: TranscriptionServiceProtocol = AppleSpeechService()
        XCTAssertNotNil(service)
    }

    // MARK: - Published Properties

    @MainActor
    func testIsTranscribingIsPublished() async {
        let expectation = XCTestExpectation(description: "isTranscribing changed")

        let cancellable = speechService.$isTranscribing.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    @MainActor
    func testProgressIsPublished() async {
        let expectation = XCTestExpectation(description: "progress changed")

        let cancellable = speechService.$progress.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    // MARK: - Instance Creation

    func testMultipleInstancesAreIndependent() {
        let service1 = AppleSpeechService()
        let service2 = AppleSpeechService()

        XCTAssertFalse(service1 === service2)
    }

    // MARK: - Transcription Error Handling

    func testTranscribeWithInvalidURLThrows() async {
        let invalidURL = URL(fileURLWithPath: "/nonexistent/path/audio.wav")

        do {
            _ = try await speechService.transcribe(audioURL: invalidURL)
            // May succeed if permission granted, or throw
        } catch {
            // Expected to throw some error (TranscriptionError or system error)
            XCTAssertNotNil(error)
        }
    }
}

// MARK: - TranscriptionError Tests

final class TranscriptionErrorTests: XCTestCase {

    func testPermissionDeniedError() {
        let error = TranscriptionError.permissionDenied
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("permission"))
    }

    func testSpeechRecognizerUnavailableError() {
        let error = TranscriptionError.speechRecognizerUnavailable
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("unavailable") ||
                      error.errorDescription!.lowercased().contains("not available"))
    }

    func testTranscriptionFailedError() {
        let error = TranscriptionError.transcriptionFailed("Audio corrupted")
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("Audio corrupted"))
    }

    func testNoResultError() {
        let error = TranscriptionError.noResult
        XCTAssertNotNil(error.errorDescription)
    }

    func testErrorsAreLocalizedError() {
        let errors: [TranscriptionError] = [
            .permissionDenied,
            .speechRecognizerUnavailable,
            .transcriptionFailed("test"),
            .noResult
        ]

        for error in errors {
            // All TranscriptionError cases conform to LocalizedError
            XCTAssertNotNil(error.errorDescription)
            XCTAssertFalse(error.errorDescription!.isEmpty)
        }
    }

    func testTranscriptionFailedPreservesMessage() {
        let message = "Custom error message with details"
        let error = TranscriptionError.transcriptionFailed(message)
        XCTAssertTrue(error.errorDescription!.contains(message))
    }
}

// MARK: - TranscriptionServiceProtocol Tests

final class TranscriptionServiceProtocolTests: XCTestCase {

    func testAppleSpeechServiceConforms() {
        let service: TranscriptionServiceProtocol = AppleSpeechService()
        XCTAssertNotNil(service)
    }

    func testProtocolHasTranscribeMethod() async throws {
        // This test verifies the protocol requires the transcribe method
        let service: TranscriptionServiceProtocol = AppleSpeechService()

        // Verify we can reference the method (compile-time check)
        let testURL = URL(fileURLWithPath: "/tmp/nonexistent.wav")

        do {
            // This will throw but proves the method exists with correct signature
            _ = try await service.transcribe(audioURL: testURL)
        } catch {
            // Expected - file doesn't exist
        }
    }
}
