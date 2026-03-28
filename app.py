from datetime import datetime

import streamlit as st

from article_utils import parse_google_alert_urls, unique_urls
from articles_view import initialize_article_filters, render_articles_tab
from db import init_db
from source_setup_view import render_source_setup_tab
from summary_view import render_summary_metrics
from ui_common import get_next_half_hour, render_app_shell


st.set_page_config(page_title="Google Alerts RSS Viewer", layout="wide")
st.title("Google Alerts RSS Viewer")

init_db()

TAB_SOURCE_SETUP = "ソース設定"
TAB_ARTICLES = "記事一覧"
TAB_OPTIONS = [TAB_SOURCE_SETUP, TAB_ARTICLES]
READ_FILTER_OPTIONS = ["未読", "既読", "すべて"]
SORT_ORDER_OPTIONS = ["新しい順", "古い順", "保存記事を先頭"]


def sync_selected_tab():
    selected_tab = st.session_state.get("main_tabs", TAB_SOURCE_SETUP)
    if selected_tab in TAB_OPTIONS:
        st.session_state.selected_tab = selected_tab
        st.query_params["tab"] = selected_tab


def initialize_selected_tab():
    query_tab = st.query_params.get("tab", TAB_SOURCE_SETUP)
    if query_tab not in TAB_OPTIONS:
        query_tab = TAB_SOURCE_SETUP

    if "selected_tab" not in st.session_state or st.session_state["selected_tab"] not in TAB_OPTIONS:
        st.session_state.selected_tab = query_tab
    elif st.session_state["selected_tab"] != query_tab:
        st.session_state.selected_tab = query_tab

    st.query_params["tab"] = st.session_state["selected_tab"]


def render_main_tabs():
    tab1, tab2 = st.tabs(
        TAB_OPTIONS,
        default=st.session_state["selected_tab"],
        key="main_tabs",
        on_change=sync_selected_tab,
    )

    with tab1:
        render_source_setup_tab(parse_google_alert_urls, unique_urls)

    with tab2:
        render_articles_tab(READ_FILTER_OPTIONS, SORT_ORDER_OPTIONS)


next_auto_fetch_at = get_next_half_hour(datetime.now())
render_app_shell(next_auto_fetch_at)
initialize_selected_tab()
initialize_article_filters(READ_FILTER_OPTIONS, SORT_ORDER_OPTIONS)
render_summary_metrics(next_auto_fetch_at)
render_main_tabs()
