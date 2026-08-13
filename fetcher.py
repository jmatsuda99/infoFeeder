import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, parse_qs, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import feedparser
from article_utils import article_key, is_non_japanese_text, split_source_name_prefix, title_merge_key
from category_classifier import classify_article
from db import get_conn, get_excluded_domain_keywords, set_app_state
from exclusion_rules import is_excluded_domain_url_by_keywords
from noise_filter import is_noise_article
from policy_sources import get_committee_watch_source, get_official_watch_source, get_policy_design_source
from translation import translate_title_summary
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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
FETCH_LOCK_PATH = Path("data/fetch.lock")
FETCH_LOCK_STALE_SECONDS = 15 * 60
MAX_FETCH_WORKERS = 32
SQLITE_MAX_VARIABLES = 900


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


def extract_policy_listing_entries(url):
    """Read only meeting/material links from a curated official policy source."""
    source = get_policy_design_source(url)
    if source is None:
        raise ValueError(f"Unsupported policy listing source: {url}")

    content, _, charset = fetch_url_content(url)
    parser = FeedDiscoveryParser()
    parser.feed(content.decode(charset, errors="ignore"))
    entries = []
    seen = set()
    prefix = source["path_prefix"]
    for href, text in parser.article_links:
        article_url = normalize_url(urljoin(url, href))
        parsed = urlparse(article_url)
        is_source_index = article_url == normalize_url(url)
        if not parsed.path.startswith(prefix) or is_source_index:
            continue
        if parsed.path.endswith("/index.html") and not source.get("allow_index_entries"):
            continue
        if not parsed.path.endswith(".html") or article_url in seen:
            continue
        title = unescape(" ".join(text.split())).strip()
        if not title:
            continue
        if source.get("meeting_title_required") and not re.search(r"第\s*\d+\s*回", title):
            continue
        # EGC's table uses generic anchor labels such as "配布資料". Preserve
        # the meeting identity in the card title by taking its number from URL.
        if source["name"].startswith("電力・ガス取引監視"):
            match = re.search(r"/(\d+)_", parsed.path)
            meeting = f"第{int(match.group(1))}回" if match else "開催情報"
            title = f"{meeting} {title}"
        entries.append(
            {
                "title": f"{source['title_prefix']}: {title}",
                "link": article_url,
                "published": datetime.now().isoformat(timespec="seconds"),
                "summary": "Official policy-design committee update.",
            }
        )
        seen.add(article_url)
        if len(entries) >= 30:
            break
    return entries


def extract_official_watch_entries(url):
    """Extract current, content-bearing links from a curated official watcher."""
    source = get_official_watch_source(url)
    if source is None:
        raise ValueError(f"Unsupported official watch source: {url}")
    content, _, charset = fetch_url_content(url)
    parser = FeedDiscoveryParser()
    parser.feed(content.decode(charset, errors="ignore"))
    entries = []
    seen = set()
    for href, text in parser.article_links:
        article_url = normalize_url(urljoin(url, href))
        parsed = urlparse(article_url)
        if not any(parsed.path.startswith(prefix) for prefix in source["path_prefixes"]):
            continue
        allowed_extensions = source.get("allowed_extensions", (".html",))
        if not parsed.path.endswith(allowed_extensions) or article_url in seen:
            continue
        title = unescape(" ".join(text.split())).strip()
        if not title or not all(term in title for term in source["required_terms"]):
            continue
        entries.append(
            {
                "title": f"{source['name']}: {title}",
                "link": article_url,
                "published": datetime.now().isoformat(timespec="seconds"),
                "summary": "Official organization update.",
            }
        )
        seen.add(article_url)
        if len(entries) >= 30:
            break
    return entries


