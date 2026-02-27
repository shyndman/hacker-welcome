## Why

The current prompt path is doing too much: it runs setup logic, may trigger a refresh, and invokes Python to parse JSON before rendering. That adds startup latency and keeps most of the rendering behavior locked in a large shell script that is hard to evolve.

## What Changes

- Replace prompt-time JSON parsing with a cached, pre-rendered banner artifact written by the refresh job and stored alongside `top5.json`.
- Move banner string composition to a Python refresh script that runs under `uv` with PEP 723 metadata.
- Keep the prompt-time Zsh path minimal: perform time/visibility gating, print cached banner string, and show a simple generic fallback error string when artifact read fails.
- Render and cache the banner at the computed maximum content width for the top-five payload (the "red-box" width), not a fixed terminal preset.
- Accept "as of last cron run" relative-time text in the cached output.

## Capabilities

### New Capabilities
- `pre-rendered-banner-cache`: Generate and store a fully rendered top-five banner string artifact during scheduled refresh so prompt rendering requires no Python.

### Modified Capabilities
- *(none)*

## Impact

- Affects `hacker-welcome.plugin.zsh` prompt-time banner loading/rendering and setup behavior.
- Replaces/reshapes `scripts/hacker_welcome_refresh.py` to include rendering and artifact output concerns.
- Introduces runtime dependency on `uv` for executing the PEP 723 script in cron.
- Changes cache contract from JSON-only consumption to rendered-banner artifact consumption by the shell plugin.
