#!/usr/bin/env python3
"""shipgate — predict your answers to Apple's App Store age-rating capability
questions before you submit, with file:line evidence for every one.

From September 2026 Apple will not accept a new app, an update, or a notarization
request until you have answered whether your app has "social media capabilities."
Answer yes and you take a minimum 13+ rating, a Social Media descriptor on your
product page, and placement in the iOS 27 Social Media Time Allowance bucket.
There is no sandbox and no preview. This is the preview.

Usage:
    shipgate.py PATH [--json] [--html FILE] [--answers FILE] [--interview]
    shipgate.py --explain            # the rulebook: five questions, what each costs
    shipgate.py PATH --answers-template > answers.json

Exit status is non-zero when any capability lands above 4+, so it drops into CI.

Stdlib only — no install step. Run with any Python 3.9+ (CI proves 3.9/3.11/3.13;
macOS has shipped 3.9 since Monterey).

Guidance tool, not legal advice. Apple's wording changes; every quote carries its
source URL so you can re-check before a submission you are betting on.
"""

import argparse
import json
import os
import plistlib
import re
import sys
import zipfile

from capability_db import (CAPABILITIES, CAPABILITY_ORDER, INTERVIEW,
                           RATING_ORDER, REQUIREMENT, UNDER_13_CARVE_OUT,
                           max_rating)
from signals import (ADVERTISING_PURPOSES, NON_SOCIAL_CONTENT_TYPES, SIGNALS,
                     USER_CONTENT_DATA_TYPES, leg_of)

SKIP_DIRS = {
    "build", "DerivedData", "Pods", "Carthage",
    "node_modules", "vendor", "fastlane",
}


def prune(dirnames):
    """Filter a walk's directory list, in place, to things that are actually
    part of *this* app.

    Dot-directories are skipped wholesale. That is not cosmetic: agent worktrees
    under `.claude/worktrees/` hold complete checkouts of sibling projects, and
    scanning one app was silently pulling in every other app in the repo — a
    trip-planning app inherited a social network's like/comment/follow evidence
    and came back 13+. A compliance tool that reports another app's capabilities
    as yours is worse than no tool.
    """
    dirnames[:] = [d for d in dirnames
                   if not d.startswith(".")
                   and d not in SKIP_DIRS
                   and not d.endswith(".xcarchive")]
    return dirnames
CODE_EXTS = {".swift", ".m", ".mm", ".h", ".c", ".cc", ".cpp", ".hpp"}
DEP_FILES = {"Package.swift", "Package.resolved", "Podfile", "Podfile.lock",
             "Cartfile", "Cartfile.resolved"}
MANIFEST_NAME = "PrivacyInfo.xcprivacy"

RANK = {"low": 0, "medium": 1, "high": 2}
# Prediction bands, weakest to strongest.
ANSWERS = ["no", "likely-no", "unclear", "likely-yes", "yes"]

# Real source trees contain form feeds, vertical tabs and stray control bytes.
# They survive errors="ignore" decoding, then poison JSON and HTML downstream.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def excerpt(line):
    """A source line safe to embed in JSON, HTML and a terminal."""
    return CONTROL_CHARS.sub(" ", line).strip()[:120]


# ── corpus walk ──────────────────────────────────────────────────────────
def corpus_of(path):
    """Which scan corpus a file belongs to, or None to skip it."""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1]
    if ext in CODE_EXTS:
        return "source"
    if name in DEP_FILES or ext == ".pbxproj":
        return "deps"
    if ext == ".plist":
        return "plist"
    if ext == ".entitlements":
        return "entitlements"
    return None


