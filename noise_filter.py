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

# --- Stage-1 rollout: "electricity system as a whole" anchor keywords -----
#
# New project policy narrows what counts as "電力事情そのもの" (the
# electricity situation itself) to the electricity *system*: storage,
# trading, supply-demand, the grid, tariffs/institutions. Because this is a
# large-impact change (James's simulation found 61.2% of the 11,296 held
# articles would become noise-candidates under the new criteria across the
# full taxonomy), it is being rolled out in stages rather than applied
# everywhere at once. Stage 1 (this change) applies the stricter anchor-word
# requirement only to the three topic_category values whose impact was
# smallest in James's simulation: 制度設計 (23.8%), 電力市場 (16.1%),
# 事業者動向 (53.9%). See SYSTEM_ANCHOR_SCOPE_CATEGORIES and the
# topic_category handling in is_noise_article.
#
# Generation-technology categories (再生可能エネルギー, 脱炭素・カーボン
# ニュートラル, 水素・アンモニア, 火力・化石燃料, 原子力, EV・モビリティ,
# データセンター・AI電力, 国際動向, ...) are explicitly OUT of scope for this
# stage-1 change and must keep using the existing STRONG_RETAIN_KEYWORDS-only
# logic unchanged. (脱炭素・カーボンニュートラル was brought into scope by a
# later stage-2 change -- see POWER_GENERATION_ANCHOR_KEYWORDS /
# POWER_GENERATION_ANCHOR_SCOPE_CATEGORIES below, which use a broader
# generation-technology-aware anchor set rather than SYSTEM_ANCHOR_KEYWORDS.
# The other generation-technology categories listed above remain out of
# scope and unchanged.)
SYSTEM_ANCHOR_KEYWORDS = frozenset(
    {
        # 蓄電
        "蓄電池",
        "蓄電所",
        "蓄電システム",
        "ESS",
        "BESS",
        "蓄電",
        # 電力取引・市場
        "電力取引",
        "卸電力",
        "スポット市場",
        "容量市場",
        "需給調整市場",
        "JEPX",
        "OCCTO",
        # 需給
        "需給",
        "電力需給",
        "需給ひっ迫",
        "需給逼迫",
        "需給バランス",
        "需給調整",
        # 系統
        "系統",
        "グリッド",
        "送配電",
        "送電",
        "配電",
        "変電",
        # 料金・制度
        "料金",
        "電気料金",
        "託送",
        "FIT",
        "FIP",
        "再エネ賦課金",
        "電気事業法",
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
    }
)

_SYSTEM_ANCHOR_KEYWORDS_LOWER = tuple(keyword.lower() for keyword in SYSTEM_ANCHOR_KEYWORDS)

# topic_category values (as produced by category_classifier.classify_article)
# that the stage-1 anchor-word requirement applies to. All other
# topic_category values (including "" for callers that don't pass one) skip
# the anchor check entirely and fall through to the unchanged legacy logic.
SYSTEM_ANCHOR_SCOPE_CATEGORIES = frozenset({"制度設計", "電力市場", "事業者動向"})


def _contains_system_anchor_keyword(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in _SYSTEM_ANCHOR_KEYWORDS_LOWER)


# --- Stage-2 rollout: 脱炭素・カーボンニュートラル -------------------------
#
# 脱炭素・カーボンニュートラル (4,750 articles) is next in the staged
# rollout. James's investigation found that the narrow SYSTEM_ANCHOR_KEYWORDS
# set above (storage/trading/supply-demand/grid/tariff/utility-name terms
# only) makes 90.0% of this category noise-candidates -- too strict, because
# this category is fundamentally about *generation* technology (solar,
# wind, nuclear, hydrogen power, PPAs, ...), which SYSTEM_ANCHOR_KEYWORDS
# does not cover at all. A broadened anchor set that adds
# generation/power-source vocabulary relaxes this to 71.9%, which is the
# basis for POWER_GENERATION_ANCHOR_KEYWORDS below.
#
# Two precision problems were found and fixed before rollout:
# - A bare "電気"/"電力" was in the first draft of the broadened list. Both
#   are common substrings of unrelated compounds (most notably "電気自動車"
#   / EV), so keeping them as standalone anchor terms let EV articles with
#   no actual generation/power-source content survive via a substring match
#   on "電気自動車". They are intentionally *not* included here (or anywhere
#   in this set) -- see the id=296/342/364 verification in the noise_filter
#   test/verification notes.
# - "太陽電池" (solar cell/panel manufacturing, e.g. perovskite solar cell
#   articles like id=284) was missing from the draft list entirely, which
#   incorrectly sent genuine solar-cell-industry articles to noise. Added
#   here along with "太陽光パネル".
POWER_GENERATION_ANCHOR_KEYWORDS = SYSTEM_ANCHOR_KEYWORDS | frozenset(
    {
        # 発電・電源（「電気」「電力」の単独語は意図的に含めない -- 上記参照）
        "発電",
        "電源",
        "電源構成",
        "送電",
        "配電",
        # 太陽光・風力
        "太陽光発電",
        "太陽光発電所",
        "風力発電",
        "風力発電所",
        "メガソーラー",
        "洋上風力",
        # 太陽電池（Jamesが指摘した欠落分）
        "太陽電池",
        "太陽光パネル",
        # 原子力・火力・水素
        "原子力発電",
        "原発",
        "火力発電",
        "水素発電",
        "燃料電池発電",
        # PPA・自家消費
        "PPA",
        "自家消費",
        "オフサイトPPA",
        "コーポレートPPA",
        # 電力事業者（一般名詞）
        "電力会社",
        "電力事業者",
        "発電事業者",
        # 単位
        "kWh",
        "kW",
        "MWh",
        "MW",
    }
)

