"""One-off (re-runnable) training script for the RESCUE model.

RESCUE flags articles that are unlikely to ever be SAVEd by the user, so they
can eventually be deprioritized in the UI. This is intentionally NOT wired
into db.init_db()'s automatic startup path, for the same reason
backfill_translations.py isn't: it does a full scan of every non-noise
article in the DB to fit per-category keyword weights, which would make
every app startup noticeably slower for no benefit (the weights only need to
change when re-trained on fresh SAVE/no-SAVE data). db.init_db() only creates
the `rescue_weights` / `rescue_category_priors` tables (CREATE TABLE IF NOT
EXISTS) and applies whatever weights are already there; this script is the
only thing that ever computes and writes their contents.

Run manually:
    python train_rescue_model.py

Model (James's backtested design)
----------------------------------
For each topic_category `c`:
  prior_c = (saved_c + 1) / (n_c + 2)          [Laplace-smoothed SAVE rate]
  base_score = logit(prior_c) = log(prior_c / (1 - prior_c))

Candidate vocabulary = union of:
  - category_classifier.KEYWORD_CATEGORY_MAP keys
  - noise_filter.STRONG_RETAIN_KEYWORDS
  - noise_filter.WEAK_RETAIN_KEYWORDS
  - noise_filter.POWER_GENERATION_ANCHOR_KEYWORDS

For each candidate term `t`, within category `c` only:
  w_c(t) = log((saved_with+1)/(saved_without+1)) - log((nonsaved_with+1)/(nonsaved_without+1))
  (Laplace-smoothed log-likelihood-ratio of SAVE given the term appears,
  computed separately per category so a term's weight reflects how it
  behaves *within* that category's articles, not the whole corpus.)

  Two guards, both required before a term's weight is used at all:
  - Occurrence guard: a term appearing in fewer than MIN_TERM_OCCURRENCES
    articles within the category is skipped (not enough data for a stable
    estimate).
  - 85% presence-rate guard: a term appearing in more than
    MAX_TERM_PRESENCE_RATE of the category's articles is skipped outright.
    These are the keyword(s) that effectively *define* the category (e.g.
    "データセンター" inside データセンター・AI電力) -- they appear in nearly
    every article regardless of SAVE outcome, so their log-likelihood ratio
    ends up measuring the saved-vs-nonsaved population size difference
    rather than any real signal, producing spuriously large weights. This is
    the exact bug James found and fixed for データセンター・AI電力 (which
    had an inflated apparent RESCUE rate of 78.2% before this guard existed).

An article's score = base_score + sum of the (up to MAX_MATCHED_TERMS, by
|weight|) matched terms' weights for its category. See
rescue_classifier.compute_rescue_score(), which applies this exact formula at
read time using the weights this script writes.

Eligibility (RESCUE_ELIGIBLE_CATEGORIES)
-----------------------------------------
Per project policy (see this repo's RESCUE feature spec), RESCUE is only
applied to categories with enough SAVEd articles for the model to be
statistically meaningful *and* that pass a self-consistency backtest. A
category is eligible only if ALL of:
  1. saved_c >= MIN_SAVED_FOR_ELIGIBILITY (default 30) -- categories with a
     handful of SAVEs (原子力, 水素・アンモニア, 国際動向, ...) can't support
     a meaningful ranking.
  2. Not in EXPLICITLY_EXCLUDED_CATEGORIES -- currently just
     脱炭素・カーボンニュートラル. This category has the largest population
     and the lowest prior SAVE rate of all 15, and James's manual audit found
     genuine SAVEd articles (municipal decarbonization-plan announcements,
     etc.) concentrated in the model's low-score tail, i.e. exactly where
     RESCUE would flag them. It stays excluded even though it would
     otherwise pass checks 1 and 3 on volume alone -- a category-specific
     finding a generic threshold can't detect.
  3. Self-consistency check: sort the category's articles by score and take
     the bottom BOTTOM_PERCENTILE (20%) by score (all articles with a score
     <= the value at that percentile boundary -- the same fixed-threshold
     rule compute_rescue_score() uses at read time, not just a positional
     slice, so this check measures exactly what production will do). If more
     than SELF_CONSISTENCY_MAX_LEAK_RATE of the category's SAVEd articles
     fall into that bottom slice, the model doesn't reliably separate this
     category's SAVEd articles from its RESCUE candidates, and the category
     is excluded. See SELF_CONSISTENCY_MAX_LEAK_RATE's own comment for how
     its value (10%, calibrated against the ~20% a zero-signal model would
     produce by chance) was chosen empirically rather than taken verbatim
     from the feature spec's illustrative "5%" figure. This check is what
     would automatically catch a future recurrence of the
     データセンター・AI電力-style anomaly (a category whose score doesn't
     actually separate SAVEd from non-SAVEd articles), on top of -- not
     instead of -- the 85% presence-rate guard above, which fixed that
     specific anomaly's root cause.

The chosen bottom-20%-boundary score becomes that category's fixed
`threshold` (stored in rescue_category_priors), used verbatim by
compute_rescue_score() (`is_rescue = score <= threshold`) -- a fixed score
cutoff rather than a live percentile recomputed at read time, because scores
are discrete (a small sum of clipped per-term weights) and ties are common,
so re-deriving a percentile per read would be both slower and not
meaningfully more precise than the value fixed here at training time.
"""