def iter_files(root):
    """Yield (path, corpus). Test targets are excluded — they do not ship, so
    their capabilities are not the app's."""
    for dirpath, dirnames, filenames in os.walk(root):
        prune(dirnames)
        # Test targets do not ship, so their capabilities are not the app's.
        dirnames[:] = [d for d in dirnames
                       if not d.endswith("Tests") and not d.endswith("UITests")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            corpus = corpus_of(path)
            if corpus:
                yield path, corpus


def scan(root):
    """Run every signal against every file in its declared corpora.

    Returns {signal_id: {"count", "hits": [{file,line,text}]}}.
    """
    fired = {}
    counts = {"source": 0, "deps": 0, "plist": 0, "entitlements": 0}
    for path, corpus in iter_files(root):
        counts[corpus] += 1
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        active = [s for s in SIGNALS if corpus in s["corpora"]]
        for lineno, line in enumerate(lines, 1):
            for sig in active:
                if sig["rx"].search(line):
                    bucket = fired.setdefault(sig["id"], {"count": 0, "hits": []})
                    bucket["count"] += 1
                    if len(bucket["hits"]) < 5:
                        bucket["hits"].append({
                            "file": os.path.relpath(path, root),
                            "line": lineno,
                            "text": excerpt(line),
                        })
    return fired, counts


# ── structured checks ────────────────────────────────────────────────────
def scan_privacy_manifests(root):
    """Read the app's own PrivacyInfo.xcprivacy files.

    Per the spec this is the single highest-signal check: the developer already
    had to answer "do you collect user content" truthfully for a *different*
    Apple requirement, so it is a declaration rather than an inference.
    """
    found = {"manifests": [], "user_content": [], "advertising_purposes": [],
             "contacts": False}
    for dirpath, dirnames, filenames in os.walk(root):
        prune(dirnames)
        if MANIFEST_NAME not in filenames:
            continue
        path = os.path.join(dirpath, MANIFEST_NAME)
        found["manifests"].append(os.path.relpath(path, root))
        try:
            with open(path, "rb") as fh:
                data = plistlib.load(fh)
        except (OSError, plistlib.InvalidFileException, ValueError):
            continue
        for entry in data.get("NSPrivacyCollectedDataTypes", []) or []:
            dtype = entry.get("NSPrivacyCollectedDataType", "")
            if dtype in USER_CONTENT_DATA_TYPES:
                found["user_content"].append({
                    "type": dtype,
                    "label": USER_CONTENT_DATA_TYPES[dtype],
                    "file": os.path.relpath(path, root),
                    "social_relevant": dtype not in NON_SOCIAL_CONTENT_TYPES,
                })
            if dtype == "NSPrivacyCollectedDataTypeContacts":
                found["contacts"] = True
            for purpose in entry.get("NSPrivacyCollectedDataTypePurposes", []) or []:
                if purpose in ADVERTISING_PURPOSES:
                    found["advertising_purposes"].append({
                        "purpose": purpose,
                        "label": ADVERTISING_PURPOSES[purpose],
                        "file": os.path.relpath(path, root),
                    })
    return found


def scan_info_plists(root):
    """Structured Info.plist facts: relaxed ATS and Share Extension targets."""
    facts = {"arbitrary_loads": [], "share_extensions": []}
    for dirpath, dirnames, filenames in os.walk(root):
        prune(dirnames)
        for name in filenames:
            if not name.endswith(".plist"):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, "rb") as fh:
                    data = plistlib.load(fh)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            ats = data.get("NSAppTransportSecurity") or {}
            if isinstance(ats, dict) and ats.get("NSAllowsArbitraryLoads"):
                facts["arbitrary_loads"].append(os.path.relpath(path, root))
            ext = data.get("NSExtension") or {}
            if isinstance(ext, dict):
                point = ext.get("NSExtensionPointIdentifier", "")
                if point == "com.apple.share-services":
                    facts["share_extensions"].append(os.path.relpath(path, root))
    return facts


def scan_ipa(ipa_path):
    """SDK inventory from a built .ipa — bundled frameworks and their names.

    Deliberately limited: an IPA gives you the dependency list, not the source,
    so this mode can inventory SDKs but cannot classify identifier-level
    evidence. The report says so.
    """
    inventory = {"frameworks": [], "matched": {}}
    try:
        with zipfile.ZipFile(ipa_path) as zf:
            names = zf.namelist()
    except (OSError, zipfile.BadZipFile) as exc:
        return None, f"cannot read {ipa_path}: {exc}"
    seen = set()
    for name in names:
        m = re.search(r"/([^/]+)\.(framework|bundle)/", name)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            inventory["frameworks"].append(m.group(1))
    inventory["frameworks"].sort()
    blob = "\n".join(inventory["frameworks"])
    for sig in SIGNALS:
        if "deps" not in sig["corpora"]:
            continue
        hits = [f for f in inventory["frameworks"] if sig["rx"].search(f)]
        if hits:
            inventory["matched"][sig["id"]] = hits
    return inventory, None


