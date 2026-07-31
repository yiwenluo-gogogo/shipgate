"""The rulebook: Apple's age-rating capability questions, verbatim.

Every definition and minimum rating below is quoted from Apple's own pages and
re-verified 31 July 2026. Where Apple contradicts itself — and on the two
load-bearing points it does — both versions are recorded rather than reconciled,
because the disagreement is the developer's actual problem.

  1. The Social Media definition differs between Apple's reference page and its
     9 July 2026 news post. The reference page ends "...that visibly spreads
     content to many users"; the news post drops the clause. That clause is the
     difference between a friends-only feed being in scope or out of it.

  2. The under-13 carve-out row on the reference page lists a minimum rating of
     13+, while the 8 June 2026 news post says selecting it means "your overall
     responses in the age rating questionnaire determine your age rating and may
     result in a rating lower than 13+."

Note what most developers do not know: plain user-generated content and plain
chat are both 4+. Only the feed/discovery shape forces 13+. And Unrestricted Web
Access is 16+ — a *higher* minimum than Social Media, reached by one unconstrained
WKWebView.
"""

# Apple's rating ladder, lowest to highest.
RATING_ORDER = ["4+", "9+", "13+", "16+", "18+"]


def max_rating(ratings):
    """Highest rating in the list, or 4+ for an empty list."""
    best = "4+"
    for r in ratings:
        if RATING_ORDER.index(r) > RATING_ORDER.index(best):
            best = r
    return best


# ── the five capability questions ────────────────────────────────────────
# Ordered as the report presents them: the one that costs you most first.
CAPABILITIES = {
    "social_media": {
        "label": "Social Media",
        "question": "Does your app include social media capabilities?",
        "min_rating": "13+",
        # Reference page, verbatim.
        "definition": (
            "Redistribution, amplification, or interaction with user-generated "
            "content through a social feed or similar discovery method that "
            "visibly spreads content to many users."
        ),
        "examples": (
            "users reposting, liking, commenting, reacting, or making "
            "user-generated content more visible through a social feed, "
            "community, search, or other sharing and discovery tools"
        ),
        # 9 July 2026 news post, verbatim — note the dropped final clause.
        "definition_alt": (
            "the ability to redistribute, amplify, or interact with "
            "user-generated content through a social feed or similar discovery "
            "method"
        ),
        "definition_conflict": (
            "Apple's reference page ends the definition with \"...that visibly "
            "spreads content to many users\". The 9 July 2026 news post drops "
            "that clause. If your feed is friends-only or otherwise limited in "
            "reach, the two texts disagree about whether you are in scope — and "
            "Apple has not said which governs."
        ),
        "costs": [
            "Minimum age rating of 13+.",
            "A Social Media content descriptor on your App Store product page.",
            "Placement in the iOS 27 Social Media Time Allowance category, where "
            "parents' screen-time limits apply to your app.",
            "If you are Made for Kids: incompatible. Made for Kids requires a "
            "calculated 4+/9+ rating and is permanent once approved.",
        ],
        "source": "https://developer.apple.com/help/app-store-connect/reference/age-ratings-values-and-definitions",
    },
    "web_access": {
        "label": "Unrestricted Web Access",
        "question": "Can users navigate to any webpage within your app?",
        "min_rating": "16+",
        "definition": (
            "Users can navigate to any webpage within the app or freely browse "
            "the web."
        ),
        "examples": "embedded browser functionality or browser app",
        "costs": [
            "Minimum age rating of 16+ — higher than Social Media.",
            "Routinely missed: one WKWebView that can reach an arbitrary URL "
            "costs more rating than a full social feed does.",
        ],
        "source": "https://developer.apple.com/help/app-store-connect/reference/age-ratings-values-and-definitions",
    },
    "ugc": {
        "label": "User-Generated Content",
        "question": "Does your app broadly distribute content created by users?",
        "min_rating": "4+",
        "definition": (
            "Includes the broad distribution of content created by users as a "
            "component of the app's intended user experience."
        ),
        "examples": (
            "broadly distributed videos, photos, text, and/or audio created by "
            "users of the app"
        ),
        "costs": [
            "Minimum age rating of 4+ — on its own, UGC costs you nothing.",
            "But UGC is one of the two legs of Social Media. Add a discovery or "
            "amplification surface on top and you are at 13+.",
        ],
        "source": "https://developer.apple.com/help/app-store-connect/reference/age-ratings-values-and-definitions",
    },
    "messaging": {
        "label": "Messaging and Chat",
        "question": "Can users directly communicate with one another in your app?",
        "min_rating": "4+",
        "definition": (
            "Users can directly communicate with one another through features "
            "within the app."
        ),
        "examples": (
            "text, voice and/or video chat, direct and/or group messaging, or "
            "public posting"
        ),
        "costs": [
            "Minimum age rating of 4+ — chat on its own does not force 13+.",
            "Apple's own examples for this question include \"public posting\", "
            "which also reads on Social Media. Answering yes here does not "
            "answer Social Media for you.",
        ],
        "source": "https://developer.apple.com/help/app-store-connect/reference/age-ratings-values-and-definitions",
    },
    "advertising": {
        "label": "Advertising",
        "question": "Does your app show paid promotion of products or services?",
        "min_rating": "4+",
        "definition": "Paid promotion of products or services within the app.",
        "examples": (
            "banner ads, video and playable ads, rich media ads, or native ad "
            "formats"
        ),
        "costs": [
            "Minimum age rating of 4+.",
            "Included because the questionnaire asks it and an ad SDK is trivially "
            "detectable — not because it is a rating risk.",
        ],
        "source": "https://developer.apple.com/help/app-store-connect/reference/age-ratings-values-and-definitions",
    },
}

