import Foundation
import SwiftUI

class SettingsManager: ObservableObject {
    static let shared = SettingsManager()

    private let defaults = UserDefaults.standard

    // MARK: - Keys
    private enum Keys {
        static let transcriptionBackend = "transcriptionBackend"
        static let whisperModel = "whisperModel"
        static let hotkey = "hotkey"
        static let autoPaste = "autoPaste"
        static let fixGrammar = "fixGrammar"
        static let saveAudio = "saveAudio"
        static let floatOnTop = "floatOnTop"
        static let showInMenuBar = "showInMenuBar"
        static let launchAtLogin = "launchAtLogin"
        static let healthNotificationsEnabled = "healthNotificationsEnabled"
        static let fatigueAlertThreshold = "fatigueAlertThreshold"
        static let illnessAlertThreshold = "illnessAlertThreshold"
        static let translationEnabled = "translationEnabled"
        static let targetLanguage = "targetLanguage"
        static let analyticsEnabled = "notta.analytics.enabled"
    }

    // MARK: - Published Properties

    @Published var transcriptionBackend: TranscriptionBackend {
        didSet {
            defaults.set(transcriptionBackend.rawValue, forKey: Keys.transcriptionBackend)
            let oldVal = oldValue.rawValue
            let newVal = transcriptionBackend.rawValue
            Task { @MainActor in
                AnalyticsService.shared.track("settings_changed", data: [
                    "setting": "transcription_backend",
                    "old_value": oldVal,
                    "new_value": newVal
                ])
            }
        }
    }

    @Published var whisperModel: WhisperModel {
        didSet {
            defaults.set(whisperModel.rawValue, forKey: Keys.whisperModel)
            let oldVal = oldValue.rawValue
            let newVal = whisperModel.rawValue
            Task { @MainActor in
                AnalyticsService.shared.track("settings_changed", data: [
                    "setting": "whisper_model",
                    "old_value": oldVal,
                    "new_value": newVal
                ])
            }
        }
    }

    @Published var hotkey: HotkeyOption {
        didSet {
            defaults.set(hotkey.rawValue, forKey: Keys.hotkey)
            let oldVal = oldValue.rawValue
            let newVal = hotkey.rawValue
            Task { @MainActor in
                AnalyticsService.shared.track("settings_changed", data: [
                    "setting": "hotkey",
                    "old_value": oldVal,
                    "new_value": newVal
                ])
            }
        }
    }

    @Published var autoPaste: Bool {
        didSet {
            defaults.set(autoPaste, forKey: Keys.autoPaste)
            let oldVal = String(oldValue)
            let newVal = String(autoPaste)
            Task { @MainActor in
                AnalyticsService.shared.track("settings_changed", data: [
                    "setting": "auto_paste",
                    "old_value": oldVal,
                    "new_value": newVal
                ])
            }
        }
    }

    @Published var fixGrammar: Bool {
        didSet {
            defaults.set(fixGrammar, forKey: Keys.fixGrammar)
            let oldVal = String(oldValue)
            let newVal = String(fixGrammar)
            Task { @MainActor in
                AnalyticsService.shared.track("settings_changed", data: [
                    "setting": "fix_grammar",
                    "old_value": oldVal,
                    "new_value": newVal
                ])
            }
        }
    }

    @Published var saveAudio: Bool {
        didSet {
            defaults.set(saveAudio, forKey: Keys.saveAudio)
            let oldVal = String(oldValue)
            let newVal = String(saveAudio)
            Task { @MainActor in
                AnalyticsService.shared.track("settings_changed", data: [
                    "setting": "save_audio",
                    "old_value": oldVal,
                    "new_value": newVal
                ])
            }
        }
    }

    @Published var floatOnTop: Bool {
        didSet { defaults.set(floatOnTop, forKey: Keys.floatOnTop) }
    }

    @Published var showInMenuBar: Bool {
        didSet { defaults.set(showInMenuBar, forKey: Keys.showInMenuBar) }
    }

    @Published var launchAtLogin: Bool {
        didSet { defaults.set(launchAtLogin, forKey: Keys.launchAtLogin) }
    }

    @Published var healthNotificationsEnabled: Bool {
        didSet {
            defaults.set(healthNotificationsEnabled, forKey: Keys.healthNotificationsEnabled)
            let oldVal = String(oldValue)
            let newVal = String(healthNotificationsEnabled)
            Task { @MainActor in
                AnalyticsService.shared.track("settings_changed", data: [
                    "setting": "health_notifications",
                    "old_value": oldVal,
                    "new_value": newVal
                ])
            }
        }
    }

    @Published var fatigueAlertThreshold: Int {
        didSet { defaults.set(fatigueAlertThreshold, forKey: Keys.fatigueAlertThreshold) }
    }

    @Published var illnessAlertThreshold: Int {
        didSet { defaults.set(illnessAlertThreshold, forKey: Keys.illnessAlertThreshold) }
    }

    @Published var translationEnabled: Bool {
        didSet {
            defaults.set(translationEnabled, forKey: Keys.translationEnabled)
            let oldVal = String(oldValue)
            let newVal = String(translationEnabled)
            Task { @MainActor in
                AnalyticsService.shared.track("settings_changed", data: [
                    "setting": "translation_enabled",
                    "old_value": oldVal,
                    "new_value": newVal
                ])
            }
        }
    }

