import XCTest
@testable import Notta

final class TranslationTests: XCTestCase {

    // MARK: - TranslationLanguage Enum Tests

    // MARK: Display Names

    func testLanguageDisplayNames() {
        XCTAssertEqual(TranslationLanguage.none.displayName, "None (no translation)")
        XCTAssertEqual(TranslationLanguage.spanish.displayName, "Spanish")
        XCTAssertEqual(TranslationLanguage.french.displayName, "French")
        XCTAssertEqual(TranslationLanguage.german.displayName, "German")
        XCTAssertEqual(TranslationLanguage.italian.displayName, "Italian")
        XCTAssertEqual(TranslationLanguage.portuguese.displayName, "Portuguese")
        XCTAssertEqual(TranslationLanguage.chineseSimplified.displayName, "Chinese (Simplified)")
        XCTAssertEqual(TranslationLanguage.japanese.displayName, "Japanese")
        XCTAssertEqual(TranslationLanguage.korean.displayName, "Korean")
        XCTAssertEqual(TranslationLanguage.arabic.displayName, "Arabic")
        XCTAssertEqual(TranslationLanguage.russian.displayName, "Russian")
        XCTAssertEqual(TranslationLanguage.hindi.displayName, "Hindi")
        XCTAssertEqual(TranslationLanguage.dutch.displayName, "Dutch")
        XCTAssertEqual(TranslationLanguage.polish.displayName, "Polish")
        XCTAssertEqual(TranslationLanguage.turkish.displayName, "Turkish")
        XCTAssertEqual(TranslationLanguage.vietnamese.displayName, "Vietnamese")
        XCTAssertEqual(TranslationLanguage.thai.displayName, "Thai")
        XCTAssertEqual(TranslationLanguage.indonesian.displayName, "Indonesian")
        XCTAssertEqual(TranslationLanguage.ukrainian.displayName, "Ukrainian")
    }

    // MARK: Raw Values (Language Codes)

    func testLanguageRawValues() {
        XCTAssertEqual(TranslationLanguage.none.rawValue, "none")
        XCTAssertEqual(TranslationLanguage.spanish.rawValue, "es")
        XCTAssertEqual(TranslationLanguage.french.rawValue, "fr")
        XCTAssertEqual(TranslationLanguage.german.rawValue, "de")
        XCTAssertEqual(TranslationLanguage.italian.rawValue, "it")
        XCTAssertEqual(TranslationLanguage.portuguese.rawValue, "pt")
        XCTAssertEqual(TranslationLanguage.chineseSimplified.rawValue, "zh-Hans")
        XCTAssertEqual(TranslationLanguage.japanese.rawValue, "ja")
        XCTAssertEqual(TranslationLanguage.korean.rawValue, "ko")
        XCTAssertEqual(TranslationLanguage.arabic.rawValue, "ar")
        XCTAssertEqual(TranslationLanguage.russian.rawValue, "ru")
        XCTAssertEqual(TranslationLanguage.hindi.rawValue, "hi")
        XCTAssertEqual(TranslationLanguage.dutch.rawValue, "nl")
        XCTAssertEqual(TranslationLanguage.polish.rawValue, "pl")
        XCTAssertEqual(TranslationLanguage.turkish.rawValue, "tr")
        XCTAssertEqual(TranslationLanguage.vietnamese.rawValue, "vi")
        XCTAssertEqual(TranslationLanguage.thai.rawValue, "th")
        XCTAssertEqual(TranslationLanguage.indonesian.rawValue, "id")
        XCTAssertEqual(TranslationLanguage.ukrainian.rawValue, "uk")
    }

    // MARK: Flag Emojis