_POWER_GENERATION_ANCHOR_KEYWORDS_LOWER = tuple(
    keyword.lower() for keyword in POWER_GENERATION_ANCHOR_KEYWORDS
)

# topic_category values that the stage-2 (power-generation) anchor-word
# requirement applies to. Disjoint from SYSTEM_ANCHOR_SCOPE_CATEGORIES: a
# topic_category is never in both sets, so is_noise_article applies at most
# one of the two anchor checks.
POWER_GENERATION_ANCHOR_SCOPE_CATEGORIES = frozenset({"脱炭素・カーボンニュートラル"})


def _contains_power_generation_anchor_keyword(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in _POWER_GENERATION_ANCHOR_KEYWORDS_LOWER)

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
        "ebc.com",
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


# ESG-declaration-type noise: articles whose entire content is a company's
# ESG-initiative announcement / certification-acquisition puff piece (e.g.
# "SBT認定取得", "CDP評価A獲得", "「再エネ100宣言」に参加"), matched by a
# specific certification/declaration term (e.g. id=1258760: "「再エネ100宣言」
# 企業が業績好調、広がる事業成長と脱炭素の両立の可能性", reprinted verbatim
# -- same 日刊工業新聞社アンケート -- as id=918372 on PR TIMES and id=1200155
# on 日刊工業新聞, all three matched here via "再エネ100宣言"). These
# previously survived STRONG_RETAIN_KEYWORDS because "再エネ"/"脱炭素" appear
# as generic scene-setting vocabulary, not because the article describes any
# actual electricity procurement or equipment.
#
# A broader pair of catch-all patterns keyed only on generic phrasing
# ("業績好調.{0,20}(脱炭素|再エネ)", "(脱炭素|再エネ).{0,20}(両立|業績)",
# without requiring any certification/declaration-specific term) was tried
# and rejected: on the full corpus it matched 69 of 104 newly-noise articles
# via that phrasing alone -- unrelated real-estate, agriculture, logistics,
# EU-policy, and government-subsidy articles, and worse, genuine
# electricity-industry articles that are supposed to be retained (e.g.
# "北陸電力、発電効率高いLNG火力2号機稼働へ 安定供給と脱炭素両立" -- a
# utility building new generation capacity, forced to noise only because its
# headline uses the common "安定供給と脱炭素(の)両立" formula). "脱炭素/
# 再エネ" co-occurring with "両立"/"業績" within 20 characters is simply the
# standard Japanese energy-journalism headline template and is not specific
# to ESG-declaration puff pieces, so it was dropped; the specific-term
# patterns below already catch all 3 reported articles and produce 35 newly-
# noise matches on the full corpus -- in line with James's ~30 estimate,
# instead of the ~97 the broader pair produced.
ESG_DECLARATION_NOISE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"SBTi?認定",
        r"CDP.{0,10}(評価|スコア)",
        r"再エネ100宣言",
        r"RE\s*Action",
        r"RE100.{0,5}(宣言|加盟|参加)",
    )
)

# Exception terms: if any of these co-occur in the same title + summary as an
# ESG_DECLARATION_NOISE_PATTERNS hit, the article describes concrete
# electricity procurement/equipment (a PPA, a kWh/MW figure, a solar/wind
# installation, self-consumption, battery storage, ...) rather than a bare
# announcement, so it is *not* forced to noise here -- it falls through to
# the normal STRONG_RETAIN_KEYWORDS flow like any other article.
ESG_DECLARATION_RETAIN_EXCEPTIONS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"PPA",
        r"kWh",
        r"MWh",
        r"kW",
        r"MW",
        r"太陽光発電設備",
        r"太陽光導入",
        r"太陽光発電",
        r"メガソーラー",
        r"風力発電",
        r"自家消費",
        r"オフサイト",
        # Real headlines use both orderings ("実質100%再エネ化" and "100%
        # 実質再エネ化", e.g. 豊田通商's id=447308/499385 RE100 articles use
        # the latter) and both a half-width "%" and a full-width "％" (as in
        # id=499385's title "実質100％再エネ化へ") -- match any combination.
        r"実質.{0,6}\d+\s*[%％]",
        r"\d+\s*[%％].{0,6}実質",
        r"蓄電池",
        r"蓄電システム",
    )
)


