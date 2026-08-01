import SwiftUI
import DeclaredAgeRange
import FamilyControls

// Fixture for the In-App Controls section of Apple's questionnaire, which sits
// above Capabilities and is easy to miss entirely. Exercises both rows plus the
// carve-out wiring check: DeclaredAgeRange is imported AND actually called.
struct AgeGate {
    let service = AgeRangeService.shared

    func check(in scene: UIWindowScene) async throws {
        let response = try await service.requestAgeRange(ageGates: 13, in: scene)
        switch response {
        case .sharing(let declaration):
            apply(declaration.ageRange)
        case .declinedSharing:
            applyRestrictedDefaults()
        }
    }

    func apply(_ range: Any) {}
    func applyRestrictedDefaults() {}
}

// Parental controls: a real restricted mode, not just an app lock.
struct ParentalControls {
    var childMode = false
    var contentRestriction: Int = 0
    func requestAuthorization() async throws {
        try await AuthorizationCenter.shared.requestAuthorization(for: .child)
    }
}
