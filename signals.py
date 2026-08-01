"""Statically detectable evidence for each capability question.

Design rule, and the reason this file is as fussy as it is: **a tool that answers
"yes" for everything is worthless.** Every app that has ever imported Firebase
will trip a naive signal list. So:

* Firebase / Supabase / a generic backend on its own is a LOW hint on
  User-Generated Content and contributes *nothing* to Social Media. Storing user
  data is not a social feed.
* Social Media is modelled the way Apple actually defines it — as two legs that
  must both be present:
      UGC leg        content created by one user
      DISCOVERY leg  a feed / browse / search / leaderboard surface, or an
                     amplification verb (like, comment, react, repost, follow)
  A signal that supplies only one leg can never produce a "yes" on its own. This
  is the single biggest false-positive brake in the tool.
* Sharing *out* of the app (`ShareLink`, `UIActivityViewController`) is NOT a
  social feed. It hands content to iMessage; it does not redistribute it through
  your app's discovery surface. Ranked LOW with a note, deliberately.
* Generic words that are common in unrelated code — `post`, `block`, `like`,
  `report`, `feed` — are only matched in declaration or call contexts
  (`func likePost(`, `struct Comment`, `blockedUsers`), never bare.

Confidence: high = the symbol almost always means the capability is present;
medium = usually, verify the call site; low = a hint, never a finding on its own.
"""

import re

# capability keys a signal may contribute to. "social_media" entries must carry a
# leg; everything else carries None.
LEGS = ("ugc", "discovery")


def S(sid, pattern, confidence, caps, why, corpora=("source",), note=None,
      mitigates=None, reach=False):
    """Build a signal record.

    caps: {capability_key: leg or None}. A signal contributing to "ugc" also
    supplies Social Media's UGC leg automatically — see leg_of().

    reach: this signal implies content is visible to a broad audience, not just
    to a private group. Apple's reference-page definition ends "...that visibly
    spreads content to many users", and reach is otherwise a server fact no
    static scan can see. Only a reach signal lets the classifier commit to a
    hard yes; without one it stops at likely-yes and asks. A follower graph, an
    explore tab or a public feed implies reach. Comments on a shared object do
    not — that could be three people planning a holiday.
    """
    return {
        "id": sid,
        "rx": re.compile(pattern),
        "confidence": confidence,
        "caps": caps,
        "why": why,
        "corpora": set(corpora),
        "note": note,
        "mitigates": mitigates,
        "reach": reach,
    }


def leg_of(signal):
    """Which of Social Media's two legs this signal supplies, if any."""
    legs = set()
    if "social_media" in signal["caps"]:
        legs.add(signal["caps"]["social_media"] or "discovery")
    if "ugc" in signal["caps"]:
        legs.add("ugc")
    return legs


# Corpora a pattern can be matched against. Files are classified once during the
# walk and each signal only runs against the corpora it declares.
#   source       .swift .m .mm .h .c .cc .cpp
#   deps         Package.swift/.resolved, Podfile(.lock), Cartfile, *.pbxproj
#   plist        Info.plist and friends (raw text pass; structured checks are
#                separate, in shipgate.py)
#   entitlements *.entitlements
CORPORA = ("source", "deps", "plist", "entitlements")


