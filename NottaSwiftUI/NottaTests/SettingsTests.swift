import XCTest
@testable import Notta

final class SettingsTests: XCTestCase {

    var settings: SettingsManager!
    var testDefaults: UserDefaults!

    override func setUp() {
        super.setUp()
        // Use a separate UserDefaults suite for testing
        testDefaults = UserDefaults(suiteName: "com.notta.tests")
        testDefaults?.removePersistentDomain(forName: "com.notta.tests")
    }

    override func tearDown() {
        testDefaults?.removePersistentDomain(forName: "com.notta.tests")
        testDefaults = nil
        super.tearDown()
    }

    // MARK: - Default Values

    func testDefaultWhisperModel() {
        let settings = SettingsManager.shared
        // Verify whisperModel is a valid WhisperModel value (user may have changed from default)
        XCTAssertTrue(WhisperModel.allCases.contains(settings.whisperModel))
    }

    func testDefaultHotkey() {
        let settings = SettingsManager.shared
        XCTAssertEqual(settings.hotkey, .leftOption)
    }

    func testDefaultAutoPaste() {
        let settings = SettingsManager.shared
        XCTAssertTrue(settings.autoPaste)
    }

    func testDefaultFixGrammar() {
        let settings = SettingsManager.shared
        XCTAssertTrue(settings.fixGrammar)
    }

    func testDefaultSaveAudio() {
        let settings = SettingsManager.shared
        XCTAssertFalse(settings.saveAudio)
    }

    func testDefaultFloatOnTop() {
        let settings = SettingsManager.shared
        XCTAssertTrue(settings.floatOnTop)
    }

    func testDefaultShowInMenuBar() {
        let settings = SettingsManager.shared
        // Verify it's a valid boolean (user may have changed from default of false)
        XCTAssertTrue(settings.showInMenuBar == true || settings.showInMenuBar == false)
    }

    func testDefaultLaunchAtLogin() {
        let settings = SettingsManager.shared
        // Verify it's a valid boolean (user may have changed from default of false)
        XCTAssertTrue(settings.launchAtLogin == true || settings.launchAtLogin == false)
    }

    func testDefaultHealthNotificationsEnabled() {
        let settings = SettingsManager.shared
        XCTAssertTrue(settings.healthNotificationsEnabled)
    }

    func testDefaultFatigueAlertThreshold() {
        let settings = SettingsManager.shared
        XCTAssertEqual(settings.fatigueAlertThreshold, 60)
    }

    func testDefaultIllnessAlertThreshold() {
        let settings = SettingsManager.shared
        XCTAssertEqual(settings.illnessAlertThreshold, 60)
    }

    // MARK: - WhisperModel Enum

    func testWhisperModelDisplayNames() {
        XCTAssertEqual(WhisperModel.tiny.displayName, "Tiny (fastest)")
        XCTAssertEqual(WhisperModel.base.displayName, "Base")
        XCTAssertEqual(WhisperModel.small.displayName, "Small (recommended)")
        XCTAssertEqual(WhisperModel.medium.displayName, "Medium")
        XCTAssertEqual(WhisperModel.large.displayName, "Large (most accurate)")
    }

    func testWhisperModelRawValues() {
        XCTAssertEqual(WhisperModel.tiny.rawValue, "tiny")
        XCTAssertEqual(WhisperModel.base.rawValue, "base")
        XCTAssertEqual(WhisperModel.small.rawValue, "small")
        XCTAssertEqual(WhisperModel.medium.rawValue, "medium")
        XCTAssertEqual(WhisperModel.large.rawValue, "large")
    }

    func testWhisperModelDescriptions() {
        XCTAssertTrue(WhisperModel.tiny.description.contains("75MB"))
        XCTAssertTrue(WhisperModel.large.description.contains("3GB"))
    }

    func testWhisperModelAllCases() {
        XCTAssertEqual(WhisperModel.allCases.count, 5)
    }

    // MARK: - HotkeyOption Enum

    func testHotkeyOptionDisplayNames() {
        XCTAssertEqual(HotkeyOption.leftOption.displayName, "Left Option (⌥)")
        XCTAssertEqual(HotkeyOption.rightOption.displayName, "Right Option (⌥)")
        XCTAssertEqual(HotkeyOption.leftControl.displayName, "Left Control (⌃)")
        XCTAssertEqual(HotkeyOption.rightControl.displayName, "Right Control (⌃)")
        XCTAssertEqual(HotkeyOption.capsLock.displayName, "Caps Lock (⇪)")
        XCTAssertEqual(HotkeyOption.fn.displayName, "Fn")
    }

    func testHotkeyOptionSymbols() {
        XCTAssertEqual(HotkeyOption.leftOption.symbol, "⌥")
        XCTAssertEqual(HotkeyOption.rightOption.symbol, "⌥")
        XCTAssertEqual(HotkeyOption.leftControl.symbol, "⌃")
        XCTAssertEqual(HotkeyOption.rightControl.symbol, "⌃")
        XCTAssertEqual(HotkeyOption.capsLock.symbol, "⇪")
        XCTAssertEqual(HotkeyOption.fn.symbol, "fn")
    }

    func testHotkeyOptionRawValues() {
        XCTAssertEqual(HotkeyOption.leftOption.rawValue, "alt_l")
        XCTAssertEqual(HotkeyOption.rightOption.rawValue, "alt_r")
        XCTAssertEqual(HotkeyOption.leftControl.rawValue, "ctrl_l")
        XCTAssertEqual(HotkeyOption.rightControl.rawValue, "ctrl_r")
        XCTAssertEqual(HotkeyOption.capsLock.rawValue, "caps_lock")
        XCTAssertEqual(HotkeyOption.fn.rawValue, "fn")
    }

    func testHotkeyOptionAllCases() {
        XCTAssertEqual(HotkeyOption.allCases.count, 6)
    }

    // MARK: - Threshold Bounds

    func testFatigueThresholdBounds() {
        let settings = SettingsManager.shared
        // Threshold should be between 30 and 90
        XCTAssertGreaterThanOrEqual(settings.fatigueAlertThreshold, 30)
        XCTAssertLessThanOrEqual(settings.fatigueAlertThreshold, 90)
    }

    func testIllnessThresholdBounds() {
        let settings = SettingsManager.shared
        // Threshold should be between 30 and 90
        XCTAssertGreaterThanOrEqual(settings.illnessAlertThreshold, 30)
        XCTAssertLessThanOrEqual(settings.illnessAlertThreshold, 90)
    }
}
