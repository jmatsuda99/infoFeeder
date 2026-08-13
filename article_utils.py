import html
import re
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse


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


def parse_google_alert_urls(text):
    urls = []
    for line in text.splitlines():
        value = line.strip()
        if not value:
            continue
        if value.startswith("http://") or value.startswith("https://"):
            urls.append(value)
    return urls


def unique_urls(urls):
    seen = set()
    unique = []

    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique.append(url)

    return unique


_JAPANESE_CHAR_PATTERN = re.compile(r"[぀-ヿ㐀-鿿]")


def is_non_japanese_text(text):
    """Return True when text contains no Japanese characters at all.

    Used to decide whether a title/summary needs machine translation before
    it is stored. Empty/None text is treated as "not a translation target"
    (False) rather than "non-Japanese", since there is nothing to translate.
    """
    if not text:
        return False
    if not text.strip():
        return False
    return not _JAPANESE_CHAR_PATTERN.search(text)


def split_source_name_prefix(title, feed_name):
    """Split a "<feed_name>: <article title>" lead-in off of ``title``.

    official_watch/policy_listing/committee_json sources prepend their
    (often Japanese) source name to every article title, e.g.
    "IEA（国際エネルギー機関）: Oil market report". That prefix makes
    is_non_japanese_text() see Japanese characters even when the article
    title itself is entirely non-Japanese, so translation gets skipped.

    Returns (prefix, remainder) where ``prefix`` is "" and remainder is the
    original title unchanged when no such lead-in is present (e.g. plain
    rss/Google Alerts titles), so callers can uniformly do:

        prefix, body = split_source_name_prefix(title, feed_name)
        # ... check/translate body ...
        title = f"{prefix}{body}"
    """
    if feed_name:
        prefix = f"{feed_name}: "
        if title.startswith(prefix):
            return prefix, title[len(prefix):]
    return "", title


_BOLD_TERMS = re.compile(r"<b>(.*?)</b>", re.IGNORECASE | re.DOTALL)


def extract_bold_terms(text):
    """Extract the terms Google Alerts highlights with <b>...</b> tags.

    Returns the cleaned terms (HTML-unescaped, inner tags stripped, whitespace
    collapsed) in the order they appear, keeping duplicates so callers can
    weight repeated hits if they want to.
    """
    terms = []
    for raw_term in _BOLD_TERMS.findall(text or ""):
        clean_term = re.sub(r"<[^>]+>", "", raw_term)
        clean_term = html.unescape(clean_term)
        clean_term = re.sub(r"\s+", " ", clean_term).strip()
        if clean_term:
            terms.append(clean_term)
    return terms


def text_for_copy(title, link):
    clean_title = re.sub(r"<[^>]+>", "", title or "")
    clean_title = html.unescape(clean_title).strip()
    clean_link = (link or "").strip()
    return f"{clean_title}\n{clean_link}".strip()


def normalize_title(title):
    clean_title = re.sub(r"<[^>]+>", "", title or "")
    clean_title = html.unescape(clean_title)
    clean_title = re.sub(r"\s+", " ", clean_title).strip().lower()
    return clean_title


def normalize_article_url(url):
    raw_url = (url or "").strip()
    if not raw_url:
        return ""

    try:
        parsed = urlparse(raw_url)

        if parsed.netloc.endswith("google.com") and parsed.path == "/url":
            query = parse_qs(parsed.query)
            target = query.get("url") or query.get("q")
            if target and target[0]:
                return normalize_article_url(target[0])

        filtered_query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS
        ]
        normalized_path = parsed.path.rstrip("/") or "/"

        return urlunparse(
            parsed._replace(
                scheme=parsed.scheme.lower(),
                netloc=parsed.netloc.lower(),
                path=normalized_path,
                query=urlencode(filtered_query, doseq=True),
                fragment="",
            )
        )
    except Exception:
        return raw_url


def article_key(title, link):
    normalized_link = normalize_article_url(link)
    if normalized_link:
        return f"url:{normalized_link}"

    normalized = normalize_title(title)
    if normalized:
        return f"title:{normalized}"
    return f"link:{(link or '').strip()}"


# Wire-service/press-release stories are routinely re-published under a different
# URL on every portal that picks them up (Yahoo!, TBS NEWS DIG, docomo news, ...),
# so article_key (URL-based) treats each republish as a distinct article. Below
# this length, though, titles are generic enough ("お知らせ", "配布資料") that two
# unrelated items could collide, so only titles at or above this length are used
# to merge same-story duplicates across sources.
TITLE_MERGE_MIN_LENGTH = 10


def title_merge_key(title):
    normalized = normalize_title(title)
    if len(normalized) >= TITLE_MERGE_MIN_LENGTH:
        return normalized
    return ""


def merge_group_key(article_key_value, title, title_key_value=None):
    """Identity used to fold same-story republishes into a single display group."""
    resolved_title_key = (title_key_value or "").strip() or title_merge_key(title)
    if resolved_title_key:
        return f"title:{resolved_title_key}"
    return str(article_key_value or "")


def deduplicate_articles(df):
    working = df.copy()
    working["article_key"] = working.apply(lambda row: article_key(row["title"], row["link"]), axis=1)
    working = (
        working.sort_values(by=["published", "id"], ascending=[False, False])
        .drop_duplicates(subset=["article_key"], keep="first")
    )
    return working
