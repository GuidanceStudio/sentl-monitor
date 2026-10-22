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
# Until a host's run is recorded in the devplan (R3e), its row says "Not yet tested". The support
# table opens the README, under "What works today".
README_ROWS=$(awk '/^## What works today$/ {on=1; next} on && /^## / {exit} on && /^\| / {print}' "$REPO_ROOT/README.md")
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
for cmd in "--host claude" "--host agents" "--check" "monitor.py doctor"; do
    if grep -qF -- "$cmd" <<<"$INSTALL_SECTION"; then
        ok "the install section names $cmd"
    else
        bad "the install section names $cmd"
    fi
done
UPDATE_SECTION=$(awk '/^## Update and uninstall$/ {on=1; next} on && /^## / {exit} on' "$REPO_ROOT/README.md")
for cmd in "./install.sh --uninstall" "./install.sh --force" "claude plugin update sentl-monitor@sentl-monitor" \
           "claude plugin uninstall sentl-monitor@sentl-monitor"; do
    if grep -qF -- "$cmd" <<<"$UPDATE_SECTION"; then
        ok "the update and uninstall section gives '$cmd'"
    else
        bad "the update and uninstall section gives '$cmd'"
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
echo "=== README: what works, what is planned, and the commands it shows (R1) ==="
README="$REPO_ROOT/README.md"
MONITOR="$PAYLOAD/scripts/monitor.py"
# A routes table is a table whose first header cell is "Route". Outside the section "## Planned",
# every route such a table lists has its playbook (<route>/<ROUTE>.md in the payload), every
# route with a playbook is listed, and every `sentl-monitor <route>` the README tells the reader
# to invoke, in a code span, has its playbook. The routes under "## Planned" have none yet.
ROUTE_PROBLEMS=$(python3 - "$README" "$PAYLOAD" <<'PY'
import pathlib, re, sys
text = open(sys.argv[1], encoding="utf-8").read()
payload = pathlib.Path(sys.argv[2])
playbooks = {p.parent.name for p in payload.glob("*/*.md") if p.stem == p.parent.name.upper()}
sections = re.split(r"(?m)^(?=## )", text)
planned = [s for s in sections if s.splitlines()[0].strip() == "## Planned"]
if len(planned) != 1:
    print("the README has one section '## Planned'")
listed, in_table = set(), False
for section in sections:
    if section in planned:
        continue
    for line in section.splitlines():
        if re.match(r"^\|\s*Route\s*\|", line):
            in_table = True
            continue
        if in_table and (not line.startswith("|")):
            in_table = False
        if not in_table or re.fullmatch(r"\|[\s:|-]+\|", line):
            continue
        m = re.match(r"^\|\s*`([a-z-]+)", line)
        if not m:
            print(f"a routes table row names no route: {line}")
            continue
        listed.add(m.group(1))
    for route in re.findall(r"`sentl-monitor ([a-z][a-z-]*)", section):
        if route not in playbooks:
            print(f"the README invokes 'sentl-monitor {route}' outside 'Planned', and {route} has no playbook")
if not listed:
    print("the README has a routes table outside 'Planned'")
for route in sorted(listed - playbooks):
    print(f"the routes table lists '{route}' outside 'Planned', and it has no playbook")
for route in sorted(playbooks - listed):
    print(f"the routes table does not list '{route}', which has a playbook")
for section in planned:
    for route in ("brief", "design", "setup", "snapshot"):
        if f"`{route}" not in section:
            print(f"'## Planned' names the {route} route")
    for route in sorted(playbooks):
        if re.search(rf"^\|\s*`{route}\b", section, re.M):
            print(f"'## Planned' lists '{route}', which has a playbook")
PY
)
if [ -z "$ROUTE_PROBLEMS" ]; then
    ok "the README's routes table lists exactly the routes with a playbook, the others under 'Planned'"
else
    bad "the README's routes:"
    echo "$ROUTE_PROBLEMS" | sed 's/^/        /'
