import SwiftUI

// MARK: - Brand Colors

extension Color {
    // Primary Brand Colors
    static let brandOrange = Color(hex: "F5A623")
    static let brandYellow = Color(hex: "FFD54F")
    static let brandNavy = Color(hex: "2C3E50")
    static let brandCream = Color(hex: "FFF9F0")
    static let brandSky = Color(hex: "4A90D9")
    static let brandGray = Color(hex: "7F8C8D")

    // Semantic Colors - App-wide usage
    static let appBackground = Color.brandCream
    static let cardBackground = Color.white
    static let primaryText = Color.brandNavy
    static let secondaryText = Color.brandGray
    static let brandAccent = Color.brandOrange

    // Status Colors - Keep universal meanings
    static let statusSuccess = Color.green
    static let statusWarning = Color.brandOrange
    static let statusError = Color.red
    static let statusInfo = Color.brandSky

    // Recording Colors
    static let recordingActive = Color.red  // Keep red for safety/visual clarity
    static let recordingIdle = Color.brandOrange

    // Health Score Colors
    static let healthGood = Color.green
    static let healthModerate = Color.brandYellow
    static let healthWarning = Color.brandOrange
    static let healthAlert = Color.red

    // Trial/License Colors
    static let trialNormal = Color.brandOrange
    static let trialUrgent = Color.brandOrange
    static let licenseActive = Color.green
    static let licenseTrial = Color.brandOrange
    static let licenseExpired = Color.red
}

// MARK: - Hex Initializer

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }

        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Gradients

extension LinearGradient {
    static let brandGradient = LinearGradient(
        colors: [.brandOrange, .brandYellow],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static let recordingGradient = LinearGradient(
        colors: [.red, .red.opacity(0.8)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    static let idleButtonGradient = LinearGradient(
        colors: [.brandOrange, .brandYellow],
        startPoint: .top,
        endPoint: .bottom
    )
}

// MARK: - Shadows

extension View {
    func warmShadow(radius: CGFloat = 10, y: CGFloat = 4) -> some View {
        self.shadow(color: .brandOrange.opacity(0.3), radius: radius, y: y)
    }

    func cardShadow() -> some View {
        self.shadow(color: .brandOrange.opacity(0.1), radius: 4, y: 2)
    }
}

// MARK: - View Modifiers

struct WarmCardStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .background(.regularMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.brandOrange.opacity(0.15), lineWidth: 1)
            )
            .shadow(color: .brandOrange.opacity(0.1), radius: 4, y: 2)
    }
}

extension View {
    func warmCardStyle() -> some View {
        modifier(WarmCardStyle())
    }
}
