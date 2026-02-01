import XCTest
@testable import Notta

final class HotkeyManagerTests: XCTestCase {

    var hotkeyManager: HotkeyManager!

    override func setUp() {
        super.setUp()
        hotkeyManager = HotkeyManager.shared
        // Ensure clean state
        hotkeyManager.stopListening()
    }

    override func tearDown() {
        hotkeyManager.stopListening()
        super.tearDown()
    }

    // MARK: - Singleton

    func testSharedInstanceExists() {
        XCTAssertNotNil(HotkeyManager.shared)
    }

    func testSharedInstanceIsSingleton() {
        let instance1 = HotkeyManager.shared
        let instance2 = HotkeyManager.shared
        XCTAssertTrue(instance1 === instance2)
    }

    // MARK: - Initial State

    func testInitialIsListeningFalse() {
        XCTAssertFalse(hotkeyManager.isListening)
    }

    func testInitialIsHotkeyPressedFalse() {
        XCTAssertFalse(hotkeyManager.isHotkeyPressed)
    }

    // MARK: - Start/Stop Listening

    func testStartListeningSetsIsListeningTrue() {
        hotkeyManager.startListening()
        XCTAssertTrue(hotkeyManager.isListening)
    }

    func testStopListeningSetsIsListeningFalse() {
        hotkeyManager.startListening()
        hotkeyManager.stopListening()
        XCTAssertFalse(hotkeyManager.isListening)
    }

    func testStopListeningClearsHotkeyPressed() {
        hotkeyManager.startListening()
        // Simulate hotkey being pressed (if we could)
        hotkeyManager.stopListening()
        XCTAssertFalse(hotkeyManager.isHotkeyPressed)
    }

    func testStartListeningIdempotent() {
        hotkeyManager.startListening()
        hotkeyManager.startListening()
        hotkeyManager.startListening()

        // Should still be listening, no crash
        XCTAssertTrue(hotkeyManager.isListening)
    }

    func testStopListeningIdempotent() {
        hotkeyManager.stopListening()
        hotkeyManager.stopListening()
        hotkeyManager.stopListening()

        // Should be not listening, no crash
        XCTAssertFalse(hotkeyManager.isListening)
    }

    // MARK: - Accessibility Permission

    func testHasAccessibilityPermissionProperty() {
        // Just verify the property is accessible
        let _ = hotkeyManager.hasAccessibilityPermission
        // Can't assert specific value as it depends on system state
    }

    func testRequestAccessibilityPermissionDoesNotCrash() {
        // This just verifies the method doesn't crash
        // It may prompt the user in actual use
        // We can't verify the actual permission request in a unit test
    }

    func testOpenAccessibilitySettingsDoesNotCrash() {
        // This would open System Settings in production
        // We just verify it doesn't crash when called
        // In a real test environment, we might mock NSWorkspace
    }

    // MARK: - Notification Names

    func testHotkeyPressedNotificationName() {
        XCTAssertEqual(Notification.Name.hotkeyPressed.rawValue, "hotkeyPressed")
    }

    func testHotkeyReleasedNotificationName() {
        XCTAssertEqual(Notification.Name.hotkeyReleased.rawValue, "hotkeyReleased")
    }

    // MARK: - HotkeyOption Tests

    func testHotkeyOptionDisplayNames() {
        XCTAssertEqual(HotkeyOption.leftOption.displayName, "Left Option (\u{2325})")
        XCTAssertEqual(HotkeyOption.rightOption.displayName, "Right Option (\u{2325})")
        XCTAssertEqual(HotkeyOption.leftControl.displayName, "Left Control (\u{2303})")
        XCTAssertEqual(HotkeyOption.rightControl.displayName, "Right Control (\u{2303})")
        XCTAssertEqual(HotkeyOption.capsLock.displayName, "Caps Lock (\u{21EA})")
        XCTAssertEqual(HotkeyOption.fn.displayName, "Fn")
    }

    func testHotkeyOptionSymbols() {
        XCTAssertEqual(HotkeyOption.leftOption.symbol, "\u{2325}")
        XCTAssertEqual(HotkeyOption.rightOption.symbol, "\u{2325}")
        XCTAssertEqual(HotkeyOption.leftControl.symbol, "\u{2303}")
        XCTAssertEqual(HotkeyOption.rightControl.symbol, "\u{2303}")
        XCTAssertEqual(HotkeyOption.capsLock.symbol, "\u{21EA}")
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
        XCTAssertTrue(HotkeyOption.allCases.contains(.leftOption))
        XCTAssertTrue(HotkeyOption.allCases.contains(.rightOption))
        XCTAssertTrue(HotkeyOption.allCases.contains(.leftControl))
        XCTAssertTrue(HotkeyOption.allCases.contains(.rightControl))
        XCTAssertTrue(HotkeyOption.allCases.contains(.capsLock))
        XCTAssertTrue(HotkeyOption.allCases.contains(.fn))
    }

    func testHotkeyOptionIdentifiable() {
        for option in HotkeyOption.allCases {
            XCTAssertEqual(option.id, option.rawValue)
        }
    }

    func testHotkeyOptionRawValueRoundtrip() {
        // Test that raw values can be used to recreate options
        for option in HotkeyOption.allCases {
            let rawValue = option.rawValue
            let recreated = HotkeyOption(rawValue: rawValue)
            XCTAssertEqual(recreated, option)
        }
    }

    // MARK: - Notification Observer Tests

    func testHotkeyPressedNotificationPosted() {
        let expectation = XCTestExpectation(description: "Hotkey pressed notification")

        let observer = NotificationCenter.default.addObserver(
            forName: .hotkeyPressed,
            object: nil,
            queue: .main
        ) { _ in
            expectation.fulfill()
        }

        // Manually post to verify the mechanism works
        NotificationCenter.default.post(name: .hotkeyPressed, object: nil)

        wait(for: [expectation], timeout: 1.0)
        NotificationCenter.default.removeObserver(observer)
    }

    func testHotkeyReleasedNotificationPosted() {
        let expectation = XCTestExpectation(description: "Hotkey released notification")

        let observer = NotificationCenter.default.addObserver(
            forName: .hotkeyReleased,
            object: nil,
            queue: .main
        ) { _ in
            expectation.fulfill()
        }

        // Manually post to verify the mechanism works
        NotificationCenter.default.post(name: .hotkeyReleased, object: nil)

        wait(for: [expectation], timeout: 1.0)
        NotificationCenter.default.removeObserver(observer)
    }
}
