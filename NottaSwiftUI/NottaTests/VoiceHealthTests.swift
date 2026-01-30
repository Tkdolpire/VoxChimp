import XCTest
@testable import Notta

final class VoiceHealthTests: XCTestCase {

    // MARK: - VoiceHealthMetrics

    func testVoiceHealthMetricsCreation() {
        let metrics = VoiceHealthMetrics(
            timestamp: Date(),
            pitchHz: 150.0,
            jitterPercent: 2.5,
            shimmerPercent: 10.0,
            hnrDb: 15.0,
            speechRate: 120.0,
            fatigueScore: 25,
            illnessScore: 10,
            recommendation: "Your voice sounds healthy.",
            indicators: []
        )

        XCTAssertEqual(metrics.pitchHz, 150.0)
        XCTAssertEqual(metrics.jitterPercent, 2.5)
        XCTAssertEqual(metrics.shimmerPercent, 10.0)
        XCTAssertEqual(metrics.hnrDb, 15.0)
        XCTAssertEqual(metrics.speechRate, 120.0)
        XCTAssertEqual(metrics.fatigueScore, 25)
        XCTAssertEqual(metrics.illnessScore, 10)
    }

    func testVoiceHealthMetricsDefaultValues() {
        let metrics = VoiceHealthMetrics()

        XCTAssertEqual(metrics.pitchHz, 0)
        XCTAssertEqual(metrics.jitterPercent, 0)
        XCTAssertEqual(metrics.shimmerPercent, 0)
        XCTAssertEqual(metrics.hnrDb, 0)
        XCTAssertEqual(metrics.speechRate, 0)
        XCTAssertEqual(metrics.fatigueScore, 0)
        XCTAssertEqual(metrics.illnessScore, 0)
        XCTAssertTrue(metrics.recommendation.isEmpty)
        XCTAssertTrue(metrics.indicators.isEmpty)
    }

