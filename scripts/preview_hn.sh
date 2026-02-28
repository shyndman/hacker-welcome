#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/hacker-welcome"
CACHE_FILE="$CACHE_DIR/top5.json"

/usr/bin/env python3 "$PROJECT_ROOT/scripts/hacker_welcome_refresh.py" --cache "$CACHE_FILE" --count 5

PLUGIN_FILE="$PROJECT_ROOT/hacker-welcome.plugin.zsh" CACHE_FILE="$CACHE_FILE" \
  /usr/bin/env zsh -fic 'cd "$HOME"; source "$PLUGIN_FILE"; HW_CACHE_FILE="$CACHE_FILE"; HW_SHOW_INTERVAL=0; hw::preview_banner'
