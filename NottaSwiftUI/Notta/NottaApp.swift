import SwiftUI
import AVFoundation
import AppKit

@main
struct NottaApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var appState = AppState()
    @StateObject private var licenseManager = LicenseManager.shared
    @StateObject private var updaterService = UpdaterService.shared

    var body: some Scene {
        WindowGroup {
            MainView()
                .environmentObject(appState)
                .environmentObject(licenseManager)
                .frame(minWidth: 360, minHeight: 400)
                #if !APPSTORE
                .onOpenURL { url in
                    handleIncomingURL(url)
                }
                #endif
        }
        .handlesExternalEvents(matching: Set(["*"]))
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        .commands {
            CommandGroup(replacing: .newItem) { }

            // Check for Updates menu item
            CommandGroup(after: .appInfo) {
                #if !APPSTORE
                Button("Check for Updates...") {
                    updaterService.checkForUpdates()
                }
                .checkForUpdatesStyle()
                #endif
            }
        }

        Settings {
            SettingsView()
                .environmentObject(appState)
                .environmentObject(licenseManager)
        }

        Window("History", id: "history") {
            HistoryView()
                .environmentObject(appState)
                .environmentObject(licenseManager)
                .frame(minWidth: 500, minHeight: 400)
        }

        Window("Voice Health", id: "health") {
            HealthDashboardView()
                .environmentObject(appState)
                .environmentObject(licenseManager)
                .frame(minWidth: 450, minHeight: 550)
        }
    }

    // MARK: - URL Handling

    #if !APPSTORE
    private func handleIncomingURL(_ url: URL) {
        // Handle notta:// URLs for license activation
        LicenseManager.handleIncomingURL(url)
    }
    #endif
}

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    var hotkeyManager: HotkeyManager?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Setup global hotkey monitoring
        hotkeyManager = HotkeyManager.shared
        hotkeyManager?.startListening()

        // Request necessary permissions
        requestPermissions()

        // Initialize license manager
        Task { @MainActor in
            await LicenseManager.shared.initialize()
        }

        // Request notification permission if health notifications enabled
        if SettingsManager.shared.healthNotificationsEnabled {
            Task {
                await NotificationService.shared.requestPermission()
            }
        }

        // Check accessibility permission after a short delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            self.checkAccessibilityPermission()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        hotkeyManager?.stopListening()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    // MARK: - URL Handling

    #if !APPSTORE
    func application(_ application: NSApplication, open urls: [URL]) {
        // Bring app to front
        NSApp.activate(ignoringOtherApps: true)

        for url in urls {
            LicenseManager.handleIncomingURL(url)
        }
    }
    #endif

    // MARK: - Permissions

    private func requestPermissions() {
        // Microphone permission
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            if !granted {
                print("Microphone access denied")
            }
        }
    }

    private func checkAccessibilityPermission() {
        guard let hotkeyManager = hotkeyManager else { return }

        if !hotkeyManager.hasAccessibilityPermission {
            showAccessibilityPermissionAlert()
        }
    }

    private func showAccessibilityPermissionAlert() {
        let alert = NSAlert()
        alert.messageText = "Accessibility Permission Required"
        alert.informativeText = "Notta needs Accessibility permission to:\n\n• Detect hotkeys when other apps are focused\n• Auto-paste transcribed text at your cursor\n\nClick \"Open System Settings\" and add Notta to the Accessibility list."
        alert.alertStyle = .informational
        alert.icon = NSImage(systemSymbolName: "hand.raised.fill", accessibilityDescription: "Permission")

        alert.addButton(withTitle: "Open System Settings")
        alert.addButton(withTitle: "Later")

        let response = alert.runModal()

        if response == .alertFirstButtonReturn {
            hotkeyManager?.openAccessibilitySettings()
        }
    }
}
