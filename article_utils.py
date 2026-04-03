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


def deduplicate_articles(df):
    working = df.copy()
    working["article_key"] = working.apply(lambda row: article_key(row["title"], row["link"]), axis=1)
    working = (
        working.sort_values(by=["published", "id"], ascending=[False, False])
        .drop_duplicates(subset=["article_key"], keep="first")
    )
    return working
