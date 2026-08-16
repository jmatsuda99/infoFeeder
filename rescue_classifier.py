"""RESCUE scoring: flag articles unlikely to ever be SAVEd by the user.

Design (James's backtested model, see train_rescue_model.py for the training
side): for each `topic_category`, score = logit(category prior save rate) +
the sum of the (up to 6, by |weight|) matched keyword log-likelihood-ratio
weights for that category. A category only participates in RESCUE at all
(`eligible=1` in `rescue_category_priors`) when it had enough SAVEd articles
to fit a meaningful model *and* passed a self-consistency backtest -- see
train_rescue_model.py's docstring for the full criteria and the reason
脱炭素・カーボンニュートラル is permanently excluded regardless of volume.

This module only *reads* the trained weights (from the `rescue_weights` /
`rescue_category_priors` tables) and applies them -- it never computes them.
The tables are populated exclusively by running train_rescue_model.py as an
independent script (never from db.init_db()'s automatic startup path, which
only creates the tables via CREATE TABLE IF NOT EXISTS -- see that module's
docstring for why). Until that script has been run at least once, both
tables are empty and compute_rescue_score() harmlessly returns (0.0, False)
for every article -- callers do not need to special-case an untrained DB.

The trained weights are cached in memory after the first lookup (a lightweight
key-value read, not the heavy training computation) so this stays cheap to
call from both fetcher.insert_feed_rows() and db.py's backfill loop, exactly
like category_classifier.classify_article() / noise_filter.is_noise_article().
Call reload_rescue_model_cache() after re-running train_rescue_model.py in a
long-lived process (e.g. the web app) to pick up freshly trained weights
without a restart.
"""

import math
import re
import sqlite3
from threading import Lock

from article_utils import extract_bold_terms

# Keep in sync with train_rescue_model.py's MAX_MATCHED_TERMS -- both must
# agree on how many top-|weight| matched terms contribute to the score.
MAX_MATCHED_TERMS = 6

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text):
    return _HTML_TAG_RE.sub(" ", text or "")


def build_matchable_text(title, summary):
    """Lowercased text used for candidate-keyword substring matching.

    Shared by train_rescue_model.py (to compute term statistics) and
    compute_rescue_score() below (to score a single article), so the two
    stay consistent by construction. Mirrors the matching approach already
    used by category_classifier.classify_article() / noise_filter's
    keyword checks: Google Alerts' <b>...</b>-highlighted terms plus the
    HTML-stripped title/summary text.
    """
    title_text = title or ""
    summary_text = summary or ""
    bold_terms = extract_bold_terms(title_text) + extract_bold_terms(summary_text)
    combined = " ".join(bold_terms) if bold_terms else ""
    combined = f"{combined} {_strip_html(title_text)} {_strip_html(summary_text)}"
    return combined.lower()


def top_matched_weights(text_lower, term_weights, limit=MAX_MATCHED_TERMS):
    """Weights of the terms (from `term_weights`, a {term: weight} dict) that
    appear in `text_lower`, keeping only the `limit` largest by |weight|.
    """
    matched = [weight for term, weight in term_weights.items() if term.lower() in text_lower]
    matched.sort(key=abs, reverse=True)
    return matched[:limit]


_cache_lock = Lock()
_cache = None  # {"priors": {category: {"prior", "threshold", "eligible"}}, "weights": {category: {term: weight}}}


def _load_cache_from_db():
    from db import get_conn

    conn = get_conn()
    cur = conn.cursor()
    try:
        priors = {}
        try:
            for row in cur.execute(
                "SELECT topic_category, prior, threshold, eligible FROM rescue_category_priors"
            ):
                priors[row["topic_category"]] = {
                    "prior": row["prior"],
                    "threshold": row["threshold"],
                    "eligible": bool(row["eligible"]),
                }
        except sqlite3.OperationalError:
            # Table doesn't exist yet (schema not migrated) or isn't visible
            # yet from this connection (e.g. mid-transaction in db.init_db()
            # on the very first run, before the CREATE TABLE is committed).
            # Either way, behave as "no trained model yet".
            priors = {}

        weights = {}
        try:
            for row in cur.execute("SELECT topic_category, term, weight FROM rescue_weights"):
                weights.setdefault(row["topic_category"], {})[row["term"]] = row["weight"]
        except sqlite3.OperationalError:
            weights = {}

        return {"priors": priors, "weights": weights}
    finally:
        conn.close()


def _get_cache():
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = _load_cache_from_db()
        return _cache


def reload_rescue_model_cache():
    """Force a reload of the trained weights from the DB.

    Only needed in a long-lived process (e.g. the web app) after re-running
    train_rescue_model.py; short-lived scripts (fetch runs, backfills) pick
    up fresh weights automatically since they start with an empty cache.
    """
    global _cache
    with _cache_lock:
        _cache = _load_cache_from_db()
    return _cache


def is_rescue_eligible_category(topic_category):
    """Whether `topic_category` is in RESCUE_ELIGIBLE_CATEGORIES (per the
    trained model currently cached), i.e. whether compute_rescue_score() can
    ever return is_rescue=True for it.
    """
    info = _get_cache()["priors"].get(topic_category or "")
    return bool(info and info["eligible"])


def compute_rescue_score(title, summary, topic_category):
    """Return (score: float, is_rescue: bool) for one article.

    `topic_category` should be the value already produced by
    category_classifier.classify_article() for this article. Categories
    outside RESCUE_ELIGIBLE_CATEGORIES (including "" and any category with no
    trained row yet) always return is_rescue=False, with score=0.0.
    """
    cache = _get_cache()
    info = cache["priors"].get(topic_category or "")
    if not info or not info["eligible"]:
        return 0.0, False

    prior = info["prior"]
    threshold = info["threshold"]
    if prior is None or not (0.0 < prior < 1.0):
        return 0.0, False

    base_score = math.log(prior / (1.0 - prior))

    term_weights = cache["weights"].get(topic_category, {})
    text_lower = build_matchable_text(title, summary)
    matched = top_matched_weights(text_lower, term_weights)
    score = base_score + sum(matched)

    is_rescue = threshold is not None and score <= threshold
    return score, bool(is_rescue)