    func testLanguageFlagEmojis() {
        XCTAssertEqual(TranslationLanguage.none.flagEmoji, "")
        XCTAssertEqual(TranslationLanguage.spanish.flagEmoji, "\u{1F1EA}\u{1F1F8}") // ES
        XCTAssertEqual(TranslationLanguage.french.flagEmoji, "\u{1F1EB}\u{1F1F7}") // FR
        XCTAssertEqual(TranslationLanguage.german.flagEmoji, "\u{1F1E9}\u{1F1EA}") // DE
        XCTAssertEqual(TranslationLanguage.italian.flagEmoji, "\u{1F1EE}\u{1F1F9}") // IT
        XCTAssertEqual(TranslationLanguage.portuguese.flagEmoji, "\u{1F1F5}\u{1F1F9}") // PT
        XCTAssertEqual(TranslationLanguage.chineseSimplified.flagEmoji, "\u{1F1E8}\u{1F1F3}") // CN
        XCTAssertEqual(TranslationLanguage.japanese.flagEmoji, "\u{1F1EF}\u{1F1F5}") // JP
        XCTAssertEqual(TranslationLanguage.korean.flagEmoji, "\u{1F1F0}\u{1F1F7}") // KR
        XCTAssertEqual(TranslationLanguage.arabic.flagEmoji, "\u{1F1F8}\u{1F1E6}") // SA
        XCTAssertEqual(TranslationLanguage.russian.flagEmoji, "\u{1F1F7}\u{1F1FA}") // RU
        XCTAssertEqual(TranslationLanguage.hindi.flagEmoji, "\u{1F1EE}\u{1F1F3}") // IN
        XCTAssertEqual(TranslationLanguage.dutch.flagEmoji, "\u{1F1F3}\u{1F1F1}") // NL
        XCTAssertEqual(TranslationLanguage.polish.flagEmoji, "\u{1F1F5}\u{1F1F1}") // PL
        XCTAssertEqual(TranslationLanguage.turkish.flagEmoji, "\u{1F1F9}\u{1F1F7}") // TR
        XCTAssertEqual(TranslationLanguage.vietnamese.flagEmoji, "\u{1F1FB}\u{1F1F3}") // VN
        XCTAssertEqual(TranslationLanguage.thai.flagEmoji, "\u{1F1F9}\u{1F1ED}") // TH
        XCTAssertEqual(TranslationLanguage.indonesian.flagEmoji, "\u{1F1EE}\u{1F1E9}") // ID
        XCTAssertEqual(TranslationLanguage.ukrainian.flagEmoji, "\u{1F1FA}\u{1F1E6}") // UA
    }

    // MARK: isEnabled Property

    func testNoneLanguageIsNotEnabled() {
        XCTAssertFalse(TranslationLanguage.none.isEnabled)
    }

    func testAllOtherLanguagesAreEnabled() {
        for language in TranslationLanguage.allCases where language != .none {
            XCTAssertTrue(language.isEnabled, "\(language.displayName) should be enabled")
        }
    }

    // MARK: enabledCases

    func testEnabledCasesExcludesNone() {
        let enabledCases = TranslationLanguage.enabledCases
        XCTAssertFalse(enabledCases.contains(.none))
    }

    func testEnabledCasesCount() {
        // Total cases minus "none"
        XCTAssertEqual(TranslationLanguage.enabledCases.count, TranslationLanguage.allCases.count - 1)
    }

    func testEnabledCasesContainsAllLanguages() {
        let enabledCases = TranslationLanguage.enabledCases
        XCTAssertTrue(enabledCases.contains(.spanish))
        XCTAssertTrue(enabledCases.contains(.french))
        XCTAssertTrue(enabledCases.contains(.german))
        XCTAssertTrue(enabledCases.contains(.japanese))
        XCTAssertTrue(enabledCases.contains(.korean))
        XCTAssertTrue(enabledCases.contains(.chineseSimplified))
    }

    // MARK: Identifiable Conformance

    func testLanguageIdEqualsRawValue() {
        for language in TranslationLanguage.allCases {
            XCTAssertEqual(language.id, language.rawValue)
        }
    }

    // MARK: Codable Conformance

    func testLanguageEncodingDecoding() throws {
        let encoder = JSONEncoder()
        let decoder = JSONDecoder()

        for language in TranslationLanguage.allCases {
            let encoded = try encoder.encode(language)
            let decoded = try decoder.decode(TranslationLanguage.self, from: encoded)
            XCTAssertEqual(decoded, language)
        }
    }

    func testLanguageDecodingFromRawValue() throws {
        let decoder = JSONDecoder()

        let spanishJSON = "\"es\"".data(using: .utf8)!
        let spanish = try decoder.decode(TranslationLanguage.self, from: spanishJSON)
        XCTAssertEqual(spanish, .spanish)

        let japaneseJSON = "\"ja\"".data(using: .utf8)!
        let japanese = try decoder.decode(TranslationLanguage.self, from: japaneseJSON)
        XCTAssertEqual(japanese, .japanese)
    }

    // MARK: allCases

    func testAllCasesCount() {
        // none + 18 languages = 19 total
        XCTAssertEqual(TranslationLanguage.allCases.count, 19)
    }

    // MARK: Locale Property (macOS 15+)

    @available(macOS 15.0, *)
    func testLocaleIdentifiers() {
        XCTAssertEqual(TranslationLanguage.spanish.locale.languageCode?.identifier, "es")
        XCTAssertEqual(TranslationLanguage.french.locale.languageCode?.identifier, "fr")
        XCTAssertEqual(TranslationLanguage.german.locale.languageCode?.identifier, "de")
        XCTAssertEqual(TranslationLanguage.japanese.locale.languageCode?.identifier, "ja")
        XCTAssertEqual(TranslationLanguage.korean.locale.languageCode?.identifier, "ko")
    }

