import Foundation
import WhisperKit

/// Manages Whisper model downloads and storage
@MainActor
class ModelManager: ObservableObject {
    static let shared = ModelManager()

    @Published var downloadProgress: Double = 0
    @Published var isDownloading = false
    @Published var downloadingModel: WhisperModel?
    @Published var downloadedModels: Set<WhisperModel> = []
    @Published var downloadError: String?

    private let modelsDirectory: URL
    private var downloadTask: Task<Void, Error>?

    private init() {
        // Store models in ~/.notta_models/whisperkit/
        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        modelsDirectory = homeDir.appendingPathComponent(".notta_models/whisperkit")

        // Create directory if needed
        try? FileManager.default.createDirectory(at: modelsDirectory, withIntermediateDirectories: true)

        // Scan for already downloaded models
        scanForDownloadedModels()
    }

    // MARK: - Model Status

    /// Check if a model is downloaded
    func isDownloaded(_ model: WhisperModel) -> Bool {
        return downloadedModels.contains(model)
    }

    /// Get the storage used by downloaded models
    func totalStorageUsed() -> Int64 {
        guard FileManager.default.fileExists(atPath: modelsDirectory.path) else { return 0 }

        var totalSize: Int64 = 0
        if let enumerator = FileManager.default.enumerator(at: modelsDirectory, includingPropertiesForKeys: [.fileSizeKey]) {
            while let fileURL = enumerator.nextObject() as? URL {
                if let fileSize = try? fileURL.resourceValues(forKeys: [.fileSizeKey]).fileSize {
                    totalSize += Int64(fileSize)
                }
            }
        }
        return totalSize
    }

    /// Format storage size for display
    func formattedStorageUsed() -> String {
        let bytes = totalStorageUsed()
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: bytes)
    }

    // MARK: - Model Download

    /// Download a Whisper model
    func downloadModel(_ model: WhisperModel) async throws {
        guard !isDownloading else {
            print("[ModelManager] Download already in progress")
            return
        }

        print("[ModelManager] Starting download for model: \(model.rawValue)")
        isDownloading = true
        downloadingModel = model
        downloadProgress = 0
        downloadError = nil

        defer {
            isDownloading = false
            downloadingModel = nil
        }

        do {
            // WhisperKit downloads models automatically when initializing
            // We'll use a temporary instance to trigger the download
            let modelName = "openai_whisper-\(model.rawValue)"

            // Download the model
            _ = try await WhisperKit(
                model: modelName,
                verbose: false,
                prewarm: false
            )

            downloadProgress = 1.0
            downloadedModels.insert(model)
            print("[ModelManager] Model \(model.rawValue) downloaded successfully")

        } catch {
            downloadError = error.localizedDescription
            print("[ModelManager] Download failed: \(error)")
            throw WhisperKitError.downloadFailed(error.localizedDescription)
        }
    }

    /// Cancel the current download
    func cancelDownload() {
        downloadTask?.cancel()
        downloadTask = nil
        isDownloading = false
        downloadingModel = nil
        downloadProgress = 0
        print("[ModelManager] Download cancelled")
    }

    /// Delete a downloaded model
    func deleteModel(_ model: WhisperModel) {
        let modelPath = modelsDirectory.appendingPathComponent("openai_whisper-\(model.rawValue)")

        do {
            try FileManager.default.removeItem(at: modelPath)
            downloadedModels.remove(model)
            print("[ModelManager] Model \(model.rawValue) deleted")
        } catch {
            print("[ModelManager] Failed to delete model: \(error)")
        }
    }

    // MARK: - Private

    private func scanForDownloadedModels() {
        // Check WhisperKit's default model cache location
        // WhisperKit stores models in ~/Library/Caches/com.argmax.WhisperKit/
        let cacheDir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
            .appendingPathComponent("com.argmax.WhisperKit")

        guard let cacheDir = cacheDir,
              FileManager.default.fileExists(atPath: cacheDir.path) else {
            return
        }

        do {
            let contents = try FileManager.default.contentsOfDirectory(at: cacheDir, includingPropertiesForKeys: nil)
            for url in contents {
                let name = url.lastPathComponent
                // Check if this matches a known model
                for model in WhisperModel.allCases {
                    if name.contains(model.rawValue) {
                        downloadedModels.insert(model)
                        print("[ModelManager] Found cached model: \(model.rawValue)")
                    }
                }
            }
        } catch {
            print("[ModelManager] Error scanning for models: \(error)")
        }
    }
}

// MARK: - WhisperModel Extensions

extension WhisperModel {
    /// Approximate download size in megabytes
    var downloadSizeMB: Int {
        switch self {
        case .tiny: return 75
        case .base: return 150
        case .small: return 500
        case .medium: return 1500
        case .large: return 3000
        }
    }

    /// Formatted download size string
    var downloadSizeFormatted: String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(downloadSizeMB) * 1024 * 1024)
    }

    /// Relative accuracy description
    var accuracyDescription: String {
        switch self {
        case .tiny: return "Basic"
        case .base: return "Good"
        case .small: return "Very Good"
        case .medium: return "Excellent"
        case .large: return "Best"
        }
    }

    /// Relative speed description
    var speedDescription: String {
        switch self {
        case .tiny: return "Fastest"
        case .base: return "Fast"
        case .small: return "Moderate"
        case .medium: return "Slower"
        case .large: return "Slowest"
        }
    }
}
