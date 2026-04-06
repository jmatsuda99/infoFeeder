import pandas as pd

from article_utils import article_key
from db import get_item_with_feed_by_id, list_articles, list_articles_by_key
from ui_common import format_jst_datetime


def prepare_article_dataframe(keyword):
    df = list_articles(keyword)
    if df.empty:
        return df

    article_key_series = df["article_key"].fillna("").astype(str)
    missing_article_key = article_key_series.eq("")
    if missing_article_key.any():
        df.loc[missing_article_key, "article_key"] = df.loc[missing_article_key].apply(
            lambda row: article_key(row["title"], row["link"]),
            axis=1,
        )
    df["is_read"] = df["is_read"].fillna(0).astype(bool)
    df["is_saved"] = df["is_saved"].fillna(0).astype(bool)
    return df


def build_article_groups(df):
    groups = []
    if df.empty:
        return groups

    for current_article_key, group_df in df.groupby("article_key", sort=False):
        sorted_group = group_df.sort_values(by=["published", "id"], ascending=[False, False]).copy()
        representative = sorted_group.iloc[0]
        groups.append(
            {
                "id": int(representative["id"]),
                "article_key": current_article_key,
                "title": representative["title"] or "(no title)",
                "link": representative["link"] or "",
                "source_name": representative["source_name"] or "",
                "category": representative["category"] or "",
                "published": representative["published"] or "",
                "published_display": format_jst_datetime(representative["published"]) if representative["published"] else "",
                "summary": representative["summary"] or "",
                "is_read": bool(sorted_group["is_read"].any()),
                "is_saved": bool(sorted_group["is_saved"].any()),
                "group_count": int(len(sorted_group)),
                "related_articles": [
                    {
                        "id": int(row["id"]),
                        "title": row["title"] or "(no title)",
                        "link": row["link"] or "",
                        "source_name": row["source_name"] or "",
                        "published_display": format_jst_datetime(row["published"]) if row["published"] else "",
                    }
                    for _, row in sorted_group.head(5).iterrows()
                ],
            }
        )

    return groups


def get_article_groups(keyword="", read_filter="all", saved_filter="all", sort_order="newest", limit=50):
    df = prepare_article_dataframe(keyword)
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


def _first_group_from_item_rows(rows):
    if not rows:
        return None
    df = pd.DataFrame(rows)
    article_key_series = df["article_key"].fillna("").astype(str)
    missing_article_key = article_key_series.eq("")
    if missing_article_key.any():
        df.loc[missing_article_key, "article_key"] = df.loc[missing_article_key].apply(
            lambda row: article_key(row["title"], row["link"]),
            axis=1,
        )
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
    return _first_group_from_item_rows(rows)
