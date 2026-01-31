import Foundation

enum TranslationLanguage: String, CaseIterable, Identifiable, Codable {
    case none = "none"
    case spanish = "es"
    case french = "fr"
    case german = "de"
    case italian = "it"
    case portuguese = "pt"
    case chineseSimplified = "zh-Hans"
    case japanese = "ja"
    case korean = "ko"
    case arabic = "ar"
    case russian = "ru"
    case hindi = "hi"
    case dutch = "nl"
    case polish = "pl"
    case turkish = "tr"
    case vietnamese = "vi"
    case thai = "th"
    case indonesian = "id"
    case ukrainian = "uk"

    var id: String { rawValue }

    var isEnabled: Bool { self != .none }

    var displayName: String {
        switch self {
        case .none: return "None (no translation)"
        case .spanish: return "Spanish"
        case .french: return "French"
        case .german: return "German"
        case .italian: return "Italian"
        case .portuguese: return "Portuguese"
        case .chineseSimplified: return "Chinese (Simplified)"
        case .japanese: return "Japanese"
        case .korean: return "Korean"
        case .arabic: return "Arabic"
        case .russian: return "Russian"
        case .hindi: return "Hindi"
        case .dutch: return "Dutch"
        case .polish: return "Polish"
        case .turkish: return "Turkish"
        case .vietnamese: return "Vietnamese"
        case .thai: return "Thai"
        case .indonesian: return "Indonesian"
        case .ukrainian: return "Ukrainian"
        }
    }

    var flagEmoji: String {
        switch self {
        case .none: return ""
        case .spanish: return "🇪🇸"
        case .french: return "🇫🇷"
        case .german: return "🇩🇪"
        case .italian: return "🇮🇹"
        case .portuguese: return "🇵🇹"
        case .chineseSimplified: return "🇨🇳"
        case .japanese: return "🇯🇵"
        case .korean: return "🇰🇷"
        case .arabic: return "🇸🇦"
        case .russian: return "🇷🇺"
        case .hindi: return "🇮🇳"
        case .dutch: return "🇳🇱"
        case .polish: return "🇵🇱"
        case .turkish: return "🇹🇷"
        case .vietnamese: return "🇻🇳"
        case .thai: return "🇹🇭"
        case .indonesian: return "🇮🇩"
        case .ukrainian: return "🇺🇦"
        }
    }

    @available(macOS 15.0, *)
    var locale: Locale.Language {
        Locale.Language(identifier: rawValue)
    }

    /// All languages excluding "none" - use this for the picker
    static var enabledCases: [TranslationLanguage] {
        allCases.filter { $0.isEnabled }
    }
}
