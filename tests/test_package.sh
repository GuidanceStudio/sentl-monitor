#!/usr/bin/env bash
set -uo pipefail

# Verifies what a release ships: the zip tools/build_zip.py builds from the tracked payload
# files, the Claude Code plugin manifests, the Codex metadata, and the workflows that build
# and attach the zip. Every build runs on a temporary git copy of the repository, its tracked
# files committed, so the checks do not depend on what this working tree has not committed,
# and nothing in it changes.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="$REPO_ROOT/skills/sentl-monitor"
BUILD="$REPO_ROOT/tools/build_zip.py"
PASS=0
FAIL=0

ok()  { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

TMP="$(mktemp -d)"
trap 'chmod -R u+w "$TMP" 2>/dev/null; rm -rf "$TMP"' EXIT

skill_version() {
    sed -n '/^metadata:/,/^[^ ]/s/^  version: "\(.*\)"$/\1/p' "$1"
}
VERSION="$(skill_version "$PAYLOAD/SKILL.md")"

commit_all() {
    git -C "$1" add -A
    git -C "$1" -c user.name=test -c user.email=test@example.invalid -c commit.gpgsign=false \
        -c core.hooksPath=/dev/null commit -qm "${2:-copy}"
}

# A temporary repository holding the tracked files as they are in the working tree, committed.
copy_repo() {
    local dest="$1"
    mkdir -p "$dest"
    git -C "$REPO_ROOT" ls-files -z | (cd "$REPO_ROOT" && tar --null -T - -cf -) | tar -xf - -C "$dest"
    git -C "$dest" init -q
    commit_all "$dest"
}

# Lines describing the zip's entries: name, mode, date, for the checks below.
zip_listing() {
    python3 - "$1" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    for i in z.infolist():
        print(f"{i.filename}\t{(i.external_attr >> 16) & 0o777:o}\t{'-'.join(str(n) for n in i.date_time)}")
PY
}

echo "=== build_zip.py builds the zip from the tracked payload ==="
if [ ! -f "$BUILD" ]; then
    bad "tools/build_zip.py missing; the checks below need it"
fi
MAIN="$TMP/main"
copy_repo "$MAIN"
BUILD="$MAIN/tools/build_zip.py"
for n in 1 2; do
    if python3 "$BUILD" --out "$TMP/out$n" >"$TMP/build$n.txt" 2>&1; then
        ok "build $n exits 0"
    else
        bad "build $n exits 0"; sed 's/^/        /' "$TMP/build$n.txt"
    fi
done
ZIP="$TMP/out1/sentl-monitor.zip"
if [ -f "$ZIP" ] && cmp -s "$ZIP" "$TMP/out2/sentl-monitor.zip"; then
    ok "two builds are identical byte for byte"
else
    bad "two builds are identical byte for byte"
fi
if [ -f "$ZIP.sha256" ]; then
    EXPECTED="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$ZIP")"
    if [ "$(cat "$ZIP.sha256")" = "$EXPECTED  sentl-monitor.zip" ]; then
        ok "sentl-monitor.zip.sha256 holds the zip's digest in sha256sum's format"
    else
        bad "sentl-monitor.zip.sha256 holds the zip's digest in sha256sum's format"
    fi
else
    bad "sentl-monitor.zip.sha256 is written next to the zip"
fi

LISTING="$(zip_listing "$ZIP" 2>/dev/null)"
NAMES="$(cut -f1 <<<"$LISTING")"
if [ -n "$NAMES" ] && ! grep -qv '^sentl-monitor/' <<<"$NAMES"; then
    ok "every entry sits under one root folder, sentl-monitor/"
else
    bad "every entry sits under one root folder, sentl-monitor/"
fi
for f in SKILL.md LICENSE agents/openai.yaml adopt/ADOPT.md report/REPORT.md scripts/monitor.py; do
    if grep -qx "sentl-monitor/$f" <<<"$NAMES"; then ok "the zip holds $f"; else bad "the zip holds $f"; fi
done
if grep -qE '__pycache__|\.pyc$|(^|/)tests?/|(^|/)test_[^/]*$' <<<"$NAMES"; then
    bad "no __pycache__, .pyc or test file in the zip"
