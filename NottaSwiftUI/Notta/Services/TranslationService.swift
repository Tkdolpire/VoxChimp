import Foundation
import SwiftUI
import AppKit
#if canImport(Translation)
import Translation
#endif

/// Request for translation with unique ID
struct TranslationRequest: Equatable {
    let id: UUID
    let text: String
    let language: TranslationLanguage

    static func == (lhs: TranslationRequest, rhs: TranslationRequest) -> Bool {
        lhs.id == rhs.id
    }
}

/// Manages translation using Apple's Translation framework.
/// Uses an inline invisible view with .translationTask modifier for reliable translation.
@MainActor
class TranslationService: ObservableObject {
    static let shared = TranslationService()

    // MARK: - Published State

    @Published var isTranslating = false
    @Published var error: String?
    @Published var isDownloadingModel = false
    @Published var downloadProgress: String = ""

    // Translation trigger - observed by inline view
    @Published var currentRequest: TranslationRequest?

    // Legacy properties for API compatibility
    @Published var pendingText: String?
    @Published var translatedText: String?
    var translationRequestId: Int = 0

    // Track language status
    @Published var languageStatuses: [TranslationLanguage: LanguageStatus] = [:]

    enum LanguageStatus: Equatable {
        case unknown
        case checking
        case installed
        case needsDownload
        case unsupported
    }

    // MARK: - Private State

    private var pendingContinuations: [UUID: CheckedContinuation<String, Never>] = [:]
    private var timeoutTasks: [UUID: Task<Void, Never>] = [:]

    private init() {}

    // MARK: - Language Status

    /// Check language availability status using Apple's LanguageAvailability API
    func checkLanguageStatus(_ language: TranslationLanguage) async -> LanguageStatus {
        guard language.isEnabled else { return .unknown }
        guard isAvailable else { return .unknown }

        if #available(macOS 15.0, *) {
            languageStatuses[language] = .checking

            let availability = LanguageAvailability()
            let sourceLocale = Locale.Language(identifier: "en")
            let targetLocale = language.locale

            let status = await availability.status(from: sourceLocale, to: targetLocale)

            let result: LanguageStatus
            switch status {
            case .installed:
                result = .installed
            case .supported:
                result = .needsDownload
            case .unsupported:
                result = .unsupported
            @unknown default:
                result = .unknown
            }

            languageStatuses[language] = result
            print("[Translation] Language \(language.displayName) status: \(result)")
            return result
        }

