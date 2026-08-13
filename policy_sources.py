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
