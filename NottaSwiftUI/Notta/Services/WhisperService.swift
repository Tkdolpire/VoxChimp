import Foundation
import Speech
import AVFoundation

/// Service for transcribing audio
/// Uses Apple's Speech framework as the primary method
class WhisperService: ObservableObject {
    @Published var isTranscribing = false
    @Published var progress: Double = 0

    private let speechRecognizer: SFSpeechRecognizer?

    init() {
        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    }

    // MARK: - Transcription

    func transcribe(audioURL: URL) async throws -> String {
        print("Starting transcription for: \(audioURL.path)")
        isTranscribing = true
        progress = 0

        defer {
            Task { @MainActor in
                self.isTranscribing = false
                self.progress = 1.0
            }
        }

        // Request speech recognition permission
        let authStatus = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status)
            }
        }

        print("Speech recognition auth status: \(authStatus.rawValue)")

        guard authStatus == .authorized else {
            print("Speech recognition permission denied")
            throw TranscriptionError.permissionDenied
        }

        await MainActor.run { progress = 0.2 }

        // Use Apple Speech Recognition
        let result = try await transcribeWithAppleSpeech(audioURL: audioURL)
        print("Transcription result: \(result)")
        return result
    }

    // MARK: - Apple Speech Framework

    private func transcribeWithAppleSpeech(audioURL: URL) async throws -> String {
        guard let recognizer = speechRecognizer, recognizer.isAvailable else {
            throw TranscriptionError.speechRecognizerUnavailable
        }

        let request = SFSpeechURLRecognitionRequest(url: audioURL)
        request.shouldReportPartialResults = false
        request.addsPunctuation = true

        await MainActor.run { progress = 0.4 }

        return try await withCheckedThrowingContinuation { continuation in
            recognizer.recognitionTask(with: request) { [weak self] result, error in
                Task { @MainActor in
                    self?.progress = 0.8
                }

                if let error = error {
                    // Check if it's just "no speech detected"
                    let nsError = error as NSError
                    if nsError.domain == "kAFAssistantErrorDomain" && nsError.code == 1110 {
                        continuation.resume(returning: "")
                        return
                    }
                    continuation.resume(throwing: TranscriptionError.transcriptionFailed(error.localizedDescription))
                    return
                }

                guard let result = result else {
                    continuation.resume(throwing: TranscriptionError.noResult)
                    return
                }

                if result.isFinal {
                    let text = result.bestTranscription.formattedString
                    continuation.resume(returning: text)
                }
            }
        }
    }
}

// MARK: - Errors

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
