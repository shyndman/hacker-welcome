# Hacker Welcome Plugin

if [[ -n ${HACKER_WELCOME_LOADED:-} ]]; then
  return
fi
typeset -g HACKER_WELCOME_LOADED=1

setopt local_options no_prompt_subst
typeset -g HW_PLUGIN_FILE="${${(%):-%N}}"
typeset -g HW_PLUGIN_DIR="${HW_PLUGIN_FILE:A:h}"
typeset -g HW_PROJECT_ROOT="$HW_PLUGIN_DIR"
typeset -g HW_REFRESH_SCRIPT="$HW_PROJECT_ROOT/scripts/hacker_welcome_refresh.py"
typeset -g HW_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/hacker-welcome"
typeset -g HW_CACHE_FILE="$HW_CACHE_DIR/top5.json"
typeset -g HW_LOG_FILE="$HW_CACHE_DIR/refresh.log"
typeset -g HW_CRON_TAG="# hacker-welcome refresh"
typeset -g HW_SENTINEL="$HW_CACHE_DIR/.cron-installed"
typeset -gi HW_SETUP_DONE=0

hw::_repeat() {
  local char=$1 count=$2
  if (( count <= 0 )); then
    REPLY=""
    return
  fi
  REPLY=$(printf '%*s' "$count" "" | tr ' ' "$char")
}

hw::_truncate() {
  local text="$1"
  local limit=$2
  [[ -z $text ]] && text="(untitled)"
  if (( limit <= 0 )); then
    REPLY=""
    return
  fi
  local len=${#text}
  if (( len <= limit )); then
    REPLY="$text"
  else
    local cut=$((limit-1))
    (( cut < 1 )) && cut=1
    REPLY="${text[1,$cut]}…"
  fi
}

hw::_cron_line() {
  print -r -- "*/15 * * * * /usr/bin/env python3 ${(q)HW_REFRESH_SCRIPT} --cache ${(q)HW_CACHE_FILE} >> ${(q)HW_LOG_FILE} 2>&1 ${HW_CRON_TAG}"
}

hw::_install_cron_if_needed() {
  local existing line cron_status
  existing=$(crontab -l 2>/dev/null)
  cron_status=$?
  line=$(hw::_cron_line)
  if (( cron_status == 0 )) && [[ $existing == *${HW_CRON_TAG}* ]]; then
    return
  fi
  if (( cron_status == 0 )) && [[ -n $existing ]]; then
    { print -r -- "$existing"; print -r -- "$line"; } | crontab -
  else
    print -r -- "$line" | crontab -
  fi
  : >| "$HW_SENTINEL"
}

hw::_refresh_cache() {
  command -v python3 >/dev/null 2>&1 || return
  /usr/bin/env python3 "$HW_REFRESH_SCRIPT" --cache "$HW_CACHE_FILE" --count 5 >/dev/null 2>&1
}

hw::_ensure_setup() {
  (( HW_SETUP_DONE )) && return
  command -v python3 >/dev/null 2>&1 || return
  mkdir -p "$HW_CACHE_DIR" 2>/dev/null
  [[ -x $HW_REFRESH_SCRIPT ]] || chmod +x "$HW_REFRESH_SCRIPT" 2>/dev/null
  hw::_install_cron_if_needed
  hw::_refresh_cache
  HW_SETUP_DONE=1
}

hw::_load_lines() {
  [[ -s $HW_CACHE_FILE ]] || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  /usr/bin/env python3 - "$HW_CACHE_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    sys.exit(1)
for idx, entry in enumerate(data[:5], start=1):
    rank = entry.get("rank") or idx
    title = entry.get("title") or "(untitled)"
    score = entry.get("score") or 0
    author = entry.get("author") or "unknown"
    print(f"{rank}|{title}|{score}|{author}")
PY
}

hw::_format_entry() {
  local cols=$1 line="$2"
  local inner=$((cols - 2))
  local content_width=$((inner - 2))
  (( content_width < 10 )) && content_width=10
  local -a parts
  parts=(${(@s/|/)line})
  local rank=${parts[1]:-?}
  local title=${parts[2]:-"(untitled)"}
  local score=${parts[3]:-0}
  local author=${parts[4]:-unknown}
  local label="${rank}. ${title}"
  local meta=""
  if (( content_width >= 32 )); then
    meta="[$score pts | by $author]"
  elif (( content_width >= 20 )); then
    meta="[$score pts]"
  fi
  local title_space=$content_width
  if [[ -n $meta ]]; then
    title_space=$((content_width - ${#meta} - 1))
  fi
  (( title_space < 4 )) && title_space=4
  hw::_truncate "$label" $title_space
  local truncated=$REPLY
  local line_text="$truncated"
  if [[ -n $meta ]]; then
    local gap=$((content_width - ${#truncated} - ${#meta}))
    (( gap < 1 )) && gap=1
    hw::_repeat " " $gap; local pad=$REPLY
    line_text+="$pad$meta"
  else
    hw::_repeat " " $((content_width - ${#truncated}))
    line_text+="$REPLY"
  fi
  REPLY="│ ${line_text} │"
}

hw::_format_header() {
  local cols=$1
  local inner=$((cols - 2))
  local content_width=$((inner - 2))
  local label=" TOP HACKER NEWS "
  if (( ${#label} > content_width )); then
    hw::_truncate "$label" $content_width
    label=" $REPLY "
  fi
  local padding=$((content_width - ${#label}))
  (( padding < 0 )) && padding=0
  local left=$((padding / 2))
  local right=$((padding - left))
  hw::_repeat " " $left; local left_pad=$REPLY
  hw::_repeat " " $right; local right_pad=$REPLY
  REPLY="│ ${left_pad}${label}${right_pad} │"
}

hw::print_banner() {
  [[ -o interactive ]] || return
  [[ -t 1 ]] || return
  if [[ ${PWD:A} != ${HOME:A} ]]; then
    return
  fi

  hw::_ensure_setup

  local cols=${COLUMNS:-$(command tput cols 2>/dev/null || print 80)}
  (( cols >= 32 )) || return
  local inner=$((cols - 2))
  local border_color="%F{6}"
  local text_color="%F{15}"
  local accent_color="%F{3}"
  local reset="%f"
  local lines_output
  if ! lines_output=$(hw::_load_lines); then
    print -P "${accent_color}Hacker News cache unavailable; updating soon.${reset}"
    return
  fi

  hw::_repeat "─" $inner; local horiz=$REPLY
  print -P "${border_color}┌${horiz}┐${reset}"
  hw::_format_header $cols; local header_line=$REPLY
  print -P "${border_color}${header_line}${reset}"
  hw::_repeat "─" $inner; local divider=$REPLY
  print -P "${border_color}├${divider}┤${reset}"

  local line entry_line
  while IFS= read -r line; do
    [[ -z $line ]] && continue
    hw::_format_entry $cols "$line"; entry_line=$REPLY
    print -P "${text_color}${entry_line}${reset}"
  done <<< "$lines_output"

  hw::_repeat "─" $inner; horiz=$REPLY
  print -P "${border_color}└${horiz}┘${reset}"
}

autoload -Uz add-zsh-hook 2>/dev/null

hw::_print_banner_once() {
  add-zsh-hook -d precmd hw::_print_banner_once 2>/dev/null
  hw::print_banner
}

if (( ${+functions[add-zsh-hook]} )); then
  add-zsh-hook precmd hw::_print_banner_once
else
  hw::print_banner
fi
