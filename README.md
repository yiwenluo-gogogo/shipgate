# shipgate

A zero-dependency CLI that predicts your answers to Apple's **App Store age-rating
capability questions** before you submit — with file:line evidence for every one,
and the rating each answer costs you.

From **September 2026** Apple will not accept a new app, an update, or a
notarization request until you have answered whether your app has *social media
capabilities*. Answer yes and you take a **minimum 13+ rating**, a **Social Media
descriptor** on your product page, and placement in the **iOS 27 Social Media
Time Allowance** bucket where parents' screen-time limits apply to you. Answer no
and risk a rejection or a post-hoc rating change.

There is no sandbox and no preview in App Store Connect. This is the preview.

## Why this exists

Apple's definition is unambiguous at the two extremes and genuinely undecidable in
the middle — a kids' drawing app with a gallery, a fitness app with a friends
feed, a game with a global leaderboard whose display names are freeform. Worse,
**Apple has published two different definitions and they disagree**, and its
reference page contradicts its own news post about what the under-13 carve-out
buys you. Those two conflicts are documented in [`capability_db.py`](capability_db.py)
with both texts quoted verbatim, and `--explain` prints them side by side.

## Usage

```bash
# stdlib only — nothing to install
python3 shipgate.py /path/to/YourApp
```

```bash
python3 shipgate.py /path/to/YourApp --json                 # machine-readable
python3 shipgate.py /path/to/YourApp --html report.html     # single-file report
python3 shipgate.py /path/to/YourApp --interview            # answer the open questions
python3 shipgate.py --explain                               # the rulebook
python3 shipgate.py --explain --html web/index.html         # the rulebook as a public page
```

`web/index.html` is generated, never hand-edited — it renders straight from
`capability_db.py`, so the public page cannot drift from the rules the CLI applies
when Apple silently edits the reference page.

For CI, answer the interview once and commit the file:

```bash
python3 shipgate.py /path/to/YourApp --answers-template > answers.json
python3 shipgate.py /path/to/YourApp --answers answers.json
```

Exit status is `1` when the predicted rating **exceeds `--expect`** (default `4+`),
`0` otherwise — so it drops straight into a CI step or an Xcode build phase.

## A whole portfolio at once

```bash
python3 shipgate.py --portfolio ~/code/ios-apps
```

```
APP                      RATING  SOCIAL      OPEN
--------------------------------------------------------------
MiniGalaxy               13+     yes         5      above expected  could reach 16+
TravelTogether           13+     likely-yes  9      above expected  could reach 16+
Abandoned                4+      likely-no   6
...
3 of 22 above 4+.
2 with a social capability and no Declared Age Range call: MiniGalaxy, TravelTogether
```

Scans every Xcode project under a directory. Exits non-zero if any app exceeds
`--expect`, so a studio can gate its whole catalogue in one CI step.

## What would it take to get to 4+?

```bash
python3 shipgate.py . --remediate --target 4+
```

A rating is a diagnosis; this is the treatment. It names the *specific* signals and
file:line sites driving each capability, and for Social Media it tells you the thing
that actually matters — you only have to break **one** of the two legs, not both.

It will also stop you wasting a sprint on the wrong fix: gating your feed behind
Declared Age Range does **not** lower the calculated rating. That's measured, not
assumed — see below.

## Catching drift, not just thresholds

```bash
python3 shipgate.py . --save-baseline .shipgate-baseline.json   # once
python3 shipgate.py . --baseline .shipgate-baseline.json        # in CI
```

`--expect` answers "am I above a line". `--baseline` answers "**did this PR change
what I would answer**" — which is the question an app already sitting at 13+ actually
needs. A stricter answer fails the build even when the rating is unchanged.

## In Xcode

Add a Run Script build phase and findings appear inline in the editor, on the line
that caused them:

```bash
python3 "$SRCROOT/shipgate/shipgate.py" "$SRCROOT" --xcode || true
```

Drop the `|| true` once you're clean and a rating rise will fail the build.

## Made for Kids

```bash
python3 shipgate.py . --made-for-kids
```

Made for Kids requires a **calculated** rating of 4+ or 9+, and the choice is
**permanent once approved**. So a kids app that trips 13+ isn't facing a cosmetic
rating change — it loses the category it was built for. This flag makes that a hard
failure, and deliberately overrides `--expect`: "I expected 13+" is not a way to make
an incompatible kids app pass.

## Silencing a false positive

Every static analyzer needs an escape hatch, or it gets uninstalled the first time
it's wrong:

```swift
var isMuted = false   // shipgate:ignore graph-mute -- audio mute, not a user mute
// shipgate:ignore -- everything on the next line
```

