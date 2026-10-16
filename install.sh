#!/usr/bin/env bash
# Copy the sentl-monitor payload into the assistant's skills directories:
# Claude Code always, opencode when ~/.config/opencode exists.
#
# The skill reaches Sentl through its MCP server, which the assistant
# connects and authenticates. This script needs no key and stores none.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/sentl-monitor"
FORCE=false
CHECK=false
DESTS=()

usage() {
    cat <<'EOF'
Usage: install.sh [--force] [--check] [--dest <dir>]

  --force        overwrite an existing install without asking
  --check        compare the installed copy with the repository; no writes
                 (prints OK and exits 0, or DRIFT and exits 1)
  --dest <dir>   install to exactly <dir>; without it the skill goes to
                 ~/.claude/skills/sentl-monitor and, when ~/.config/opencode
                 exists, to ~/.config/opencode/skills/sentl-monitor
  --help         show this message

The skill needs the Sentl MCP server connected to the assistant:
https://app.sentl.ai/mcp/setup
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --force) FORCE=true; shift ;;
        --check) CHECK=true; shift ;;
        --dest)
            [ $# -ge 2 ] || { echo "Error: --dest needs a directory" >&2; exit 64; }
            DESTS=("$2"); shift 2 ;;
        --dest=*) DESTS=("${1#--dest=}"); shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

[ -d "$SRC" ] || { echo "Error: payload not found at $SRC" >&2; exit 1; }

if [ ${#DESTS[@]} -eq 0 ]; then
    DESTS=("$HOME/.claude/skills/sentl-monitor")
    if [ -d "$HOME/.config/opencode" ]; then
        DESTS+=("$HOME/.config/opencode/skills/sentl-monitor")
    fi
fi

# Running the tests byte-compiles the scripts in place; those caches are not payload.
DIFF_EXCLUDES=(--exclude=__pycache__ --exclude='*.pyc')

if [ "$CHECK" = true ]; then
    STATUS=0
    for dest in "${DESTS[@]}"; do
        if [ ! -d "$dest" ]; then
            echo "DRIFT: not installed at $dest"
            STATUS=1
        elif diff -r "${DIFF_EXCLUDES[@]}" "$SRC" "$dest" >/dev/null 2>&1; then
            echo "OK: $dest matches the repository"
        else
            echo "DRIFT: $dest differs from the repository"
            diff -r "${DIFF_EXCLUDES[@]}" "$SRC" "$dest" || true
            STATUS=1
        fi
    done
    exit "$STATUS"
fi

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    echo "Error: the skill's scripts need python3 3.10 or later on PATH" >&2
    exit 1
fi

# Without a terminal there is nobody to ask, so refuse before writing anywhere.
if [ "$FORCE" != true ] && [ ! -t 0 ]; then
    for dest in "${DESTS[@]}"; do
        if [ -d "$dest" ]; then
            echo "Already installed at $dest; pass --force to overwrite." >&2
            exit 1
        fi
    done
fi

# An install replaces its destination with rm -rf, so a destination that holds anything
# other than an earlier sentl-monitor install is refused before any write.
for dest in "${DESTS[@]}"; do
    if [ -d "$dest" ] && [ -n "$(ls -A "$dest")" ] && ! grep -qs '^name: sentl-monitor$' "$dest/SKILL.md"; then
        echo "Error: $dest is not empty and is not a sentl-monitor install; choose another --dest." >&2
        exit 1
    fi
done

for dest in "${DESTS[@]}"; do
    if [ -d "$dest" ] && [ "$FORCE" != true ]; then
        printf 'Target already exists: %s\nOverwrite? [y/N] ' "$dest"
        read -r reply || reply=""
        case "$reply" in [yY]*) ;; *) echo "Skipped $dest."; continue ;; esac
    fi

    mkdir -p "$(dirname "$dest")"
    rm -rf "$dest"
    cp -R "$SRC" "$dest"
    find "$dest" -type d -name '__pycache__' -prune -exec rm -rf {} +
    find "$dest" -type f -name '*.pyc' -delete
    echo "Installed sentl-monitor to $dest"
done

echo "Connect the Sentl MCP server to your assistant before the first run: https://app.sentl.ai/mcp/setup"
