import SwiftUI
import Combine

@MainActor
class AppState: ObservableObject {
    // MARK: - Recording State
    @Published var isRecording = false
    @Published var recordingStatus: RecordingStatus = .ready
    @Published var lastTranscription: String?
    @Published var audioLevel: Float = 0  // Normalized 0-1 for UI
    @Published var showTranscriptionSuccess = false  // For success animation

    // MARK: - Services
    let audioRecorder = AudioRecorder()
    let transcriptionManager = TranscriptionManager.shared
    let acousticAnalyzer = AcousticAnalyzer()
    let settings = SettingsManager.shared

    // MARK: - History
    @Published var transcriptionHistory: [Transcription] = []

    // MARK: - Health
    @Published var healthMetrics: VoiceHealthMetrics?
    @Published var healthHistory: [HealthDataPoint] = []
    @Published var baselineMetrics: BaselineMetrics?

    private var cancellables = Set<AnyCancellable>()
    private var audioLevelTimer: Timer?

    init() {
        loadHistory()
        loadHealthData()
        setupHotkeyBinding()
    }

    // MARK: - Recording

    private var recordingStartTime: Date?

    func startRecording() {
        guard !isRecording else { return }
        isRecording = true
        recordingStartTime = Date()
        postRecordingStateChange()
        recordingStatus = .recording
        showTranscriptionSuccess = false

        AnalyticsService.shared.track("recording_start")

        Task {
            do {
                try await audioRecorder.startRecording()
                startAudioLevelMonitoring()
            } catch {
                recordingStatus = .error(error.localizedDescription)
                isRecording = false
                postRecordingStateChange()
                AnalyticsService.shared.track("error", data: [
                    "context": "recording_start",
                    "error_type": String(describing: type(of: error))
                ])
            }
        }
    }

