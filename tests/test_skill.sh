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
echo "=== The report playbook points to the insights ==="
has 'INSIGHTS\.md' "$PAYLOAD/report/REPORT.md" "REPORT.md points the writer to report/INSIGHTS.md"
has "goes in the findings entry of its dimension" "$PAYLOAD/report/INSIGHTS.md" "INSIGHTS.md puts every insight in its dimension's findings entry"
if grep -qiE "or in the changes section" "$PAYLOAD/report/INSIGHTS.md"; then
    bad "INSIGHTS.md offers the changes section instead of the findings entry"
else
    ok "INSIGHTS.md never offers the changes section instead of the findings entry"
fi
has "«" "$PAYLOAD/report/INSIGHTS.md" "INSIGHTS.md tells the writer to quote a fact term in «»"
for f in "$PAYLOAD/report/REPORT.md" "$REPO_ROOT/ARCHITECTURE.md"; do
    has "the subject's own first, then the most cited, five in all" "$f" \
        "$(basename "$f") lists the domains after the excerpts as the subject's own first, then the most cited"
done
INSIGHT_LINE=$(grep -n "The insights the material prints" "$PAYLOAD/report/REPORT.md" | head -1 | cut -d: -f1)
CLIENT_LINE=$(grep -n "One line on what it means for the client" "$PAYLOAD/report/REPORT.md" | head -1 | cut -d: -f1)
if [ -n "$INSIGHT_LINE" ] && [ -n "$CLIENT_LINE" ] && [ "$INSIGHT_LINE" -lt "$CLIENT_LINE" ]; then
    ok "REPORT.md step 7 puts the insights before the line for the client"
else
    bad "REPORT.md step 7 puts the insights before the line for the client"
fi
has "summary is written last" "$PAYLOAD/report/REPORT.md" "REPORT.md writes the summary last, from the findings and changes"
has "In short|summary" "$REPO_ROOT/ARCHITECTURE.md" "ARCHITECTURE.md names the summary section"
has "five domains cited by most answers of the group" "$PAYLOAD/report/INSIGHTS.md" \
    "INSIGHTS.md states the sources rule as the five domains cited most in each group"
if grep -qE "at least 10 points apart|at least five of the two groups" "$PAYLOAD/report/INSIGHTS.md"; then
    bad "INSIGHTS.md still states the thresholds of the earlier rule"
else
    ok "INSIGHTS.md states no threshold of the earlier rule"
fi
for insight in "Fact currency" "Sources behind" "Readings" "Episodes" "Presence by run" "Missing evidence" \
               "Who wrote the sources" "Presence changes"; do
    has "^## $insight" "$PAYLOAD/report/INSIGHTS.md" "INSIGHTS.md has an entry for $insight"
done

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
    has "An internal server error occurred" "$f" "$(basename "$f") says what to do on Sentl's internal error"
    has "[Ee]xit 5" "$f" "$(basename "$f") says what to do on exit 5"
done
if grep -q "order the runs by \`started_at\`" "$PAYLOAD/report/REPORT.md"; then
    bad "REPORT.md still has the assistant order the runs by hand"
else
    ok "REPORT.md leaves the run selection to monitor.py runs"
fi

echo ""
echo "=== monitor.py --help, commands ==="
for cmd in adopt detect runs ingest period method check charts doctor; do
    if grep -qw -- "$cmd" <<<"$HELP_TEXT"; then
        ok "--help lists the '$cmd' subcommand"
    else
        bad "--help lists the '$cmd' subcommand"
    fi
done

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
