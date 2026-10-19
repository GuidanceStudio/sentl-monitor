#!/usr/bin/env bash
set -uo pipefail

# Verifies the repository layout: dev-tree files at the root, the installable
# payload in the nested sentl-monitor/ folder, and scripts that import only
# the standard library.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="$REPO_ROOT/sentl-monitor"
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
assert_ignored "sentl-monitor/scripts/__pycache__/probe.pyc"

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
assert_dir "sentl-monitor"
assert_nonempty "sentl-monitor/SKILL.md"
assert_nonempty "sentl-monitor/adopt/ADOPT.md"
assert_nonempty "sentl-monitor/report/REPORT.md"
assert_nonempty "sentl-monitor/report/INSIGHTS.md"
assert_nonempty "sentl-monitor/scripts/monitor.py"
assert_dir "sentl-monitor/scripts/sentlmon"
assert_file "sentl-monitor/scripts/sentlmon/__init__.py"

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
    bad "import scan needs sentl-monitor/scripts/monitor.py"
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
