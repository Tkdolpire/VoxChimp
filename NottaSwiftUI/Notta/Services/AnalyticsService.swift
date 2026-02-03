import Foundation
import CryptoKit
import IOKit

/// Privacy-first, opt-in analytics for understanding usage patterns.
/// No PII collected - only anonymized usage metrics.
@MainActor
final class AnalyticsService: ObservableObject {
    // MARK: - Singleton

    static let shared = AnalyticsService()

    // MARK: - Published State

    @Published private(set) var isEnabled: Bool = false

    // MARK: - Configuration

    private let analyticsEndpoint = "https://notta-api.vercel.app/api/analytics"
    private let batchSize = 20
    private let flushInterval: TimeInterval = 60  // seconds
    private let maxQueueSize = 500

    // MARK: - Private State

    private var deviceId: String = ""
    private var eventQueue: [AnalyticsEvent] = []
    private var flushTimer: Timer?
    private var sessionStart: Date?
    private var isShuttingDown = false

    private let osVersion: String = {
        let version = ProcessInfo.processInfo.operatingSystemVersion
        return "macOS \(version.majorVersion).\(version.minorVersion).\(version.patchVersion)"
    }()

    private var appVersion: String {
        Bundle.main.appVersion
    }

    // MARK: - UserDefaults Keys

    private enum Keys {
        static let analyticsEnabled = "notta.analytics.enabled"
        static let analyticsConsented = "notta.analytics.consented"
        static let eventQueue = "notta.analytics.queue"
        static let deviceId = "notta.analytics.deviceId"
    }

    // MARK: - Initialization

    private init() {
        loadState()
        deviceId = loadOrGenerateDeviceId()
        print("[Analytics] Initialized (enabled=\(isEnabled))")
    }

    // MARK: - Public API

    /// Enable analytics collection
    func enable() {
        isEnabled = true
        UserDefaults.standard.set(true, forKey: Keys.analyticsEnabled)
        UserDefaults.standard.set(true, forKey: Keys.analyticsConsented)
        startFlushTimer()
        print("[Analytics] Enabled")

        track("settings_changed", data: [
            "setting": "analytics_enabled",
            "old_value": "false",
            "new_value": "true"
        ])
    }

    /// Disable analytics collection
    func disable() {
        track("settings_changed", data: [
            "setting": "analytics_enabled",
            "old_value": "true",
            "new_value": "false"
        ])

        flush()  // Send pending events

        isEnabled = false
        UserDefaults.standard.set(false, forKey: Keys.analyticsEnabled)
        stopFlushTimer()
        print("[Analytics] Disabled")
    }

    /// Check if user has made a consent decision
    var hasConsented: Bool {
        UserDefaults.standard.bool(forKey: Keys.analyticsConsented)
    }

    /// Track an analytics event
    func track(_ eventType: String, data: [String: Any]? = nil) {
        guard isEnabled else { return }

        let event = AnalyticsEvent(
            eventType: eventType,
            eventData: sanitizeData(data ?? [:]),
            timestamp: ISO8601DateFormatter().string(from: Date())
        )

        eventQueue.append(event)

        // Trim queue if too large
        if eventQueue.count > maxQueueSize {
            eventQueue = Array(eventQueue.suffix(maxQueueSize))
        }

        saveQueue()

        print("[Analytics] Tracked: \(eventType) (queue size: \(eventQueue.count))")

        // Flush if batch is full
        if eventQueue.count >= batchSize {
            Task {
                await flushAsync()
            }
        }
    }

    /// Start a new analytics session
    func startSession() {
        sessionStart = Date()
        track("app_launch")
        startFlushTimer()
    }

    /// End the current analytics session
    func endSession() {
        if let start = sessionStart {
            let duration = Int(Date().timeIntervalSince(start))
            track("app_quit", data: ["session_duration_seconds": duration])
        }
        flush()
        stopFlushTimer()
    }

    /// Graceful shutdown
    func shutdown() {
        isShuttingDown = true
        stopFlushTimer()
        if isEnabled {
            flush()
        }
        print("[Analytics] Shutdown complete")
    }

    /// Flush events synchronously (blocking)
    func flush() {
        guard !eventQueue.isEmpty, !deviceId.isEmpty else { return }

        let batch = Array(eventQueue.prefix(batchSize))
        let success = sendBatchSync(batch)

        if success {
            eventQueue.removeFirst(min(batch.count, eventQueue.count))
            saveQueue()
            print("[Analytics] Flushed \(batch.count) events")

            // Recursively flush if more events remain
            if eventQueue.count >= batchSize {
                flush()
            }
        }
    }

    // MARK: - Private Methods

    private func loadState() {
        isEnabled = UserDefaults.standard.bool(forKey: Keys.analyticsEnabled)
        loadQueue()
    }

    private func loadQueue() {
        guard let data = UserDefaults.standard.data(forKey: Keys.eventQueue),
              let queue = try? JSONDecoder().decode([AnalyticsEvent].self, from: data) else {
            return
        }
        eventQueue = queue
        print("[Analytics] Loaded \(eventQueue.count) queued events")
    }

    private func saveQueue() {
        guard let data = try? JSONEncoder().encode(eventQueue) else { return }
        UserDefaults.standard.set(data, forKey: Keys.eventQueue)
    }

