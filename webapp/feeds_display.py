from db import list_feeds
from ui_common import format_jst_datetime


def get_feed_rows():
    feeds = []
    for feed in list_feeds():
        feeds.append(
            {
                "id": int(feed["id"]),
                "name": feed["name"] or "",
                "url": feed["url"] or "",
                "base_url": feed["base_url"] or feed["url"] or "",
                "source_type": feed["source_type"] or "rss",
                "category": feed["category"] or "",
                "is_active": bool(feed["is_active"]),
                "item_count": int(feed["item_count"] or 0),
                "last_fetched_at": format_jst_datetime(feed["last_fetched_at"]) if feed["last_fetched_at"] else "",
                "last_success_at": format_jst_datetime(feed["last_success_at"]) if feed["last_success_at"] else "",
                "last_error_at": format_jst_datetime(feed["last_error_at"]) if feed["last_error_at"] else "",
                "last_error_message": feed["last_error_message"] or "",
            }
        )
    return feeds