def extract_committee_watch_entries(url):
    """Read meeting cards with published handouts from an OCCTO JSON listing."""
    source = get_committee_watch_source(url)
    if source is None:
        raise ValueError(f"Unsupported committee watch source: {url}")

    content, _, charset = fetch_url_content(url)
    listing = json.loads(content.decode(charset, errors="ignore"))
    entries = []
    for meeting in listing:
        document_names = {document.get("name") for document in meeting.get("doc_status", [])}
        if "配布資料" not in document_names:
            continue
        title = unescape(" ".join(str(meeting.get("title", "")).split())).strip()
        link = normalize_url(urljoin(source["site_url"], meeting.get("url", "")))
        if not title or not link:
            continue
        agenda = re.sub(r"<[^>]+>", " ", str(meeting.get("agenda", "")))
        entries.append(
            {
                "title": f"{source['name']}: {title} 配布資料",
                "link": link,
                "published": meeting.get("published_date", "") or datetime.now().isoformat(timespec="seconds"),
                "summary": unescape(" ".join(agenda.split())),
            }
        )
        if len(entries) >= 30:
            break
    return entries


def prefetch_read_status(cur, article_keys):
    keys = list({k for k in article_keys if k})
    if not keys:
        return {}
    result = {}
    for start in range(0, len(keys), SQLITE_MAX_VARIABLES):
        chunk = keys[start : start + SQLITE_MAX_VARIABLES]
        placeholders = ",".join("?" * len(chunk))
        cur.execute(
            f"""
            SELECT article_key, MAX(COALESCE(is_read, 0)) AS mr
            FROM items
            WHERE article_key IN ({placeholders})
            GROUP BY article_key
            """,
            chunk,
        )
        for row in cur.fetchall():
            result[row["article_key"]] = row["mr"] or 0
    return result


