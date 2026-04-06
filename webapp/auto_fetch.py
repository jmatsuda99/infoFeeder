from datetime import datetime, timedelta

from db import get_app_state, set_app_state
from fetcher import fetch_active_feeds

AUTO_FETCH_SLOT_KEY = "last_auto_fetch_slot"


def get_next_half_hour(now):
    next_half_hour = now.replace(second=0, microsecond=0)
    if now.minute < 30:
        return next_half_hour.replace(minute=30)
    return (next_half_hour + timedelta(hours=1)).replace(minute=0)


def get_next_auto_fetch_delay_ms(now):
    next_fetch_at = get_next_half_hour(now)
    return max(1000, int((next_fetch_at - now).total_seconds() * 1000) + 1000)


def maybe_run_auto_fetch(now):
    if now.minute not in (0, 30):
        return 0

    current_slot = now.strftime("%Y-%m-%dT%H:%M")
    if get_app_state(AUTO_FETCH_SLOT_KEY, "") == current_slot:
        return 0

    inserted_count = fetch_active_feeds()
    set_app_state(AUTO_FETCH_SLOT_KEY, current_slot)
    return inserted_count
