import XCTest
@testable import Notta

@MainActor
final class ModelManagerTests: XCTestCase {

    var modelManager: ModelManager!

    override func setUp() async throws {
        try await super.setUp()
        modelManager = ModelManager.shared
    }

    override func tearDown() async throws {
        // Cancel any pending downloads
        modelManager.cancelDownload()
        try await super.tearDown()
    }

    // MARK: - Singleton

    func testSharedInstanceExists() {
        XCTAssertNotNil(ModelManager.shared)
    }

    func testSharedInstanceIsSingleton() {
        let instance1 = ModelManager.shared
        let instance2 = ModelManager.shared
        XCTAssertTrue(instance1 === instance2)
    }

    // MARK: - Initial State

    func testInitialDownloadProgressZero() {
        XCTAssertEqual(modelManager.downloadProgress, 0)
    }

    func testInitialIsDownloadingFalse() {
        XCTAssertFalse(modelManager.isDownloading)
    }

    func testInitialDownloadingModelNil() {
        XCTAssertNil(modelManager.downloadingModel)
    }

    func testInitialDownloadErrorNil() {
        XCTAssertNil(modelManager.downloadError)
    }

    // MARK: - Model Status

    func testIsDownloadedReturnsBoolean() {
        // Just verify we can call the method
        let _ = modelManager.isDownloaded(.tiny)
        let _ = modelManager.isDownloaded(.small)
        let _ = modelManager.isDownloaded(.medium)
        let _ = modelManager.isDownloaded(.large)
    }

    func testDownloadedModelsIsSet() {
        // Verify the set exists and can be accessed
        XCTAssertNotNil(modelManager.downloadedModels)
    }

    // MARK: - Storage

    func testTotalStorageUsedReturnsNonNegative() {
        let storage = modelManager.totalStorageUsed()
        XCTAssertGreaterThanOrEqual(storage, 0)
    }

    func testFormattedStorageUsedReturnsString() {
        let formatted = modelManager.formattedStorageUsed()
        XCTAssertFalse(formatted.isEmpty)
    }

    func testFormattedStorageUsedContainsUnit() {
        let formatted = modelManager.formattedStorageUsed()
        // Should contain a unit like "bytes", "KB", "MB", "GB"
        let hasUnit = formatted.contains("bytes") ||
                      formatted.contains("KB") ||
                      formatted.contains("MB") ||
                      formatted.contains("GB") ||
                      formatted.contains("Zero")
        XCTAssertTrue(hasUnit, "Formatted storage should contain a unit: \(formatted)")
    }

    // MARK: - Cancel Download

    func testCancelDownloadResetsState() {
        modelManager.cancelDownload()

        XCTAssertFalse(modelManager.isDownloading)
        XCTAssertNil(modelManager.downloadingModel)
        XCTAssertEqual(modelManager.downloadProgress, 0)
    }

    func testCancelDownloadIdempotent() {
        // Should not crash when called multiple times
        modelManager.cancelDownload()
        modelManager.cancelDownload()
        modelManager.cancelDownload()
    }

    // MARK: - WhisperModel Extensions

    func testWhisperModelDownloadSizeMB() {
        XCTAssertEqual(WhisperModel.tiny.downloadSizeMB, 75)
        XCTAssertEqual(WhisperModel.base.downloadSizeMB, 150)
        XCTAssertEqual(WhisperModel.small.downloadSizeMB, 500)
        XCTAssertEqual(WhisperModel.medium.downloadSizeMB, 1500)
        XCTAssertEqual(WhisperModel.large.downloadSizeMB, 3000)
    }

    func testWhisperModelDownloadSizeFormatted() {
        // Verify formatted strings are non-empty
        XCTAssertFalse(WhisperModel.tiny.downloadSizeFormatted.isEmpty)
        XCTAssertFalse(WhisperModel.base.downloadSizeFormatted.isEmpty)
        XCTAssertFalse(WhisperModel.small.downloadSizeFormatted.isEmpty)
        XCTAssertFalse(WhisperModel.medium.downloadSizeFormatted.isEmpty)
        XCTAssertFalse(WhisperModel.large.downloadSizeFormatted.isEmpty)
    }