else
    ok "no __pycache__, .pyc or test file in the zip"
fi
TRACKED="$(git -C "$MAIN" ls-files skills/sentl-monitor | sed 's|^skills/||' | LC_ALL=C sort)"
FILES="$(grep -v '/$' <<<"$NAMES" | LC_ALL=C sort)"
if [ -n "$FILES" ] && [ "$FILES" = "$TRACKED" ]; then
    ok "the zip's files are the payload files git tracks"
else
    bad "the zip's files are the payload files git tracks"
    diff <(echo "$TRACKED") <(echo "$FILES") | sed 's/^/        /'
fi
if [ "$NAMES" = "$(LC_ALL=C sort <<<"$NAMES")" ]; then ok "entries are sorted"; else bad "entries are sorted"; fi
DATES="$(cut -f3 <<<"$LISTING" | sort -u)"
if [ -n "$LISTING" ] && [ "$DATES" = "1980-1-1-0-0-0" ]; then
    ok "every entry is dated 1980-01-01 00:00"
else
    bad "every entry is dated 1980-01-01 00:00"
fi
MODES=$(awk -F'\t' '$1 !~ /\/$/ { want = ($1 == "sentl-monitor/scripts/monitor.py") ? "755" : "644"
                                     if ($2 != want) wrong = 1; if (want == "755") seen = 1 }
                    END { print (seen && !wrong) ? "ok" : "wrong" }' <<<"$LISTING")
if [ "$MODES" = "ok" ]; then
    ok "monitor.py is 0755 and every other file 0644"
else
    bad "monitor.py is 0755 and every other file 0644"
fi
SIZE=$(wc -c <"$ZIP" 2>/dev/null || echo 0)
if [ "$SIZE" -gt 0 ] && [ "$SIZE" -le 5242880 ]; then ok "the zip is $SIZE bytes (5 MB at most)"; else bad "the zip is $SIZE bytes (5 MB at most)"; fi

echo ""
echo "=== The extracted copy runs ==="
python3 -m zipfile -e "$ZIP" "$TMP/extracted" 2>/dev/null
X_MONITOR="$TMP/extracted/sentl-monitor/scripts/monitor.py"
if python3 "$X_MONITOR" --help >"$TMP/help.txt" 2>&1; then ok "monitor.py --help exits 0"; else bad "monitor.py --help exits 0"; fi
if [ "$(python3 "$X_MONITOR" --version 2>&1)" = "$VERSION" ]; then
    ok "monitor.py --version prints SKILL.md's version ($VERSION)"
else
    bad "monitor.py --version prints SKILL.md's version ($VERSION)"
fi
mkdir -p "$TMP/study"
if python3 "$X_MONITOR" doctor --study "$TMP/study" >"$TMP/doctor.txt" 2>&1 && grep -q 'writable' "$TMP/doctor.txt"; then
    ok "monitor.py doctor exits 0 and finds the study folder writable"
else
    bad "monitor.py doctor exits 0 and finds the study folder writable"; sed 's/^/        /' "$TMP/doctor.txt"
fi

echo ""
echo "=== Caches and test files stay out, even when git tracks them ==="
COPY="$TMP/repo"
copy_repo "$COPY"
mkdir -p "$COPY/skills/sentl-monitor/scripts/__pycache__" "$COPY/skills/sentl-monitor/tests" \
    "$COPY/skills/sentl-monitor/scripts/sentlmon/__pycache__"
echo cache >"$COPY/skills/sentl-monitor/scripts/__pycache__/monitor.cpython-312.pyc"
echo "print(1)" >"$COPY/skills/sentl-monitor/scripts/test_probe.py"
echo "print(1)" >"$COPY/skills/sentl-monitor/tests/test_more.py"
git -C "$COPY" add -f skills/sentl-monitor/scripts/__pycache__ skills/sentl-monitor/scripts/test_probe.py \
    skills/sentl-monitor/tests