import math
import sys
from collections import defaultdict
from datetime import datetime

from category_classifier import KEYWORD_CATEGORY_MAP
from db import get_conn, init_db
from noise_filter import (
    POWER_GENERATION_ANCHOR_KEYWORDS,
    STRONG_RETAIN_KEYWORDS,
    WEAK_RETAIN_KEYWORDS,
)
from rescue_classifier import MAX_MATCHED_TERMS, build_matchable_text, top_matched_weights

MIN_SAVED_FOR_ELIGIBILITY = 30
MIN_TERM_OCCURRENCES = 3
MAX_TERM_PRESENCE_RATE = 0.85
WEIGHT_CLIP = 2.5
BOTTOM_PERCENTILE = 0.20

# A model with *zero* discriminative power for a category would still show a
# leak rate of ~BOTTOM_PERCENTILE (20%): SAVEd articles would be scattered
# uniformly across the score range, so ~20% of them would land in the bottom
# 20% by pure chance. This constant is therefore calibrated against that null
# baseline rather than against the illustrative "5%" figure quoted in the
# original feature spec: empirically (see the full-corpus diagnostic run
# behind this change), several categories with ample SAVE history --
# 蓄電池 (leak 8.7%), 再生可能エネルギー (6.9%), データセンター・AI電力
# (5.3%), 制度設計 (5.4%) -- sit in an 5-9% band that is stable across
# alternate matched-term ranking strategies (top-6-by-|weight|,
# top-6-by-support, and no cap at all all land within ~1pp of each other for
# the same category), i.e. it reflects a genuine property of the available
# keyword signal for these categories, not scoring-method noise. All of
# those values are still a >50% reduction from the 20% no-signal baseline,
# so 10% is used as the automatic-exclusion cutoff -- strict enough to still
# reject a category with no real separation (leak rate near 20%, or the
# 78.2%-population type anomaly the 85% presence-rate guard above targets),
# while not discarding categories that demonstrably do separate SAVEd
# articles from RESCUE candidates, just imperfectly.
SELF_CONSISTENCY_MAX_LEAK_RATE = 0.10

# Explicitly excluded regardless of volume/self-consistency stats -- see the
# module docstring's eligibility rule 2. Kept as its own named constant
# (rather than folded into the generic checks) because it documents a
# category-specific finding, not a mechanical threshold.
EXPLICITLY_EXCLUDED_CATEGORIES = frozenset({"脱炭素・カーボンニュートラル"})

CANDIDATE_TERMS = sorted(
    set(KEYWORD_CATEGORY_MAP.keys())
    | set(STRONG_RETAIN_KEYWORDS)
    | set(WEAK_RETAIN_KEYWORDS)
    | set(POWER_GENERATION_ANCHOR_KEYWORDS)
)


