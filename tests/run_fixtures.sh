#!/usr/bin/env bash
# Regression test that needs no private corpus — anyone who clones the repo can
# run it. Two fixtures pin the behaviour that actually matters:
#
#   social-app  both legs + a reach signal      -> hard yes, 13+
#   clean-app   curated content, no UGC         -> not above 4+
#
# clean-app deliberately contains the two tokens that caused real false
# positives during development (`isMuted`, the word "unlikely"). If either ever
# drags a curated content app above 4+ again, this fails.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CLI="$HERE/../shipgate.py"
fail=0

# NB: the project argument is deliberately NOT called `path`. In zsh `$path` is
# tied to `$PATH`, so a local named `path` silently replaces the command search
# path with a project directory and every external command vanishes.
check() {  # name  proj  expected_rating  expected_social
  local name="$1" proj="$2" want_rating="$3" want_social="$4"
  local json rating social
  json=$(python3 "$CLI" "$proj" --json 2>/dev/null)
  rating=$(printf '%s' "$json" | python3 -c 'import json,sys;print(json.load(sys.stdin)["minimum_rating"])')
  social=$(printf '%s' "$json" | python3 -c 'import json,sys;print(json.load(sys.stdin)["capabilities"]["social_media"]["answer"])')
  if [ "$rating" = "$want_rating" ] && [ "$social" = "$want_social" ]; then
    echo "  ok   $name — $rating, social=$social"
  else
    echo "  FAIL $name — got $rating/social=$social, want $want_rating/social=$want_social"
    fail=1
  fi
}

echo "fixtures:"
check "social-app" "$HERE/fixtures/social-app" "13+" "yes"
check "clean-app"  "$HERE/fixtures/clean-app"  "4+"  "no"
# In-App Controls must never move the rating — they carry no minimum of their own.
check "controls-app" "$HERE/fixtures/controls-app" "4+" "no"

echo "in-app controls:"
ctl() {  # name proj key expected
  local name="$1" proj="$2" key="$3" want="$4" got
  got=$(python3 "$CLI" "$proj" --json 2>/dev/null \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['in_app_controls']['$key']['answer'])")
  if [ "$got" = "$want" ]; then
    echo "  ok   $name $key=$got"
  else
    echo "  FAIL $name $key=$got, want $want"; fail=1
  fi
}
ctl "controls-app" "$HERE/fixtures/controls-app" "parental_controls" "yes"
ctl "controls-app" "$HERE/fixtures/controls-app" "age_assurance"     "yes"
ctl "clean-app"    "$HERE/fixtures/clean-app"    "parental_controls" "no"
ctl "clean-app"    "$HERE/fixtures/clean-app"    "age_assurance"     "no"

# A social app with no age assurance must raise the contradiction — this is the
# case that renders with ZERO evidence, so it is exactly the one a naive
# "only show what we detected" report silently drops.
conflict=$(python3 "$CLI" "$HERE/fixtures/social-app" --json 2>/dev/null \
  | python3 -c "import json,sys;print(bool(json.load(sys.stdin)['in_app_controls']['age_assurance'].get('conflict')))")
[ "$conflict" = "True" ] \
  && echo "  ok   social-app flags missing age assurance" \
  || { echo "  FAIL social-app should flag missing age assurance"; fail=1; }

echo "exit codes:"
python3 "$CLI" "$HERE/fixtures/clean-app" >/dev/null 2>&1
[ $? -eq 0 ] && echo "  ok   clean-app exits 0 by default" || { echo "  FAIL clean-app should exit 0"; fail=1; }

python3 "$CLI" "$HERE/fixtures/social-app" >/dev/null 2>&1
[ $? -eq 1 ] && echo "  ok   social-app exits 1 by default (--expect 4+)" || { echo "  FAIL social-app should exit 1"; fail=1; }

python3 "$CLI" "$HERE/fixtures/social-app" --expect 13+ >/dev/null 2>&1
[ $? -eq 0 ] && echo "  ok   social-app exits 0 with --expect 13+" || { echo "  FAIL --expect 13+ should pass"; fail=1; }

python3 "$CLI" "$HERE/fixtures/social-app" --expect bogus >/dev/null 2>&1
[ $? -eq 2 ] && echo "  ok   invalid --expect exits 2" || { echo "  FAIL invalid --expect should exit 2"; fail=1; }

echo "round-1 features:"
# Made for Kids requires a calculated 4+/9+ and is permanent once approved, so a
# kids app at 13+ must be a hard failure that --expect cannot talk its way out of.
python3 "$CLI" "$HERE/fixtures/social-app" --made-for-kids >/dev/null 2>&1
[ $? -eq 1 ] && echo "  ok   made-for-kids blocks a 13+ app" || { echo "  FAIL kids should block"; fail=1; }
python3 "$CLI" "$HERE/fixtures/clean-app" --made-for-kids >/dev/null 2>&1
[ $? -eq 0 ] && echo "  ok   made-for-kids passes a 4+ app" || { echo "  FAIL kids should pass"; fail=1; }
python3 "$CLI" "$HERE/fixtures/social-app" --expect 13+ --made-for-kids >/dev/null 2>&1
[ $? -eq 1 ] && echo "  ok   made-for-kids overrides --expect" || { echo "  FAIL kids must override expect"; fail=1; }

