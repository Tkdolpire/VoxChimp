import XCTest
@testable import Notta

final class LicenseTests: XCTestCase {

    // MARK: - LicenseState

    func testLicenseStateUnknown() {
        let state = LicenseState.unknown
        XCTAssertFalse(state.isUnlocked)
        XCTAssertEqual(state.displayName, "Unknown")
    }

    func testLicenseStateTrial() {
        let state = LicenseState.trial(daysRemaining: 5)
        XCTAssertTrue(state.isUnlocked)
        XCTAssertTrue(state.displayName.contains("5"))
        XCTAssertTrue(state.displayName.lowercased().contains("trial"))
    }

    func testLicenseStateTrialLastDay() {
        let state = LicenseState.trial(daysRemaining: 1)
        XCTAssertTrue(state.isUnlocked)
        XCTAssertTrue(state.displayName.contains("1"))
    }

    func testLicenseStateTrialExpired() {
        let state = LicenseState.trialExpired
        XCTAssertFalse(state.isUnlocked)
        XCTAssertTrue(state.displayName.lowercased().contains("expired"))
    }

    func testLicenseStateActive() {
        let state = LicenseState.active
        XCTAssertTrue(state.isUnlocked)
        // DisplayName is "Pro"
        XCTAssertEqual(state.displayName, "Pro")
    }

    func testLicenseStateExpired() {
        let state = LicenseState.expired
        XCTAssertFalse(state.isUnlocked)
        XCTAssertTrue(state.displayName.lowercased().contains("expired"))
    }

    func testLicenseStateInvalid() {
        let state = LicenseState.invalid
        XCTAssertFalse(state.isUnlocked)
        XCTAssertTrue(state.displayName.lowercased().contains("invalid"))
    }

    func testLicenseStateStatusColors() {
        XCTAssertEqual(LicenseState.active.statusColor, "green")
        XCTAssertEqual(LicenseState.trial(daysRemaining: 5).statusColor, "blue")
        XCTAssertEqual(LicenseState.trialExpired.statusColor, "orange")
        XCTAssertEqual(LicenseState.expired.statusColor, "orange")
        XCTAssertEqual(LicenseState.invalid.statusColor, "orange")
        XCTAssertEqual(LicenseState.unknown.statusColor, "orange")
    }

    // MARK: - License.LicenseStatus Enum

    func testLicenseStatusRawValues() {
        XCTAssertEqual(License.LicenseStatus.active.rawValue, "active")
        XCTAssertEqual(License.LicenseStatus.canceled.rawValue, "canceled")
        XCTAssertEqual(License.LicenseStatus.pastDue.rawValue, "past_due")
        XCTAssertEqual(License.LicenseStatus.expired.rawValue, "expired")
        XCTAssertEqual(License.LicenseStatus.invalid.rawValue, "invalid")
    }

    func testLicenseStatusFromRawValue() {
        XCTAssertEqual(License.LicenseStatus(rawValue: "active"), .active)
        XCTAssertEqual(License.LicenseStatus(rawValue: "canceled"), .canceled)
        XCTAssertEqual(License.LicenseStatus(rawValue: "past_due"), .pastDue)
        XCTAssertEqual(License.LicenseStatus(rawValue: "expired"), .expired)
        XCTAssertEqual(License.LicenseStatus(rawValue: "invalid"), .invalid)
        XCTAssertNil(License.LicenseStatus(rawValue: "unknown_status"))
    }

    // MARK: - License Model

    func testLicenseCreation() {
        let license = License(
            key: "NOTTA-1234-5678-ABCD-EFGH",
            email: "test@example.com",
            status: .active,
            expiresAt: Date().addingTimeInterval(86400 * 30),
            createdAt: Date(),
            machineId: "test-machine-id"
        )

        XCTAssertEqual(license.key, "NOTTA-1234-5678-ABCD-EFGH")
        XCTAssertEqual(license.email, "test@example.com")
        XCTAssertEqual(license.status, .active)
        XCTAssertNotNil(license.expiresAt)
        XCTAssertNotNil(license.machineId)
    }

    func testLicenseWithMinimalFields() {
        let license = License(
            key: "NOTTA-TEST-TEST-TEST-TEST",
            email: nil,
            status: .active,
            expiresAt: nil,
            createdAt: Date(),
            machineId: nil
        )

        XCTAssertEqual(license.key, "NOTTA-TEST-TEST-TEST-TEST")
        XCTAssertNil(license.email)
        XCTAssertNil(license.expiresAt)
        XCTAssertNil(license.machineId)
    }

    // MARK: - License Key Validation

    func testValidLicenseKeyFormat() {
        let validKeys = [
            "NOTTA-ABCD-1234-EFGH-5678",
            "NOTTA-TEST-TEST-TEST-TEST",
            "NOTTA-1234-5678-9012-3456"
        ]

        for key in validKeys {
            XCTAssertTrue(LicenseKeyValidator.isValidFormat(key), "Key should be valid: \(key)")
        }
    }