    private func loadOrGenerateDeviceId() -> String {
        // Check for existing ID
        if let storedId = UserDefaults.standard.string(forKey: Keys.deviceId), !storedId.isEmpty {
            return storedId
        }

        // Generate new anonymized ID
        let newId = generateDeviceId()
        UserDefaults.standard.set(newId, forKey: Keys.deviceId)
        return newId
    }

    private func generateDeviceId() -> String {
        // Try to get hardware UUID
        if let hardwareUUID = getHardwareUUID() {
            // Hash it for privacy
            let hash = SHA256.hash(data: Data(hardwareUUID.utf8))
            return hash.compactMap { String(format: "%02x", $0) }.joined()
        }

        // Fallback: use hostname + username hash
        let hostname = Host.current().localizedName ?? "unknown"
        let username = NSUserName()
        let identifier = "\(hostname)-\(username)"
        let hash = SHA256.hash(data: Data(identifier.utf8))
        return hash.compactMap { String(format: "%02x", $0) }.joined()
    }

    private func getHardwareUUID() -> String? {
        let platformExpert = IOServiceGetMatchingService(
            kIOMainPortDefault,
            IOServiceMatching("IOPlatformExpertDevice")
        )

        guard platformExpert != 0 else { return nil }

        defer { IOObjectRelease(platformExpert) }

        guard let uuid = IORegistryEntryCreateCFProperty(
            platformExpert,
            kIOPlatformUUIDKey as CFString,
            kCFAllocatorDefault,
            0
        )?.takeRetainedValue() as? String else {
            return nil
        }

        return uuid
    }

    private func sanitizeData(_ data: [String: Any]) -> [String: Any] {
        // Convert all values to JSON-safe types
        var sanitized: [String: Any] = [:]
        for (key, value) in data {
            switch value {
            case let string as String:
                sanitized[key] = string
            case let number as Int:
                sanitized[key] = number
            case let number as Double:
                sanitized[key] = number
            case let bool as Bool:
                sanitized[key] = bool
            default:
                sanitized[key] = String(describing: value)
            }
        }
        return sanitized
    }

    private func startFlushTimer() {
        guard flushTimer == nil, isEnabled else { return }

        flushTimer = Timer.scheduledTimer(withTimeInterval: flushInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self = self, !self.isShuttingDown else { return }
                await self.flushAsync()
            }
        }
    }

    private func stopFlushTimer() {
        flushTimer?.invalidate()
        flushTimer = nil
    }

    private func flushAsync() async {
        guard !eventQueue.isEmpty, !deviceId.isEmpty else { return }

        let batch = Array(eventQueue.prefix(batchSize))

        do {
            let success = try await sendBatch(batch)
            if success {
                eventQueue.removeFirst(min(batch.count, eventQueue.count))
                saveQueue()
                print("[Analytics] Flushed \(batch.count) events")

                // Continue flushing if more events
                if eventQueue.count >= batchSize {
                    await flushAsync()
                }
            }
        } catch {
            print("[Analytics] Flush failed: \(error)")
        }
    }

    private func sendBatch(_ events: [AnalyticsEvent]) async throws -> Bool {
        guard let url = URL(string: analyticsEndpoint) else { return false }

        let payload = AnalyticsPayload(
            deviceId: deviceId,
            events: events,
            appVersion: appVersion,
            osVersion: osVersion
        )

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Notta/\(appVersion)", forHTTPHeaderField: "User-Agent")
        request.httpBody = try JSONEncoder().encode(payload)
        request.timeoutInterval = 10

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else { return false }

        if httpResponse.statusCode == 200 {
            return true
        } else if httpResponse.statusCode == 400 {
            // Bad request - drop the events
            print("[Analytics] Server rejected events (400)")
            return true
        }

        return false
    }

    private func sendBatchSync(_ events: [AnalyticsEvent]) -> Bool {
        guard let url = URL(string: analyticsEndpoint) else { return false }

        let payload = AnalyticsPayload(
            deviceId: deviceId,
            events: events,
            appVersion: appVersion,
            osVersion: osVersion
        )

        guard let body = try? JSONEncoder().encode(payload) else { return false }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Notta/\(appVersion)", forHTTPHeaderField: "User-Agent")
        request.httpBody = body
        request.timeoutInterval = 10

        let semaphore = DispatchSemaphore(value: 0)
        var success = false

        let task = URLSession.shared.dataTask(with: request) { _, response, error in
            if error == nil,
               let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200 || httpResponse.statusCode == 400 {
                success = true
            }
            semaphore.signal()
        }
        task.resume()
        semaphore.wait()

        return success
    }
}

// MARK: - Data Models

private struct AnalyticsEvent: Codable {
    let eventType: String
    let eventData: [String: AnyCodable]
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case eventType = "event_type"
        case eventData = "event_data"
        case timestamp
    }

    init(eventType: String, eventData: [String: Any], timestamp: String) {
        self.eventType = eventType
        self.eventData = eventData.mapValues { AnyCodable($0) }
        self.timestamp = timestamp
    }
}

private struct AnalyticsPayload: Codable {
    let deviceId: String
    let events: [AnalyticsEvent]
    let appVersion: String
    let osVersion: String

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case events
        case appVersion = "app_version"
        case osVersion = "os_version"
    }
}

/// Type-erased codable wrapper for heterogeneous dictionaries
private struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) {
            value = string
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else {
            value = ""
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let string as String:
            try container.encode(string)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let bool as Bool:
            try container.encode(bool)
        default:
            try container.encode(String(describing: value))
        }
    }
}

