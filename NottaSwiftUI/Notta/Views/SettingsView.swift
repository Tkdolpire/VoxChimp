import SwiftUI

struct SettingsView: View {
    var body: some View {
        TabView {
            GeneralSettingsView()
                .tabItem {
                    Label("General", systemImage: "gear")
                }

            TranscriptionSettingsView()
                .tabItem {
                    Label("Transcription", systemImage: "waveform")
                }

            HealthSettingsView()
                .tabItem {
                    Label("Health", systemImage: "heart")
                }

            #if !APPSTORE
            LicenseSettingsView()
                .tabItem {
                    Label("License", systemImage: "key.fill")
                }
            #else
            StoreSettingsView()
                .tabItem {
                    Label("Subscription", systemImage: "creditcard.fill")
                }
            #endif

            AdvancedSettingsView()
                .tabItem {
                    Label("Advanced", systemImage: "wrench.and.screwdriver")
                }
        }
        .frame(width: 450, height: 380)
    }
}

// MARK: - General Settings

struct GeneralSettingsView: View {
    @ObservedObject var settings = SettingsManager.shared

    var body: some View {
        Form {
            Section {
                Picker("Recording Hotkey", selection: $settings.hotkey) {
                    ForEach(HotkeyOption.allCases) { option in
                        Text(option.displayName).tag(option)
                    }
                }
                .pickerStyle(.menu)

                Toggle("Auto-paste transcription", isOn: $settings.autoPaste)
                    .help("Automatically paste transcribed text at cursor position")

                Toggle("Window floats on top", isOn: $settings.floatOnTop)
                    .help("Keep Notta window above other windows")
            } header: {
                Text("Recording")
            }

            Section {
                Toggle("Launch at login", isOn: $settings.launchAtLogin)

                Toggle("Show in menu bar", isOn: $settings.showInMenuBar)
                    .help("Add a menu bar icon for quick access")
            } header: {
                Text("Startup")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - Transcription Settings

struct TranscriptionSettingsView: View {
    @ObservedObject var settings = SettingsManager.shared

    var body: some View {
        Form {
            Section {
                HStack {
                    Image(systemName: "apple.logo")
                        .foregroundStyle(.secondary)
                    Text("Using Apple Speech Recognition")
                }

                Text("Notta uses Apple's on-device speech recognition for fast, private transcription. This improves automatically with macOS updates.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } header: {
                Text("Speech Recognition")
            }

            Section {
                Toggle("Fix grammar and capitalization", isOn: $settings.fixGrammar)
                    .help("Automatically capitalize sentences and fix common contractions")
            } header: {
                Text("Post-Processing")
            }

            Section {
                Toggle("Save audio recordings", isOn: $settings.saveAudio)
                    .help("Keep audio files for voice health analysis")

                if settings.saveAudio {
                    HStack {
                        Text("Storage location:")
                            .foregroundStyle(.secondary)
                        Text("~/.notta_audio/")
                            .font(.caption.monospaced())

                        Spacer()

                        Button("Open Folder") {
                            let url = FileManager.default.homeDirectoryForCurrentUser
                                .appendingPathComponent(".notta_audio")
                            NSWorkspace.shared.open(url)
                        }
                        .buttonStyle(.link)
                    }
                    .font(.caption)
                }
            } header: {
                Text("Audio Storage")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - Health Settings

struct HealthSettingsView: View {
    @ObservedObject var settings = SettingsManager.shared

    var body: some View {
        Form {
            Section {
                Toggle("Enable health notifications", isOn: $settings.healthNotificationsEnabled)
                    .help("Get notified when voice changes suggest fatigue or illness")
                    .onChange(of: settings.healthNotificationsEnabled) { _, enabled in
                        if enabled {
                            Task {
                                await NotificationService.shared.requestPermission()
                            }
                        }
                    }

                if settings.healthNotificationsEnabled {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Fatigue alert threshold:")
                            Spacer()
                            Text("\(settings.fatigueAlertThreshold)%")
                                .foregroundStyle(.secondary)
                        }
                        Slider(
                            value: Binding(
                                get: { Double(settings.fatigueAlertThreshold) },
                                set: { settings.fatigueAlertThreshold = Int($0) }
                            ),
                            in: 30...90,
                            step: 5
                        )

                        HStack {
                            Text("Illness alert threshold:")
                            Spacer()
                            Text("\(settings.illnessAlertThreshold)%")
                                .foregroundStyle(.secondary)
                        }
                        Slider(
                            value: Binding(
                                get: { Double(settings.illnessAlertThreshold) },
                                set: { settings.illnessAlertThreshold = Int($0) }
                            ),
                            in: 30...90,
                            step: 5
                        )
                    }
                }
            } header: {
                Text("Notifications")
            } footer: {
                Text("You'll receive a macOS notification when your voice analysis detects fatigue or illness scores above these thresholds.")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - App Store Subscription Settings

#if APPSTORE
struct StoreSettingsView: View {
    var body: some View {
        Form {
            Section {
                Text("Subscription management coming soon.")
                    .foregroundStyle(.secondary)

                Button("Manage in App Store") {
                    if let url = URL(string: "macappstore://apps.apple.com/account/subscriptions") {
                        NSWorkspace.shared.open(url)
                    }
                }
            } header: {
                Text("Subscription")
            } footer: {
                Text("Your subscription is managed through the App Store.")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}
#endif

// MARK: - Advanced Settings

struct AdvancedSettingsView: View {
    @ObservedObject var updater = UpdaterService.shared
    @State private var showDebugInfo = false

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
                #endif
            } header: {
                Text("Software Updates")
            }

            Section {
                Button("Open Log File") {
                    let url = FileManager.default.homeDirectoryForCurrentUser
                        .appendingPathComponent(".notta.log")
                    NSWorkspace.shared.open(url)
                }

                Button("Open Config Directory") {
                    let url = FileManager.default.homeDirectoryForCurrentUser
                    NSWorkspace.shared.open(url)
                }

                Toggle("Show debug information", isOn: $showDebugInfo)
            } header: {
                Text("Debugging")
            }

            Section {
                VStack(alignment: .leading, spacing: 8) {
                    PermissionRow(
                        title: "Microphone",
                        description: "Required for audio recording",
                        systemImage: "mic.fill"
                    )

                    PermissionRow(
                        title: "Accessibility",
                        description: "Required for auto-paste",
                        systemImage: "accessibility"
                    )

                    PermissionRow(
                        title: "Input Monitoring",
                        description: "Required for global hotkeys",
                        systemImage: "keyboard"
                    )
                }

                Button("Open System Settings") {
                    if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy") {
                        NSWorkspace.shared.open(url)
                    }
                }
            } header: {
                Text("Permissions")
            }

            Section {
                HStack {
                    Text("Version")
                    Spacer()
                    Text(Bundle.main.appVersion)
                        .foregroundStyle(.secondary)
                }

                HStack {
                    Text("Build")
                    Spacer()
                    #if APPSTORE
                    Text("\(Bundle.main.buildNumber) (App Store)")
                        .foregroundStyle(.secondary)
                    #else
                    Text("\(Bundle.main.buildNumber) (Direct)")
                        .foregroundStyle(.secondary)
                    #endif
                }
            } header: {
                Text("About")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

struct PermissionRow: View {
    let title: String
    let description: String
    let systemImage: String

    var body: some View {
        HStack {
            Image(systemName: systemImage)
                .frame(width: 20)
                .foregroundStyle(.secondary)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(.green)
        }
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
}
