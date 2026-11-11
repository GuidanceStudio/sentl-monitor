#!/usr/bin/env bash
set -uo pipefail

# Contract tests for the router SKILL.md and the monitor.py entry point.
#
# Every playbook path the router dispatches to must exist on disk. The router
# grows one route per milestone, so this holds at every commit without
# placeholder files for routes not built yet.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="$REPO_ROOT/skills/sentl-monitor"
SKILL="$PAYLOAD/SKILL.md"
MONITOR="$PAYLOAD/scripts/monitor.py"
PASS=0
FAIL=0

ok()  { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

# grep -i: these are prose contracts, not exact strings.
has() {
    local pattern="$1" file="$2" label="$3"
    if grep -qiE "$pattern" "$file" 2>/dev/null; then ok "$label"; else bad "$label"; fi
}

if [ ! -f "$SKILL" ]; then
    bad "skills/sentl-monitor/SKILL.md missing; every check below reads it"
fi

echo "=== Frontmatter ==="

if [ "$(head -1 "$SKILL" 2>/dev/null)" = "---" ]; then
    ok "SKILL.md opens with a frontmatter fence"
else
    bad "SKILL.md opens with a frontmatter fence"
fi

has '^name: sentl-monitor$' "$SKILL" "frontmatter declares name: sentl-monitor"
has '^description:'         "$SKILL" "frontmatter declares a description"
has '^compatibility:'       "$SKILL" "frontmatter declares compatibility"

# The limits every host applies: the agentskills.io spec (name, compatibility, metadata) and
# claude.ai's upload (description <= 200 characters, no XML tags, "claude" and "anthropic"
# reserved). The parser reads the YAML subset SKILL.md uses: plain, quoted and folded scalars
# and one nested mapping.
FM=$(python3 - "$SKILL" <<'PY' 2>/dev/null
import json, re, sys
text = open(sys.argv[1], encoding="utf-8").read().replace("\r\n", "\n")
m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
if not m:
    print("{}"); raise SystemExit
fm, key, block, nested = {}, None, None, None
def scalar(v):
    v = v.strip()
    if v[:1] == '"' and v[-1:] == '"':
        return json.loads(v)
    if v[:1] == "'" and v[-1:] == "'":
        return v[1:-1].replace("''", "'")
    return v
for line in m.group(1).split("\n"):
    if line.strip().startswith("#") or not line.strip():
        if block is not None:
            block.append("")
        continue
    if not line.startswith(" "):
        key, rest = line.split(":", 1)
        rest = rest.strip()
        block = nested = None
        if rest in (">", ">-", "|", "|-"):
            block = []
            fm[key] = block
        elif rest == "":
            nested = fm[key] = {}
        else:
            fm[key] = scalar(rest)
    elif block is not None:
        block.append(line.strip())
    elif nested is not None:
        k, v = line.strip().split(":", 1)
        nested[k] = v.strip()
for k, v in fm.items():
    if isinstance(v, list):
        fm[k] = " ".join(x for x in v if x)
print(json.dumps(fm))
PY
)
fm() { python3 -c 'import json,sys; d=json.loads(sys.argv[1]); 
for k in sys.argv[2].split("."): d = d.get(k, "") if isinstance(d, dict) else ""
print(d if isinstance(d, str) else json.dumps(d))' "${FM:-{\}}" "$1"; }

NAME="$(fm name)"
FOLDER="$(basename "$PAYLOAD")"
if [ "$NAME" = "$FOLDER" ]; then ok "name equals the folder ($FOLDER)"; else bad "name '$NAME' differs from the folder '$FOLDER'"; fi
if [[ "$NAME" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] && [ "${#NAME}" -le 64 ]; then
    ok "name is lowercase letters, digits and single hyphens, at most 64 characters"
else
    bad "name '$NAME' breaks the spec's pattern or length"
fi
if grep -qiE 'claude|anthropic' <<<"$NAME"; then bad "name holds a word claude.ai reserves"; else ok "name holds no word claude.ai reserves"; fi

DESC="$(fm description)"
if [ "${#DESC}" -gt 0 ] && [ "${#DESC}" -le 200 ]; then
    ok "description is ${#DESC} characters (claude.ai allows 200)"
else
    bad "description is ${#DESC} characters (must be 1..200)"
fi
if grep -q '[<>]' <<<"$DESC"; then bad "description holds < or >"; else ok "description holds no < or >"; fi

COMPAT="$(fm compatibility)"
if [ "${#COMPAT}" -gt 0 ] && [ "${#COMPAT}" -le 500 ]; then
    ok "compatibility is ${#COMPAT} chars (<= 500)"
else
    bad "compatibility is ${#COMPAT} chars (must be 1..500)"
fi
for host in "Claude Code" opencode Codex claude.ai ChatGPT; do
    if grep -qF "$host" <<<"$COMPAT"; then ok "compatibility names $host"; else bad "compatibility names $host"; fi
done

if [ "$(fm license)" = "MIT" ]; then ok "license is MIT"; else bad "license is MIT (found '$(fm license)')"; fi
VERSION="$(fm metadata.version)"
if [[ "$VERSION" =~ ^\"[0-9]+\.[0-9]+\.[0-9]+\"$ ]]; then
    ok "metadata.version is a quoted version string ($VERSION)"
else
    bad "metadata.version is a quoted version string, such as \"0.1.0\" (found '$VERSION')"
fi

if cmp -s "$REPO_ROOT/LICENSE" "$PAYLOAD/LICENSE"; then
    ok "the payload's LICENSE equals the root one"
else
    bad "the payload's LICENSE equals the root one"
fi

echo ""
echo "=== The body says when to use the skill ==="
WHEN=$(awk '/^## When to use$/ {on=1; next} on && /^## / {exit} on' "$SKILL" 2>/dev/null)
if [ -n "$WHEN" ]; then ok "SKILL.md has a '## When to use' section"; else bad "SKILL.md has a '## When to use' section"; fi
# The trigger phrases sit in the description, which is all a host reads before choosing the skill.
for phrase in "AI visibility" "GEO" "AEO" "LLM reputation"; do
    if grep -qF "$phrase" <<<"$DESC"; then ok "the description names $phrase"; else bad "the description names $phrase"; fi
done
for phrase in "sentl-monitor adopt" "sentl-monitor report"; do
    if grep -qF "$phrase" <<<"$WHEN"; then ok "'When to use' names $phrase"; else bad "'When to use' names $phrase"; fi
done
# 'When to use' chooses the route; what each route does is the Routes table's, said once.
REPEATED=$(python3 - "$SKILL" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
when = re.search(r"^## When to use\n(.*?)(?=^## )", text, re.M | re.S)
routes = re.search(r"^## Routes\n(.*?)(?=^## )", text, re.M | re.S)
words = lambda s: re.findall(r"[a-z0-9<>/.-]+", s.lower())
grams = lambda ws: {" ".join(ws[i:i + 4]) for i in range(len(ws) - 3)}
cells = [row.split("|")[3] for row in (routes.group(1) if routes else "").splitlines()
         if row.startswith("| `") and row.count("|") >= 4]
when_grams = grams(words(when.group(1) if when else ""))
for cell in cells:
    for gram in sorted(grams(words(cell)) & when_grams):
        print(gram)
PY
)
if [ -z "$REPEATED" ]; then
    ok "'When to use' repeats no wording of the Routes table"
else
    bad "'When to use' repeats the Routes table: $(tr '\n' ';' <<<"$REPEATED")"
fi
FIRST_H2=$(grep -m1 '^## ' "$SKILL" 2>/dev/null)
if [ "$FIRST_H2" = "## When to use" ]; then ok "'When to use' is the body's first section"; else bad "'When to use' is the body's first section (first is '$FIRST_H2')"; fi

echo ""
echo "=== Router names the routes M1 ships ==="
# A route is named as `sentl-monitor <route>` or as a code span opening with
# the route; the dispatch path `adopt/ADOPT.md` alone does not count.
for route in adopt report; do
    has "sentl-monitor[[:space:]]+$route\\b|\`$route[\` ]" "$SKILL" "router names the '$route' route"
done

echo ""
echo "=== Router states that writes to Sentl need the operator's approval ==="
has 'approv' "$SKILL" "router requires the operator's approval for writes"

echo ""
echo "=== Every dispatched playbook exists ==="
TARGETS=$(grep -oE '`[a-z-]+/[A-Z][A-Z-]*\.md`' "$SKILL" 2>/dev/null | tr -d '`' | sort -u)
if [ -z "$TARGETS" ]; then
    bad "router dispatches to at least one playbook"
else
    for t in $TARGETS; do
        if [ -f "$PAYLOAD/$t" ]; then
            ok "dispatch target $t exists"
        else
            bad "dispatch target $t referenced by SKILL.md but missing on disk"
        fi
    done
fi
for t in adopt/ADOPT.md report/REPORT.md; do
    if grep -q "$t" <<<"$TARGETS"; then ok "router dispatches to $t"; else bad "router dispatches to $t"; fi
done

echo ""
echo "=== The report playbook ends at the period and goes on into the deck ==="
# The deck is the only thing the reader gets: REPORT.md runs nothing after `period` in its steps,
# and hands the period to DECK.md.
HANDOVER=$(python3 - "$PAYLOAD/report/REPORT.md" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
steps = text.split("\n## Redo the latest", 1)[0]
commands = [(m.start(), m.group(1)) for m in re.finditer(r"scripts/monitor\.py (\w+)", steps)]
print("yes" if commands and commands[-1][1] == "period" and steps.find("report/DECK.md", commands[-1][0]) > 0 else "no")
PY
)
if [ "$HANDOVER" = "yes" ]; then
    ok "REPORT.md ends its steps at period and hands over to report/DECK.md"
else
    bad "REPORT.md ends its steps at period and hands over to report/DECK.md"
fi
if [ -e "$PAYLOAD/report/INSIGHTS.md" ]; then
    bad "the long report's report/INSIGHTS.md is gone"
else
    ok "the long report's report/INSIGHTS.md is gone"
fi
for f in "$SKILL" "$PAYLOAD"/*/*.md; do
    if grep -qE 'monitor\.py (method|charts)|reports/D\.md|charts\.md|INSIGHTS\.md' "$f"; then
        bad "$(basename "$f") runs neither method nor charts and writes no long report"
    else
        ok "$(basename "$f") runs neither method nor charts and writes no long report"
    fi
done

echo ""
echo "=== The report playbook says how to redo the latest period of its date ==="
REDO=$(awk '/^## Redo the latest period/ {on=1; print; next} on && /^## / {exit} on' "$PAYLOAD/report/REPORT.md")
if [ -n "$REDO" ]; then ok "REPORT.md has a section on redoing the latest period"; else bad "REPORT.md has a section on redoing the latest period"; fi
for phrase in "monitor.py period" "monitor.py deck" "monitor.py check" "Keeps" "Rewrites" \
              "history/reports.json" "reports/D.deck.json"; do
    if grep -qF -- "$phrase" <<<"$REDO"; then ok "the redo section names $phrase"; else bad "the redo section names $phrase"; fi
done

echo ""
echo "=== The guide follows Sentl's MCP of 2026-10-29 ==="
has '^\| You want \| Route \|' "$SKILL" "SKILL.md holds the table of what the operator may want"
has 'error code|code and a message' "$SKILL" "SKILL.md tells the operator an error's code and message"
if grep -rqiE "cannot archive|no tool that archives" "$PAYLOAD" --include=*.md; then
    bad "no playbook says the MCP cannot archive"
else
    ok "no playbook says the MCP cannot archive"
fi
has 'archive-project-tool' "$PAYLOAD/setup/SETUP.md" "SETUP.md archives a project that is no longer needed"
has 'project_limit_reached' "$PAYLOAD/setup/SETUP.md" "SETUP.md handles the plan's project limit"
has 'create-snapshot-tool' "$PAYLOAD/snapshot/SNAPSHOT.md" "SNAPSHOT.md creates a snapshot, not a project"
has 'delete-snapshot-tool' "$PAYLOAD/snapshot/SNAPSHOT.md" "SNAPSHOT.md ends by deleting on the operator's go"

echo ""
echo "=== monitor.py --help ==="
# Captured before grepping: grep -q exits at the first match and the SIGPIPE
# it leaves would fail the command under pipefail.
if HELP_TEXT="$(python3 "$MONITOR" --help 2>&1)"; then
    ok "monitor.py --help exits 0"
else
    bad "monitor.py --help exits 0"
    echo "$HELP_TEXT" | sed 's/^/        /'
fi
echo ""
echo "=== Sentl's responses and errors (R2) ==="
has "5 a Sentl response" "$SKILL" "SKILL.md names exit 5: a Sentl response the skill cannot read"
has "6 unexpected error" "$SKILL" "SKILL.md names exit 6: an unexpected error"
for f in "$PAYLOAD/adopt/ADOPT.md" "$PAYLOAD/report/REPORT.md"; do
    has "monitor.py runs" "$f" "$(basename "$f") picks the runs with monitor.py runs"
    has '`internal`' "$f" "$(basename "$f") says what to do on Sentl's internal error"
    has '`not_found`' "$f" "$(basename "$f") says what to do on not_found"
    has '`invalid_argument`' "$f" "$(basename "$f") says what to do on invalid_argument"
    has "[Ee]xit 5" "$f" "$(basename "$f") says what to do on exit 5"
done
for status in queued pending researching running judging completed completed_with_warnings failed stalled; do
    has "\`$status\`" "$SKILL" "SKILL.md names the status $status"
done
for f in "$PAYLOAD/setup/SETUP.md" "$PAYLOAD/snapshot/SNAPSHOT.md"; do
    has '`not_found`' "$f" "$(basename "$f") says what to do on not_found"
    has '`invalid_argument`' "$f" "$(basename "$f") says what to do on invalid_argument"
done
has 'compare <folder> <folder>' "$SKILL" "SKILL.md routes compare"
has 'monitor.py compare' "$PAYLOAD/compare/COMPARE.md" "COMPARE.md runs compare"
has '`researching`' "$PAYLOAD/snapshot/SNAPSHOT.md" "SNAPSHOT.md follows a run in researching"
has '`judging`' "$PAYLOAD/snapshot/SNAPSHOT.md" "SNAPSHOT.md follows a run in judging"
has '`failed`' "$PAYLOAD/report/REPORT.md" "REPORT.md reads a failed run as final with no results"
has '`stalled`' "$PAYLOAD/report/REPORT.md" "REPORT.md reads a stalled run as final with no results"
has 'history/deck/D.notes.md' "$PAYLOAD/report/DECK.md" "DECK.md has the writer keep its notes on file"
has 'one section per command' "$PAYLOAD/report/DECK.md" "DECK.md has the writer write one section at a time"
has 'first draft' "$PAYLOAD/report/DECK.md" "DECK.md has the writer draft before opening answers and pages"
has 'Two readers in the whole session' "$PAYLOAD/report/DECK.md" "DECK.md stops at two readers, whatever changes after them"
has 'Two audits in the whole session' "$PAYLOAD/report/DECK.md" "DECK.md stops at two audits"
has 'ends on a deck that passes' "$PAYLOAD/report/DECK.md" "DECK.md has the session end on a passing deck"
if grep -q "has no paging" "$PAYLOAD/report/REPORT.md"; then
    bad "REPORT.md still says Sentl's listing has no paging"
else
    ok "REPORT.md reads the listing in pages"
fi
if grep -q "order the runs by \`started_at\`" "$PAYLOAD/report/REPORT.md"; then
    bad "REPORT.md still has the assistant order the runs by hand"
else
    ok "REPORT.md leaves the run selection to monitor.py runs"
fi

echo ""
echo "=== Hosts without a lasting folder (R3b) ==="
has "Hosts without a lasting folder" "$SKILL" "SKILL.md has the rule for hosts without a lasting folder"
# The rule, from its bold title to the next bullet: doctor first, unpack before the first
# command, pack after check, both files offered for download.
RULE=$(awk '/\*\*Hosts without a lasting folder/ {on=1} on && /^- \*\*/ && !/Hosts without a lasting folder/ {exit} on' "$SKILL" 2>/dev/null)
for word in "monitor.py doctor" "unpack" "monitor.py pack" "download"; do
    if grep -qF "$word" <<<"$RULE"; then ok "the rule names $word"; else bad "the rule names $word"; fi
done
# Positions in the rule: doctor, then unpack, then the deck's check, then pack.
ORDERED=$(python3 - "$RULE" <<'PY'
import sys
rule = sys.argv[1]
at = [rule.find(w) for w in ("doctor", "unpack", "check", "monitor.py pack")]
print("yes" if all(n >= 0 for n in at) and at == sorted(at) else "no")
PY
)
if [ "$ORDERED" = "yes" ]; then
    ok "the rule says doctor, then unpack, then pack after check"
else
    bad "the rule says doctor, then unpack, then pack after check"
fi
# In each playbook the first command run (`scripts/monitor.py <command>`, not a mention in prose)
# is doctor, in the section that opens the route (ADOPT §2, REPORT §1, DECK §1), the second is unpack,
# and pack comes after the command that closes the route: adopt in adopt, the deck's pdf in report
# and deck (REPORT.md ends in DECK.md).
playbook_order() {
    python3 - "$1" "$2" "$3" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
last, section = sys.argv[2], sys.argv[3]
commands = [(m.start(), m.group(1)) for m in re.finditer(r"scripts/monitor\.py (\w+)", text)]
opens = text.find(section)
nxt = text.find("\n## ", opens + 1)
names = [c for _, c in commands]
first_ok = names[:2] == ["doctor", "unpack"] and opens >= 0 and opens < commands[0][0] < (nxt if nxt >= 0 else len(text))
pack = [at for at, c in commands if c == "pack"]
closing = [at for at, c in commands if c == last]
last_ok = bool(pack) and bool(closing) and pack[0] > max(closing)
print(("doctor-unpack-first " if first_ok else "") + ("pack-last" if last_ok else ""))
PY
}
for spec in "adopt/ADOPT.md:adopt:## 2. Study folder" "report/DECK.md:pdf:## 1. Preflight"; do
    rel="${spec%%:*}"; rest="${spec#*:}"; closing="${rest%%:*}"; section="${rest#*:}"
    file="$PAYLOAD/$rel"; name="$(basename "$file")"
    found=$(playbook_order "$file" "$closing" "$section")
    if grep -q "doctor-unpack-first" <<<"$found"; then
        ok "$name runs monitor.py doctor first, in '$section', then monitor.py unpack"
    else
        bad "$name runs monitor.py doctor first, in '$section', then monitor.py unpack"
    fi
    if grep -q "pack-last" <<<"$found"; then
        ok "$name runs monitor.py pack after monitor.py $closing"
    else
        bad "$name runs monitor.py pack after monitor.py $closing"
    fi
    has "Hosts without a lasting folder|without a lasting folder" "$file" "$name says when the pack steps apply"
    if grep -qF "Project's files" "$file"; then
        ok "$name says to keep the latest pack in the Project's files"
    else
        bad "$name says to keep the latest pack in the Project's files"
    fi
done
if grep -q "doctor-unpack-first" <<<"$(playbook_order "$PAYLOAD/report/REPORT.md" check "## 1. Preflight")"; then
    ok "REPORT.md runs monitor.py doctor first, in '## 1. Preflight', then monitor.py unpack"
else
    bad "REPORT.md runs monitor.py doctor first, in '## 1. Preflight', then monitor.py unpack"
fi
# What the user keeps, and which pack to unpack.
for word in "PDF" "Project's files" "latest date" "keep"; do
    if grep -qF "$word" <<<"$RULE"; then ok "the rule names $word"; else bad "the rule names $word"; fi
done
has "pack's manifest" "$SKILL" "SKILL.md names exit 5 for a pack's manifest it cannot read"

echo ""
echo "=== monitor.py --help, commands ==="
for cmd in adopt detect runs ingest period check deck pdf doctor pack unpack resume close; do
    if grep -qw -- "$cmd" <<<"$HELP_TEXT"; then
        ok "--help lists the '$cmd' subcommand"
    else
        bad "--help lists the '$cmd' subcommand"
    fi
done
# The long report's commands are gone: a command is listed as an indented name at the start of a line.
for cmd in method charts; do
    if grep -qE "^ {4}$cmd( |$)" <<<"$HELP_TEXT"; then
        bad "--help lists no '$cmd' subcommand"
    else
        ok "--help lists no '$cmd' subcommand"
    fi
done

echo ""
echo "=== The setup playbook guards its writes ==="
SETUP_MD="$PAYLOAD/setup/SETUP.md"
has "setup/SETUP\\.md" "$SKILL" "SKILL.md dispatches to setup/SETUP.md"
has "dry_run: true" "$SETUP_MD" "SETUP.md saves with dry_run first"
has "delete_missing: true.*only|Only when they approve those deletions" "$SETUP_MD" "SETUP.md sends delete_missing only on the operator's approval"
has "explicit go" "$SETUP_MD" "SETUP.md asks for the operator's explicit go"
has "Recap table" "$SETUP_MD" "SETUP.md defines the recap table"
has "Models \\(credits\\)" "$SETUP_MD" "SETUP.md recap table has the models column with their credits"
has "Credits per 30 days" "$SETUP_MD" "SETUP.md recap table has the credits per 30 days column"
has "daily 30" "$SETUP_MD" "SETUP.md gives the runs in a 30-day cycle of a daily schedule"
has "weekly 30/7" "$SETUP_MD" "SETUP.md gives the runs in a 30-day cycle of a weekly schedule"
has "resets_at" "$SETUP_MD" "SETUP.md names the next reset"
if grep -rqiE "worst month|Judging adds" "$PAYLOAD" 2>/dev/null; then bad "the skill still has a worst month or says judging adds credits"; else ok "no worst month and no judging credits in the skill"; fi
ESTIMATE_LINE=$(grep -n "estimate-run-tool" "$SETUP_MD" | head -1 | cut -d: -f1)
TRIGGER_LINE=$(grep -n "trigger-run-tool" "$SETUP_MD" | tail -1 | cut -d: -f1)
if [ -n "$ESTIMATE_LINE" ] && [ -n "$TRIGGER_LINE" ] && [ "$ESTIMATE_LINE" -lt "$TRIGGER_LINE" ]; then
    ok "SETUP.md shows estimate-run-tool before it calls trigger-run-tool"
else
    bad "SETUP.md shows estimate-run-tool before it calls trigger-run-tool"
fi

echo ""
echo "=== The snapshot playbook guards its run ==="
SNAPSHOT_MD="$PAYLOAD/snapshot/SNAPSHOT.md"
has "snapshot/SNAPSHOT\\.md" "$SKILL" "SKILL.md dispatches to snapshot/SNAPSHOT.md"
has "dry_run: true" "$SNAPSHOT_MD" "SNAPSHOT.md saves with dry_run first"
has "explicit go" "$SNAPSHOT_MD" "SNAPSHOT.md asks for the operator's explicit go"
SNAPSHOT_ORDER=$(python3 - "$SNAPSHOT_MD" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
calls = [(m.start(), m.group(1)) for m in re.finditer(r"`(estimate-run-tool|trigger-run-tool)`", text)]
names = [name for _, name in calls]
if "trigger-run-tool" not in names or "estimate-run-tool" not in names:
    print("missing")
elif names.index("estimate-run-tool") > len(names) - 1 - names[::-1].index("trigger-run-tool"):
    print("trigger first")
else:
    # Each mention of trigger-run-tool sits in a paragraph that names the operator's go, or says nothing is started.
    bad = []
    for m in re.finditer(r"trigger-run-tool", text):
        para = text[text.rfind("\n\n", 0, m.start()) + 2:text.find("\n\n", m.end())]
        if not re.search(r"\bgo\b|starts nothing|start nothing|do not call", para):
            bad.append(para[:60])
    print("ungated: " + "; ".join(bad) if bad else "ok")
PY
)
if [ "$SNAPSHOT_ORDER" = "ok" ]; then
    ok "SNAPSHOT.md shows estimate-run-tool before it calls trigger-run-tool, and calls it only on the operator's go"
else
    bad "SNAPSHOT.md shows estimate-run-tool before trigger-run-tool and gates trigger-run-tool on the go ($SNAPSHOT_ORDER)"
fi
has "update-project-settings-tool" "$SNAPSHOT_MD" "SNAPSHOT.md pauses the project"
has "monitor\\.py close" "$SNAPSHOT_MD" "SNAPSHOT.md records the closing with monitor.py close"
has "monitor\\.py resume" "$SNAPSHOT_MD" "SNAPSHOT.md resumes with monitor.py resume"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
