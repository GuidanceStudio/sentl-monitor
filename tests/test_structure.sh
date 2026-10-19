#!/usr/bin/env bash
set -uo pipefail

# Verifies the repository layout: dev-tree files at the root, the installable
# payload in skills/sentl-monitor/, where the Claude Code plugin format looks
# for skills, and scripts that import only the standard library.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="$REPO_ROOT/skills/sentl-monitor"
PASS=0
FAIL=0

ok()  { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

assert_file()       { if [ -f "$REPO_ROOT/$1" ]; then ok "$1 exists"; else bad "$1 missing"; fi; }
assert_nonempty()   { if [ -s "$REPO_ROOT/$1" ]; then ok "$1 is non-empty"; else bad "$1 is empty or missing"; fi; }
assert_dir()        { if [ -d "$REPO_ROOT/$1" ]; then ok "$1/ exists"; else bad "$1/ missing"; fi; }
assert_executable() { if [ -x "$REPO_ROOT/$1" ]; then ok "$1 is executable"; else bad "$1 is not executable"; fi; }

# --no-index asks whether the rule matches, whether or not the path exists.
assert_ignored() {
    if git -C "$REPO_ROOT" check-ignore -q --no-index "$1"; then
        ok ".gitignore ignores $1"
    else
        bad ".gitignore does not ignore $1"
    fi
}

echo "=== Dev-tree root ==="
for f in LICENSE README.md ARCHITECTURE.md DEVPLAN.md .gitignore install.sh; do
    assert_file "$f"
done
assert_executable "install.sh"
assert_dir "tests"
assert_dir "tests/python"

echo ""
echo "=== Client data and build artefacts stay out of git ==="
assert_ignored "studies/probe/report.md"
assert_ignored "snapshots/probe/report.md"
assert_ignored "skills/sentl-monitor/scripts/__pycache__/probe.pyc"
assert_ignored "dist/sentl-monitor.zip"

echo ""
echo "=== Line endings stay LF on every system ==="
assert_file ".gitattributes"
for rule in "*.sh text eol=lf" "*.py text eol=lf"; do
    if grep -qxF "$rule" "$REPO_ROOT/.gitattributes" 2>/dev/null; then
        ok ".gitattributes has '$rule'"
    else
        bad ".gitattributes lacks '$rule'"
    fi
done

echo ""
echo "=== Installable payload ==="
assert_dir "skills/sentl-monitor"
if [ -e "$REPO_ROOT/sentl-monitor" ]; then bad "the old payload folder sentl-monitor/ is still at the root"; else ok "no payload folder left at the root"; fi
assert_nonempty "skills/sentl-monitor/SKILL.md"
assert_nonempty "skills/sentl-monitor/adopt/ADOPT.md"
assert_nonempty "skills/sentl-monitor/report/REPORT.md"
assert_nonempty "skills/sentl-monitor/report/INSIGHTS.md"
assert_nonempty "skills/sentl-monitor/scripts/monitor.py"
assert_dir "skills/sentl-monitor/scripts/sentlmon"
assert_file "skills/sentl-monitor/scripts/sentlmon/__init__.py"

echo ""
echo "=== README: an install section per host and a support table ==="
# Until a host's run is recorded in the devplan (R3e), its row says "Not yet tested".
README_ROWS=$(awk '/^## Install$/ {on=1; next} on && /^## / {exit} on && /^\| / {print}' "$REPO_ROOT/README.md")
for host in "Claude Code" opencode Codex claude.ai ChatGPT; do
    row=$(grep -F "| $host |" <<<"$README_ROWS")
    if [ -z "$row" ]; then
        bad "the support table has a row for $host"
    elif [ "$host" = "Claude Code" ]; then
        if grep -q "| Tested" <<<"$row"; then ok "the support table marks Claude Code tested"; else bad "the support table marks Claude Code tested"; fi
    elif grep -q "| Not yet tested" <<<"$row"; then
        ok "the support table marks $host not yet tested"
    else
        bad "the support table marks $host not yet tested"
    fi
    if grep -q "^### $host$" "$REPO_ROOT/README.md"; then ok "README has an install subsection for $host"; else bad "README has an install subsection for $host"; fi
done
# Captured before grepping: grep -q exits at the first match, and the SIGPIPE awk then gets
# would fail the pipeline under pipefail.
INSTALL_SECTION=$(awk '/^## Install$/ {on=1; next} on && /^## / {exit} on' "$REPO_ROOT/README.md")
for cmd in "--host claude" "--host agents" "--check" "--uninstall" "monitor.py doctor"; do
    if grep -qF -- "$cmd" <<<"$INSTALL_SECTION"; then
        ok "the install section names $cmd"
    else
        bad "the install section names $cmd"
    fi
done
# Install commands in the shell forms each CLI's --help confirms; Codex's step names the server.
for cmd in "claude plugin install sentl-monitor --marketplace GuidanceStudio/sentl-monitor" \
           "claude plugin marketplace add GuidanceStudio/sentl-monitor" \
           "claude plugin install sentl-monitor@sentl-monitor" \
           "codex mcp add sentinel-reputation --url https://app.sentl.ai/mcp/reputation" \
           "codex mcp login sentinel-reputation"; do
    if grep -qF -- "$cmd" <<<"$INSTALL_SECTION"; then ok "the install section gives '$cmd'"; else bad "the install section gives '$cmd'"; fi
done
if grep -qE '^/plugin ' <<<"$INSTALL_SECTION"; then
    bad "the install section gives no /plugin slash command, which no --help confirms"
else
    ok "the install section gives no /plugin slash command, which no --help confirms"
fi
CHATGPT_ROW=$(grep -F "| ChatGPT |" <<<"$README_ROWS")
CHATGPT_SECTION=$(awk '/^### ChatGPT$/ {on=1; next} on && /^##/ {exit} on' "$REPO_ROOT/README.md")
for phrase in "desktop app" "Codex CLI" "IDE extension" "only inside plugins" "not confirmed"; do
    if grep -qF "$phrase" <<<"$CHATGPT_SECTION"; then
        ok "the ChatGPT subsection says: $phrase"
    else
        bad "the ChatGPT subsection says: $phrase"
    fi
done
if grep -qF "not confirmed" <<<"$CHATGPT_ROW"; then ok "the ChatGPT row says the upload on chatgpt.com is not confirmed"; else bad "the ChatGPT row says the upload on chatgpt.com is not confirmed"; fi
if grep -q "releases/latest/download/sentl-monitor.zip" "$REPO_ROOT/README.md"; then
    ok "README links the latest release's zip"
else
    bad "README links the latest release's zip"
fi

echo ""
echo "=== Scripts import only the standard library ==="
if [ -f "$PAYLOAD/scripts/monitor.py" ]; then
    NONSTD=$(python3 - "$PAYLOAD/scripts" <<'PY'
import ast, pathlib, sys
scripts = pathlib.Path(sys.argv[1])
allowed = set(sys.stdlib_module_names) | {"sentlmon"}
files = [scripts / "monitor.py"] + sorted((scripts / "sentlmon").rglob("*.py"))
for path in files:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module]
        else:
            continue
        for name in names:
            if name.split(".")[0] not in allowed:
                print(f"{path.relative_to(scripts.parent.parent)}:{node.lineno}: {name}")
PY
    )
    STATUS=$?
    if [ "$STATUS" -ne 0 ]; then
        bad "import scan could not parse the scripts (exit $STATUS)"
    elif [ -z "$NONSTD" ]; then
        ok "monitor.py and sentlmon/ import only the standard library"
    else
        bad "imports outside the standard library:"
        echo "$NONSTD" | sed 's/^/        /'
    fi
