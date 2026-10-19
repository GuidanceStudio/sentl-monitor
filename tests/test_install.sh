#!/usr/bin/env bash
set -uo pipefail

# Verifies install.sh: it copies the payload and only the payload, to the hosts named with
# --host or detected in HOME and on PATH; an existing install is kept unless --force is given;
# --check lists every install with its version; --uninstall removes sentl-monitor installs and
# nothing else; an older copy in ~/.config/opencode/skills is removed after a prompt. Every
# run gets a temporary HOME and a PATH holding only the tools the script needs, so the real
# ~/.claude, ~/.agents and ~/.config are never read or written, and a codex or opencode
# installed on this machine does not count as a detected host.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="$REPO_ROOT/install.sh"
PAYLOAD="$REPO_ROOT/skills/sentl-monitor"
PASS=0
FAIL=0

ok()  { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; sed 's/^/        /' "$TMP/out.txt"; fi; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [ ! -f "$INSTALL" ]; then
    bad "install.sh missing"
fi
if [ ! -f "$PAYLOAD/SKILL.md" ]; then
    bad "skills/sentl-monitor/SKILL.md missing; the install checks below need the payload"
fi
VERSION="$(sed -n '/^metadata:/,/^[^ ]/s/^  version: "\(.*\)"$/\1/p' "$PAYLOAD/SKILL.md")"

SAFE_BIN="$TMP/bin"
mkdir -p "$SAFE_BIN" "$TMP/fakebin"
for tool in bash sh python3 mkdir rm rmdir cp mv find diff ls grep awk sed dirname basename cat head tail tr sort \
            wc env chmod mktemp touch; do
    path="$(command -v "$tool" 2>/dev/null)" && ln -s "$path" "$SAFE_BIN/$tool"
done
EXTRA_PATH=""

new_home() {
    local home
    home="$(mktemp -d "$TMP/home-XXXXXX")"
    local d
    for d in "$@"; do mkdir -p "$home/$d"; done
    echo "$home"
}

# No terminal: stdin is /dev/null.
run() {
    local home="$1"; shift
    HOME="$home" PATH="$SAFE_BIN${EXTRA_PATH:+:$EXTRA_PATH}" bash "$INSTALL" "$@" </dev/null >"$TMP/out.txt" 2>&1
}

# A terminal that answers each prompt with the next line of $2.
SCRIPT="$(command -v script 2>/dev/null)"
SCRIPT_VERSION="$([ -n "$SCRIPT" ] && "$SCRIPT" --version 2>/dev/null)"
if grep -q util-linux <<<"$SCRIPT_VERSION"; then HAVE_TTY=true; else HAVE_TTY=false; fi
run_tty() {
    local home="$1" answers="$2"; shift 2
    printf '%b' "$answers" | HOME="$home" PATH="$SAFE_BIN" SHELL="$SAFE_BIN/bash" \
        "$SCRIPT" -qec "bash '$INSTALL' $*" /dev/null >"$TMP/out.txt" 2>&1
}

# An installed copy whose SKILL.md declares `version`, or no version when it is empty.
plant() {
    local dest="$1" version="${2-}"
    mkdir -p "$(dirname "$dest")"
    cp -R "$PAYLOAD" "$dest"
    if [ -z "$version" ]; then
        sed -i.bak '/^  version: /d' "$dest/SKILL.md"
    else
        sed -i.bak "s/^  version: \".*\"$/  version: \"$version\"/" "$dest/SKILL.md"
    fi
    rm -f "$dest/SKILL.md.bak"
}

same_as_payload() { diff -r --exclude=__pycache__ --exclude='*.pyc' "$PAYLOAD" "$1" >/dev/null 2>&1; }

echo "=== Fresh install with --dest ==="
H="$(new_home)"
DEST="$TMP/dest/sentl-monitor"
check "install.sh --dest exits 0" 'run "$H" --dest "$DEST"'
check "SKILL.md lands in the destination" '[ -f "$DEST/SKILL.md" ]'
check "the destination holds the payload" 'same_as_payload "$DEST"'
check "install points to the Sentl MCP setup page" 'grep -q "app.sentl.ai/mcp/setup" "$TMP/out.txt"'
check "an install to --dest writes nothing in HOME" '[ -z "$(ls -A "$H")" ]'

echo ""
echo "=== Dev-tree files do not ship ==="
for f in DEVPLAN.md ARCHITECTURE.md README.md CLAUDE.md install.sh tests skills sentl-monitor tools dist .claude-plugin .github; do
    if [ -e "$DEST/$f" ]; then bad "$f leaked into the install"; else ok "$f stays in the dev tree"; fi
done

echo ""
echo "=== An existing install is kept without --force ==="
echo "local edit" >>"$DEST/SKILL.md"
check "re-install without --force and without a terminal is refused" '! run "$H" --dest "$DEST"'
check "the refusal names --force" 'grep -q -- "--force" "$TMP/out.txt"'
check "the existing install is not overwritten" 'grep -q "local edit" "$DEST/SKILL.md"'

echo ""
echo "=== --force overwrites ==="
check "install.sh --force --dest exits 0" 'run "$H" --force --dest "$DEST"'
check "--force replaces the edited file" 'cmp -s "$PAYLOAD/SKILL.md" "$DEST/SKILL.md"'

echo ""
echo "=== --check ==="
check "--check prints OK with the version and exits 0 on a fresh copy" \
    'run "$H" --check --dest "$DEST" && grep -q "^OK: $DEST .*$VERSION" "$TMP/out.txt"'
mkdir -p "$DEST/scripts/__pycache__"
echo "cache" >"$DEST/scripts/__pycache__/probe.cpython.pyc"
check "--check ignores byte-compiled caches" 'run "$H" --check --dest "$DEST" && grep -q "^OK" "$TMP/out.txt"'
echo "local edit" >>"$DEST/SKILL.md"
run "$H" --check --dest "$DEST"; STATUS=$?
check "--check prints DRIFT and exits 1 after an edit" '[ "$STATUS" -eq 1 ] && grep -q "^DRIFT" "$TMP/out.txt"'
run "$H" --check --dest "$TMP/nowhere"; STATUS=$?
check "--check prints DRIFT and exits 1 when nothing is installed" '[ "$STATUS" -eq 1 ] && grep -q "^DRIFT" "$TMP/out.txt"'

echo ""
echo "=== --host ==="
H="$(new_home)"
check "--host claude exits 0" 'run "$H" --host claude'
check "--host claude installs to ~/.claude/skills" 'same_as_payload "$H/.claude/skills/sentl-monitor"'
check "--host claude installs nowhere else" '[ ! -e "$H/.agents" ] && [ ! -e "$H/.config" ]'
H="$(new_home)"
check "--host agents exits 0" 'run "$H" --host agents'
check "--host agents installs to ~/.agents/skills" 'same_as_payload "$H/.agents/skills/sentl-monitor"'
check "--host agents installs nowhere else" '[ ! -e "$H/.claude" ] && [ ! -e "$H/.config" ]'
for alias in codex opencode; do
    H="$(new_home)"
    check "--host $alias installs to ~/.agents/skills" 'run "$H" --host "$alias" && [ -f "$H/.agents/skills/sentl-monitor/SKILL.md" ]'
done
H="$(new_home)"
check "--host claude --host agents installs to both" \
    'run "$H" --host claude --host agents && [ -f "$H/.claude/skills/sentl-monitor/SKILL.md" ] && [ -f "$H/.agents/skills/sentl-monitor/SKILL.md" ]'
H="$(new_home)"
check "an unknown host is refused" '! run "$H" --host gemini && grep -q "gemini" "$TMP/out.txt"'
check "--host with --dest is refused" '! run "$H" --host claude --dest "$TMP/both"'
check "a refused host writes nothing" '[ -z "$(ls -A "$H")" ] && [ ! -e "$TMP/both" ]'

echo ""
echo "=== Hosts detected in HOME and on PATH ==="
H="$(new_home .claude)"
check "with ~/.claude only, the install exits 0" 'run "$H"'
check "with ~/.claude only, it installs for Claude Code" '[ -f "$H/.claude/skills/sentl-monitor/SKILL.md" ]'
check "with ~/.claude only, it does not install to ~/.agents" '[ ! -e "$H/.agents" ]'
H="$(new_home .codex)"
check "with ~/.codex, it installs to ~/.agents/skills only" \
    'run "$H" && [ -f "$H/.agents/skills/sentl-monitor/SKILL.md" ] && [ ! -e "$H/.claude" ]'
H="$(new_home .config/opencode)"
check "with ~/.config/opencode, it installs to ~/.agents/skills" 'run "$H" && [ -f "$H/.agents/skills/sentl-monitor/SKILL.md" ]'
check "with ~/.config/opencode, it no longer writes ~/.config/opencode/skills" '[ ! -e "$H/.config/opencode/skills" ]'
for tool in codex opencode; do
    rm -f "$TMP/fakebin/"*
    printf '#!/bin/sh\nexit 0\n' >"$TMP/fakebin/$tool"
    chmod +x "$TMP/fakebin/$tool"
    H="$(new_home)"
    EXTRA_PATH="$TMP/fakebin"
    check "with $tool on PATH, it installs to ~/.agents/skills" 'run "$H" && [ -f "$H/.agents/skills/sentl-monitor/SKILL.md" ]'
    EXTRA_PATH=""
done
H="$(new_home .claude .codex)"
check "with both hosts, it installs to both" \
    'run "$H" && [ -f "$H/.claude/skills/sentl-monitor/SKILL.md" ] && [ -f "$H/.agents/skills/sentl-monitor/SKILL.md" ]'
BOTH="$H"

echo ""
echo "=== No host detected ==="
H="$(new_home)"
run "$H"; STATUS=$?
check "the install is refused when no host is detected" '[ "$STATUS" -ne 0 ]'
for opt in "--host claude" "--host agents" "--dest"; do
    check "the refusal names $opt" 'grep -q -- "$opt" "$TMP/out.txt"'
done
check "a refusal writes nothing" '[ -z "$(ls -A "$H")" ]'

echo ""
echo "=== --check lists every install and its version ==="
check "--check with both hosts exits 0" 'run "$BOTH" --check'
for d in .claude/skills/sentl-monitor .agents/skills/sentl-monitor; do
    check "--check prints OK and the version for ~/$d" 'grep -q "^OK: $BOTH/$d .*$VERSION" "$TMP/out.txt"'
done
H="$(new_home .claude)"
run "$H" --force
plant "$H/.agents/skills/sentl-monitor" "0.0.9"
check "--check exits 0 when the detected hosts match" 'run "$H" --check'
check "--check lists an install outside the detected hosts, with its version" \
    'grep -q "$H/.agents/skills/sentl-monitor.*0\.0\.9" "$TMP/out.txt"'
plant "$TMP/unversioned/sentl-monitor" ""
run "$H" --check --dest "$TMP/unversioned/sentl-monitor"
check "--check says when an install declares no version" 'grep -q "unversioned/sentl-monitor.*version unknown" "$TMP/out.txt"'
H="$(new_home)"
run "$H" --check; STATUS=$?
check "--check with no host and no install exits 1 and says so" \
    '[ "$STATUS" -eq 1 ] && grep -qi "no sentl-monitor install" "$TMP/out.txt"'

echo ""
echo "=== An older copy in ~/.config/opencode/skills ==="
LEGACY=.config/opencode/skills/sentl-monitor
H="$(new_home .claude)"
plant "$H/$LEGACY" ""
run "$H"; STATUS=$?
check "without a terminal and without --force, the install is refused" '[ "$STATUS" -ne 0 ] && grep -q -- "--force" "$TMP/out.txt"'
check "the refusal names the older copy" 'grep -q "$H/$LEGACY" "$TMP/out.txt"'
check "the refusal keeps the older copy and installs nothing" '[ -d "$H/$LEGACY" ] && [ ! -e "$H/.claude/skills" ]'
run "$H" --check; STATUS=$?
check "--check reports the older copy as DRIFT and exits 1" \
    '[ "$STATUS" -eq 1 ] && grep -q "^DRIFT: .*$H/$LEGACY" "$TMP/out.txt"'
check "--force installs and removes the older copy" \
    'run "$H" --force && [ ! -e "$H/$LEGACY" ] && [ -f "$H/.claude/skills/sentl-monitor/SKILL.md" ]'
check "the opencode folder itself stays" '[ -d "$H/.config/opencode" ]'
if [ "$HAVE_TTY" = true ]; then
    H="$(new_home .claude)"
    plant "$H/$LEGACY" "0.0.9"
    check "on a terminal, answering y removes the older copy" \
        'run_tty "$H" "y\n" && [ ! -e "$H/$LEGACY" ] && [ -f "$H/.claude/skills/sentl-monitor/SKILL.md" ]'
    check "the prompt names the older copy" 'grep -q "$H/$LEGACY" "$TMP/out.txt"'
    H="$(new_home .claude)"
    plant "$H/$LEGACY" "0.0.9"
    check "on a terminal, answering n keeps the older copy and installs" \
        'run_tty "$H" "n\n" && [ -d "$H/$LEGACY" ] && [ -f "$H/.claude/skills/sentl-monitor/SKILL.md" ]'
else
    echo "  (util-linux script not found: the prompt checks are skipped)"
fi
H="$(new_home .claude)"
mkdir -p "$H/$LEGACY"
printf -- '---\nname: another-skill\n---\n' >"$H/$LEGACY/SKILL.md"
check "a folder there that is not a sentl-monitor install is left alone" \
    'run "$H" --force && [ -f "$H/$LEGACY/SKILL.md" ]'
H="$(new_home .claude)"
plant "$H/$LEGACY" ""
check "an install to --dest leaves the older copy alone" 'run "$H" --force --dest "$TMP/elsewhere/sentl-monitor" && [ -d "$H/$LEGACY" ]'

echo ""
echo "=== --uninstall ==="
setup_installed() {
    local home
    home="$(new_home .claude .codex)"
    run "$home" --force
    plant "$home/$LEGACY" ""
    mkdir -p "$home/.claude/skills/other-skill"
    echo "keep" >"$home/.claude/skills/other-skill/SKILL.md"
    echo "$home"
}
H="$(setup_installed)"
run "$H" --uninstall; STATUS=$?
check "without a terminal and without --force, --uninstall is refused" '[ "$STATUS" -ne 0 ] && grep -q -- "--force" "$TMP/out.txt"'
check "the refusal removes nothing" \
    '[ -d "$H/.claude/skills/sentl-monitor" ] && [ -d "$H/.agents/skills/sentl-monitor" ] && [ -d "$H/$LEGACY" ]'
check "--uninstall --force exits 0" 'run "$H" --uninstall --force'
for d in .claude/skills/sentl-monitor .agents/skills/sentl-monitor "$LEGACY"; do
    check "--uninstall removes ~/$d" '[ ! -e "$H/$d" ]'
done
check "--uninstall leaves another skill alone" '[ -f "$H/.claude/skills/other-skill/SKILL.md" ]'
H="$(setup_installed)"
check "--uninstall --host agents removes only ~/.agents/skills/sentl-monitor" \
    'run "$H" --uninstall --host agents --force && [ ! -e "$H/.agents/skills/sentl-monitor" ] && [ -d "$H/.claude/skills/sentl-monitor" ]'
H="$(new_home)"
plant "$TMP/custom/sentl-monitor" "$VERSION"
check "--uninstall --dest removes that install" 'run "$H" --uninstall --dest "$TMP/custom/sentl-monitor" --force && [ ! -e "$TMP/custom/sentl-monitor" ]'
H="$(new_home)"
mkdir -p "$H/.agents/skills/sentl-monitor"
printf -- '---\nname: another-skill\n---\n' >"$H/.agents/skills/sentl-monitor/SKILL.md"
run "$H" --uninstall --force
check "--uninstall leaves a folder that is not a sentl-monitor install, and says so" \
    '[ -f "$H/.agents/skills/sentl-monitor/SKILL.md" ] && grep -q "not a sentl-monitor install" "$TMP/out.txt"'
H="$(new_home)"
check "--uninstall with nothing installed exits 0 and says so" 'run "$H" --uninstall && grep -qi "no sentl-monitor install" "$TMP/out.txt"'
if [ "$HAVE_TTY" = true ]; then
    H="$(setup_installed)"
    check "on a terminal, answering y to each prompt uninstalls" \
        'run_tty "$H" "y\ny\ny\n" --uninstall && [ ! -e "$H/.claude/skills/sentl-monitor" ] && [ ! -e "$H/.agents/skills/sentl-monitor" ] && [ ! -e "$H/$LEGACY" ]'
fi

echo ""
echo "=== --force never empties a folder that is not a sentl-monitor install ==="
H="$(new_home)"
OTHER="$TMP/other"
mkdir -p "$OTHER"
echo "keep me" >"$OTHER/notes.txt"
check "--force on a foreign folder is refused" '! run "$H" --force --dest "$OTHER"'
check "the foreign folder keeps its files" '[ -f "$OTHER/notes.txt" ]'

echo ""
echo "=== A target that is not a folder is refused ==="
H="$(new_home)"
echo "keep me" >"$TMP/a-file"
for force in "" --force; do
    check "--dest on a file is refused ${force:-without --force}" '! run "$H" $force --dest "$TMP/a-file"'
    check "the file keeps its content ${force:-without --force}" '[ -f "$TMP/a-file" ] && [ "$(cat "$TMP/a-file")" = "keep me" ]'
done
ln -s "$TMP/a-file" "$TMP/a-link"
check "--dest on a link to a file is refused" '! run "$H" --force --dest "$TMP/a-link"'
check "the link and its file stay" '[ -L "$TMP/a-link" ] && [ "$(cat "$TMP/a-file")" = "keep me" ]'
ln -s "$TMP/nothing-here" "$TMP/dangling"
check "--dest on a dangling link is refused" '! run "$H" --force --dest "$TMP/dangling"'
check "the dangling link stays and nothing is created behind it" '[ -L "$TMP/dangling" ] && [ ! -e "$TMP/nothing-here" ]'
check "the refusal says the target is not a folder" 'grep -q "not a folder" "$TMP/out.txt"'

echo ""
echo "=== The payload itself is never a target ==="
# These run a copy of the repository, so a failing check cannot delete this one's payload.
COPY="$TMP/repo-copy"
mkdir -p "$COPY/skills"
cp "$INSTALL" "$COPY/install.sh"
cp -R "$PAYLOAD" "$COPY/skills/sentl-monitor"
COPY_PAYLOAD="$COPY/skills/sentl-monitor"
run_copy() {
    local home="$1"; shift
    HOME="$home" PATH="$SAFE_BIN" bash "$COPY/install.sh" "$@" </dev/null >"$TMP/out.txt" 2>&1
}
payload_intact() { same_as_payload "$COPY_PAYLOAD"; }
H="$(new_home)"
check "--uninstall --force --dest <payload> is refused" '! run_copy "$H" --uninstall --force --dest "$COPY_PAYLOAD"'
check "the payload survives --uninstall on itself" 'payload_intact'
check "the refusal names the payload" 'grep -q "payload" "$TMP/out.txt"'
check "--force --dest <payload> is refused" '! run_copy "$H" --force --dest "$COPY_PAYLOAD"'
check "the payload survives an install onto itself" 'payload_intact'
check "--force --dest on the folder holding the payload is refused" '! run_copy "$H" --force --dest "$COPY/skills"'
check "the payload survives an install onto its parent" 'payload_intact'
check "--force --dest inside the payload is refused" '! run_copy "$H" --force --dest "$COPY_PAYLOAD/scripts/copy"'
check "nothing is written inside the payload" 'payload_intact && [ ! -e "$COPY_PAYLOAD/scripts/copy" ]'
check "a relative --dest that names the payload is refused" \
    '! (cd "$COPY" && HOME="$H" PATH="$SAFE_BIN" bash ./install.sh --force --dest skills/./sentl-monitor </dev/null >"$TMP/out.txt" 2>&1)'
check "the payload survives a relative --dest" 'payload_intact'
H="$(new_home)"
mkdir -p "$H/.claude"
ln -s "$COPY/skills" "$H/.claude/skills"
check "with ~/.claude/skills linked into the repository, --host claude --force is refused" \
    '! run_copy "$H" --host claude --force'
check "the payload survives an install through the link" 'payload_intact'
check "with ~/.claude/skills linked into the repository, --uninstall --force is refused" '! run_copy "$H" --uninstall --force'
check "the payload survives an uninstall through the link" 'payload_intact'
H="$(new_home .claude .config/opencode)"
ln -s "$COPY/skills" "$H/.config/opencode/skills"
check "with ~/.config/opencode/skills linked into the repository, the install is refused" '! run_copy "$H" --force'
check "the payload survives the removal of the older copy through the link" 'payload_intact'
check "the refusal comes before any write" '[ ! -e "$H/.claude/skills" ]'

echo ""
echo "=== Options ==="
HELP_TEXT="$(bash "$INSTALL" --help 2>&1)"
for opt in --force --check --dest --host --uninstall claude agents; do
    if grep -q -- "$opt" <<<"$HELP_TEXT"; then ok "--help documents $opt"; else bad "--help documents $opt"; fi
done
H="$(new_home)"
check "an unknown option is refused" '! run "$H" --bogus'

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