SIGNALS = [
    # ── turnkey chat / messaging SDKs ────────────────────────────────────
    # These ship a whole messaging product. Presence is close to dispositive for
    # Messaging and Chat, and implies UGC (users type the messages).
    S("sdk-streamchat", r"\bStreamChat(SwiftUI|UI)?\b", "high",
      {"messaging": None, "ugc": None},
      "StreamChat is a turnkey chat SDK", corpora=("source", "deps")),
    S("sdk-getstream-feeds", r"\bGetStream\b|\bStreamFeeds\b|\bstream-swift\b", "high",
      {"social_media": "discovery", "ugc": None},
      "Stream's activity-feed product is a social feed by construction",
      corpora=("source", "deps"), reach=True),
    S("sdk-sendbird", r"\bSendBird(SyncManager|UIKit|ChatSDK)?\b|\bSendbirdChat", "high",
      {"messaging": None, "ugc": None},
      "Sendbird is a turnkey chat SDK", corpora=("source", "deps")),
    S("sdk-cometchat", r"\bCometChat", "high", {"messaging": None, "ugc": None},
      "CometChat is a turnkey chat SDK", corpora=("source", "deps")),
    S("sdk-talkjs", r"\bTalkJS\b|\bTalkjs\b", "high", {"messaging": None, "ugc": None},
      "TalkJS is a turnkey chat SDK", corpora=("source", "deps")),
    S("sdk-quickblox", r"\bQuickblox\b|\bQBChat", "high", {"messaging": None, "ugc": None},
      "QuickBlox is a turnkey chat SDK", corpora=("source", "deps")),
    S("sdk-applozic", r"\bApplozic\b", "high", {"messaging": None, "ugc": None},
      "Applozic is a turnkey chat SDK", corpora=("source", "deps")),
    S("sdk-twilio-conv", r"\bTwilioConversations\b|\bTCHChannel\b|\bTwilioChat", "high",
      {"messaging": None, "ugc": None},
      "Twilio Conversations is a messaging SDK", corpora=("source", "deps")),
    S("sdk-matrix", r"\bMatrixSDK\b|\bMatrixRustSDK\b", "high",
      {"messaging": None, "ugc": None},
      "Matrix is a federated messaging protocol SDK", corpora=("source", "deps")),
    S("sdk-xmtp", r"\bXMTP\b", "high", {"messaging": None, "ugc": None},
      "XMTP is a messaging protocol SDK", corpora=("source", "deps")),
    S("sdk-rocketchat", r"\bRocketChat\b", "high", {"messaging": None, "ugc": None},
      "Rocket.Chat SDK", corpora=("source", "deps")),
    S("sdk-ivs-chat", r"\bAmazonIVSChat\b|\bIVSChat", "high",
      {"messaging": None, "ugc": None},
      "Amazon IVS Chat is a live-stream chat SDK", corpora=("source", "deps")),

    # ── realtime voice/video ─────────────────────────────────────────────
    S("sdk-agora", r"\bAgoraRtcKit\b|\bAgoraRtmKit\b|\bAgoraRtcEngine\b", "high",
      {"messaging": None, "ugc": None},
      "Agora provides realtime voice/video/messaging between users",
      corpora=("source", "deps")),
    S("sdk-zego", r"\bZegoExpressEngine\b|\bZEGOCLOUD\b|\bZegoUIKit", "high",
      {"messaging": None, "ugc": None},
      "ZEGOCLOUD provides realtime voice/video between users",
      corpora=("source", "deps")),
    S("sdk-livekit", r"\bLiveKit(Client)?\b", "medium", {"messaging": None, "ugc": None},
      "LiveKit is realtime audio/video between participants",
      corpora=("source", "deps")),
    S("sdk-twilio-video", r"\bTwilioVideo\b|\bTVIRoom\b", "medium",
      {"messaging": None, "ugc": None},
      "Twilio Video connects users in a room", corpora=("source", "deps")),
    S("sdk-webrtc", r"\bWebRTC\b|\bRTCPeerConnection\b", "medium",
      {"messaging": None},
      "WebRTC peer connections carry user-to-user audio/video/data",
      corpora=("source", "deps")),

    # ── realtime transports (weaker — could be anything) ─────────────────
    S("sdk-pubnub", r"\bPubNub\b", "medium", {"messaging": None},
      "PubNub is a realtime pub/sub transport, very often used for chat",
      corpora=("source", "deps"),
      note="Also used for non-social realtime (prices, presence). Verify."),
    S("sdk-ably", r"\bAbly(Realtime)?\b", "medium", {"messaging": None},
      "Ably is a realtime pub/sub transport, often used for chat",
      corpora=("source", "deps"),
      note="Also used for non-social realtime. Verify."),
    S("sdk-pusher", r"\bPusherSwift\b|\bPusherChatkit\b", "medium", {"messaging": None},
      "Pusher channels are commonly used for chat", corpora=("source", "deps"),
      note="Also used for non-social realtime. Verify."),
    S("sdk-socketio", r"\bSocketIO\b|\bSocketManager\b", "low", {"messaging": None},
      "Socket.IO is a generic realtime transport", corpora=("source", "deps"),
      note="Generic transport — weak evidence on its own."),

    # ── generic backends: LOW, and never Social Media ────────────────────
    # This is the anti-false-positive rule. Half the App Store uses Firebase.
    S("backend-firestore", r"\bFirestore\b|\bFIRFirestore\b|\bcollection\(\s*\"", "low",
      {"ugc": None},
      "A Firestore/document-store write path can carry user content",
      corpora=("source", "deps"),
      note="Firebase alone is NOT a social signal. Most apps that use it have no "
           "feed at all. Treated as a weak UGC hint only."),
    S("backend-rtdb", r"\bFirebaseDatabase\b|\bFIRDatabase\b|\bDatabase\.database\(", "low",
      {"ugc": None},
      "Firebase Realtime Database write path can carry user content",
      corpora=("source", "deps"),
      note="Weak hint only — see backend-firestore."),
    S("backend-supabase", r"\bSupabase\b|\bsupabase-swift\b", "low", {"ugc": None},
      "Supabase can carry user content", corpora=("source", "deps"),
      note="Weak hint only — see backend-firestore."),
    S("backend-cloudkit-public", r"CKDatabaseScope\.public|publicCloudDatabase", "medium",
      {"ugc": None},
      "The CloudKit *public* database is shared across all users of the app — "
      "content written there is visible to everyone", reach=True),
    S("backend-cloudkit-shared", r"CKShare\b|sharedCloudDatabase|UICloudSharingController",
      "medium", {"ugc": None},
      "CloudKit sharing distributes a record to other users"),

    # ── moderation: strong proof that UGC exists ─────────────────────────
    # Nobody buys a moderation pipeline for content they wrote themselves.
    S("mod-hive", r"\bHiveAI\b|thehive\.ai", "high", {"ugc": None},
      "Hive moderation is only bought when users can publish"),
    S("mod-sightengine", r"sightengine", "high", {"ugc": None},
      "Sightengine moderation implies user-published content"),
    S("mod-perspective", r"commentanalyzer\.googleapis\.com|PerspectiveAPI", "high",
      {"ugc": None, "social_media": "discovery"},
      "Google's Perspective API scores *comments* — implies both UGC and a "
      "commenting surface"),
    S("mod-openai", r"/v1/moderations|openai.*moderation", "high", {"ugc": None},
      "An OpenAI moderation endpoint call implies user-published content"),
    S("mod-rekognition", r"DetectModerationLabels|AWSRekognition", "high", {"ugc": None},
      "Rekognition moderation labels imply user-uploaded imagery"),
    S("mod-azure", r"ContentSafety|ContentModerator", "high", {"ugc": None},
      "Azure Content Safety/Moderator implies user-published content"),
    S("mod-safesearch", r"safeSearchAnnotation|SAFE_SEARCH_DETECTION", "high", {"ugc": None},
      "Cloud Vision SafeSearch implies user-uploaded imagery"),
    S("mod-communitysift", r"CommunitySift|TwoHat\b|Bodyguard\b|SpectrumLabs", "high",
      {"ugc": None},
      "A community-moderation vendor implies user-published content"),

    # ── the social-graph safety trio: block / mute / report ──────────────
    # Very high signal. You only build these when users can see each other.
    # Every token here must be USER-scoped. Bare `isMuted` is the audio mute in
    # every game ever written and bare `isBlocked` is a grid cell in half of
    # them; both produced a false Social Media "yes" on a snake game in testing.
    S("graph-block", r"\b(blockUser|blockedUsers|unblockUser|blockedUserIDs|"
                     r"BlockedUser|blockedAccounts)\b", "high",
      {"social_media": "discovery", "ugc": None},
      "A user-blocking feature exists only when users are exposed to each "
      "other's content or messages"),
    S("graph-mute", r"\b(muteUser|mutedUsers|unmuteUser|mutedUserIDs|MutedUser|"
                    r"mutedAccounts)\b", "high",
      {"social_media": "discovery", "ugc": None},
      "A user-muting feature implies exposure to other users' content"),
    S("graph-report", r"\b(reportUser|reportContent|reportPost|reportAbuse|"
                      r"ReportReason|flagContent|flagPost|reportComment)\b", "high",
      {"social_media": "discovery", "ugc": None},
      "A report/flag flow exists to police content other users published — and "
      "App Review requires one for UGC apps (Guideline 1.2)"),

    # ── amplification verbs: Apple's own example list ────────────────────
    # NB: `unlike` is anchored without \w* on purpose — `unlike\w*` matches the
    # English word "unlikely", which appears in comments in almost every codebase.
    S("amp-like", r"\b(likeCount|likedBy|toggleLike|isLiked|didLike|likePost|"
                  r"likeComment|LikeButton|hasLiked|likesCount|"
                  r"unlike(?:Post|Comment|User)?)\b", "high",
      {"social_media": "discovery"},
      "Apple names \"liking\" in the Social Media example list"),
    S("amp-comment", r"\b(commentCount|postComment|addComment|CommentsView|"
                     r"CommentViewModel|commentText|replyToComment|CommentCell)\b|"
                     r"\b(struct|class|enum)\s+Comment\b", "high",
      {"social_media": "discovery", "ugc": None},
      "Apple names \"commenting\" in the Social Media example list"),
    S("amp-react", r"\b(reactionCount|addReaction|ReactionType|reactedBy|"
                   r"ReactionPicker|emojiReaction)\b", "high",
      {"social_media": "discovery"},
      "Apple names \"reacting\" in the Social Media example list"),
    S("amp-repost", r"\b(repost\w*|reshare\w*|retweet\w*|boostPost|regram)\b", "high",
      {"social_media": "discovery"},
      "Apple names \"reposting\" in the Social Media example list", reach=True),
    S("amp-vote", r"\b(upvote\w*|downvote\w*|voteCount|karmaScore)\b", "high",
      {"social_media": "discovery"},
      "Up/downvoting makes content more visible to others — amplification",
      reach=True),
    S("amp-follow", r"\b(followUser|unfollow\w*|followers?Count|isFollowing|"
                    r"followingList|followerIDs|FollowButton|followedBy)\b", "high",
      {"social_media": "discovery"},
      "A follow graph is a discovery method — Apple names it in the example list",
      reach=True),

    # ── discovery surfaces ───────────────────────────────────────────────
    S("feed-view", r"\b(FeedView|FeedViewModel|SocialFeed|ActivityFeed|feedItems|"
                   r"fetchFeed|loadFeed|FeedCell|FeedScreen|HomeFeed)\b", "high",
      {"social_media": "discovery"},
      "A feed is Apple's named example of a discovery method",
      note="RSS/Atom readers also use the word 'feed' — check the call site if "
           "your app is a news reader.", reach=True),
    S("feed-rss-exempt", r"\b(RSSFeed|AtomFeed|rssURL|feedURL|parseRSS|FeedKit)\b", "low",
      {}, "RSS/Atom parsing — a content feed you publish, not a social feed",
      mitigates="feed-view",
      note="Mitigating signal: lowers confidence in feed-view."),
    S("discover-surface", r"\b(ExploreView|DiscoverView|exploreFeed|discoverFeed|"
                          r"ForYouView|forYouFeed|TrendingView|trendingPosts|"
                          r"PopularPosts|GlobalGallery|CommunityGallery|"
                          r"PublicGallery|browsePosts)\b", "high",
      {"social_media": "discovery"},
      "Explore/trending/community surfaces are exactly Apple's \"sharing and "
      "discovery tools\"", reach=True),
    S("hashtag", r"\b(hashtag\w*|Hashtag|parseHashtags|tagSearch)\b", "medium",
      {"social_media": "discovery"},
      "Hashtags exist to make content findable by other users", reach=True),
    S("mention", r"@mention|\bmentionedUsers\b|\bMentionParser\b|\bparseMentions\b",
      "medium", {"social_media": "discovery"},
      "@-mentions push content into another user's attention"),
    S("post-type", r"\b(struct|class|enum)\s+\w*Post\b|\b(PostViewModel|PostCell|"
                   r"PostDetailView|createPost|publishPost|submitPost|postsCollection)\b",
      "medium", {"social_media": "discovery", "ugc": None},
      "A first-class Post type implies user-authored items in a shared space",
      note="Not matched on bare 'post' — HTTP POST and postNotification are "
           "excluded by requiring a declaration or call context."),
    S("user-profile-other", r"\b(UserProfileView|OtherUserProfile|profileFor\(|"
                            r"viewProfile|PublicProfile|profileOf)\b", "medium",
      {"social_media": "discovery"},
      "Viewing *another* user's profile is a discovery method", reach=True),
    S("codingkeys-social", r"\bcase\s+(likes|likeCount|comments|commentCount|"
                           r"followers|following|reposts|shares|reactions|"
                           r"authorId|authorID|authorName|postedBy)\b", "medium",
      {"social_media": "discovery", "ugc": None},
      "Social fields in a networking model survive even when the UI is "
      "server-driven — the backend has a feed even if the client looks plain"),

    # ── UGC creation ─────────────────────────────────────────────────────
    S("ugc-upload", r"\b(uploadImage|uploadPhoto|uploadVideo|uploadFile|"
                    r"uploadAvatar|StorageReference|putData\(|uploadTask)\b", "medium",
      {"ugc": None},
      "An upload path sends user-created media to a server"),
    S("ugc-picker", r"\bPHPickerViewController\b|\bUIImagePickerController\b|"
                    r"\bPhotosPicker\b", "low", {"ugc": None},
      "A photo picker often precedes a user upload",
      note="Very weak on its own — many apps pick photos for purely local use."),
    S("ugc-camera", r"\bAVCaptureSession\b|\bUIImagePickerController\.SourceType\.camera",
      "low", {"ugc": None},
      "Camera capture often precedes user-published media",
      note="Weak — scanning, OCR and AR all use the camera without publishing."),
    # `handle` is deliberately absent — `handle:` is a closure parameter in half
    # the Swift ever written.
    S("ugc-displayname", r"\b(displayName|username|userName|nickname)\s*[:=]",
      "low", {"ugc": None},
      "A user-chosen display name is itself user-generated content",
      note="Only counts toward Social Media if the name appears on a shared "
           "surface — see the leaderboard question in the interview."),

    # ── GameKit ──────────────────────────────────────────────────────────
    S("gk-leaderboard", r"\bGKLeaderboard\b|\bGKLeaderboardSet\b|"
                        r"\bGKAccessPoint\b|\breportScore\b", "medium",
      {"social_media": "discovery"},
      "A global leaderboard is a discovery surface; whether it carries UGC "
      "depends on whether display names are freeform",
      note="Only becomes a Social Media yes when combined with freeform display "
           "names — the interview asks."),
    S("gk-alias", r"\bGKPlayer\b.*\balias\b|\blocalPlayer\.alias\b|\bplayer\.alias\b",
      "medium", {"ugc": None},
      "Game Center aliases are user-chosen names shown to other players"),
    S("gk-match", r"\bGKMatch\b|\bGKMatchmaker\b|\bGKMatchRequest\b|"
                  r"\bGKTurnBasedMatch\b", "low", {"messaging": None},
      "GKMatch can carry data messages directly between players",
      note="Usually game state, not communication. Multiplayer matchmaking on "
           "its own is not Messaging and Chat — check whether players can send "
           "each other anything they authored."),
    S("gk-voice", r"\bGKVoiceChat\b", "high", {"messaging": None},
      "GKVoiceChat is direct voice communication between players"),
    S("gk-challenge", r"\bGKChallenge\b|\bissueChallengeToPlayers\b", "medium",
      {"messaging": None},
      "Game Center challenges send a message to another player"),

    # ── web access ───────────────────────────────────────────────────────
    S("web-wkwebview", r"\bWKWebView\b|\bWKWebViewConfiguration\b", "medium",
      {"web_access": None},
      "A WKWebView can reach arbitrary URLs unless navigation is constrained",
      note="Not a finding on its own — a web view pinned to your own domain is "
           "not Unrestricted Web Access. The interview settles it."),
    S("web-uiwebview", r"\bUIWebView\b", "medium", {"web_access": None},
      "UIWebView (deprecated) can reach arbitrary URLs"),
    S("web-safari-vc", r"\bSFSafariViewController\b", "low", {"web_access": None},
      "SFSafariViewController opens web content in-app",
      note="Usually a privacy-policy or support link, which is not Unrestricted "
           "Web Access. Low by design."),
    S("web-ats-arbitrary", r"NSAllowsArbitraryLoads", "medium", {"web_access": None},
      "App Transport Security is relaxed for arbitrary hosts, which is what an "
      "unconstrained browser needs", corpora=("plist", "source")),
    # NB: a function named `searchURL` that builds one fixed https://vendor.com
    # link is not a browser. Only address-bar-shaped identifiers qualify, and
    # even then classify() requires an actual in-app web view to be present.
    S("web-search-in-app", r"\b(addressBar|urlTextField|urlBar|openArbitraryURL|"
                           r"loadArbitraryURL|browserTab|WebBrowserView)\b", "high",
      {"web_access": None},
      "An address bar or in-app browser chrome is Unrestricted Web Access"),
    S("web-nav-policy", r"decidePolicyFor\s+navigationAction|WKNavigationDelegate",
      "low", {}, "Navigation policy is implemented — the web view may be "
                 "constrained to an allowlist",
      mitigates="web-wkwebview",
      note="Mitigating signal: implementing a navigation delegate is evidence "
           "of restriction, though it does not prove one."),

    # ── advertising ──────────────────────────────────────────────────────
    S("ad-admob", r"\bGoogleMobileAds\b|\bGAD(BannerView|InterstitialAd|RewardedAd|"
                  r"NativeAd|AppOpenAd|MobileAds)\b", "high", {"advertising": None},
      "Google AdMob / Google Mobile Ads", corpora=("source", "deps")),
    S("ad-applovin", r"\bAppLovin\b|\bMAAdView\b|\bMAInterstitialAd\b|\bALSdk\b", "high",
      {"advertising": None}, "AppLovin MAX", corpora=("source", "deps")),
    S("ad-ironsource", r"\bIronSource\b|\bISAdUnit\b|\bLevelPlay\b", "high",
      {"advertising": None}, "ironSource / LevelPlay", corpora=("source", "deps")),
    S("ad-unity", r"\bUnityAds\b|\bUADSBanner\b", "high", {"advertising": None},
      "Unity Ads", corpora=("source", "deps")),
    S("ad-meta", r"\bFBAudienceNetwork\b|\bFBAdView\b|\bFBInterstitialAd\b", "high",
      {"advertising": None}, "Meta Audience Network", corpora=("source", "deps")),
    S("ad-vungle", r"\bVungleSDK\b|\bVungleAds\b|\bLiftoff\b", "high",
      {"advertising": None}, "Vungle / Liftoff", corpora=("source", "deps")),
    S("ad-chartboost", r"\bChartboost\b", "high", {"advertising": None},
      "Chartboost", corpora=("source", "deps")),
    S("ad-inmobi", r"\bInMobi\b|\bIMBanner\b", "high", {"advertising": None},
      "InMobi", corpora=("source", "deps")),
    S("ad-mintegral", r"\bMintegral\b|\bMTGSDK\b", "high", {"advertising": None},
      "Mintegral", corpora=("source", "deps")),
    S("ad-pangle", r"\bPangle\b|\bBUAdSDK\b", "high", {"advertising": None},
      "Pangle / ByteDance ads", corpora=("source", "deps")),
    S("ad-tapjoy", r"\bTapjoy\b|\bTJPlacement\b", "high", {"advertising": None},
      "Tapjoy", corpora=("source", "deps")),
    S("ad-adcolony", r"\bAdColony\b", "high", {"advertising": None},
      "AdColony", corpora=("source", "deps")),
    S("ad-fyber", r"\bFyber\b|\bDigitalTurbine\b", "high", {"advertising": None},
      "Fyber / Digital Turbine", corpora=("source", "deps")),
    S("ad-smaato", r"\bSmaato\b", "high", {"advertising": None}, "Smaato",
      corpora=("source", "deps")),
    S("ad-yandex", r"\bYandexMobileAds\b", "high", {"advertising": None},
      "Yandex Mobile Ads", corpora=("source", "deps")),
    S("ad-att", r"\bATTrackingManager\b|NSUserTrackingUsageDescription", "low",
      {"advertising": None},
      "App Tracking Transparency is usually requested for ad attribution",
      corpora=("source", "plist"),
      note="Attribution is not the same as displaying ads. Weak hint."),

    # ── sharing OUT of the app (deliberately weak) ───────────────────────
    S("share-out", r"\bUIActivityViewController\b|\bShareLink\b", "low",
      {"social_media": "discovery"},
      "A share sheet hands content to another app",
      note="Sharing OUT is not a social feed. Apple's definition is about "
           "redistribution through *your* discovery surface. LOW on purpose — "
           "a share button alone should never make this a yes."),
    S("share-extension", r"com\.apple\.share-services", "low",
      {"social_media": "discovery"},
      "A Share Extension receives content from other apps",
      corpora=("plist",),
      note="Receiving shared content is not by itself a feed."),

    # ── push notification categories ─────────────────────────────────────
    S("push-social", r"\b(UNNotificationCategory|categoryIdentifier|"
                     r"notificationCategory)\b.*(comment|mention|follow|like|reply)|"
                     r"[\"'](new_?comment|new_?follower|new_?like|mention|"
                     r"someone_?liked|replied_?to)[\"']", "high",
      {"social_media": "discovery"},
      "Push categories for comments/mentions/follows/likes only exist when "
      "other users act on your content", reach=True),

    # ── In-App Controls ──────────────────────────────────────────────────
    # The questionnaire's first section. No rating attached; these change how
    # you answer everything else.
    S("pc-familycontrols", r"\bFamilyControls\b|\bManagedSettings\b|"
                           r"\bDeviceActivity\b|\bAuthorizationCenter\b", "high",
      {"parental_controls": None},
      "Apple's Screen Time / FamilyControls frameworks are parental controls",
      corpora=("source", "deps")),
    S("pc-gate", r"\b(parentalGate|parentGate|ParentalControls?|parentalLock|"
                 r"kidsMode|childLock|childMode|guardianPIN|parentPIN|"
                 r"restrictedMode|contentRestriction)\b", "high",
      {"parental_controls": None},
      "An in-app parental gate or restricted mode"),
    S("pc-pin", r"\b(pinLock|passcodeLock|appLock|requirePasscode)\b", "low",
      {"parental_controls": None},
      "A passcode lock — sometimes a parental control, often just privacy",
      note="A lock on the whole app is not necessarily a parental control. "
           "Verify it restricts content rather than access."),

    S("aa-declaredagerange", r"\bDeclaredAgeRange\b|\bAgeRangeService\b|"
                             r"\brequestAgeRange\s*\(", "high",
      {"age_assurance": None},
      "A Declared Age Range call is age assurance — Apple's own mechanism",
      corpora=("source", "deps")),
    S("aa-dob-gate", r"\b(ageGate|AgeGate|isOver13|isOver18|isAdult|"
                     r"verifyAge|ageVerif\w*|AgeVerification|minimumAge|"
                     r"birthDate|dateOfBirth|birthYear|dobPicker)\b", "medium",
      {"age_assurance": None},
      "A date-of-birth or age-gate flow confirms the user's age",
      note="A birthdate field collected for a profile is not necessarily an "
           "age gate. Check whether it actually restricts anything."),
    S("aa-vendor", r"\bk-?ID\b|\bAgeKit\b|\bYoti\b|\bPersonaKit\b|\bIncode\b|"
                   r"\bVerifyMy\b|\bAgeChecked\b|\bSuperAwesome\b", "high",
      {"age_assurance": None},
      "A third-party age-assurance vendor SDK", corpora=("source", "deps")),

    # ── Declared Age Range (the carve-out check) ─────────────────────────
    S("dar-import", r"^\s*import\s+DeclaredAgeRange\b", "high", {"carve_out": None},
      "The DeclaredAgeRange framework is imported"),
    S("dar-service", r"\bAgeRangeService\b", "high", {"carve_out": None},
      "AgeRangeService is referenced"),
    S("dar-request", r"\brequestAgeRange\s*\(", "high", {"carve_out": None},
      "requestAgeRange is actually called — not merely imported"),
    S("dar-response", r"\bdeclinedSharing\b|\bAgeRangeDeclaration\b|"
                      r"\bageGates\s*:", "medium", {"carve_out": None},
      "The Declared Age Range response is handled"),
    S("dar-entitlement", r"age-range|declared-age-range", "medium", {"carve_out": None},
      "A Declared Age Range entitlement key is present",
      corpora=("entitlements",),
      note="Apple requires the Declared Age Range capability to be enabled in "
           "Signing & Capabilities. Confirm the key in Xcode rather than "
           "trusting this match."),
]