def insert_feed_rows(
    cur,
    feed_id,
    rows,
    excluded_domain_keywords,
    *,
    feed_url="",
    feed_category="",
    feed_source_type="rss",
    feed_name="",
    force_unread=False,
    skip_existing_links=False,
):
    if not rows:
        return 0

    prepared = []
    keys_for_prefetch = []
    for row in rows:
        title = row["title"]
        link = row["link"]
        published = row["published"]
        summary = row["summary"]
        if not link or is_excluded_domain_url_by_keywords(link, excluded_domain_keywords):
            continue
        # official_watch/policy_listing/committee_json titles are prefixed with
        # the (often Japanese) source name, e.g. "IEA（国際エネルギー機関）: ...".
        # Judge/translate only the article title itself so a Japanese source
        # name does not mask an all-English article title from translation.
        prefix, title_body = split_source_name_prefix(title, feed_name)
        if is_non_japanese_text(title_body):
            translation = translate_title_summary(title_body, summary)
            if translation.ok:
                title = f"{prefix}{translation.title_ja}"
                if translation.summary_ja or not (summary or "").strip():
                    summary = translation.summary_ja
        ak = article_key(title, link)
        tk = title_merge_key(title)
        topic_category = classify_article(title, summary, feed_category, feed_source_type)
        is_noise = 1 if is_noise_article(title, summary, link, feed_url, feed_category) else 0
        prepared.append((title, link, published, summary, ak, tk, topic_category, is_noise))
        keys_for_prefetch.append(ak)

    if not prepared:
        return 0

    read_by_key = {} if force_unread else prefetch_read_status(cur, keys_for_prefetch)
    inserted = 0
    fetched_at = datetime.now().isoformat(timespec="seconds")
    for title, link, published, summary, ak, tk, topic_category, is_noise in prepared:
        if skip_existing_links and cur.execute("SELECT 1 FROM items WHERE link=? LIMIT 1", (link,)).fetchone():
            continue
        existing_read = read_by_key.get(ak, 0)
        cur.execute(
            """
            INSERT OR IGNORE INTO items
            (feed_id,title,link,article_key,title_key,published,summary,topic_category,is_noise,is_read,fetched_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                feed_id,
                title,
                link,
                ak,
                tk,
                published,
                summary,
                topic_category,
                is_noise,
                existing_read,
                fetched_at,
            ),
        )
        if cur.rowcount > 0:
            inserted += 1
            read_by_key[ak] = existing_read

    return inserted


def _fetch_worker(args):
    feed_id, url, source_type = args
    try:
        if source_type == "html_listing":
            entries = extract_html_listing_entries(url)
        elif source_type == "policy_listing":
            entries = extract_policy_listing_entries(url)
        elif source_type == "official_watch":
            entries = extract_official_watch_entries(url)
        elif source_type == "committee_json":
            entries = extract_committee_watch_entries(url)

        if source_type in {"html_listing", "policy_listing", "official_watch", "committee_json"}:
            rows = [
                {
                    "title": e["title"],
                    "link": e["link"],
                    "published": e["published"],
                    "summary": e["summary"],
                }
                for e in entries
            ]
        else:
            parsed = feedparser.parse(url)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                raise ValueError(str(getattr(parsed, "bozo_exception", "Feed parsing failed")))
            rows = []
            for entry in parsed.entries:
                link = resolve_entry_url(entry)
                rows.append(
                    {
                        "title": entry.get("title", "") or "",
                        "link": link or "",
                        "published": entry.get("published", "") or "",
                        "summary": entry.get("summary", "") or "",
                    }
                )
        return {"feed_id": feed_id, "ok": True, "rows": rows, "error": None}
    except Exception as error:
        return {"feed_id": feed_id, "ok": False, "rows": [], "error": str(error)}


def update_feed_fetch_status(cur, feed_id, *, success, error_message=""):
    now = datetime.now().isoformat(timespec="seconds")
    if success:
        cur.execute(
            """
            UPDATE feeds
            SET last_success_at=?, last_error_at=NULL, last_error_message='', updated_at=?
            WHERE id=?
            """,
            (now, now, feed_id),
        )
    else:
        cur.execute(
            """
            UPDATE feeds
            SET last_error_at=?, last_error_message=?, updated_at=?
            WHERE id=?
            """,
            (now, error_message[:500], now, feed_id),
        )


def acquire_fetch_lock():
    Path("data").mkdir(exist_ok=True)

    if FETCH_LOCK_PATH.exists():
        age_seconds = datetime.now().timestamp() - FETCH_LOCK_PATH.stat().st_mtime
        if age_seconds > FETCH_LOCK_STALE_SECONDS:
            FETCH_LOCK_PATH.unlink(missing_ok=True)

    try:
        fd = os.open(str(FETCH_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(datetime.now().isoformat(timespec="seconds"))

    return FETCH_LOCK_PATH


def release_fetch_lock(lock_path):
    if lock_path:
        Path(lock_path).unlink(missing_ok=True)


def fetch_active_feeds(source_type=None):
    lock_path = acquire_fetch_lock()
    if not lock_path:
        return 0

    conn = get_conn()
    cur = conn.cursor()

    try:
        query = "SELECT id,url,source_type,category,name FROM feeds WHERE is_active=1"
        params = []
        if source_type:
            query += " AND source_type=?"
            params.append(source_type)
        cur.execute(query, params)
        feeds = cur.fetchall()
        excluded_domain_keywords = get_excluded_domain_keywords()

        feed_args = [(row["id"], row["url"], row["source_type"]) for row in feeds]

        if not feed_args:
            conn.commit()
            set_app_state("last_fetch_inserted_count", 0)
            return 0

        max_workers = min(MAX_FETCH_WORKERS, max(1, len(feed_args)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_fetch_worker, feed_args))

        results.sort(key=lambda r: r["feed_id"])
        inserted = 0
        for result in results:
            feed_id = result["feed_id"]
            if result["ok"]:
                feed_source_type = next(row["source_type"] for row in feeds if row["id"] == feed_id)
                feed_category = next(row["category"] for row in feeds if row["id"] == feed_id)
                feed_url = next(row["url"] for row in feeds if row["id"] == feed_id)
                feed_name = next(row["name"] for row in feeds if row["id"] == feed_id)
                inserted += insert_feed_rows(
                    cur,
                    feed_id,
                    result["rows"],
                    excluded_domain_keywords,
                    feed_url=feed_url or "",
                    feed_category=feed_category or "",
                    feed_source_type=feed_source_type,
                    feed_name=feed_name or "",
                    force_unread=feed_source_type
                    in {"policy_listing", "official_watch", "committee_json"},
                    skip_existing_links=feed_source_type == "committee_json",
                )
                update_feed_fetch_status(cur, feed_id, success=True)
            else:
                update_feed_fetch_status(cur, feed_id, success=False, error_message=result["error"] or "")

        conn.commit()
        set_app_state("last_fetch_inserted_count", inserted)
        return inserted
    finally:
        conn.close()
        release_fetch_lock(lock_path)
