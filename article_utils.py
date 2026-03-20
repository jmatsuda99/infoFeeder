import html
import re


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


def article_key(title, link):
    normalized = normalize_title(title)
    if normalized:
        return f"title:{normalized}"
    return f"link:{(link or '').strip()}"


def deduplicate_articles(df):
    working = df.copy()
    working["normalized_title"] = working["title"].apply(normalize_title)
    working = (
        working.sort_values(by=["published", "id"], ascending=[False, False])
        .drop_duplicates(subset=["normalized_title"], keep="first")
        .drop(columns=["normalized_title"])
    )
    return working
