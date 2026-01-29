import SwiftUI

#if !APPSTORE

/// Settings view for license management
struct LicenseSettingsView: View {
    @ObservedObject var licenseManager = LicenseManager.shared
    @State private var licenseKeyInput: String = ""
    @State private var isActivating: Bool = false
    @State private var showActivationSuccess: Bool = false

    var body: some View {
        Form {
            // Current Status Section
            Section {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Status")
                            .foregroundStyle(.secondary)
                        Text(licenseManager.state.displayName)
                            .font(.headline)
                    }

                    Spacer()

                    statusBadge
                }

                if let email = licenseManager.email {
                    HStack {
                        Text("Account")
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text(email)
                            .foregroundStyle(.secondary)
                    }
                }

                if case .trial(let days) = licenseManager.state {
                    trialProgressView(daysRemaining: days)
                }
            } header: {
                Text("License Status")
            }

            // Activation Section
            Section {
                VStack(alignment: .leading, spacing: 12) {
                    TextField("NOTTA-XXXX-XXXX-XXXX-XXXX", text: $licenseKeyInput)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(.body, design: .monospaced))
                        .onChange(of: licenseKeyInput) { _, newValue in
                            // Auto-format as user types
                            if newValue.count > licenseKeyInput.count {
                                licenseKeyInput = LicenseKeyValidator.format(newValue)
                            }
                        }
                        .disabled(isActivating)

                    HStack {
                        Button("Activate License") {
                            activateLicense()
                        }
                        .disabled(licenseKeyInput.isEmpty || isActivating)
                        .buttonStyle(.borderedProminent)

                        if isActivating {
                            ProgressView()
                                .scaleEffect(0.7)
                        }

                        if showActivationSuccess {
                            Label("Activated!", systemImage: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                        }
                    }
                }

                if let error = licenseManager.lastError {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.caption)
                }
            } header: {
                Text("Activate License")
            } footer: {
                Text("Enter your license key to unlock Notta Pro features.")
            }

            // Purchase Section
            if licenseManager.state != .active {
                Section {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            VStack(alignment: .leading) {
                                Text("Notta Pro Monthly")
                                    .font(.headline)
                                Text("Unlimited transcriptions & voice health")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text("$7.99/mo")
                                .font(.headline)
                        }

                        Button("Subscribe Now") {
                            Task {
                                await licenseManager.openPurchasePage(plan: "monthly")
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .frame(maxWidth: .infinity)

                        HStack {
                            VStack(alignment: .leading) {
                                Text("Notta Pro Annual")
                                    .font(.headline)
                                Text("Save 25% with annual billing")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            VStack(alignment: .trailing) {
                                Text("$59.99/yr")
                                    .font(.headline)
                                Text("~$5/mo")
                                    .font(.caption)
                                    .foregroundStyle(.green)
                            }
                        }
                        .padding(.top, 8)

                        Button("Subscribe Annually") {
                            Task {
                                await licenseManager.openPurchasePage(plan: "annual")
                            }
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.large)
                        .frame(maxWidth: .infinity)
                    }
                } header: {
                    Text("Upgrade to Pro")
                }
            }

            // Manage Subscription Section
            if licenseManager.state == .active {
                Section {
                    Button("Manage Subscription") {
                        Task {
                            await licenseManager.openCustomerPortal()
                        }
                    }

                    Button("Deactivate License", role: .destructive) {
                        licenseManager.deactivateLicense()
                        licenseKeyInput = ""
                    }
                } header: {
                    Text("Subscription")
                }
            }
        }
        .formStyle(.grouped)
        .padding()
        .onAppear {
            if let key = licenseManager.licenseKey {
                licenseKeyInput = key
            }
        }
    }

    // MARK: - Subviews

    @ViewBuilder
    private var statusBadge: some View {
        let (color, icon): (Color, String) = {
            switch licenseManager.state {
            case .active:
                return (.green, "checkmark.seal.fill")
            case .trial:
                return (.blue, "clock.fill")
            case .trialExpired, .expired:
                return (.orange, "exclamationmark.triangle.fill")
            case .invalid:
                return (.red, "xmark.circle.fill")
            case .unknown:
                return (.gray, "questionmark.circle.fill")
            }
        }()

        Image(systemName: icon)
            .foregroundStyle(color)
            .imageScale(.large)
    }

    private func trialProgressView(daysRemaining: Int) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Trial Progress")
                    .foregroundStyle(.secondary)
                Spacer()
                Text("\(daysRemaining) days remaining")
                    .foregroundStyle(.blue)
                    .font(.caption)
            }

            ProgressView(value: Double(7 - daysRemaining), total: 7)
                .tint(daysRemaining <= 3 ? .orange : .blue)
        }
    }

    // MARK: - Actions

    private func activateLicense() {
        isActivating = true
        showActivationSuccess = false

        Task {
            let success = await licenseManager.activateLicense(licenseKeyInput)

            isActivating = false

            if success {
                showActivationSuccess = true
                // Hide success message after 3 seconds
                try? await Task.sleep(for: .seconds(3))
                showActivationSuccess = false
            }
        }
    }
}

