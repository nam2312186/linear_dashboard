from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.auth import require_login
from lib.constants import WORKFLOW_STATE_LABELS, WORKFLOW_STATE_ORDER


LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
WORKFLOW_COUNT_COLUMNS = [
    (f"{bucket}_issues", label) for bucket, label in WORKFLOW_STATE_LABELS.items()
]
WORKFLOW_STATE_COLORS = {
    "Backlog": "#64748b",
    "Todo": "#2563eb",
    "In Process": "#d97706",
    "Review": "#7c3aed",
    "Done": "#16a34a",
}


def setup_page(title: str) -> None:
    st.set_page_config(
        page_title=f"{title} | Fanme Linear",
        page_icon=LOGO_PATH,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    require_login()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --fanme-bg: #f6f8fb;
            --fanme-panel: #ffffff;
            --fanme-border: #dbe3ef;
            --fanme-text: #0f172a;
            --fanme-muted: #64748b;
            --fanme-blue: #2563eb;
            --fanme-green: #15803d;
            --fanme-amber: #b45309;
            --fanme-red: #b91c1c;
            --fanme-slate: #475569;
        }
        .stApp {
            background: var(--fanme-bg);
        }
        .block-container {
            padding-top: 1.45rem;
            padding-bottom: 3rem;
            max-width: 1480px;
        }
        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--fanme-border);
        }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        section[data-testid="stSidebar"] label {
            font-size: 0.86rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 14px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        div[data-testid="stMetricLabel"] p {
            color: #64748b;
            font-size: 0.82rem;
        }
        div[data-testid="stMetricValue"] {
            color: #0f172a;
            font-size: 1.7rem;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        h1 {
            font-size: 1.85rem;
            margin-bottom: 0.2rem;
        }
        h2, h3 {
            color: var(--fanme-text);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--fanme-border);
            border-radius: 8px;
            overflow: hidden;
            background: #ffffff;
        }
        .fanme-hero {
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 58%, #0f766e 100%);
            border-radius: 8px;
            color: #ffffff;
            padding: 20px 24px;
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 16px 36px rgba(15, 23, 42, 0.16);
            margin-bottom: 18px;
        }
        .fanme-hero-title {
            font-size: 1.55rem;
            font-weight: 740;
            line-height: 1.2;
            margin-bottom: 6px;
        }
        .fanme-hero-subtitle {
            color: rgba(255,255,255,0.82);
            font-size: 0.92rem;
        }
        .fanme-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }
        .fanme-pill {
            display: inline-flex;
            align-items: center;
            padding: 5px 9px;
            border-radius: 999px;
            background: rgba(255,255,255,0.13);
            color: rgba(255,255,255,0.9);
            border: 1px solid rgba(255,255,255,0.18);
            font-size: 0.78rem;
        }
        .fanme-section {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 12px;
            margin: 22px 0 10px;
        }
        .fanme-section-title {
            font-size: 1.08rem;
            font-weight: 740;
            color: var(--fanme-text);
        }
        .fanme-section-subtitle {
            color: var(--fanme-muted);
            font-size: 0.84rem;
            margin-top: 2px;
        }
        .fanme-source {
            display: inline-flex;
            max-width: 100%;
            padding: 4px 8px;
            border: 1px solid var(--fanme-border);
            border-radius: 999px;
            color: var(--fanme-muted);
            background: #ffffff;
            font-size: 0.72rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .fanme-card {
            background: var(--fanme-panel);
            border: 1px solid var(--fanme-border);
            border-radius: 8px;
            padding: 14px 15px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            min-height: 104px;
            position: relative;
            overflow: hidden;
        }
        .fanme-card:before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 4px;
            background: var(--fanme-slate);
        }
        .fanme-card.good:before { background: var(--fanme-green); }
        .fanme-card.warn:before { background: var(--fanme-amber); }
        .fanme-card.danger:before { background: var(--fanme-red); }
        .fanme-card.info:before { background: var(--fanme-blue); }
        .fanme-card-title {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--fanme-muted);
            font-size: 0.76rem;
            font-weight: 680;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .fanme-card-value {
            color: var(--fanme-text);
            font-size: 1.78rem;
            line-height: 1.1;
            font-weight: 780;
            margin-top: 8px;
        }
        .fanme-card-note {
            color: var(--fanme-muted);
            font-size: 0.8rem;
            margin-top: 6px;
            line-height: 1.35;
        }
        .fanme-alert {
            padding: 11px 12px;
            border: 1px solid var(--fanme-border);
            border-radius: 8px;
            background: #ffffff;
        }
        .fanme-alert-label {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--fanme-muted);
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .fanme-alert-value {
            color: var(--fanme-text);
            font-size: 1.35rem;
            font-weight: 760;
            margin-top: 4px;
        }
        .fanme-alert.danger { border-left: 4px solid var(--fanme-red); }
        .fanme-alert.warn { border-left: 4px solid var(--fanme-amber); }
        .fanme-alert.info { border-left: 4px solid var(--fanme-blue); }
        .fanme-alert.good { border-left: 4px solid var(--fanme-green); }
        .fanme-help {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 15px;
            height: 15px;
            border-radius: 999px;
            border: 1px solid #cbd5e1;
            color: #64748b;
            background: #f8fafc;
            font-size: 0.68rem;
            font-weight: 760;
            line-height: 1;
            text-transform: none;
            letter-spacing: 0;
            cursor: help;
            transform: translateY(-1px);
        }
        .fanme-help:hover {
            color: #2563eb;
            border-color: #93c5fd;
            background: #eff6ff;
        }
        .fanme-login {
            max-width: 420px;
            margin: 18vh auto 18px;
            padding: 22px 0 10px;
            text-align: center;
        }
        .fanme-login-title {
            color: var(--fanme-text);
            font-size: 1.55rem;
            line-height: 1.2;
            font-weight: 760;
        }
        .fanme-login-subtitle {
            color: var(--fanme-muted);
            font-size: 0.92rem;
            margin-top: 7px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None) -> None:
    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle or "")
    subtitle_html = f'<div class="fanme-hero-subtitle">{safe_subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="fanme-hero">
            <div class="fanme-hero-title">{safe_title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_int(value: Any) -> str:
    if pd.isna(value):
        return "0"
    return f"{int(value):,}"


def format_progress(value: Any) -> str:
    if pd.isna(value):
        return "0.0%"
    number = float(value)
    if number > 1:
        return f"{number:.1f}%"
    return f"{number:.1%}"


def progress_points(value: Any) -> float | None:
    if pd.isna(value):
        return None
    number = float(value)
    return number if number > 1 else number * 100


def num(value: Any, default: float = 0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def safe_ratio(numerator: Any, denominator: Any) -> float:
    bottom = num(denominator)
    if bottom <= 0:
        return 0
    return max(num(numerator), 0) / bottom


def ratio_label(value: float) -> str:
    return f"{value:.0%}"


def good_ratio_tone(value: float, warn_at: float = 0.85, good_at: float = 0.95) -> str:
    if value >= good_at:
        return "good"
    if value >= warn_at:
        return "warn"
    return "danger"


def pressure_tone(value: Any, warn_at: float = 1, danger_at: float = 10) -> str:
    pressure = num(value)
    if pressure >= danger_at:
        return "danger"
    if pressure >= warn_at:
        return "warn"
    return "good"


def notice_tone(value: Any) -> str:
    return "warn" if num(value) > 0 else "good"


def help_icon(help_text: str | None) -> str:
    if not help_text:
        return ""
    return f'<span class="fanme-help" title="{html.escape(help_text)}">?</span>'


def card(
    label: str,
    value: str,
    note: str = "",
    tone: str = "info",
    help_text: str | None = None,
) -> None:
    safe_label = html.escape(label)
    safe_value = html.escape(value)
    safe_note = html.escape(note)
    help_html = help_icon(help_text)
    st.markdown(
        f"""
        <div class="fanme-card {tone}">
            <div class="fanme-card-title">{safe_label}{help_html}</div>
            <div class="fanme-card-value">{safe_value}</div>
            <div class="fanme-card-note">{safe_note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert_tile(
    label: str,
    value: str,
    tone: str = "info",
    help_text: str | None = None,
) -> None:
    help_html = help_icon(help_text)
    st.markdown(
        f"""
        <div class="fanme-alert {tone}">
            <div class="fanme-alert-label">{html.escape(label)}{help_html}</div>
            <div class="fanme-alert-value">{html.escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None, source: str | None = None) -> None:
    subtitle_html = (
        f'<div class="fanme-section-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    )
    source_html = f'<div class="fanme-source">{html.escape(source)}</div>' if source else ""
    st.markdown(
        f"""
        <div class="fanme-section">
            <div>
                <div class="fanme-section-title">{html.escape(title)}</div>
                {subtitle_html}
            </div>
            {source_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_chart_style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#0f172a", size=12),
        margin=dict(l=10, r=10, t=32, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#ffffff", font_size=12),
    )
    fig.update_xaxes(gridcolor="#edf2f7", zerolinecolor="#edf2f7")
    fig.update_yaxes(gridcolor="#edf2f7", zerolinecolor="#edf2f7")
    return fig


def workflow_state_order(df: pd.DataFrame) -> list[str]:
    if "workflow_state" not in df:
        return WORKFLOW_STATE_ORDER

    values = [str(value) for value in df["workflow_state"].dropna().unique()]
    remaining = {value.casefold(): value for value in values}
    ordered: list[str] = []
    for preferred in WORKFLOW_STATE_ORDER:
        actual = remaining.pop(preferred.casefold(), None)
        if actual is not None:
            ordered.append(actual)

    ordered.extend(sorted(remaining.values(), key=str.casefold))
    return ordered


def workflow_stack_bar(
    df: pd.DataFrame,
    entity_column: str,
    title: str,
    limit: int = 20,
    sort_column: str = "open_issues",
    height: int = 420,
) -> None:
    if df.empty or entity_column not in df:
        no_data()
        return

    count_columns = [column for column, _ in WORKFLOW_COUNT_COLUMNS if column in df]
    if not count_columns:
        no_data()
        return

    sort_by = sort_column if sort_column in df else count_columns[0]
    top = df.sort_values(sort_by, ascending=False).head(limit).copy()
    top[entity_column] = top[entity_column].astype(str)
    entity_order = top[entity_column].tolist()[::-1]

    label_by_column = dict(WORKFLOW_COUNT_COLUMNS)
    chart = top[[entity_column, *count_columns]].melt(
        id_vars=entity_column,
        value_vars=count_columns,
        var_name="workflow_metric",
        value_name="issue_count",
    )
    chart["workflow_state"] = chart["workflow_metric"].map(label_by_column)
    chart = chart[chart["issue_count"].fillna(0) > 0]
    if chart.empty:
        no_data()
        return

    fig = px.bar(
        chart,
        x="issue_count",
        y=entity_column,
        color="workflow_state",
        orientation="h",
        title=title,
        category_orders={
            entity_column: entity_order,
            "workflow_state": list(WORKFLOW_STATE_LABELS.values()),
        },
        labels={
            entity_column: "",
            "issue_count": "Issues",
            "workflow_state": "Workflow state",
        },
        color_discrete_map=WORKFLOW_STATE_COLORS,
    )
    fig.update_layout(showlegend=True)
    st.plotly_chart(apply_chart_style(fig, height=height), width="stretch")


def health_color(value: str | None) -> str:
    normalized = (value or "").lower()
    if normalized in {"ontrack", "on track", "healthy"}:
        return "#15803d"
    if normalized in {"atrisk", "at risk"}:
        return "#b45309"
    if normalized in {"offtrack", "off track"}:
        return "#b91c1c"
    return "#475569"


def no_data() -> None:
    st.info("No data for the selected filters.")


def risk_badge(score: Any) -> str:
    if pd.isna(score):
        return "low"
    value = float(score)
    if value >= 30:
        return "critical"
    if value >= 15:
        return "watch"
    return "low"


def state_bar(df: pd.DataFrame, title: str) -> None:
    if df.empty or "workflow_state" not in df:
        no_data()
        return
    state_totals = df.groupby("workflow_state", as_index=False)["issue_count"].sum()
    fig = px.bar(
        state_totals,
        x="issue_count",
        y="workflow_state",
        orientation="h",
        category_orders={"workflow_state": workflow_state_order(state_totals)},
        labels={"issue_count": "Issues", "workflow_state": "Workflow state"},
        title=title,
        color="workflow_state",
        color_discrete_map=WORKFLOW_STATE_COLORS,
    )
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=45, b=10), showlegend=False)
    st.plotly_chart(fig, width="stretch")
