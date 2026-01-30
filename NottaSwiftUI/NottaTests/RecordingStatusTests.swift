import XCTest
@testable import Notta

final class RecordingStatusTests: XCTestCase {

    // MARK: - Display Text

    func testReadyDisplayText() {
        let status = RecordingStatus.ready
        XCTAssertEqual(status.displayText, "Ready")
    }

    func testRecordingDisplayText() {
        let status = RecordingStatus.recording
        XCTAssertEqual(status.displayText, "Recording...")
    }

    func testProcessingDisplayText() {
        let status = RecordingStatus.processing
        XCTAssertEqual(status.displayText, "Processing...")
    }

    func testSuccessDisplayText() {
        let status = RecordingStatus.success
        XCTAssertEqual(status.displayText, "Done!")
    }

    func testErrorDisplayText() {
        let status = RecordingStatus.error("Permission denied")
        XCTAssertEqual(status.displayText, "Error: Permission denied")
    }

    func testErrorDisplayTextEmpty() {
        let status = RecordingStatus.error("")
        XCTAssertEqual(status.displayText, "Error: ")
    }

    // MARK: - Color

    func testReadyColor() {
        let status = RecordingStatus.ready
        XCTAssertEqual(status.color, .primary)
    }

    func testRecordingColor() {
        let status = RecordingStatus.recording
        XCTAssertEqual(status.color, .red)
    }

    func testProcessingColor() {
        let status = RecordingStatus.processing
        XCTAssertEqual(status.color, .secondary)
    }

    func testSuccessColor() {
        let status = RecordingStatus.success
        XCTAssertEqual(status.color, .green)
    }

    func testErrorColor() {
        let status = RecordingStatus.error("Any error")
        XCTAssertEqual(status.color, .orange)
    }

    // MARK: - Equatable

    func testReadyEquality() {
        XCTAssertEqual(RecordingStatus.ready, RecordingStatus.ready)
    }

    func testRecordingEquality() {
        XCTAssertEqual(RecordingStatus.recording, RecordingStatus.recording)
    }

    func testProcessingEquality() {
        XCTAssertEqual(RecordingStatus.processing, RecordingStatus.processing)
    }

    func testSuccessEquality() {
        XCTAssertEqual(RecordingStatus.success, RecordingStatus.success)
    }

    func testErrorEquality() {
        XCTAssertEqual(
            RecordingStatus.error("Same message"),
            RecordingStatus.error("Same message")
        )
    }

    func testErrorInequality() {
        XCTAssertNotEqual(
            RecordingStatus.error("Message 1"),
            RecordingStatus.error("Message 2")
        )
    }

    func testDifferentStatusesNotEqual() {
        XCTAssertNotEqual(RecordingStatus.ready, RecordingStatus.recording)
        XCTAssertNotEqual(RecordingStatus.recording, RecordingStatus.processing)
        XCTAssertNotEqual(RecordingStatus.processing, RecordingStatus.success)
        XCTAssertNotEqual(RecordingStatus.success, RecordingStatus.error("Error"))
    }

    // MARK: - State Transitions

    func testTypicalStateTransition() {
        var status = RecordingStatus.ready

        // User starts recording
        status = .recording
        XCTAssertEqual(status, .recording)

        // User stops recording, processing begins
        status = .processing
        XCTAssertEqual(status, .processing)

        // Processing completes successfully
        status = .success
        XCTAssertEqual(status, .success)

        // Reset to ready
        status = .ready
        XCTAssertEqual(status, .ready)
    }

    func testErrorStateTransition() {
        var status = RecordingStatus.ready

        // User starts recording
        status = .recording
        XCTAssertEqual(status, .recording)

        // Error occurs
        status = .error("Microphone access denied")
        XCTAssertEqual(status.displayText, "Error: Microphone access denied")

        // Reset to ready after error
        status = .ready
        XCTAssertEqual(status, .ready)
    }

    // MARK: - Error Messages

    func testCommonErrorMessages() {
        let errorMessages = [
            "Microphone access denied",
            "Recording failed",
            "Transcription failed",
            "No audio detected",
            "Network error",
            "Audio too short"
        ]

        for message in errorMessages {
            let status = RecordingStatus.error(message)
            XCTAssertTrue(status.displayText.contains(message))
        }
    }

    func testLongErrorMessage() {
        let longMessage = String(repeating: "Error details. ", count: 50)
        let status = RecordingStatus.error(longMessage)

        // Should handle long messages without crashing
        XCTAssertTrue(status.displayText.contains("Error:"))
    }

    func testSpecialCharactersInErrorMessage() {
        let specialMessage = "Error: File not found at path /tmp/audio.wav (errno: 2)"
        let status = RecordingStatus.error(specialMessage)

        XCTAssertEqual(status.displayText, "Error: \(specialMessage)")
    }

    func testUnicodeInErrorMessage() {
        let unicodeMessage = "错误: 录音失败"
        let status = RecordingStatus.error(unicodeMessage)

        XCTAssertTrue(status.displayText.contains(unicodeMessage))
    }
}
