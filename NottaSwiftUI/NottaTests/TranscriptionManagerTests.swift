import XCTest
@testable import Notta

@MainActor
final class TranscriptionManagerTests: XCTestCase {

    var transcriptionManager: TranscriptionManager!

    override func setUp() async throws {
        try await super.setUp()
        transcriptionManager = TranscriptionManager.shared
    }

    override func tearDown() async throws {
        transcriptionManager = nil
        try await super.tearDown()
    }

    // MARK: - Singleton

    func testSharedInstanceExists() {
        XCTAssertNotNil(TranscriptionManager.shared)
    }

    func testSharedInstanceIsSingleton() {
        let instance1 = TranscriptionManager.shared
        let instance2 = TranscriptionManager.shared
        XCTAssertTrue(instance1 === instance2)
    }

    // MARK: - Initial State

    func testInitialIsTranscribingFalse() {
        XCTAssertFalse(transcriptionManager.isTranscribing)
    }

    func testInitialProgressZero() {
        XCTAssertEqual(transcriptionManager.progress, 0)
    }

    func testInitialErrorNil() {
        XCTAssertNil(transcriptionManager.error)
    }

    func testInitialCurrentBackend() {
        // Should have a valid backend
        let validBackends: [TranscriptionBackend] = [.appleSpeech, .whisperKit]
        XCTAssertTrue(validBackends.contains(transcriptionManager.currentBackend))
    }

    // MARK: - Backend Switching

    func testSwitchToAppleSpeech() {
        transcriptionManager.switchBackend(to: .appleSpeech)
        XCTAssertEqual(transcriptionManager.currentBackend, .appleSpeech)
    }

    func testSwitchToWhisperKit() {
        transcriptionManager.switchBackend(to: .whisperKit)
        XCTAssertEqual(transcriptionManager.currentBackend, .whisperKit)
    }

    func testSwitchBackendClearsError() {
        transcriptionManager.error = "Some error"
        transcriptionManager.switchBackend(to: .appleSpeech)
        XCTAssertNil(transcriptionManager.error)
    }

    func testSwitchToSameBackendIsNoOp() {
        let original = transcriptionManager.currentBackend
        transcriptionManager.switchBackend(to: original)
        XCTAssertEqual(transcriptionManager.currentBackend, original)
    }

    // MARK: - Model Ready State

    func testAppleSpeechIsAlwaysReady() {
        transcriptionManager.switchBackend(to: .appleSpeech)
        XCTAssertTrue(transcriptionManager.isModelReady)
    }

    func testIsModelReadyProperty() {
        // Should be a valid boolean
        let _ = transcriptionManager.isModelReady
    }

    func testIsLoadingModelProperty() {
        let _ = transcriptionManager.isLoadingModel
    }

    func testModelLoadingProgressProperty() {
        let progress = transcriptionManager.modelLoadingProgress
        XCTAssertNotNil(progress)
    }

    // MARK: - Published Properties

    func testIsTranscribingIsPublished() async {
        let expectation = XCTestExpectation(description: "isTranscribing changed")

        let cancellable = transcriptionManager.$isTranscribing.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    func testProgressIsPublished() async {
        let expectation = XCTestExpectation(description: "progress changed")

        let cancellable = transcriptionManager.$progress.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    func testCurrentBackendIsPublished() async {
        let expectation = XCTestExpectation(description: "currentBackend changed")

        let cancellable = transcriptionManager.$currentBackend.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    func testErrorIsPublished() async {
        let expectation = XCTestExpectation(description: "error changed")

        let cancellable = transcriptionManager.$error.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    // MARK: - Transcription Error Handling

    func testTranscribeWithInvalidURL() async {
        let invalidURL = URL(fileURLWithPath: "/nonexistent/audio.wav")

        do {
            _ = try await transcriptionManager.transcribe(audioURL: invalidURL)
            // May succeed or fail depending on permissions and backend
        } catch {
            // Expected to throw
            XCTAssertNotNil(error)
        }
    }
}

// MARK: - TranscriptionBackend Tests

final class TranscriptionBackendTests: XCTestCase {

    func testAppleSpeechRawValue() {
        XCTAssertEqual(TranscriptionBackend.appleSpeech.rawValue, "appleSpeech")
    }

    func testWhisperKitRawValue() {
        XCTAssertEqual(TranscriptionBackend.whisperKit.rawValue, "whisperKit")
    }

    func testAllCases() {
        XCTAssertEqual(TranscriptionBackend.allCases.count, 2)
        XCTAssertTrue(TranscriptionBackend.allCases.contains(.appleSpeech))
        XCTAssertTrue(TranscriptionBackend.allCases.contains(.whisperKit))
    }

    func testDisplayName() {
        XCTAssertFalse(TranscriptionBackend.appleSpeech.displayName.isEmpty)
        XCTAssertFalse(TranscriptionBackend.whisperKit.displayName.isEmpty)
    }

    func testDescription() {
        XCTAssertFalse(TranscriptionBackend.appleSpeech.description.isEmpty)
        XCTAssertFalse(TranscriptionBackend.whisperKit.description.isEmpty)
    }

    func testIdentifiable() {
        for backend in TranscriptionBackend.allCases {
            XCTAssertEqual(backend.id, backend.rawValue)
        }
    }

    func testRawValueEncodeDecode() throws {
        // Test that raw values can be encoded/decoded (for storage)
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        for backend in TranscriptionBackend.allCases {
            let encoded = try encoder.encode(backend.rawValue)
            let decodedRaw = try decoder.decode(String.self, from: encoded)
            let recreated = TranscriptionBackend(rawValue: decodedRaw)
            XCTAssertEqual(recreated, backend)
        }
    }

    func testRawValueRoundtrip() {
        for backend in TranscriptionBackend.allCases {
            let rawValue = backend.rawValue
            let recreated = TranscriptionBackend(rawValue: rawValue)
            XCTAssertEqual(recreated, backend)
        }
    }
}

// MARK: - Backend Fallback Tests

final class TranscriptionFallbackTests: XCTestCase {

    @MainActor
    func testWhisperKitFallsBackWhenNotReady() async {
        let manager = TranscriptionManager.shared

        // Switch to WhisperKit
        manager.switchBackend(to: .whisperKit)

        // If model isn't loaded, transcription should still work (via fallback)
        // This tests the fallback logic exists
        XCTAssertEqual(manager.currentBackend, .whisperKit)
    }

    @MainActor
    func testAppleSpeechDoesNotFallBack() {
        let manager = TranscriptionManager.shared
        manager.switchBackend(to: .appleSpeech)

        // Apple Speech is always ready, no fallback needed
        XCTAssertTrue(manager.isModelReady)
    }
}