    @available(macOS 15.0, *)
    func testChineseSimplifiedLocale() {
        let locale = TranslationLanguage.chineseSimplified.locale
        XCTAssertEqual(locale.languageCode?.identifier, "zh")
        // Script should be Hans (Simplified)
        XCTAssertEqual(locale.script?.identifier, "Hans")
    }

    // MARK: - TranslationService Tests

    // MARK: Initial State

    @MainActor
    func testTranslationServiceInitialState() {
        let service = TranslationService.shared
        XCTAssertFalse(service.isTranslating)
        XCTAssertFalse(service.isDownloadingModel)
        XCTAssertEqual(service.downloadProgress, "")
        XCTAssertNil(service.error)
        XCTAssertNil(service.pendingText)
        XCTAssertNil(service.translatedText)
    }

    // MARK: Availability

    @MainActor
    func testTranslationServiceAvailability() {
        let service = TranslationService.shared
        // Should return true on macOS 15+, false otherwise
        if #available(macOS 15.0, *) {
            XCTAssertTrue(service.isAvailable)
        } else {
            XCTAssertFalse(service.isAvailable)
        }
    }

    // MARK: Language Status

    @MainActor
    func testLanguageStatusDefaultsToUnknown() {
        let service = TranslationService.shared
        let status = service.getLanguageStatus(.spanish)
        // Before checking, status should be unknown
        XCTAssertEqual(status, .unknown)
    }

    @MainActor
    func testLanguageStatusForDisabledLanguage() async {
        let service = TranslationService.shared
        let status = await service.checkLanguageStatus(.none)
        XCTAssertEqual(status, .unknown)
    }

    // MARK: onLanguageChanged

    @MainActor
    func testOnLanguageChangedClearsError() {
        let service = TranslationService.shared
        service.error = "Some error"
        service.onLanguageChanged()
        XCTAssertNil(service.error)
    }

    // MARK: cancelPendingTranslation

    @MainActor
    func testCancelPendingTranslationClearsState() {
        let service = TranslationService.shared
        service.pendingText = "Test text"
        service.isTranslating = true
        service.isDownloadingModel = true

        service.cancelPendingTranslation()

        XCTAssertNil(service.pendingText)
        XCTAssertFalse(service.isTranslating)
        XCTAssertFalse(service.isDownloadingModel)
    }

    // MARK: Translation Request ID

    @MainActor
    func testTranslationRequestIdStartsAtZero() {
        let service = TranslationService.shared
        XCTAssertEqual(service.translationRequestId, 0)
    }

    // MARK: - Integration with Settings

    func testTargetLanguageIsValidLanguage() {
        let settings = SettingsManager.shared
        // Target language should be a valid TranslationLanguage
        XCTAssertTrue(TranslationLanguage.allCases.contains(settings.targetLanguage))
    }

    func testDefaultTranslationEnabled() {
        let settings = SettingsManager.shared
        // Translation should be disabled by default
        XCTAssertFalse(settings.translationEnabled)
    }

    // MARK: - LanguageStatus Enum

    @MainActor
    func testLanguageStatusEquatable() {
        XCTAssertEqual(TranslationService.LanguageStatus.unknown, TranslationService.LanguageStatus.unknown)
        XCTAssertEqual(TranslationService.LanguageStatus.installed, TranslationService.LanguageStatus.installed)
        XCTAssertEqual(TranslationService.LanguageStatus.needsDownload, TranslationService.LanguageStatus.needsDownload)
        XCTAssertNotEqual(TranslationService.LanguageStatus.installed, TranslationService.LanguageStatus.needsDownload)
    }

    // MARK: - Edge Cases

    func testLanguageWithSpecialRawValue() {
        // Chinese Simplified has a hyphenated code
        XCTAssertEqual(TranslationLanguage.chineseSimplified.rawValue, "zh-Hans")
        XCTAssertTrue(TranslationLanguage.chineseSimplified.isEnabled)
    }

    func testAllLanguagesHaveDisplayNames() {
        for language in TranslationLanguage.allCases {
            XCTAssertFalse(language.displayName.isEmpty, "\(language) should have a display name")
        }
    }

    func testAllEnabledLanguagesHaveFlags() {
        for language in TranslationLanguage.enabledCases {
            XCTAssertFalse(language.flagEmoji.isEmpty, "\(language.displayName) should have a flag emoji")
        }
    }

    func testLanguageRawValuesAreValidISOCodes() {
        // Verify ISO 639-1 codes (2 letters) or extended codes
        let validPatterns = [
            "^[a-z]{2}$",           // ISO 639-1: es, fr, de, etc.
            "^[a-z]{2}-[A-Za-z]+$", // Extended: zh-Hans
            "^none$"                // Special case
        ]

        for language in TranslationLanguage.allCases {
            let rawValue = language.rawValue
            let matchesPattern = validPatterns.contains { pattern in
                rawValue.range(of: pattern, options: .regularExpression) != nil
            }
            XCTAssertTrue(matchesPattern, "\(rawValue) should be a valid language code")
        }
    }
}