fi
# Every `monitor.py <command>` the README shows, in a code span or after python3, is a command of
# monitor.py --help, and every option shown after it is in that command's --help; a global option
# shown (`monitor.py --version`) is in monitor.py --help.
COMMAND_PROBLEMS=$(python3 - "$README" "$MONITOR" <<'PY'
import re, subprocess, sys
text = open(sys.argv[1], encoding="utf-8").read().replace("\\\n", " ")
monitor = sys.argv[2]
def help_of(*args):
    proc = subprocess.run([sys.executable, monitor, *args, "--help"], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else ""
top = help_of()
commands = set(re.findall(r"^    ([a-z]+)\s", top, re.M))
seen = 0
for m in re.finditer(r"(?:`|python3 [^`\n]*?)monitor\.py((?:[ \t]+[^`\n|]*)?)", text):
    words = m.group(1).split()
    if not words or words[0].startswith("<"):
        continue
    seen += 1
    first = words[0]
    if first.startswith("--"):
        if first not in top:
            print(f"'monitor.py {first}' is not an option of monitor.py --help")
        continue
    if first not in commands:
        print(f"'monitor.py {first}' is not a command of monitor.py --help")
        continue
    sub = help_of(first)
    for option in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", " ".join(words[1:])):
        if not re.search(rf"(?<![\w-]){re.escape(option)}(?![\w-])", sub):
            print(f"'monitor.py {first} {option}': {option} is not in monitor.py {first} --help")
if not seen:
    print("the README shows at least one monitor.py command")
PY
)
if [ -z "$COMMAND_PROBLEMS" ]; then
    ok "every monitor.py command and option the README shows is in monitor.py --help"
else
    bad "monitor.py commands in the README:"
    echo "$COMMAND_PROBLEMS" | sed 's/^/        /'
fi
# The sample report the README links exists; the unit test test_sample_report.py runs check on it.
SAMPLE_LINKS=$(grep -oE '\(examples/[^)]+\.md\)' "$README" | tr -d '()' | sort -u)
if [ -z "$SAMPLE_LINKS" ]; then
    bad "the README links the sample report in examples/"
else
    for link in $SAMPLE_LINKS; do
        if [ -f "$REPO_ROOT/$link" ]; then ok "the README's link $link exists"; else bad "the README's link $link exists"; fi
    done
fi
for section in "## Prerequisites" "## Exit codes" "## Update and uninstall" "## Version and changes" "## Planned" "## Contributing and support"; do
    if grep -qxF "$section" "$README"; then ok "README has '$section'"; else bad "README has '$section'"; fi
done
# Each exit code monitor.py ends with gets a line saying what to do.
EXIT_SECTION=$(awk '/^## Exit codes$/ {on=1; next} on && /^## / {exit} on' "$README")
for code in 0 1 2 3 4 5 6 130; do
    if grep -qE "^\| $code \|" <<<"$EXIT_SECTION"; then ok "the exit codes table has $code"; else bad "the exit codes table has $code"; fi
done
# R1 review: Sentl's tools in every folder, the tested install route first, the hosts where a report
# cannot be produced, the release link, the skill's folder, and md2 named with its link.
CLAUDE_SECTION=$(awk '/^### Claude Code$/ {on=1; next} on && /^##/ {exit} on' "$README")
MCP_ADD="claude mcp add --scope user --transport http sentinel-reputation https://app.sentl.ai/mcp/reputation"
if grep -qxF -- "$MCP_ADD" <<<"$CLAUDE_SECTION"; then ok "the Claude Code subsection gives '$MCP_ADD'"; else bad "the Claude Code subsection gives '$MCP_ADD'"; fi
if grep -F "claude mcp add" "$README" | grep -vqF -- "--scope user"; then
    bad "every 'claude mcp add' in the README has --scope user"
else
    ok "every 'claude mcp add' in the README has --scope user"
fi
FIRST_INSTALL=$(grep -nE '^\./install\.sh --host claude$|^claude plugin install ' <<<"$CLAUDE_SECTION" | head -1)
if grep -q "install.sh" <<<"$FIRST_INSTALL"; then
    ok "the Claude Code subsection leads with install.sh, the tested route"
else
    bad "the Claude Code subsection leads with install.sh, the tested route"
fi
for host in Codex claude.ai ChatGPT; do
    SUB=$(awk -v h="### $host" '$0 == h {on=1; next} on && /^##/ {exit} on' "$README")
    TEXT=$(tr -s '\n ' ' ' <<<"$SUB")
    if grep -qF "reads Sentl's run export" <<<"$TEXT" && grep -qF "not been tested" <<<"$TEXT"; then
        ok "the $host subsection says a report reads Sentl's run export and that it is not tested yet"
    else
        bad "the $host subsection says a report reads Sentl's run export and that it is not tested yet"
    fi
done
if grep -qF "once v0.1.0 is released" <<<"$(tr -s '\n ' ' ' <<<"$(awk '/^### claude.ai$/ {on=1; next} on && /^##/ {exit} on' "$README")")"; then
    ok "the claude.ai subsection says the download link works once v0.1.0 is released"
else
    bad "the claude.ai subsection says the download link works once v0.1.0 is released"
fi
if grep -qF "<skill folder>" "$README"; then bad "the README resolves <skill folder> to the install paths"; else ok "the README resolves <skill folder> to the install paths"; fi
for path in "~/.claude/skills/sentl-monitor" "~/.agents/skills/sentl-monitor" "claude plugin list --json"; do
    if grep -qF -- "$path" "$README"; then ok "the README names $path"; else bad "the README names $path"; fi
done
for f in README.md CHANGELOG.md; do
    if grep -q "md2" "$REPO_ROOT/$f" && ! grep -qF "github.com/GuidanceStudio/md2" "$REPO_ROOT/$f"; then
        bad "$f links md2 where it names it"
    else
        ok "$f links md2 where it names it"
    fi
done
if grep -qF "by their suffix" <<<"$(tr -s '\n ' ' ' <<<"$(awk '/^## Prerequisites$/ {on=1; next} on && /^## / {exit} on' "$README")")"; then
    ok "the prerequisites say the skill finds Sentl's tools by their suffix"
else
    bad "the prerequisites say the skill finds Sentl's tools by their suffix"
fi
assert_nonempty "CHANGELOG.md"
if grep -qE "^## 0\.1\.0 " "$REPO_ROOT/CHANGELOG.md" 2>/dev/null; then
    ok "CHANGELOG.md has an entry for 0.1.0"
else
    bad "CHANGELOG.md has an entry for 0.1.0"
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
