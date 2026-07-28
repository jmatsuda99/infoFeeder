"""Build the saved-article relationship map without persisting derived links."""

from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
from html import unescape
import json
import re

from jst_format import JST, is_recent_article, parse_datetime_value
from webapp.article_groups import build_article_groups
from db import list_articles


_ENGLISH_WORDS = re.compile(r"[a-z0-9][a-z0-9_-]{2,}", re.IGNORECASE)
_JAPANESE_RUNS = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]{3,}")
_HTML_TAGS = re.compile(r"<[^>]+>")
_BOLD_TERMS = re.compile(r"<b>(.*?)</b>", re.IGNORECASE | re.DOTALL)
_LATIN_COMPANY = re.compile(r"\b[A-Z][A-Za-z0-9&.-]*(?:\s+[A-Z][A-Za-z0-9&.-]*)*\b")
_JAPANESE_COMPANY = re.compile(
    r"[A-Za-z0-9&.-]*[\u3040-\u30ff\u3400-\u9fff]{1,20}"
    r"(?:電力|ガス|ホールディングス|エナジー|ソリューション|ポイント|グループ|カンパニー)"
)
_COMMITTEE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff・]{2,40}(?:委員会|審議会|検討会)")
_STOP_WORDS = {
    "about", "after", "again", "and", "are", "article", "articles", "atom", "been",
    "com", "feedburner", "from", "has", "have", "html", "http", "https", "imported",
    "index", "info", "into", "news", "page", "rss", "that", "the", "their", "this",
    "was", "were", "with", "will", "www", "your", "これ", "それ", "ため", "より", "について",
    "として", "による", "発表", "記事", "関連", "最新", "ニュース",
}
_TOPIC_STOP_TERMS = {"エネルギー", "エネルギ", "ネルギー", "ネルギ", "ルギー", "ニュース", "事業", "市場"}
_COMPANY_STOP_TERMS = {
    "AI", "EPC", "ESS", "FIP", "HTML", "Imported", "JEPX", "JST", "Listing",
    "MWh", "O&M", "VPP", "WSJ", "Yahoo",
}
_POWER_MARKETS = ("需給調整市場", "容量市場", "長期脱炭素電源オークション", "JEPX", "電力3市場")


def _keywords(group):
    """Return simple, explainable tokens for English and Japanese titles/summaries."""
    text = f"{group.get('title', '')} {group.get('summary', '')}".lower()
    tokens = {
        word for word in _ENGLISH_WORDS.findall(text)
        if word not in _STOP_WORDS and not word.isdigit()
    }
    for run in _JAPANESE_RUNS.findall(text):
        # Japanese does not use word separators. Three-character fragments avoid
        # linking articles merely because they share a common single character.
        tokens.update(run[index:index + 3] for index in range(len(run) - 2))
    return tokens


def _topic_terms(group):
    """Extract short displayable topic candidates from an article's text."""
    raw_text = f"{group.get('title', '')} {group.get('summary', '')}"
    terms = set()
    for term in _BOLD_TERMS.findall(raw_text):
        clean_term = _HTML_TAGS.sub("", unescape(term)).strip().lower()
        if len(clean_term) >= 3 and clean_term not in _STOP_WORDS:
            terms.add(clean_term)

    text = _HTML_TAGS.sub(" ", unescape(raw_text)).lower()
    terms.update(word for word in _ENGLISH_WORDS.findall(text) if word not in _STOP_WORDS and not word.isdigit())
    for run in _JAPANESE_RUNS.findall(text):
        for length in range(3, min(10, len(run)) + 1):
            terms.update(run[index:index + length] for index in range(len(run) - length + 1))
    return {
        term for term in terms
        if term not in _STOP_WORDS
        and term not in _TOPIC_STOP_TERMS
        and not any(term in stop_term for stop_term in _TOPIC_STOP_TERMS)
        and not any("\u3040" <= character <= "\u309f" for character in term)
    }