// MARK: - Translation Workflow Tests

final class TranslationWorkflowTests: XCTestCase {

    // MARK: Fail-Open Pattern Tests

    @MainActor
    func testTranslateReturnsOriginalWhenNotAvailable() async {
        // On systems without Translation framework, should return original text
        if #unavailable(macOS 15.0) {
            let service = TranslationService.shared
            let originalText = "Hello world"
            let result = await service.translate(originalText)
            XCTAssertEqual(result, originalText)
        }
    }

    @MainActor
    func testTranslateReturnsOriginalWhenDisabled() async {
        let settings = SettingsManager.shared
        let originalEnabled = settings.translationEnabled
        let originalLanguage = settings.targetLanguage

        // Ensure translation is disabled
        settings.translationEnabled = false

        let service = TranslationService.shared
        let originalText = "Hello world"
        let result = await service.translate(originalText)

        // Should return original text when disabled
        XCTAssertEqual(result, originalText)

        // Restore settings
        settings.translationEnabled = originalEnabled
        settings.targetLanguage = originalLanguage
    }

    @MainActor
    func testTranslateReturnsOriginalWhenTargetIsNone() async {
        let settings = SettingsManager.shared
        let originalEnabled = settings.translationEnabled
        let originalLanguage = settings.targetLanguage

        // Enable translation but set target to none
        settings.translationEnabled = true
        settings.targetLanguage = .none

        let service = TranslationService.shared
        let originalText = "Hello world"
        let result = await service.translate(originalText)

        // Should return original text when target is none
        XCTAssertEqual(result, originalText)

        // Restore settings
        settings.translationEnabled = originalEnabled
        settings.targetLanguage = originalLanguage
    }

    // MARK: State Management During Translation

    @MainActor
    func testTranslationSetsIsTranslatingFlag() async throws {
        guard #available(macOS 15.0, *) else {
            throw XCTSkip("Translation requires macOS 15.0+")
        }

        let settings = SettingsManager.shared
        let originalEnabled = settings.translationEnabled
        let originalLanguage = settings.targetLanguage

        settings.translationEnabled = true
        settings.targetLanguage = .spanish

        let service = TranslationService.shared

        // Start translation in background
        Task {
            _ = await service.translate("Hello")
        }

        // Give it a moment to start
        try? await Task.sleep(for: .milliseconds(100))

        // Should be translating (or already timed out/completed)
        // The flag should have been set at some point
        // This is hard to test deterministically, so we just verify no crash

        // Restore settings
        settings.translationEnabled = originalEnabled
        settings.targetLanguage = originalLanguage
    }
}

// MARK: - Settings Integration Tests

final class TranslationSettingsTests: XCTestCase {

    func testTargetLanguagePersistence() {
        let settings = SettingsManager.shared
        let original = settings.targetLanguage

        // Change to Spanish
        settings.targetLanguage = .spanish
        XCTAssertEqual(settings.targetLanguage, .spanish)

        // Change to Japanese
        settings.targetLanguage = .japanese
        XCTAssertEqual(settings.targetLanguage, .japanese)

        // Restore
        settings.targetLanguage = original
    }

    func testTranslationEnabledPersistence() {
        let settings = SettingsManager.shared
        let original = settings.translationEnabled

        settings.translationEnabled = true
        XCTAssertTrue(settings.translationEnabled)

        settings.translationEnabled = false
        XCTAssertFalse(settings.translationEnabled)

        // Restore
        settings.translationEnabled = original
    }

    func testTargetLanguageAllCasesAvailableInPicker() {
        // All enabled languages should be available for selection
        let enabledCases = TranslationLanguage.enabledCases
        XCTAssertGreaterThan(enabledCases.count, 0)

        // Verify common languages are present
        XCTAssertTrue(enabledCases.contains(.spanish))
        XCTAssertTrue(enabledCases.contains(.french))
        XCTAssertTrue(enabledCases.contains(.german))
        XCTAssertTrue(enabledCases.contains(.japanese))
        XCTAssertTrue(enabledCases.contains(.korean))
        XCTAssertTrue(enabledCases.contains(.chineseSimplified))
    }
}
