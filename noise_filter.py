"""Article-level noise filtering.

Project policy: an article is treated as *noise* (hidden from the article
list, but never deleted from the DB) unless it relates to one of:
- 蓄電池/蓄電システム (batteries / energy storage systems)
- 電力取引 (electricity trading) or something that influences it
- 電力事情そのもの (the electricity situation/industry itself)

Curated sources (see `policy_sources.py`) are feeds that were added one by
one in code because the *entire* feed is inherently about electricity/energy
(a utility's press releases, a government committee's meeting listing, a
research institute's press page, ...). Their articles frequently have thin
titles (e.g. a bare meeting number) that would fail a keyword check even
though the content is unambiguously on-topic, so those feeds skip the text
check entirely and are always treated as non-noise.

Everything else (Google Alerts feeds, and general-purpose industry-media
feeds added via the "Add source" form, e.g. 環境ビジネスオンライン, 日経GX,
rief-jp, スマートジャパン) is judged by keyword presence in the title +
summary: retained if any STRONG_RETAIN_KEYWORDS term is present; a
WEAK_RETAIN_KEYWORDS-only match (generic terms like 委員会/審議会/需給/
料金/小売 that are also common outside the electricity context) is not
enough on its own, and the article is noise otherwise. See
is_noise_article's docstring for the full priority order.
"""

import re
from urllib.parse import urlparse

from article_utils import extract_bold_terms
from category_classifier import KEYWORD_CATEGORY_MAP
from policy_sources import (
    COMMITTEE_WATCH_SOURCES,
    INTERNATIONAL_RSS_SOURCES,
    OFFICIAL_WATCH_SOURCES,
    POLICY_DESIGN_SOURCES,
    RESEARCH_RSS_SOURCES,
    UTILITY_RSS_SOURCES,
)

