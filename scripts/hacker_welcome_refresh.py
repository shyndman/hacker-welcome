#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["wcwidth>=0.2.13"]
# ///
"""Fetch top Hacker News stories and atomically cache JSON + rendered banner."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from wcwidth import wcwidth

BASE_URL = "https://hacker-news.firebaseio.com/v0"
TOP_STORIES_URL = f"{BASE_URL}/topstories.json"
ITEM_URL = f"{BASE_URL}/item/{{story_id}}.json"
DEFAULT_COUNT = 5

ANSI_RESET = "\033[0m"
ANSI_FG_RESET = "\033[39m"
ANSI_TEXT_RESET = "\033[22;39m"
ANSI_HEADER_LEFT = "\033[22;1;38:2:156:207:216m"
ANSI_HEADER_LAMBDA = "\033[22;1;38:2:255:102:0m"
ANSI_HEADER_RIGHT = "\033[22;38:2:144:140:170m"
ANSI_DIVIDER = "\033[38:2:110:106:134;49m"
ANSI_RANK_TOP = "\033[22;1;38:2:196:167:231m"
ANSI_RANK = "\033[22;1;38:2:110:106:134m"
ANSI_TITLE = "\033[22;1;38:2:224:222:244m"
ANSI_DOMAIN = "\033[3;38:2:110:106:134m"
ANSI_SCORE = "\033[38:2:235:188:186m"
ANSI_META = "\033[38:2:144:140:170m"
ANSI_AUTHOR = "\033[38:2:156:207:216m"
ANSI_COMMENTS = "\033[38:2:49:116:143;58:2:49:116:143;4:3m"
ANSI_COMMENTS_RESET = "\033[39;59;24m"
KITTY_TEXT_SIZING_PREFIX = "\033]66;"
KITTY_TEXT_SIZING_SUFFIX = "\a"
TITLE_SCALE = 1
TITLE_SIZE_NUMERATOR = 0
TITLE_SIZE_DENOMINATOR = 0
DOMAIN_SIZE_NUMERATOR = 7
DOMAIN_SIZE_DENOMINATOR = 8
ORDINAL_SIZE_NUMERATOR = 14
ORDINAL_SIZE_DENOMINATOR = 15
SECOND_LINE_SIZE_NUMERATOR = 14
SECOND_LINE_SIZE_DENOMINATOR = 15
SECOND_LINE_VERTICAL_ALIGN = 1
HEADER_LEFT = "  λ  HACKER NEWS "
HEADER_LAMBDA = "λ"
HEADER_RIGHT = "  top_stories.json"


class RefreshError(RuntimeError):
    """Raised when refresh cannot safely produce new cache artifacts."""


def fetch_json(url: str) -> Any:
    """Load JSON from the Hacker News API with a bounded timeout."""
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def display_width(text: str) -> int:
    """Return terminal cell width for visible text content."""
    width = 0
    for character in text:
        char_width = wcwidth(character)
        width += 0 if char_width < 0 else char_width
    return width


def truncate_to_width(text: str, limit: int) -> str:
    """Clamp visible text width and append an ellipsis if truncation occurs."""
    if limit <= 0:
        return ""
    if display_width(text) <= limit:
        return text

    ellipsis = "…"
    ellipsis_width = display_width(ellipsis)
    if limit <= ellipsis_width:
        return ellipsis

    allowed = limit - ellipsis_width
    rendered: list[str] = []
    used = 0
    for character in text:
        char_width = wcwidth(character)
        char_width = 0 if char_width < 0 else char_width
        if used + char_width > allowed:
            break
        rendered.append(character)
        used += char_width
    return "".join(rendered) + ellipsis


def extract_domain(url: str) -> str:
    """Extract a compact host label used in the title line."""
    domain = (url or "").split("://", maxsplit=1)[-1]
    domain = domain.split("/", maxsplit=1)[0]
    domain = domain.removeprefix("www.")
    return domain or "news.ycombinator.com"


def relative_time(posted_at: int, now_epoch: int) -> str:
    """Produce a refresh-snapshot age label for story metadata."""
    delta = max(0, now_epoch - posted_at)
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


def kitty_link(url: str, text: str) -> str:
    """Wrap text in OSC8 hyperlinks while keeping visible text unchanged."""
    if not url:
        return text
    return f"\033]8;;{url}\a{text}\033]8;;\a"


def kitty_text_size(
    text: str,
    numerator: int,
    denominator: int,
    scale: int | None = None,
    vertical_align: int | None = None,
) -> str:
    """Wrap text in kitty OSC 66 metadata to request fractional text sizing."""
    metadata: list[str] = []
    if scale is not None:
        metadata.append(f"s={scale}")
    metadata.extend([f"n={numerator}", f"d={denominator}"])
    if vertical_align is not None:
        metadata.append(f"v={vertical_align}")
    return (
        f"{KITTY_TEXT_SIZING_PREFIX}{':'.join(metadata)};"
        f"{text}{KITTY_TEXT_SIZING_SUFFIX}"
    )


def write_atomic_text(path: Path, payload: str) -> None:
    """Write UTF-8 text atomically to prevent partial cache artifacts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(payload)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, path)


