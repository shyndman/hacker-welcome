## 1. Refresh Script Refactor

- [x] 1.1 Convert `scripts/hacker_welcome_refresh.py` to PEP 723 script format with `uv run --script` shebang and `wcwidth` dependency metadata.
- [x] 1.2 Add banner-render pipeline in refresh script that computes payload-derived max content width and produces the full ANSI banner string artifact.
- [x] 1.3 Preserve atomic cache writes so failed refreshes do not clobber the last good rendered banner artifact.

## 2. Cache Contract and Cron Wiring

- [x] 2.1 Define/update cache file paths and constants so the rendered banner artifact is stored alongside `top5.json` in the plugin cache directory.
- [x] 2.2 Update cron command installation to execute the refresh script via the new script entry model and write expected artifact outputs.
- [x] 2.3 Confirm setup path still creates required cache/state directories and no longer depends on prompt-time JSON parse helpers.

## 3. Prompt-Time Shell Simplification

- [x] 3.1 Replace prompt-time data loading with direct read/print of cached rendered banner artifact.
- [x] 3.2 Remove prompt-time Python invocations used for JSON parsing/render data extraction.
- [x] 3.3 Add deterministic single-line generic fallback error output (no timestamp/log hint) when the rendered artifact is missing, unreadable, or empty.

## 4. Manual Verification

- [x] 4.1 Manually run refresh script and verify rendered banner artifact is generated and non-empty.
- [x] 4.2 Smoke-test prompt rendering in a clean Zsh session from `$HOME` and confirm banner is printed without Python execution.
- [x] 4.3 Simulate missing/corrupt artifact and verify exactly one fallback error line is shown.
