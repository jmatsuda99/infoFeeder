"""Article-level topic classification for the fixed 15-category taxonomy.

Feed-level `feeds.category` is either empty (Google Alerts feeds) or just the
media outlet name (industry-media feeds), so it cannot be shown to users as a
meaningful topic. This module derives a per-article topic instead:

- Curated official sources (policy_listing / official_watch / committee_json)
  already carry a trustworthy feed-level category, so it is simply normalized
  onto the new taxonomy.
- Everything else (rss / html_listing, mostly Google Alerts) is classified
  from the `<b>...</b>` terms Google highlights in the title/summary, which
  mark the keyword that matched the alert.
"""

import re

from article_utils import extract_bold_terms

CATEGORY_TAXONOMY = (
    "再生可能エネルギー",
    "蓄電池",
    "原子力",
    "火力・化石燃料",
    "水素・アンモニア",
    "電力系統・グリッド",
    "脱炭素・カーボンニュートラル",
    "データセンター・AI電力",
    "EV・モビリティ",
    "電力市場",
    "制度設計",
    "料金制度・小売",
    "事業者動向",
    "国際動向",
    "その他",
)

OTHER_CATEGORY = "その他"

# Curated sources' feeds.category values, normalized onto CATEGORY_TAXONOMY.
LEGACY_FEED_CATEGORY_MAP = {
    "制度設計": "制度設計",
    "電力市場": "電力市場",
    "九電グループ": "事業者動向",
    "JERAグループ": "事業者動向",
}

_CURATED_SOURCE_TYPES = {"policy_listing", "official_watch", "committee_json"}

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# keyword -> category. Matched by case-insensitive substring against the
# Google-highlighted <b> terms (or, failing that, the raw title/summary
# text). Extend freely as more high-frequency <b> terms are observed.
KEYWORD_CATEGORY_MAP = {
    "蓄電池": "蓄電池",
    "蓄電システム": "蓄電池",
    "蓄電": "蓄電池",
    "太陽光": "再生可能エネルギー",
    "風力": "再生可能エネルギー",
    "再エネ": "再生可能エネルギー",
    "再生可能": "再生可能エネルギー",
    "バイオマス": "再生可能エネルギー",
    "地熱": "再生可能エネルギー",
    "EV": "EV・モビリティ",
    "電気自動車": "EV・モビリティ",
    "モビリティ": "EV・モビリティ",
    "データセンター": "データセンター・AI電力",
    "脱炭素": "脱炭素・カーボンニュートラル",
    "カーボンニュートラル": "脱炭素・カーボンニュートラル",
    "GHG": "脱炭素・カーボンニュートラル",
    "非化石": "脱炭素・カーボンニュートラル",
    "原子力": "原子力",
    "原発": "原子力",
    "LNG": "火力・化石燃料",
    "石炭": "火力・化石燃料",
    "火力": "火力・化石燃料",
    "水素": "水素・アンモニア",
    "アンモニア": "水素・アンモニア",
    "系統": "電力系統・グリッド",
    "グリッド": "電力系統・グリッド",
    "容量市場": "電力市場",
    "需給調整市場": "電力市場",
    "JEPX": "電力市場",
    "委員会": "制度設計",
    "審議会": "制度設計",
    "検討会": "制度設計",
    "専門会合": "制度設計",
    "料金": "料金制度・小売",
    "小売": "料金制度・小売",
}


def _strip_html(text):
    return _HTML_TAG_RE.sub(" ", text or "")


def _score_terms(terms, weight, scores):
    for term in terms:
        term_lower = term.lower()
        for keyword, category in KEYWORD_CATEGORY_MAP.items():
            if keyword.lower() in term_lower:
                scores[category] = scores.get(category, 0) + weight


def classify_article(title, summary, feed_category, source_type):
    """Classify a single article into the new 15-category taxonomy."""
    if source_type in _CURATED_SOURCE_TYPES:
        return LEGACY_FEED_CATEGORY_MAP.get(feed_category, OTHER_CATEGORY)

    title_text = title or ""
    summary_text = summary or ""

    title_terms = extract_bold_terms(title_text)
    summary_terms = extract_bold_terms(summary_text)

    if not title_terms and not summary_terms:
        title_terms = [_strip_html(title_text)]
        summary_terms = [_strip_html(summary_text)]

    scores = {}
    _score_terms(title_terms, 2, scores)
    _score_terms(summary_terms, 1, scores)

    if not scores:
        return OTHER_CATEGORY

    best_category = max(scores.items(), key=lambda item: (item[1], item[0]))[0]
    return best_category
