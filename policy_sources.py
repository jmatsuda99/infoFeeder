"""Official sources monitored for electricity-market policy design updates."""

POLICY_DESIGN_SOURCES = (
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
)

OFFICIAL_WATCH_SOURCES = (
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
)


COMMITTEE_WATCH_SOURCES = (
    {
        "name": "調整力及び需給バランス評価等に関する委員会",
        "url": "https://www.occto.or.jp/_include/json/committees-list_chousei_jukyu.json",
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