CURATED_FEED_URLS = frozenset(
    source["url"]
    for source in (
        *POLICY_DESIGN_SOURCES,
        *OFFICIAL_WATCH_SOURCES,
        *COMMITTEE_WATCH_SOURCES,
        *UTILITY_RSS_SOURCES,
        *RESEARCH_RSS_SOURCES,
        *INTERNATIONAL_RSS_SOURCES,
    )
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Keyword universe used to decide whether an article is about the electricity
# situation itself. Starts from the existing topic-classification keywords
# (battery/renewables/nuclear/market/policy terms already curated there) and
# adds general electricity-infrastructure, unit, market, policy, and utility
# terms that classify_article's map does not need but noise-filtering does.
_EXTRA_RETAIN_KEYWORDS = (
    # 電力インフラ・需給語
    "電力",
    "発電",
    "送電",
    "配電",
    "送配電",
    "変電",
    "系統",
    "グリッド",
    "電源",
    "需給",
    "電力需給",
    "停電",
    "電力復旧",
    "電源車",
    "太陽電池",
    "ソーラーシェアリング",
    # 単位
    "kWh",
    "kW",
    "MWh",
    "MW",
    "GWh",
    "GW",
    "キロワット",
    "メガワット",
    # 電力市場・取引語
    "電力取引",
    "卸電力",
    "スポット市場",
    "容量市場",
    "需給調整市場",
    "非化石価値",
    "非化石証書",
    "JEPX",
    "OCCTO",
    # 電力政策・制度語
    "電気事業法",
    "託送",
    "FIT",
    "FIP",
    "再エネ賦課金",
    "電力・ガス",
    "電気料金",
    "電化",
    # 電力系統の需給運用語（一般的な「需給」「委員会」単独より特定性が高い
    # 複合語。広域機関(OCCTO)の需給調整・調整力・供給信頼度関連の委員会名
    # 等で使われ、電力以外の文脈にはほぼ現れない）
    "需給バランス評価",
    "需給調整",
    "供給信頼度",
    # 電力事業者名
    "東京電力",
    "関西電力",
    "中部電力",
    "東北電力",
    "北海道電力",
    "九州電力",
    "四国電力",
    "中国電力",
    "北陸電力",
    "沖縄電力",
    "JERA",
)

_ALL_RETAIN_KEYWORD_CANDIDATES = frozenset(KEYWORD_CATEGORY_MAP.keys()) | frozenset(
    _EXTRA_RETAIN_KEYWORDS
)

# These terms are too generic on their own to prove an article is about the
# electricity situation: they are common vocabulary in unrelated meeting
# bodies/legislation (委員会/審議会/検討会/専門会合), unrelated supply-demand
# topics (需給), or pricing/retail topics outside electricity (料金/小売).
# The rief-jp false-positive cluster investigated alongside id=1250746 was
# largely caused by exactly these terms matching EU ESG-disclosure articles
# (国際サステナビリティ基準審議会, 欧州委員会, ...) and other unrelated
# committee/council/pricing articles.
#
# 原発/原子力 were *not* kept here even though id=1250746's false positive
# was caused by "原発" (matched only inside "反原発"): empirically,
# demoting them to a co-occurrence requirement caused 6 real nuclear-power
# articles (e.g. "3.11から15年、原発事故後の東電に足りなかったもの",
# "「原発11～14基の建て替え必要」政府、2050年代見通しを初明示", France's
# Gravelines plant cooling shutdown) to be misclassified as noise, because
# their title/summary had no other STRONG_RETAIN_KEYWORDS term -- a false
# negative rate far higher than the single false positive being fixed.
# Instead, 原発/原子力 stay in STRONG_RETAIN_KEYWORDS, and the specific
# "反原発"/"脱原発"/"反原子力"/"脱原子力" opposition-phrase wording (the
# actual source of id=1250746's false positive) is stripped out of the text
# before the STRONG_RETAIN_KEYWORDS scan -- see _strip_opposition_phrases.
WEAK_RETAIN_KEYWORDS = frozenset(
    {
        "委員会",
        "審議会",
        "検討会",
        "専門会合",
        "需給",
        "料金",
        "小売",
    }
) & _ALL_RETAIN_KEYWORD_CANDIDATES

# Terms specific enough to electricity/energy that a single occurrence is
# sufficient evidence to retain the article. WEAK_RETAIN_KEYWORDS are simply
# excluded from this set: a WEAK-only match is never, on its own, enough to
# retain an article (see is_noise_article). WEAK_RETAIN_KEYWORDS is kept as
# its own named set purely to document which terms were demoted and why --
# there is no separate "weak co-occurring with strong" check, because that
# condition already implies a STRONG_RETAIN_KEYWORDS match, which the check
# below handles on its own.
STRONG_RETAIN_KEYWORDS = _ALL_RETAIN_KEYWORD_CANDIDATES - WEAK_RETAIN_KEYWORDS

# Case-insensitive matching is needed for the Latin-script keywords (kWh,
# JEPX, FIT, ...); pre-lowering the set once keeps the hot path cheap.
_STRONG_RETAIN_KEYWORDS_LOWER = tuple(keyword.lower() for keyword in STRONG_RETAIN_KEYWORDS)

# "反原発"/"脱原発"/"反原子力"/"脱原子力" are political/social-movement
# phrasing that can appear in articles with nothing to do with the
# electricity situation itself (e.g. id=1250746: a company-law-reform
# article mentioning "反原発の市民団体" only as one of several protest
# groups). These exact compounds are stripped before the
# STRONG_RETAIN_KEYWORDS scan so that a bare "原発"/"原子力" elsewhere in
# the text (the normal case for genuine nuclear-power articles) still
# matches.
_OPPOSITION_PHRASE_RE = re.compile(r"(?:反|脱)(?:原発|原子力)")


def _strip_opposition_phrases(text):
    return _OPPOSITION_PHRASE_RE.sub(" ", text)


# Domains that are dedicated overseas market-research report resellers, or
# individual-stock/investing commentary sites. Their articles frequently
# smuggle in a STRONG_RETAIN_KEYWORDS hit (e.g. "再生可能エネルギー", "EV")
# as a throwaway lead-in phrase while the actual content is an unrelated
# component-market CAGR/size template ad, or stock-price/earnings-outlook
# investor commentary that has nothing to do with the electricity situation
# itself. A domain match here overrides STRONG_RETAIN_KEYWORDS entirely.
NOISE_DOMAIN_BLOCKLIST = frozenset(
    {
        "pando.life",
        "innovations-i.com",
        "sphericalinsights.com",
        "researchnester.jp",
        "sdki.jp",
        "fortunebusinessinsights.com",
        "marketgrowthreports.com",
        "news.550909.com",
        "reportocean.co.jp",
        "gii.co.jp",
        "businessresearchinsights.com",
        "finance.biggo.jp",
        "simplywall.st",
        "moomoo.com",
        "jp.investing.com",
    }
)

# Domain + path-substring combinations that are noise, where only a specific
# account/section of an otherwise legitimate domain is the problem (e.g. one
# note.com author account reposting market-report ads, or one press-release
# syndication path on a local newspaper's site). Unlike
# NOISE_DOMAIN_BLOCKLIST, the rest of the domain is left untouched.
NOISE_PATH_PATTERNS = (
    ("note.com", "/qy_research/"),
    ("the-miyanichi.co.jp", "/pressrelease/dreamnews/"),
)

# Stock template phrasing used by overseas market-research report ads and by
# CAGR/market-size boilerplate. Matched against title + summary as a
# fallback for articles hosted on domains not in NOISE_DOMAIN_BLOCKLIST
# (e.g. syndicated onto a portal/aggregator).
NOISE_TITLE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"市場規模",
        r"CAGR",
        r"市場調査レポート",
        r"市場調査会社",
        r"市場シェア",
        r"主要プレイヤー",
        r"の(日本|世界|北米|中国|欧州|アジア)市場（",
        r"億米ドル",
        r"億ドル(へ|に|到達)",
        r"市場は20\d{2}年",
        r"予測20\d{2}",
        r"20\d{2}年[～\-–—]20\d{2}年",
        r"20\d{2}年から20\d{2}年",
        r"市場インテリジェンスレポート",
        r"業界動向20\d{2}",
        r"売上高予測",
        r"年平均成長率",
    )
)


