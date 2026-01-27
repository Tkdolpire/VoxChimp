import SwiftUI
import AppKit

struct MainView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(spacing: 0) {
            // Toolbar area
            ToolbarView(openWindow: openWindow)
                .padding(.horizontal, 16)
                .padding(.top, 12)

            Divider()
                .padding(.top, 12)

            Spacer()

            // Main content
            VStack(spacing: 20) {
                RecordButton(
                    isRecording: appState.isRecording,
                    audioLevel: appState.audioLevel,
                    onPress: { appState.startRecording() },
                    onRelease: { appState.stopRecording() }
                )

                VStack(spacing: 6) {
                    // Animated status text
                    Text(appState.recordingStatus.displayText)
                        .font(.title3.weight(.medium))
                        .foregroundStyle(appState.recordingStatus.color)
                        .id(appState.recordingStatus.displayText)
                        .transition(.asymmetric(
                            insertion: .opacity.combined(with: .move(edge: .bottom)),
                            removal: .opacity.combined(with: .move(edge: .top))
                        ))
                        .animation(.easeInOut(duration: 0.25), value: appState.recordingStatus.displayText)

                    Text("Hold \(SettingsManager.shared.hotkey.displayName) to record")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            // Last transcription preview
            if let lastText = appState.lastTranscription {
                LastTranscriptionView(
                    text: lastText,
                    isNew: appState.showTranscriptionSuccess
                )
                .padding(.horizontal, 16)
                .padding(.bottom, 16)
                .transition(.asymmetric(
                    insertion: .move(edge: .bottom).combined(with: .opacity),
                    removal: .opacity
                ))
                .animation(.spring(response: 0.4, dampingFraction: 0.8), value: lastText)
            }
        }
        .frame(width: 360, height: 400)
        .background(.ultraThinMaterial)
    }
}

// MARK: - Toolbar

struct ToolbarView: View {
    let openWindow: OpenWindowAction

    var body: some View {
        HStack(spacing: 10) {
            // App icon + title
            HStack(spacing: 8) {
                Image(nsImage: NSApp.applicationIconImage)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: 24, height: 24)

                Text("Notta")
                    .font(.title2.weight(.semibold))
            }

            Spacer()

            HStack(spacing: 8) {
                SettingsLink {
                    Image(systemName: "gear")
                        .font(.system(size: 14, weight: .medium))
                        .frame(width: 28, height: 28)
                        .background(Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                .buttonStyle(ToolbarButtonStyle())
                .help("Settings")

                ToolbarButton(icon: "list.bullet", tooltip: "History") {
                    openWindow(id: "history")
                }

                ToolbarButton(icon: "heart.fill", tooltip: "Voice Health") {
                    openWindow(id: "health")
                }
            }
        }
    }
}

struct ToolbarButtonStyle: ButtonStyle {
    @State private var isHovered = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .background(isHovered ? Color.primary.opacity(0.1) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .scaleEffect(isHovered ? 1.05 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: isHovered)
            .onHover { hovering in
                isHovered = hovering
            }
    }
}

struct ToolbarButton: View {
    let icon: String
    let tooltip: String
    let action: () -> Void

    @State private var isHovered = false

    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .medium))
                .frame(width: 28, height: 28)
                .background(isHovered ? Color.primary.opacity(0.1) : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
        .scaleEffect(isHovered ? 1.05 : 1.0)
        .animation(.easeInOut(duration: 0.15), value: isHovered)
        .help(tooltip)
        .onHover { hovering in
            isHovered = hovering
        }
    }
}

// MARK: - Record Button

struct RecordButton: View {
    let isRecording: Bool
    let audioLevel: Float
    let onPress: () -> Void
    let onRelease: () -> Void

    @State private var isPressed = false
    @State private var pulseScale: CGFloat = 1.0

    var body: some View {
        ZStack {
            // Audio level ring (responsive to voice)
            if isRecording {
                Circle()
                    .stroke(
                        Color.red.opacity(Double(audioLevel) * 0.6 + 0.2),
                        lineWidth: 4 + CGFloat(audioLevel) * 8
                    )
                    .frame(width: 120, height: 120)
                    .scaleEffect(1.0 + CGFloat(audioLevel) * 0.15)
                    .animation(.easeOut(duration: 0.1), value: audioLevel)
            }

            // Pulse effect when recording
            if isRecording {
                Circle()
                    .fill(Color.red.opacity(0.2))
                    .frame(width: 130, height: 130)
                    .scaleEffect(pulseScale)
                    .onAppear {
                        withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                            pulseScale = 1.15
                        }
                    }
                    .onDisappear {
                        pulseScale = 1.0
                    }
            }

            // Main button
            Circle()
                .fill(isRecording ? Color.red : Color.accentColor)
                .frame(width: 100, height: 100)
                .shadow(color: (isRecording ? Color.red : Color.accentColor).opacity(0.4), radius: 10, y: 4)

            // Icon
            Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                .font(.system(size: 36, weight: .medium))
                .foregroundStyle(.white)
        }
        .scaleEffect(isPressed ? 0.95 : 1.0)
        .animation(.spring(response: 0.3, dampingFraction: 0.6), value: isPressed)
        .gesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in
                    if !isPressed {
                        isPressed = true
                        onPress()
                    }
                }
                .onEnded { _ in
                    isPressed = false
                    onRelease()
                }
        )
        .accessibilityLabel(isRecording ? "Stop recording" : "Start recording")
        .accessibilityHint("Press and hold to record")
    }
}

// MARK: - Last Transcription Preview

struct LastTranscriptionView: View {
    let text: String
    var isNew: Bool = false

    @State private var isCopied = false
    @State private var showCheckmark = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                HStack(spacing: 6) {
                    // Success checkmark when just transcribed
                    if showCheckmark {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                            .font(.caption)
                            .transition(.scale.combined(with: .opacity))
                    }

                    Text("Last transcription")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    // Word count badge
                    let wordCount = text.split(separator: " ").count
                    Text("\(wordCount) words")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.primary.opacity(0.08))
                        .clipShape(Capsule())
                }

                Spacer()

                Button {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)
                    isCopied = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                        isCopied = false
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: isCopied ? "checkmark" : "doc.on.doc")
                        Text(isCopied ? "Copied" : "Copy")
                    }
                    .font(.caption)
                }
                .buttonStyle(.plain)
                .foregroundStyle(isCopied ? .green : .secondary)
            }

            Text(text.count > 150 ? String(text.prefix(150)) + "..." : text)
                .font(.callout)
                .lineLimit(3)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(12)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.primary.opacity(0.08), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.05), radius: 2, y: 1)
        .onAppear {
            if isNew {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                    showCheckmark = true
                }
                // Hide checkmark after 3 seconds
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                    withAnimation {
                        showCheckmark = false
                    }
                }
            }
        }
        .onChange(of: isNew) { _, newValue in
            if newValue {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                    showCheckmark = true
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                    withAnimation {
                        showCheckmark = false
                    }
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    MainView()
        .environmentObject(AppState())
}
