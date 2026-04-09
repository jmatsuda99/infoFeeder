from datetime import datetime

from db import get_app_state, set_app_state
from fetcher import fetch_active_feeds

AUTO_FETCH_SLOT_KEY = "last_auto_fetch_slot"


def _half_hour_slot(now):
    slot_minute = 0 if now.minute < 30 else 30
    return now.replace(minute=slot_minute, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def maybe_run_auto_fetch(now):
    # Allow delayed timer execution (sleep/resume, background tab throttling):
    # e.g. 09:03 should still execute the 09:00 slot once.
    current_slot = _half_hour_slot(now)
    if get_app_state(AUTO_FETCH_SLOT_KEY, "") == current_slot:
        return 0

    inserted_count = fetch_active_feeds()
    set_app_state(AUTO_FETCH_SLOT_KEY, current_slot)
    return inserted_count
