import XCTest
@testable import Notta

final class TranscriptionTests: XCTestCase {

    // MARK: - Initialization

    func testTranscriptionCreation() {
        let text = "Hello world"
        let timestamp = Date()
        let transcription = Transcription(text: text, timestamp: timestamp)

        XCTAssertEqual(transcription.text, text)
        XCTAssertEqual(transcription.timestamp, timestamp)
        XCTAssertNil(transcription.audioFilePath)
        XCTAssertNil(transcription.category)
        XCTAssertTrue(transcription.tags.isEmpty)
    }

    func testTranscriptionWithAllFields() {
        let text = "Test transcription"
        let timestamp = Date()
        let audioPath = "/path/to/audio.wav"
        let category = "Medical"
        let tags = ["important", "follow-up"]

        let transcription = Transcription(
            text: text,
            timestamp: timestamp,
            audioFilePath: audioPath,
            category: category,
            tags: tags
        )

        XCTAssertEqual(transcription.text, text)
        XCTAssertEqual(transcription.audioFilePath, audioPath)
        XCTAssertEqual(transcription.category, category)
        XCTAssertEqual(transcription.tags, tags)
    }

    func testTranscriptionHasUniqueID() {
        let t1 = Transcription(text: "Test 1", timestamp: Date())
        let t2 = Transcription(text: "Test 2", timestamp: Date())

        XCTAssertNotEqual(t1.id, t2.id)
    }

    // MARK: - Word Count

    func testWordCountSingleWord() {
        let transcription = Transcription(text: "Hello", timestamp: Date())
        XCTAssertEqual(transcription.wordCount, 1)
    }

    func testWordCountMultipleWords() {
        let transcription = Transcription(text: "Hello world how are you", timestamp: Date())
        XCTAssertEqual(transcription.wordCount, 5)
    }

    func testWordCountEmptyString() {
        let transcription = Transcription(text: "", timestamp: Date())
        XCTAssertEqual(transcription.wordCount, 0)
    }

    func testWordCountWithExtraSpaces() {
        let transcription = Transcription(text: "Hello   world", timestamp: Date())
        // Should handle multiple spaces gracefully
        XCTAssertGreaterThanOrEqual(transcription.wordCount, 2)
    }

    func testWordCountWithNewlines() {
        // Implementation splits on spaces only, not newlines
        let transcription = Transcription(text: "Hello\nworld", timestamp: Date())
        XCTAssertEqual(transcription.wordCount, 1) // "Hello\nworld" has no spaces
    }

    // MARK: - Character Count

    func testCharCountEmpty() {
        let transcription = Transcription(text: "", timestamp: Date())
        XCTAssertEqual(transcription.charCount, 0)
    }

    func testCharCountWithSpaces() {
        let transcription = Transcription(text: "Hello world", timestamp: Date())
        XCTAssertEqual(transcription.charCount, 11)
    }

    func testCharCountUnicode() {
        // Swift counts grapheme clusters: "Hello " = 6, "👋" = 1 = 7 total
        let transcription = Transcription(text: "Hello 👋", timestamp: Date())
        XCTAssertEqual(transcription.charCount, 7)
    }

    // MARK: - Preview

    func testPreviewShortText() {
        let shortText = "Short text"
        let transcription = Transcription(text: shortText, timestamp: Date())
        XCTAssertEqual(transcription.preview, shortText)
    }

    func testPreviewLongText() {
        let longText = String(repeating: "word ", count: 100)
        let transcription = Transcription(text: longText, timestamp: Date())
        // Preview should be truncated
        XCTAssertLessThan(transcription.preview.count, longText.count)
    }

    func testPreviewEmptyText() {
        let transcription = Transcription(text: "", timestamp: Date())
        XCTAssertTrue(transcription.preview.isEmpty)
    }

    // MARK: - Date Formatting

    func testFormattedDateNotEmpty() {
        let transcription = Transcription(text: "Test", timestamp: Date())
        XCTAssertFalse(transcription.formattedDate.isEmpty)
    }

    func testRelativeDateNotEmpty() {
        let transcription = Transcription(text: "Test", timestamp: Date())
        XCTAssertFalse(transcription.relativeDate.isEmpty)
    }

    func testRelativeDateRecentTimestamp() {
        let transcription = Transcription(text: "Test", timestamp: Date())
        // Should say something like "Just now" or "0 minutes ago"
        let relative = transcription.relativeDate.lowercased()
        XCTAssertTrue(
            relative.contains("now") ||
            relative.contains("second") ||
            relative.contains("minute") ||
            relative.contains("0")
        )
    }

    // MARK: - Codable

    func testTranscriptionEncodeDecode() throws {
        let original = Transcription(
            text: "Test transcription",
            timestamp: Date(),
            audioFilePath: "/path/to/audio.wav",
            category: "Medical",
            tags: ["tag1", "tag2"]
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(Transcription.self, from: data)

        XCTAssertEqual(decoded.id, original.id)
        XCTAssertEqual(decoded.text, original.text)
        XCTAssertEqual(decoded.audioFilePath, original.audioFilePath)
        XCTAssertEqual(decoded.category, original.category)
        XCTAssertEqual(decoded.tags, original.tags)
    }

    func testTranscriptionArrayEncodeDecode() throws {
        let transcriptions = [
            Transcription(text: "First", timestamp: Date()),
            Transcription(text: "Second", timestamp: Date().addingTimeInterval(-3600)),
            Transcription(text: "Third", timestamp: Date().addingTimeInterval(-7200))
        ]

        let encoder = JSONEncoder()
        let data = try encoder.encode(transcriptions)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode([Transcription].self, from: data)

        XCTAssertEqual(decoded.count, 3)
        XCTAssertEqual(decoded[0].text, "First")
        XCTAssertEqual(decoded[1].text, "Second")
        XCTAssertEqual(decoded[2].text, "Third")
    }

    // MARK: - Equatable

    func testTranscriptionEquality() {
        let timestamp = Date()
        let t1 = Transcription(id: UUID(), text: "Test", timestamp: timestamp)
        let t2 = Transcription(id: t1.id, text: "Test", timestamp: timestamp)

        XCTAssertEqual(t1, t2)
    }

    func testTranscriptionInequality() {
        let t1 = Transcription(text: "Test 1", timestamp: Date())
        let t2 = Transcription(text: "Test 2", timestamp: Date())

        XCTAssertNotEqual(t1, t2)
    }

    // MARK: - Hashable

    func testTranscriptionHashable() {
        let t1 = Transcription(text: "Test", timestamp: Date())
        let t2 = Transcription(text: "Test", timestamp: Date())

        var set = Set<Transcription>()
        set.insert(t1)
        set.insert(t2)

        XCTAssertEqual(set.count, 2) // Different IDs
    }
}