// MARK: - Activation Sheet View

/// Standalone view for license activation (can be shown as a sheet)
struct LicenseActivationView: View {
    @ObservedObject var licenseManager = LicenseManager.shared
    @Environment(\.dismiss) private var dismiss
    @State private var licenseKeyInput: String = ""
    @State private var isActivating: Bool = false

    var body: some View {
        VStack(spacing: 24) {
            // Header
            VStack(spacing: 8) {
                Image(systemName: "key.fill")
                    .font(.system(size: 48))
                    .foregroundStyle(.accent)

                Text("Activate Notta Pro")
                    .font(.title2.bold())

                Text("Enter your license key to unlock all features")
                    .foregroundStyle(.secondary)
            }

            // License Key Input
            VStack(alignment: .leading, spacing: 8) {
                TextField("NOTTA-XXXX-XXXX-XXXX-XXXX", text: $licenseKeyInput)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(.body, design: .monospaced))
                    .onChange(of: licenseKeyInput) { _, newValue in
                        if newValue.count > licenseKeyInput.count {
                            licenseKeyInput = LicenseKeyValidator.format(newValue)
                        }
                    }
                    .disabled(isActivating)

                if let error = licenseManager.lastError {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.caption)
                }
            }

            // Buttons
            VStack(spacing: 12) {
                Button {
                    activateLicense()
                } label: {
                    if isActivating {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                    } else {
                        Text("Activate")
                            .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(licenseKeyInput.isEmpty || isActivating)

                Button("Buy License") {
                    Task {
                        await licenseManager.openPurchasePage()
                    }
                }
                .buttonStyle(.bordered)
                .controlSize(.large)

                Button("Continue Trial") {
                    dismiss()
                }
                .foregroundStyle(.secondary)
            }
        }
        .padding(32)
        .frame(width: 400)
    }

    private func activateLicense() {
        isActivating = true

        Task {
            let success = await licenseManager.activateLicense(licenseKeyInput)
            isActivating = false

            if success {
                dismiss()
            }
        }
    }
}

#else

// MARK: - App Store Stubs

/// App Store version - placeholder that shows StoreKit info
struct LicenseSettingsView: View {
    var body: some View {
        Form {
            Section {
                Text("Your subscription is managed through the App Store.")
                    .foregroundStyle(.secondary)

                Button("Manage Subscription") {
                    if let url = URL(string: "https://apps.apple.com/account/subscriptions") {
                        NSWorkspace.shared.open(url)
                    }
                }
            } header: {
                Text("Subscription")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

/// App Store version - not used
struct LicenseActivationView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 16) {
            Text("Subscription managed via App Store")
                .foregroundStyle(.secondary)
            Button("Close") {
                dismiss()
            }
        }
        .padding(32)
        .frame(width: 400)
    }
}

#endif

// MARK: - Preview

#Preview("License Settings") {
    LicenseSettingsView()
        .frame(width: 450)
}

#Preview("Activation Sheet") {
    LicenseActivationView()
}
