from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.operation_groups import filters_for_projects, open_overdue_ratio, operation_project_groups, operation_ratio_card
from lib.queries import load_completion_events, load_project_rollup, load_snapshot_trend
from lib.ui import (
    apply_chart_style,
    card,
    format_int,
    format_progress,
    good_ratio_tone,
    notice_tone,
    page_header,
    pressure_tone,
    progress_points,
    ratio_label,
    safe_ratio,
    section_header,
    setup_page,
)


def as_ratio(value):
    points = progress_points(value)
    return None if points is None else points / 100


def signed_int(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.0f} vs range start"


def render_trend_kpis(config, filters, trend, events, projects) -> None:
    ordered = trend.sort_values("snapshot_hour")
    first = ordered.iloc[0]
    latest = ordered.iloc[-1]
    open_issues = int(latest["open_issues"] or 0)
    overdue = int(latest["overdue_issues"] or 0)
    completion = latest["issue_completion_ratio"]
    open_delta = float(latest["open_issues"] - first["open_issues"])
    overdue_delta = float(latest["overdue_issues"] - first["overdue_issues"])
    done_events = int(events["done_events"].sum()) if not events.empty and "done_events" in events else 0
    completed_events = int(events["completed_events"].sum()) if not events.empty else 0
    canceled_events = int(events["canceled_events"].sum()) if not events.empty else 0

    cols = st.columns(6)
    for index, (team_name, _team_note, project_names) in enumerate(operation_project_groups(projects)):
        has_scope = bool(project_names)
        if has_scope:
            team_trend = load_snapshot_trend(config, filters_for_projects(filters, project_names))
            if team_trend.empty:
                has_scope = False
                ratio = 0
                note = "No snapshot data"
            else:
                team_latest = team_trend.sort_values("snapshot_hour").iloc[-1]
                team_open = int(team_latest["open_issues"] or 0)
                team_overdue = int(team_latest["overdue_issues"] or 0)
                ratio = open_overdue_ratio(team_open, team_overdue)
                note = f"{format_int(team_overdue)} overdue now"
        else:
            ratio = 0
            note = "No selected projects"
        with cols[index]:
            operation_ratio_card(team_name, ratio, note, "Latest open not overdue / latest open.", has_scope)

    with cols[2]:
        card(
            "Open trend",
            format_int(open_issues),
            signed_int(open_delta),
            notice_tone(open_delta),
            "Latest open vs range start.",
        )
    with cols[3]:
        card(
            "Completion",
            format_progress(completion),
            "Latest snapshot",
            good_ratio_tone(safe_ratio(completion, 1), warn_at=0.45, good_at=0.7),
            "Completed / (total - canceled).",
        )
    with cols[4]:
        card(
            "Overdue trend",
            format_int(overdue),
            signed_int(overdue_delta),
            pressure_tone(overdue),
            "Latest overdue vs range start.",
        )
    with cols[5]:
        card(
            "Done events",
            format_int(done_events or completed_events),
            f"{format_int(canceled_events)} canceled",
            "good" if (done_events or completed_events) >= canceled_events else "warn",
            "Workflow Done entries inferred from snapshots.",
        )


def main() -> None:
    setup_page("Trends")
    config = load_config()
    page_header("Trends", "Historical movement from hourly snapshots")

    filters = render_global_filters(config)
    trend = load_snapshot_trend(config, filters)
    events = load_completion_events(config, filters)
    projects = load_project_rollup(config, filters)

    section_header("Snapshot trend table", "Hourly operating movement from the snapshot table.", config["snapshot_table"])

    if trend.empty:
        st.warning("No snapshot data in the selected history window.")
        return

    render_trend_kpis(config, filters, trend, events, projects)

    chart_trend = trend.copy()
    chart_trend["avg_project_progress_ratio"] = chart_trend["avg_project_progress"].map(as_ratio)

    fig = go.Figure()
    for column, color in [
        ("open_issues", "#2563eb"),
        ("backlog_issues", "#64748b"),
        ("todo_issues", "#3b82f6"),
        ("in_process_issues", "#d97706"),
        ("review_issues", "#7c3aed"),
        ("done_issues", "#16a34a"),
        ("overdue_issues", "#dc2626"),
        ("canceled_issues", "#475569"),
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
        section_header(
            "Workflow state-change events",
            "Entries into Todo, In Process, Review, Done and Canceled detected between snapshots.",
            config["snapshot_table"],
        )
        fig = go.Figure()
        for column, label, color in [
            ("todo_events", "Todo", "#3b82f6"),
            ("in_process_events", "In Process", "#d97706"),
            ("review_events", "Review", "#7c3aed"),
            ("done_events", "Done", "#16a34a"),
            ("canceled_events", "Canceled", "#64748b"),
        ]:
            if column in events:
                fig.add_trace(
                    go.Bar(
                        x=events["event_date"],
                        y=events[column],
                        name=label,
                        marker_color=color,
                    )
                )
        fig.update_layout(barmode="group")
        st.plotly_chart(apply_chart_style(fig, height=380), width="stretch")
        st.dataframe(events.sort_values("event_date", ascending=False), width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
