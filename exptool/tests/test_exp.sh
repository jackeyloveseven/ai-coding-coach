#!/usr/bin/env bash
# Smoke tests for exp. Local mode only: no cluster, no tmux, no ssh needed.
#
# Run it with:
#   bash tests/test_exp.sh
#
# The interpreter is auto-detected (python3 / python / py), or set REMOTE_PYTHON.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TOOL="$(dirname "$HERE")"
FAILED=0

pass() { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; FAILED=$((FAILED + 1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Find an interpreter that actually runs. On Windows, python3 is often the
# Microsoft Store stub, which exits without doing anything (no error, no output)
# and would make every assertion involving the progress reader fail spuriously.
if [ -n "${REMOTE_PYTHON:-}" ]; then
  PY="$REMOTE_PYTHON"
else
  PY=""
  for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'pass' >/dev/null 2>&1; then
      PY="$cand"; break
    fi
  done
  if [ -z "$PY" ]; then
    echo "no usable python interpreter found (tried python3 / python / py); set REMOTE_PYTHON." >&2
    exit 1
  fi
fi

# PLAN files may hold non-ASCII text (the reader accepts Chinese field names too),
# so make the interpreter emit UTF-8 rather than the platform default.
export PYTHONIOENCODING=utf-8

# Use the example registry; its machine column is local, so nothing goes over ssh
cat > "$TMP/config" <<EOF
RUNS_CONF="$TOOL/runs.conf.example"
REMOTE_PYTHON="$PY"
EOF

# The missing-registry case
cat > "$TMP/bad.conf" <<EOF
RUNS_CONF="$TMP/does-not-exist.conf"
REMOTE_PYTHON="$PY"
EOF

run() { EXPT_CONF="$TMP/config" bash "$TOOL/exp" "$@" 2>&1; }

echo "exp help"
out="$(run help)"; code=$?
[ $code -eq 0 ] && pass "exit code 0" || fail "exit code $code"
case "$out" in *"exp status"*) pass "lists status" ;; *) fail "does not list status" ;; esac

echo "exp list"
out="$(run list)"; code=$?
[ $code -eq 0 ] && pass "exit code 0" || fail "exit code $code"
case "$out" in *demo-sft*) pass "sees demo-sft" ;; *) fail "cannot see demo-sft" ;; esac

echo "exp status demo-sft"
out="$(run status demo-sft)"; code=$?
[ $code -eq 0 ] && pass "exit code 0" || fail "exit code $code"
case "$out" in *metrics.jsonl*) pass "found the metric source" ;; *) fail "did not find the metric source" ;; esac
case "$out" in *loss*) pass "shows loss" ;; *) fail "no loss" ;; esac
case "$out" in *"step "*) fail "step metadata leaked in" ;; *) pass "no step metadata leaked in" ;; esac
case "$out" in *"8 segments"*) pass "8 segments by default" ;; *) fail "not 8 segments" ;; esac

echo "exp status (no argument: defaults to the first row)"
out="$(run status)"; code=$?
[ $code -eq 0 ] && pass "exit code 0" || fail "exit code $code"

echo "exp config demo-sft"
out="$(run config demo-sft)"; code=$?
[ $code -eq 0 ] && pass "exit code 0" || fail "exit code $code"
case "$out" in *echo*) pass "printed launch.sh" ;; *) fail "did not print launch.sh" ;; esac

echo "exp errors demo-sft"
out="$(run errors demo-sft)"; code=$?
[ $code -eq 0 ] && pass "exit code 0" || fail "exit code $code"

echo "pre-registration (exp plan / status)"
out="$(run status demo-sft)"
case "$out" in *"criterion: judge by eval loss"*) pass "status prints the criterion next to the metrics" ;; *) fail "status did not carry the criterion" ;; esac

out="$(run plan demo-sft)"; code=$?
[ $code -eq 0 ] && pass "exp plan exit code 0" || fail "exp plan exit code $code"
case "$out" in *"Budget and stop-loss"*) pass "printed the full PLAN.md" ;; *) fail "did not print the full text" ;; esac