def _select_topics(topic_stats, score_key, limit=5):
    """Pick non-overlapping labels so one phrase is not shown several times."""
    selected = []
    for term, stats in sorted(topic_stats.items(), key=lambda item: (-score_key(item[0], item[1]), -len(item[0]), item[0])):
        if stats["count"] < 2:
            continue
        containing_topic = next((current for current in selected if term in current["term"]), None)
        if containing_topic:
            continue
        contained_topic = next((current for current in selected if current["term"] in term), None)
        if contained_topic:
            # Prefer a concrete phrase over its shorter fragment when it covers
            # nearly the same set of articles (e.g. 太陽光発電 over 太陽光).
            if stats["count"] >= contained_topic["count"] * 0.7:
                selected[selected.index(contained_topic)] = {"term": term, **stats}
            continue
        selected.append({"term": term, **stats})
        if len(selected) == limit:
            break
    return selected


def _build_topic_insights(nodes):
    now = datetime.now(JST)
    recent_cutoff = now - timedelta(days=7)
    stats = {}

    for node in nodes:
        published = parse_datetime_value(node["published"])
        is_recent = bool(published and published >= recent_cutoff)
        for term in _topic_terms(node):
            term_stats = stats.setdefault(
                term,
                {"count": 0, "recent_count": 0, "previous_count": 0, "connections": 0},
            )
            term_stats["count"] += 1
            term_stats["connections"] += node["degree"]
            if is_recent:
                term_stats["recent_count"] += 1
            else:
                term_stats["previous_count"] += 1

    hot_topics = _select_topics(
        stats,
        lambda term, item: item["count"] * 4 + item["recent_count"] * 2
        + item["connections"] / max(item["count"], 1) + min(len(term), 10) * 3,
    )
    emerging_topics = _select_topics(
        {
            term: item for term, item in stats.items()
            if item["recent_count"] >= 2 and item["recent_count"] > item["previous_count"]
        },
        lambda term, item: item["recent_count"] * 5 - item["previous_count"] * 2
        + item["connections"] / max(item["count"], 1) + min(len(term), 10) * 3,
    )
    return {"hot_topics": hot_topics, "emerging_topics": emerging_topics}


def _build_map_insights(nodes, edges, topic_insights):
    """Create short, evidence-backed observations for the map page."""
    if not nodes:
        return []

    insights = []
    hot_topics = topic_insights["hot_topics"]
    emerging_topics = topic_insights["emerging_topics"]
    if hot_topics:
        leading = hot_topics[:2]
        labels = "・".join(f"「{topic['term']}」" for topic in leading)
        counts = "、".join(f"{topic['count']}件" for topic in leading)
        insights.append(f"中心テーマは{labels}で、保存記事では{counts}に現れています。")

    hub = max(nodes, key=lambda node: node["degree"])
    hub_title = _HTML_TAGS.sub("", unescape(hub["title"])).strip()
    short_title = hub_title if len(hub_title) <= 56 else f"{hub_title[:56]}…"
    insights.append(f"最も多くの話題をつなぐハブは「{short_title}」で、{hub['degree']}本の関係を持ちます。")

    connected_nodes = sum(node["degree"] > 0 for node in nodes)
    insights.append(
        f"{len(nodes)}件中{connected_nodes}件が少なくとも1件とつながり、関係線は{len(edges):,}本です。"
    )

    if emerging_topics:
        leading = emerging_topics[0]
        insights.append(
            f"「{leading['term']}」は直近7日間で{leading['recent_count']}件、以前は{leading['previous_count']}件で、急浮上の候補です。"
        )
    return insights


def _clean_article_text(node):
    return _HTML_TAGS.sub(" ", unescape(f"{node['title']} {node['summary']}"))


def _rank_attention_entities(nodes, extractor, limit=3):
    entities = {}
    for node in nodes:
        for name in set(extractor(_clean_article_text(node))):
            entry = entities.setdefault(name, {"name": name, "count": 0, "connections": 0})
            entry["count"] += 1
            entry["connections"] += node["degree"]
    return sorted(entities.values(), key=lambda item: (-item["count"], -item["connections"], item["name"]))[:limit]


