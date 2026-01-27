import SwiftUI
import Charts
import AppKit

struct HealthDashboardView: View {
    @EnvironmentObject var appState: AppState
    @State private var isAnalyzing = false
    @State private var selectedTimeRange: TimeRange = .week

    enum TimeRange: String, CaseIterable {
        case day = "24h"
        case week = "7 days"
        case month = "30 days"
    }

    // Sample data for preview
    private let metrics = VoiceHealthMetrics.sample
    private let baseline = BaselineMetrics.sample
    private let chartData = HealthDataPoint.sampleWeekData

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header with refresh
                headerSection

                // Score cards
                HStack(spacing: 16) {
                    ScoreCard(
                        title: "Fatigue",
                        score: metrics.fatigueScore,
                        icon: "moon.zzz.fill",
                        color: scoreColor(for: metrics.fatigueScore)
                    )

                    ScoreCard(
                        title: "Illness",
                        score: metrics.illnessScore,
                        icon: "thermometer.medium",
                        color: scoreColor(for: metrics.illnessScore)
                    )
                }

                // Recommendation
                if !metrics.recommendation.isEmpty {
                    RecommendationCard(message: metrics.recommendation)
                }

                // Trend chart
                TrendChartSection(
                    data: chartData,
                    selectedRange: $selectedTimeRange
                )

                // Metrics comparison
                MetricsComparisonSection(
                    current: metrics,
                    baseline: baseline
                )

                // Indicators
                if !metrics.indicators.isEmpty {
                    IndicatorsSection(indicators: metrics.indicators)
                }
            }
            .padding(20)
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    runAnalysis()
                } label: {
                    if isAnalyzing {
                        ProgressView()
                            .scaleEffect(0.7)
                    } else {
                        Image(systemName: "arrow.clockwise")
                    }
                }
                .disabled(isAnalyzing)
                .help("Refresh analysis")
            }

            ToolbarItem(placement: .primaryAction) {
                Button {
                    openHealthFolder()
                } label: {
                    Image(systemName: "folder")
                }
                .help("Open health data folder")
            }
        }
    }

    // MARK: - Sections

    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Label("Voice Health", systemImage: "heart.text.square.fill")
                    .font(.title2.weight(.semibold))
                    .symbolRenderingMode(.multicolor)

                Text("Last updated: \(metrics.timestamp.formatted(date: .abbreviated, time: .shortened))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
    }

    // MARK: - Helpers

    private func scoreColor(for score: Int) -> Color {
        switch score {
        case 0..<30: return .green
        case 30..<50: return .yellow
        case 50..<70: return .orange
        default: return .red
        }
    }

    private func runAnalysis() {
        isAnalyzing = true
        // TODO: Implement actual analysis
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            isAnalyzing = false
        }
    }

    private func openHealthFolder() {
        let url = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".notta_health")
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        NSWorkspace.shared.open(url)
    }
}

// MARK: - Score Card

struct ScoreCard: View {
    let title: String
    let score: Int
    let icon: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .foregroundStyle(color)
                Text(title)
                    .font(.subheadline.weight(.medium))

                Spacer()

                Text("\(score)%")
                    .font(.title2.weight(.bold))
                    .foregroundStyle(color)
            }

            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.secondary.opacity(0.2))

                    RoundedRectangle(cornerRadius: 4)
                        .fill(color)
                        .frame(width: geometry.size.width * CGFloat(score) / 100)
                }
            }
            .frame(height: 8)
        }
        .padding(16)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Recommendation Card

struct RecommendationCard: View {
    let message: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "lightbulb.fill")
                .font(.title2)
                .foregroundStyle(.yellow)

            Text(message)
                .font(.callout)

            Spacer()
        }
        .padding(16)
        .background(.yellow.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Trend Chart

struct TrendChartSection: View {
    let data: [HealthDataPoint]
    @Binding var selectedRange: HealthDashboardView.TimeRange

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Trends", systemImage: "chart.line.uptrend.xyaxis")
                    .font(.headline)

                Spacer()

                Picker("Range", selection: $selectedRange) {
                    ForEach(HealthDashboardView.TimeRange.allCases, id: \.self) { range in
                        Text(range.rawValue).tag(range)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 180)
            }

            Chart(data) { point in
                LineMark(
                    x: .value("Date", point.date),
                    y: .value("Fatigue", point.fatigueScore)
                )
                .foregroundStyle(.orange)
                .interpolationMethod(.catmullRom)

                LineMark(
                    x: .value("Date", point.date),
                    y: .value("Illness", point.illnessScore)
                )
                .foregroundStyle(.red)
                .interpolationMethod(.catmullRom)

                AreaMark(
                    x: .value("Date", point.date),
                    y: .value("Fatigue", point.fatigueScore)
                )
                .foregroundStyle(.orange.opacity(0.1))
                .interpolationMethod(.catmullRom)
            }
            .chartYScale(domain: 0...100)
            .chartYAxis {
                AxisMarks(position: .leading)
            }
            .chartLegend(position: .top, alignment: .trailing)
            .frame(height: 180)

            HStack {
                LegendItem(color: .orange, label: "Fatigue")
                LegendItem(color: .red, label: "Illness")
            }
            .font(.caption)
        }
        .padding(16)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct LegendItem: View {
    let color: Color
    let label: String

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .foregroundStyle(.secondary)
        }
    }
}

