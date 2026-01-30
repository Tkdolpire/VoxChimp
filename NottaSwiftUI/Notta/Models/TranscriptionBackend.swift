import Foundation

/// Represents the available transcription backends
enum TranscriptionBackend: String, CaseIterable, Identifiable {
    case appleSpeech = "apple_speech"
    case whisperKit = "whisper_kit"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .appleSpeech: return "Apple Speech Recognition"
        case .whisperKit: return "OpenAI Whisper (Local)"
        }
    }

    var description: String {
        switch self {
        case .appleSpeech:
            return "Fast, private, no download required"
        case .whisperKit:
            return "Higher accuracy, requires model download"
        }
    }

    var iconName: String {
        switch self {
        case .appleSpeech: return "apple.logo"
        case .whisperKit: return "waveform.badge.mic"
        }
    }
}
