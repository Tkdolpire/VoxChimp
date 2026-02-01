import XCTest
@testable import Notta

@MainActor
final class WhisperKitServiceTests: XCTestCase {

    var whisperService: WhisperKitService!

    override func setUp() async throws {
        try await super.setUp()
        whisperService = WhisperKitService()
    }

    override func tearDown() async throws {
        whisperService.unloadModel()
        whisperService = nil
        try await super.tearDown()
    }

    // MARK: - Initial State

    func testInitialIsTranscribingFalse() {
        XCTAssertFalse(whisperService.isTranscribing)
    }

    func testInitialProgressZero() {
        XCTAssertEqual(whisperService.progress, 0)
    }

    func testInitialIsModelLoadedFalse() {
        XCTAssertFalse(whisperService.isModelLoaded)
    }

    func testInitialLoadingErrorNil() {
        XCTAssertNil(whisperService.loadingError)
    }

    // MARK: - Model State

    func testIsLoadedReturnsFalseWhenNoModel() {
        XCTAssertFalse(whisperService.isLoaded(.tiny))
        XCTAssertFalse(whisperService.isLoaded(.base))
        XCTAssertFalse(whisperService.isLoaded(.small))
        XCTAssertFalse(whisperService.isLoaded(.medium))
        XCTAssertFalse(whisperService.isLoaded(.large))
    }

    func testUnloadModelClearsState() {
        whisperService.unloadModel()

        XCTAssertFalse(whisperService.isModelLoaded)
        XCTAssertFalse(whisperService.isLoaded(.small))
    }

    func testUnloadModelIdempotent() {
        whisperService.unloadModel()
        whisperService.unloadModel()
        whisperService.unloadModel()

        // Should not crash
        XCTAssertFalse(whisperService.isModelLoaded)
    }

    // MARK: - Transcription Without Model

    func testTranscribeThrowsWhenModelNotLoaded() async {
        let testURL = URL(fileURLWithPath: "/tmp/test.wav")

        do {
            _ = try await whisperService.transcribe(audioURL: testURL)
            XCTFail("Should throw when model not loaded")
        } catch {
            if case WhisperKitError.modelNotLoaded = error {
                // Expected
            } else {
                XCTFail("Should throw modelNotLoaded error, got: \(error)")
            }
        }
    }

    // MARK: - Published Properties

    func testIsTranscribingIsPublished() {
        // Verify we can observe changes
        let expectation = XCTestExpectation(description: "isTranscribing changed")

        let cancellable = whisperService.$isTranscribing.sink { _ in
            expectation.fulfill()
        }

        // Initial value triggers sink
        wait(for: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    func testProgressIsPublished() {
        let expectation = XCTestExpectation(description: "progress changed")

        let cancellable = whisperService.$progress.sink { _ in
            expectation.fulfill()
        }

        wait(for: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    func testIsModelLoadedIsPublished() {
        let expectation = XCTestExpectation(description: "isModelLoaded changed")

        let cancellable = whisperService.$isModelLoaded.sink { _ in
            expectation.fulfill()
        }

        wait(for: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    func testLoadingErrorIsPublished() {
        let expectation = XCTestExpectation(description: "loadingError changed")

        let cancellable = whisperService.$loadingError.sink { _ in
            expectation.fulfill()
        }

        wait(for: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    // MARK: - New Instance Creation

    func testMultipleInstancesAreIndependent() {
        let service1 = WhisperKitService()
        let service2 = WhisperKitService()

        XCTAssertFalse(service1 === service2)
        XCTAssertFalse(service1.isModelLoaded)
        XCTAssertFalse(service2.isModelLoaded)
    }
}

// MARK: - WhisperKitError Tests

final class WhisperKitErrorTests: XCTestCase {

    func testModelNotLoadedError() {
        let error = WhisperKitError.modelNotLoaded
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("not loaded"))
    }

    func testModelNotDownloadedError() {
        let error = WhisperKitError.modelNotDownloaded
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("not downloaded"))
    }

    func testDownloadFailedError() {
        let error = WhisperKitError.downloadFailed("Connection timeout")
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("Connection timeout"))
    }

    func testTranscriptionFailedError() {
        let error = WhisperKitError.transcriptionFailed("Invalid audio format")
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("Invalid audio format"))
    }

    func testCancelledError() {
        let error = WhisperKitError.cancelled
        XCTAssertNotNil(error.errorDescription)
    }

    func testErrorsAreLocalizedError() {
        let errors: [WhisperKitError] = [
            .modelNotLoaded,
            .modelNotDownloaded,
            .downloadFailed("test"),
            .transcriptionFailed("test"),
            .cancelled
        ]

        for error in errors {
            XCTAssertTrue(error is LocalizedError)
        }
    }
}
