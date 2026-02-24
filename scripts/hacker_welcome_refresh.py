#!/usr/bin/env python3
"""Fetch top Hacker News stories and store them in a cache file."""
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
from typing import Any, Dict, Iterable, List

BASE_URL = "https://hacker-news.firebaseio.com/v0"
TOP_STORIES_URL = f"{BASE_URL}/topstories.json"
ITEM_URL = f"{BASE_URL}/item/{{story_id}}.json"
DEFAULT_COUNT = 5


def fetch_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def build_record(story_id: int, rank: int) -> Dict[str, Any]:
    data = fetch_json(ITEM_URL.format(story_id=story_id))
    url = data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
    return {
        "rank": rank,
        "id": story_id,
        "title": data.get("title") or "(untitled)",
        "author": data.get("by") or "unknown",
        "score": data.get("score"),
        "posted_at": data.get("time"),
        "url": url,
        "hn_discussion": f"https://news.ycombinator.com/item?id={story_id}",
        "fetched_at": int(time.time()),
    }


def write_atomic(path: Path, payload: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(list(payload), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, path)


def refresh(cache_path: Path, story_count: int) -> None:
    try:
        top_ids = fetch_json(TOP_STORIES_URL)[:story_count]
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[hacker-welcome] Failed to fetch top story IDs: {exc}", file=sys.stderr)
        raise

    records: List[Dict[str, Any]] = []
    for idx, story_id in enumerate(top_ids, start=1):
        try:
            records.append(build_record(story_id, idx))
        except urllib.error.URLError as exc:
            print(f"[hacker-welcome] Failed to fetch story {story_id}: {exc}", file=sys.stderr)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[hacker-welcome] Unexpected error for story {story_id}: {exc}", file=sys.stderr)

    if not records:
        print("[hacker-welcome] No stories fetched; cache not updated", file=sys.stderr)
        return

    write_atomic(cache_path, records)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        / "hacker-welcome"
        / "top5.json",
        help="path to cache file",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help="number of stories to cache",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        refresh(args.cache, max(1, args.count))
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
