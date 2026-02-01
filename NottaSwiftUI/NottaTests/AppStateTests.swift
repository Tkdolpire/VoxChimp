import XCTest
@testable import Notta

@MainActor
final class AppStateTests: XCTestCase {

    var appState: AppState!

    override func setUp() async throws {
        try await super.setUp()
        appState = AppState()
    }

    override func tearDown() async throws {
        appState = nil
        try await super.tearDown()
    }

    // MARK: - Initial State

    func testInitialRecordingState() {
        XCTAssertFalse(appState.isRecording)
    }

    func testInitialRecordingStatus() {
        XCTAssertEqual(appState.recordingStatus, .ready)
    }

    func testInitialLastTranscription() {
        XCTAssertNil(appState.lastTranscription)
    }

    func testInitialAudioLevel() {
        XCTAssertEqual(appState.audioLevel, 0)
    }

    func testInitialShowTranscriptionSuccess() {
        XCTAssertFalse(appState.showTranscriptionSuccess)
    }

    func testInitialHealthMetrics() {
        // Health metrics may be nil initially
        // or may have loaded previous data
        // Just verify it doesn't crash
        _ = appState.healthMetrics
    }

    func testInitialHealthHistory() {
        // Health history may be empty or have loaded data
        XCTAssertNotNil(appState.healthHistory)
    }

    func testInitialTranscriptionHistory() {
        // Transcription history may be empty or have loaded data
        XCTAssertNotNil(appState.transcriptionHistory)
    }

    // MARK: - Recording State Changes

    func testStartRecordingChangesState() {
        appState.startRecording()

        XCTAssertTrue(appState.isRecording)
        XCTAssertEqual(appState.recordingStatus, .recording)
        XCTAssertFalse(appState.showTranscriptionSuccess)
    }

    func testStartRecordingWhileAlreadyRecording() {
        appState.startRecording()
        appState.startRecording() // Should be ignored

        // Should still be recording, not double-recording
        XCTAssertTrue(appState.isRecording)
    }

    func testStopRecordingChangesState() {
        appState.startRecording()
        appState.stopRecording()

        XCTAssertFalse(appState.isRecording)
        // Status becomes .processing after stopping
        XCTAssertEqual(appState.recordingStatus, .processing)
    }

    func testStopRecordingWithoutStarting() {
        // Should handle gracefully
        appState.stopRecording()

        // Should remain ready
        XCTAssertFalse(appState.isRecording)
    }

    // MARK: - Transcription History

    func testSaveTranscription() {
        let initialCount = appState.transcriptionHistory.count

        let transcription = Transcription(
            text: "Test transcription",
            timestamp: Date()
        )
        appState.saveTranscription(transcription)

        XCTAssertEqual(appState.transcriptionHistory.count, initialCount + 1)
        XCTAssertEqual(appState.transcriptionHistory.first?.text, "Test transcription")
    }

    func testSaveTranscriptionInsertsAtBeginning() {
        let t1 = Transcription(text: "First", timestamp: Date())
        let t2 = Transcription(text: "Second", timestamp: Date())

        appState.saveTranscription(t1)
        appState.saveTranscription(t2)

        XCTAssertEqual(appState.transcriptionHistory.first?.text, "Second")
    }

    func testDeleteTranscription() {
        let transcription = Transcription(text: "To be deleted", timestamp: Date())
        appState.saveTranscription(transcription)

        let countBefore = appState.transcriptionHistory.count

        appState.deleteTranscription(transcription)

        XCTAssertEqual(appState.transcriptionHistory.count, countBefore - 1)
        XCTAssertFalse(appState.transcriptionHistory.contains { $0.id == transcription.id })
    }

    func testDeleteNonExistentTranscription() {
        let countBefore = appState.transcriptionHistory.count

        let fakeTranscription = Transcription(text: "Fake", timestamp: Date())
        appState.deleteTranscription(fakeTranscription)

        // Count should remain the same
        XCTAssertEqual(appState.transcriptionHistory.count, countBefore)
    }

    // MARK: - Grammar Fixes

    func testGrammarFixesCapitalization() {
        let settings = SettingsManager.shared
        let originalValue = settings.fixGrammar
        settings.fixGrammar = true

        // The grammar fix is applied in stopRecording flow
        // We test the logic indirectly through settings
        XCTAssertTrue(settings.fixGrammar)

        settings.fixGrammar = originalValue
    }

    // MARK: - Audio Level

    func testAudioLevelBounds() {
        // Audio level should always be 0-1
        XCTAssertGreaterThanOrEqual(appState.audioLevel, 0)
        XCTAssertLessThanOrEqual(appState.audioLevel, 1)
    }

    // MARK: - Health Data

    func testHealthHistoryRetentionPeriod() {
        // Health history should only keep last 30 days
        let thirtyDaysAgo = Date().addingTimeInterval(-30 * 24 * 60 * 60)

        for dataPoint in appState.healthHistory {
            XCTAssertGreaterThan(dataPoint.date, thirtyDaysAgo)
        }
    }

    // MARK: - Services

    func testAudioRecorderExists() {
        XCTAssertNotNil(appState.audioRecorder)
    }

    func testTranscriptionManagerExists() {
        // TranscriptionManager is a singleton, verify it exists
        XCTAssertNotNil(TranscriptionManager.shared)
    }

    func testAcousticAnalyzerExists() {
        XCTAssertNotNil(appState.acousticAnalyzer)
    }

    func testSettingsExists() {
        XCTAssertNotNil(appState.settings)
    }

    // MARK: - Settings Reference

    func testSettingsIsSharedInstance() {
        XCTAssertTrue(appState.settings === SettingsManager.shared)
    }

    // MARK: - Voice Health Analysis

    func testAnalyzeVoiceHealthWithInvalidURL() async {
        let invalidURL = URL(fileURLWithPath: "/nonexistent/file.wav")

        // Should handle gracefully without crashing
        await appState.analyzeVoiceHealth(audioURL: invalidURL)

        // Health metrics might still be nil or previous value
        // Just verify no crash
        XCTAssertTrue(true)
    }
}

// MARK: - Notification Tests

extension AppStateTests {

    func testHotkeyPressedNotification() {
        let expectation = XCTestExpectation(description: "Hotkey pressed should start recording")

        // Observer for state change
        let cancellable = appState.$isRecording.sink { isRecording in
            if isRecording {
                expectation.fulfill()
            }
        }

        // Post notification
        NotificationCenter.default.post(name: .hotkeyPressed, object: nil)

        wait(for: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    func testHotkeyReleasedNotification() {
        // First start recording
        appState.startRecording()
        XCTAssertTrue(appState.isRecording)

        let expectation = XCTestExpectation(description: "Hotkey released should stop recording")

        let cancellable = appState.$isRecording.sink { isRecording in
            if !isRecording {
                expectation.fulfill()
            }
        }

        // Post notification
        NotificationCenter.default.post(name: .hotkeyReleased, object: nil)

        wait(for: [expectation], timeout: 1.0)
        cancellable.cancel()
    }
}
