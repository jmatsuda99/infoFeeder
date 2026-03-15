from __future__ import annotations

import socket
from urllib.error import URLError
from urllib.request import Request, urlopen

import feedparser

from db import insert_item, list_feeds, set_feed_check_result

USER_AGENT = "Mozilla/5.0 (compatible; GoogleAlertsRSSViewer/1.0)"


def validate_feed_url(url: str) -> tuple[bool, str]:
    try:
        parsed = feedparser.parse(url)
        if parsed.bozo and getattr(parsed, "bozo_exception", None):
            exc = parsed.bozo_exception
            if not getattr(parsed, "entries", None):
                return False, str(exc)
        if not getattr(parsed, "entries", None):
            return False, "エントリが見つかりませんでした。"
        return True, f"{len(parsed.entries)}件のエントリを確認"
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


def _read_feed(url: str):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=20) as response:
        content = response.read()
    return feedparser.parse(content)


def fetch_active_feeds() -> dict[str, int]:
    result = {"feeds_processed": 0, "new_items": 0, "failed_feeds": 0}
    for feed in list_feeds():
        feed_id, name, url, category, is_active, *_ = feed
        if not is_active:
            continue
        result["feeds_processed"] += 1
        try:
            parsed = _read_feed(url)
            if parsed.bozo and getattr(parsed, "bozo_exception", None) and not parsed.entries:
                raise ValueError(str(parsed.bozo_exception))

            new_count = 0
            for entry in parsed.entries:
                inserted = insert_item(
                    feed_id=feed_id,
                    title=entry.get("title", ""),
                    link=entry.get("link", ""),
                    published=entry.get("published", "") or entry.get("updated", ""),
                    summary=entry.get("summary", "") or entry.get("description", ""),
                )
                if inserted:
                    new_count += 1
            result["new_items"] += new_count
            set_feed_check_result(feed_id, error=None)
        except (URLError, socket.timeout, TimeoutError, ValueError, OSError) as exc:
            result["failed_feeds"] += 1
            set_feed_check_result(feed_id, error=str(exc))
    return result