A bare `shipgate:ignore` silences every signal on the line; a comma-separated list
silences only those. The comment works on the matching line or the one above it.
Text after `--` is a reason, kept and shown by `--show-suppressed` so suppressions
stay reviewable instead of becoming invisible debt.

## In CI

```yaml
- uses: yiwenluo-gogogo/shipgate@main
  with:
    path: .
    expect: '13+'        # your app's CURRENT App Store rating
```

Set `expect` to what your app is rated **today**. The build then fails only when a
change would *raise* it — which is the alert you actually want. An app that is
legitimately 13+ should not sit permanently red, and a permanently-red check is one
everybody learns to ignore.

The action writes a Markdown summary to the job summary, can emit the HTML report as
an artifact, and exposes outputs you can branch on:

| Input | Default | |
| --- | --- | --- |
| `path` | `.` | Project directory to scan |
| `expect` | `4+` | Fail only above this rating |
| `answers` | — | Interview answers JSON (see `--answers-template`) |
| `report` | — | Write the HTML report here |
| `json` | — | Write the JSON report here |
| `summary` | `true` | Markdown summary in the job summary |
| `fail-on-exceed` | `true` | Set `false` to report without failing |

Outputs: `rating`, `worst-case-rating`, `social-media`, `exceeded`, `open-questions`.

Answer the interview once and commit the file so CI isn't guessing at the things
static analysis genuinely cannot see:

```bash
python3 shipgate.py . --interview            # answer them
python3 shipgate.py . --answers answers.json # then in CI, via the `answers` input
```

## What it answers

All five capability questions, ordered by what they cost you:

| Question | Minimum rating | What triggers it |
| --- | --- | --- |
| **Social Media** | **13+** | UGC *and* a feed/discovery/amplification surface — both legs |
| **Unrestricted Web Access** | **16+** | An in-app web view that can reach a URL you didn't choose |
| User-Generated Content | 4+ | Users create content the app distributes |
| Messaging and Chat | 4+ | Users communicate directly |
| Advertising | 4+ | An ad SDK or a declared advertising purpose |

Plus the **In-App Controls** section the questionnaire opens with — Parental Controls
and Age Assurance. Neither carries a minimum rating, but both change how you are
expected to answer everything after them, because Apple asks you to consider what a
user *with those turned on* encounters. It is easy to miss from the documentation
alone; it is the first thing you see in the real form.

Two things most developers get wrong, both of which this tool makes explicit:

- **Plain UGC and plain chat are 4+.** Only the feed/discovery shape forces 13+.
- **Unrestricted Web Access is 16+ — higher than Social Media.** One unconstrained
  `WKWebView` costs more rating than a full social feed does.

Predictions come in five bands: `yes`, `likely-yes`, `unclear`, `likely-no`, `no`.
Every prediction above `no` carries at least one file:line citation.

## The design rule: two legs, and reach

Apple defines Social Media as *"redistribution, amplification, or interaction with
user-generated content through a social feed or similar discovery method."* That
is two things, not one, and ShipGate models it that way:

- **UGC leg** — content created by a user
- **DISCOVERY leg** — a feed, browse, search, gallery or leaderboard surface, or
  an amplification verb (like, comment, react, repost, follow)

A signal supplying only one leg can never produce a yes. This is the tool's main
brake on false positives, and it is why **Firebase on its own scores nothing**:
half the App Store uses it, and storing user data is not a social feed.

There is a third gate. Apple's reference page ends the definition *"...that
visibly spreads content to many users"* — and the 9 July 2026 news post drops that
clause. **Reach is a server fact no static scan can see**, so ShipGate only
commits to a hard `yes` when it finds a signal that *implies* broad reach: a
follower graph, an explore/trending tab, a public feed, a public CloudKit
database. With both legs but no reach signal it stops at `likely-yes` and tells
you that under one Apple text you are already in scope and under the other you are
not. That case is the product.

## Classifier, not oracle

Some things are fundamentally not statically detectable, and the report says so
per finding rather than guessing:

- whether a feed visibly spreads content to many users (reach is a server fact)
- a feed shipped dark today behind a flag and enabled next Thursday
- whether UGC is moderated before publication
- what lives behind a `WKWebView` URL — a Discord community is one line of Swift
- whether an under-13 gate is enforced server-side or only in the client
- whether display names are freeform or drawn from a fixed word list

So ShipGate is **a classifier plus a short interview**. Static evidence eliminates
the questions it can answer and narrows the rest to the three or four you must
answer yourself. The artifact is a defensible answer sheet with citations. Anyone
marketing this kind of tool as an oracle is the fastest way to be wrong in public.

## The under-13 carve-out check

