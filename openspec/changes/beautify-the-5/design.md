## Context

`hacker-welcome.plugin.zsh` currently performs setup, refresh orchestration, JSON loading, and terminal rendering. Prompt-time execution invokes Python and may trigger network refresh work, which increases shell startup latency and keeps most banner behavior in a large shell file. The change goal is to shift banner composition into scheduled refresh execution and leave prompt-time behavior as a thin read-and-print path.

## Goals / Non-Goals

**Goals:**
- Remove prompt-time Python process execution for normal banner display.
- Produce a single cached, fully rendered banner artifact that matches the desired "red-box" content.
- Render the artifact at computed maximum item-content width derived from the current top-five payload.
- Use a PEP 723 Python script executed via `uv run --script` in cron.
- Provide deterministic fallback text when banner artifact cannot be read.

**Non-Goals:**
- Dynamic per-terminal reflow or re-wrapping during prompt rendering.
- Real-time relative-time updates between cron refresh intervals.
- Building a long-lived rendering IR framework beyond what is needed for this change.

## Decisions

### 1) Pre-render full banner during refresh
The refresh script will fetch top stories and write a complete, ANSI-styled banner string artifact to cache. Prompt-time logic reads and prints that artifact verbatim.

The rendered banner artifact will live alongside `top5.json` in the existing cache directory rather than replacing the JSON file.

- **Why:** Eliminates prompt-time JSON parsing and Python startup overhead.
- **Alternative considered:** Keep JSON cache and parse/render in Zsh. Rejected because it preserves complexity and width/link handling burden in shell.

### 2) Compute width from payload max content
Rendering width for the cached artifact will be derived from the longest rendered item content in the current top-five set (plus fixed layout padding), producing the red-box width.

- **Why:** Matches user’s desired visual contract and avoids fixed-width assumptions.
- **Alternative considered:** Render to fixed columns (e.g., 80/120). Rejected because it does not preserve desired width semantics.

### 3) Use `wcwidth` for visible-width measurement
The refresh renderer will measure visible cell width using `wcwidth` so truncation and padding decisions use terminal display width rather than codepoint length.

- **Why:** Avoids obvious width drift from wide glyphs/combining behavior.
- **Alternative considered:** `len()` / codepoint count only. Rejected as too error-prone for terminal layout.

### 4) Keep prompt fallback plain and explicit
If the cached artifact is missing, unreadable, or empty, prompt rendering prints a single plain generic failure string (no timestamp and no log-hint text) and exits without additional work.

- **Why:** Keeps prompt path predictable and low-risk.
- **Alternative considered:** Attempt prompt-time regeneration. Rejected to preserve no-Python/no-network prompt path.

### 5) Adopt PEP 723 + `uv` execution model for script dependencies
The refresh script will declare interpreter/dependencies inline and execute via shebang (`#!/usr/bin/env -S uv run --script`).

- **Why:** Keeps dependency declaration colocated with the script and reduces external packaging setup.
- **Alternative considered:** System Python + manually installed deps. Rejected due to setup drift risk.

## Risks / Trade-offs

- **[Risk] Cached banner may overflow on very narrow terminals** → **Mitigation:** Accept in v1; preserve exact red-box rendering contract and revisit reflow only if needed.
- **[Risk] Cron environment may not find `uv`** → **Mitigation:** Ensure user-level cron PATH includes `uv` location or use stable absolute path in cron command installation.
- **[Risk] Relative-time text becomes stale between refreshes** → **Mitigation:** Define text as "as of last refresh" behavior and refresh every 15 minutes.
- **[Risk] Cached artifact corruption causes missing banner** → **Mitigation:** Continue atomic file writes and emit deterministic fallback string in prompt path.

## Migration Plan

1. Update refresh script to PEP 723/`uv`, fetch top-five stories, and render/write full banner artifact atomically.
2. Update plugin setup/cron command to execute new script entry path and artifact output contract.
3. Simplify prompt-time plugin path to read/print banner artifact and fallback on read failure.
4. Validate with manual smoke tests for cache refresh, startup rendering, and fallback behavior.

## Open Questions

- *(none)*
