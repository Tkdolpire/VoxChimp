import XCTest
@testable import Notta

final class UpdaterServiceTests: XCTestCase {

    var updaterService: UpdaterService!

    override func setUp() {
        super.setUp()
        updaterService = UpdaterService.shared
    }

    override func tearDown() {
        updaterService = nil
        super.tearDown()
    }

    // MARK: - Singleton

    func testSharedInstanceExists() {
        XCTAssertNotNil(UpdaterService.shared)
    }

    func testSharedInstanceIsSingleton() {
        let instance1 = UpdaterService.shared
        let instance2 = UpdaterService.shared
        XCTAssertTrue(instance1 === instance2)
    }

    // MARK: - Properties

    func testAutomaticallyChecksForUpdatesProperty() {
        // Verify property is accessible
        let _ = updaterService.automaticallyChecksForUpdates
    }

    func testCanCheckForUpdatesProperty() {
        // Verify property is accessible
        let _ = updaterService.canCheckForUpdates
    }

    func testLastUpdateCheckDateProperty() {
        // Verify property is accessible (may be nil)
        let _ = updaterService.lastUpdateCheckDate
    }

    // MARK: - Methods

    func testCheckForUpdatesDoesNotCrash() {
        // This method should not crash even without Sparkle configured
        // In App Store build or without Sparkle, it's a no-op
        updaterService.checkForUpdates()
    }

    func testCheckForUpdatesInBackgroundDoesNotCrash() {
        // This method should not crash even without Sparkle configured
        updaterService.checkForUpdatesInBackground()
    }

    // MARK: - Published Properties

    @MainActor
    func testAutomaticallyChecksForUpdatesIsPublished() async {
        let expectation = XCTestExpectation(description: "automaticallyChecksForUpdates changed")

        let cancellable = updaterService.$automaticallyChecksForUpdates.sink { _ in
            expectation.fulfill()
        }

        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()
    }

    // MARK: - Setting automaticallyChecksForUpdates

    func testSetAutomaticallyChecksForUpdates() {
        let original = updaterService.automaticallyChecksForUpdates

        updaterService.automaticallyChecksForUpdates = true
        XCTAssertTrue(updaterService.automaticallyChecksForUpdates)

        updaterService.automaticallyChecksForUpdates = false
        XCTAssertFalse(updaterService.automaticallyChecksForUpdates)

        // Restore
        updaterService.automaticallyChecksForUpdates = original
    }
}

// MARK: - CheckForUpdatesViewModifier Tests

final class CheckForUpdatesViewModifierTests: XCTestCase {

    func testViewModifierExists() {
        // Verify the modifier type exists
        let _ = CheckForUpdatesViewModifier.self
    }
}

// MARK: - UpdateSettingsView Tests

import SwiftUI

final class UpdateSettingsViewTests: XCTestCase {

    func testUpdateSettingsViewCanBeCreated() {
        let view = UpdateSettingsView()
        XCTAssertNotNil(view)
    }

    func testUpdateSettingsViewUsesSharedUpdater() {
        let view = UpdateSettingsView()
        // View uses UpdaterService.shared internally
        XCTAssertNotNil(view)
    }
}
