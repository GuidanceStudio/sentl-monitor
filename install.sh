#!/usr/bin/env bash
# Copy the sentl-monitor payload into the skills directories the assistants read:
# ~/.claude/skills for Claude Code, ~/.agents/skills for Codex and opencode.
#
# The skill reaches Sentl through its MCP server, which the assistant
# connects and authenticates. This script needs no key and stores none.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/skills/sentl-monitor"
CLAUDE_DIR="$HOME/.claude/skills/sentl-monitor"
AGENTS_DIR="$HOME/.agents/skills/sentl-monitor"
# opencode reads ~/.claude/skills and ~/.agents/skills, so a copy here is an older one it would
# read besides the current one.
LEGACY_DIR="$HOME/.config/opencode/skills/sentl-monitor"

FORCE=false
CHECK=false
UNINSTALL=false
DEST=""
HOSTS=()

usage() {
    cat <<'EOF'
Usage: install.sh [--host claude|agents]... [--dest <dir>] [--check | --uninstall] [--force]

  --host claude   install to ~/.claude/skills/sentl-monitor (Claude Code; opencode reads it too)
  --host agents   install to ~/.agents/skills/sentl-monitor (Codex and opencode);
                  --host codex and --host opencode mean the same
                  Without --host or --dest, the script installs for every host it detects:
                  ~/.claude means claude; ~/.codex, ~/.config/opencode, or codex or opencode
                  on PATH means agents. With none detected it refuses.
  --dest <dir>    install to exactly <dir>
  --check         compare each install with the repository and print its version; no writes
                  (exits 0 when every install checked matches, 1 otherwise)
  --uninstall     remove sentl-monitor from ~/.claude/skills, ~/.agents/skills and
                  ~/.config/opencode/skills, or from the --host or --dest given; nothing else
  --force         overwrite or remove without asking
  --help          show this message

An older copy in ~/.config/opencode/skills/sentl-monitor is removed when the skill is installed
for a host, after a prompt (--force without a terminal).

The skill needs the Sentl MCP server connected to the assistant:
https://app.sentl.ai/mcp/setup
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --force) FORCE=true; shift ;;
        --check) CHECK=true; shift ;;
        --uninstall) UNINSTALL=true; shift ;;
        --host)
            [ $# -ge 2 ] || { echo "Error: --host needs claude or agents" >&2; exit 64; }
            HOSTS+=("$2"); shift 2 ;;
        --host=*) HOSTS+=("${1#--host=}"); shift ;;
        --dest)
            [ $# -ge 2 ] || { echo "Error: --dest needs a directory" >&2; exit 64; }
            DEST="$2"; shift 2 ;;
        --dest=*) DEST="${1#--dest=}"; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 64 ;;
    esac
done

if [ "$CHECK" = true ] && [ "$UNINSTALL" = true ]; then
    echo "Error: choose --check or --uninstall, not both" >&2; exit 64
fi
if [ -n "$DEST" ] && [ ${#HOSTS[@]} -gt 0 ]; then
    echo "Error: choose --host or --dest, not both" >&2; exit 64
fi

host_dir() {
    case "$1" in
        claude) echo "$CLAUDE_DIR" ;;
        agents|codex|opencode) echo "$AGENTS_DIR" ;;
        *) return 1 ;;
    esac
}

is_install() { grep -qs '^name: sentl-monitor$' "$1/SKILL.md"; }

