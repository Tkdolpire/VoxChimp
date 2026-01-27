import SwiftUI
import AVFoundation
import AppKit

@main
struct NottaApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            MainView()
                .environmentObject(appState)
                .frame(minWidth: 360, minHeight: 400)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        .commands {
            CommandGroup(replacing: .newItem) { }
            CommandGroup(after: .appInfo) {
                Button("Check for Updates...") {
                    // Future: Sparkle integration
                }
            }
        }

        Settings {
            SettingsView()
                .environmentObject(appState)
        }

        Window("History", id: "history") {
            HistoryView()
                .environmentObject(appState)
                .frame(minWidth: 500, minHeight: 400)
        }

        Window("Voice Health", id: "health") {
            HealthDashboardView()
                .environmentObject(appState)
                .frame(minWidth: 450, minHeight: 550)
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var hotkeyManager: HotkeyManager?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Setup global hotkey monitoring
        hotkeyManager = HotkeyManager.shared
        hotkeyManager?.startListening()

        // Request necessary permissions
        requestPermissions()

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
