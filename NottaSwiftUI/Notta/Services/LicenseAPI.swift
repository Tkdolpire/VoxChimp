import Foundation

/// API client for license validation and subscription management
actor LicenseAPI {
    // MARK: - Configuration

    /// Base URL for the license API - update this when deploying
    private static let baseURL = "https://notta-api.vercel.app/api"

    /// API timeout in seconds
    private let timeout: TimeInterval = 30

    // MARK: - Endpoints

    /// Validates a license key with the server
    func validate(licenseKey: String, machineId: String? = nil) async throws -> ValidationResponse {
        var body: [String: Any] = ["key": licenseKey]
        if let machineId = machineId {
            body["machineId"] = machineId
        }

        let data = try await post(endpoint: "validate", body: body)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(ValidationResponse.self, from: data)
    }

    /// Creates a Stripe checkout session and returns the checkout URL
    func createCheckoutSession(email: String? = nil, plan: String = "monthly") async throws -> CheckoutResponse {
        var body: [String: Any] = [
            "plan": plan,
            "machineId": MachineIdentifier.current,
            "successUrl": "notta://activate?session_id={CHECKOUT_SESSION_ID}",
            "cancelUrl": "notta://cancel"
        ]

        if let email = email {
            body["email"] = email
        }

        let data = try await post(endpoint: "checkout", body: body)
        return try JSONDecoder().decode(CheckoutResponse.self, from: data)
    }

    /// Gets the Stripe customer portal URL for subscription management
    func getPortalURL(licenseKey: String) async throws -> PortalResponse {
        let body: [String: Any] = ["key": licenseKey]
        let data = try await post(endpoint: "portal", body: body)
        return try JSONDecoder().decode(PortalResponse.self, from: data)
    }

    /// Retrieves the license key for a completed checkout session
    func getLicenseForSession(sessionId: String) async throws -> ValidationResponse {
        let body: [String: Any] = ["sessionId": sessionId]
        let data = try await post(endpoint: "session-license", body: body)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(ValidationResponse.self, from: data)
    }

    // MARK: - HTTP Helpers

    private func post(endpoint: String, body: [String: Any]) async throws -> Data {
        guard let url = URL(string: "\(Self.baseURL)/\(endpoint)") else {
            throw LicenseAPIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Notta/\(Bundle.main.appVersion)", forHTTPHeaderField: "User-Agent")
        request.timeoutInterval = timeout

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw LicenseAPIError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return data
        case 401:
            throw LicenseAPIError.unauthorized
        case 404:
            throw LicenseAPIError.notFound
        case 429:
            throw LicenseAPIError.rateLimited
        case 500...599:
            throw LicenseAPIError.serverError(httpResponse.statusCode)
        default:
            // Try to parse error message from response
            if let errorResponse = try? JSONDecoder().decode(APIErrorResponse.self, from: data) {
                throw LicenseAPIError.apiError(errorResponse.message)
            }
            throw LicenseAPIError.unexpectedStatusCode(httpResponse.statusCode)
        }
    }
}

// MARK: - Error Types

enum LicenseAPIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case unauthorized
    case notFound
    case rateLimited
    case serverError(Int)
    case unexpectedStatusCode(Int)
    case apiError(String)
    case networkError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid API URL"
        case .invalidResponse:
            return "Invalid response from server"
        case .unauthorized:
            return "Invalid or expired license key"
        case .notFound:
            return "License not found"
        case .rateLimited:
            return "Too many requests. Please try again later."
        case .serverError(let code):
            return "Server error (\(code)). Please try again later."
        case .unexpectedStatusCode(let code):
            return "Unexpected response (\(code))"
        case .apiError(let message):
            return message
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        }
    }
}

// MARK: - API Error Response

private struct APIErrorResponse: Codable {
    let error: Bool
    let message: String
}

// MARK: - Bundle Extension

extension Bundle {
    var appVersion: String {
        return infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0"
    }

    var buildNumber: String {
        return infoDictionary?["CFBundleVersion"] as? String ?? "1"
    }
}
