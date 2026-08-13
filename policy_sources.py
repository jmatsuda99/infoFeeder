"""Official sources monitored for electricity-market policy design updates."""

POLICY_DESIGN_SOURCES = (
    {
        "name": "電力・ガス取引監視等委員会",
        "url": "https://www.egc.meti.go.jp/activity/index_emsc.html",
        "category": "制度設計",
        "path_prefix": "/activity/emsc/",
        "title_prefix": "電力・ガス取引監視等委員会",
    },
    {
        "name": "OCCTO 調整力・需給バランス委員会",
        "url": "https://www.occto.or.jp/iinkai/index.html",
        "category": "制度設計",
        "path_prefix": "/iinkai/",
        "title_prefix": "OCCTO 委員会・検討会",
    },
    {
        "name": "資源エネルギー庁 次世代電力・ガス基盤",
        "url": "https://www.meti.go.jp/shingikai/enecho/denryoku_gas/jisedai_kiban/index.html",
        "category": "制度設計",
        "path_prefix": "/shingikai/enecho/denryoku_gas/jisedai_kiban/",
        "title_prefix": "資源エネルギー庁 次世代電力・ガス基盤",
        "meeting_title_required": True,
    },
    {
        "name": "電力・ガス取引監視等委員会 制度設計・監視専門会合",
        "url": "https://www.egc.meti.go.jp/activity/index_systemsurveillance.html",
        "category": "制度設計",
        "path_prefix": "/activity/emsc_systemsurveillance/",
        "title_prefix": "電力・ガス取引監視等委員会 制度設計・監視専門会合",
    },
    {
        "name": "電力・ガス取引監視等委員会 制度設計専門会合",
        "url": "https://www.egc.meti.go.jp/activity/index_system.html",
        "category": "制度設計",
        "path_prefix": "/activity/emsc_system/",
        "title_prefix": "電力・ガス取引監視等委員会 制度設計専門会合",
    },
    {
        "name": "電力事業環境整備WG",
        "url": "https://www.meti.go.jp/shingikai/enecho/denryoku_gas/jisedai_kiban/electric_power_wg/index.html",
        "category": "制度設計",
        "path_prefix": "/shingikai/enecho/denryoku_gas/jisedai_kiban/electric_power_wg/",
        "title_prefix": "電力事業環境整備WG",
        "meeting_title_required": True,
    },
    {
        "name": "電力安定供給WG",
        "url": "https://www.meti.go.jp/shingikai/enecho/denryoku_gas/jisedai_kiban/stable_power_supply_wg/index.html",
        "category": "制度設計",
        "path_prefix": "/shingikai/enecho/denryoku_gas/jisedai_kiban/stable_power_supply_wg/",
        "title_prefix": "電力安定供給WG",
        "meeting_title_required": True,
    },
    {
        "name": "再エネ主力電源化小委",
        "url": "https://www.meti.go.jp/shingikai/enecho/denryoku_gas/saiene_shuryoku/index.html",
        "category": "制度設計",
        "path_prefix": "/shingikai/enecho/denryoku_gas/saiene_shuryoku/",
        "title_prefix": "再エネ主力電源化小委",
        "meeting_title_required": True,
    },
    {
        "name": "次世代電力系統WG",
        "url": "https://www.meti.go.jp/shingikai/enecho/denryoku_gas/saisei_kano/smart_power_grid_wg/index.html",
        "category": "制度設計",
        "path_prefix": "/shingikai/enecho/denryoku_gas/saisei_kano/smart_power_grid_wg/",
        "title_prefix": "次世代電力系統WG",
        "meeting_title_required": True,
    },
)

OFFICIAL_WATCH_SOURCES = (
    {
        "name": "電力広域的運営推進機関 公式お知らせ",
        "url": "https://www.occto.or.jp/",
        "category": "電力市場",
        "path_prefixes": ("/news/",),
        "required_terms": (),
    },
    {
        "name": "OCCTO 会合配布資料",
        "url": "https://www.occto.or.jp/index.html",
        "category": "制度設計",
        "path_prefixes": ("/iinkai/",),
        "required_terms": ("第", "回", "配布資料"),
    },
    {
        "name": "九電グループ 公式発表",
        "url": "https://www.kyuden.co.jp/press/2026/",
        "category": "九電グループ",
        "path_prefixes": ("/press/2026/", "/td/press/2026/"),
        "required_terms": (),
    },
    {
        "name": "JEPX 電力取引に関するお知らせ",
        "url": "https://www.jepx.jp/electricpower/news/",
        "category": "電力市場",
        "path_prefixes": ("/electricpower/news/",),
        "required_terms": (),
        "allowed_extensions": (".pdf",),
    },
    {
        "name": "JERAクロス 公式発表",
        "url": "https://www.jera-cross.com/ja/news",
        "category": "JERAグループ",
        "path_prefixes": ("/ja/news/",),
        "required_terms": (),
        "allowed_extensions": ("",),
    },
    {
        "name": "東京電力ホールディングス 公式発表",
        "url": "https://www.tepco.co.jp/press/index-j.html",
        "category": "事業者動向",
        "path_prefixes": (
            "/press/release/2026/",
            "/press/news/2026/",
            "/pg/company/press-information/press/2026/",
            "/rp/about/company/press-information/press/2026/",
            "/ep/notice/pressrelease/2026/",
        ),
        "required_terms": (),
        "allowed_extensions": (".pdf",),
    },
    {
        "name": "CRIEPI（電力中央研究所）",
        "url": "https://criepi.denken.or.jp/press/pressrelease/index.html",
        "category": "CRIEPI",
        "path_prefixes": (
            "/press/pressrelease/2026/",
            "/press/pressrelease/2025/",
        ),
        "required_terms": (),
    },
    {
        # NOTE: the canonical listing page
        # https://www.nedo.go.jp/news/press/presslist.html is a meta-refresh
        # redirect-only page; urlopen() does not follow it, so it yields no
        # entries. The real article links live on this event listing URL.
        "name": "NEDO（新エネルギー・産業技術総合開発機構）",
        "url": "https://www.nedo.go.jp/form/event.php?f=press.html",
        "category": "NEDO",
        "path_prefixes": ("/news/press/",),
        "required_terms": (),
    },
    {
        # Press releases are direct PDF links; there is no HTML article page.
        "name": "IEEJ（日本エネルギー経済研究所）",
        "url": "https://eneken.ieej.or.jp/press/",
        "category": "IEEJ",
        "path_prefixes": ("/press/",),
        "required_terms": (),
        "allowed_extensions": (".pdf",),
    },
    {
        # Article links are extension-less (e.g. /press-release/<slug>), so
        # the default allowed_extensions=(".html",) filter must be relaxed
        # the same way it is for JERAクロス below.
        "name": "ASEAN Centre for Energy（ACE）",
        "url": "https://aseanenergy.org/press-release/",
        "category": "国際動向",
        "path_prefixes": ("/press-release/",),
        "required_terms": (),
        "allowed_extensions": ("",),
    },
    {
        # Article links are extension-less (e.g. /news/<slug>,
        # /commentaries/<slug>); see ACE note above.
        "name": "IEA（国際エネルギー機関）",
        "url": "https://www.iea.org/news",
        "category": "国際動向",
        "path_prefixes": ("/news/", "/commentaries/"),
        "required_terms": (),
        "allowed_extensions": ("",),
    },
)


