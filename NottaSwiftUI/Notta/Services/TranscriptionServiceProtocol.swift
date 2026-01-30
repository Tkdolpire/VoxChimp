import Foundation

/// Protocol defining the interface for transcription services
protocol TranscriptionServiceProtocol: AnyObject {
    /// Whether transcription is currently in progress
    var isTranscribing: Bool { get }

    /// Current progress of transcription (0.0 to 1.0)
    var progress: Double { get }

    /// Transcribe audio from the given URL
    /// - Parameter audioURL: URL to the audio file
    /// - Returns: Transcribed text
    func transcribe(audioURL: URL) async throws -> String
}

/// Common transcription errors (used by Apple Speech)
enum TranscriptionError: LocalizedError {
    case permissionDenied
    case speechRecognizerUnavailable
    case transcriptionFailed(String)
    case noResult

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Speech recognition permission denied. Please enable in System Settings > Privacy & Security > Speech Recognition."
        case .speechRecognizerUnavailable:
            return "Speech recognition not available."
        case .transcriptionFailed(let message):
            return "Transcription failed: \(message)"
        case .noResult:
            return "No transcription result received."
        }
    }
}

/// Errors specific to WhisperKit transcription
enum WhisperKitError: LocalizedError {
    case modelNotLoaded
    case modelNotDownloaded
    case downloadFailed(String)
    case transcriptionFailed(String)
    case cancelled

    var errorDescription: String? {
        switch self {
        case .modelNotLoaded:
            return "Whisper model is not loaded. Please wait for the model to load."
        case .modelNotDownloaded:
            return "Whisper model is not downloaded. Please download the model in Settings."
        case .downloadFailed(let message):
            return "Model download failed: \(message)"
        case .transcriptionFailed(let message):
            return "Transcription failed: \(message)"
        case .cancelled:
            return "Operation was cancelled."
        }
    }
}