// MARK: - Metrics Comparison

struct MetricsComparisonSection: View {
    let current: VoiceHealthMetrics
    let baseline: BaselineMetrics

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Voice Metrics", systemImage: "waveform")
                .font(.headline)

            Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 10) {
                GridRow {
                    Text("Metric")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("Current")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("Baseline")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("Change")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Divider()
                    .gridCellColumns(4)

                MetricRowView(
                    name: "Pitch",
                    unit: "Hz",
                    current: current.pitchHz,
                    baseline: baseline.pitchHz
                )

                MetricRowView(
                    name: "Jitter",
                    unit: "%",
                    current: current.jitterPercent,
                    baseline: baseline.jitterPercent,
                    lowerIsBetter: true
                )

                MetricRowView(
                    name: "Shimmer",
                    unit: "%",
                    current: current.shimmerPercent,
                    baseline: baseline.shimmerPercent,
                    lowerIsBetter: true
                )

                MetricRowView(
                    name: "HNR",
                    unit: "dB",
                    current: current.hnrDb,
                    baseline: baseline.hnrDb
                )

                MetricRowView(
                    name: "Speech Rate",
                    unit: "wpm",
                    current: current.speechRate,
                    baseline: baseline.speechRate
                )
            }
        }
        .padding(16)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct MetricRowView: View {
    let name: String
    let unit: String
    let current: Double
    let baseline: Double
    var lowerIsBetter: Bool = false

    private var changePercent: Double {
        guard baseline != 0 else { return 0 }
        return ((current - baseline) / baseline) * 100
    }

    private var changeColor: Color {
        let isPositive = lowerIsBetter ? changePercent < 0 : changePercent > 0
        let isNegative = lowerIsBetter ? changePercent > 0 : changePercent < 0

        if abs(changePercent) < 5 {
            return .secondary
        } else if isPositive {
            return .green
        } else if isNegative {
            return .red
        }
        return .secondary
    }

    var body: some View {
        GridRow {
            Text(name)
                .font(.callout)

            Text(String(format: "%.1f", current))
                .font(.callout.monospacedDigit())

            Text(String(format: "%.1f", baseline))
                .font(.callout.monospacedDigit())
                .foregroundStyle(.secondary)

            HStack(spacing: 2) {
                Image(systemName: changePercent > 0 ? "arrow.up" : changePercent < 0 ? "arrow.down" : "minus")
                    .font(.caption2)
                Text(String(format: "%.0f%%", abs(changePercent)))
                    .font(.caption.monospacedDigit())
            }
            .foregroundStyle(changeColor)
        }
    }
}

// MARK: - Indicators Section

struct IndicatorsSection: View {
    let indicators: [HealthIndicator]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Health Indicators", systemImage: "checklist")
                .font(.headline)

            VStack(spacing: 8) {
                ForEach(indicators) { indicator in
                    IndicatorRowView(indicator: indicator)
                }
            }
        }
        .padding(16)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct IndicatorRowView: View {
    let indicator: HealthIndicator

    private var statusColor: Color {
        switch indicator.status {
        case .excellent, .good: return .green
        case .stable: return .blue
        case .monitor: return .yellow
        case .attention: return .red
        }
    }

    var body: some View {
        HStack {
            Image(systemName: indicator.status.icon)
                .foregroundStyle(statusColor)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text(indicator.name)
                    .font(.callout.weight(.medium))

                Text(indicator.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            if let change = indicator.changePercent {
                Text(String(format: "%+.0f%%", change))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(change < 0 ? .red : .green)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Preview

#Preview {
    HealthDashboardView()
        .environmentObject(AppState())
        .frame(width: 450, height: 700)
}