    private func startAudioLevelMonitoring() {
        audioLevelTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self = self else { return }
                let db = self.audioRecorder.updateMeters()
                // Convert dB (-160 to 0) to normalized value (0 to 1)
                // Typical speech is around -20 to -10 dB
                let normalized = max(0, min(1, (db + 50) / 50))
                self.audioLevel = normalized
            }
        }
    }

    private func stopAudioLevelMonitoring() {
        audioLevelTimer?.invalidate()
        audioLevelTimer = nil
        audioLevel = 0
    }

    private func postRecordingStateChange() {
        NotificationCenter.default.post(
            name: .recordingStateChanged,
            object: nil,
            userInfo: ["isRecording": isRecording]
        )
    }

    func stopRecording() {
        guard isRecording else { return }
        isRecording = false
        postRecordingStateChange()
        recordingStatus = .processing
        stopAudioLevelMonitoring()

        let recordingDurationMs: Int
        if let startTime = recordingStartTime {
            recordingDurationMs = Int(Date().timeIntervalSince(startTime) * 1000)
        } else {
            recordingDurationMs = 0
        }

        AnalyticsService.shared.track("recording_stop", data: [
            "duration_ms": recordingDurationMs
        ])

        Task {
            let transcriptionStartTime = Date()

            do {
                let audioURL = try await audioRecorder.stopRecording()
                print("Audio recorded, starting transcription...")
                let transcription = try await transcriptionManager.transcribe(audioURL: audioURL)
                print("Transcription completed: \(transcription)")

                let processingMs = Int(Date().timeIntervalSince(transcriptionStartTime) * 1000)
                let wordCount = transcription.split(separator: " ").count

                // Track transcription success
                AnalyticsService.shared.track("transcription_complete", data: [
                    "word_count": wordCount,
                    "backend": settings.transcriptionBackend.rawValue,
                    "model": settings.whisperModel.rawValue,
                    "processing_ms": processingMs
                ])

                // Apply grammar fixes if enabled
                let afterGrammar = settings.fixGrammar ? applyGrammarFixes(transcription) : transcription

                // Apply translation if enabled
                let (finalText, originalText, translatedTo) = await applyTranslation(afterGrammar)

                // Save to history
                let entry = Transcription(
                    text: finalText,
                    timestamp: Date(),
                    audioFilePath: settings.saveAudio ? audioURL.path : nil,
                    originalText: originalText,
                    translatedTo: translatedTo
                )
                saveTranscription(entry)

                lastTranscription = finalText
                recordingStatus = .success
                showTranscriptionSuccess = true

                // Auto-paste if enabled
                if settings.autoPaste {
                    pasteToFrontmostApp(finalText)
                }

                // Analyze voice health (runs in background)
                Task {
                    await analyzeVoiceHealth(audioURL: audioURL)

                    // Clean up audio after analysis if not saving
                    if !self.settings.saveAudio {
                        try? FileManager.default.removeItem(at: audioURL)
                    }
                }

                // Reset status after delay
                try? await Task.sleep(for: .seconds(2))
                recordingStatus = .ready

            } catch {
                print("Recording/transcription error: \(error)")
                recordingStatus = .error(error.localizedDescription)

                // Track transcription failure
                AnalyticsService.shared.track("transcription_failed", data: [
                    "reason": error.localizedDescription,
                    "error_type": String(describing: type(of: error))
                ])

                // Reset after showing error
                try? await Task.sleep(for: .seconds(3))
                recordingStatus = .ready
            }
        }
    }

    // MARK: - History Management

    private func loadHistory() {
        let historyURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_history.json")

        guard let data = try? Data(contentsOf: historyURL),
              let history = try? JSONDecoder().decode([Transcription].self, from: data) else {
            return
        }

        transcriptionHistory = history.sorted { $0.timestamp > $1.timestamp }
    }

    func saveTranscription(_ transcription: Transcription) {
        transcriptionHistory.insert(transcription, at: 0)

        let historyURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_history.json")

        if let data = try? JSONEncoder().encode(transcriptionHistory) {
            try? data.write(to: historyURL)
        }
    }

    func deleteTranscription(_ transcription: Transcription) {
        transcriptionHistory.removeAll { $0.id == transcription.id }

        // Remove audio file if exists
        if let audioPath = transcription.audioFilePath {
            try? FileManager.default.removeItem(atPath: audioPath)
        }

        // Save updated history
        let historyURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_history.json")

        if let data = try? JSONEncoder().encode(transcriptionHistory) {
            try? data.write(to: historyURL)
        }
    }

    // MARK: - Health Analysis

    func analyzeVoiceHealth(audioURL: URL) async {
        do {
            let metrics = try await acousticAnalyzer.analyzeAudio(at: audioURL)
            healthMetrics = metrics

            // Add to history
            let dataPoint = HealthDataPoint(
                date: metrics.timestamp,
                fatigueScore: Double(metrics.fatigueScore),
                illnessScore: Double(metrics.illnessScore)
            )
            healthHistory.append(dataPoint)

            // Keep only last 30 days of data
            let thirtyDaysAgo = Date().addingTimeInterval(-30 * 24 * 60 * 60)
            healthHistory = healthHistory.filter { $0.date > thirtyDaysAgo }

            // Save health history
            saveHealthHistory()

            // Update baseline reference
            loadBaseline()

            print("Voice health analyzed - Fatigue: \(metrics.fatigueScore)%, Illness: \(metrics.illnessScore)%")

            // Track health analysis completion
            AnalyticsService.shared.track("health_analysis_complete", data: [
                "fatigue_score": metrics.fatigueScore,
                "illness_score": metrics.illnessScore
            ])

            // Send notifications if enabled and thresholds exceeded
            if settings.healthNotificationsEnabled {
                if metrics.fatigueScore >= settings.fatigueAlertThreshold {
                    NotificationService.shared.sendHealthAlert(
                        title: "Voice Fatigue Detected",
                        body: "Your voice shows signs of fatigue (\(metrics.fatigueScore)%). Consider resting your voice.",
                        type: .fatigue
                    )
                }

                if metrics.illnessScore >= settings.illnessAlertThreshold {
                    NotificationService.shared.sendHealthAlert(
                        title: "Voice Health Alert",
                        body: "Changes in your voice may indicate early illness (\(metrics.illnessScore)%). Stay hydrated and monitor how you feel.",
                        type: .illness
                    )
                }
            }
        } catch {
            print("Voice health analysis failed: \(error)")
        }
    }

    private func loadHealthData() {
        loadHealthHistory()
        loadBaseline()
    }

    private func loadHealthHistory() {
        let historyURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_health")
            .appendingPathComponent("history.json")

        guard let data = try? Data(contentsOf: historyURL),
              let history = try? JSONDecoder().decode([HealthDataPointCodable].self, from: data) else {
            return
        }

        healthHistory = history.map {
            HealthDataPoint(date: $0.date, fatigueScore: $0.fatigueScore, illnessScore: $0.illnessScore)
        }
    }

    private func saveHealthHistory() {
        let historyURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_health")
            .appendingPathComponent("history.json")

        let codable = healthHistory.map {
            HealthDataPointCodable(date: $0.date, fatigueScore: $0.fatigueScore, illnessScore: $0.illnessScore)
        }

        try? FileManager.default.createDirectory(
            at: historyURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )

        if let data = try? JSONEncoder().encode(codable) {
            try? data.write(to: historyURL)
        }
    }

    private func loadBaseline() {
        let baselineURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_health")
            .appendingPathComponent("baseline.json")

        if let data = try? Data(contentsOf: baselineURL),
           let baseline = try? JSONDecoder().decode(BaselineMetrics.self, from: data) {
            baselineMetrics = baseline
        }
    }

    // MARK: - Helpers

    private func applyTranslation(_ text: String) async -> (text: String, original: String?, language: String?) {
        guard settings.translationEnabled, settings.targetLanguage.isEnabled else {
            return (text, nil, nil)
        }

        let translated = await TranslationService.shared.translate(text)
        if translated != text {
            return (translated, text, settings.targetLanguage.rawValue)
        }
        return (text, nil, nil)
    }

    private func applyGrammarFixes(_ text: String) -> String {
        var result = text.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !result.isEmpty else { return result }

        // Capitalize first letter
        result = result.prefix(1).uppercased() + result.dropFirst()

        // Common contractions
        let replacements = [
            "\\bi\\b": "I",
            "\\bim\\b": "I'm",
            "\\bdont\\b": "don't",
            "\\bcant\\b": "can't",
            "\\bwont\\b": "won't",
            "\\bive\\b": "I've",
            "\\bid\\b": "I'd",
            "\\bill\\b": "I'll"
        ]

        for (pattern, replacement) in replacements {
            if let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive) {
                result = regex.stringByReplacingMatches(
                    in: result,
                    range: NSRange(result.startIndex..., in: result),
                    withTemplate: replacement
                )
            }
        }

        // Add period if missing punctuation
        if let lastChar = result.last, !".!?".contains(lastChar) {
            result += "."
        }

        return result
    }

    private func pasteToFrontmostApp(_ text: String) {
        // Copy to clipboard
        NSPasteboard.general.clearContents()
        let success = NSPasteboard.general.setString(text, forType: .string)
        print("Clipboard set: \(success), text: \(text.prefix(50))...")

        // Small delay to ensure clipboard is ready
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            // Simulate Cmd+V using CGEvent (more reliable than AppleScript)
            self.simulatePaste()
        }
    }

    private func simulatePaste() {
        // Try CGEvent approach first (doesn't require Accessibility for clipboard, but does for keystroke)
        let source = CGEventSource(stateID: .hidSystemState)

        // Key down
        guard let keyDown = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: true) else {
            print("Failed to create key down event")
            return
        }
        keyDown.flags = .maskCommand

        // Key up
        guard let keyUp = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: false) else {
            print("Failed to create key up event")
            return
        }
        keyUp.flags = .maskCommand

        // Post events
        keyDown.post(tap: .cghidEventTap)
        keyUp.post(tap: .cghidEventTap)
        print("Paste keystroke sent (Cmd+V)")
    }

    private func setupHotkeyBinding() {
        NotificationCenter.default.publisher(for: .hotkeyPressed)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.startRecording()
            }
            .store(in: &cancellables)

        NotificationCenter.default.publisher(for: .hotkeyReleased)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.stopRecording()
            }
            .store(in: &cancellables)
    }
}

// MARK: - Recording Status

enum RecordingStatus: Equatable {
    case ready
    case recording
    case processing
    case success
    case error(String)

    var displayText: String {
        switch self {
        case .ready: return "Ready"
        case .recording: return "Recording..."
        case .processing: return "Processing..."
        case .success: return "Done!"
        case .error(let message): return "Error: \(message)"
        }
    }

    var color: Color {
        switch self {
        case .ready: return Color.brandNavy
        case .recording: return Color.recordingActive  // Keep red for safety
        case .processing: return Color.brandGray
        case .success: return Color.statusSuccess
        case .error: return Color.statusWarning
        }
    }
}

// MARK: - Notifications

extension Notification.Name {
    static let hotkeyPressed = Notification.Name("hotkeyPressed")
    static let hotkeyReleased = Notification.Name("hotkeyReleased")
    static let recordingStateChanged = Notification.Name("recordingStateChanged")
    static let openHistoryWindow = Notification.Name("openHistoryWindow")
    static let openHealthWindow = Notification.Name("openHealthWindow")
}