# ── structured (non-regex) checks ────────────────────────────────────────
# Apple's privacy-manifest data types that mean "this app collects content the
# user made". Per the spec this is the single highest-signal check available,
# because the developer already had to answer it truthfully for a different
# Apple requirement.
USER_CONTENT_DATA_TYPES = {
    "NSPrivacyCollectedDataTypeEmailsOrTextMessages": "Emails or Text Messages",
    "NSPrivacyCollectedDataTypePhotosorVideos": "Photos or Videos",
    "NSPrivacyCollectedDataTypeAudioData": "Audio Data",
    "NSPrivacyCollectedDataTypeGameplayContent": "Gameplay Content",
    "NSPrivacyCollectedDataTypeCustomerSupport": "Customer Support",
    "NSPrivacyCollectedDataTypeOtherUserContent": "Other User Content",
}

# Customer Support is user content in Apple's taxonomy but is a support inbox,
# not a social surface — it must not push an app toward Social Media.
NON_SOCIAL_CONTENT_TYPES = {"NSPrivacyCollectedDataTypeCustomerSupport"}

ADVERTISING_PURPOSES = {
    "NSPrivacyCollectedDataTypePurposeThirdPartyAdvertising": "Third-Party Advertising",
    "NSPrivacyCollectedDataTypePurposeDeveloperAdvertising": "Developer's Advertising or Marketing",
}