# Xcode parses `path:line: level: message`; paths must be absolute to resolve.
xc=$(python3 "$CLI" "$HERE/fixtures/social-app" --xcode 2>/dev/null | head -1)
case "$xc" in
  /*:[0-9]*:\ error:*|/*:[0-9]*:\ warning:*|/*:[0-9]*:\ note:*)
    echo "  ok   --xcode emits absolute-path diagnostics" ;;
  *) echo "  FAIL --xcode format: $xc"; fail=1 ;;
esac

# Suppression: a signal silenced inline must leave the findings AND be reviewable.
tmpdir=$(mktemp -d)
mkdir -p "$tmpdir/App"
cat > "$tmpdir/App/S.swift" <<'SWIFT'
struct A { var likeCount = 0 }  // shipgate:ignore amp-like -- counter, not a social like
SWIFT
n=$(python3 "$CLI" "$tmpdir" --json 2>/dev/null | python3 -c "import json,sys;print(len(json.load(sys.stdin)['suppressed']))")
[ "$n" = "1" ] && echo "  ok   inline suppression records the hit" || { echo "  FAIL suppression n=$n"; fail=1; }
gone=$(python3 "$CLI" "$tmpdir" --json 2>/dev/null | python3 -c "import json,sys;print(any(e['signal']=='amp-like' for e in json.load(sys.stdin)['capabilities']['social_media']['evidence']))")
[ "$gone" = "False" ] && echo "  ok   suppressed signal leaves the evidence" || { echo "  FAIL suppressed signal still present"; fail=1; }
rm -rf "$tmpdir"

echo "round-2 features:"
# Remediation must name the specific signals, not give generic advice.
rem=$(python3 "$CLI" "$HERE/fixtures/social-app" --remediate 2>/dev/null)
case "$rem" in
  *"Social Media needs BOTH legs"*"feed-view"*) echo "  ok   --remediate names the legs and the signals" ;;
  *) echo "  FAIL --remediate output"; fail=1 ;;
esac
rem4=$(python3 "$CLI" "$HERE/fixtures/clean-app" --remediate 2>/dev/null)
case "$rem4" in
  *"Nothing to change"*) echo "  ok   --remediate is quiet on a 4+ app" ;;
  *) echo "  FAIL --remediate should be quiet"; fail=1 ;;
esac

# Portfolio must find apps whose sources live BELOW the top level, which is
# every real Xcode project.
pf=$(python3 "$CLI" --portfolio "$HERE/fixtures" --json 2>/dev/null \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d['apps']))")
[ "$pf" = "3" ] && echo "  ok   --portfolio finds all 3 fixtures" || { echo "  FAIL portfolio found $pf"; fail=1; }
python3 "$CLI" --portfolio "$HERE/fixtures" >/dev/null 2>&1
[ $? -eq 1 ] && echo "  ok   --portfolio exits 1 when an app exceeds" || { echo "  FAIL portfolio exit"; fail=1; }

# Baseline drift must fail even when --expect is satisfied — that is the point.
bl=$(mktemp "${TMPDIR:-/tmp}/shipgate-bl.XXXXXX")
python3 "$CLI" "$HERE/fixtures/clean-app" --save-baseline "$bl" >/dev/null 2>&1
python3 "$CLI" "$HERE/fixtures/clean-app" --baseline "$bl" >/dev/null 2>&1
[ $? -eq 0 ] && echo "  ok   baseline vs itself passes" || { echo "  FAIL baseline self-compare"; fail=1; }
python3 "$CLI" "$HERE/fixtures/social-app" --baseline "$bl" --expect 13+ >/dev/null 2>&1
[ $? -eq 1 ] && echo "  ok   drift fails even when --expect is satisfied" || { echo "  FAIL drift should fail"; fail=1; }
rm -f "$bl"

echo "other modes:"
python3 "$CLI" --explain >/dev/null 2>&1 && echo "  ok   --explain" || { echo "  FAIL --explain"; fail=1; }
# NB: capture rather than pipe. Under `pipefail`, shipgate's intentional exit 1
# on a 13+ app would fail the pipeline even when the grep matches.
md=$(python3 "$CLI" "$HERE/fixtures/social-app" --markdown --expect 13+ 2>/dev/null)
case "$md" in
  *"ShipGate"*"Social Media"*) echo "  ok   --markdown" ;;
  *) echo "  FAIL --markdown"; fail=1 ;;
esac
python3 "$CLI" --answers-template >/dev/null 2>&1 && echo "  ok   --answers-template" || { echo "  FAIL --answers-template"; fail=1; }

# The public page must stay reproducible from capability_db.py, or it silently
# drifts from the rules the CLI applies.
#
# NB: `mktemp -t PREFIX` is a BSD/macOS spelling; GNU coreutils reads -t as
# "template" and rejects it for having too few X's. The explicit XXXXXX template
# works on both. It failed exactly this way on a Linux runner, and — worse — the
# missing temp file made the diff fail, which this reported as "page is stale".
# A broken harness must not masquerade as a content failure, hence the guard.
tmp="$(mktemp "${TMPDIR:-/tmp}/shipgate-page.XXXXXX" 2>/dev/null)" || tmp=""
if [ -z "$tmp" ]; then
  echo "  FAIL could not create a temp file (harness problem, not a stale page)"
  fail=1
else
  if ! python3 "$CLI" --explain --html "$tmp" >/dev/null 2>&1; then
    echo "  FAIL --explain --html could not write the page"
    fail=1
  elif diff -q "$tmp" "$HERE/../web/index.html" >/dev/null 2>&1; then
    echo "  ok   web/index.html reproducible from capability_db.py"
  else
    echo "  FAIL web/index.html is stale — run: shipgate.py --explain --html web/index.html"
    fail=1
  fi
  rm -f "$tmp"
fi

[ $fail -eq 0 ] && echo "all passed" || echo "FAILURES"
exit $fail
