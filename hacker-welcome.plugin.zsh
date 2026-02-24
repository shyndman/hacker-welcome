# Hacker Welcome Plugin

if [[ -n ${HACKER_WELCOME_LOADED:-} ]]; then
  return
fi
typeset -g HACKER_WELCOME_LOADED=1

setopt local_options no_prompt_subst
zmodload zsh/datetime 2>/dev/null
typeset -g HW_PLUGIN_FILE="${${(%):-%N}}"
typeset -g HW_PLUGIN_DIR="${HW_PLUGIN_FILE:A:h}"
typeset -g HW_PROJECT_ROOT="$HW_PLUGIN_DIR"
typeset -g HW_REFRESH_SCRIPT="$HW_PROJECT_ROOT/scripts/hacker_welcome_refresh.py"
typeset -g HW_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/hacker-welcome"
typeset -g HW_CACHE_FILE="$HW_CACHE_DIR/top5.json"
typeset -g HW_LOG_FILE="$HW_CACHE_DIR/refresh.log"
typeset -g HW_CRON_TAG="# hacker-welcome refresh"
typeset -g HW_SENTINEL="$HW_CACHE_DIR/.cron-installed"
typeset -g HW_STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/hacker-welcome"
typeset -g HW_LAST_SHOWN_FILE="$HW_STATE_DIR/last-shown"
typeset -gi HW_SHOW_INTERVAL=$((4*60*60))
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
  mkdir -p "$HW_STATE_DIR" 2>/dev/null
  [[ -x $HW_REFRESH_SCRIPT ]] || chmod +x "$HW_REFRESH_SCRIPT" 2>/dev/null
  hw::_install_cron_if_needed
  hw::_refresh_cache
  HW_SETUP_DONE=1
}

hw::_banner_recently_shown() {
  local interval=$1
  (( interval > 0 )) || return 1
  local now=$EPOCHSECONDS
  local last=0
  if [[ -s $HW_LAST_SHOWN_FILE ]]; then
    local raw
    if read -r raw < "$HW_LAST_SHOWN_FILE" 2>/dev/null; then
      [[ $raw == <-> ]] && last=$raw
    fi
  elif [[ -f $HW_LAST_SHOWN_FILE ]]; then
    local mtime
    if mtime=$(command stat -f %m -- "$HW_LAST_SHOWN_FILE" 2>/dev/null); then
      last=$mtime
    elif mtime=$(command stat -c %Y -- "$HW_LAST_SHOWN_FILE" 2>/dev/null); then
      last=$mtime
    fi
  fi
  (( last > 0 )) || return 1
  local elapsed=$((now - last))
  (( elapsed < 0 )) && elapsed=0
  (( elapsed < interval ))
}

hw::_record_banner_shown() {
  local now=$EPOCHSECONDS
  mkdir -p "$HW_STATE_DIR" 2>/dev/null
  print -r -- "$now" >| "$HW_LAST_SHOWN_FILE" 2>/dev/null
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
    url = entry.get("url") or entry.get("hn_discussion") or ""
    discussion = entry.get("hn_discussion") or ""
    print("\t".join(map(str, [rank, title, score, author, url, discussion])))
PY
}

hw::_render_entry() {
  local cols=$1 line="$2"
  local -a parts
  parts=(${(s:	:)line})
  local rank=${parts[1]:-?}
  local title=${parts[2]:-"(untitled)"}
  local score=${parts[3]:-0}
  local author=${parts[4]:-unknown}
  local url=${parts[5]:-}
  local discussion=${parts[6]:-}
  local link=${url:-$discussion}
  local title_color="%B%F{15}"
  local rank_color="%B%F{11}"
  local meta_color="%F{7}"
  local url_color="%F{8}"
  local reset="%f%b"
  local rank_label
  printf -v rank_label "%2s." "$rank"
  local indent=4
  local title_width=$((cols - indent - ${#rank_label}))
  (( title_width < 10 )) && title_width=10
  hw::_truncate "$title" $title_width
  local title_text=$REPLY
  print -P "  ${rank_color}${rank_label}${reset} ${title_color}${title_text}${reset}"
  local meta="${score} pts · by ${author}"
  hw::_truncate "$meta" $((cols - indent))
  local meta_text=$REPLY
  print -P "    ${meta_color}${meta_text}${reset}"
  if [[ -n $link ]]; then
    hw::_truncate "$link" $((cols - indent))
    local url_text=$REPLY
    print -P "    ${url_color}${url_text}${reset}"
  fi
}


hw::print_banner() {
  [[ -o interactive ]] || return
  [[ -t 1 ]] || return
  if [[ ${PWD:A} != ${HOME:A} ]]; then
    return
  fi

  hw::_ensure_setup

  if hw::_banner_recently_shown $HW_SHOW_INTERVAL; then
    return
  fi

  local cols=${COLUMNS:-$(command tput cols 2>/dev/null || print 80)}
  (( cols >= 40 )) || return
  local border_color="%F{6}"
  local accent_color="%B%F{14}"
  local reset="%f%b"
  local lines_output
  if ! lines_output=$(hw::_load_lines); then
    print -P "${border_color}Hacker News cache unavailable; updating soon.${reset}"
    return
  fi

  hw::_repeat "═" $cols; local horiz=$REPLY
  print -P "${border_color}${horiz}${reset}"
  local header="Hacker News Highlights"
  hw::_truncate "$header" $((cols - 2))
  print -P " ${accent_color}${REPLY}${reset}"
  hw::_repeat "─" $cols; local horiz=$REPLY
  print -P "${border_color}${horiz}${reset}"
  print

  local first=1
  local line
  while IFS= read -r line; do
    [[ -z $line ]] && continue
    if (( ! first )); then
      print
    fi
    first=0
    hw::_render_entry $cols "$line"
  done <<< "$lines_output"
  print

  hw::_repeat "═" $cols; horiz=$REPLY
  print -P "${border_color}${horiz}${reset}"
  hw::_record_banner_shown
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
