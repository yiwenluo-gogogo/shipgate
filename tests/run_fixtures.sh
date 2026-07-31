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

echo "exit codes:"
python3 "$CLI" "$HERE/fixtures/clean-app" >/dev/null 2>&1
[ $? -eq 0 ] && echo "  ok   clean-app exits 0 by default" || { echo "  FAIL clean-app should exit 0"; fail=1; }

python3 "$CLI" "$HERE/fixtures/social-app" >/dev/null 2>&1
[ $? -eq 1 ] && echo "  ok   social-app exits 1 by default (--expect 4+)" || { echo "  FAIL social-app should exit 1"; fail=1; }

python3 "$CLI" "$HERE/fixtures/social-app" --expect 13+ >/dev/null 2>&1
[ $? -eq 0 ] && echo "  ok   social-app exits 0 with --expect 13+" || { echo "  FAIL --expect 13+ should pass"; fail=1; }

python3 "$CLI" "$HERE/fixtures/social-app" --expect bogus >/dev/null 2>&1
[ $? -eq 2 ] && echo "  ok   invalid --expect exits 2" || { echo "  FAIL invalid --expect should exit 2"; fail=1; }

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
