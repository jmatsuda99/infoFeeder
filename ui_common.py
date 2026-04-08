import json
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

from fetcher import fetch_active_feeds
from version import read_app_version


JST = ZoneInfo("Asia/Tokyo")


def fetch_articles_with_feedback(success_message):
    count = fetch_active_feeds()
    st.success(success_message.format(count=count))
    return count


def render_app_shell(next_fetch_at):
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f4f7fb 0%, #eef2f7 100%);
        }
        .block-container {
            max-width: 1180px;
            padding-top: 1.8rem;
            padding-bottom: 2.5rem;
        }
        h1, h2, h3 {
            color: #132238;
            letter-spacing: -0.01em;
        }
        [data-baseweb="tab-list"] {
            gap: 0.4rem;
            background: #e8edf4;
            padding: 0.3rem;
            border-radius: 0.9rem;
        }
        button[data-baseweb="tab"] {
            background: transparent;
            border-radius: 0.7rem;
            color: #425466;
            font-weight: 600;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: #ffffff;
            color: #132238;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.08);
        }
        div[data-testid="stForm"],
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px;
        }
        div[data-testid="stForm"] {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #d9e2ec;
            padding: 1rem 1rem 0.4rem 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #d9e2ec;
            padding: 0.9rem 1rem;
            border-radius: 14px;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stMetric"] label {
            color: #5b6b7d;
            font-weight: 600;
        }
        div[data-testid="stMetricValue"] {
            color: #132238;
        }
        .if-muted {
            color: #5b6b7d;
            font-size: 0.95rem;
        }
        .if-card-title {
            color: #132238;
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.2rem;
        }
        .if-badge {
            display: inline-block;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            background: #e7eef7;
            color: #28435c;
            font-size: 0.76rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }
        .if-badge-muted {
            background: #eef2f6;
            color: #526273;
        }
        .if-meta-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.9rem;
            margin-top: 0.45rem;
        }
        .if-meta-item {
            color: #526273;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .if-page-intro {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #d9e2ec;
            border-radius: 18px;
            padding: 1rem 1.15rem;
            margin-bottom: 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        .if-control-panel {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #d9e2ec;
            border-radius: 16px;
            padding: 1rem 1rem 0.25rem 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stCheckbox"] label,
        div[data-testid="stToggle"] label {
            font-weight: 600;
        }
        .stButton > button {
            border-radius: 10px;
            border: 1px solid #c7d3e0;
            background: #f8fafc;
            color: #18324b;
            font-weight: 600;
        }
        .stButton > button[kind="primary"] {
            background: #23415f;
            color: #ffffff;
            border-color: #23415f;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="if-page-intro">
            <div class="if-card-title">Google Alerts RSS Viewer</div>
            <div class="if-muted">Ver.{read_app_version()}</div>
            <div class="if-muted">ソースを管理し、未読記事を確認し、30分ごとに自動更新します。次回取得予定: {format_jst_datetime(next_fetch_at, include_date=True)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_jst_datetime(value, include_date=False):
    dt = None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return value

    if dt is None:
        return ""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    else:
        dt = dt.astimezone(JST)

    if include_date:
        return dt.strftime("%Y-%m-%d %H:%M JST")
    return dt.strftime("%Y-%m-%d %H:%M:%S JST")


def format_jst_time(value):
    dt = None

    if isinstance(value, datetime):
        dt = value
    else:
        formatted = format_jst_datetime(value)
        if not formatted:
            return ""
        return formatted.split(" ")[1]

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    else:
        dt = dt.astimezone(JST)
    return dt.strftime("%H:%M")


def get_next_half_hour(now):
    next_half_hour = now.replace(second=0, microsecond=0)
    if now.minute < 30:
        next_half_hour = next_half_hour.replace(minute=30)
    else:
        next_half_hour = (next_half_hour + timedelta(hours=1)).replace(minute=0)
    return next_half_hour


def render_scheduled_reload(next_fetch_at, now):
    target_timestamp_ms = int(next_fetch_at.timestamp() * 1000)
    components.html(
        f"""
        <script>
        const targetTime = {target_timestamp_ms};
        const checkAndReload = () => {{
            if (Date.now() >= targetTime) {{
                // スリープ復帰直後の不安定な時間を考慮し、2秒待ってからリロード
                setTimeout(() => window.parent.location.reload(), 2000);
            }} else {{
                // 5秒おきにチェック（スリープ中の時間経過を検知可能にする）
                setTimeout(checkAndReload, 5000);
            }}
        }};
        checkAndReload();
        </script>
        """,
        height=0,
    )


def render_copy_button(copy_text, key):
    button_id = f"copy-button-{key}"
    payload = json.dumps(copy_text)
    html_block = f"""
    <button id="{button_id}" style="
        background:#f3f4f6;
        border:1px solid #d1d5db;
        border-radius:6px;
        padding:0.35rem 0.75rem;
        cursor:pointer;
        font-size:0.9rem;
    ">コピー</button>
    <script>
    const button = document.getElementById("{button_id}");
    if (button) {{
        button.onclick = async () => {{
            try {{
                await navigator.clipboard.writeText({payload});
                const original = button.innerText;
                button.innerText = "コピー済み";
                setTimeout(() => button.innerText = original, 1200);
            }} catch (error) {{
                button.innerText = "失敗";
            }}
        }};
    }}
    </script>
    """
    components.html(html_block, height=40)