# Report/interview order — highest cost first.
CAPABILITY_ORDER = ["social_media", "web_access", "ugc", "messaging", "advertising"]


# ── the under-13 carve-out ───────────────────────────────────────────────
UNDER_13_CARVE_OUT = {
    "label": "Social Media Disabled for Users Under 13",
    # Reference page, verbatim.
    "definition": (
        "Users under 13 don't have access to social media capabilities. At a "
        "minimum, the Declared Age Range API is called to check users' age "
        "ranges before enabling social media features. Only age-appropriate UGC "
        "is delivered."
    ),
    "reference_min_rating": "13+",
    # 8 June 2026 news post, verbatim.
    "news_wording": (
        "If you indicate that your app or game includes social media "
        "capabilities but they are disabled for anyone under 13, it won't be "
        "included in the Time Allowance category for Social Media for users "
        "under 13. You'll also need to use the Declared Age Range API (at a "
        "minimum) to check users' age ranges. If you select this option, your "
        "overall responses in the age rating questionnaire determine your age "
        "rating and may result in a rating lower than 13+."
    ),
    "conflict": (
        "Apple's reference page lists this row with a minimum rating of 13+. "
        "Apple's 8 June 2026 news post says your overall questionnaire responses "
        "govern and \"may result in a rating lower than 13+\". These cannot both "
        "be true. Measured in App Store Connect on 31 July 2026, the reference "
        "page is what the questionnaire actually implements: the carve-out does "
        "not lower the calculated rating below 13+."
    ),
    # Answered empirically rather than left open, because this is the question
    # every kids/education developer is actually asking. Run against a real app
    # in App Store Connect (no prior age rating), iOS, with every content
    # question set to NONE and every other capability NO except User-Generated
    # Content = YES, Social Media = YES, Age Assurance = YES. The questionnaire
    # was cancelled, not saved, so no rating was applied to the app.
    "carve_out_measured": {
        "date": "2026-07-31",
        "method": (
            "App Store Connect age-rating questionnaire, 7 steps, calculated "
            "rating read on step 7 before saving. Only the "
            "'Social Media Disabled for Users Under 13' answer was changed "
            "between the two runs."
        ),
        "runs": [
            {"social_media": True, "under_13_disabled": True, "calculated": "13+"},
            {"social_media": True, "under_13_disabled": False, "calculated": "13+"},
        ],
        "finding": (
            "Taking the under-13 carve-out did NOT reduce the calculated age "
            "rating. Both runs returned 13+. On this evidence the carve-out "
            "changes your Time Allowance placement for under-13 users — which is "
            "what the 8 June news post actually promises — but not the age "
            "rating shown on your product page. If a sub-13 rating is why you "
            "were planning to take it, it does not buy you that."
        ),
        "caveats": (
            "One app, one platform, one date. Not tested: Social Media = NO as a "
            "baseline, or the carve-out with Age Assurance = NO. Apple can "
            "change the calculation silently, and the questionnaire's calculated "
            "rating is not a guarantee of what App Review ultimately assigns."
        ),
    },
    "sources": [
        "https://developer.apple.com/help/app-store-connect/reference/age-ratings-values-and-definitions",
        "https://developer.apple.com/news/?id=0d2gpmml",
    ],
}


# ── deadline & scope ─────────────────────────────────────────────────────
REQUIREMENT = {
    "effective": "September 2026",
    # 9 July 2026 news post, verbatim.
    "wording": (
        "Beginning in September 2026, responses will be required when submitting "
        "new apps or updates to the App Store, or when submitting apps for "
        "notarization for alternative distribution."
    ),
    "covers": [
        "new apps submitted to the App Store",
        "updates to apps already on the App Store",
        "apps submitted for notarization for alternative distribution",
    ],
    "unknowns": [
        "Apple has published a month, not a day. Treat 1 September 2026 as the date.",
        "Whether watchOS-only, tvOS-only, visionOS-only and Mac Catalyst "
        "submissions get the same questionnaire is unverified.",
        "What happens to a live app that never answers — blocked from updating, "
        "or delisted — is unverified.",
    ],
    "sources": [
        "https://developer.apple.com/news/?id=tlur8uvi",
        "https://developer.apple.com/news/?id=0d2gpmml",
        "https://developer.apple.com/news/?id=ks775ehf",
    ],
}


