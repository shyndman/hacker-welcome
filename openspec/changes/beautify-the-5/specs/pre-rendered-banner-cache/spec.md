## ADDED Requirements

### Requirement: Scheduled refresh SHALL produce a rendered banner artifact
The system SHALL run the Hacker Welcome refresh workflow as a Python script executable via `uv run --script` with PEP 723 metadata, and each successful refresh SHALL write a fully rendered banner string artifact for prompt-time display. The rendered banner artifact SHALL be stored alongside `top5.json` in the cache directory.

#### Scenario: Refresh writes display artifact
- **WHEN** the scheduled refresh job runs successfully
- **THEN** the cache directory contains a non-empty rendered banner artifact file
- **THEN** the artifact represents the current top-five stories from that refresh run

#### Scenario: JSON cache remains alongside rendered artifact
- **WHEN** refresh completes successfully
- **THEN** `top5.json` remains present in the cache directory
- **THEN** the rendered banner artifact exists as a separate sibling file

#### Scenario: Refresh fails before rendering completes
- **WHEN** story fetching or rendering fails
- **THEN** the existing banner artifact SHALL remain unchanged
- **THEN** the refresh process SHALL return a non-zero exit status

### Requirement: Banner render width SHALL match payload-derived max content width
The refresh renderer SHALL compute display width from the current top-five data by measuring visible text width with `wcwidth`, and SHALL render the banner to the resulting maximum content width (the red-box width) instead of a fixed terminal preset.

#### Scenario: One item is significantly longer than others
- **WHEN** one story line has the largest visible width in the top-five set
- **THEN** rendered rows use that item-derived width as the content width baseline
- **THEN** shorter item rows are padded to preserve aligned layout boundaries

#### Scenario: Titles include wide or combining characters
- **WHEN** titles/authors/domains contain characters with display width not equal to codepoint count
- **THEN** width calculations SHALL use `wcwidth`-based visible-width semantics
- **THEN** row alignment remains visually consistent in terminal output

### Requirement: Prompt rendering SHALL not invoke Python
Prompt-time banner display SHALL read and print the rendered banner artifact directly, and SHALL not execute Python for normal banner display.

#### Scenario: Banner artifact is available
- **WHEN** an interactive prompt in `$HOME` triggers the banner path
- **THEN** the plugin prints the cached banner artifact verbatim
- **THEN** no prompt-time Python process is executed to parse or render story data

### Requirement: Prompt rendering SHALL provide deterministic fallback on artifact error
If prompt-time banner artifact read fails (missing, unreadable, or empty), the plugin SHALL print a single generic fallback error string and continue prompt execution.

#### Scenario: Artifact missing
- **WHEN** the banner artifact file does not exist at render time
- **THEN** the plugin prints exactly one fallback error message line
- **THEN** the fallback line contains no timestamp and no log-hint text
- **THEN** prompt execution continues without crash or retry loop

#### Scenario: Artifact unreadable or empty
- **WHEN** artifact read returns an error or empty payload
- **THEN** the plugin prints exactly one fallback error message line
- **THEN** the fallback line contains no timestamp and no log-hint text
- **THEN** no additional recovery work (network refresh or Python execution) is attempted in prompt path

### Requirement: Relative-time labels SHALL reflect refresh time snapshot
Rendered relative-time text in the cached artifact SHALL represent story age at refresh time and SHALL not be recomputed during prompt display.

#### Scenario: Prompt opened between refresh intervals
- **WHEN** a prompt is shown after a successful refresh and before the next refresh
- **THEN** the displayed relative-time strings remain the values rendered during that refresh
- **THEN** no live recomputation is performed in prompt path
