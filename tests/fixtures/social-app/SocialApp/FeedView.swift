import SwiftUI

// Fixture: an unambiguous social app. Both legs of Apple's definition plus a
// reach signal (follower graph), so the classifier should commit to a hard yes.
struct FeedViewModel: ObservableObject {
    @Published var feedItems: [Post] = []
    func loadFeed() async { /* ... */ }
}

struct Post: Identifiable, Codable {
    let id: String
    let authorId: String
    var likeCount: Int
    var commentCount: Int

    enum CodingKeys: String, CodingKey {
        case id, authorId, likeCount, commentCount
    }
}

struct Comment: Identifiable, Codable {
    let id: String
    let body: String
}

struct FeedView: View {
    @StateObject private var model = FeedViewModel()
    var body: some View { Text("feed") }
}

func toggleLike(post: Post) { /* ... */ }
func followUser(_ id: String) { /* ... */ }
func unfollowUser(_ id: String) { /* ... */ }
func blockUser(_ id: String) { /* ... */ }
func reportContent(_ id: String) { /* ... */ }