    func testVoiceHealthMetricsCodable() throws {
        let original = VoiceHealthMetrics(
            timestamp: Date(),
            pitchHz: 145.0,
            jitterPercent: 3.0,
            shimmerPercent: 12.0,
            hnrDb: 14.0,
            speechRate: 110.0,
            fatigueScore: 30,
            illnessScore: 20,
            recommendation: "Test recommendation",
            indicators: [
                HealthIndicator(name: "Pitch", status: .stable, description: "Normal")
            ]
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(VoiceHealthMetrics.self, from: data)

        XCTAssertEqual(decoded.pitchHz, original.pitchHz)
        XCTAssertEqual(decoded.fatigueScore, original.fatigueScore)
        XCTAssertEqual(decoded.illnessScore, original.illnessScore)
        XCTAssertEqual(decoded.indicators.count, 1)
    }

    func testVoiceHealthMetricsSample() {
        let sample = VoiceHealthMetrics.sample

        XCTAssertGreaterThan(sample.pitchHz, 0)
        XCTAssertGreaterThan(sample.jitterPercent, 0)
        XCTAssertGreaterThan(sample.shimmerPercent, 0)
        XCTAssertFalse(sample.recommendation.isEmpty)
    }

    // MARK: - HealthIndicator

    func testHealthIndicatorCreation() {
        let indicator = HealthIndicator(
            name: "Pitch",
            status: .monitor,
            description: "Lower than usual",
            changePercent: -10.0
        )

        XCTAssertEqual(indicator.name, "Pitch")
        XCTAssertEqual(indicator.status, .monitor)
        XCTAssertEqual(indicator.description, "Lower than usual")
        XCTAssertEqual(indicator.changePercent, -10.0)
    }

    func testHealthIndicatorWithoutChangePercent() {
        let indicator = HealthIndicator(
            name: "Clarity",
            status: .good,
            description: "Within normal range"
        )

        XCTAssertNil(indicator.changePercent)
    }

    func testHealthIndicatorHasUniqueID() {
        let i1 = HealthIndicator(name: "Test", status: .stable, description: "Test")
        let i2 = HealthIndicator(name: "Test", status: .stable, description: "Test")

        XCTAssertNotEqual(i1.id, i2.id)
    }

    func testHealthIndicatorCodable() throws {
        let original = HealthIndicator(
            name: "Voice Stability",
            status: .attention,
            description: "Needs attention",
            changePercent: 25.5
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(HealthIndicator.self, from: data)

        XCTAssertEqual(decoded.id, original.id)
        XCTAssertEqual(decoded.name, original.name)
        XCTAssertEqual(decoded.status, original.status)
        XCTAssertEqual(decoded.changePercent, original.changePercent)
    }

    // MARK: - IndicatorStatus

    func testIndicatorStatusColors() {
        XCTAssertEqual(IndicatorStatus.excellent.color, "green")
        XCTAssertEqual(IndicatorStatus.good.color, "green")
        XCTAssertEqual(IndicatorStatus.stable.color, "blue")
        XCTAssertEqual(IndicatorStatus.monitor.color, "yellow")
        XCTAssertEqual(IndicatorStatus.attention.color, "red")
    }

    func testIndicatorStatusIcons() {
        XCTAssertEqual(IndicatorStatus.excellent.icon, "checkmark.circle.fill")
        XCTAssertEqual(IndicatorStatus.good.icon, "checkmark.circle")
        XCTAssertEqual(IndicatorStatus.stable.icon, "equal.circle")
        XCTAssertEqual(IndicatorStatus.monitor.icon, "exclamationmark.triangle")
        XCTAssertEqual(IndicatorStatus.attention.icon, "exclamationmark.circle.fill")
    }

    func testIndicatorStatusCodable() throws {
        let statuses: [IndicatorStatus] = [.excellent, .good, .stable, .monitor, .attention]

        for status in statuses {
            let encoder = JSONEncoder()
            let data = try encoder.encode(status)

            let decoder = JSONDecoder()
            let decoded = try decoder.decode(IndicatorStatus.self, from: data)

            XCTAssertEqual(decoded, status)
        }
    }

    // MARK: - BaselineMetrics

    func testBaselineMetricsCreation() {
        let baseline = BaselineMetrics(
            pitchHz: 140.0,
            jitterPercent: 2.0,
            shimmerPercent: 15.0,
            hnrDb: 16.0,
            speechRate: 130.0,
            sampleCount: 10,
            lastUpdated: Date()
        )

        XCTAssertEqual(baseline.pitchHz, 140.0)
        XCTAssertEqual(baseline.jitterPercent, 2.0)
        XCTAssertEqual(baseline.shimmerPercent, 15.0)
        XCTAssertEqual(baseline.hnrDb, 16.0)
        XCTAssertEqual(baseline.speechRate, 130.0)
        XCTAssertEqual(baseline.sampleCount, 10)
    }

    func testBaselineMetricsIsValidWithEnoughSamples() {
        let baseline = BaselineMetrics(
            pitchHz: 140.0,
            jitterPercent: 2.0,
            shimmerPercent: 15.0,
            hnrDb: 16.0,
            speechRate: 130.0,
            sampleCount: 5,
            lastUpdated: Date()
        )

        XCTAssertTrue(baseline.isValid)
    }

    func testBaselineMetricsIsInvalidWithFewSamples() {
        let baseline = BaselineMetrics(
            pitchHz: 140.0,
            jitterPercent: 2.0,
            shimmerPercent: 15.0,
            hnrDb: 16.0,
            speechRate: 130.0,
            sampleCount: 4,
            lastUpdated: Date()
        )

        XCTAssertFalse(baseline.isValid)
    }

    func testBaselineMetricsIsInvalidWithZeroSamples() {
        let baseline = BaselineMetrics(
            pitchHz: 0,
            jitterPercent: 0,
            shimmerPercent: 0,
            hnrDb: 0,
            speechRate: 0,
            sampleCount: 0,
            lastUpdated: Date()
        )

        XCTAssertFalse(baseline.isValid)
    }

    func testBaselineMetricsCodable() throws {
        let original = BaselineMetrics(
            pitchHz: 145.0,
            jitterPercent: 2.5,
            shimmerPercent: 14.0,
            hnrDb: 15.5,
            speechRate: 125.0,
            sampleCount: 8,
            lastUpdated: Date()
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(BaselineMetrics.self, from: data)

        XCTAssertEqual(decoded.pitchHz, original.pitchHz)
        XCTAssertEqual(decoded.sampleCount, original.sampleCount)
        XCTAssertEqual(decoded.isValid, original.isValid)
    }

    func testBaselineMetricsSample() {
        let sample = BaselineMetrics.sample

        XCTAssertGreaterThan(sample.pitchHz, 0)
        XCTAssertGreaterThan(sample.sampleCount, 0)
        XCTAssertTrue(sample.isValid)
    }

    // MARK: - HealthDataPoint

    func testHealthDataPointCreation() {
        let date = Date()
        let dataPoint = HealthDataPoint(
            date: date,
            fatigueScore: 25.0,
            illnessScore: 15.0
        )

        XCTAssertEqual(dataPoint.date, date)
        XCTAssertEqual(dataPoint.fatigueScore, 25.0)
        XCTAssertEqual(dataPoint.illnessScore, 15.0)
    }

    func testHealthDataPointHasUniqueID() {
        let d1 = HealthDataPoint(date: Date(), fatigueScore: 20, illnessScore: 10)
        let d2 = HealthDataPoint(date: Date(), fatigueScore: 20, illnessScore: 10)

        XCTAssertNotEqual(d1.id, d2.id)
    }

    func testHealthDataPointSampleWeekData() {
        let weekData = HealthDataPoint.sampleWeekData

        XCTAssertEqual(weekData.count, 7)

        // All fatigue scores should be in expected range
        for dataPoint in weekData {
            XCTAssertGreaterThanOrEqual(dataPoint.fatigueScore, 0)
            XCTAssertLessThanOrEqual(dataPoint.fatigueScore, 100)
            XCTAssertGreaterThanOrEqual(dataPoint.illnessScore, 0)
            XCTAssertLessThanOrEqual(dataPoint.illnessScore, 100)
        }
    }

    // MARK: - HealthDataPointCodable

    func testHealthDataPointCodableRoundTrip() throws {
        let original = HealthDataPointCodable(
            date: Date(),
            fatigueScore: 35.5,
            illnessScore: 22.3
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(HealthDataPointCodable.self, from: data)

        XCTAssertEqual(decoded.fatigueScore, original.fatigueScore, accuracy: 0.01)
        XCTAssertEqual(decoded.illnessScore, original.illnessScore, accuracy: 0.01)
    }

    func testHealthDataPointCodableArrayRoundTrip() throws {
        let originals = [
            HealthDataPointCodable(date: Date(), fatigueScore: 10, illnessScore: 5),
            HealthDataPointCodable(date: Date().addingTimeInterval(-86400), fatigueScore: 20, illnessScore: 15),
            HealthDataPointCodable(date: Date().addingTimeInterval(-172800), fatigueScore: 30, illnessScore: 25)
        ]

        let encoder = JSONEncoder()
        let data = try encoder.encode(originals)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode([HealthDataPointCodable].self, from: data)

        XCTAssertEqual(decoded.count, 3)
        XCTAssertEqual(decoded[0].fatigueScore, 10)
        XCTAssertEqual(decoded[1].fatigueScore, 20)
        XCTAssertEqual(decoded[2].fatigueScore, 30)
    }

    // MARK: - Score Bounds

    func testFatigueScoreBounds() {
        // Fatigue score should be 0-100
        let lowMetrics = VoiceHealthMetrics(fatigueScore: 0, illnessScore: 0)
        let highMetrics = VoiceHealthMetrics(fatigueScore: 100, illnessScore: 100)

        XCTAssertGreaterThanOrEqual(lowMetrics.fatigueScore, 0)
        XCTAssertLessThanOrEqual(highMetrics.fatigueScore, 100)
    }

    func testIllnessScoreBounds() {
        // Illness score should be 0-100
        let lowMetrics = VoiceHealthMetrics(fatigueScore: 0, illnessScore: 0)
        let highMetrics = VoiceHealthMetrics(fatigueScore: 100, illnessScore: 100)

        XCTAssertGreaterThanOrEqual(lowMetrics.illnessScore, 0)
        XCTAssertLessThanOrEqual(highMetrics.illnessScore, 100)
    }
}
