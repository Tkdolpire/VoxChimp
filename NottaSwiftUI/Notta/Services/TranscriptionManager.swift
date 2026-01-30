import Foundation
import Combine

/// Unified manager for handling transcription across different backends
@MainActor
class TranscriptionManager: ObservableObject {
    static let shared = TranscriptionManager()

    @Published var isTranscribing = false
    @Published var isModelReady = false
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
        defer { isPreparingModel = false }

        do {
            // Check if model is already loaded
            if whisperKitService.isModelLoaded {
                print("[TranscriptionManager] Model already loaded")
                updateModelReadyState()
                return
            }

            print("[TranscriptionManager] Preparing model: \(model.rawValue)")

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
    /// Falls back to Apple Speech if Whisper model isn't ready
    func transcribe(audioURL: URL) async throws -> String {
        isTranscribing = true
        progress = 0
        error = nil

        defer {
            isTranscribing = false
            progress = 1.0
        }

        do {
            let result: String

            switch currentBackend {
            case .appleSpeech:
                result = try await appleSpeechService.transcribe(audioURL: audioURL)

            case .whisperKit:
                // Fall back to Apple Speech if Whisper model isn't ready
                if !whisperKitService.isModelLoaded {
                    print("[TranscriptionManager] Whisper model not ready, falling back to Apple Speech")
                    result = try await appleSpeechService.transcribe(audioURL: audioURL)
                } else {
                    result = try await whisperKitService.transcribe(audioURL: audioURL)
                }
            }

            return result

        } catch {
            self.error = error.localizedDescription
            throw error
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
