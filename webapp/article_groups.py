import pandas as pd

from article_utils import article_key, merge_group_key, title_merge_key
from db import (
    get_item_with_feed_by_id,
    list_articles,
    list_articles_by_key,
    list_articles_by_title_key,
)
from jst_format import format_jst_datetime, is_recent_article


def _fill_missing_keys(df):
    article_key_series = df["article_key"].fillna("").astype(str)
    missing_article_key = article_key_series.eq("")
    if missing_article_key.any():
        df.loc[missing_article_key, "article_key"] = df.loc[missing_article_key].apply(
            lambda row: article_key(row["title"], row["link"]),
            axis=1,
        )
    if "title_key" not in df.columns:
        df["title_key"] = ""
    df["title_key"] = df["title_key"].fillna("").astype(str)
    return df


def prepare_article_dataframe(keyword, category=""):
    df = list_articles(keyword, category)
    if df.empty:
        return df

    df = df[df["published"].apply(is_recent_article)].copy()
    if df.empty:
        return df

    df = _fill_missing_keys(df)
    df["is_read"] = df["is_read"].fillna(0).astype(bool)
    df["is_saved"] = df["is_saved"].fillna(0).astype(bool)
    return df


def build_article_groups(df):
    groups = []
    if df.empty:
        return groups

    df = df.copy()
    df["_group_key"] = df.apply(
        lambda row: merge_group_key(row["article_key"], row["title"], row.get("title_key")),
        axis=1,
    )

    for _group_key, group_df in df.groupby("_group_key", sort=False):
        sorted_group = group_df.sort_values(by=["published", "id"], ascending=[False, False]).copy()
        representative = sorted_group.iloc[0]
        groups.append(
            {
                "id": int(representative["id"]),
                "article_key": representative["article_key"],
                "member_article_keys": sorted(set(sorted_group["article_key"].astype(str))),
                "title": representative["title"] or "(no title)",
                "link": representative["link"] or "",
                "source_name": representative["source_name"] or "",
                "category": representative["category"] or "",
                "published": representative["published"] or "",
                "published_display": format_jst_datetime(representative["published"]) if representative["published"] else "",
                "summary": representative["summary"] or "",
                "generated_overview": representative.get("generated_overview", "") or "",
                "generated_overview_error": representative.get("generated_overview_error", "") or "",
                "generated_overview_source": representative.get("generated_overview_source", "") or "",
                "generated_at": representative.get("generated_at", "") or "",
                "is_read": bool(sorted_group["is_read"].any()),
                "is_saved": bool(sorted_group["is_saved"].any()),
                "saved_at": representative.get("saved_at", "") or "",
                "group_count": int(len(sorted_group)),
                "related_articles": [
                    {
                        "id": int(r["id"]),
                        "title": r["title"] or "(no title)",
                        "link": r["link"] or "",
                        "source_name": r["source_name"] or "",
                        "published_display": format_jst_datetime(r["published"]) if r["published"] else "",
                    }
                    for r in sorted_group.head(5).to_dict("records")
                ],
            }
        )

    return groups


def get_article_groups(keyword="", category="", read_filter="all", saved_filter="all", sort_order="newest", limit=50):
    df = prepare_article_dataframe(keyword, category)
    groups = build_article_groups(df)

    if read_filter == "unread":
        groups = [group for group in groups if not group["is_read"]]
    elif read_filter == "read":
        groups = [group for group in groups if group["is_read"]]

    if saved_filter == "saved":
        groups = [group for group in groups if group["is_saved"]]

    reverse = sort_order != "oldest"
    groups.sort(key=lambda group: (group["published"], group["id"]), reverse=reverse)
    if sort_order == "saved":
        groups.sort(key=lambda group: group["is_saved"], reverse=True)
    return groups[:limit]


def _expand_by_title_key(rows):
    """Pull in same-story republishes (other article_keys sharing this title_key)."""
    if not rows:
        return rows
    title_key_value = (rows[0].get("title_key") or "").strip()
    if not title_key_value:
        title_key_value = title_merge_key(rows[0].get("title", ""))
    if not title_key_value:
        return rows
    merged_rows = list_articles_by_title_key(title_key_value)
    return merged_rows if merged_rows else rows


def get_group_article_keys(article_key_value: str):
    """All article_keys that belong to the same displayed card as article_key_value."""
    rows = list_articles_by_key(article_key_value)
    if not rows:
        return [article_key_value]
    rows = _expand_by_title_key(rows)
    keys = sorted({(row.get("article_key") or "").strip() for row in rows if (row.get("article_key") or "").strip()})
    return keys or [article_key_value]


def get_article_group_by_article_key(article_key_value: str):
    """Single merged group for one article_key (after DB update); avoids scanning all articles."""
    rows = list_articles_by_key(article_key_value)
    if not rows:
        return None
    rows = _expand_by_title_key(rows)
    return _first_group_from_item_rows(rows)


def _first_group_from_item_rows(rows):
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df = _fill_missing_keys(df)
    df["is_read"] = df["is_read"].fillna(0).astype(bool)
    df["is_saved"] = df["is_saved"].fillna(0).astype(bool)
    groups = build_article_groups(df)
    return groups[0] if groups else None


def get_article_group_by_id(article_id):
    seed = get_item_with_feed_by_id(article_id)
    if not seed:
        return None
    stored = (seed.get("article_key") or "").strip()
    effective_key = stored if stored else article_key(seed["title"], seed["link"])
    rows = list_articles_by_key(effective_key)
    if not rows:
        rows = [seed]
    else:
        seed_id = int(seed["id"])
        if seed_id not in {int(r["id"]) for r in rows}:
            rows.append(seed)
    rows = _expand_by_title_key(rows)
    return _first_group_from_item_rows(rows)