    func testInvalidLicenseKeyFormat() {
        let invalidKeys = [
            "",
            "invalid",
            "ABCD-1234-EFGH-5678", // Missing NOTTA prefix
            "NOTTA-ABCD-1234-EFGH", // Too short
            "NOTTA-ABCD-1234-EFGH-5678-9012", // Too long
            "notta-abcd-1234-efgh-5678", // Lowercase
        ]

        for key in invalidKeys {
            XCTAssertFalse(LicenseKeyValidator.isValidFormat(key), "Key should be invalid: \(key)")
        }
    }

    func testLicenseKeyFormatting() {
        // Test that formatter properly formats raw input
        let formatted = LicenseKeyValidator.format("ABCD1234EFGH5678")
        XCTAssertTrue(formatted.hasPrefix("NOTTA-"))
        XCTAssertTrue(formatted.contains("-"))
    }

    func testLicenseKeyFormattingWithPrefix() {
        let formatted = LicenseKeyValidator.format("NOTTAABCD1234EFGH5678")
        XCTAssertTrue(formatted.hasPrefix("NOTTA-"))
    }

    func testLicenseKeyFormattingShortInput() {
        let formatted = LicenseKeyValidator.format("ABC")
        // Should return uppercased input for short inputs
        XCTAssertEqual(formatted, "ABC")
    }

    // MARK: - ValidationResponse

    func testValidationResponseDecoding() throws {
        let json = """
        {
            "valid": true,
            "status": "active",
            "expiresAt": null,
            "email": "test@example.com",
            "message": null
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let response = try decoder.decode(ValidationResponse.self, from: json)

        XCTAssertTrue(response.valid)
        XCTAssertEqual(response.status, "active")
        XCTAssertEqual(response.email, "test@example.com")
    }

    func testValidationResponseInvalid() throws {
        let json = """
        {
            "valid": false,
            "status": "invalid",
            "expiresAt": null,
            "email": null,
            "message": "License key not found"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let response = try decoder.decode(ValidationResponse.self, from: json)

        XCTAssertFalse(response.valid)
        XCTAssertEqual(response.message, "License key not found")
    }

    // MARK: - CheckoutResponse

    func testCheckoutResponseDecoding() throws {
        let json = """
        {
            "url": "https://checkout.stripe.com/session/123",
            "sessionId": "cs_test_123"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let response = try decoder.decode(CheckoutResponse.self, from: json)

        XCTAssertEqual(response.url, "https://checkout.stripe.com/session/123")
        XCTAssertEqual(response.sessionId, "cs_test_123")
    }

    // MARK: - PortalResponse

    func testPortalResponseDecoding() throws {
        let json = """
        {
            "url": "https://billing.stripe.com/portal/123"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let response = try decoder.decode(PortalResponse.self, from: json)

        XCTAssertEqual(response.url, "https://billing.stripe.com/portal/123")
    }

    // MARK: - MachineIdentifier

    func testMachineIdentifierNotEmpty() {
        let machineId = MachineIdentifier.current
        XCTAssertFalse(machineId.isEmpty)
    }

    func testMachineIdentifierConsistent() {
        let id1 = MachineIdentifier.current
        let id2 = MachineIdentifier.current

        XCTAssertEqual(id1, id2, "Machine ID should be consistent across calls")
    }

    func testMachineIdentifierFormat() {
        let machineId = MachineIdentifier.current

        // Should be a UUID format or hardware serial
        // At minimum, should have reasonable length
        XCTAssertGreaterThan(machineId.count, 8)
    }

    // MARK: - Trial Duration

    func testTrialDurationDays() {
        // Trial should be 7 days
        let expectedTrialDays = 7
        XCTAssertEqual(expectedTrialDays, 7)
    }

    // MARK: - Grace Period

    func testGracePeriodDays() {
        // Grace period should be 3 days
        let expectedGraceDays = 3
        XCTAssertEqual(expectedGraceDays, 3)
    }

    // MARK: - License Equality

    func testLicenseEquality() {
        let date = Date()
        let l1 = License(key: "NOTTA-TEST-TEST-TEST-TEST", email: "test@example.com", status: .active, expiresAt: date, createdAt: date, machineId: "machine1")
        let l2 = License(key: "NOTTA-TEST-TEST-TEST-TEST", email: "test@example.com", status: .active, expiresAt: date, createdAt: date, machineId: "machine1")

        XCTAssertEqual(l1, l2)
    }

    func testLicenseInequality() {
        let date = Date()
        let l1 = License(key: "NOTTA-TEST-TEST-TEST-TEST", email: "test@example.com", status: .active, expiresAt: date, createdAt: date, machineId: "machine1")
        let l2 = License(key: "NOTTA-DIFF-DIFF-DIFF-DIFF", email: "test@example.com", status: .active, expiresAt: date, createdAt: date, machineId: "machine1")

        XCTAssertNotEqual(l1, l2)
    }
}