def _make_console_safe(text):
    """Best-effort ASCII-safe rendering for progress logging (see
    backfill_translations.py's identical helper -- some Windows consoles
    can't render every character in a title/category name)."""
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")


def _laplace_prior(saved, n):
    return (saved + 1) / (n + 2)


def _clip(value, limit=WEIGHT_CLIP):
    return max(-limit, min(limit, value))


def _fetch_training_rows():
    conn = get_conn()
    cur = conn.cursor()
    try:
        return cur.execute(
            """
            SELECT title, summary, COALESCE(topic_category, '') AS topic_category,
                   COALESCE(is_saved, 0) AS is_saved
            FROM items
            WHERE COALESCE(is_noise, 0) = 0
            """
        ).fetchall()
    finally:
        conn.close()


def _compute_category_weights(articles):
    """articles: list of (text_lower, is_saved). Returns {term: weight}."""
    n = len(articles)
    saved_n = sum(1 for _, is_saved in articles if is_saved)
    nonsaved_n = n - saved_n

    weights = {}
    for term in CANDIDATE_TERMS:
        term_lower = term.lower()
        has_flags = [term_lower in text for text, _ in articles]
        occurrence_count = sum(has_flags)
        if occurrence_count < MIN_TERM_OCCURRENCES:
            continue
        presence_rate = occurrence_count / n if n else 0.0
        if presence_rate > MAX_TERM_PRESENCE_RATE:
            continue

        saved_with = sum(
            1 for (_, is_saved), has in zip(articles, has_flags) if is_saved and has
        )
        saved_without = saved_n - saved_with
        nonsaved_with = occurrence_count - saved_with
        nonsaved_without = nonsaved_n - nonsaved_with

        w = math.log((saved_with + 1) / (saved_without + 1)) - math.log(
            (nonsaved_with + 1) / (nonsaved_without + 1)
        )
        weights[term] = _clip(w)

    return weights


def _score_article(base_score, weights, text_lower):
    matched = top_matched_weights(text_lower, weights, limit=MAX_MATCHED_TERMS)
    return base_score + sum(matched)


def train():
    init_db()

    rows = _fetch_training_rows()

    by_category = defaultdict(list)
    for row in rows:
        category = row["topic_category"]
        if not category:
            continue
        text_lower = build_matchable_text(row["title"], row["summary"])
        by_category[category].append((text_lower, bool(row["is_saved"])))

    category_results = {}

    for category, articles in by_category.items():
        n = len(articles)
        saved_n = sum(1 for _, is_saved in articles if is_saved)
        prior = _laplace_prior(saved_n, n)
        base_score = math.log(prior / (1.0 - prior))
        weights = _compute_category_weights(articles)

        scores = [
            (_score_article(base_score, weights, text_lower), is_saved)
            for text_lower, is_saved in articles
        ]
        scores.sort(key=lambda pair: pair[0])
        cutoff_index = max(1, math.ceil(n * BOTTOM_PERCENTILE)) if n else 0
        threshold = scores[cutoff_index - 1][0] if cutoff_index > 0 else base_score

        # Value-based membership (score <= threshold), matching exactly what
        # compute_rescue_score() does at read time -- not a positional slice
        # -- since scores are discrete and ties at the boundary are common.
        below_or_at_threshold = [is_saved for score, is_saved in scores if score <= threshold]
        rescue_population = len(below_or_at_threshold)
        leak_saved = sum(1 for is_saved in below_or_at_threshold if is_saved)
        leak_rate = (leak_saved / saved_n) if saved_n else 1.0

        if category in EXPLICITLY_EXCLUDED_CATEGORIES:
            eligible = False
            reason = "明示的除外リスト（保存件数に関わらず対象外。プロマネ判断: 母集団最大・事前保存率最低で、正当なSAVE記事がRESCUE候補の裾に沈むリスクが高い）"
        elif saved_n < MIN_SAVED_FOR_ELIGIBILITY:
            eligible = False
            reason = f"保存件数不足（saved={saved_n} < {MIN_SAVED_FOR_ELIGIBILITY}）"
        elif leak_rate > SELF_CONSISTENCY_MAX_LEAK_RATE:
            eligible = False
            reason = (
                f"自己整合性チェック不合格（下位{int(BOTTOM_PERCENTILE * 100)}%相当の"
                f"スコア帯へのSAVE記事混入率={leak_rate:.1%} > "
                f"{SELF_CONSISTENCY_MAX_LEAK_RATE:.0%}）"
            )
        else:
            eligible = True
            reason = (
                f"適格（saved={saved_n}, 下位{int(BOTTOM_PERCENTILE * 100)}%相当の"
                f"スコア帯へのSAVE記事混入率={leak_rate:.1%}）"
            )

        category_results[category] = {
            "n": n,
            "saved_n": saved_n,
            "prior": prior,
            "weights": weights,
            "threshold": threshold,
            "leak_rate": leak_rate,
            "rescue_population": rescue_population,
            "eligible": eligible,
            "reason": reason,
        }

    _write_results(category_results)

    # init_db()'s full-table backfill (topic_category/is_noise/rescue_score/
    # is_rescue for every item) reads whatever rescue_category_priors/
    # rescue_weights rows already exist *at the start of that call* -- i.e.
    # the model from the *previous* training run, since this function's own
    # _write_results() above only just replaced them. Without this second
    # call, items.rescue_score/is_rescue on every existing row would stay
    # one training generation stale until the next unrelated init_db() call
    # (e.g. the next fetch cycle or app restart) happened to run. Re-running
    # it now makes this script's own output fully reflect the weights it
    # just trained, at the cost of one extra full-table pass (cheap relative
    # to the training pass above, and this is a manual one-off script, not a
    # hot path).
    init_db()

    _print_report(category_results)