commit_all "$COPY" "planted"
# An ignored cache that git does not track is not an uncommitted change.
echo cache >"$COPY/skills/sentl-monitor/scripts/sentlmon/__pycache__/common.cpython-312.pyc"
if python3 "$COPY/tools/build_zip.py" --out "$TMP/out3" >"$TMP/build3.txt" 2>&1; then
    ok "an ignored cache does not count as an uncommitted change"
    NAMES3="$(zip_listing "$TMP/out3/sentl-monitor.zip" | cut -f1)"
    for f in scripts/__pycache__/monitor.cpython-312.pyc scripts/test_probe.py tests/test_more.py \
             scripts/sentlmon/__pycache__/common.cpython-312.pyc; do
        if grep -qx "sentl-monitor/$f" <<<"$NAMES3"; then bad "$f left out of the zip"; else ok "$f left out of the zip"; fi
    done
else
    bad "a build with planted files exits 0"; sed 's/^/        /' "$TMP/build3.txt"
fi

echo ""
echo "=== Uncommitted payload changes are refused unless --allow-dirty ==="
# Each case starts from a clean committed copy, changes one thing, and builds.
dirty_case() {
    local label="$1" change="$2" expect="$3"
    local copy
    copy="$(mktemp -d "$TMP/dirty-XXXXXX")"
    copy_repo "$copy"
    (cd "$copy" && eval "$change")
    rm -rf "$copy/dist"
    if python3 "$copy/tools/build_zip.py" --out "$copy/dist" >"$TMP/dirty.txt" 2>&1; then STATUS=0; else STATUS=$?; fi
    if [ "$expect" = refused ]; then
        if [ "$STATUS" -ne 0 ] && [ ! -e "$copy/dist/sentl-monitor.zip" ] && grep -q -- "--allow-dirty" "$TMP/dirty.txt"; then
            ok "$label is refused, naming --allow-dirty"
        else
            bad "$label is refused, naming --allow-dirty (exit $STATUS)"; sed 's/^/        /' "$TMP/dirty.txt"
        fi
        cp "$TMP/dirty.txt" "$TMP/dirty-refusal.txt"
        if python3 "$copy/tools/build_zip.py" --allow-dirty --out "$copy/dist" >"$TMP/dirty.txt" 2>&1 \
            && [ -f "$copy/dist/sentl-monitor.zip" ]; then
            ok "$label builds with --allow-dirty"
        else
            bad "$label builds with --allow-dirty"; sed 's/^/        /' "$TMP/dirty.txt"
        fi
        DIRTY_NAMES="$(zip_listing "$copy/dist/sentl-monitor.zip" 2>/dev/null | cut -f1)"
    elif [ "$STATUS" -eq 0 ]; then
        ok "$label builds"
    else
        bad "$label builds (exit $STATUS)"; sed 's/^/        /' "$TMP/dirty.txt"
    fi
}
dirty_case "an edited payload file" 'echo "edit" >>skills/sentl-monitor/adopt/ADOPT.md' refused
if grep -q "skills/sentl-monitor/adopt/ADOPT.md" "$TMP/dirty-refusal.txt" 2>/dev/null; then
    ok "the refusal names the changed file"
else
    bad "the refusal names the changed file"
fi
dirty_case "a staged payload change" 'echo "edit" >>skills/sentl-monitor/SKILL.md; git add skills/sentl-monitor/SKILL.md' refused
dirty_case "an untracked payload file" 'echo "notes" >skills/sentl-monitor/notes.md' refused
if grep -qx "sentl-monitor/notes.md" <<<"$DIRTY_NAMES"; then
    bad "with --allow-dirty, an untracked file still stays out of the zip"
else
    ok "with --allow-dirty, an untracked file still stays out of the zip"
fi
dirty_case "a deleted payload file" 'rm skills/sentl-monitor/report/INSIGHTS.md' refused
dirty_case "a change outside the payload" 'echo "edit" >>README.md' builds

