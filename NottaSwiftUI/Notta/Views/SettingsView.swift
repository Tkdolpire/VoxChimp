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
        .tint(.brandOrange)
    }
}

// MARK: - Transcription Settings

struct TranscriptionSettingsView: View {
    @ObservedObject var settings = SettingsManager.shared
    @StateObject var modelManager = ModelManager.shared
    @StateObject var transcriptionManager = TranscriptionManager.shared
    @StateObject var translationService = TranslationService.shared
    @State private var showModelDownloadAlert = false
    @State private var modelToDownload: WhisperModel?

    var body: some View {
        Form {
            Section {
                Picker("Speech Engine", selection: $settings.transcriptionBackend) {
                    ForEach(TranscriptionBackend.allCases) { backend in
                        HStack {
                            Image(systemName: backend.iconName)
                            VStack(alignment: .leading) {
                                Text(backend.displayName)
                                Text(backend.description)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .tag(backend)
                    }
                }
                .pickerStyle(.radioGroup)
                .onChange(of: settings.transcriptionBackend) { _, newBackend in
                    if newBackend == .whisperKit {
                        // Show download alert if model not ready
                        if !transcriptionManager.isModelReady && !modelManager.isDownloading {
                            modelToDownload = settings.whisperModel
                            showModelDownloadAlert = true
                        }
                    }
                }
            } header: {
                Text("Speech Recognition")
            }

            // Model selection (Whisper only)
            if settings.transcriptionBackend == .whisperKit {
                Section {
                    Picker("Model", selection: $settings.whisperModel) {
                        ForEach(WhisperModel.allCases) { model in
                            HStack {
                                VStack(alignment: .leading) {
                                    Text(model.displayName)
                                    Text("\(model.accuracyDescription) accuracy, \(model.speedDescription.lowercased())")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                if modelManager.isDownloaded(model) {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundStyle(.green)
                                } else {
                                    Text(model.downloadSizeFormatted)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .tag(model)
                        }
                    }
                    .pickerStyle(.radioGroup)
                    .onChange(of: settings.whisperModel) { _, newModel in
                        // Only prompt if model not ready and not already downloading
                        if !modelManager.isDownloading {
                            modelToDownload = newModel
                            showModelDownloadAlert = true
                        }
                    }

                    // Download/Loading progress
                    if modelManager.isDownloading || transcriptionManager.isLoadingModel {
                        HStack {
                            ProgressView()
                                .scaleEffect(0.8)
                            if !transcriptionManager.modelLoadingProgress.isEmpty {
                                Text(transcriptionManager.modelLoadingProgress)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            } else {
                                Text("Downloading \(modelManager.downloadingModel?.displayName ?? "model")...")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            if modelManager.isDownloading {
                                Button("Cancel") {
                                    modelManager.cancelDownload()
                                }
                                .buttonStyle(.link)
                                .font(.caption)
                            }
                        }
                    }

                    // Model status
                    if transcriptionManager.isModelReady && !transcriptionManager.isLoadingModel {
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                            Text("Model ready")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    } else if let error = transcriptionManager.error {
                        HStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(.orange)
                            Text(error)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                } header: {
                    Text("Whisper Model")
                } footer: {
                    Text("Larger models are more accurate but slower. Models are downloaded once and stored locally.")
                }

                // Storage info
                Section {
                    HStack {
                        Text("Models storage")
                        Spacer()
                        Text(modelManager.formattedStorageUsed())
                            .foregroundStyle(.secondary)
                    }
                } header: {
                    Text("Storage")
                }
            }

            Section {
                Toggle("Fix grammar and capitalization", isOn: $settings.fixGrammar)
                    .help("Automatically capitalize sentences and fix common contractions")
            } header: {
                Text("Post-Processing")
            }

            // Translation Section
            if translationService.isAvailable {
                Section {
                    Toggle("Translate to another language", isOn: $settings.translationEnabled)
                        .help("Translate transcribed text before pasting")

                    if settings.translationEnabled {
                        Picker("Target Language", selection: $settings.targetLanguage) {
                            ForEach(TranslationLanguage.enabledCases) { lang in
                                HStack {
                                    Text(lang.displayName)
                                    Spacer()
                                    switch translationService.getLanguageStatus(lang) {
                                    case .installed:
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundStyle(.green)
                                            .font(.caption)
                                    case .needsDownload:
                                        Image(systemName: "arrow.down.circle")
                                            .foregroundStyle(.orange)
                                            .font(.caption)
                                    default:
                                        EmptyView()
                                    }
                                }
                                .tag(lang)
                            }
                        }
                        .pickerStyle(.menu)
                        .onAppear {
                            Task {
                                await translationService.checkAllLanguageStatuses()
                            }
                        }
                        .onChange(of: settings.targetLanguage) { _, newLang in
                            Task {
                                await translationService.checkLanguageStatus(newLang)
                            }
                        }

                        // Language status
                        HStack {
                            switch translationService.getLanguageStatus(settings.targetLanguage) {
                            case .installed:
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(.green)
                                Text("\(settings.targetLanguage.displayName) is ready")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            case .needsDownload:
                                Image(systemName: "arrow.down.circle")
                                    .foregroundStyle(.orange)
                                Text("\(settings.targetLanguage.displayName) needs to be downloaded")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            case .checking:
                                ProgressView()
                                    .scaleEffect(0.7)
                                Text("Checking availability...")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            case .unsupported:
                                Image(systemName: "xmark.circle")
                                    .foregroundStyle(.red)
                                Text("\(settings.targetLanguage.displayName) is not supported")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            case .unknown:
                                Image(systemName: "questionmark.circle")
                                    .foregroundStyle(.secondary)
                                Text("Status unknown")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }

                        if translationService.isDownloadingModel {
                            HStack {
                                ProgressView()
                                    .scaleEffect(0.8)
                                Text(translationService.downloadProgress)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }

                        if let error = translationService.error {
                            HStack {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundStyle(.orange)
                                Text(error)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }

                        // Button to open Translate app for downloading
                        if translationService.getLanguageStatus(settings.targetLanguage) == .needsDownload {
                            Button {
                                translationService.openTranslateApp()
                            } label: {
                                Label("Open Translate App to Download \(settings.targetLanguage.displayName)", systemImage: "arrow.down.circle")
                            }
                            .buttonStyle(.borderedProminent)
                            .font(.caption)
                        }

                        // Link to open Translate app
                        Button {
                            translationService.openTranslateApp()
                        } label: {
                            Label("Manage Languages in Translate App", systemImage: "arrow.up.forward.app")
                        }
                        .buttonStyle(.link)
                        .font(.caption)
                    }
                } header: {
                    Text("Translation")
                } footer: {
                    Text("Translation happens on-device. Languages must be downloaded via the Translate app first.")
                }
            } else {
                Section {
                    Label("Translation requires macOS 15.0 or later", systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.secondary)
                } header: {
                    Text("Translation")
                }
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
        .tint(.brandOrange)
        .alert("Download Model?", isPresented: $showModelDownloadAlert) {
            Button("Download") {
                Task {
                    // WhisperKitService.loadModel handles download automatically
                    await transcriptionManager.prepareWhisperModel()
                }
            }
            Button("Cancel", role: .cancel) {
                // Revert to Apple Speech if user cancels and model not ready
                if !transcriptionManager.isModelReady {
                    settings.transcriptionBackend = .appleSpeech
                }
            }
        } message: {
            if let model = modelToDownload {
                Text("The \(model.displayName) model (\(model.downloadSizeFormatted)) needs to be downloaded. This only happens once.")
            }
        }
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
        .tint(.brandOrange)
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
        .tint(.brandOrange)
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
                .foregroundStyle(Color.statusSuccess)
        }
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
}
