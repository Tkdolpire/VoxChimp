import SwiftUI

/// Banner displayed when user is in trial or trial has expired
struct TrialBannerView: View {
    @ObservedObject var licenseManager = LicenseManager.shared
    @State private var showActivation: Bool = false

    var body: some View {
        Group {
            switch licenseManager.state {
            case .trial(let daysRemaining):
                if daysRemaining <= 7 {
                    trialBanner(daysRemaining: daysRemaining)
                }
            case .trialExpired:
                expiredBanner
            case .expired:
                subscriptionExpiredBanner
            default:
                EmptyView()
            }
        }
        .sheet(isPresented: $showActivation) {
            LicenseActivationView()
        }
    }

    // MARK: - Banner Variants

    private func trialBanner(daysRemaining: Int) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "clock.fill")
                .foregroundStyle(daysRemaining <= 3 ? .orange : .blue)

            VStack(alignment: .leading, spacing: 2) {
                Text(daysRemaining <= 3 ? "Trial Ending Soon" : "Trial Mode")
                    .font(.caption.bold())
                Text("\(daysRemaining) day\(daysRemaining == 1 ? "" : "s") remaining")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button("Upgrade") {
                Task {
                    await licenseManager.openPurchasePage()
                }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background {
            RoundedRectangle(cornerRadius: 8)
                .fill(daysRemaining <= 3 ? Color.orange.opacity(0.15) : Color.blue.opacity(0.1))
        }
    }

    private var expiredBanner: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)

            VStack(alignment: .leading, spacing: 2) {
                Text("Trial Expired")
                    .font(.caption.bold())
                Text("Upgrade to continue using Notta")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button("Activate") {
                showActivation = true
            }
            .buttonStyle(.bordered)
            .controlSize(.small)

            Button("Upgrade") {
                Task {
                    await licenseManager.openPurchasePage()
                }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background {
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.orange.opacity(0.15))
        }
    }

    private var subscriptionExpiredBanner: some View {
        HStack(spacing: 12) {
            Image(systemName: "creditcard.fill")
                .foregroundStyle(.red)

            VStack(alignment: .leading, spacing: 2) {
                Text("Subscription Expired")
                    .font(.caption.bold())
                Text("Renew to restore Pro features")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button("Renew") {
                Task {
                    await licenseManager.openCustomerPortal()
                }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background {
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.red.opacity(0.1))
        }
    }
}

// MARK: - Compact Trial Indicator

/// Small indicator for status bar or toolbar
struct TrialIndicator: View {
    @ObservedObject var licenseManager = LicenseManager.shared

    var body: some View {
        Group {
            switch licenseManager.state {
            case .trial(let days):
                HStack(spacing: 4) {
                    Image(systemName: "clock.fill")
                        .font(.caption2)
                    Text("\(days)d")
                        .font(.caption2.monospacedDigit())
                }
                .foregroundStyle(days <= 3 ? .orange : .blue)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background {
                    Capsule()
                        .fill(days <= 3 ? Color.orange.opacity(0.2) : Color.blue.opacity(0.15))
                }
                .help("Trial: \(days) days remaining")

            case .active:
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.caption2)
                    Text("Pro")
                        .font(.caption2.bold())
                }
                .foregroundStyle(.green)
                .help("Notta Pro - Active")

            case .trialExpired, .expired, .invalid:
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.caption2)
                    .foregroundStyle(.orange)
                    .help("License expired or invalid")

            default:
                EmptyView()
            }
        }
    }
}

// MARK: - Feature Lock Overlay

/// Overlay for locked features when trial has expired
struct FeatureLockOverlay: View {
    @ObservedObject var licenseManager = LicenseManager.shared
    let featureName: String

    var body: some View {
        if !licenseManager.state.isUnlocked {
            ZStack {
                Color.black.opacity(0.6)

                VStack(spacing: 16) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 32))
                        .foregroundStyle(.white)

                    Text("\(featureName) Locked")
                        .font(.headline)
                        .foregroundStyle(.white)

                    Text("Upgrade to Notta Pro to unlock this feature")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.8))
                        .multilineTextAlignment(.center)

                    Button("Upgrade Now") {
                        Task {
                            await licenseManager.openPurchasePage()
                        }
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding(24)
            }
        }
    }
}

// MARK: - Preview

#Preview("Trial Banner - 7 days") {
    VStack {
        TrialBannerView()
    }
    .padding()
    .frame(width: 360)
}

#Preview("Trial Indicator") {
    HStack(spacing: 16) {
        TrialIndicator()
    }
    .padding()
}
