import SwiftUI
import AVFoundation
import AppKit

@main
struct NottaApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var appState = AppState()
    @StateObject private var licenseManager = LicenseManager.shared
    @StateObject private var updaterService = UpdaterService.shared
    @StateObject private var analyticsService = AnalyticsService.shared
    @Environment(\.openWindow) private var openWindow
    @State private var showAnalyticsConsent = false

    var body: some Scene {
        WindowGroup {
            MainView()
                .environmentObject(appState)
                .environmentObject(licenseManager)
                .environmentObject(analyticsService)
                .withTranslationSupport()
                .frame(minWidth: 360, minHeight: 400)
                .onReceive(NotificationCenter.default.publisher(for: .openHistoryWindow)) { _ in
                    openWindow(id: "history")
                    analyticsService.track("history_opened")
                }
                .onReceive(NotificationCenter.default.publisher(for: .openHealthWindow)) { _ in
                    openWindow(id: "health")
                    analyticsService.track("health_window_opened")
                }
                .onAppear {
                    // Show analytics consent on first launch
                    if !analyticsService.hasConsented {
                        showAnalyticsConsent = true
                    }
                }
                .alert("Help Improve Notta", isPresented: $showAnalyticsConsent) {
                    Button("Share Usage Data") {
                        analyticsService.enable()
                        analyticsService.startSession()
                    }
                    Button("No Thanks", role: .cancel) {
                        // Mark as consented but not enabled
                        UserDefaults.standard.set(true, forKey: "notta.analytics.consented")
                    }
                } message: {
                    Text("Would you like to share anonymous usage data?\n\nWhat we collect:\n\u{2022} Feature usage (which buttons you use)\n\u{2022} Performance metrics (transcription speed)\n\u{2022} Error rates\n\nWhat we never collect:\n\u{2022} Your audio recordings\n\u{2022} Your transcribed text\n\u{2022} Any personal information\n\nYou can change this anytime in Settings.")
                }
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
    var statusItem: NSStatusItem?
    private var recordingObserver: NSObjectProtocol?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Setup global hotkey monitoring
        hotkeyManager = HotkeyManager.shared
        hotkeyManager?.startListening()

        // Setup menu bar status item
        setupMenuBarItem()

        // Request necessary permissions
        requestPermissions()

        // Initialize license manager
        Task { @MainActor in
            await LicenseManager.shared.initialize()
        }

        // Track first launch
        let isFirstLaunch = !UserDefaults.standard.bool(forKey: "notta.hasLaunchedBefore")
        if isFirstLaunch {
            UserDefaults.standard.set(true, forKey: "notta.hasLaunchedBefore")
        }

        // Initialize analytics (start session if already enabled)
        Task { @MainActor in
            let analytics = AnalyticsService.shared
            if analytics.isEnabled {
                analytics.startSession()
                if isFirstLaunch {
                    analytics.track("first_launch")
                }
            }
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

    // MARK: - Menu Bar Status Item

    private func setupMenuBarItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)

        if let button = statusItem?.button {
            button.image = circularMenuBarIcon(named: "MenuBarIdle")
            button.toolTip = "Notta - Ready"
        }

        // Create menu
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Notta", action: #selector(openMainWindow), keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "History", action: #selector(openHistory), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Voice Health", action: #selector(openHealth), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Settings...", action: #selector(openSettings), keyEquivalent: ","))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit Notta", action: #selector(quitApp), keyEquivalent: "q"))

        statusItem?.menu = menu

        // Observe recording state changes
        recordingObserver = NotificationCenter.default.addObserver(
            forName: .recordingStateChanged,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            let isRecording = notification.userInfo?["isRecording"] as? Bool ?? false
            self?.updateMenuBarIcon(isRecording: isRecording)
        }
    }

    private func updateMenuBarIcon(isRecording: Bool) {
        guard let button = statusItem?.button else { return }

        let imageName = isRecording ? "MenuBarRecording" : "MenuBarIdle"
        button.image = circularMenuBarIcon(named: imageName)
        button.toolTip = isRecording ? "Notta - Recording..." : "Notta - Ready"
    }

    private func circularMenuBarIcon(named: String) -> NSImage? {
        guard let sourceImage = NSImage(named: named) else { return nil }

        let size = NSSize(width: 18, height: 18)
        let circularImage = NSImage(size: size)

        circularImage.lockFocus()

        // Create circular clipping path
        let rect = NSRect(origin: .zero, size: size)
        let circlePath = NSBezierPath(ovalIn: rect)
        circlePath.addClip()

        // Draw the source image scaled to fit
        sourceImage.draw(in: rect, from: NSRect(origin: .zero, size: sourceImage.size), operation: .sourceOver, fraction: 1.0)

        circularImage.unlockFocus()

        return circularImage
    }

    @objc private func openMainWindow() {
        NSApp.activate(ignoringOtherApps: true)
        // Find and show the main window
        for window in NSApp.windows {
            if window.title == "Notta" || window.title.isEmpty {
                window.makeKeyAndOrderFront(nil)
                return
            }
        }
        NSApp.windows.first?.makeKeyAndOrderFront(nil)
    }

    @objc private func openHistory() {
        NSApp.activate(ignoringOtherApps: true)
        NotificationCenter.default.post(name: .openHistoryWindow, object: nil)
    }

    @objc private func openHealth() {
        NSApp.activate(ignoringOtherApps: true)
        NotificationCenter.default.post(name: .openHealthWindow, object: nil)
    }

    @objc private func openSettings() {
        NSApp.activate(ignoringOtherApps: true)
        // Try modern macOS 14+ settings, fall back to older
        if NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil) == false {
            NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
        }
    }

    @objc private func quitApp() {
        NSApp.terminate(nil)
    }

    func applicationWillTerminate(_ notification: Notification) {
        hotkeyManager?.stopListening()
        if let observer = recordingObserver {
            NotificationCenter.default.removeObserver(observer)
        }

        // Flush analytics before quit
        Task { @MainActor in
            AnalyticsService.shared.endSession()
            AnalyticsService.shared.shutdown()
        }
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
                Task { @MainActor in
                    AnalyticsService.shared.track("permission_denied", data: [
                        "permission": "microphone"
                    ])
                }
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
        } else {
            Task { @MainActor in
                AnalyticsService.shared.track("permission_denied", data: [
                    "permission": "accessibility",
                    "action": "dismissed_later"
                ])
            }
        }
    }
}