# ── classification ───────────────────────────────────────────────────────
def collect_evidence(fired, manifests, plists):
    """Fold regex hits and structured facts into per-capability evidence lists.

    Each record: {signal, confidence, why, note, hits, count, legs}.
    """
    by_id = {s["id"]: s for s in SIGNALS}
    # Signals that mitigate another signal, if they fired.
    mitigators = {}
    for sig in SIGNALS:
        if sig["mitigates"] and sig["id"] in fired:
            mitigators.setdefault(sig["mitigates"], []).append(sig["id"])

    evidence = {k: [] for k in list(CAPABILITIES) + ["carve_out"]}
    for sid, bucket in fired.items():
        sig = by_id[sid]
        if not sig["caps"]:
            continue  # pure mitigating signal
        confidence = sig["confidence"]
        mitigated_by = mitigators.get(sid, [])
        if mitigated_by and RANK[confidence] > 0:
            confidence = "low" if confidence == "medium" else "medium"
        for cap in sig["caps"]:
            evidence[cap].append({
                "signal": sid,
                "confidence": confidence,
                "declared_confidence": sig["confidence"],
                "mitigated_by": mitigated_by,
                "why": sig["why"],
                "note": sig["note"],
                "count": bucket["count"],
                "hits": bucket["hits"],
                "legs": sorted(leg_of(sig)),
                "reach": sig["reach"],
            })

    # Privacy manifest: a declaration, not an inference — treat as high.
    for item in manifests["user_content"]:
        evidence["ugc"].append({
            "signal": "manifest-user-content",
            "confidence": "high",
            "declared_confidence": "high",
            "mitigated_by": [],
            "why": f"Your own privacy manifest declares collection of "
                   f"{item['label']} — you already told Apple this app takes "
                   f"user content",
            "note": None if item["social_relevant"] else
                    "Customer Support content is a support inbox, not a social "
                    "surface — it does not push you toward Social Media.",
            "count": 1,
            "hits": [{"file": item["file"], "line": 0,
                      "text": item["type"]}],
            "legs": ["ugc"] if item["social_relevant"] else [],
            "reach": False,
        })
    for item in manifests["advertising_purposes"]:
        evidence["advertising"].append({
            "signal": "manifest-ad-purpose",
            "confidence": "high",
            "declared_confidence": "high",
            "mitigated_by": [],
            "why": f"Your privacy manifest declares data collected for "
                   f"{item['label']}",
            "note": None,
            "count": 1,
            "hits": [{"file": item["file"], "line": 0, "text": item["purpose"]}],
            "legs": [],
            "reach": False,
        })
    for path in plists["arbitrary_loads"]:
        evidence["web_access"].append({
            "signal": "plist-arbitrary-loads",
            "confidence": "medium",
            "declared_confidence": "medium",
            "mitigated_by": [],
            "why": "NSAllowsArbitraryLoads is set — ATS is relaxed for any host, "
                   "which is what an unconstrained browser needs",
            "note": "Also commonly set for one legacy API endpoint. Verify.",
            "count": 1,
            "hits": [{"file": path, "line": 0, "text": "NSAllowsArbitraryLoads"}],
            "legs": [],
            "reach": False,
        })
    for path in plists["share_extensions"]:
        evidence["social_media"].append({
            "signal": "plist-share-extension",
            "confidence": "low",
            "declared_confidence": "low",
            "mitigated_by": [],
            "why": "A Share Extension target receives content from other apps",
            "note": "Receiving shared content is not by itself a discovery "
                    "surface.",
            "count": 1,
            "hits": [{"file": path, "line": 0,
                      "text": "NSExtensionPointIdentifier = com.apple.share-services"}],
            "legs": ["discovery"],
            "reach": False,
        })
    return evidence


def peak(records):
    """Strongest confidence present in a list of evidence records."""
    best = -1
    for r in records:
        best = max(best, RANK[r["confidence"]])
    return best


def classify_social(records):
    """Apple's definition has two legs. Both must be present.

    This is the tool's central rule and its main brake on false positives: a
    backend, a photo picker or a share button supplies at most one leg and can
    never on its own produce a yes.
    """
    ugc_leg = [r for r in records if "ugc" in r["legs"]]
    disc_leg = [r for r in records if "discovery" in r["legs"]]
    u, d = peak(ugc_leg), peak(disc_leg)

    if u < 0 and d < 0:
        return "no", "No user-generated content and no discovery surface found."
    if u < 0:
        return "likely-no", (
            "Found a discovery/amplification surface but no evidence that the "
            "content on it is created by users. Curated or first-party content "
            "on a browse screen is not Social Media.")
    if d < 0:
        return "likely-no", (
            "Found user-generated content but no feed, browse, search or "
            "amplification surface. Plain UGC is a 4+ question, not this one.")
    broad = [r for r in disc_leg if r.get("reach")]
    if u >= 2 and d >= 2 and broad:
        return "yes", (
            "Both legs of Apple's definition are present with high-confidence "
            "evidence: users create content, and there is a surface that "
            "redistributes or amplifies it to a broad audience (%s)."
            % ", ".join(sorted({r["signal"] for r in broad})))
    if u >= 2 and d >= 2:
        return "likely-yes", (
            "Both legs of Apple's definition are present with high-confidence "
            "evidence: users create content, and there is a surface that "
            "redistributes or amplifies it. What is missing is reach — nothing "
            "in the code shows whether that content goes beyond a private or "
            "invited group. Apple's reference page ends its definition "
            "\"...that visibly spreads content to many users\"; the 9 July 2026 "
            "news post drops the clause. Under the news post this is already a "
            "yes. One question (SM4) settles it under the reference page.")
    if u >= 1 and d >= 1:
        return "likely-yes", (
            "Both legs are present, but at least one rests on medium-confidence "
            "evidence. Confirm the call sites below.")
    return "unclear", (
        "Both legs have some evidence, all of it weak. The interview will "
        "settle this faster than reading the code.")


