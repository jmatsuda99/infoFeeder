
import sqlite3
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, parse_qs, urlparse, urlunparse

import feedparser

DB_PATH="data/alerts.db"
TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_name",
    "utm_reader",
    "utm_viz_id",
    "utm_pubreferrer",
    "utm_swu",
    "gclid",
    "gclsrc",
    "fbclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "s",
}


def _looks_like_primary_source(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        if "google." in parsed.netloc and parsed.path in ("/url", "/alerts/feeds"):
            return False
        return True
    except Exception:
        return False

def normalize_url(url):
    try:
        p=urlparse(url)

        if p.netloc.endswith("google.com") and p.path == "/url":
            query = parse_qs(p.query)
            target = query.get("url") or query.get("q")
            if target and target[0]:
                return normalize_url(target[0])

        filtered_query = [
            (key, value)
            for key, value in parse_qsl(p.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS
        ]
        normalized_path = p.path.rstrip("/") or "/"

        return urlunparse(
            p._replace(
                scheme=p.scheme.lower(),
                netloc=p.netloc.lower(),
                path=normalized_path,
                query=urlencode(filtered_query, doseq=True),
                fragment=""
            )
        )
    except Exception:
        return url


def resolve_entry_url(entry):
    candidates = []

    for key in ("link", "id"):
        value = entry.get(key, "")
        if value:
            candidates.append(value)

    source = entry.get("source")
    if isinstance(source, dict):
        for key in ("href", "link", "url"):
            value = source.get(key, "")
            if value:
                candidates.append(value)

    for link_info in entry.get("links", []):
        if isinstance(link_info, dict):
            href = link_info.get("href", "")
            if href:
                candidates.append(href)

    normalized_candidates = []
    seen = set()
    for candidate in candidates:
        normalized = normalize_url(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_candidates.append(normalized)

    for candidate in normalized_candidates:
        if _looks_like_primary_source(candidate):
            return candidate

    if normalized_candidates:
        return normalized_candidates[0]

    return ""

def fetch_active_feeds():
    conn=sqlite3.connect(DB_PATH)
    cur=conn.cursor()

    cur.execute("SELECT id,url FROM feeds WHERE is_active=1")
    feeds=cur.fetchall()

    inserted=0

    for feed_id,url in feeds:
        parsed=feedparser.parse(url)

        for e in parsed.entries:
            link = resolve_entry_url(e)
            cur.execute("""
            INSERT OR IGNORE INTO items
            (feed_id,title,link,published,summary,fetched_at)
            VALUES(?,?,?,?,?,?)
            """,(
                feed_id,
                e.get("title",""),
                link,
                e.get("published",""),
                e.get("summary",""),
                datetime.now().isoformat(timespec="seconds")
            ))

            if cur.rowcount > 0:
                inserted += 1

    conn.commit()
    conn.close()

    return inserted
