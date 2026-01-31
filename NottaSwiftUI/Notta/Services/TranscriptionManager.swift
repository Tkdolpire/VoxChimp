import Foundation
import Combine

/// Unified manager for handling transcription across different backends
@MainActor
class TranscriptionManager: ObservableObject {
    static let shared = TranscriptionManager()

    @Published var isTranscribing = false
    @Published var isModelReady = false
    @Published var isLoadingModel = false
    @Published var modelLoadingProgress: String = ""
    @Published var progress: Double = 0
    @Published var currentBackend: TranscriptionBackend = .appleSpeech
    @Published var error: String?

    private let appleSpeechService = AppleSpeechService()
    private let whisperKitService = WhisperKitService()
    private let modelManager = ModelManager.shared
    private var cancellables = Set<AnyCancellable>()

    private init() {
        // Load saved backend preference
        let settings = SettingsManager.shared
        currentBackend = settings.transcriptionBackend

        // Apple Speech is always ready
        updateModelReadyState()

        // Observe settings changes
        settings.$transcriptionBackend
            .receive(on: DispatchQueue.main)
            .sink { [weak self] backend in
                self?.switchBackend(to: backend)
            }
            .store(in: &cancellables)

        // Observe whisper service state
        whisperKitService.$isModelLoaded
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.updateModelReadyState()
            }
            .store(in: &cancellables)
    }

    // MARK: - Backend Management

    /// Switch to a different transcription backend
    func switchBackend(to backend: TranscriptionBackend) {
        guard backend != currentBackend else { return }

        print("[TranscriptionManager] Switching backend to: \(backend.rawValue)")
        currentBackend = backend
        error = nil
        updateModelReadyState()

        // If switching to Whisper, try to load the model
        if backend == .whisperKit {
            Task {
                await prepareWhisperModel()
            }
        }
    }

    private var isPreparingModel = false

    /// Prepare the Whisper model for transcription
    func prepareWhisperModel() async {
        let settings = SettingsManager.shared
        let model = settings.whisperModel

        guard currentBackend == .whisperKit else { return }

        // Prevent concurrent preparation attempts
        guard !isPreparingModel else {
            print("[TranscriptionManager] Model preparation already in progress")
            return
        }
        isPreparingModel = true
        isLoadingModel = true
        modelLoadingProgress = "Downloading \(model.displayName) model..."

        defer {
            isPreparingModel = false
            isLoadingModel = false
            modelLoadingProgress = ""
        }

        do {
            // Check if model is already loaded
            if whisperKitService.isModelLoaded {
                print("[TranscriptionManager] Model already loaded")
                updateModelReadyState()
                return
            }

            print("[TranscriptionManager] Preparing model: \(model.rawValue)")
            modelLoadingProgress = "Loading \(model.displayName) model..."

            // Load the model (WhisperKit handles download automatically)
            try await whisperKitService.loadModel(model)
            updateModelReadyState()
            print("[TranscriptionManager] Model ready")
        } catch {
            self.error = error.localizedDescription
            print("[TranscriptionManager] Failed to prepare model: \(error)")
        }
    }

    // MARK: - Transcription

    /// Transcribe audio from the given URL using the current backend
    /// Falls back to Apple Speech if Whisper model isn't ready or encounters errors
    func transcribe(audioURL: URL) async throws -> String {
        isTranscribing = true
        progress = 0
        error = nil

        defer {
            isTranscribing = false
            progress = 1.0
        }

        switch currentBackend {
        case .appleSpeech:
            return try await appleSpeechService.transcribe(audioURL: audioURL)

        case .whisperKit:
            // Fall back to Apple Speech if Whisper model isn't ready
            if !whisperKitService.isModelLoaded {
                print("[TranscriptionManager] Whisper model not ready, falling back to Apple Speech")
                return try await appleSpeechService.transcribe(audioURL: audioURL)
            }

            // Try Whisper, with fallback to Apple Speech on recoverable errors
            do {
                return try await whisperKitService.transcribe(audioURL: audioURL)
            } catch {
                let errorMessage = error.localizedDescription.lowercased()

                // Check for recoverable errors (tokenizer, configuration issues)
                let isRecoverableError = errorMessage.contains("tokenizer") ||
                                         errorMessage.contains("configuration") ||
                                         errorMessage.contains("incomplete") ||
                                         errorMessage.contains("couldn't be moved")

                if isRecoverableError {
                    print("[TranscriptionManager] Whisper error (recoverable), falling back to Apple Speech: \(error)")
                    // Try to reload model in background for next time
                    Task {
                        whisperKitService.unloadModel()
                        await prepareWhisperModel()
                    }
                    return try await appleSpeechService.transcribe(audioURL: audioURL)
                }

                // Non-recoverable error, propagate it
                self.error = error.localizedDescription
                throw error
            }
        }
    }

    // MARK: - Private

    private func updateModelReadyState() {
        switch currentBackend {
        case .appleSpeech:
            isModelReady = true
        case .whisperKit:
            isModelReady = whisperKitService.isModelLoaded
        }
    }
}
