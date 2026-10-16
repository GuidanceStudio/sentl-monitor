#!/usr/bin/env bash
set -uo pipefail

# Contract tests for the router SKILL.md and the monitor.py entry point.
#
# Every playbook path the router dispatches to must exist on disk. The router
# grows one route per milestone, so this holds at every commit without
# placeholder files for routes not built yet.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="$REPO_ROOT/sentl-monitor"
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
    bad "sentl-monitor/SKILL.md missing; every check below reads it"
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

# The agentskills.io spec caps compatibility at 500 characters.
COMPAT_LEN=$(python3 - "$SKILL" <<'PY' 2>/dev/null
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
if not m:
    print(-1); raise SystemExit
value, grabbing = [], False
for line in m.group(1).split("\n"):
    if line.startswith("compatibility:"):
        grabbing = True
        value.append(line.split(":", 1)[1].strip().lstrip(">|-").strip())
        continue
    if grabbing:
        if re.match(r"^[A-Za-z_]+:", line):
            break
        value.append(line.strip())
print(len(" ".join(v for v in value if v)))
PY
)
COMPAT_LEN="${COMPAT_LEN:--1}"
if [ "$COMPAT_LEN" -gt 0 ] && [ "$COMPAT_LEN" -le 500 ]; then
    ok "compatibility is $COMPAT_LEN chars (<= 500)"
else
    bad "compatibility is $COMPAT_LEN chars (must be 1..500)"
fi

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
echo "=== monitor.py --help ==="
# Captured before grepping: grep -q exits at the first match and the SIGPIPE
# it leaves would fail the command under pipefail.
if HELP_TEXT="$(python3 "$MONITOR" --help 2>&1)"; then
    ok "monitor.py --help exits 0"
else
    bad "monitor.py --help exits 0"
    echo "$HELP_TEXT" | sed 's/^/        /'
fi
for cmd in adopt detect ingest period method check; do
    if grep -qw -- "$cmd" <<<"$HELP_TEXT"; then
        ok "--help lists the '$cmd' subcommand"
    else
        bad "--help lists the '$cmd' subcommand"
    fi
done

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
