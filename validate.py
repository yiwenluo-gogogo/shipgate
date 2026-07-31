#!/usr/bin/env python3
"""Measure the classifier against a hand-labelled corpus.

This is the instrument for the question that decides whether ShipGate is a
product at all: **is there an ambiguous middle band?** If every app is trivially
yes or trivially no, developers need a one-page explainer, not a tool.

Scoring is deliberately unkind to the tool:

  label "yes"        correct only if predicted yes or likely-yes
  label "no"         correct only if predicted no or likely-no
  label "ambiguous"  correct only if the tool DECLINES to commit — unclear, or a
                     prediction paired with open interview questions. Committing
                     hard to either side on a genuinely undecidable app is scored
                     as a miss, because that is the failure mode that gets a
                     developer rejected.

Usage:
    validate.py [labels.json] [--verbose]
"""

import json
import os
import sys

import shipgate

COMMITS_YES = ("yes", "likely-yes")
COMMITS_NO = ("no", "likely-no")


def evaluate(path):
    fired, counts = shipgate.scan(path)
    manifests = shipgate.scan_privacy_manifests(path)
    plists = shipgate.scan_info_plists(path)
    return shipgate.build_report(path, fired, counts, manifests, plists, {})


def score(label, predicted, pending):
    if label == "yes":
        return predicted in COMMITS_YES
    if label == "no":
        return predicted in COMMITS_NO
    # ambiguous: the honest answer is "I can't tell you — here are the
    # questions". A hard yes/no is a miss even when questions are attached,
    # because the headline answer is what a hurried developer copies into the
    # questionnaire.
    return predicted not in ("yes", "no") and bool(pending)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    here = os.path.dirname(os.path.abspath(__file__))
    labels_path = args[0] if args else os.path.join(here, "labels.json")
    if not os.path.exists(labels_path):
        example = os.path.join(here, "labels.example.json")
        print("No corpus at %s.\n" % labels_path, file=sys.stderr)
        print("Accuracy is only meaningful against apps you can label yourself, so "
              "this repo ships no corpus. Copy %s to labels.json, point the paths "
              "at real projects, and label each one BEFORE running this."
              % os.path.basename(example), file=sys.stderr)
        return 2
    with open(labels_path, "r", encoding="utf-8") as fh:
        corpus = json.load(fh)

    rows, missing = [], []
    for entry in corpus["apps"]:
        path = os.path.normpath(os.path.join(here, entry["path"]))
        if not os.path.isdir(path):
            missing.append(entry["path"])
            continue
        rep = evaluate(path)
        cap = rep["capabilities"]["social_media"]
        pending = [q for q in rep["interview_pending"] if q["cap"] == "social_media"]
        ok = score(entry["social_media"], cap["answer"], pending)
        # Every non-"no" prediction must carry at least one evidence line — the
        # spec's own acceptance criterion.
        evidenced = cap["answer"] == "no" or bool(cap["evidence"])
        rows.append({
            "name": os.path.basename(path),
            "label": entry["social_media"],
            "predicted": cap["answer"],
            "ok": ok,
            "evidenced": evidenced,
            "rating": rep["minimum_rating"],
            "open_qs": len(rep["interview_pending"]),
            "carve_out": rep["carve_out"]["verdict"],
            "top": sorted(cap["evidence"],
                          key=lambda r: -shipgate.RANK[r["confidence"]])[:3],
            "note": entry.get("note", ""),
        })

    print("%-22s %-10s %-11s %-6s %-5s %s" %
          ("APP", "LABEL", "PREDICTED", "RATING", "OPEN", ""))
    print("-" * 72)
    for r in rows:
        mark = "ok " if r["ok"] else "MISS"
        print("%-22s %-10s %-11s %-6s %-5d %s" %
              (r["name"][:22], r["label"], r["predicted"], r["rating"],
               r["open_qs"], mark))
        if verbose and r["top"]:
            for ev in r["top"]:
                print("      %-24s %-7s %s" %
                      (ev["signal"], ev["confidence"], ev["hits"][0]["file"]
                       if ev["hits"] else ""))

    total = len(rows)
    correct = sum(1 for r in rows if r["ok"])
    unevidenced = [r for r in rows if not r["evidenced"]]
    by_label = {}
    for r in rows:
        b = by_label.setdefault(r["label"], [0, 0])
        b[1] += 1
        if r["ok"]:
            b[0] += 1

    print("-" * 72)
    print("Social Media accuracy: %d/%d" % (correct, total))
    for label in ("yes", "ambiguous", "no"):
        if label in by_label:
            got, n = by_label[label]
            print("  label %-10s %d/%d" % (label, got, n))
    print("Every prediction carries evidence: %s"
          % ("yes" if not unevidenced else
             "NO — " + ", ".join(r["name"] for r in unevidenced)))
    carve_missing = [r for r in rows if r["carve_out"] == "missing"]
    print("Carve-out flagged unavailable (no DeclaredAgeRange call): %d app(s)%s"
          % (len(carve_missing),
             (" — " + ", ".join(r["name"] for r in carve_missing))
             if carve_missing else ""))
    if missing:
        print("Not on disk, skipped: %s" % ", ".join(missing))

    # The kill criterion, stated plainly.
    unambiguous = sum(1 for r in rows if r["label"] in ("yes", "no"))
    print()
    print("Middle band: %d/%d apps labelled ambiguous."
          % (total - unambiguous, total))
    if total and (total - unambiguous) / total < 0.12:
        print("  ⚑ This corpus is almost entirely unambiguous. Per the spec's own")
        print("    kill criterion that argues against the product — but note this")
        print("    corpus is one solo developer's content apps, not a sample of")
        print("    the App Store. Re-run against apps you did not write before")
        print("    treating this as a demand signal.")
    return 0 if correct == total else 1


if __name__ == "__main__":
    sys.exit(main())
