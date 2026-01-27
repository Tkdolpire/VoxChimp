import Foundation
import AVFoundation

@MainActor
class AudioRecorder: NSObject, ObservableObject {
    private var audioRecorder: AVAudioRecorder?
    private var currentRecordingURL: URL?

    @Published var isRecording = false
    @Published var recordingDuration: TimeInterval = 0

    private var durationTimer: Timer?

    override init() {
        super.init()
    }

    // MARK: - Recording

    func startRecording() async throws {
        // Request permission if needed
        let permission = await AVCaptureDevice.requestAccess(for: .audio)
        guard permission else {
            throw RecordingError.permissionDenied
        }

        // Create temp file URL
        let tempDir = FileManager.default.temporaryDirectory
        let filename = "notta_recording_\(Date().timeIntervalSince1970).wav"
        let fileURL = tempDir.appendingPathComponent(filename)
        currentRecordingURL = fileURL

        // Audio settings for Whisper compatibility
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16000.0,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]

        do {
            audioRecorder = try AVAudioRecorder(url: fileURL, settings: settings)
            audioRecorder?.delegate = self
            audioRecorder?.isMeteringEnabled = true
            audioRecorder?.prepareToRecord()

            if audioRecorder?.record() == true {
                isRecording = true
                recordingDuration = 0
                startDurationTimer()
                print("Recording started: \(fileURL.path)")
            } else {
                throw RecordingError.recordingFailed
            }
        } catch {
            print("Recording setup failed: \(error)")
            throw RecordingError.recordingFailed
        }
    }

    func stopRecording() async throws -> URL {
        guard let recorder = audioRecorder, let url = currentRecordingURL else {
            throw RecordingError.noRecording
        }

        stopDurationTimer()
        recorder.stop()
        isRecording = false

        // Validate the recording
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw RecordingError.noRecording
        }

        let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
        let fileSize = attributes[.size] as? Int ?? 0

        if fileSize < 1000 {
            throw RecordingError.tooShort
        }

        // Validate audio content
        let isValid = try await validateAudio(at: url)
        if !isValid {
            throw RecordingError.noAudioDetected
        }

        print("Recording stopped: \(url.path), size: \(fileSize) bytes")
        return url
    }

    func cancelRecording() {
        stopDurationTimer()
        audioRecorder?.stop()
        audioRecorder = nil
        isRecording = false

        // Clean up temp file
        if let url = currentRecordingURL {
            try? FileManager.default.removeItem(at: url)
        }
        currentRecordingURL = nil
    }

    // MARK: - Audio Validation

    private func validateAudio(at url: URL) async throws -> Bool {
        let file = try AVAudioFile(forReading: url)
        let format = file.processingFormat
        let frameCount = UInt32(file.length)

        guard frameCount > 0 else { return false }

        let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount)!
        try file.read(into: buffer)

        // Check for actual audio content (not just silence)
        guard let channelData = buffer.floatChannelData?[0] else { return false }

        var maxAmplitude: Float = 0
        for i in 0..<Int(buffer.frameLength) {
            maxAmplitude = max(maxAmplitude, abs(channelData[i]))
        }

        // Threshold for detecting actual audio vs silence
        let threshold: Float = 0.001
        return maxAmplitude > threshold
    }

    // MARK: - Duration Timer

    private func startDurationTimer() {
        durationTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.recordingDuration += 0.1
            }
        }
    }

    private func stopDurationTimer() {
        durationTimer?.invalidate()
        durationTimer = nil
    }

    // MARK: - Audio Level

    func updateMeters() -> Float {
        audioRecorder?.updateMeters()
        return audioRecorder?.averagePower(forChannel: 0) ?? -160
    }
}

// MARK: - AVAudioRecorderDelegate

extension AudioRecorder: AVAudioRecorderDelegate {
    nonisolated func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        Task { @MainActor in
            if !flag {
                print("Recording finished unsuccessfully")
            }
        }
    }

    nonisolated func audioRecorderEncodeErrorDidOccur(_ recorder: AVAudioRecorder, error: Error?) {
        Task { @MainActor in
            print("Recording encode error: \(error?.localizedDescription ?? "unknown")")
            self.cancelRecording()
        }
    }
}

// MARK: - Recording Errors

enum RecordingError: LocalizedError {
    case permissionDenied
    case recordingFailed
    case noRecording
    case tooShort
    case noAudioDetected

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Microphone permission denied. Please enable in System Settings."
        case .recordingFailed:
            return "Failed to start recording."
        case .noRecording:
            return "No recording available."
        case .tooShort:
            return "Recording too short."
        case .noAudioDetected:
            return "No audio detected. Check microphone permissions."
        }
    }
}
