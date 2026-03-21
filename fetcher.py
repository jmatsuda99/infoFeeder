
import sqlite3
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, parse_qs, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import feedparser
from article_utils import article_key

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
RSS_CONTENT_TYPES = ("application/rss+xml", "application/atom+xml", "application/xml", "text/xml")
USER_AGENT = "infoFeeder/1.0"


class FeedDiscoveryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.feed_links = []
        self.article_links = []
        self._current_anchor_href = ""
        self._current_anchor_text = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "link":
            rel = attributes.get("rel", "").lower()
            type_value = attributes.get("type", "").lower()
            href = attributes.get("href", "")
            if "alternate" in rel and href and type_value in RSS_CONTENT_TYPES:
                self.feed_links.append((href, type_value))
        if tag == "a":
            self._current_anchor_href = attributes.get("href", "")
            self._current_anchor_text = []

    def handle_data(self, data):
        if self._current_anchor_href:
            self._current_anchor_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._current_anchor_href:
            text = unescape(" ".join(self._current_anchor_text)).strip()
            self.article_links.append((self._current_anchor_href, text))
            self._current_anchor_href = ""
            self._current_anchor_text = []


def fetch_url_content(url):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        content = response.read()
        content_type = response.headers.get_content_type().lower()
        charset = response.headers.get_content_charset() or "utf-8"
    return content, content_type, charset


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


def _is_probable_feed(parsed):
    return bool(parsed.entries) or bool(getattr(parsed, "version", ""))


def _looks_like_article_link(base_netloc, candidate_url, text):
    parsed = urlparse(candidate_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    if parsed.netloc != base_netloc:
        return False
    if parsed.path in ("", "/"):
        return False
    if any(part in parsed.path.lower() for part in ("/tag/", "/category/", "/author/", "/search")):
        return False
    if len(text.strip()) < 8:
        return False
    return True


def discover_feed_source(base_url):
    normalized_base_url = normalize_url(base_url)
    content, content_type, charset = fetch_url_content(normalized_base_url)
    parsed_feed = feedparser.parse(content)
    if _is_probable_feed(parsed_feed) or content_type in RSS_CONTENT_TYPES:
        return {
            "source_type": "rss",
            "fetch_url": normalized_base_url,
            "base_url": normalized_base_url,
            "detail": "Direct feed detected.",
        }

    parser = FeedDiscoveryParser()
    parser.feed(content.decode(charset, errors="ignore"))
    if parser.feed_links:
        feed_url = normalize_url(urljoin(normalized_base_url, parser.feed_links[0][0]))
        return {
            "source_type": "rss",
            "fetch_url": feed_url,
            "base_url": normalized_base_url,
            "detail": "RSS/Atom feed discovered from page metadata.",
        }

    return {
        "source_type": "html_listing",
        "fetch_url": normalized_base_url,
        "base_url": normalized_base_url,
        "detail": "Falling back to HTML listing.",
    }


def extract_html_listing_entries(url):
    content, _, charset = fetch_url_content(url)
    parser = FeedDiscoveryParser()
    parser.feed(content.decode(charset, errors="ignore"))

    base_netloc = urlparse(url).netloc
    entries = []
    seen = set()
    for href, text in parser.article_links:
        article_url = normalize_url(urljoin(url, href))
        if not _looks_like_article_link(base_netloc, article_url, text):
            continue
        if article_url in seen:
            continue
        seen.add(article_url)
        entries.append({
            "title": text,
            "link": article_url,
            "published": datetime.now().isoformat(timespec="seconds"),
            "summary": "Imported from HTML listing.",
        })
        if len(entries) >= 30:
            break

    return entries


def insert_item(cur, feed_id, title, link, published, summary):
    current_article_key = article_key(title, link)
    existing_read = cur.execute(
        "SELECT MAX(COALESCE(is_read, 0)) FROM items WHERE article_key=?",
        (current_article_key,)
    ).fetchone()[0] or 0
    cur.execute("""
    INSERT OR IGNORE INTO items
    (feed_id,title,link,article_key,published,summary,is_read,fetched_at)
    VALUES(?,?,?,?,?,?,?,?)
    """,(
        feed_id,
        title,
        link,
        current_article_key,
        published,
        summary,
        existing_read,
        datetime.now().isoformat(timespec="seconds")
    ))
    return cur.rowcount > 0

def fetch_active_feeds():
    conn=sqlite3.connect(DB_PATH)
    cur=conn.cursor()

    cur.execute("SELECT id,url,source_type FROM feeds WHERE is_active=1")
    feeds=cur.fetchall()

    inserted=0

    for feed_id,url,source_type in feeds:
        if source_type == "html_listing":
            entries = extract_html_listing_entries(url)
            for entry in entries:
                if insert_item(cur, feed_id, entry["title"], entry["link"], entry["published"], entry["summary"]):
                    inserted += 1
            continue

        parsed=feedparser.parse(url)

        for e in parsed.entries:
            link = resolve_entry_url(e)
            if insert_item(
                cur,
                feed_id,
                e.get("title",""),
                link,
                e.get("published",""),
                e.get("summary","")
            ):
                inserted += 1

    conn.commit()
    conn.close()

    return inserted
