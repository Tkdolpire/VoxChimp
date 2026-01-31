import Foundation
import WhisperKit

/// Service for transcribing audio using WhisperKit (local Whisper models)
@MainActor
class WhisperKitService: ObservableObject {
    @Published var isTranscribing = false
    @Published var progress: Double = 0
    @Published var isModelLoaded = false
    @Published var loadingError: String?

    private var whisperKit: WhisperKit?
    private var currentModel: WhisperModel?

    // MARK: - Model Loading

    /// Load a specific Whisper model
    func loadModel(_ model: WhisperModel) async throws {
        guard currentModel != model || whisperKit == nil else {
            print("[WhisperKit] Model \(model.rawValue) already loaded")
            return
        }

        let startTime = Date()
        print("[WhisperKit] ⏳ Loading model: \(model.rawValue)...")
        print("[WhisperKit]    This includes: loading from disk, CoreML compilation, and prewarming")
        isModelLoaded = false
        loadingError = nil

        do {
            // WhisperKit handles model download automatically
            // prewarm: true makes first transcription faster but loading slower
            whisperKit = try await WhisperKit(
                model: model.rawValue,
                verbose: true,
                prewarm: true
            )

            let loadTime = Date().timeIntervalSince(startTime)
            currentModel = model
            isModelLoaded = true
            print("[WhisperKit] ✓ Model loaded successfully in \(String(format: "%.1f", loadTime)) seconds")
        } catch {
            let loadTime = Date().timeIntervalSince(startTime)
            loadingError = error.localizedDescription
            print("[WhisperKit] ✗ Failed to load model after \(String(format: "%.1f", loadTime))s: \(error)")
            throw WhisperKitError.downloadFailed(error.localizedDescription)
        }
    }

    /// Check if a model is currently loaded
    func isLoaded(_ model: WhisperModel) -> Bool {
        return currentModel == model && whisperKit != nil
    }

    /// Unload the current model to free memory
    func unloadModel() {
        whisperKit = nil
        currentModel = nil
        isModelLoaded = false
        print("[WhisperKit] Model unloaded")
    }

    // MARK: - Transcription

    func transcribe(audioURL: URL) async throws -> String {
        guard let whisperKit = whisperKit else {
            throw WhisperKitError.modelNotLoaded
        }

        let startTime = Date()
        print("[WhisperKit] Starting transcription...")
        isTranscribing = true
        progress = 0

        defer {
            isTranscribing = false
            progress = 1.0
        }

        do {
            progress = 0.1

            // Transcribe the audio file using simplified API
            let results = try await whisperKit.transcribe(audioPath: audioURL.path)

            progress = 0.95

            // Combine all transcription results
            let text = results.map { $0.text }.joined(separator: " ").trimmingCharacters(in: CharacterSet.whitespacesAndNewlines)

            let transcribeTime = Date().timeIntervalSince(startTime)
            print("[WhisperKit] ✓ Transcription complete in \(String(format: "%.2f", transcribeTime))s: \(text.prefix(50))...")
            return text

        } catch {
            print("[WhisperKit] ✗ Transcription failed: \(error)")
            throw WhisperKitError.transcriptionFailed(error.localizedDescription)
        }
    }
}
