import SwiftUI
import AppKit

struct HistoryView: View {
    @EnvironmentObject var appState: AppState
    @State private var searchText = ""
    @State private var selectedTranscription: Transcription?
    @State private var sortOrder: SortOrder = .newest

    enum SortOrder: String, CaseIterable {
        case newest = "Newest First"
        case oldest = "Oldest First"
        case longest = "Longest First"
    }

    var filteredHistory: [Transcription] {
        var results = appState.transcriptionHistory

        if !searchText.isEmpty {
            results = results.filter { transcription in
                transcription.text.localizedCaseInsensitiveContains(searchText) ||
                (transcription.category?.localizedCaseInsensitiveContains(searchText) ?? false) ||
                transcription.tags.contains { $0.localizedCaseInsensitiveContains(searchText) }
            }
        }

        switch sortOrder {
        case .newest:
            results.sort { $0.timestamp > $1.timestamp }
        case .oldest:
            results.sort { $0.timestamp < $1.timestamp }
        case .longest:
            results.sort { $0.wordCount > $1.wordCount }
        }

        return results
    }

    var body: some View {
        NavigationSplitView {
            sidebarContent
        } detail: {
            detailContent
        }
        .navigationTitle("History")
    }

    @ViewBuilder
    private var sidebarContent: some View {
        List(filteredHistory, selection: $selectedTranscription) { transcription in
            TranscriptionRow(transcription: transcription)
                .tag(transcription)
                .contextMenu {
                    Button("Copy") {
                        appState.copyTranscription(transcription)
                    }
                    Divider()
                    Button("Delete", role: .destructive) {
                        appState.deleteTranscription(transcription)
                    }
                }
        }
        .listStyle(.sidebar)
        .frame(minWidth: 280)
        .searchable(text: $searchText, prompt: "Search transcriptions")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                sortMenu
            }
        }
    }

    @ViewBuilder
    private var sortMenu: some View {
        Menu {
            ForEach(SortOrder.allCases, id: \.self) { order in
                Button(order.rawValue) {
                    sortOrder = order
                }
            }
        } label: {
            Image(systemName: "arrow.up.arrow.down")
        }
    }

    @ViewBuilder
    private var detailContent: some View {
        if let transcription = selectedTranscription {
            TranscriptionDetailView(transcription: transcription)
                .environmentObject(appState)
        } else {
            ContentUnavailableView(
                "Select a Transcription",
                systemImage: "text.quote",
                description: Text("Choose a transcription from the list to view details")
            )
        }
    }

}

// MARK: - Transcription Row

struct TranscriptionRow: View {
    let transcription: Transcription

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(transcription.relativeDate)
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Spacer()

                if transcription.audioFilePath != nil {
                    Image(systemName: "waveform")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Text(transcription.preview)
                .font(.callout)
                .lineLimit(2)

            HStack(spacing: 8) {
                if let category = transcription.category {
                    Label(category, systemImage: "folder")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                Text("\(transcription.wordCount) words")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Detail View

struct TranscriptionDetailView: View {
    @EnvironmentObject var appState: AppState
    let transcription: Transcription
    @State private var isCopied = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                headerSection
                Divider()
                textSection
                tagsSection
                audioSection
            }
            .padding(20)
        }
        .frame(minWidth: 350)
    }

    @ViewBuilder
    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(transcription.formattedDate)
                    .font(.headline)

                HStack(spacing: 12) {
                    Label("\(transcription.wordCount) words", systemImage: "textformat.abc")
                    Label("\(transcription.charCount) characters", systemImage: "character")
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Spacer()

            Button {
                copyToClipboard()
            } label: {
                HStack {
                    Image(systemName: isCopied ? "checkmark.circle.fill" : "doc.on.doc")
                    Text(isCopied ? "Copied!" : "Copy")
                }
            }
            .buttonStyle(.borderedProminent)
        }
    }

    @ViewBuilder
    private var textSection: some View {
        Text(transcription.text)
            .font(.body)
            .textSelection(.enabled)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private var tagsSection: some View {
        if !transcription.tags.isEmpty {
            Divider()

            VStack(alignment: .leading, spacing: 8) {
                Text("Tags")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                HStack {
                    ForEach(transcription.tags, id: \.self) { tag in
                        Text(tag)
                            .font(.caption)
                            .foregroundStyle(Color.brandOrange)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.brandOrange.opacity(0.1))
                            .clipShape(Capsule())
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var audioSection: some View {
        EmptyView()
    }

    private func copyToClipboard() {
        appState.copyTranscription(transcription)
        isCopied = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            isCopied = false
        }
    }
}

// MARK: - Preview

#Preview {
    HistoryView()
        .environmentObject(AppState())
}
