import Foundation
import UserNotifications

class NotificationService {
    static let shared = NotificationService()

    private init() {}

    func requestPermission() async -> Bool {
        do {
            return try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            print("Notification permission request failed: \(error)")
            return false
        }
    }

    func sendHealthAlert(title: String, body: String, type: HealthAlertType) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        content.categoryIdentifier = "HEALTH_ALERT"

        let request = UNNotificationRequest(
            identifier: "\(type.rawValue)-\(Date().timeIntervalSince1970)",
            content: content,
            trigger: nil  // Deliver immediately
        )

        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("Failed to send health notification: \(error)")
            }
        }
    }

    enum HealthAlertType: String {
        case fatigue
        case illness
    }
}