def classify(cap, records):
    """Predicted answer for a non-Social-Media capability."""
    p = peak(records)
    if cap == "web_access":
        # A WKWebView is common and usually pinned to your own domain. Only an
        # explicit address-bar signal is strong enough to stand alone — and only
        # if there is an in-app web view to browse in. Apple's wording is
        # "navigate to any webpage *within the app*": handing a URL to Safari via
        # UIApplication.open is explicitly not this question.
        if p < 0:
            return "no", "No web view or in-app browsing found."
        container = [r for r in records
                     if r["signal"] in ("web-wkwebview", "web-uiwebview",
                                        "web-safari-vc")]
        strong = [r for r in records if r["confidence"] == "high"]
        if strong and container:
            return "likely-yes", (
                "Found in-app browser chrome on top of a web view. This is 16+ "
                "— a higher minimum than Social Media.")
        if strong and not container:
            return "unclear", (
                "Found browser-shaped identifiers but no in-app web view. If "
                "these URLs open in Safari rather than inside your app, this is "
                "not Unrestricted Web Access — Apple's wording is \"within the "
                "app\".")
        if not container:
            return "likely-no", (
                "Only relaxed transport settings or URL-building code found, "
                "with no in-app web view to browse in.")
        return "unclear", (
            "A web view is present. Whether it is Unrestricted Web Access "
            "depends on whether it can reach a URL you did not choose, which "
            "no static scan can tell. One interview question settles it.")
    if p < 0:
        return "no", "No supporting evidence found."
    if p == 2:
        return "yes", "High-confidence evidence found."
    if p == 1:
        return "likely-yes", "Medium-confidence evidence — verify the call sites."
    return "unclear", (
        "Only weak hints found. Not enough to answer either way; verify "
        "manually or answer the interview question.")


# ── interview ────────────────────────────────────────────────────────────
def gate(condition, answers, evidence):
    """Should this interview question be asked, given the scan?"""
    social = answers["social_media"]["answer"]
    if condition == "always":
        return True
    if condition == "social_unclear":
        return social in ("unclear", "likely-yes", "likely-no")
    if condition == "web_present":
        return bool(evidence["web_access"])
    if condition == "leaderboard_present":
        return any(r["signal"] in ("gk-leaderboard", "gk-alias")
                   for r in evidence["social_media"] + evidence["ugc"])
    if condition == "carve_out_claimed":
        return social in ("yes", "likely-yes")
    if condition == "ugc_present":
        return answers["ugc"]["answer"] in ("yes", "likely-yes", "unclear")
    return False


def pending_questions(answers, evidence, given):
    """Interview questions still unanswered, in report order."""
    out = []
    for q in INTERVIEW:
        if q["id"] in given:
            continue
        if gate(q["ask_when"], answers, evidence):
            out.append(q)
    return out


def apply_answers(answers, given, evidence):
    """Fold interview answers into the predictions.

    Returns a list of adjustment records so the report can show its work — a
    prediction that silently changed would be worse than no prediction.
    """
    adjustments = []
    legs_supplied = set()
    for q in INTERVIEW:
        if q["id"] not in given:
            continue
        val = given[q["id"]]
        if isinstance(val, str):
            val = val.strip().lower() in ("y", "yes", "true", "1")
        effect = q["yes_effect"] if val else q["no_effect"]
        cap = q["cap"]
        if effect == "none" or cap == "carve_out":
            adjustments.append({"id": q["id"], "answer": bool(val),
                                "effect": "recorded", "cap": cap})
            continue
        if effect == "rules_out":
            answers[cap]["answer"] = "no"
            answers[cap]["why"] = (
                f"Ruled out by your answer to {q['id']}: {q['q']}")
            adjustments.append({"id": q["id"], "answer": bool(val),
                                "effect": "ruled out " + cap, "cap": cap})
        elif effect == "confirms":
            answers[cap]["answer"] = "yes"
            answers[cap]["why"] = (
                f"Confirmed by your answer to {q['id']}: {q['q']}")
            adjustments.append({"id": q["id"], "answer": bool(val),
                                "effect": "confirmed " + cap, "cap": cap})
        elif effect in ("leg_ugc", "leg_discovery"):
            legs_supplied.add("ugc" if effect == "leg_ugc" else "discovery")
            adjustments.append({"id": q["id"], "answer": bool(val),
                                "effect": "supplies " + effect[4:] + " leg",
                                "cap": cap})
        elif effect == "weakens":
            adjustments.append({"id": q["id"], "answer": bool(val),
                                "effect": "weakens " + cap, "cap": cap})
        elif effect == "conflict":
            answers["_definition_conflict"] = True
            adjustments.append({
                "id": q["id"], "answer": bool(val), "cap": cap,
                "effect": "definitional conflict — in scope under Apple's news "
                          "post, out of scope under Apple's reference page"})

    # Legs supplied by the interview can complete Apple's two-leg test.
    if legs_supplied and answers["social_media"]["answer"] not in ("yes", "no"):
        have = set()
        for r in evidence["social_media"] + evidence["ugc"]:
            have.update(r["legs"])
        have |= legs_supplied
        if {"ugc", "discovery"} <= have:
            # Legs are mechanism, not reach. SM4 is what promotes this to a
            # hard yes — see classify_social.
            answers["social_media"]["answer"] = "likely-yes"
            answers["social_media"]["why"] = (
                "Both legs of Apple's definition are satisfied once your "
                "interview answers are folded in: users create content, and "
                "there is a surface that redistributes or amplifies it. Answer "
                "SM4 (does that content reach beyond a private group?) to "
                "settle it either way.")
            adjustments.append({"id": "-", "answer": True, "cap": "social_media",
                                "effect": "both legs now satisfied → likely-yes"})
    return adjustments


