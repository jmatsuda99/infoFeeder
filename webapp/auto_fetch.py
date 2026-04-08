from datetime import datetime

from db import get_app_state, set_app_state
from fetcher import fetch_active_feeds

AUTO_FETCH_SLOT_KEY = "last_auto_fetch_slot"


def maybe_run_auto_fetch(now):
    if now.minute not in (0, 30):
        return 0

    current_slot = now.strftime("%Y-%m-%dT%H:%M")
    if get_app_state(AUTO_FETCH_SLOT_KEY, "") == current_slot:
        return 0

    inserted_count = fetch_active_feeds()
    set_app_state(AUTO_FETCH_SLOT_KEY, current_slot)
    return inserted_count
