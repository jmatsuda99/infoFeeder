"""JST formatting for web UI and DB-backed timestamps (no Streamlit)."""
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
ARTICLE_VISIBILITY_DAYS = 7


def parse_datetime_value(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
    else:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def is_recent_article(value, now=None, max_age_days=ARTICLE_VISIBILITY_DAYS):
    dt = parse_datetime_value(value)
    if dt is None:
        return True
    reference_now = now.astimezone(JST) if now and now.tzinfo else now
    if reference_now is None:
        reference_now = datetime.now(JST)
    elif reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=JST)
    cutoff = reference_now - timedelta(days=max_age_days)
    return dt > cutoff


def format_jst_datetime(value, include_date=False):
    dt = parse_datetime_value(value)
    if dt is None:
        if isinstance(value, str):
            return value
        return ""

    if include_date:
        return dt.strftime("%Y-%m-%d %H:%M JST")
    return dt.strftime("%Y-%m-%d %H:%M:%S JST")


def format_jst_time(value):
    dt = None

    if isinstance(value, datetime):
        dt = value
    else:
        formatted = format_jst_datetime(value)
        if not formatted:
            return ""
        return formatted.split(" ")[1]

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    else:
        dt = dt.astimezone(JST)
    return dt.strftime("%H:%M")