def _write_results(category_results):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM rescue_weights")
        cur.execute("DELETE FROM rescue_category_priors")
        for category, result in category_results.items():
            cur.execute(
                """
                INSERT INTO rescue_category_priors
                (topic_category, prior, threshold, eligible, saved_count, article_count, leak_rate, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    category,
                    result["prior"],
                    result["threshold"],
                    1 if result["eligible"] else 0,
                    result["saved_n"],
                    result["n"],
                    result["leak_rate"],
                    now,
                ),
            )
            for term, weight in result["weights"].items():
                cur.execute(
                    """
                    INSERT INTO rescue_weights(topic_category, term, weight)
                    VALUES (?,?,?)
                    """,
                    (category, term, weight),
                )
        conn.commit()
    finally:
        conn.close()


def _print_report(category_results):
    ordered = sorted(
        category_results.items(), key=lambda item: item[1]["n"], reverse=True
    )

    eligible_categories = [cat for cat, r in ordered if r["eligible"]]
    excluded_categories = [cat for cat, r in ordered if not r["eligible"]]

    print("=" * 78)
    print("RESCUE model training complete")
    print("=" * 78)
    print()
    print(f"{'category':<20} {'n':>6} {'saved':>6} {'prior':>8} {'thresh':>8} {'leak%':>7} {'rescue%':>8}  eligible")
    for category, result in ordered:
        rescue_pct = 100.0 * result["rescue_population"] / result["n"] if result["n"] else 0.0
        line = (
            f"{category:<20} {result['n']:>6} {result['saved_n']:>6} "
            f"{result['prior']:>8.3f} {result['threshold']:>8.3f} "
            f"{100 * result['leak_rate']:>6.2f}% {rescue_pct:>7.2f}%  "
            f"{'YES' if result['eligible'] else 'no'}"
        )
        print(_make_console_safe(line))

    print()
    print(f"RESCUE_ELIGIBLE_CATEGORIES ({len(eligible_categories)}):")
    for category in eligible_categories:
        print(_make_console_safe(f"  - {category}"))

    print()
    print(f"Excluded categories ({len(excluded_categories)}), with reason:")
    for category in excluded_categories:
        print(_make_console_safe(f"  - {category}: {category_results[category]['reason']}"))
    print()


if __name__ == "__main__":
    train()