# Two runs sharing one temporary registry: no PLAN written, and an ASCII colon
mkdir -p "$TMP/noplan" "$TMP/halfwidth"
printf 'Criterion: an ASCII colon has to parse too\n' > "$TMP/halfwidth/PLAN.md"
cat > "$TMP/plan-runs.conf" <<EOF
# name   machine  dir                 method  tmux  note
fresh    local    $TMP/noplan         sft     -     no pre-registration written
half     local    $TMP/halfwidth      sft     -     ASCII colon
EOF
cat > "$TMP/plan.conf" <<EOF
RUNS_CONF="$TMP/plan-runs.conf"
REMOTE_PYTHON="$PY"
EOF
planrun() { EXPT_CONF="$TMP/plan.conf" bash "$TOOL/exp" "$@" 2>&1; }

out="$(planrun status fresh)"
case "$out" in *"no PLAN.md"*) pass "status warns when it is missing" ;; *) fail "status did not warn when it is missing" ;; esac

out="$(planrun plan fresh)"; code=$?
[ $code -eq 0 ] && pass "exp plan generates the template" || fail "template generation failed (exit code $code)"
[ -f "$TMP/noplan/PLAN.md" ] && pass "PLAN.md actually landed on disk" || fail "PLAN.md did not land on disk"
case "$(cat "$TMP/noplan/PLAN.md" 2>/dev/null)" in *"Criterion:"*) pass "the template has a Criterion item" ;; *) fail "the template is missing Criterion" ;; esac

out="$(planrun status half)"
case "$out" in *"criterion: an ASCII colon has to parse too"*) pass "an ASCII colon parses too" ;; *) fail "an ASCII colon did not parse" ;; esac

echo "exp report demo-sft"
RPT="$TMP/report.html"
out="$(run report demo-sft --out "$RPT")"; code=$?
[ $code -eq 0 ] && pass "exit code 0" || fail "exit code $code"
[ -f "$RPT" ] && pass "report file was written" || fail "report file was not written"
body="$(cat "$RPT" 2>/dev/null)"
case "$body" in *"<!doctype html>"*) pass "is HTML (has a doctype)" ;; *) fail "is not HTML" ;; esac
case "$body" in *"<svg"*) pass "contains inline SVG charts" ;; *) fail "no inline SVG" ;; esac
case "$body" in *"loss"*) pass "contains the loss metric" ;; *) fail "missing loss" ;; esac
case "$body" in *"grad_norm"*) pass "contains the grad_norm metric" ;; *) fail "missing grad_norm" ;; esac
case "$body" in *"rewards/accuracies"*) pass "contains the rewards/accuracies metric" ;; *) fail "missing rewards/accuracies" ;; esac
case "$body" in *"judge by eval loss on the fixed dev set"*) pass "contains the criterion text from PLAN.md" ;; *) fail "missing the criterion text" ;; esac
case "$body" in *"criterion ≤"*) pass "the criterion was drawn as a reference line" ;; *) fail "the criterion was not drawn as a reference line" ;; esac
case "$body" in *"Health checks"*) pass "contains the health checks" ;; *) fail "missing the health checks" ;; esac
if printf '%s' "$body" | grep -qE 'https?://'; then fail "the report has an external URL"; else pass "no external URL anywhere"; fi
if printf '%s' "$body" | grep -qE '<link|src=|@import'; then fail "the report references an external resource"; else pass "no external resource references"; fi

# Defaults to the current directory, not the run directory
( cd "$TMP" && run report demo-sft >/dev/null 2>&1 )
[ -f "$TMP/exp-report-demo-sft.html" ] && pass "defaults to ./exp-report-<name>.html" || fail "wrong default output path"

echo "exp report error paths"
out="$(run report no-such-run)"; code=$?
[ $code -ne 0 ] && pass "an unknown run errors out" || fail "an unknown run succeeded"

echo "error paths"
out="$(run nonsense)"; code=$?
[ $code -ne 0 ] && pass "an unknown command errors out" || fail "an unknown command succeeded"

out="$(run status no-such-run)"; code=$?
[ $code -ne 0 ] && pass "an unknown run errors out" || fail "an unknown run succeeded"

out="$(EXPT_CONF="$TMP/bad.conf" bash "$TOOL/exp" list 2>&1)"; code=$?
[ $code -ne 0 ] && pass "errors out when the registry is missing" || fail "succeeded with a missing registry"
case "$out" in *runs.conf*) pass "the error names runs.conf" ;; *) fail "the error does not mention runs.conf" ;; esac

echo
if [ "$FAILED" -gt 0 ]; then
  echo "$FAILED checks failed."
  exit 1
fi
echo "all passed."
