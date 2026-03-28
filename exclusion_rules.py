from urllib.parse import urlparse


EXCLUDED_DOMAIN_ALIAS_MAP = {
    "pando": ("pando",),
    "西日本新聞": ("nishinippon",),
    "西日本新聞me": ("nishinippon",),
    "nishinippon": ("nishinippon",),
}

DEFAULT_EXCLUDED_DOMAIN_NAMES = (
    "pando",
    "西日本新聞",
)


def resolve_excluded_domain_keywords(names=None):
    resolved = []
    seen = set()

    for name in names or DEFAULT_EXCLUDED_DOMAIN_NAMES:
        normalized_name = (name or "").strip()
        if not normalized_name:
            continue

        candidates = EXCLUDED_DOMAIN_ALIAS_MAP.get(normalized_name, (normalized_name,))
        for candidate in candidates:
            keyword = candidate.strip().lower()
            if keyword and keyword not in seen:
                seen.add(keyword)
                resolved.append(keyword)

    return tuple(resolved)


def is_excluded_domain_url(url, names=None):
    return is_excluded_domain_url_by_keywords(url, resolve_excluded_domain_keywords(names))


def is_excluded_domain_url_by_keywords(url, keywords):
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return False

    return any(keyword in netloc for keyword in keywords)