UTILITY_RSS_SOURCES = (
    {
        "name": "関西電力 プレスリリース",
        "url": "https://www.kepco.co.jp/corporate/pr/pressre.xml",
        "category": "事業者動向",
    },
    {
        "name": "中部電力 プレスリリース",
        "url": "https://www.chuden.co.jp/rss/press.xml",
        "category": "事業者動向",
    },
    {
        "name": "東北電力 プレスリリース",
        "url": "https://www.tohoku-epco.co.jp/rss/index.xml",
        "category": "事業者動向",
    },
    {
        "name": "北海道電力 プレスリリース",
        "url": "https://www.hepco.co.jp/info/rss/press_rss.xml",
        "category": "事業者動向",
    },
)


# Academic / research-institute sources. Unlike UTILITY_RSS_SOURCES, these are
# NOT registered in category_classifier.LEGACY_FEED_CATEGORY_MAP: a single
# institute publishes across many topics (CCS, batteries, renewables,
# nuclear, ...), so its name is used only as a display badge (feeds.category)
# and each article is still classified individually from its own content.
RESEARCH_RSS_SOURCES = (
    {
        "name": "RITE（地球環境産業技術研究機構）",
        "url": "https://www.rite.or.jp/atom.xml",
        "category": "RITE",
    },
)


# Overseas official/media sources covering North America, Europe, and
# Southeast/Northeast Asia, added to give cross-cutting visibility into
# international trends that domestic-only sources cannot surface. Unlike
# RESEARCH_RSS_SOURCES, these ARE registered in
# category_classifier.LEGACY_FEED_CATEGORY_MAP under "国際動向": what makes
# an article valuable here is that it is overseas news, not its specific
# energy topic, so every article from these sources is grouped under the
# single "国際動向" category regardless of content.
INTERNATIONAL_RSS_SOURCES = (
    {
        "name": "EIA（米国エネルギー情報局）",
        "url": "https://www.eia.gov/rss/press_rss.xml",
        "category": "国際動向",
    },
    {
        "name": "欧州委員会 エネルギー総局（DG ENER）",
        "url": "https://energy.ec.europa.eu/node/2/rss_en",
        "category": "国際動向",
    },
)


COMMITTEE_WATCH_SOURCES = (
    {
        "name": "需給調整市場検討小委員会",
        "url": "https://www.occto.or.jp/_include/json/committees-list_jukyuchousei.json",
        "site_url": "https://www.occto.or.jp/",
        "category": "制度設計",
    },
    {
        "name": "調整力及び需給バランス評価等に関する委員会",
        "url": "https://www.occto.or.jp/_include/json/committees-list_chousei_jukyu.json",
        "site_url": "https://www.occto.or.jp/",
        "category": "制度設計",
    },
    {
        "name": "計画評価及び検証小委員会",
        "url": "https://www.occto.or.jp/_include/json/committees-list_kouikikeitouseibi_hyouka.json",
        "site_url": "https://www.occto.or.jp/",
        "category": "制度設計",
    },
    {
        "name": "容量市場の在り方等に関する検討会（容量市場検討会）",
        "url": "https://www.occto.or.jp/_include/json/committees-list_youryou_kentoukai.json",
        "site_url": "https://www.occto.or.jp/",
        "category": "制度設計",
    },
)


def get_policy_design_source(url):
    return next((source for source in POLICY_DESIGN_SOURCES if source["url"] == url), None)


def get_official_watch_source(url):
    return next((source for source in OFFICIAL_WATCH_SOURCES if source["url"] == url), None)


def get_committee_watch_source(url):
    return next((source for source in COMMITTEE_WATCH_SOURCES if source["url"] == url), None)
