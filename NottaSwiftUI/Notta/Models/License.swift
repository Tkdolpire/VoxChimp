import Foundation

// MARK: - License State

enum LicenseState: Equatable {
    case unknown
    case trial(daysRemaining: Int)
    case trialExpired
    case active
    case expired
    case invalid

    var isUnlocked: Bool {
        switch self {
        case .active, .trial:
            return true
        case .unknown, .trialExpired, .expired, .invalid:
            return false
        }
    }

    var displayName: String {
        switch self {
        case .unknown:
            return "Unknown"
        case .trial(let days):
            return "Trial (\(days) days left)"
        case .trialExpired:
            return "Trial Expired"
        case .active:
            return "Pro"
        case .expired:
            return "Subscription Expired"
        case .invalid:
            return "Invalid License"
        }
    }

    var statusColor: String {
        switch self {
        case .active:
            return "green"
        case .trial:
            return "blue"
        case .unknown, .trialExpired, .expired, .invalid:
            return "orange"
        }
    }
}

// MARK: - License Model

struct License: Codable, Equatable {
    let key: String
    let email: String?
    let status: LicenseStatus
    let expiresAt: Date?
    let createdAt: Date
    let machineId: String?

    enum LicenseStatus: String, Codable {
        case active
        case canceled
        case pastDue = "past_due"
        case expired
        case invalid
    }
}

// MARK: - API Response Models

struct ValidationResponse: Codable {
    let valid: Bool
    let status: String
    let expiresAt: Date?
    let email: String?
    let message: String?
}

struct CheckoutResponse: Codable {
    let url: String
    let sessionId: String
}

struct PortalResponse: Codable {
    let url: String
}

// MARK: - Machine Identification

struct MachineIdentifier {
    static var current: String {
        // Use a combination of hardware identifiers for machine fingerprinting
        // This is used to limit license activations to a certain number of machines

        if let uuid = getMachineUUID() {
            return uuid
        }

        // Fallback: generate and persist a random UUID
        return getOrCreateFallbackUUID()
    }

    private static func getMachineUUID() -> String? {
        let platformExpert = IOServiceGetMatchingService(
            kIOMainPortDefault,
            IOServiceMatching("IOPlatformExpertDevice")
        )

        defer { IOObjectRelease(platformExpert) }

        guard platformExpert != 0 else { return nil }

        guard let serialNumberAsCFString = IORegistryEntryCreateCFProperty(
            platformExpert,
            kIOPlatformUUIDKey as CFString,
            kCFAllocatorDefault,
            0
        )?.takeUnretainedValue() as? String else {
            return nil
        }

        return serialNumberAsCFString
    }

    private static func getOrCreateFallbackUUID() -> String {
        let key = "notta.machine.uuid"

        if let existing = UserDefaults.standard.string(forKey: key) {
            return existing
        }

        let newUUID = UUID().uuidString
        UserDefaults.standard.set(newUUID, forKey: key)
        return newUUID
    }
}

// MARK: - License Key Validation

struct LicenseKeyValidator {
    /// Validates the format of a license key (NOTTA-XXXX-XXXX-XXXX-XXXX)
    static func isValidFormat(_ key: String) -> Bool {
        let pattern = "^NOTTA-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"
        return key.range(of: pattern, options: .regularExpression) != nil
    }

    /// Formats a raw key input by adding dashes and uppercasing
    static func format(_ input: String) -> String {
        let cleaned = input.uppercased().replacingOccurrences(of: "[^A-Z0-9]", with: "", options: .regularExpression)

        // If it starts with NOTTA, remove it for processing
        let withoutPrefix = cleaned.hasPrefix("NOTTA") ? String(cleaned.dropFirst(5)) : cleaned

        guard withoutPrefix.count >= 16 else {
            return input.uppercased()
        }

        let chunks = stride(from: 0, to: 16, by: 4).map { index -> String in
            let start = withoutPrefix.index(withoutPrefix.startIndex, offsetBy: index)
            let end = withoutPrefix.index(start, offsetBy: 4)
            return String(withoutPrefix[start..<end])
        }

        return "NOTTA-" + chunks.joined(separator: "-")
    }
}
