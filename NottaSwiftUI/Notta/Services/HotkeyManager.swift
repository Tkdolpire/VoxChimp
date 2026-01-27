import Foundation
import Carbon
import AppKit

/// Manages global hotkey detection for hold-to-record functionality
/// Requires Accessibility permissions in System Settings
class HotkeyManager: ObservableObject {
    static let shared = HotkeyManager()

    @Published var isListening = false
    @Published var isHotkeyPressed = false

    private var localMonitor: Any?
    private var globalMonitor: Any?
    private var flagsMonitor: Any?

    private init() {}

    // MARK: - Start/Stop Listening

    func startListening() {
        guard !isListening else { return }

        let settings = SettingsManager.shared

        // Local monitor (works within app without permissions)
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .flagsChanged) { [weak self] event in
            self?.handleFlagsChanged(event, hotkey: settings.hotkey)
            return event
        }

        // Global monitor (requires accessibility permission)
        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .flagsChanged) { [weak self] event in
            self?.handleFlagsChanged(event, hotkey: settings.hotkey)
        }

        isListening = true
        print("Hotkey listener started for: \(settings.hotkey.displayName)")

        // Check accessibility permission
        if !checkAccessibilityPermission() {
            print("Warning: Accessibility permission not granted. Global hotkeys won't work outside the app.")
        }
    }

    func stopListening() {
        if let monitor = localMonitor {
            NSEvent.removeMonitor(monitor)
            localMonitor = nil
        }
        if let monitor = globalMonitor {
            NSEvent.removeMonitor(monitor)
            globalMonitor = nil
        }

        isListening = false
        isHotkeyPressed = false
        print("Hotkey listener stopped")
    }

    // MARK: - Event Handling

    private func handleFlagsChanged(_ event: NSEvent, hotkey: HotkeyOption) {
        let flags = event.modifierFlags

        // Detect if the configured hotkey is pressed
        // Using simplified detection since keyCode isn't reliable for modifier-only events
        let simplifiedPressed: Bool
        switch hotkey {
        case .leftOption, .rightOption:
            simplifiedPressed = flags.contains(.option) && !flags.contains(.command) && !flags.contains(.control)
        case .leftControl, .rightControl:
            simplifiedPressed = flags.contains(.control) && !flags.contains(.command) && !flags.contains(.option)
        case .capsLock:
            simplifiedPressed = flags.contains(.capsLock)
        case .fn:
            simplifiedPressed = flags.contains(.function)
        }

        if simplifiedPressed != isHotkeyPressed {
            DispatchQueue.main.async { [weak self] in
                self?.isHotkeyPressed = simplifiedPressed

                if simplifiedPressed {
                    print("Hotkey pressed")
                    NotificationCenter.default.post(name: .hotkeyPressed, object: nil)
                } else {
                    print("Hotkey released")
                    NotificationCenter.default.post(name: .hotkeyReleased, object: nil)
                }
            }
        }
    }

    // MARK: - Permissions

    private func checkAccessibilityPermission() -> Bool {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: false]
        return AXIsProcessTrustedWithOptions(options as CFDictionary)
    }

    func requestAccessibilityPermission() {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true]
        AXIsProcessTrustedWithOptions(options as CFDictionary)
    }

    func openAccessibilitySettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }

    var hasAccessibilityPermission: Bool {
        checkAccessibilityPermission()
    }
}
