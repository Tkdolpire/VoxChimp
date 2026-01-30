import Foundation
import Speech
import AVFoundation

/// Service for transcribing audio using Apple's Speech framework
class AppleSpeechService: ObservableObject, TranscriptionServiceProtocol {
    @Published var isTranscribing = false
    @Published var progress: Double = 0

    private let speechRecognizer: SFSpeechRecognizer?

    init() {
        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    }

    // MARK: - TranscriptionServiceProtocol

    func transcribe(audioURL: URL) async throws -> String {
        print("[AppleSpeech] Starting transcription for: \(audioURL.path)")
        await MainActor.run {
            isTranscribing = true
            progress = 0
        }

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

        print("[AppleSpeech] Auth status: \(authStatus.rawValue)")

        guard authStatus == .authorized else {
            print("[AppleSpeech] Permission denied")
            throw TranscriptionError.permissionDenied
        }

        await MainActor.run { progress = 0.2 }

        let result = try await transcribeWithAppleSpeech(audioURL: audioURL)
        print("[AppleSpeech] Result: \(result)")
        return result
    }

    // MARK: - Private

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