def _strip_html(text):
    return _HTML_TAG_RE.sub(" ", text or "")


def _contains_strong_retain_keyword(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in _STRONG_RETAIN_KEYWORDS_LOWER)


def _domain_from_link(link):
    try:
        netloc = urlparse(link or "").netloc.lower()
    except Exception:
        return ""

    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Strip a userinfo/port suffix if present (netloc can be
    # "user:pass@host:port"); we only need the bare host.
    netloc = netloc.rsplit("@", 1)[-1]
    netloc = netloc.split(":", 1)[0]

    return netloc


def _is_blocklisted_domain(domain):
    if not domain:
        return False
    return domain in NOISE_DOMAIN_BLOCKLIST or any(
        domain.endswith(f".{blocked}") for blocked in NOISE_DOMAIN_BLOCKLIST
    )


def _matches_noise_path(domain, link):
    if not domain:
        return False

    path = urlparse(link or "").path.lower()
    for noise_domain, noise_path in NOISE_PATH_PATTERNS:
        if domain == noise_domain or domain.endswith(f".{noise_domain}"):
            if noise_path in path:
                return True
    return False


def _matches_noise_title_pattern(text):
    return any(pattern.search(text) for pattern in NOISE_TITLE_PATTERNS)


def is_noise_article(title, summary, link, feed_url, feed_category):
    """Whether an article should be hidden from the default article list.

    Priority order:
    1. Curated feeds (see CURATED_FEED_URLS) are never noise: the feed
       itself was hand-picked as inherently on-topic, so per-article text
       matching would only risk false positives on thin, meeting-number-only
       titles.
    2. The article's own link domain is checked against
       NOISE_DOMAIN_BLOCKLIST (dedicated market-report/investing sites) --
       always noise, regardless of STRONG_RETAIN_KEYWORDS /
       WEAK_RETAIN_KEYWORDS.
    3. The article's own link domain + path is checked against
       NOISE_PATH_PATTERNS (specific accounts/sections on otherwise
       legitimate domains) -- always noise, regardless of
       STRONG_RETAIN_KEYWORDS / WEAK_RETAIN_KEYWORDS.
    4. Title + summary is checked against NOISE_TITLE_PATTERNS (market
       report boilerplate phrasing) -- always noise, regardless of
       STRONG_RETAIN_KEYWORDS / WEAK_RETAIN_KEYWORDS.
    5. Otherwise, judged by keyword presence in title + summary (HTML tags
       stripped, plus any Google-highlighted <b> terms, and with
       "反原発"/"脱原発"/"反原子力"/"脱原子力" opposition-phrase wording
       removed -- see _strip_opposition_phrases):
       - If any STRONG_RETAIN_KEYWORDS term is present, the article is
         retained (not noise) -- these terms are specific enough to
         electricity/energy that a single occurrence is sufficient evidence.
       - WEAK_RETAIN_KEYWORDS terms (e.g. "委員会", "審議会", "需給", "料金",
         "小売" -- generic terms also used in unrelated meeting-body,
         supply-demand, or pricing/retail contexts) are excluded from this
         check entirely: a WEAK-only match is never sufficient on its own.
    6. If no STRONG_RETAIN_KEYWORDS term is found, the article is noise.
    """
    if feed_url in CURATED_FEED_URLS:
        return False

    domain = _domain_from_link(link)

    if _is_blocklisted_domain(domain):
        return True

    if _matches_noise_path(domain, link):
        return True

    title_text = title or ""
    summary_text = summary or ""
    stripped_combined = f"{_strip_html(title_text)} {_strip_html(summary_text)}"

    if _matches_noise_title_pattern(stripped_combined):
        return True

    bold_terms = extract_bold_terms(title_text) + extract_bold_terms(summary_text)
    if bold_terms:
        combined = " ".join(bold_terms)
    else:
        combined = ""

    combined = f"{combined} {stripped_combined}"

    # Strip "反原発"/"脱原発"/"反原子力"/"脱原子力" before the
    # STRONG_RETAIN_KEYWORDS scan so that opposition-phrase-only mentions of
    # 原発/原子力 (e.g. "反原発の市民団体" as one clause in an unrelated
    # company-law article) don't count as a match, while genuine
    # nuclear-power articles (which normally use a bare "原発"/"原子力")
    # still do.
    if _contains_strong_retain_keyword(_strip_opposition_phrases(combined)):
        return False

    # A WEAK_RETAIN_KEYWORDS-only match (no STRONG_RETAIN_KEYWORDS term
    # anywhere in title + summary) is not sufficient evidence that the
    # article is about the electricity situation -- fall through to noise.
    # (No separate check is needed here: co-occurrence with a
    # STRONG_RETAIN_KEYWORDS term was already handled above, so reaching
    # this point means, at best, a weak-only match.)
    return True