def _matches_esg_declaration_noise(text):
    if not any(pattern.search(text) for pattern in ESG_DECLARATION_NOISE_PATTERNS):
        return False
    if any(pattern.search(text) for pattern in ESG_DECLARATION_RETAIN_EXCEPTIONS):
        return False
    return True


def is_noise_article(title, summary, link, feed_url, feed_category, topic_category=""):
    """Whether an article should be hidden from the default article list.

    `topic_category` is the value already computed by
    `category_classifier.classify_article()` for this article (callers
    should classify first and pass the result here). It defaults to "" for
    backward compatibility with existing call sites that have not been
    updated; "" behaves the same as any topic_category outside
    SYSTEM_ANCHOR_SCOPE_CATEGORIES (i.e. the stage-1 check below is skipped).

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
    4b. Title + summary is checked against ESG_DECLARATION_NOISE_PATTERNS
        (ESG-initiative-declaration / certification-acquisition puff pieces,
        e.g. "SBT認定取得", "「再エネ100宣言」に参加", or a
        business-performance angle built on one) -- noise, *unless* an
        ESG_DECLARATION_RETAIN_EXCEPTIONS term (PPA, kWh/MW figures, solar/
        wind/battery equipment, 自家消費, オフサイト, 実質N%, ...) co-occurs
        in the same title + summary, in which case this check is skipped
        and the article falls through to the normal STRONG_RETAIN_KEYWORDS
        flow below.
    4c. Stage-1 "electricity system as a whole" anchor check (see
        SYSTEM_ANCHOR_KEYWORDS / SYSTEM_ANCHOR_SCOPE_CATEGORIES): only when
        `topic_category` is one of 制度設計 / 電力市場 / 事業者動向, the
        article is required to contain at least one SYSTEM_ANCHOR_KEYWORDS
        term (storage, trading/market, supply-demand, grid,
        tariff/institution, or a named utility) somewhere in title +
        summary. If it does, the article proceeds to step 5 as normal. If it
        does not, the article is noise -- *regardless* of any
        STRONG_RETAIN_KEYWORDS hit -- because this stage's stricter
        criterion overrides the legacy keyword match for these three
        categories.
    4d. Stage-2 "power generation" anchor check (see
        POWER_GENERATION_ANCHOR_KEYWORDS / POWER_GENERATION_ANCHOR_SCOPE_CATEGORIES):
        only when `topic_category` is 脱炭素・カーボンニュートラル, the
        article is required to contain at least one
        POWER_GENERATION_ANCHOR_KEYWORDS term (everything in
        SYSTEM_ANCHOR_KEYWORDS, plus generation/power-source terms such as
        発電, 太陽光発電, 太陽電池, 原子力発電, PPA, 電力会社, kWh, ...) in
        title + summary. Same all-or-nothing behavior as 4c: if absent, the
        article is noise regardless of STRONG_RETAIN_KEYWORDS. A bare
        "電気"/"電力" is deliberately excluded from this anchor set (it is a
        substring of "電気自動車" and other EV vocabulary, and was found to
        cause EV articles with no real generation content to survive via a
        false substring match).
        Every other topic_category (including "" and the remaining
        generation-technology categories such as 再生可能エネルギー,
        水素・アンモニア, 火力・化石燃料, 原子力, EV・モビリティ,
        データセンター・AI電力, 国際動向, その他) skips both 4c and 4d and
        falls through to step 5 unchanged.
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

    if _matches_esg_declaration_noise(stripped_combined):
        return True

    bold_terms = extract_bold_terms(title_text) + extract_bold_terms(summary_text)
    if bold_terms:
        combined = " ".join(bold_terms)
    else:
        combined = ""

    combined = f"{combined} {stripped_combined}"

    # Stage-1 rollout: for the three in-scope categories only, require an
    # explicit "electricity system as a whole" anchor term before allowing
    # the article to reach the (looser) STRONG_RETAIN_KEYWORDS check below.
    # Categories outside SYSTEM_ANCHOR_SCOPE_CATEGORIES (including "" and
    # every generation-technology category) are untouched by this change.
    if topic_category in SYSTEM_ANCHOR_SCOPE_CATEGORIES and not _contains_system_anchor_keyword(
        combined
    ):
        return True

    # Stage-2 rollout: 脱炭素・カーボンニュートラル uses the broader
    # power-generation anchor set instead of SYSTEM_ANCHOR_KEYWORDS (see
    # POWER_GENERATION_ANCHOR_KEYWORDS). Disjoint from
    # SYSTEM_ANCHOR_SCOPE_CATEGORIES, so at most one of these two anchor
    # checks applies to a given topic_category.
    if (
        topic_category in POWER_GENERATION_ANCHOR_SCOPE_CATEGORIES
        and not _contains_power_generation_anchor_keyword(combined)
    ):
        return True

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