# ── the interview ────────────────────────────────────────────────────────
# Static analysis cannot answer these. Each question is gated on `ask_when`: a
# set of conditions evaluated against the scan, so a developer is only asked what
# their own code left genuinely open. `weight` says what a yes does to the
# capability's answer. This is what keeps ShipGate a classifier plus an interview
# rather than an oracle — see README.
INTERVIEW = [
    {
        "id": "SM1",
        "cap": "social_media",
        "q": "Can a user see content created by another user inside your app?",
        "why": "This is the user-generated-content leg of Apple's definition. "
               "Without it there is nothing to redistribute or amplify, and "
               "Social Media is a no regardless of what else you ship.",
        "ask_when": "social_unclear",
        "yes_effect": "leg_ugc",
        "no_effect": "rules_out",
    },
    {
        "id": "SM2",
        "cap": "social_media",
        "q": "Is there a feed, browse, explore, search, gallery or leaderboard "
             "surface where that content is discovered — as opposed to only "
             "arriving in a direct message?",
        "why": "This is the discovery leg. Apple's phrase is \"through a social "
               "feed or similar discovery method\". Direct messaging alone is "
               "the Messaging and Chat question (4+), not this one.",
        "ask_when": "social_unclear",
        "yes_effect": "leg_discovery",
        "no_effect": "rules_out",
    },
    {
        "id": "SM3",
        "cap": "social_media",
        "q": "Can users react to each other's content — like, comment, react, "
             "repost, upvote, or follow another user?",
        "why": "Apple's example list names exactly these verbs. A yes here is "
               "close to dispositive on its own.",
        "ask_when": "social_unclear",
        "yes_effect": "leg_discovery",
        "no_effect": "weakens",
    },
    {
        "id": "SM4",
        "cap": "social_media",
        "q": "Does one user's content reach people beyond a private or "
             "friends-only group — for example everyone in the app, or anyone "
             "who searches?",
        "why": "This is the clause Apple's two texts disagree on. The reference "
               "page's definition ends \"...that visibly spreads content to many "
               "users\"; the 9 July news post drops it. If you answer no here, "
               "you are in scope under one Apple text and out under the other — "
               "which is exactly the case to document before you submit.",
        "ask_when": "social_unclear",
        "yes_effect": "confirms",
        "no_effect": "conflict",
    },
    {
        "id": "SM5",
        "cap": "social_media",
        "q": "Is any feed, gallery or social surface present in the binary but "
             "currently switched off behind a server-side flag?",
        "why": "A feed shipped dark today and enabled next Thursday is still a "
               "capability in the build you are submitting. Static analysis sees "
               "the code; it cannot see your flag service.",
        "ask_when": "always",
        "yes_effect": "confirms",
        "no_effect": "none",
    },
    {
        "id": "WEB1",
        "cap": "web_access",
        "q": "Can a user reach an arbitrary web page in your in-app browser — "
             "via an address bar, a web search, an unvalidated deep link, or a "
             "link inside user-supplied content?",
        "why": "A WKWebView pinned to your own domain is not Unrestricted Web "
               "Access. One that will load whatever URL it is handed is, and "
               "that is 16+ — a higher minimum than Social Media.",
        "ask_when": "web_present",
        "yes_effect": "confirms",
        "no_effect": "rules_out",
    },
    {
        "id": "WEB2",
        "cap": "social_media",
        "q": "Does that web view host a community — a Discord, a forum, a "
             "comments page — rather than your own static content?",
        "why": "A social network rendered inside a web view is still a social "
               "capability of your app. It is one line of Swift and completely "
               "invisible to any static scan.",
        "ask_when": "web_present",
        "yes_effect": "confirms",
        "no_effect": "none",
    },
    {
        "id": "NAME1",
        "cap": "social_media",
        "q": "Are user display names, avatars or profile text freeform — as "
             "opposed to picked from a fixed list you control?",
        "why": "A global leaderboard of freeform display names is user-generated "
               "content on a discovery surface. The same leaderboard with names "
               "drawn from a fixed word list is not.",
        "ask_when": "leaderboard_present",
        "yes_effect": "leg_ugc",
        "no_effect": "weakens",
    },
    {
        "id": "U13A",
        "cap": "carve_out",
        "q": "Is the under-13 gate enforced on your server, or only in the client?",
        "why": "Apple has not said whether a client-side gate behind a Declared "
               "Age Range call is sufficient. A client-only gate is the weaker "
               "position and worth knowing you are in before review asks.",
        "ask_when": "carve_out_claimed",
        "yes_effect": "none",
        "no_effect": "none",
    },
    {
        "id": "MOD1",
        "cap": "ugc",
        "q": "Is user content reviewed — by a human or an automated filter — "
             "before other users can see it?",
        "why": "Moderation does not change the capability answer. It is recorded "
               "because App Review asks about it separately under Guideline "
               "1.2, and because the presence of a moderation pipeline is itself "
               "evidence that you have UGC.",
        "ask_when": "ugc_present",
        "yes_effect": "none",
        "no_effect": "none",
    },
]
