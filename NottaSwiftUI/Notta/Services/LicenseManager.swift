import Foundation
import SwiftUI
import Combine

/// Manages license validation, trial periods, and feature gating
@MainActor
final class LicenseManager: ObservableObject {
    // MARK: - Singleton

    static let shared = LicenseManager()

    // MARK: - Published State

    @Published private(set) var state: LicenseState = .unknown
    @Published private(set) var licenseKey: String?
    @Published private(set) var email: String?
    @Published private(set) var isValidating: Bool = false
    @Published private(set) var lastError: String?

    // MARK: - Configuration

    /// Number of days for the free trial
    private let trialDays: Int = 14

    /// Number of days to allow offline usage without re-validation
    private let gracePeriodDays: Int = 3

    /// How often to re-validate the license (in seconds)
    private let validationInterval: TimeInterval = 24 * 60 * 60 // 24 hours

    // MARK: - UserDefaults Keys

    private enum Keys {
        static let trialStart = "notta.trial.startDate"
        static let licenseKey = "notta.license.key"
        static let licenseEmail = "notta.license.email"
        static let lastValidation = "notta.license.lastValidation"
        static let cachedStatus = "notta.license.cachedStatus"
    }

    // MARK: - Private Properties

    private let api = LicenseAPI()
    private var validationTask: Task<Void, Never>?
    private var periodicValidationTimer: Timer?

    // MARK: - Initialization

    private init() {
        // Load cached state immediately
        loadCachedState()
    }

    // MARK: - Public Methods

    /// Initialize the license manager - call this on app launch
    func initialize() async {
        // Check for stored license first
        if let key = storedLicenseKey, !key.isEmpty {
            await validateLicense(key, showErrors: false)
        } else {
            // No license - check/start trial
            checkTrialStatus()
        }

        // Set up periodic re-validation
        startPeriodicValidation()
    }

    /// Validate a license key
    func validateLicense(_ key: String, showErrors: Bool = true) async {
        guard LicenseKeyValidator.isValidFormat(key) else {
            if showErrors {
                lastError = "Invalid license key format"
            }
            state = .invalid
            return
        }

        isValidating = true
        lastError = nil

        do {
            let result = try await api.validate(
                licenseKey: key,
                machineId: MachineIdentifier.current
            )

            if result.valid {
                // License is valid
                licenseKey = key
                email = result.email
                state = .active
                storeLicenseKey(key)
                storeValidationTimestamp()
                cacheLicenseStatus(.active)
                print("License validated successfully")
            } else {
                // License rejected by server
                if showErrors {
                    lastError = result.message ?? "License validation failed"
                }
                state = .invalid
                clearStoredLicense()
            }
        } catch {
            // Network or server error - check grace period
            print("License validation error: \(error)")

            if isWithinGracePeriod {
                // Allow continued use during grace period
                state = .active
                print("Within grace period - allowing offline use")
            } else if showErrors {
                lastError = error.localizedDescription
                // Keep cached state if we have one, otherwise mark as expired
                if storedLicenseKey != nil {
                    state = .expired
                }
            }
        }

        isValidating = false
    }

    /// Activate a license key (wrapper that updates UI state)
    func activateLicense(_ key: String) async -> Bool {
        await validateLicense(key, showErrors: true)
        return state == .active
    }

    /// Deactivate the current license
    func deactivateLicense() {
        clearStoredLicense()
        state = .trialExpired // Since trial would have started before license
        checkTrialStatus()
    }

    /// Open the purchase page in the browser
    func openPurchasePage(plan: String = "monthly") async {
        do {
            let response = try await api.createCheckoutSession(email: email, plan: plan)
            if let url = URL(string: response.url) {
                NSWorkspace.shared.open(url)
            }
        } catch {
            lastError = "Failed to create checkout: \(error.localizedDescription)"
        }
    }

    /// Open the Stripe customer portal for subscription management
    func openCustomerPortal() async {
        guard let key = licenseKey else {
            lastError = "No active license"
            return
        }

        do {
            let response = try await api.getPortalURL(licenseKey: key)
            if let url = URL(string: response.url) {
                NSWorkspace.shared.open(url)
            }
        } catch {
            lastError = "Failed to open customer portal: \(error.localizedDescription)"
        }
    }

    /// Handle URL scheme activation (notta://activate?key=...)
    func handleActivationURL(_ url: URL) async {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return
        }

        // Check for direct key activation: notta://activate?key=NOTTA-XXXX-XXXX-XXXX-XXXX
        if let key = components.queryItems?.first(where: { $0.name == "key" })?.value {
            await activateLicense(key)
            return
        }

