from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.queries import load_completion_events, load_snapshot_trend
from lib.ui import apply_chart_style, page_header, progress_points, section_header, setup_page


def as_ratio(value):
    points = progress_points(value)
    return None if points is None else points / 100


def main() -> None:
    setup_page("Trends")
    config = load_config()
    page_header("Trends", "Historical movement from hourly snapshots")

    filters = render_global_filters(config)
    trend = load_snapshot_trend(config, filters)
    events = load_completion_events(config, filters)

    section_header("Snapshot trend table", "Hourly operating movement from the snapshot table.", config["snapshot_table"])

    if trend.empty:
        st.warning("No snapshot data in the selected history window.")
        return

    chart_trend = trend.copy()
    chart_trend["avg_project_progress_ratio"] = chart_trend["avg_project_progress"].map(as_ratio)

    fig = go.Figure()
    for column, color in [
        ("open_issues", "#2563eb"),
        ("started_issues", "#d97706"),
        ("overdue_issues", "#dc2626"),
        ("completed_issues", "#16a34a"),
        ("canceled_issues", "#64748b"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=trend["snapshot_hour"],
                y=trend[column],
                mode="lines",
                name=column.replace("_", " ").title(),
                line=dict(color=color, width=2),
            )
        )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(apply_chart_style(fig, height=460), width="stretch")

    ratio_fig = go.Figure()
    ratio_fig.add_trace(
        go.Scatter(
            x=trend["snapshot_hour"],
            y=chart_trend["issue_completion_ratio"],
            mode="lines",
            name="Issue completion",
            line=dict(color="#16a34a", width=3),
        )
    )
    ratio_fig.add_trace(
        go.Scatter(
            x=trend["snapshot_hour"],
            y=chart_trend["avg_project_progress_ratio"],
            mode="lines",
            name="Avg Linear project progress",
            line=dict(color="#2563eb", width=2),
        )
    )
    ratio_fig.update_layout(hovermode="x unified")
    ratio_fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(apply_chart_style(ratio_fig, height=340), width="stretch")

    st.dataframe(trend.sort_values("snapshot_hour", ascending=False), width="stretch", hide_index=True)

    if not events.empty:
        section_header("State-change events inferred from snapshots", "Completed and canceled events detected between snapshots.", config["snapshot_table"])
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=events["event_date"],
                y=events["completed_events"],
                name="Completed",
                marker_color="#16a34a",
            )
        )
        fig.add_trace(
            go.Bar(
                x=events["event_date"],
                y=events["canceled_events"],
                name="Canceled",
                marker_color="#64748b",
            )
        )
        fig.update_layout(barmode="group")
        st.plotly_chart(apply_chart_style(fig, height=360), width="stretch")
        st.dataframe(events.sort_values("event_date", ascending=False), width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