    @Published var targetLanguage: TranslationLanguage {
        didSet {
            defaults.set(targetLanguage.rawValue, forKey: Keys.targetLanguage)
            // Invalidate translation session when language changes
            Task { @MainActor in
                TranslationService.shared.onLanguageChanged()
            }
        }
    }

    @Published var analyticsEnabled: Bool {
        didSet {
            // Analytics state is managed by AnalyticsService, but we expose it here for UI binding
            let shouldEnable = analyticsEnabled
            Task { @MainActor in
                if shouldEnable {
                    AnalyticsService.shared.enable()
                } else {
                    AnalyticsService.shared.disable()
                }
            }
        }
    }

    // MARK: - Initialization

    private init() {
        // Load saved values or use defaults
        self.transcriptionBackend = TranscriptionBackend(rawValue: defaults.string(forKey: Keys.transcriptionBackend) ?? "") ?? .appleSpeech
        self.whisperModel = WhisperModel(rawValue: defaults.string(forKey: Keys.whisperModel) ?? "") ?? .small
        self.hotkey = HotkeyOption(rawValue: defaults.string(forKey: Keys.hotkey) ?? "") ?? .leftOption
        self.autoPaste = defaults.object(forKey: Keys.autoPaste) as? Bool ?? true
        self.fixGrammar = defaults.object(forKey: Keys.fixGrammar) as? Bool ?? true
        self.saveAudio = defaults.object(forKey: Keys.saveAudio) as? Bool ?? false
        self.floatOnTop = defaults.object(forKey: Keys.floatOnTop) as? Bool ?? true
        self.showInMenuBar = defaults.object(forKey: Keys.showInMenuBar) as? Bool ?? false
        self.launchAtLogin = defaults.object(forKey: Keys.launchAtLogin) as? Bool ?? false
        self.healthNotificationsEnabled = defaults.object(forKey: Keys.healthNotificationsEnabled) as? Bool ?? true
        self.fatigueAlertThreshold = defaults.object(forKey: Keys.fatigueAlertThreshold) as? Int ?? 60
        self.illnessAlertThreshold = defaults.object(forKey: Keys.illnessAlertThreshold) as? Int ?? 60
        self.translationEnabled = defaults.object(forKey: Keys.translationEnabled) as? Bool ?? false
        self.targetLanguage = TranslationLanguage(rawValue: defaults.string(forKey: Keys.targetLanguage) ?? "") ?? .spanish
        self.analyticsEnabled = defaults.object(forKey: Keys.analyticsEnabled) as? Bool ?? false
    }

    // MARK: - Migration

    func migrateFromLegacyConfig() {
        let legacyConfigURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_config.json")

        guard FileManager.default.fileExists(atPath: legacyConfigURL.path),
              let data = try? Data(contentsOf: legacyConfigURL),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return
        }

        if let model = json["whisper_backend"] as? String {
            whisperModel = WhisperModel(rawValue: model) ?? .small
        }
        if let key = json["hotkey"] as? String {
            hotkey = HotkeyOption(rawValue: key) ?? .leftOption
        }
        if let paste = json["auto_paste"] as? Bool {
            autoPaste = paste
        }
        if let grammar = json["fix_grammar"] as? Bool {
            fixGrammar = grammar
        }
        if let audio = json["save_audio"] as? Bool {
            saveAudio = audio
        }

        print("Migrated settings from legacy config")
    }
}

// MARK: - Whisper Model Options

enum WhisperModel: String, CaseIterable, Identifiable {
    case tiny = "tiny"
    case base = "base"
    case small = "small"
    case medium = "medium"
    case large = "large"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .tiny: return "Tiny (fastest)"
        case .base: return "Base"
        case .small: return "Small (recommended)"
        case .medium: return "Medium"
        case .large: return "Large (most accurate)"
        }
    }

    var description: String {
        switch self {
        case .tiny: return "~75MB, fastest but less accurate"
        case .base: return "~150MB, balanced for simple dictation"
        case .small: return "~500MB, good accuracy for most uses"
        case .medium: return "~1.5GB, high accuracy"
        case .large: return "~3GB, best accuracy, slowest"
        }
    }
}

// MARK: - Hotkey Options

enum HotkeyOption: String, CaseIterable, Identifiable {
    case leftOption = "alt_l"
    case rightOption = "alt_r"
    case leftControl = "ctrl_l"
    case rightControl = "ctrl_r"
    case capsLock = "caps_lock"
    case fn = "fn"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .leftOption: return "Left Option (⌥)"
        case .rightOption: return "Right Option (⌥)"
        case .leftControl: return "Left Control (⌃)"
        case .rightControl: return "Right Control (⌃)"
        case .capsLock: return "Caps Lock (⇪)"
        case .fn: return "Fn"
        }
    }

    var symbol: String {
        switch self {
        case .leftOption, .rightOption: return "⌥"
        case .leftControl, .rightControl: return "⌃"
        case .capsLock: return "⇪"
        case .fn: return "fn"
        }
    }
}
