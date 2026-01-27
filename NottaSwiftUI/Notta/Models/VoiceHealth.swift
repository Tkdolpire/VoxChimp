import Foundation

struct VoiceHealthMetrics: Codable, Equatable {
    let timestamp: Date
    let pitchHz: Double
    let jitterPercent: Double
    let shimmerPercent: Double
    let hnrDb: Double
    let speechRate: Double

    var fatigueScore: Int
    var illnessScore: Int
    var recommendation: String
    var indicators: [HealthIndicator]

    init(
        timestamp: Date = Date(),
        pitchHz: Double = 0,
        jitterPercent: Double = 0,
        shimmerPercent: Double = 0,
        hnrDb: Double = 0,
        speechRate: Double = 0,
        fatigueScore: Int = 0,
        illnessScore: Int = 0,
        recommendation: String = "",
        indicators: [HealthIndicator] = []
    ) {
        self.timestamp = timestamp
        self.pitchHz = pitchHz
        self.jitterPercent = jitterPercent
        self.shimmerPercent = shimmerPercent
        self.hnrDb = hnrDb
        self.speechRate = speechRate
        self.fatigueScore = fatigueScore
        self.illnessScore = illnessScore
        self.recommendation = recommendation
        self.indicators = indicators
    }
}

struct HealthIndicator: Codable, Equatable, Identifiable {
    let id: UUID
    let name: String
    let status: IndicatorStatus
    let description: String
    let changePercent: Double?

    init(
        id: UUID = UUID(),
        name: String,
        status: IndicatorStatus,
        description: String,
        changePercent: Double? = nil
    ) {
        self.id = id
        self.name = name
        self.status = status
        self.description = description
        self.changePercent = changePercent
    }
}

enum IndicatorStatus: String, Codable {
    case excellent
    case good
    case stable
    case monitor
    case attention

    var color: String {
        switch self {
        case .excellent, .good: return "green"
        case .stable: return "blue"
        case .monitor: return "yellow"
        case .attention: return "red"
        }
    }

    var icon: String {
        switch self {
        case .excellent: return "checkmark.circle.fill"
        case .good: return "checkmark.circle"
        case .stable: return "equal.circle"
        case .monitor: return "exclamationmark.triangle"
        case .attention: return "exclamationmark.circle.fill"
        }
    }
}

struct BaselineMetrics: Codable {
    let pitchHz: Double
    let jitterPercent: Double
    let shimmerPercent: Double
    let hnrDb: Double
    let speechRate: Double
    let sampleCount: Int
    let lastUpdated: Date

    var isValid: Bool {
        sampleCount >= 5
    }

    static let sample = BaselineMetrics(
        pitchHz: 132.4,
        jitterPercent: 2.34,
        shimmerPercent: 14.91,
        hnrDb: 15.2,
        speechRate: 150.0,
        sampleCount: 12,
        lastUpdated: Date().addingTimeInterval(-86400)
    )
}

struct HealthDataPoint: Identifiable {
    let id = UUID()
    let date: Date
    let fatigueScore: Double
    let illnessScore: Double
}

// MARK: - Sample Data for Previews

extension VoiceHealthMetrics {
    static let sample = VoiceHealthMetrics(
        timestamp: Date(),
        pitchHz: 119.1,
        jitterPercent: 2.03,
        shimmerPercent: 13.03,
        hnrDb: 13.8,
        speechRate: 145.0,
        fatigueScore: 15,
        illnessScore: 45,
        recommendation: "Your voice shows some changes. Stay hydrated and get adequate rest.",
        indicators: [
            HealthIndicator(name: "Pitch", status: .monitor, description: "10% lower than baseline", changePercent: -10),
            HealthIndicator(name: "Clarity", status: .good, description: "Within normal range"),
            HealthIndicator(name: "Energy", status: .stable, description: "Consistent with recent recordings")
        ]
    )

    static let baseline = BaselineMetrics(
        pitchHz: 132.4,
        jitterPercent: 2.34,
        shimmerPercent: 14.91,
        hnrDb: 15.2,
        speechRate: 150.0,
        sampleCount: 12,
        lastUpdated: Date().addingTimeInterval(-86400)
    )
}

extension HealthDataPoint {
    static let sampleWeekData: [HealthDataPoint] = (0..<7).map { day in
        HealthDataPoint(
            date: Date().addingTimeInterval(Double(-day * 86400)),
            fatigueScore: Double.random(in: 10...40),
            illnessScore: Double.random(in: 5...30)
        )
    }.reversed()
}