# The metadata.version an installed copy's SKILL.md declares, or "unknown".
version_of() {
    local v
    v="$(awk 'NR == 1 && $0 != "---" { exit }
              NR > 1 && $0 == "---" { exit }
              /^metadata:/ { m = 1; next }
              m && /^[^ ]/ { m = 0 }
              m && /^ +version:/ { sub(/^ +version: */, ""); gsub(/["'\'']/, ""); print; exit }' \
          "$1/SKILL.md" 2>/dev/null || true)"
    echo "${v:-unknown}"
}

# Running the tests byte-compiles the scripts in place; those caches are not payload.
DIFF_EXCLUDES=(--exclude=__pycache__ --exclude='*.pyc')
matches() { diff -r "${DIFF_EXCLUDES[@]}" "$SRC" "$1" >/dev/null 2>&1; }

contains() {
    local item="$1"; shift
    local x
    for x in "$@"; do [ "$x" = "$item" ] && return 0; done
    return 1
}

[ -d "$SRC" ] || { echo "Error: payload not found at $SRC" >&2; exit 1; }

# `path` with its symbolic links resolved. For a path that does not exist yet, its nearest
# existing parent is resolved and the rest appended.
physical() {
    local path="$1" rest="" base
    case "$path" in /*) ;; *) path="$PWD/$path" ;; esac
    while [ ! -d "$path" ]; do
        rest="/$(basename "$path")$rest"
        path="$(dirname "$path")"
    done
    base="$(cd -P "$path" && pwd -P)"
    [ "$base" = "/" ] && base=""
    printf '%s%s\n' "$base" "$rest"
}
SRC_REAL="$(physical "$SRC")"

# Removing or replacing a folder that is the payload, holds it or lies inside it would delete
# the repository's copy of the skill, whatever links lead there.
refuse_payload() {
    local real
    real="$(physical "$1")"
    case "$real/" in "$SRC_REAL/"*) ;; *) case "$SRC_REAL/" in "$real/"*) ;; *) return 0 ;; esac ;; esac
    echo "Error: $1 is, holds or lies inside this repository's payload ($SRC_REAL); choose another folder." >&2
    exit 1
}

# The directories this run acts on.
TARGETS=()
DETECTED=false
if [ -n "$DEST" ]; then
    TARGETS=("$DEST")
elif [ ${#HOSTS[@]} -gt 0 ]; then
    for host in "${HOSTS[@]}"; do
        dir="$(host_dir "$host")" || { echo "Error: unknown host '$host'; use --host claude or --host agents" >&2; exit 64; }
        contains "$dir" ${TARGETS[@]+"${TARGETS[@]}"} || TARGETS+=("$dir")
    done
else
    DETECTED=true
    if [ -d "$HOME/.claude" ]; then TARGETS+=("$CLAUDE_DIR"); fi
    if [ -d "$HOME/.codex" ] || [ -d "$HOME/.config/opencode" ] \
        || command -v codex >/dev/null 2>&1 || command -v opencode >/dev/null 2>&1; then
        TARGETS+=("$AGENTS_DIR")
    fi
fi

# Without a terminal there is nobody to ask: refuse before writing or removing anything.
ask() {
    local question="$1" reply
    if [ "$FORCE" = true ]; then return 0; fi
    printf '%s [y/N] ' "$question"
    read -r reply || reply=""
    case "$reply" in [yY]*) return 0 ;; *) return 1 ;; esac
}
INTERACTIVE=false
if [ -t 0 ]; then INTERACTIVE=true; fi

if [ "$CHECK" = true ]; then
    STATUS=0
    for dest in ${TARGETS[@]+"${TARGETS[@]}"}; do
        if [ ! -d "$dest" ]; then
            echo "DRIFT: not installed at $dest"
            STATUS=1
        elif matches "$dest"; then
            echo "OK: $dest matches the repository (version $(version_of "$dest"))"
        else
            echo "DRIFT: $dest differs from the repository (version $(version_of "$dest"))"
            diff -r "${DIFF_EXCLUDES[@]}" "$SRC" "$dest" || true
            STATUS=1
        fi
    done
    FOUND=${#TARGETS[@]}
    for dir in "$CLAUDE_DIR" "$AGENTS_DIR" "$LEGACY_DIR"; do
        if contains "$dir" ${TARGETS[@]+"${TARGETS[@]}"} || ! is_install "$dir"; then continue; fi
        FOUND=$((FOUND + 1))
        if [ "$dir" = "$LEGACY_DIR" ]; then
            echo "DRIFT: an older copy at $dir (version $(version_of "$dir")); opencode reads it besides the current one. Run ./install.sh to remove it."
            STATUS=1
        elif matches "$dir"; then
            echo "Also installed: $dir (version $(version_of "$dir"), matches the repository)"
        else
            echo "Also installed: $dir (version $(version_of "$dir"), differs from the repository)"
        fi
    done
    if [ "$FOUND" -eq 0 ]; then
        echo "DRIFT: no sentl-monitor install found, and no host detected"
        STATUS=1
    fi
    exit "$STATUS"
fi

if [ "$UNINSTALL" = true ]; then
    if [ -n "$DEST" ] || [ ${#HOSTS[@]} -gt 0 ]; then
        CANDIDATES=("${TARGETS[@]}")
    else
        CANDIDATES=("$CLAUDE_DIR" "$AGENTS_DIR" "$LEGACY_DIR")
    fi
    REMOVE=()
    STATUS=0
    for dir in "${CANDIDATES[@]}"; do
        if [ ! -e "$dir" ]; then continue; fi
        if is_install "$dir"; then
            REMOVE+=("$dir")
        else
            echo "Left alone: $dir is not a sentl-monitor install." >&2
            STATUS=1
        fi
    done
    if [ ${#REMOVE[@]} -eq 0 ]; then
        [ "$STATUS" -eq 0 ] && echo "No sentl-monitor install found."
        exit "$STATUS"
    fi
    for dir in "${REMOVE[@]}"; do refuse_payload "$dir"; done
    if [ "$FORCE" != true ] && [ "$INTERACTIVE" != true ]; then
        echo "Would remove: ${REMOVE[*]}; pass --force to remove without a terminal." >&2
        exit 1
    fi
    for dir in "${REMOVE[@]}"; do
        if ask "Remove $dir?"; then
            rm -rf "$dir"
            echo "Removed $dir"
        else
            echo "Kept $dir"
        fi
    done
    exit "$STATUS"
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
    cat >&2 <<'EOF'
Error: no assistant detected (no ~/.claude, ~/.codex or ~/.config/opencode, and no codex or
opencode on PATH). Name where to install:
  ./install.sh --host claude    Claude Code, ~/.claude/skills
  ./install.sh --host agents    Codex and opencode, ~/.agents/skills
  ./install.sh --dest <dir>     exactly <dir>
EOF
    exit 1
fi

# An install replaces each target with rm -rf and cp, so a file, a link to one, a dangling link
# or the payload itself is refused before any write.
for dest in "${TARGETS[@]}"; do
    if { [ -e "$dest" ] || [ -L "$dest" ]; } && [ ! -d "$dest" ]; then
        echo "Error: $dest exists and is not a folder; choose another --dest." >&2
        exit 1
    fi
    refuse_payload "$dest"
done

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    echo "Error: the skill's scripts need python3 3.10 or later on PATH" >&2
    exit 1
fi

# The older opencode copy goes when the skill is installed for a host, not to a --dest.
REMOVE_LEGACY=false
if [ -z "$DEST" ] && is_install "$LEGACY_DIR"; then
    REMOVE_LEGACY=true
    refuse_payload "$LEGACY_DIR"
fi

if [ "$FORCE" != true ] && [ "$INTERACTIVE" != true ]; then
    for dest in "${TARGETS[@]}"; do
        if [ -d "$dest" ]; then
            echo "Already installed at $dest; pass --force to overwrite." >&2
            exit 1
        fi
    done
    if [ "$REMOVE_LEGACY" = true ]; then
        echo "An older copy is installed at $LEGACY_DIR, which opencode reads besides the new one; pass --force to remove it and install." >&2
        exit 1
    fi
fi

# An install replaces its destination with rm -rf, so a destination that holds anything
# other than an earlier sentl-monitor install is refused before any write.
for dest in "${TARGETS[@]}"; do
    if [ -d "$dest" ] && [ -n "$(ls -A "$dest")" ] && ! is_install "$dest"; then
        echo "Error: $dest is not empty and is not a sentl-monitor install; choose another --dest." >&2
        exit 1
    fi
done

if [ "$DETECTED" = true ]; then
    echo "Hosts detected: installing to ${TARGETS[*]}"
fi

for dest in "${TARGETS[@]}"; do
    if [ -d "$dest" ] && ! ask "Target already exists: $dest
Overwrite?"; then
        echo "Skipped $dest."
        continue
    fi
    mkdir -p "$(dirname "$dest")"
    rm -rf "$dest"
    cp -R "$SRC" "$dest"
    find "$dest" -type d -name '__pycache__' -prune -exec rm -rf {} +
    find "$dest" -type f -name '*.pyc' -delete
    echo "Installed sentl-monitor $(version_of "$dest") to $dest"
done

if [ "$REMOVE_LEGACY" = true ]; then
    if ask "An older copy is installed at $LEGACY_DIR, which opencode reads besides the new one. Remove it?"; then
        rm -rf "$LEGACY_DIR"
        echo "Removed the older copy at $LEGACY_DIR"
    else
        echo "Kept the older copy at $LEGACY_DIR"
    fi
fi

echo "Connect the Sentl MCP server to your assistant before the first run: https://app.sentl.ai/mcp/setup"