    func testWhisperModelDownloadSizeFormattedContainsMB() {
        // All models are 75MB+ so should show MB
        XCTAssertTrue(WhisperModel.tiny.downloadSizeFormatted.contains("MB"))
        XCTAssertTrue(WhisperModel.base.downloadSizeFormatted.contains("MB"))
        XCTAssertTrue(WhisperModel.small.downloadSizeFormatted.contains("MB"))
        // Medium and large are 1.5GB+ so may show GB
        let mediumFormatted = WhisperModel.medium.downloadSizeFormatted
        let largeFormatted = WhisperModel.large.downloadSizeFormatted
        XCTAssertTrue(mediumFormatted.contains("MB") || mediumFormatted.contains("GB"))
        XCTAssertTrue(largeFormatted.contains("MB") || largeFormatted.contains("GB"))
    }

    func testWhisperModelAccuracyDescription() {
        XCTAssertEqual(WhisperModel.tiny.accuracyDescription, "Basic")
        XCTAssertEqual(WhisperModel.base.accuracyDescription, "Good")
        XCTAssertEqual(WhisperModel.small.accuracyDescription, "Very Good")
        XCTAssertEqual(WhisperModel.medium.accuracyDescription, "Excellent")
        XCTAssertEqual(WhisperModel.large.accuracyDescription, "Best")
    }

    func testWhisperModelSpeedDescription() {
        XCTAssertEqual(WhisperModel.tiny.speedDescription, "Fastest")
        XCTAssertEqual(WhisperModel.base.speedDescription, "Fast")
        XCTAssertEqual(WhisperModel.small.speedDescription, "Moderate")
        XCTAssertEqual(WhisperModel.medium.speedDescription, "Slower")
        XCTAssertEqual(WhisperModel.large.speedDescription, "Slowest")
    }

    func testWhisperModelRawValues() {
        XCTAssertEqual(WhisperModel.tiny.rawValue, "tiny")
        XCTAssertEqual(WhisperModel.base.rawValue, "base")
        XCTAssertEqual(WhisperModel.small.rawValue, "small")
        XCTAssertEqual(WhisperModel.medium.rawValue, "medium")
        XCTAssertEqual(WhisperModel.large.rawValue, "large")
    }

    func testWhisperModelAllCases() {
        XCTAssertEqual(WhisperModel.allCases.count, 5)
    }

    func testWhisperModelSizesAreOrdered() {
        // Verify sizes increase from tiny to large
        let sizes = WhisperModel.allCases.map { $0.downloadSizeMB }
        for i in 0..<(sizes.count - 1) {
            XCTAssertLessThan(sizes[i], sizes[i + 1], "Model sizes should be ordered")
        }
    }

    // MARK: - WhisperModel Display Names (from Settings)

    func testWhisperModelDisplayNames() {
        XCTAssertEqual(WhisperModel.tiny.displayName, "Tiny (fastest)")
        XCTAssertEqual(WhisperModel.base.displayName, "Base")
        XCTAssertEqual(WhisperModel.small.displayName, "Small (recommended)")
        XCTAssertEqual(WhisperModel.medium.displayName, "Medium")
        XCTAssertEqual(WhisperModel.large.displayName, "Large (most accurate)")
    }

    func testWhisperModelDescriptions() {
        // Verify descriptions contain size info
        XCTAssertTrue(WhisperModel.tiny.description.contains("75MB"))
        XCTAssertTrue(WhisperModel.base.description.contains("150MB"))
        XCTAssertTrue(WhisperModel.small.description.contains("500MB"))
        XCTAssertTrue(WhisperModel.medium.description.contains("1.5GB"))
        XCTAssertTrue(WhisperModel.large.description.contains("3GB"))
    }

    // MARK: - WhisperKitError

    func testWhisperKitErrorModelNotLoaded() {
        let error = WhisperKitError.modelNotLoaded
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("not loaded"))
    }

    func testWhisperKitErrorModelNotDownloaded() {
        let error = WhisperKitError.modelNotDownloaded
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("not downloaded"))
    }

    func testWhisperKitErrorDownloadFailed() {
        let error = WhisperKitError.downloadFailed("Network error")
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("Network error"))
    }

    func testWhisperKitErrorTranscriptionFailed() {
        let error = WhisperKitError.transcriptionFailed("Audio error")
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.contains("Audio error"))
    }

    func testWhisperKitErrorCancelled() {
        let error = WhisperKitError.cancelled
        XCTAssertNotNil(error.errorDescription)
        XCTAssertTrue(error.errorDescription!.lowercased().contains("cancelled"))
    }
}