else
    bad "import scan needs skills/sentl-monitor/scripts/monitor.py"
fi

echo ""
echo "=== Scripts parse on Python 3.10 ==="
# Before 3.12 an f-string cannot reuse its own quote inside a replacement field. The check reads
# the tokens a 3.12+ interpreter gives; an older one compiles the scripts instead.
NESTED=$(python3 - "$PAYLOAD/scripts" <<'PY'
import pathlib, sys, tokenize
scripts = pathlib.Path(sys.argv[1])
for path in [scripts / "monitor.py"] + sorted((scripts / "sentlmon").rglob("*.py")):
    if not hasattr(tokenize, "FSTRING_START"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        continue
    quotes = []
    with open(path, "rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            text = tok.string.lstrip("rRbBfFuU")
            if tok.type == tokenize.FSTRING_START:
                if quotes and text[0] in quotes:
                    print(f"{path.name}:{tok.start[0]}: an f-string reuses the quote of the one around it")
                quotes.append(text[0])
            elif tok.type == tokenize.FSTRING_END:
                quotes.pop()
            elif tok.type == tokenize.STRING and quotes and text[:1] in quotes:
                print(f"{path.name}:{tok.start[0]}: a string reuses the quote of the f-string around it")
PY
)
if [ $? -ne 0 ]; then
    bad "the scripts do not compile on this interpreter"
elif [ -z "$NESTED" ]; then
    ok "no f-string reuses its own quote inside a replacement field"
else
    bad "f-strings that Python 3.10 and 3.11 refuse:"
    echo "$NESTED" | sed 's/^/        /'
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
