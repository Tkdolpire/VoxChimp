import Foundation
import SwiftUI

// UpdaterService uses Sparkle for direct distribution (Pro) version only
// App Store version gets updates through the App Store

#if !APPSTORE

// Note: Sparkle must be added as a package dependency in Xcode
// File -> Add Package Dependencies -> https://github.com/sparkle-project/Sparkle
// Version: 2.x

#if canImport(Sparkle)
import Sparkle

/// Service for managing automatic updates using Sparkle
final class UpdaterService: ObservableObject {
    // MARK: - Singleton

    static let shared = UpdaterService()

    // MARK: - Properties

    private let updaterController: SPUStandardUpdaterController

    /// Whether automatic update checking is enabled
    @Published var automaticallyChecksForUpdates: Bool {
        didSet {
            updaterController.updater.automaticallyChecksForUpdates = automaticallyChecksForUpdates
        }
    }

    /// Whether updates can be checked right now
    var canCheckForUpdates: Bool {
        updaterController.updater.canCheckForUpdates
    }

    /// The last time updates were checked
    var lastUpdateCheckDate: Date? {
        updaterController.updater.lastUpdateCheckDate
    }

    // MARK: - Initialization

    private init() {
        // Initialize Sparkle updater controller
        // startingUpdater: true means it will start checking for updates immediately
        updaterController = SPUStandardUpdaterController(
            startingUpdater: true,
            updaterDelegate: nil,
            userDriverDelegate: nil
        )

        automaticallyChecksForUpdates = updaterController.updater.automaticallyChecksForUpdates
    }

    // MARK: - Public Methods

    /// Check for updates manually
    func checkForUpdates() {
        updaterController.checkForUpdates(nil)
    }

    /// Check for updates in the background (no UI if no update available)
    func checkForUpdatesInBackground() {
        updaterController.updater.checkForUpdatesInBackground()
    }
}

#else

/// Stub UpdaterService when Sparkle is not available
/// This allows the code to compile without Sparkle, but updates won't work
final class UpdaterService: ObservableObject {
    static let shared = UpdaterService()

    @Published var automaticallyChecksForUpdates: Bool = false

    var canCheckForUpdates: Bool { false }
    var lastUpdateCheckDate: Date? { nil }

    private init() {
        print("Warning: Sparkle framework not available. Auto-updates disabled.")
    }

    func checkForUpdates() {
        print("Sparkle not available - cannot check for updates")
    }

    func checkForUpdatesInBackground() {
        print("Sparkle not available - cannot check for updates")
    }
}

#endif

#else

// MARK: - App Store Stub

/// Stub UpdaterService for App Store version - updates come from the App Store
final class UpdaterService: ObservableObject {
    static let shared = UpdaterService()

    @Published var automaticallyChecksForUpdates: Bool = true

    var canCheckForUpdates: Bool { false }
    var lastUpdateCheckDate: Date? { nil }

    private init() {}

    func checkForUpdates() {
        // Open App Store to check for updates
        if let url = URL(string: "macappstore://apps.apple.com/app/idYOUR_APP_ID") {
            NSWorkspace.shared.open(url)
        }
    }

    func checkForUpdatesInBackground() {
        // App Store handles background updates
    }
}

#endif

// MARK: - SwiftUI View Modifier

/// View modifier for adding update check button to menus
struct CheckForUpdatesViewModifier: ViewModifier {
    @ObservedObject private var updater = UpdaterService.shared

    func body(content: Content) -> some View {
        content
            .disabled(!updater.canCheckForUpdates)
    }
}

extension View {
    func checkForUpdatesStyle() -> some View {
        modifier(CheckForUpdatesViewModifier())
    }
}

// MARK: - Settings View for Updates

struct UpdateSettingsView: View {
    @ObservedObject var updater = UpdaterService.shared

    var body: some View {
        Form {
            Section {
                #if !APPSTORE
                Toggle("Automatically check for updates", isOn: $updater.automaticallyChecksForUpdates)

                HStack {
                    Text("Last checked")
                    Spacer()
                    if let date = updater.lastUpdateCheckDate {
                        Text(date, style: .relative)
                            .foregroundStyle(.secondary)
                    } else {
                        Text("Never")
                            .foregroundStyle(.secondary)
                    }
                }

                Button("Check for Updates Now") {
                    updater.checkForUpdates()
                }
                .disabled(!updater.canCheckForUpdates)
                #else
                Text("Updates are delivered through the App Store.")
                    .foregroundStyle(.secondary)

                Button("Open App Store") {
                    updater.checkForUpdates()
                }
                #endif
            } header: {
                Text("Software Updates")
            } footer: {
                #if !APPSTORE
                Text("Notta will automatically download and install updates when available.")
                #else
                Text("Enable automatic updates in the App Store to stay up to date.")
                #endif
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - Preview

#Preview {
    UpdateSettingsView()
        .frame(width: 400)
}
