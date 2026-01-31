import Foundation

struct Transcription: Identifiable, Codable, Equatable, Hashable {
    let id: UUID
    let text: String
    let timestamp: Date
    let wordCount: Int
    let charCount: Int
    var audioFilePath: String?
    var category: String?
    var tags: [String]

    /// Original text before translation (nil if not translated)
    var originalText: String?
    /// Language code the text was translated to (nil if not translated)
    var translatedTo: String?

    /// Whether this transcription was translated
    var wasTranslated: Bool {
        originalText != nil && translatedTo != nil
    }

    init(
        id: UUID = UUID(),
        text: String,
        timestamp: Date = Date(),
        audioFilePath: String? = nil,
        category: String? = nil,
        tags: [String] = [],
        originalText: String? = nil,
        translatedTo: String? = nil
    ) {
        self.id = id
        self.text = text
        self.timestamp = timestamp
        self.wordCount = text.split(separator: " ").count
        self.charCount = text.count
        self.audioFilePath = audioFilePath
        self.category = category
        self.tags = tags
        self.originalText = originalText
        self.translatedTo = translatedTo
    }

    var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: timestamp)
    }

    var relativeDate: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: timestamp, relativeTo: Date())
    }

    var preview: String {
        if text.count <= 100 {
            return text
        }
        return String(text.prefix(100)) + "..."
    }
}

// MARK: - Sample Data for Previews

extension Transcription {
    static let sampleData: [Transcription] = [
        Transcription(
            text: "Patient presents with mild fatigue and occasional headaches. Recommend blood work and follow-up in two weeks.",
            timestamp: Date().addingTimeInterval(-3600),
            category: "Medical Note"
        ),
        Transcription(
            text: "Meeting notes: Discussed Q4 targets. Action items include reviewing budget and preparing presentation.",
            timestamp: Date().addingTimeInterval(-86400),
            category: "Meeting"
        ),
        Transcription(
            text: "Remember to call the pharmacy about prescription renewal.",
            timestamp: Date().addingTimeInterval(-172800),
            tags: ["reminder", "health"]
        )
    ]
}