echo ""
echo "=== A frontmatter over a limit is refused ==="
# Each case edits SKILL.md (or the payload) in a fresh copy and expects a refusal naming the field.
refused() {
    local label="$1" field="$2" script="$3"
    local copy="$TMP/refuse-$PASS-$FAIL"
    copy_repo "$copy"
    python3 - "$copy/skills/sentl-monitor" <<<"$script"
    commit_all "$copy" "over a limit"
    if python3 "$copy/tools/build_zip.py" --out "$copy/dist" >"$TMP/refused.txt" 2>&1; then
        bad "$label is refused (exit 0)"
    elif ! grep -qi -- "$field" "$TMP/refused.txt"; then
        bad "$label: the refusal names $field"; sed 's/^/        /' "$TMP/refused.txt"
    elif [ -e "$copy/dist/sentl-monitor.zip" ]; then
        bad "$label: no zip is written"
    else
        ok "$label is refused, naming $field"
    fi
}
EDIT_PRELUDE='import pathlib, re, sys
p = pathlib.Path(sys.argv[1]) / "SKILL.md"
t = p.read_text(encoding="utf-8")
def sub(pattern, repl):
    global t
    t, n = re.subn(pattern, repl, t, count=1, flags=re.M | re.S)
    assert n == 1, pattern
'
refused "a 201-character description" "description" "$EDIT_PRELUDE
sub(r'^description: >-\n.*?(?=^license:)', 'description: ' + 'x' * 201 + '\n')
p.write_text(t, encoding='utf-8')"
refused "a description holding <" "description" "$EDIT_PRELUDE
sub(r'^description: >-\n', 'description: >-\n  Reads <runs>\n')
p.write_text(t, encoding='utf-8')"
refused "a 501-character compatibility" "compatibility" "$EDIT_PRELUDE
sub(r'^compatibility: >-\n.*?(?=^metadata:)', 'compatibility: ' + 'x' * 501 + '\n')
p.write_text(t, encoding='utf-8')"
refused "a missing version" "version" "$EDIT_PRELUDE
sub(r'^  version: .*?\n', '')
p.write_text(t, encoding='utf-8')"
refused "a name that differs from the folder" "name" "$EDIT_PRELUDE
sub(r'^name: sentl-monitor$', 'name: sentl-monitor-two')
p.write_text(t, encoding='utf-8')"
refused "a name with a reserved word" "name" "$EDIT_PRELUDE
sub(r'^name: sentl-monitor$', 'name: claude-monitor')
p.write_text(t, encoding='utf-8')"
refused "a payload LICENSE that differs from the root one" "LICENSE" 'import pathlib, sys
p = pathlib.Path(sys.argv[1]) / "LICENSE"
p.write_text(p.read_text() + "changed\n")'
refused "a zip over 5 MB" "5 MB" 'import os, pathlib, subprocess, sys
p = pathlib.Path(sys.argv[1]) / "noise.bin"
p.write_bytes(os.urandom(6 * 1024 * 1024))
subprocess.run(["git", "-C", sys.argv[1], "add", "noise.bin"], check=True)'

