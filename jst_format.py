"""JST formatting for web UI and DB-backed timestamps (no Streamlit)."""
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def format_jst_datetime(value, include_date=False):
    dt = None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return value

    if dt is None:
        return ""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    else:
        dt = dt.astimezone(JST)

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