def write_atomic_json(path: Path, payload: Iterable[dict[str, Any]]) -> None:
    """Write JSON atomically so readers only observe complete snapshots."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(list(payload), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, path)


def build_record(story_id: int, rank: int, fetched_at: int) -> dict[str, Any]:
    """Normalize Hacker News item data into the cache record contract."""
    data = fetch_json(ITEM_URL.format(story_id=story_id))
    discussion_url = f"https://news.ycombinator.com/item?id={story_id}"
    return {
        "rank": rank,
        "id": story_id,
        "title": data.get("title") or "(untitled)",
        "author": data.get("by") or "unknown",
        "score": int(data.get("score") or 0),
        "comments": int(data.get("descendants") or 0),
        "posted_at": int(data.get("time") or 0),
        "url": data.get("url") or discussion_url,
        "hn_discussion": discussion_url,
        "fetched_at": fetched_at,
    }


def render_entry(record: dict[str, Any], width: int, now_epoch: int) -> list[str]:
    """Render one story block as four banner lines using shared width."""
    rank = int(record.get("rank") or 0)
    title = str(record.get("title") or "(untitled)")
    score = int(record.get("score") or 0)
    author = str(record.get("author") or "unknown")
    url = str(record.get("url") or "")
    discussion = str(record.get("hn_discussion") or "")
    comments = int(record.get("comments") or 0)
    posted_at = int(record.get("posted_at") or 0)
    link = url or discussion

    domain_label = f"({extract_domain(link)})"
    rank_label = f"{rank:02d}"
    title_prefix = f"  {rank_label}   "
    title_plain = f"{title_prefix}{title} {domain_label}"

    comments_text = f"{comments} comments"
    age_text = relative_time(posted_at, now_epoch)
    meta_prefix = f"      ▲ {score}  by "
    meta_suffix = f"  • {age_text}  • {comments_text}"
    author_budget = max(3, width - display_width(meta_prefix) - display_width(meta_suffix))
    author_text = truncate_to_width(author, author_budget)
    meta_plain = f"{meta_prefix}{author_text}{meta_suffix}"

    rank_color = ANSI_RANK_TOP if rank == 1 else ANSI_RANK
    sized_rank = kitty_text_size(rank_label, ORDINAL_SIZE_NUMERATOR, ORDINAL_SIZE_DENOMINATOR)
    sized_title = kitty_text_size(title, TITLE_SIZE_NUMERATOR, TITLE_SIZE_DENOMINATOR, scale=TITLE_SCALE)
    sized_domain = kitty_text_size(domain_label, DOMAIN_SIZE_NUMERATOR, DOMAIN_SIZE_DENOMINATOR, vertical_align=1)
    title_styled = (
        f"  {rank_color}{sized_rank}{ANSI_TEXT_RESET}   "
        f"{ANSI_TITLE}{kitty_link(link, sized_title)}{ANSI_TEXT_RESET}"
        f"{ANSI_DOMAIN} {sized_domain}{ANSI_TEXT_RESET}"
    )
    sized_score = kitty_text_size(
        f" {score}",
        SECOND_LINE_SIZE_NUMERATOR,
        SECOND_LINE_SIZE_DENOMINATOR,
        vertical_align=SECOND_LINE_VERTICAL_ALIGN,
    )
    sized_by = kitty_text_size(
        "  by ",
        SECOND_LINE_SIZE_NUMERATOR,
        SECOND_LINE_SIZE_DENOMINATOR,
        vertical_align=SECOND_LINE_VERTICAL_ALIGN,
    )
    sized_author = kitty_text_size(
        author_text,
        SECOND_LINE_SIZE_NUMERATOR,
        SECOND_LINE_SIZE_DENOMINATOR,
        vertical_align=SECOND_LINE_VERTICAL_ALIGN,
    )
    sized_tail = kitty_text_size(
        f"  • {age_text}  • ",
        SECOND_LINE_SIZE_NUMERATOR,
        SECOND_LINE_SIZE_DENOMINATOR,
        vertical_align=SECOND_LINE_VERTICAL_ALIGN,
    )
    sized_comments = kitty_text_size(
        comments_text,
        SECOND_LINE_SIZE_NUMERATOR,
        SECOND_LINE_SIZE_DENOMINATOR,
        vertical_align=SECOND_LINE_VERTICAL_ALIGN,
    )
    comments_link = kitty_link(discussion, sized_comments)
    meta_styled = (
        f"      {ANSI_SCORE}▲{sized_score}{ANSI_FG_RESET}"
        f"{ANSI_META}{sized_by}{ANSI_AUTHOR}{sized_author}"
        f"{ANSI_META}{sized_tail}{ANSI_COMMENTS}{comments_link}{ANSI_COMMENTS_RESET}"
    )

    def pad_line(plain_text: str, styled_text: str) -> str:
        pad = max(0, width - display_width(plain_text))
        return f"{styled_text}{' ' * pad}{ANSI_RESET}"

    return [
        pad_line("", ""),
        pad_line(title_plain, title_styled),
        pad_line(meta_plain, meta_styled),
        pad_line("", ""),
    ]


def compute_banner_width(records: list[dict[str, Any]], now_epoch: int) -> int:
    """Determine the red-box width from max visible item content width."""
    item_widths: list[int] = []
    for record in records:
        rank_label = f"{int(record.get('rank') or 0):02d}"
        title = str(record.get("title") or "(untitled)")
        link = str(record.get("url") or "") or str(record.get("hn_discussion") or "")
        title_plain = f"  {rank_label}   {title} ({extract_domain(link)})"

        score = int(record.get("score") or 0)
        author = str(record.get("author") or "unknown")
        comments = int(record.get("comments") or 0)
        posted_at = int(record.get("posted_at") or 0)
        age_text = relative_time(posted_at, now_epoch)
        meta_plain = f"      ▲ {score}  by {author}  • {age_text}  • {comments} comments"

        item_widths.append(max(display_width(title_plain), display_width(meta_plain)))

    content_width = max(item_widths, default=40)
    header_min = display_width(HEADER_LEFT) + display_width(HEADER_RIGHT) + 1
    return max(content_width, header_min)


def render_banner(records: list[dict[str, Any]], now_epoch: int) -> str:
    """Create the full banner string consumed directly by prompt-time shell code."""
    width = compute_banner_width(records, now_epoch)
    right_space = max(1, width - display_width(HEADER_LEFT) - display_width(HEADER_RIGHT))
    divider = "━" * width
    header_left_styled = HEADER_LEFT.replace(
        HEADER_LAMBDA,
        f"{ANSI_HEADER_LAMBDA}{HEADER_LAMBDA}{ANSI_HEADER_LEFT}",
        1,
    )

    lines = [
        f"{ANSI_HEADER_LEFT}{header_left_styled}{ANSI_HEADER_RIGHT}{HEADER_RIGHT}{' ' * right_space}{ANSI_RESET}",
        f"{ANSI_DIVIDER}{divider}{ANSI_RESET}",
    ]
    for record in records:
        lines.extend(render_entry(record, width, now_epoch))
    lines.append(f"{ANSI_DIVIDER}{divider}{ANSI_RESET}")
    return "\n".join(lines) + "\n"


def refresh(cache_path: Path, banner_path: Path, story_count: int) -> None:
    """Fetch stories and atomically publish both JSON and rendered banner artifacts."""
    now_epoch = int(time.time())
    try:
        top_ids = fetch_json(TOP_STORIES_URL)[:story_count]
    except Exception as exc:
        raise RefreshError(f"Failed to fetch top story IDs: {exc}") from exc

    records: list[dict[str, Any]] = []
    for rank, story_id in enumerate(top_ids, start=1):
        try:
            records.append(build_record(int(story_id), rank, now_epoch))
        except urllib.error.URLError as exc:
            print(f"[hacker-welcome] Failed to fetch story {story_id}: {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"[hacker-welcome] Unexpected error for story {story_id}: {exc}", file=sys.stderr)

    if not records:
        raise RefreshError("No stories fetched; cache not updated")

    banner_text = render_banner(records, now_epoch)
    if not banner_text.strip():
        raise RefreshError("Rendered banner is empty")

    write_atomic_json(cache_path, records)
    write_atomic_text(banner_path, banner_text)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments for cache locations and story-count controls."""
    default_cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "hacker-welcome"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache",
        type=Path,
        default=default_cache_dir / "top5.json",
        help="path to JSON cache file",
    )
    parser.add_argument(
        "--banner",
        type=Path,
        default=default_cache_dir / "top5.banner",
        help="path to rendered banner cache file",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help="number of stories to cache",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run refresh workflow and return shell-friendly status code."""
    args = parse_args(argv or sys.argv[1:])
    try:
        refresh(args.cache, args.banner, max(1, args.count))
    except RefreshError as exc:
        print(f"[hacker-welcome] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[hacker-welcome] Unexpected refresh failure: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