def run_interview(questions):
    """Prompt on a TTY. Returns {question_id: bool}."""
    given = {}
    print("\nShipGate interview — %d question(s) static analysis cannot answer.\n"
          % len(questions))
    for q in questions:
        print("  [%s] %s" % (q["id"], q["q"]))
        print("       why it matters: %s" % q["why"])
        while True:
            try:
                raw = input("       y / n / s(kip) > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return given
            if raw in ("y", "yes"):
                given[q["id"]] = True
                break
            if raw in ("n", "no"):
                given[q["id"]] = False
                break
            if raw in ("s", "skip", ""):
                break
        print()
    return given


# ── carve-out checklist ──────────────────────────────────────────────────
def carve_out_status(fired, social_answer):
    """Is the under-13 carve-out actually wired, or merely intended?

    Apple's requirement is that the Declared Age Range API "is called". An import
    with no call site is the failure mode this check exists to catch.
    """
    imported = "dar-import" in fired or "dar-service" in fired
    called = "dar-request" in fired
    handled = "dar-response" in fired
    entitled = "dar-entitlement" in fired
    relevant = social_answer in ("yes", "likely-yes", "unclear")

    checks = [
        {"item": "DeclaredAgeRange framework imported", "ok": imported,
         "detail": "import DeclaredAgeRange / AgeRangeService"},
        {"item": "requestAgeRange() actually called", "ok": called,
         "detail": "An import with no call site does not satisfy Apple's "
                   "\"the Declared Age Range API is called\"."},
        {"item": "Age-range response handled", "ok": handled,
         "detail": "The response is an enum — sharing(declaration) or "
                   "declinedSharing. Both paths need handling."},
        {"item": "Declared Age Range capability entitlement present", "ok": entitled,
         "detail": "Apple requires the capability to be enabled in Signing & "
                   "Capabilities. Confirm in Xcode — this check is a text match "
                   "on your .entitlements."},
    ]
    wired = imported and called
    if not relevant:
        verdict = "not applicable"
        summary = ("No social media capability predicted, so the under-13 "
                   "carve-out is not in play.")
    elif wired:
        verdict = "wired"
        summary = ("Declared Age Range is imported and called. You are in a "
                   "position to claim the carve-out — but see the rating "
                   "conflict below before you rely on it lowering your rating.")
    elif imported:
        verdict = "incomplete"
        summary = ("DeclaredAgeRange is imported but requestAgeRange() is never "
                   "called. Apple's wording is that the API \"is called\". As "
                   "shipped, this does not qualify.")
    else:
        verdict = "missing"
        summary = ("You appear to have a social media capability and no "
                   "Declared Age Range call anywhere. The under-13 carve-out is "
                   "not available to you as the code stands.")
    return {"verdict": verdict, "summary": summary, "checks": checks,
            "relevant": relevant}


# ── report assembly ──────────────────────────────────────────────────────
def build_report(root, fired, counts, manifests, plists, given):
    evidence = collect_evidence(fired, manifests, plists)

    answers = {}
    for cap in CAPABILITY_ORDER:
        if cap == "social_media":
            ans, why = classify_social(evidence[cap])
        else:
            ans, why = classify(cap, evidence[cap])
        answers[cap] = {"answer": ans, "why": why}
    answers["_definition_conflict"] = False

    adjustments = apply_answers(answers, given, evidence) if given else []
    pending = pending_questions(answers, evidence, given or {})

    # Rating: capabilities you would answer yes to today.
    committed = [c for c in CAPABILITY_ORDER
                 if answers[c]["answer"] in ("yes", "likely-yes")]
    at_risk = [c for c in CAPABILITY_ORDER if answers[c]["answer"] == "unclear"]
    rating = max_rating([CAPABILITIES[c]["min_rating"] for c in committed])
    worst = max_rating([CAPABILITIES[c]["min_rating"] for c in committed + at_risk])

    social = answers["social_media"]["answer"]
    carve = carve_out_status(fired, social)

    return {
        "root": os.path.abspath(root),
        "files_scanned": counts,
        "privacy_manifests": manifests["manifests"],
        "capabilities": {
            c: {
                "label": CAPABILITIES[c]["label"],
                "question": CAPABILITIES[c]["question"],
                "min_rating": CAPABILITIES[c]["min_rating"],
                "answer": answers[c]["answer"],
                "why": answers[c]["why"],
                "evidence": evidence[c],
            } for c in CAPABILITY_ORDER
        },
        "minimum_rating": rating,
        "worst_case_rating": worst,
        "time_allowance_social": social in ("yes", "likely-yes"),
        "definition_conflict": answers["_definition_conflict"],
        "carve_out": carve,
        "interview_pending": [{"id": q["id"], "cap": q["cap"], "q": q["q"],
                               "why": q["why"]} for q in pending],
        "interview_applied": adjustments,
        "requirement": REQUIREMENT,
    }


# ── rendering ────────────────────────────────────────────────────────────
def c(code, s, use_color):
    return f"\033[{code}m{s}\033[0m" if use_color else s


ANSWER_STYLE = {
    "yes": ("1;31", "YES"),
    "likely-yes": ("33", "LIKELY YES"),
    "unclear": ("1;33", "UNCLEAR"),
    "likely-no": ("36", "LIKELY NO"),
    "no": ("32", "NO"),
}


def render_text(rep, use_color):
    out = []
    out.append(c("1", f"shipgate — {rep['root']}", use_color))
    fc = rep["files_scanned"]
    out.append("Scanned %d source, %d dependency, %d plist, %d entitlement file(s)."
               % (fc["source"], fc["deps"], fc["plist"], fc["entitlements"]))
    if rep["privacy_manifests"]:
        out.append("Privacy manifest: " + ", ".join(rep["privacy_manifests"]))
    out.append("")

    out.append(c("1", "Predicted questionnaire answers", use_color))
    for key in CAPABILITY_ORDER:
        cap = rep["capabilities"][key]
        style, label = ANSWER_STYLE[cap["answer"]]
        out.append("  %-28s %s  %s" % (
            cap["label"],
            c(style, "%-10s" % label, use_color),
            c("2", "min %s" % cap["min_rating"], use_color)))
    out.append("")

    out.append(c("1", "Resulting age rating", use_color))
    out.append("  As predicted today:  " + c("1;36", rep["minimum_rating"], use_color))
    if rep["worst_case_rating"] != rep["minimum_rating"]:
        out.append("  If the unclear answers turn out yes:  "
                   + c("1;33", rep["worst_case_rating"], use_color))
    if rep["time_allowance_social"]:
        out.append(c("33", "  → Placed in the iOS 27 Social Media Time Allowance "
                           "category.", use_color))
        out.append(c("33", "  → Social Media descriptor on your product page.",
                     use_color))
        out.append(c("33", "  → Incompatible with Made for Kids (needs a "
                           "calculated 4+/9+).", use_color))
    out.append("")

    # Per-capability detail with evidence.
    for key in CAPABILITY_ORDER:
        cap = rep["capabilities"][key]
        if cap["answer"] == "no" and not cap["evidence"]:
            continue
        style, label = ANSWER_STYLE[cap["answer"]]
        out.append(c("1", f"{cap['label']} — ", use_color)
                   + c(style, label, use_color)
                   + c("2", f"  (minimum {cap['min_rating']})", use_color))
        out.append("  " + cap["why"])
        ranked = sorted(cap["evidence"], key=lambda r: -RANK[r["confidence"]])
        for r in ranked[:6]:
            legs = ("[%s]" % "+".join(r["legs"])) if r["legs"] else ""
            out.append("    %s %s %s" % (
                c("36", r["signal"], use_color),
                c("2", "(%s)" % r["confidence"], use_color),
                c("2", legs, use_color)))
            out.append("      " + r["why"])
            for h in r["hits"][:2]:
                loc = f"{h['file']}:{h['line']}" if h["line"] else h["file"]
                out.append("      %s  %s" % (loc, c("2", h["text"], use_color)))
            if r["count"] > len(r["hits"]):
                out.append(c("2", "      … %d more occurrence(s)"
                             % (r["count"] - len(r["hits"])), use_color))
            if r["mitigated_by"]:
                out.append(c("2", "      ↓ downgraded from %s by %s"
                             % (r["declared_confidence"],
                                ", ".join(r["mitigated_by"])), use_color))
            if r["note"]:
                out.append(c("2", "      note: " + r["note"], use_color))
        if len(ranked) > 6:
            out.append(c("2", "    … %d more signal(s)" % (len(ranked) - 6), use_color))
        out.append("")

    if rep["definition_conflict"]:
        out.append(c("1;35", "⚑ Apple's two definitions disagree about your app",
                     use_color))
        out.append("  " + CAPABILITIES["social_media"]["definition_conflict"])
        out.append("  You answered that content does not spread beyond a private "
                   "or friends-only group.")
        out.append("  Under the reference page you are OUT of scope; under the "
                   "9 July news post you are IN.")
        out.append("  Document this before you submit — it is the single most "
                   "defensible thing you can attach to a rating appeal.")
        out.append("")

    carve = rep["carve_out"]
    if carve["relevant"]:
        head = {"wired": ("32", "✓"), "incomplete": ("1;33", "⚠"),
                "missing": ("1;31", "✗"), "not applicable": ("2", "·")}
        style, mark = head[carve["verdict"]]
        out.append(c("1", "Under-13 carve-out — ", use_color)
                   + c(style, carve["verdict"].upper(), use_color))
        out.append("  " + carve["summary"])
        for chk in carve["checks"]:
            mk = c("32", "✓", use_color) if chk["ok"] else c("31", "✗", use_color)
            out.append("    %s %s" % (mk, chk["item"]))
            if not chk["ok"]:
                out.append(c("2", "        " + chk["detail"], use_color))
        out.append("")
        out.append(c("1;35", "  ⚑ Apple contradicts itself on what this buys you:",
                     use_color))
        out.append("  " + UNDER_13_CARVE_OUT["conflict"])
        out.append("")

    if rep["interview_applied"]:
        out.append(c("1", "Interview answers applied", use_color))
        for a in rep["interview_applied"]:
            out.append("  [%s] %s → %s" % (a["id"], "yes" if a["answer"] else "no",
                                           a["effect"]))
        out.append("")

    if rep["interview_pending"]:
        out.append(c("1;33", "%d question(s) static analysis cannot answer:"
                     % len(rep["interview_pending"]), use_color))
        for q in rep["interview_pending"]:
            out.append("  [%s] %s" % (c("1", q["id"], use_color), q["q"]))
            out.append(c("2", "       " + q["why"], use_color))
        out.append("")
        out.append(c("2", "  Answer them:  shipgate.py PATH --interview", use_color))
        out.append(c("2", "  Or in CI:     shipgate.py PATH --answers-template > "
                          "answers.json", use_color))
        out.append("")

    out.append(c("2", "Deadline: %s. %s" % (REQUIREMENT["effective"],
                                            REQUIREMENT["wording"]), use_color))
    out.append(c("2", "Guidance tool, not legal advice. Re-check Apple's wording "
                      "before a submission you are betting on.", use_color))
    return "\n".join(out)


def render_markdown(rep, expect):
    """Compact summary for a CI job summary or a PR comment.

    Deliberately short: a wall of evidence in a job summary is skipped. The
    headline answer, the rating delta, and the questions a human still has to
    answer — everything else is in the JSON/HTML artifact.
    """
    exceeded = (RATING_ORDER.index(rep["minimum_rating"])
                > RATING_ORDER.index(expect))
    mark = {"yes": "🔴", "likely-yes": "🟠", "unclear": "🟡",
            "likely-no": "🔵", "no": "🟢"}
    out = ["### ShipGate — Apple capability questions", ""]
    if exceeded:
        out.append("> [!WARNING]")
        out.append("> Predicted rating **%s** exceeds the expected **%s**."
                   % (rep["minimum_rating"], expect))
    else:
        out.append("Predicted minimum age rating: **%s** (expected %s or lower)."
                   % (rep["minimum_rating"], expect))
    if rep["worst_case_rating"] != rep["minimum_rating"]:
        out.append("")
        out.append("Rises to **%s** if the unclear answers turn out to be yes."
                   % rep["worst_case_rating"])
    out.append("")
    out.append("| Question | Predicted | Minimum |")
    out.append("| --- | --- | --- |")
    for key in CAPABILITY_ORDER:
        cap = rep["capabilities"][key]
        out.append("| %s | %s %s | %s |" % (
            cap["label"], mark[cap["answer"]],
            cap["answer"].replace("-", " "), cap["min_rating"]))
    if rep["time_allowance_social"]:
        out.append("")
        out.append("Placed in the iOS 27 **Social Media Time Allowance** category; "
                   "Social Media descriptor on the product page; incompatible with "
                   "Made for Kids.")
    if rep["definition_conflict"]:
        out.append("")
        out.append("> [!IMPORTANT]")
        out.append("> Apple's two definitions disagree about this app — in scope "
                   "under the 9 July 2026 news post, out of scope under the "
                   "reference page.")
    carve = rep["carve_out"]
    if carve["relevant"] and carve["verdict"] in ("missing", "incomplete"):
        out.append("")
        out.append("> [!WARNING]")
        out.append("> Under-13 carve-out **%s** — %s"
                   % (carve["verdict"], carve["summary"]))
    if rep["interview_pending"]:
        out.append("")
        out.append("<details><summary>%d question(s) static analysis cannot "
                   "answer</summary>\n" % len(rep["interview_pending"]))
        for q in rep["interview_pending"]:
            out.append("- **%s** %s" % (q["id"], q["q"]))
        out.append("\nAnswer them once and commit the file: "
                   "`shipgate.py PATH --answers-template > answers.json`")
        out.append("</details>")
    return "\n".join(out)


def render_explain(use_color):
    """The rulebook, as a CLI command — five questions and what each one costs."""
    out = [c("1", "Apple's age-rating capability questions, and what each costs",
             use_color), ""]
    out.append(REQUIREMENT["wording"])
    out.append("")
    for key in CAPABILITY_ORDER:
        cap = CAPABILITIES[key]
        out.append(c("1", "%s — minimum %s" % (cap["label"], cap["min_rating"]),
                     use_color))
        out.append("  Q: " + cap["question"])
        out.append("  Apple's definition: \"%s\"" % cap["definition"])
        out.append(c("2", "  May include: %s" % cap["examples"], use_color))
        if cap.get("definition_alt"):
            out.append(c("35", "  Apple's OTHER definition (9 Jul 2026 news post): "
                               "\"%s\"" % cap["definition_alt"], use_color))
            out.append(c("35", "  " + cap["definition_conflict"], use_color))
        for cost in cap["costs"]:
            out.append("  · " + cost)
        out.append(c("2", "  " + cap["source"], use_color))
        out.append("")
    out.append(c("1", "%s — reference page says minimum %s"
                 % (UNDER_13_CARVE_OUT["label"],
                    UNDER_13_CARVE_OUT["reference_min_rating"]), use_color))
    out.append("  \"%s\"" % UNDER_13_CARVE_OUT["definition"])
    out.append(c("35", "  " + UNDER_13_CARVE_OUT["conflict"], use_color))
    out.append("")
    out.append(c("1", "Still unknown", use_color))
    for u in REQUIREMENT["unknowns"]:
        out.append("  · " + u)
    return "\n".join(out)


# ── CLI ──────────────────────────────────────────────────────────────────
def load_answers(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: v for k, v in data.get("answers", data).items()
            if v is not None and v != ""}


def answers_template():
    return json.dumps({
        "_comment": "Set each value to true or false. Delete any you cannot "
                    "answer — ShipGate reports them as open rather than "
                    "guessing.",
        "answers": {q["id"]: None for q in INTERVIEW},
        "_questions": {q["id"]: q["q"] for q in INTERVIEW},
    }, indent=2)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="Xcode project directory to scan")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    ap.add_argument("--html", metavar="FILE", help="Write a single-file HTML report")
    ap.add_argument("--ipa", metavar="FILE",
                    help="Inventory SDKs from a built .ipa (dependency list only "
                         "— no source, so no identifier-level classification)")
    ap.add_argument("--interview", action="store_true",
                    help="Prompt for the questions static analysis cannot answer")
    ap.add_argument("--answers", metavar="FILE",
                    help="JSON file of interview answers (for CI)")
    ap.add_argument("--answers-template", action="store_true",
                    help="Print a blank answers file and exit")
    ap.add_argument("--explain", action="store_true",
                    help="Print the rulebook: the five questions and what each costs")
    ap.add_argument("--expect", metavar="RATING", default="4+",
                    help="Exit non-zero only if the predicted rating EXCEEDS this. "
                         "Default 4+. In CI, set it to your app's current App Store "
                         "rating so the build fails when a change would raise it — "
                         "an app that is legitimately 13+ should not have permanently "
                         "red CI. One of: " + ", ".join(RATING_ORDER))
    ap.add_argument("--markdown", action="store_true",
                    help="Emit a compact Markdown summary (for a CI job summary "
                         "or a PR comment)")
    ap.add_argument("--no-color", action="store_true", help="Disable ANSI color")
    args = ap.parse_args()

    use_color = not args.no_color and sys.stdout.isatty()

    if args.expect not in RATING_ORDER:
        print("error: --expect must be one of %s (got %r)"
              % (", ".join(RATING_ORDER), args.expect), file=sys.stderr)
        return 2

    if args.explain:
        if args.html:
            import report
            with open(args.html, "w", encoding="utf-8") as fh:
                fh.write(report.render_explain_html())
            print("Wrote %s" % args.html, file=sys.stderr)
        else:
            print(render_explain(use_color))
        return 0
    if args.answers_template:
        print(answers_template())
        return 0

    if args.ipa:
        inventory, err = scan_ipa(args.ipa)
        if err:
            print("error: " + err, file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(inventory, indent=2))
        else:
            print(c("1", "shipgate SDK inventory — %s" % args.ipa, use_color))
            print("%d bundled framework/bundle(s)." % len(inventory["frameworks"]))
            if inventory["matched"]:
                print("\nCapability-relevant SDKs:")
                for sid, hits in sorted(inventory["matched"].items()):
                    print("  %s → %s" % (c("36", sid, use_color), ", ".join(hits)))
            else:
                print("\nNo capability-relevant SDKs matched.")
            print(c("2", "\nAn IPA gives the dependency list, not the source. Run "
                         "against the project directory for identifier-level "
                         "evidence and a predicted answer.", use_color))
        return 0

    if not args.path:
        ap.error("PATH is required (or use --explain / --ipa / --answers-template)")
    if not os.path.isdir(args.path):
        print("error: %s is not a directory" % args.path, file=sys.stderr)
        return 2

    fired, counts = scan(args.path)
    manifests = scan_privacy_manifests(args.path)
    plists = scan_info_plists(args.path)

    given = {}
    if args.answers:
        try:
            given = load_answers(args.answers)
        except (OSError, ValueError) as exc:
            print("error: cannot read answers file: %s" % exc, file=sys.stderr)
            return 2

    rep = build_report(args.path, fired, counts, manifests, plists, given)

    if args.interview and rep["interview_pending"]:
        qmap = {q["id"]: q for q in INTERVIEW}
        asked = run_interview([qmap[q["id"]] for q in rep["interview_pending"]])
        given.update(asked)
        rep = build_report(args.path, fired, counts, manifests, plists, given)

    if args.html:
        import report
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(report.render_html(rep))
        print("Wrote %s" % args.html, file=sys.stderr)

    if args.json:
        print(json.dumps(rep, indent=2))
    elif args.markdown:
        print(render_markdown(rep, args.expect))
    elif not args.html:
        print(render_text(rep, use_color))

    # Non-zero only when the rating EXCEEDS what you said to expect. Defaulting
    # --expect to 4+ preserves "fail on anything above the floor", while an app
    # that is deliberately 13+ can set --expect 13+ and still get a signal the
    # day a change would push it to 16+.
    return 1 if (RATING_ORDER.index(rep["minimum_rating"])
                 > RATING_ORDER.index(args.expect)) else 0


if __name__ == "__main__":
    sys.exit(main())
