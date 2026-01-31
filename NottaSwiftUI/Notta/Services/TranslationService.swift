import Foundation
import SwiftUI
import AppKit
#if canImport(Translation)
import Translation
#endif

/// Manages translation state and coordinates with SwiftUI's translation task modifier.
/// The actual translation happens via .translationTask in the view layer.
@MainActor
class TranslationService: ObservableObject {
    static let shared = TranslationService()

    // MARK: - Published State

    @Published var isTranslating = false
    @Published var isDownloadingModel = false
    @Published var downloadProgress: String = ""
    @Published var error: String?

    // Translation request/response flow
    @Published var pendingText: String?
    @Published var translatedText: String?

    // Configuration trigger - when this changes, the translation task fires
    // We use a simple counter since the actual configuration is created in the modifier
    @Published var translationRequestId: Int = 0

    private var translationContinuation: CheckedContinuation<String, Never>?
    private var currentTargetLanguage: TranslationLanguage?

    // Track language status
    @Published var languageStatuses: [TranslationLanguage: LanguageStatus] = [:]

    enum LanguageStatus: Equatable {
        case unknown
        case checking
        case installed
        case needsDownload
        case unsupported
    }

    private init() {}

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

    /// Whether translation is available on this system (macOS 14.4+)
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

        print("[Translation] ⏳ Translating to \(settings.targetLanguage.displayName)...")

        // Set up the translation request
        isTranslating = true
        error = nil
        pendingText = text
        translatedText = nil
        currentTargetLanguage = settings.targetLanguage

        // Trigger the translation task by incrementing the request ID
        translationRequestId += 1
        let currentRequestId = translationRequestId

        // Wait for translation with timeout to prevent leaked continuations
        let result = await withCheckedContinuation { (continuation: CheckedContinuation<String, Never>) in
            self.translationContinuation = continuation

            // Timeout after 10 seconds - resume with original text if translation doesn't complete
            Task { @MainActor in
                try? await Task.sleep(for: .seconds(10))
                // Only timeout if this is still the active request and continuation hasn't been resumed
                if self.translationRequestId == currentRequestId,
                   self.translationContinuation != nil {
                    print("[Translation] ⚠️ Timeout after 10s - translation task didn't fire")
                    print("[Translation] ⚠️ This often means the language model isn't downloaded.")
                    print("[Translation] ⚠️ Open the Translate app and translate something to/from this language to download it.")
                    self.error = "Translation timed out. The language may need to be downloaded in the Translate app first."
                    self.completeTranslation(with: text)
                }
            }
        }

        isTranslating = false
        return result
    }

    /// Get the current configuration for the translation task
    @available(macOS 15.0, *)
    func currentConfiguration() -> TranslationSession.Configuration? {
        guard let language = currentTargetLanguage, pendingText != nil else {
            return nil
        }
        return TranslationSession.Configuration(
            source: Locale.Language(identifier: "en"),
            target: language.locale
        )
    }

    /// Called by the view's .translationTask to perform the actual translation
    @available(macOS 15.0, *)
    func performTranslation(session: TranslationSession) async {
        guard let text = pendingText else {
            print("[Translation] No pending text, skipping")
            completeTranslation(with: nil)
            return
        }

        print("[Translation] performTranslation called with text: '\(text.prefix(30))...'")
        isDownloadingModel = true
        downloadProgress = "Translating..."

        do {
            let response = try await session.translate(text)
            print("[Translation] ✓ Completed: '\(text.prefix(30))...' -> '\(response.targetText.prefix(30))...'")
            translatedText = response.targetText

            // Update language status since it worked
            if let language = currentTargetLanguage {
                languageStatuses[language] = .installed
            }

            completeTranslation(with: response.targetText)
        } catch {
            let errorString = String(describing: error)

            // Check for common error types
            if errorString.contains("Code=14") || errorString.contains("internalError") {
                self.error = "Language model not downloaded. Use the Translate app to download it first."
                print("[Translation] ✗ Language model not available. Open System Translate app to download the language pack.")
            } else {
                self.error = "Translation failed: \(error.localizedDescription)"
            }
            print("[Translation] ✗ Error: \(error)")
            // Fail-open: return original text
            completeTranslation(with: text)
        }

        isDownloadingModel = false
        downloadProgress = ""
        pendingText = nil
        currentTargetLanguage = nil
    }

    /// Complete the pending translation request
    private func completeTranslation(with result: String?) {
        guard let continuation = translationContinuation else { return }
        translationContinuation = nil
        continuation.resume(returning: result ?? pendingText ?? "")
    }

    /// Call when target language changes
    func onLanguageChanged() {
        error = nil
    }

    /// Cancel any pending translation
    func cancelPendingTranslation() {
        if let text = pendingText {
            completeTranslation(with: text)
        }
        pendingText = nil
        currentTargetLanguage = nil
        isTranslating = false
        isDownloadingModel = false
    }
}

// MARK: - SwiftUI View Extension

/// View modifier that adds translation capability to a view
@available(macOS 15.0, *)
struct TranslationTaskModifier: ViewModifier {
    @StateObject private var translationService = TranslationService.shared
    @State private var configuration: TranslationSession.Configuration?
    @State private var triggerTask = false

    func body(content: Content) -> some View {
        content
            .onChange(of: translationService.translationRequestId) { _, newId in
                // Reset configuration and use task to set new config after SwiftUI processes the nil
                if newId > 0 {
                    configuration = nil
                    triggerTask.toggle()
                }
            }
            .task(id: triggerTask) {
                // Small delay to ensure nil configuration is processed by SwiftUI
                try? await Task.sleep(for: .milliseconds(50))
                if translationService.pendingText != nil {
                    configuration = translationService.currentConfiguration()
                }
            }
            .translationTask(configuration) { session in
                await translationService.performTranslation(session: session)
                // Reset configuration after translation completes
                configuration = nil
            }
    }
}

extension View {
    /// Adds translation capability to the view
    @ViewBuilder
    func withTranslationSupport() -> some View {
        if #available(macOS 15.0, *) {
            self.modifier(TranslationTaskModifier())
        } else {
            self
        }
    }
}