If you claim *"Social Media Disabled for Users Under 13"*, Apple requires that the
Declared Age Range API **is called**. ShipGate checks that it is actually wired
rather than merely intended — import, a real `requestAgeRange()` call site,
response handling, and the capability entitlement — and flags the common failure
where the framework is imported and never called.

It also surfaces the conflict: Apple's reference page lists that row with a
**minimum rating of 13+**, while Apple's 8 June 2026 news post says your overall
questionnaire responses govern and *"may result in a rating lower than 13+"*.
These cannot both be true. If a sub-13 rating is why you are taking the carve-out,
do not assume you get it.

## Accuracy

Measured against a hand-labelled corpus of real shipping apps:

```bash
cp labels.example.json labels.json   # then point the paths at your own projects
python3 validate.py                  # add --verbose for per-app evidence
```

No corpus ships with this repo — the apps it was measured against are private, and
an accuracy number you cannot reproduce is worth little anyway. The format and the
labelling discipline are in [`labels.example.json`](labels.example.json).

Scoring is deliberately unkind: an app labelled **ambiguous** is scored correct only
if the tool **declines to commit**, because a confident wrong answer is the failure
mode that gets a developer rejected. Labels must be written *before* the classifier
runs — labels written after seeing the output measure nothing.

Against the author's own 22-app corpus it currently scores **22/22** — 2/2 yes,
19/19 no, 1/1 ambiguous.

Four real false positives were found and fixed by that harness, which is a fair
sample of how this kind of tool goes wrong:

- `unlike\w*` matched the English word **"unlikely"** in code comments
- `isMuted` matched the **audio mute** in a snake game, which alone forced a 13+
- a function named `searchURL` building one fixed vendor link read as a **browser**
- a nested agent worktree under `.claude/` held a full repo copy, so scanning one
  app **inherited every other app's** like/comment/follow evidence

The last one is the important one: a compliance tool that reports another app's
capabilities as yours is worse than no tool. Dot-directories are now pruned.

## Limitations

- **Corpus bias.** The corpus behind that 22/22 is one developer's apps — mostly
  solo content apps, only 1 of 22 genuinely ambiguous. That is *not* a sample of
  the App Store, and `validate.py` says so on every run. Label apps you did not
  write before drawing conclusions about the size of the ambiguous middle.
- **Source, not binaries.** `--ipa` inventories bundled SDKs only; identifier-level
  evidence needs the project directory.
- **Server-driven UI is invisible.** The `codingkeys-social` signal catches some of
  it by reading your networking models, but a feed assembled entirely server-side
  can be missed. The interview asks.
- **Apple's wording drifts.** The age-ratings reference page changes silently.
  Every quote in `capability_db.py` carries its source URL — diff it before a
  submission you are betting on.

## How it works

1. Walks the project, classifying files into four corpora — source
   (`.swift/.m/.mm/.h/.c/.cc/.cpp`), dependency manifests (`Package.resolved`,
   `Podfile.lock`, `*.pbxproj`), `Info.plist`, and `.entitlements` — skipping
   build output, `Pods/`, `Carthage/`, dot-directories and `*Tests/` targets.
2. Runs each signal only against the corpora it declares, recording file:line and
   a confidence level. Mitigating signals downgrade others (a `WKNavigationDelegate`
   lowers confidence in `WKWebView`; RSS parsing lowers confidence in "feed").
3. Reads your own `PrivacyInfo.xcprivacy` for user-content data types — the
   highest-signal check available, because you already had to answer it truthfully
   for a different Apple requirement.
4. Applies the two-leg + reach rule for Social Media, per-capability rules for the
   rest, folds in any interview answers, then computes the resulting minimum
   rating and Time Allowance consequence.

## Files

| File | What it is |
| --- | --- |
| [`shipgate.py`](shipgate.py) | Scanner, classifier, interview, CLI |
| [`capability_db.py`](capability_db.py) | The rulebook — Apple's wording verbatim, with both conflicts |
| [`signals.py`](signals.py) | Detectable evidence, with the anti-false-positive discipline |
| [`report.py`](report.py) | Single-file HTML report |
| [`validate.py`](validate.py) | Accuracy harness against a labelled corpus |
| [`labels.example.json`](labels.example.json) | Corpus format and labelling discipline |
| [`action.yml`](action.yml) | GitHub Action (composite) |
| [`tests/run_fixtures.sh`](tests/run_fixtures.sh) | Regression suite — needs no private corpus |

## Disclaimer

Guidance tool, not legal advice, and not an oracle. Apple's requirements change;
re-verify against the current App Store Connect reference before a submission you
are betting on.

## License

MIT — see [LICENSE](LICENSE). Free to use, fork, and ship inside your own tooling.
