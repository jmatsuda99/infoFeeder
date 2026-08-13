"""One-off backfill: translate existing non-Japanese article title/summary to Japanese.

This is intentionally NOT wired into db.init_db()'s automatic backfill loop.
Each translation is a Claude CLI subprocess call, so running this over every
existing article on every app startup would make startup noticeably slower.
Run this script manually instead, whenever there is a batch of untranslated
articles to catch up on (e.g. right after this feature is deployed).

Usage:
    python backfill_translations.py
"""

import sys

from article_utils import is_non_japanese_text, split_source_name_prefix
from db import get_conn, init_db
from translation import translate_title_summary


def _make_console_safe(text):
    """Best-effort ASCII-safe rendering for progress logging.

    Some source titles contain characters (e.g. Korean/emoji) that the
    Windows console's active code page cannot display, which would
    otherwise crash the whole backfill mid-run on a print() call. Progress
    logging is not the source of truth (the DB update is), so it is fine to
    fall back to escaped output here.
    """
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")


def backfill_translations():
    init_db()

    conn = get_conn()
    cur = conn.cursor()
    try:
        rows = cur.execute(
            """
            SELECT i.id, i.title, i.summary, f.name AS feed_name
            FROM items i
            JOIN feeds f ON i.feed_id = f.id
            """
        ).fetchall()
        # official_watch/policy_listing/committee_json titles are prefixed with
        # the (often Japanese) source name, e.g. "IEA（国際エネルギー機関）: ...".
        # Judge/translate only the article title itself so a Japanese source
        # name does not mask an all-English article title from translation.
        targets = []
        for row in rows:
            prefix, title_body = split_source_name_prefix(row["title"] or "", row["feed_name"])
            if is_non_japanese_text(title_body):
                targets.append((row, prefix, title_body))

        total = len(targets)
        print(f"Found {total} non-Japanese article(s) to translate.")

        success_count = 0
        failed_count = 0

        for index, (row, prefix, title_body) in enumerate(targets, start=1):
            item_id = row["id"]
            original_summary = row["summary"] or ""

            print(
                f"[{index}/{total}] id={item_id} translating: {_make_console_safe(title_body[:60])!r}",
                flush=True,
            )

            result = translate_title_summary(title_body, original_summary)

            if not result.ok:
                failed_count += 1
                print(f"  -> SKIPPED: {_make_console_safe(result.error)}", flush=True)
                continue

            new_title = f"{prefix}{result.title_ja}"
            new_summary = (
                result.summary_ja
                if (result.summary_ja or not original_summary.strip())
                else original_summary
            )

            cur.execute(
                "UPDATE items SET title=?, summary=? WHERE id=?",
                (new_title, new_summary, item_id),
            )
            conn.commit()
            success_count += 1
            print(f"  -> OK: {_make_console_safe(new_title[:60])!r}", flush=True)

        print(
            f"Done. total={total} success={success_count} failed={failed_count}",
            flush=True,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    backfill_translations()
