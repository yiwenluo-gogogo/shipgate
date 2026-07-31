import SwiftUI

// Fixture: a curated content app. No user-generated content, no discovery
// surface over user content. The classifier must NOT drag this above 4+.
// Contains deliberate near-miss tokens — an audio mute and the word
// "unlikely" — which both caused real false positives during development.
struct ContentView: View {
    @State private var isMuted = false          // audio mute, not a user mute
    @State private var articles: [Article] = []
    var body: some View { Text("today") }
}

struct Article: Identifiable, Codable {
    let id: String
    let title: String
    let body: String
}

// It is unlikely that this comment should trip the amplification signal.
func playChime() { }
