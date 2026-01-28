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

            LicenseSettingsView()
                .tabItem {
                    Label("License", systemImage: "key.fill")
                }

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
                Picker("Whisper Model", selection: $settings.whisperModel) {
                    ForEach(WhisperModel.allCases) { model in
                        VStack(alignment: .leading) {
                            Text(model.displayName)
                            Text(model.description)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .tag(model)
                    }
                }
                .pickerStyle(.radioGroup)

                Text("Larger models are more accurate but slower. The 'small' model works well for most uses.")
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
    @State private var baselineSamples = 12
    @State private var enableNotifications = true
    @State private var fatigueThreshold = 60.0
    @State private var illnessThreshold = 60.0

    var body: some View {
        Form {
            Section {
                HStack {
                    Text("Baseline samples collected:")
                    Spacer()
                    Text("\(baselineSamples)")
                        .foregroundStyle(.secondary)
                }

                Button("Reset Baseline") {
                    // TODO: Implement baseline reset
                }
                .foregroundStyle(.red)
            } header: {
                Text("Voice Baseline")
            }

            Section {
                Toggle("Enable health notifications", isOn: $enableNotifications)
                    .help("Get notified when voice changes suggest fatigue or illness")

                if enableNotifications {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Fatigue alert threshold:")
                            Spacer()
                            Text("\(Int(fatigueThreshold))%")
                                .foregroundStyle(.secondary)
                        }
                        Slider(value: $fatigueThreshold, in: 30...90, step: 5)

                        HStack {
                            Text("Illness alert threshold:")
                            Spacer()
                            Text("\(Int(illnessThreshold))%")
                                .foregroundStyle(.secondary)
                        }
                        Slider(value: $illnessThreshold, in: 30...90, step: 5)
                    }
                }
            } header: {
                Text("Notifications")
            }

            Section {
                Button("Export Health Data...") {
                    // TODO: Implement export
                }

                Button("Clear All Health Data") {
                    // TODO: Implement clear with confirmation
                }
                .foregroundStyle(.red)
            } header: {
                Text("Data Management")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - Advanced Settings

struct AdvancedSettingsView: View {
    @ObservedObject var updater = UpdaterService.shared
    @State private var showDebugInfo = false

    var body: some View {
        Form {
            Section {
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
                    Text(Bundle.main.buildNumber)
                        .foregroundStyle(.secondary)
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