        return .unknown
    }

    /// Check all language statuses
    func checkAllLanguageStatuses() async {
        guard isAvailable else { return }

        for language in TranslationLanguage.enabledCases {
            _ = await checkLanguageStatus(language)
        }
    }

    /// Get the current status for a language
    func getLanguageStatus(_ language: TranslationLanguage) -> LanguageStatus {
        languageStatuses[language] ?? .unknown
    }

    /// Open the system Translate app (for downloading languages)
    func openTranslateApp() {
        let translateAppURL = URL(fileURLWithPath: "/System/Applications/Translate.app")
        NSWorkspace.shared.open(translateAppURL)
    }

    /// Open System Settings to Language & Region
    func openLanguageSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.Localization-Settings.extension") {
            NSWorkspace.shared.open(url)
        }
    }

    // MARK: - Availability

    /// Whether translation is available on this system (macOS 15.0+)
    var isAvailable: Bool {
        if #available(macOS 15.0, *) {
            return true
        }
        return false
    }

    // MARK: - Translation API

    /// Translate text to the target language specified in settings.
    /// Returns original text on any failure (fail-open pattern).
    func translate(_ text: String) async -> String {
        guard isAvailable else {
            print("[Translation] Not available: macOS 15.0+ required")
            return text
        }

        let settings = SettingsManager.shared
        print("[Translation] Checking settings - enabled: \(settings.translationEnabled), target: \(settings.targetLanguage.displayName)")

        guard settings.translationEnabled else {
            print("[Translation] Disabled in settings, skipping")
            return text
        }

        guard settings.targetLanguage.isEnabled else {
            print("[Translation] Target language is 'none', skipping")
            return text
        }

        print("[Translation] Translating to \(settings.targetLanguage.displayName)...")
        print("[Translation] Text length: \(text.count) characters")

        isTranslating = true
        error = nil

        defer {
            isTranslating = false
        }

        if #available(macOS 15.0, *) {
            // First check if language is available
            let availability = LanguageAvailability()
            let sourceLocale = Locale.Language(identifier: "en")
            let targetLocale = settings.targetLanguage.locale
            let status = await availability.status(from: sourceLocale, to: targetLocale)

            if status == .unsupported {
                print("[Translation] Language pair not supported")
                error = "Translation from English to \(settings.targetLanguage.displayName) is not supported."
                return text
            }

            if status == .supported {
                // Language needs to be downloaded first
                print("[Translation] Language needs to be downloaded...")
                self.error = "Language model not ready. Please open the Translate app and download \(settings.targetLanguage.displayName)."
                languageStatuses[settings.targetLanguage] = .needsDownload
                return text
            }

            // Language is installed - trigger translation via the view
            return await triggerTranslation(text: text, to: settings.targetLanguage)
        }

        return text
    }

    /// Trigger translation by setting the request (observed by inline view)
    @available(macOS 15.0, *)
    private func triggerTranslation(text: String, to language: TranslationLanguage) async -> String {
        let requestId = UUID()
        let request = TranslationRequest(id: requestId, text: text, language: language)

        print("[Translation] Creating request \(requestId)")

        return await withCheckedContinuation { continuation in
            // Store continuation
            pendingContinuations[requestId] = continuation

            // Set up timeout (10 seconds instead of 30)
            let timeoutTask = Task {
                try? await Task.sleep(nanoseconds: 10_000_000_000) // 10 seconds

                // If still pending, timeout
                if let cont = self.pendingContinuations.removeValue(forKey: requestId) {
                    print("[Translation] Request \(requestId) timed out")
                    self.error = "Translation timed out. Please try again."
                    self.currentRequest = nil
                    cont.resume(returning: text)
                }
                self.timeoutTasks.removeValue(forKey: requestId)
            }
            timeoutTasks[requestId] = timeoutTask

            // Trigger the translation view
            currentRequest = request
        }
    }

    /// Called by the inline translation view when translation completes
    func completeTranslation(requestId: UUID, result: String) {
        print("[Translation] Completed request \(requestId): '\(result.prefix(50))...'")

        // Cancel timeout
        timeoutTasks[requestId]?.cancel()
        timeoutTasks.removeValue(forKey: requestId)

        // Resume continuation
        if let continuation = pendingContinuations.removeValue(forKey: requestId) {
            if let request = currentRequest {
                languageStatuses[request.language] = .installed
            }
            currentRequest = nil
            continuation.resume(returning: result)
        }
    }

    /// Called by the inline translation view when translation fails
    func failTranslation(requestId: UUID, error: Error, originalText: String) {
        let errorString = String(describing: error)
        print("[Translation] Request \(requestId) failed: \(error)")

        // Cancel timeout
        timeoutTasks[requestId]?.cancel()
        timeoutTasks.removeValue(forKey: requestId)

        // Parse common errors
        if errorString.contains("Code=14") || errorString.contains("internalError") {
            if let request = currentRequest {
                self.error = "Language model not downloaded. Please open the Translate app and download \(request.language.displayName)."
                languageStatuses[request.language] = .needsDownload
            } else {
                self.error = "Language model not downloaded."
            }
        } else if errorString.contains("cancelled") {
            self.error = "Translation was cancelled."
        } else {
            self.error = "Translation failed: \(error.localizedDescription)"
        }

        // Resume with original text (fail-open)
        if let continuation = pendingContinuations.removeValue(forKey: requestId) {
            currentRequest = nil
            continuation.resume(returning: originalText)
        }
    }

    /// Call when target language changes
    func onLanguageChanged() {
        error = nil
    }

    /// Cancel any pending translation (for API compatibility)
    func cancelPendingTranslation() {
        pendingText = nil
        isTranslating = false
        isDownloadingModel = false

        // Cancel all pending
        for (requestId, continuation) in pendingContinuations {
            timeoutTasks[requestId]?.cancel()
            if let request = currentRequest, request.id == requestId {
                continuation.resume(returning: request.text)
            } else {
                continuation.resume(returning: "")
            }
        }
        pendingContinuations.removeAll()
        timeoutTasks.removeAll()
        currentRequest = nil
    }
}

// MARK: - Inline Translation View

/// Invisible view that hosts the .translationTask modifier.
/// Add this to your main view hierarchy (e.g., in MainView or NottaApp).
@available(macOS 15.0, *)
struct InlineTranslationView: View {
    @ObservedObject var service: TranslationService

    var body: some View {
        // Use request ID to force view recreation for each new request
        // This ensures .translationTask fires for every request, even with same language pair
        TranslationTaskView(request: service.currentRequest, service: service)
            .id(service.currentRequest?.id ?? UUID())
    }
}

/// Inner view that gets recreated for each translation request
@available(macOS 15.0, *)
private struct TranslationTaskView: View {
    let request: TranslationRequest?
    let service: TranslationService

    @State private var translationConfig: TranslationSession.Configuration?
    @State private var hasTriggered = false

    var body: some View {
        Color.clear
            .frame(width: 1, height: 1)
            .translationTask(translationConfig) { session in
                guard let request = request else { return }

                do {
                    let response = try await session.translate(request.text)
                    await MainActor.run {
                        service.completeTranslation(requestId: request.id, result: response.targetText)
                    }
                } catch {
                    await MainActor.run {
                        service.failTranslation(requestId: request.id, error: error, originalText: request.text)
                    }
                }
            }
            .onAppear {
                guard let request = request, !hasTriggered else { return }
                hasTriggered = true

                // Set config to trigger translation
                translationConfig = TranslationSession.Configuration(
                    source: Locale.Language(identifier: "en"),
                    target: request.language.locale
                )
            }
    }
}

// MARK: - SwiftUI View Extension

extension View {
    /// Add translation support to a view by embedding the inline translation helper.
    @ViewBuilder
    func withTranslationSupport() -> some View {
        if #available(macOS 15.0, *) {
            ZStack {
                self
                InlineTranslationView(service: TranslationService.shared)
            }
        } else {
            self
        }
    }
}