        // Check for Stripe session completion: notta://activate?session_id=cs_xxx
        if let sessionId = components.queryItems?.first(where: { $0.name == "session_id" })?.value {
            await activateFromCheckoutSession(sessionId)
            return
        }
    }

    /// Restore a purchase from a previous checkout session
    func activateFromCheckoutSession(_ sessionId: String) async {
        isValidating = true
        lastError = nil

        do {
            let response = try await api.getLicenseForSession(sessionId: sessionId)

            if response.valid, let key = response.message {
                // The message field contains the license key for new activations
                licenseKey = key
                email = response.email
                state = .active
                storeLicenseKey(key)
                storeValidationTimestamp()
                cacheLicenseStatus(.active)
            } else {
                lastError = response.message ?? "Failed to retrieve license"
            }
        } catch {
            lastError = "Failed to activate: \(error.localizedDescription)"
        }

        isValidating = false
    }

    // MARK: - Feature Gating

    /// Whether unlimited transcriptions are available
    var canUseUnlimitedTranscriptions: Bool {
        state.isUnlocked
    }

    /// Whether voice health features are available
    var canUseVoiceHealth: Bool {
        state.isUnlocked
    }

    /// Whether the user should see upgrade prompts
    var shouldShowUpgradePrompt: Bool {
        switch state {
        case .trialExpired, .expired, .invalid:
            return true
        case .trial(let days) where days <= 3:
            return true
        default:
            return false
        }
    }

    // MARK: - Trial Management

    private func checkTrialStatus() {
        let now = Date()

        if let trialStart = trialStartDate {
            let daysSinceStart = Calendar.current.dateComponents([.day], from: trialStart, to: now).day ?? 0
            let daysRemaining = max(0, trialDays - daysSinceStart)

            if daysRemaining > 0 {
                state = .trial(daysRemaining: daysRemaining)
            } else {
                state = .trialExpired
            }
        } else {
            // Start new trial
            startTrial()
        }
    }

    private func startTrial() {
        let now = Date()
        UserDefaults.standard.set(now, forKey: Keys.trialStart)
        state = .trial(daysRemaining: trialDays)
        print("Trial started - \(trialDays) days remaining")
    }

    private var trialStartDate: Date? {
        UserDefaults.standard.object(forKey: Keys.trialStart) as? Date
    }

    // MARK: - Storage

    private var storedLicenseKey: String? {
        UserDefaults.standard.string(forKey: Keys.licenseKey)
    }

    private func storeLicenseKey(_ key: String) {
        UserDefaults.standard.set(key, forKey: Keys.licenseKey)
    }

    private func storeValidationTimestamp() {
        UserDefaults.standard.set(Date(), forKey: Keys.lastValidation)
    }

    private func cacheLicenseStatus(_ status: License.LicenseStatus) {
        UserDefaults.standard.set(status.rawValue, forKey: Keys.cachedStatus)
    }

    private func clearStoredLicense() {
        UserDefaults.standard.removeObject(forKey: Keys.licenseKey)
        UserDefaults.standard.removeObject(forKey: Keys.licenseEmail)
        UserDefaults.standard.removeObject(forKey: Keys.lastValidation)
        UserDefaults.standard.removeObject(forKey: Keys.cachedStatus)
        licenseKey = nil
        email = nil
    }

    private var isWithinGracePeriod: Bool {
        guard let lastValidation = UserDefaults.standard.object(forKey: Keys.lastValidation) as? Date else {
            return false
        }

        let gracePeriodEnd = lastValidation.addingTimeInterval(TimeInterval(gracePeriodDays * 24 * 60 * 60))
        return Date() < gracePeriodEnd
    }

    private func loadCachedState() {
        // Load cached license key
        if let key = storedLicenseKey, !key.isEmpty {
            licenseKey = key
            email = UserDefaults.standard.string(forKey: Keys.licenseEmail)

            // Load cached status
            if let statusString = UserDefaults.standard.string(forKey: Keys.cachedStatus),
               let status = License.LicenseStatus(rawValue: statusString) {
                switch status {
                case .active:
                    state = .active
                case .canceled, .pastDue:
                    state = .expired
                case .expired, .invalid:
                    state = .invalid
                }
            } else if isWithinGracePeriod {
                state = .active
            }
        } else {
            checkTrialStatus()
        }
    }

    // MARK: - Periodic Validation

    private func startPeriodicValidation() {
        // Validate every 24 hours
        periodicValidationTimer = Timer.scheduledTimer(withTimeInterval: validationInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self = self, let key = self.licenseKey else { return }
                await self.validateLicense(key, showErrors: false)
            }
        }
    }

    deinit {
        periodicValidationTimer?.invalidate()
    }
}

// MARK: - URL Handling Extension

extension LicenseManager {
    /// Process incoming URLs for the app
    static func handleIncomingURL(_ url: URL) {
        Task { @MainActor in
            if url.scheme == "notta" {
                if url.host == "activate" || url.path.contains("activate") {
                    await LicenseManager.shared.handleActivationURL(url)
                }
            }
        }
    }
}
