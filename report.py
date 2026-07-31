"""Single-file HTML report.

The artifact a developer keeps: a defensible answer sheet with citations, not an
oracle's verdict. Everything is inlined — no fonts, no CDN, no network — because
this gets attached to an App Review appeal or dropped in a CI artifact bucket.
"""

import html

from capability_db import (CAPABILITIES, CAPABILITY_ORDER, REQUIREMENT,
                           UNDER_13_CARVE_OUT)

CSS = """
:root{--bg:#fff;--fg:#16181d;--dim:#6b7280;--line:#e5e7eb;--card:#fafafa;
--yes:#b91c1c;--maybe:#b45309;--unclear:#a16207;--no:#15803d;--flag:#7c3aed;
--code:#f3f4f6}
@media(prefers-color-scheme:dark){:root{--bg:#0e1116;--fg:#e6e8eb;--dim:#9aa3af;
--line:#242a33;--card:#151a21;--yes:#f87171;--maybe:#fbbf24;--unclear:#fcd34d;
--no:#4ade80;--flag:#c4b5fd;--code:#1b212a}}
*{box-sizing:border-box}
body{margin:0;padding:2rem 1.25rem 4rem;background:var(--bg);color:var(--fg);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:52rem;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 .25rem}
h2{font-size:1.05rem;margin:2.5rem 0 .75rem;padding-bottom:.4rem;
border-bottom:1px solid var(--line)}
h3{font-size:.95rem;margin:1.5rem 0 .4rem}
.sub{color:var(--dim);font-size:.85rem;margin:0 0 2rem;word-break:break-all}
.verdict{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:1.25rem;margin:0 0 1rem}
.rating{font-size:2.5rem;font-weight:700;line-height:1;margin:.25rem 0}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:.78rem;text-transform:uppercase;
letter-spacing:.04em}
.tag{display:inline-block;padding:.1rem .5rem;border-radius:999px;
font-size:.72rem;font-weight:700;letter-spacing:.03em;white-space:nowrap}
.a-yes{background:var(--yes);color:#fff}
.a-likely-yes{background:var(--maybe);color:#fff}
.a-unclear{background:var(--unclear);color:#3b2f04}
.a-likely-no{background:transparent;color:var(--dim);border:1px solid var(--line)}
.a-no{background:transparent;color:var(--no);border:1px solid currentColor}
.cap{border:1px solid var(--line);border-radius:10px;padding:1rem 1.1rem;
margin:0 0 .9rem;background:var(--card)}
.cap .why{color:var(--fg);margin:.5rem 0 0}
.quote{border-left:3px solid var(--line);padding:.1rem 0 .1rem .8rem;
color:var(--dim);font-size:.87rem;margin:.6rem 0}
.sig{margin:.9rem 0 0;padding:.6rem .75rem;background:var(--bg);
border:1px solid var(--line);border-radius:7px}
.sig .name{font:600 .8rem/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
.sig .meta{color:var(--dim);font-size:.75rem}
.sig .why{font-size:.87rem;margin:.25rem 0 .4rem}
code{background:var(--code);padding:.08rem .3rem;border-radius:4px;
font:.78rem/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-all}
.hit{font:.76rem/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--dim);
display:block;word-break:break-all}
.note{color:var(--dim);font-size:.8rem;margin:.35rem 0 0;font-style:italic}
.flag{border:1px solid var(--flag);border-radius:10px;padding:1rem 1.1rem;
margin:1rem 0}
.flag h3{color:var(--flag);margin-top:0}
ul{margin:.4rem 0;padding-left:1.2rem}
li{margin:.2rem 0}
.check{list-style:none;padding:0}
.check li{margin:.35rem 0}
.ok{color:var(--no);font-weight:700}
.bad{color:var(--yes);font-weight:700}
.q{margin:.8rem 0;padding-left:.9rem;border-left:3px solid var(--unclear)}
.q .id{font:700 .78rem ui-monospace,Menlo,monospace;color:var(--dim)}
footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);
color:var(--dim);font-size:.8rem}
a{color:inherit}
"""


def e(s):
    return html.escape(str(s))


# ── the public explainer page ────────────────────────────────────────────
# Generated from capability_db.py rather than hand-written, so the page cannot
# drift from the rulebook the CLI uses. Apple edits the reference page silently;
# when that happens, one edit updates the tool, `--explain`, and this page.