def _extract_companies(text):
    names = set()
    for name in _LATIN_COMPANY.findall(text):
        if name not in _COMPANY_STOP_TERMS and len(name) >= 3:
            names.add(name)
    for name in _JAPANESE_COMPANY.findall(text):
        if (
            name not in _COMPANY_STOP_TERMS
            and not name.startswith(("FIP", "系統用", "低圧", "高圧"))
            and not any(fragment in name for fragment in ("された", "発電所", "発電された"))
        ):
            names.add(name)
    return names


def _extract_committees(text):
    ignored = {"委員会", "委員会検討会", "委員会・検討会", "検討会"}
    return {name.strip() for name in _COMMITTEE.findall(text) if name.strip() not in ignored}


def _extract_power_markets(text):
    return {market for market in _POWER_MARKETS if market in text}


def _build_attention_insights(nodes):
    return {
        "companies": _rank_attention_entities(nodes, _extract_companies),
        "committees": _rank_attention_entities(nodes, _extract_committees),
        "markets": _rank_attention_entities(nodes, _extract_power_markets),
    }


def _relation(left, right):
    score = 0
    reasons = []

    if left["category"] and left["category"] == right["category"]:
        score += 2
        reasons.append(f"Category: {left['category']}")
    if left["source_name"] and left["source_name"] == right["source_name"]:
        score += 1
        reasons.append(f"Source: {left['source_name']}")

    shared_keywords = sorted(left["keywords"] & right["keywords"])
    if shared_keywords:
        selected_keywords = shared_keywords[:2]
        score += min(len(selected_keywords), 2) * 2
        reasons.append("Keywords: " + ", ".join(selected_keywords))

    # Category alone is intentionally not enough; this keeps large categories
    # from becoming an unreadable complete graph.
    return score, reasons if score >= 3 else []


def get_saved_article_map(limit=80):
    """Return saved article groups and their strongest deterministic relations."""
    df = list_articles("")
    if df.empty:
        return {"nodes": [], "edges": []}

    saved_df = df[df["is_saved"].fillna(0).astype(bool)].copy()
    saved_df = saved_df[saved_df["published"].apply(lambda value: is_recent_article(value, max_age_days=30))]
    groups = build_article_groups(saved_df)
    groups.sort(key=lambda group: (group["saved_at"], group["published"], group["id"]), reverse=True)
    groups = groups[:limit]

    nodes = []
    for group in groups:
        nodes.append(
            {
                "id": str(group["id"]),
                "article_key": group["article_key"],
                "title": group["title"],
                "link": group["link"],
                "summary": group["summary"],
                "source_name": group["source_name"],
                "category": group["category"],
                "published": group["published"],
                "published_display": group["published_display"],
                "saved_at": group["saved_at"],
                "keywords": _keywords(group),
            }
        )

    candidates = []
    for left_index, left in enumerate(nodes):
        for right in nodes[left_index + 1:]:
            score, reasons = _relation(left, right)
            if reasons:
                candidates.append((score, left["id"], right["id"], reasons))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    edge_counts = Counter()
    edges = []
    for score, source, target, reasons in candidates:
        edges.append({"source": source, "target": target, "score": score, "reasons": reasons})
        edge_counts[source] += 1
        edge_counts[target] += 1

    for node in nodes:
        node["degree"] = edge_counts[node["id"]]
        del node["keywords"]
    topic_insights = _build_topic_insights(nodes)
    attention_insights = _build_attention_insights(nodes)
    revision_payload = [
        (node["id"], node["article_key"], node["published"], node["saved_at"])
        for node in nodes
    ]
    revision = sha256(json.dumps(revision_payload, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "nodes": nodes,
        "edges": edges,
        "topic_insights": topic_insights,
        "insights": _build_map_insights(nodes, edges, topic_insights),
        "attention_insights": attention_insights,
        "revision": revision,
    }


def get_saved_article_map_revision():
    """Stable identifier for the saved cards currently represented on the map."""
    return get_saved_article_map()["revision"]
