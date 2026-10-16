#!/usr/bin/env bash
set -uo pipefail

# Verifies install.sh: it copies the payload and only the payload, an existing
# install is kept unless --force is given, and --check tells a matching copy
# from a drifted one. Every write goes to a temporary directory; the default
# destinations are exercised with HOME pointed there.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"
PAYLOAD="$REPO_ROOT/sentl-monitor"
PASS=0
FAIL=0

ok()  { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
DEST="$TMP/dest/sentl-monitor"

run() { bash "$INSTALL" "$@" </dev/null >"$TMP/out.txt" 2>&1; }

if [ ! -f "$INSTALL" ]; then
    bad "install.sh missing"
fi
if [ ! -f "$PAYLOAD/SKILL.md" ]; then
    bad "sentl-monitor/SKILL.md missing; the install checks below need the payload"
fi

echo "=== Fresh install with --dest ==="
if run --dest "$DEST"; then ok "install.sh --dest exits 0"; else bad "install.sh --dest exits 0"; cat "$TMP/out.txt"; fi
[ -f "$DEST/SKILL.md" ] && ok "SKILL.md lands in the destination" || bad "SKILL.md lands in the destination"
if diff -r --exclude=__pycache__ --exclude='*.pyc' "$PAYLOAD" "$DEST" >/dev/null 2>&1; then
    ok "the destination holds the payload"
else
    bad "the destination holds the payload"
fi
if grep -q 'app.sentl.ai/mcp/setup' "$TMP/out.txt"; then
    ok "install points to the Sentl MCP setup page"
else
    bad "install points to the Sentl MCP setup page"
fi

echo ""
echo "=== Dev-tree files do not ship ==="
for f in DEVPLAN.md ARCHITECTURE.md README.md CLAUDE.md install.sh tests sentl-monitor; do
    if [ -e "$DEST/$f" ]; then bad "$f leaked into the install"; else ok "$f stays in the dev tree"; fi
done

echo ""
echo "=== An existing install is kept without --force ==="
echo "local edit" >>"$DEST/SKILL.md"
if run --dest "$DEST"; then
    bad "re-install without --force and without a terminal is refused (exit 0)"
else
    ok "re-install without --force and without a terminal is refused"
fi
if grep -q -- '--force' "$TMP/out.txt"; then ok "the refusal names --force"; else bad "the refusal names --force"; fi
if grep -q 'local edit' "$DEST/SKILL.md"; then ok "the existing install is not overwritten"; else bad "the existing install is not overwritten"; fi

echo ""
echo "=== --force overwrites ==="
if run --force --dest "$DEST"; then ok "install.sh --force --dest exits 0"; else bad "install.sh --force --dest exits 0"; cat "$TMP/out.txt"; fi
if cmp -s "$PAYLOAD/SKILL.md" "$DEST/SKILL.md"; then ok "--force replaces the edited file"; else bad "--force replaces the edited file"; fi

echo ""
echo "=== --check ==="
if run --check --dest "$DEST" && grep -q '^OK' "$TMP/out.txt"; then
    ok "--check prints OK and exits 0 on a fresh copy"
else
    bad "--check prints OK and exits 0 on a fresh copy"; cat "$TMP/out.txt"
fi

mkdir -p "$DEST/scripts/__pycache__"
echo "cache" >"$DEST/scripts/__pycache__/probe.cpython.pyc"
if run --check --dest "$DEST" && grep -q '^OK' "$TMP/out.txt"; then
    ok "--check ignores byte-compiled caches"
else
    bad "--check ignores byte-compiled caches"; cat "$TMP/out.txt"
fi

echo "local edit" >>"$DEST/SKILL.md"
if run --check --dest "$DEST"; then STATUS=0; else STATUS=$?; fi
if [ "$STATUS" -eq 1 ] && grep -q '^DRIFT' "$TMP/out.txt"; then
    ok "--check prints DRIFT and exits 1 after an edit"
else
    bad "--check prints DRIFT and exits 1 after an edit (exit $STATUS)"; cat "$TMP/out.txt"
fi

if run --check --dest "$TMP/nowhere"; then STATUS=0; else STATUS=$?; fi
if [ "$STATUS" -eq 1 ] && grep -q '^DRIFT' "$TMP/out.txt"; then
    ok "--check prints DRIFT and exits 1 when nothing is installed"
else
    bad "--check prints DRIFT and exits 1 when nothing is installed (exit $STATUS)"
fi

echo ""
echo "=== Default destinations ==="
FAKE_HOME="$TMP/home"
mkdir -p "$FAKE_HOME"
if HOME="$FAKE_HOME" run --force; then ok "install without --dest exits 0"; else bad "install without --dest exits 0"; cat "$TMP/out.txt"; fi
[ -f "$FAKE_HOME/.claude/skills/sentl-monitor/SKILL.md" ] \
    && ok "installs for Claude Code" || bad "installs for Claude Code"
[ -e "$FAKE_HOME/.config/opencode/skills/sentl-monitor" ] \
    && bad "installs for opencode although it is not set up" || ok "skips opencode when it is not set up"

mkdir -p "$FAKE_HOME/.config/opencode"
if HOME="$FAKE_HOME" run --force; then ok "install with opencode set up exits 0"; else bad "install with opencode set up exits 0"; fi
[ -f "$FAKE_HOME/.config/opencode/skills/sentl-monitor/SKILL.md" ] \
    && ok "installs for opencode when it is set up" || bad "installs for opencode when it is set up"
if HOME="$FAKE_HOME" run --check && grep -q '^OK' "$TMP/out.txt"; then
    ok "--check without --dest checks both destinations"
else
    bad "--check without --dest checks both destinations"; cat "$TMP/out.txt"
fi

echo ""
echo "=== --force never empties a folder that is not a sentl-monitor install ==="
OTHER="$TMP/other"
mkdir -p "$OTHER"
echo "keep me" >"$OTHER/notes.txt"
if bash "$INSTALL" --force --dest "$OTHER" </dev/null >"$TMP/out.txt" 2>&1; then
    bad "--force on a foreign folder is refused (exit 0)"
else
    ok "--force on a foreign folder is refused"
fi
if [ -f "$OTHER/notes.txt" ]; then ok "the foreign folder keeps its files"; else bad "the foreign folder keeps its files"; fi

echo ""
echo "=== Options ==="
HELP_TEXT="$(bash "$INSTALL" --help 2>&1)"
for opt in --force --check --dest; do
    if grep -q -- "$opt" <<<"$HELP_TEXT"; then ok "--help documents $opt"; else bad "--help documents $opt"; fi
done
if bash "$INSTALL" --bogus </dev/null >/dev/null 2>&1; then
    bad "an unknown option is refused"
else
    ok "an unknown option is refused"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