# The page is public; this repo must therefore be public too. Pointing it at the
# caviar monorepo path would 404 for every visitor, since caviar is private.
REPO_URL = "https://github.com/yiwenluo-gogogo/shipgate"

EXPLAIN_EXTRA_CSS = """
.hero{border:1px solid var(--line);border-radius:12px;padding:1.5rem;
background:var(--card);margin:0 0 2rem}
.deadline{display:inline-block;padding:.2rem .6rem;border-radius:999px;
background:var(--yes);color:#fff;font-size:.75rem;font-weight:700;
letter-spacing:.04em;text-transform:uppercase}
.lede{font-size:1.05rem;margin:.9rem 0 0}
.cost{font-size:.9rem;margin:.6rem 0 0;padding-left:1.1rem}
.rating-badge{display:inline-block;min-width:3rem;text-align:center;
padding:.15rem .5rem;border-radius:6px;font-weight:700;font-size:.8rem;
background:var(--code)}
.r13,.r16{background:var(--yes);color:#fff}
.mental{border:1px solid var(--line);border-left:4px solid var(--fg);
border-radius:8px;padding:1rem 1.1rem;margin:1.5rem 0;background:var(--card)}
.mental h3{margin-top:0}
"""


def render_explain_html():
    """Standalone, self-contained reference page. Full document — this one is
    served to the public, so it needs a head, a description and OG tags."""
    p = []
    w = p.append
    title = ("Apple's five App Store capability questions — and what each one "
             "costs you")
    desc = ("From September 2026 Apple requires an answer on social media "
            "capabilities for every App Store submission. Here is each "
            "question, Apple's exact wording, the minimum age rating it forces, "
            "and the two places Apple contradicts itself.")

    w("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    w("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    w("<title>%s</title>" % e(title))
    w("<meta name='description' content='%s'>" % e(desc))
    w("<meta property='og:title' content='%s'>" % e(title))
    w("<meta property='og:description' content='%s'>" % e(desc))
    w("<meta property='og:type' content='article'>")
    w("<style>%s%s</style></head><body><main>" % (CSS, EXPLAIN_EXTRA_CSS))

    w('<div class="hero">')
    w('<span class="deadline">Required from %s</span>'
      % e(REQUIREMENT["effective"]))
    w("<h1>Apple's five capability questions, and what each one costs you</h1>")
    w('<p class="lede">&ldquo;%s&rdquo;</p>' % e(REQUIREMENT["wording"]))
    w("<p>Answer <strong>yes</strong> to social media capabilities and you take "
      "a minimum <strong>13+</strong> rating, a Social Media descriptor on your "
      "product page, and placement in the iOS 27 Social Media Time Allowance "
      "category where parents' screen-time limits apply to you. Answer no and "
      "risk a rejection or a post-hoc rating change. App Store Connect gives you "
      "no examples page, no pre-check and no sandbox.</p>")
    w("</div>")

    # The mental model that actually resolves most cases.
    w('<div class="mental">')
    w("<h3>The part most developers get wrong</h3>")
    w("<p><strong>Plain user-generated content is 4+. Plain chat is 4+.</strong> "
      "Neither forces 13+ on its own. Only the <em>feed or discovery shape</em> "
      "does &mdash; a surface where one user's content is redistributed, "
      "amplified or made more visible to others.</p>")
    w("<p>Apple's definition is really two conditions that must both hold:</p>")
    w("<ul><li><strong>User-generated content</strong> &mdash; a user made it</li>"
      "<li><strong>A discovery or amplification surface</strong> &mdash; a feed, "
      "browse, search, gallery or leaderboard, or a verb like like, comment, "
      "react, repost, follow</li></ul>")
    w("<p>A photo picker, a backend, or a share-sheet button gives you the first "
      "without the second. That is not social media.</p>")
    w("<p><strong>And watch the 16+ trap:</strong> Unrestricted Web Access has a "
      "<em>higher</em> minimum than Social Media. One in-app web view that can "
      "reach a URL you didn't choose costs you more rating than a full social "
      "feed does.</p>")
    w("</div>")

    # Summary table.
    w("<h2>The five questions</h2>")
    w("<table><thead><tr><th>Question</th><th>Minimum rating</th></tr></thead>"
      "<tbody>")
    for key in CAPABILITY_ORDER:
        cap = CAPABILITIES[key]
        cls = "rating-badge"
        if cap["min_rating"] in ("13+", "16+"):
            cls += " r13"
        w("<tr><td><a href='#%s'>%s</a></td>"
          "<td><span class='%s'>%s</span></td></tr>"
          % (e(key), e(cap["label"]), cls, e(cap["min_rating"])))
    w("</tbody></table>")

    # Per-question detail.
    for key in CAPABILITY_ORDER:
        cap = CAPABILITIES[key]
        w('<div class="cap" id="%s">' % e(key))
        w("<h3>%s &mdash; minimum %s</h3>" % (e(cap["label"]), e(cap["min_rating"])))
        w("<p><em>%s</em></p>" % e(cap["question"]))
        w('<div class="quote">Apple: &ldquo;%s&rdquo;<br><em>May include: %s</em>'
          "</div>" % (e(cap["definition"]), e(cap["examples"])))
        w('<ul class="cost">')
        for cost in cap["costs"]:
            w("<li>%s</li>" % e(cost))
        w("</ul>")
        if cap.get("definition_alt"):
            w('<div class="flag"><h3>Apple has published two definitions of this'
              "</h3>")
            w("<p><strong>Reference page:</strong> &ldquo;%s&rdquo;</p>"
              % e(cap["definition"]))
            w("<p><strong>News post, 9 July 2026:</strong> &ldquo;%s&rdquo;</p>"
              % e(cap["definition_alt"]))
            w("<p>%s</p></div>" % e(cap["definition_conflict"]))
        w('<p class="note"><a href="%s">%s</a></p>'
          % (e(cap["source"]), e(cap["source"])))
        w("</div>")

    # Carve-out.
    w("<h2>%s</h2>" % e(UNDER_13_CARVE_OUT["label"]))
    w('<div class="cap">')
    w('<div class="quote">Apple: &ldquo;%s&rdquo;</div>'
      % e(UNDER_13_CARVE_OUT["definition"]))
    w("<p>If you take this option, Apple requires that the Declared Age Range "
      "API <strong>is called</strong> &mdash; an import with no call site does "
      "not qualify.</p></div>")
    w('<div class="flag"><h3>Apple contradicts itself on what this buys you</h3>')
    w("<p>Apple's reference page lists this row with a minimum rating of "
      "<strong>%s</strong>. Apple's 8 June 2026 news post says your overall "
      "questionnaire responses govern and &ldquo;may result in a rating lower "
      "than 13+&rdquo;. These cannot both be true.</p>"
      % e(UNDER_13_CARVE_OUT["reference_min_rating"]))
    w('<div class="quote">Reference page: minimum rating <strong>%s</strong>.'
      "<br>News post, 8 June 2026: &ldquo;%s&rdquo;</div></div>"
      % (e(UNDER_13_CARVE_OUT["reference_min_rating"]),
         e(UNDER_13_CARVE_OUT["news_wording"])))

    # The measured answer. This is the part nobody else has published.
    m = UNDER_13_CARVE_OUT["carve_out_measured"]
    w('<div class="mental"><h3>So we measured it</h3>')
    w("<p>We ran Apple's own questionnaire in App Store Connect on %s against a "
      "real app with no prior age rating, changing <em>only</em> the under-13 "
      "answer between runs. Every content question was set to None.</p>"
      % e(m["date"]))
    w("<table><thead><tr><th>Social Media</th>"
      "<th>Social Media Disabled for Users Under 13</th>"
      "<th>Calculated rating</th></tr></thead><tbody>")
    for r in m["runs"]:
        w("<tr><td>%s</td><td><strong>%s</strong></td>"
          "<td><span class='rating-badge r13'>%s</span></td></tr>"
          % ("Yes" if r["social_media"] else "No",
             "Yes" if r["under_13_disabled"] else "No",
             e(r["calculated"])))
    w("</tbody></table>")
    w("<p><strong>%s</strong></p>" % e(m["finding"]))
    w('<p class="note">%s</p></div>' % e(m["caveats"]))

    w("<h2>Still unknown</h2><ul>")
    for u in REQUIREMENT["unknowns"]:
        w("<li>%s</li>" % e(u))
    w("</ul>")

    w("<h2>Check your own app</h2>")
    w("<p><code>shipgate</code> is a free, zero-dependency CLI that predicts "
      "each of these answers from your Xcode project with file:line evidence, "
      "computes the resulting rating, and checks whether your under-13 carve-out "
      "is actually wired. It is a classifier plus a short interview, not an "
      "oracle &mdash; reach and server-driven features are things no static scan "
      "can see, and it says so per finding.</p>")
    w("<p><a href=\"%s\">%s</a> &middot; MIT</p>"
      % (e(REPO_URL), e(REPO_URL.replace("https://", ""))))

    w("<footer><p>Every quote on this page is from Apple's own pages, linked "
      "above, and was re-verified on 31 July 2026. Apple edits the age-ratings "
      "reference page silently &mdash; re-check before a submission you are "
      "betting on. Guidance, not legal advice.</p></footer>")
    w("</main></body></html>")
    return "\n".join(p)


def render_html(rep):
    p = []
    w = p.append

    w("<style>%s</style>" % CSS)
    w("<main>")
    w("<h1>ShipGate report</h1>")
    w('<p class="sub">%s</p>' % e(rep["root"]))

    # ── verdict ──────────────────────────────────────────────────────────
    w('<div class="verdict">')
    w("<div>Predicted minimum age rating</div>")
    w('<div class="rating">%s</div>' % e(rep["minimum_rating"]))
    if rep["worst_case_rating"] != rep["minimum_rating"]:
        w("<div>Rises to <strong>%s</strong> if the unclear answers below turn "
          "out to be yes.</div>" % e(rep["worst_case_rating"]))
    if rep["time_allowance_social"]:
        w("<ul>"
          "<li>Placed in the iOS 27 <strong>Social Media Time Allowance</strong> "
          "category, where parents' screen-time limits apply.</li>"
          "<li>A <strong>Social Media descriptor</strong> appears on your product "
          "page.</li>"
          "<li>Incompatible with <strong>Made for Kids</strong>, which requires a "
          "calculated 4+/9+ rating and is permanent once approved.</li>"
          "</ul>")
    w("</div>")

    # ── summary table ────────────────────────────────────────────────────
    w("<table><thead><tr><th>Question</th><th>Predicted answer</th>"
      "<th>Minimum</th></tr></thead><tbody>")
    for key in CAPABILITY_ORDER:
        cap = rep["capabilities"][key]
        w("<tr><td>%s</td><td><span class='tag a-%s'>%s</span></td>"
          "<td>%s</td></tr>" % (e(cap["label"]), e(cap["answer"]),
                                e(cap["answer"].replace("-", " ").upper()),
                                e(cap["min_rating"])))
    w("</tbody></table>")

    # ── definitional conflict ────────────────────────────────────────────
    if rep["definition_conflict"]:
        w('<div class="flag"><h3>Apple\'s two definitions disagree about your app</h3>')
        w("<p>%s</p>" % e(CAPABILITIES["social_media"]["definition_conflict"]))
        w("<p>You answered that content does not spread beyond a private or "
          "friends-only group. Under Apple's reference page you are "
          "<strong>out of scope</strong>; under the 9 July 2026 news post you are "
          "<strong>in</strong>. Keep this page — it is the most defensible thing "
          "you can attach to a rating appeal.</p></div>")

    # ── per-capability evidence ──────────────────────────────────────────
    w("<h2>Evidence</h2>")
    for key in CAPABILITY_ORDER:
        cap = rep["capabilities"][key]
        db = CAPABILITIES[key]
        if cap["answer"] == "no" and not cap["evidence"]:
            continue
        w('<div class="cap">')
        w("<h3>%s <span class='tag a-%s'>%s</span></h3>"
          % (e(cap["label"]), e(cap["answer"]),
             e(cap["answer"].replace("-", " ").upper())))
        w('<div class="quote">Apple: &ldquo;%s&rdquo;<br><em>May include: %s</em>'
          '</div>' % (e(db["definition"]), e(db["examples"])))
        w('<p class="why">%s</p>' % e(cap["why"]))
        ranked = sorted(cap["evidence"],
                        key=lambda r: -{"low": 0, "medium": 1, "high": 2}[r["confidence"]])
        for r in ranked:
            w('<div class="sig">')
            legs = (" &middot; %s leg" % e("+".join(r["legs"]))) if r["legs"] else ""
            w('<div><span class="name">%s</span> '
              '<span class="meta">%s confidence%s &middot; %d occurrence(s)</span>'
              '</div>' % (e(r["signal"]), e(r["confidence"]), legs, r["count"]))
            w('<p class="why">%s</p>' % e(r["why"]))
            for h in r["hits"]:
                loc = "%s:%s" % (h["file"], h["line"]) if h["line"] else h["file"]
                w('<span class="hit">%s &nbsp; %s</span>' % (e(loc), e(h["text"])))
            if r["mitigated_by"]:
                w('<p class="note">Downgraded from %s because %s also fired.</p>'
                  % (e(r["declared_confidence"]), e(", ".join(r["mitigated_by"]))))
            if r["note"]:
                w('<p class="note">%s</p>' % e(r["note"]))
            w("</div>")
        w('<p class="note"><a href="%s">%s</a></p>' % (e(db["source"]), e(db["source"])))
        w("</div>")

    # ── carve-out ────────────────────────────────────────────────────────
    carve = rep["carve_out"]
    if carve["relevant"]:
        w("<h2>Under-13 carve-out</h2>")
        w('<div class="cap">')
        w("<h3>%s &mdash; %s</h3>" % (e(UNDER_13_CARVE_OUT["label"]),
                                      e(carve["verdict"].upper())))
        w('<div class="quote">Apple: &ldquo;%s&rdquo;</div>'
          % e(UNDER_13_CARVE_OUT["definition"]))
        w("<p>%s</p>" % e(carve["summary"]))
        w('<ul class="check">')
        for chk in carve["checks"]:
            mark = '<span class="ok">&#10003;</span>' if chk["ok"] \
                else '<span class="bad">&#10007;</span>'
            w("<li>%s %s" % (mark, e(chk["item"])))
            if not chk["ok"]:
                w('<div class="note">%s</div>' % e(chk["detail"]))
            w("</li>")
        w("</ul></div>")
        w('<div class="flag"><h3>Apple contradicts itself on what this buys you</h3>')
        w("<p>%s</p>" % e(UNDER_13_CARVE_OUT["conflict"]))
        w('<div class="quote">Reference page: minimum rating <strong>%s</strong>.'
          '<br>News post, 8 June 2026: &ldquo;%s&rdquo;</div>'
          % (e(UNDER_13_CARVE_OUT["reference_min_rating"]),
             e(UNDER_13_CARVE_OUT["news_wording"])))
        w("</div>")

    # ── interview ────────────────────────────────────────────────────────
    if rep["interview_applied"]:
        w("<h2>Your interview answers</h2><ul>")
        for a in rep["interview_applied"]:
            w("<li><code>%s</code> &rarr; <strong>%s</strong> &mdash; %s</li>"
              % (e(a["id"]), "yes" if a["answer"] else "no", e(a["effect"])))
        w("</ul>")

    if rep["interview_pending"]:
        w("<h2>Open questions</h2>")
        w("<p>Static analysis cannot answer these. They are what separates a "
          "defensible answer sheet from a guess.</p>")
        for q in rep["interview_pending"]:
            w('<div class="q"><span class="id">%s</span><br><strong>%s</strong>'
              '<p class="note">%s</p></div>'
              % (e(q["id"]), e(q["q"]), e(q["why"])))

    # ── footer ───────────────────────────────────────────────────────────
    w("<footer>")
    w("<p><strong>Deadline:</strong> %s. &ldquo;%s&rdquo;</p>"
      % (e(REQUIREMENT["effective"]), e(REQUIREMENT["wording"])))
    w("<p>Still unknown:</p><ul>")
    for u in REQUIREMENT["unknowns"]:
        w("<li>%s</li>" % e(u))
    w("</ul>")
    w("<p>Sources: " + " &middot; ".join(
        '<a href="%s">%s</a>' % (e(s), e(s)) for s in REQUIREMENT["sources"]) + "</p>")
    w("<p>ShipGate is a guidance tool, not legal advice, and not an oracle. "
      "Apple's wording changes; re-check every quote above before a submission "
      "you are betting on.</p>")
    w("</footer></main>")
    return "\n".join(p)
