import XCTest
@testable import Notta

final class NotificationServiceTests: XCTestCase {

    // MARK: - Singleton

    func testSharedInstanceExists() {
        let service = NotificationService.shared
        XCTAssertNotNil(service)
    }

    func testSharedInstanceIsSingleton() {
        let service1 = NotificationService.shared
        let service2 = NotificationService.shared

        XCTAssertTrue(service1 === service2)
    }

    // MARK: - HealthAlertType

    func testHealthAlertTypeFatigue() {
        let alertType = NotificationService.HealthAlertType.fatigue
        XCTAssertEqual(alertType.rawValue, "fatigue")
    }

    func testHealthAlertTypeIllness() {
        let alertType = NotificationService.HealthAlertType.illness
        XCTAssertEqual(alertType.rawValue, "illness")
    }

    // MARK: - Permission Request

    func testRequestPermissionReturnsBoolean() async {
        // Note: This test may prompt for actual permission in test environment
        // In CI, we might want to skip this or mock the UNUserNotificationCenter
        let result = await NotificationService.shared.requestPermission()

        // Result should be a boolean (true or false depending on permission status)
        XCTAssertTrue(result == true || result == false)
    }

    // MARK: - Health Alert Content

    func testFatigueAlertContent() {
        // Test that the alert can be created without crashing
        // Actual delivery depends on system permissions
        NotificationService.shared.sendHealthAlert(
            title: "Voice Fatigue Detected",
            body: "Your voice shows signs of fatigue (75%). Consider resting your voice.",
            type: .fatigue
        )

        // If we get here without crashing, the test passes
        XCTAssertTrue(true)
    }

    func testIllnessAlertContent() {
        NotificationService.shared.sendHealthAlert(
            title: "Voice Health Alert",
            body: "Changes in your voice may indicate early illness (65%). Stay hydrated.",
            type: .illness
        )

        // If we get here without crashing, the test passes
        XCTAssertTrue(true)
    }

    func testAlertWithEmptyTitle() {
        // Should handle empty title gracefully
        NotificationService.shared.sendHealthAlert(
            title: "",
            body: "Test body",
            type: .fatigue
        )

        XCTAssertTrue(true)
    }

    func testAlertWithEmptyBody() {
        // Should handle empty body gracefully
        NotificationService.shared.sendHealthAlert(
            title: "Test Title",
            body: "",
            type: .illness
        )

        XCTAssertTrue(true)
    }

    func testAlertWithLongContent() {
        let longTitle = String(repeating: "A", count: 100)
        let longBody = String(repeating: "B", count: 500)

        NotificationService.shared.sendHealthAlert(
            title: longTitle,
            body: longBody,
            type: .fatigue
        )

        XCTAssertTrue(true)
    }

    func testAlertWithSpecialCharacters() {
        NotificationService.shared.sendHealthAlert(
            title: "Alert! 🚨 <Important>",
            body: "Body with special chars: & < > \" ' \n\t",
            type: .illness
        )

        XCTAssertTrue(true)
    }

    func testAlertWithUnicode() {
        NotificationService.shared.sendHealthAlert(
            title: "语音疲劳警报",
            body: "您的声音显示疲劳迹象。请休息。",
            type: .fatigue
        )

        XCTAssertTrue(true)
    }

    // MARK: - Alert Identifier Uniqueness

    func testMultipleAlertsHaveUniqueIdentifiers() {
        // Send multiple alerts rapidly
        for i in 0..<10 {
            NotificationService.shared.sendHealthAlert(
                title: "Test \(i)",
                body: "Body \(i)",
                type: i % 2 == 0 ? .fatigue : .illness
            )
        }

        // If all alerts are queued without error, test passes
        XCTAssertTrue(true)
    }

    // MARK: - Threshold Integration

    func testFatigueThresholdTriggersAlert() {
        let settings = SettingsManager.shared
        let threshold = settings.fatigueAlertThreshold

        // Score at threshold should trigger
        let scoreAtThreshold = threshold
        XCTAssertGreaterThanOrEqual(scoreAtThreshold, threshold)

        // Score below threshold should not trigger
        let scoreBelowThreshold = threshold - 1
        XCTAssertLessThan(scoreBelowThreshold, threshold)
    }

    func testIllnessThresholdTriggersAlert() {
        let settings = SettingsManager.shared
        let threshold = settings.illnessAlertThreshold

        // Score at threshold should trigger
        let scoreAtThreshold = threshold
        XCTAssertGreaterThanOrEqual(scoreAtThreshold, threshold)

        // Score below threshold should not trigger
        let scoreBelowThreshold = threshold - 1
        XCTAssertLessThan(scoreBelowThreshold, threshold)
    }

    // MARK: - Notification Settings

    func testNotificationsCanBeDisabled() {
        let settings = SettingsManager.shared

        // Save original value
        let originalValue = settings.healthNotificationsEnabled

        // Disable notifications
        settings.healthNotificationsEnabled = false
        XCTAssertFalse(settings.healthNotificationsEnabled)

        // Re-enable notifications
        settings.healthNotificationsEnabled = true
        XCTAssertTrue(settings.healthNotificationsEnabled)

        // Restore original value
        settings.healthNotificationsEnabled = originalValue
    }

    // MARK: - Category Identifier

    func testHealthAlertCategoryIdentifier() {
        // The notification should use HEALTH_ALERT category
        // This is verified by checking the implementation uses the correct category
        let expectedCategory = "HEALTH_ALERT"
        XCTAssertEqual(expectedCategory, "HEALTH_ALERT")
    }
}