echo ""
echo "=== Claude Code plugin manifests: the skill only, at SKILL.md's name and version ==="
MANIFESTS=$(python3 - "$REPO_ROOT" <<'PY' 2>&1
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ("marketplace.json", "plugin.json"):
    try:
        data = json.loads((root / ".claude-plugin" / name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"{name}\tparse\t{exc}")
        continue
    print(f"{name}\tparse\tok")
    if name == "marketplace.json":
        plugins = data.get("plugins") or []
        print(f"{name}\tname\t{data.get('name')}")
        print(f"{name}\towner\t{(data.get('owner') or {}).get('name', '')}")
        print(f"{name}\tplugins\t{len(plugins)}")
        entry = plugins[0] if plugins else {}
        print(f"{name}\tplugin.name\t{entry.get('name')}")
        print(f"{name}\tplugin.source\t{entry.get('source')}")
        print(f"{name}\tplugin.version\t{entry.get('version', data.get('metadata', {}).get('version'))}")
        print(f"{name}\tplugin.mcpServers\t{'mcpServers' in entry}")
    else:
        print(f"{name}\tname\t{data.get('name')}")
        print(f"{name}\tversion\t{data.get('version')}")
        print(f"{name}\tlicense\t{data.get('license')}")
        print(f"{name}\tmcpServers\t{'mcpServers' in data}")
        print(f"{name}\tdescription\t{data.get('description')}")
PY
)
field() { awk -F'\t' -v f="$1" -v k="$2" '$1 == f && $2 == k { print $3 }' <<<"$MANIFESTS"; }
for f in marketplace.json plugin.json; do
    if [ "$(field "$f" parse)" = "ok" ]; then ok "$f parses"; else bad "$f parses: $(field "$f" parse)"; fi
done
[ "$(field marketplace.json name)" = "sentl-monitor" ] && ok "the marketplace is named sentl-monitor" \
    || bad "the marketplace is named sentl-monitor"
[ -n "$(field marketplace.json owner)" ] && ok "the marketplace names an owner" || bad "the marketplace names an owner"
[ "$(field marketplace.json plugins)" = "1" ] && ok "the marketplace lists one plugin" || bad "the marketplace lists one plugin"
[ "$(field marketplace.json plugin.name)" = "sentl-monitor" ] && ok "its plugin is sentl-monitor" \
    || bad "its plugin is sentl-monitor"
[ "$(field marketplace.json plugin.source)" = "./" ] && ok "the plugin's source is the repository root" \
    || bad "the plugin's source is the repository root"
[ "$(field marketplace.json plugin.version)" = "$VERSION" ] && ok "the marketplace entry is at SKILL.md's version" \
    || bad "the marketplace entry is at SKILL.md's version ($(field marketplace.json plugin.version) vs $VERSION)"
[ "$(field plugin.json name)" = "sentl-monitor" ] && ok "plugin.json is named sentl-monitor" \
    || bad "plugin.json is named sentl-monitor"
[ "$(field plugin.json version)" = "$VERSION" ] && ok "plugin.json is at SKILL.md's version" \
    || bad "plugin.json is at SKILL.md's version ($(field plugin.json version) vs $VERSION)"
[ "$(field plugin.json license)" = "MIT" ] && ok "plugin.json's license is MIT" || bad "plugin.json's license is MIT"
SKILL_DESC=$(python3 - "$PAYLOAD/SKILL.md" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
block = re.search(r"^description: >-\n((?:  .*\n)+)", text, re.M)
print(" ".join(line.strip() for line in block.group(1).splitlines()) if block else "")
PY
)
[ -n "$SKILL_DESC" ] && [ "$(field plugin.json description)" = "$SKILL_DESC" ] \
    && ok "plugin.json's description is SKILL.md's" || bad "plugin.json's description is SKILL.md's"
if [ "$(field plugin.json mcpServers)" = "False" ] && [ "$(field marketplace.json plugin.mcpServers)" = "False" ] \
    && [ ! -e "$REPO_ROOT/.mcp.json" ]; then
    ok "the plugin carries no MCP server entry"
else
    bad "the plugin carries no MCP server entry"
fi
if [ -d "$REPO_ROOT/agents" ] || [ -d "$REPO_ROOT/commands" ] || [ -d "$REPO_ROOT/hooks" ]; then
    bad "no agents/, commands/ or hooks/ at the plugin root, which Claude Code would load"
else
    ok "no agents/, commands/ or hooks/ at the plugin root, which Claude Code would load"
fi

if command -v claude >/dev/null 2>&1; then
    mkdir -p "$TMP/claude-home"
    if (cd "$REPO_ROOT" && HOME="$TMP/claude-home" claude plugin validate . >"$TMP/validate.txt" 2>&1); then
        ok "claude plugin validate . passes"
    else
        bad "claude plugin validate . passes"; sed 's/^/        /' "$TMP/validate.txt"
    fi
else
    echo "  (claude not on PATH: claude plugin validate skipped)"
fi

echo ""
echo "=== agents/openai.yaml: Codex's display fields and the Sentl MCP dependency ==="
OPENAI="$PAYLOAD/agents/openai.yaml"
for key in '^interface:' '^  display_name: ' '^  short_description: ' '^  default_prompt: ' '^dependencies:' \
           '^  tools:' '^    - type: "mcp"' '^      transport: "streamable_http"' \
           '^      url: "https://app.sentl.ai/mcp"'; do
    if grep -qE "$key" "$OPENAI" 2>/dev/null; then ok "openai.yaml has $key"; else bad "openai.yaml has $key"; fi
done
SHORT=$(sed -n 's/^  short_description: "\(.*\)"$/\1/p' "$OPENAI" 2>/dev/null)
if [ -n "$SHORT" ] && [ "${#SHORT}" -le 64 ]; then
    ok "short_description is ${#SHORT} characters (64 at most)"
else
    bad "short_description is ${#SHORT} characters (must be 1..64)"
fi
if grep -q '\$sentl-monitor' "$OPENAI" 2>/dev/null; then
    ok "the default prompt invokes \$sentl-monitor"
else
    bad "the default prompt invokes \$sentl-monitor"
fi

echo ""
echo "=== Workflows ==="
RELEASE="$REPO_ROOT/.github/workflows/release.yml"
TESTS_WF="$REPO_ROOT/.github/workflows/test.yml"
has_line() { if grep -qE -- "$1" "$2" 2>/dev/null; then ok "$3"; else bad "$3"; fi; }
has_line "^ *- ['\"]?v\*['\"]?$" "$RELEASE" "release.yml runs on a pushed v* tag"
has_line "bash tests/test_all.sh" "$RELEASE" "release.yml runs the tests first"
has_line "monitor.py --version" "$RELEASE" "release.yml compares the tag with SKILL.md's version"
has_line "python3 tools/build_zip.py" "$RELEASE" "release.yml builds the zip"
has_line "dist/sentl-monitor.zip dist/sentl-monitor.zip.sha256" "$RELEASE" \
    "release.yml attaches the zip and its sha256 under fixed names"
# Every action is pinned to a full commit SHA, its release named in a comment.
for wf in "$RELEASE" "$TESTS_WF"; do
    USES="$(grep -E '^ *- uses: |^ *uses: ' "$wf" 2>/dev/null)"
    UNPINNED="$(grep -vE 'uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40} # v[0-9]+(\.[0-9]+)*$' <<<"$USES")"
    if [ -n "$USES" ] && [ -z "$UNPINNED" ]; then
        ok "$(basename "$wf") pins every action to a commit SHA with its version in a comment"
    else
        bad "$(basename "$wf") pins every action to a commit SHA with its version in a comment"
        sed 's/^/        /' <<<"$UNPINNED"
    fi
done
# Write access to the repository's contents belongs to the release job alone.
PERMS=$(python3 - "$RELEASE" "$TESTS_WF" <<'PY'
import re, sys
def blocks(path):
    """(indent of the permissions key, its contents lines) for each permissions block."""
    lines = open(path, encoding="utf-8").read().splitlines()
    out = []
    for i, line in enumerate(lines):
        m = re.match(r"^( *)permissions:\s*(.*)$", line)
        if not m:
            continue
        indent, inline = len(m.group(1)), m.group(2).strip()
        body = [inline] if inline else []
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt.strip())
        out.append((indent, " ".join(body)))
    return out
release, tests = blocks(sys.argv[1]), blocks(sys.argv[2])
top = [body for indent, body in release if indent == 0]
job = [body for indent, body in release if indent > 0]
print("top-read" if top and all("write" not in b for b in top) else "top-not-read")
print("job-write" if any("contents: write" in b for b in job) else "job-no-write")
print("tests-read" if tests and all("write" not in b for _, b in tests) else "tests-not-read")
PY
)
for want in top-read job-write tests-read; do
    case "$want" in
        top-read) label="release.yml grants no write access at the top level" ;;
        job-write) label="release.yml grants contents: write on the release job" ;;
        tests-read) label="test.yml grants no write access" ;;
    esac
    if grep -qx "$want" <<<"$PERMS"; then ok "$label"; else bad "$label"; fi
done
for v in 3.10 3.11 3.12 3.13; do
    has_line "['\"]${v}['\"]" "$TESTS_WF" "test.yml runs on Python $v"
done
has_line "bash tests/test_all.sh" "$TESTS_WF" "test.yml runs tests/test_all.sh"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
