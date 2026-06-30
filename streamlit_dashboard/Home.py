from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.operation_groups import grouped_project_open_overdue, operation_ratio_card
from lib.queries import (
    load_completion_events,
    load_issue_queue,
    load_kpis,
    load_people_rollup,
    load_project_rollup,
    load_snapshot_trend,
    load_state_breakdown,
    load_team_rollup,
)
from lib.ui import (
    alert_tile,
    apply_chart_style,
    card,
    format_int,
    format_progress,
    good_ratio_tone,
    num,
    page_header,
    progress_points,
    ratio_label,
    safe_ratio,
    section_header,
    setup_page,
    state_bar,
    workflow_stack_bar,
)


def int_value(row: pd.Series, column: str) -> int:
    return int(num(row.get(column, 0)))


def ratio_to_points(value) -> float | None:
    return progress_points(value)


def completion_ratio(row: pd.Series) -> float:
    total_without_canceled = max(
        int_value(row, "total_issues") - int_value(row, "canceled_issues"), 0
    )
    if total_without_canceled == 0:
        return 0
    return int_value(row, "completed_issues") / total_without_canceled


def trend_delta(trend: pd.DataFrame, column: str) -> float | None:
    if trend.empty or column not in trend or len(trend) < 2:
        return None
    ordered = trend.sort_values("snapshot_hour")
    return num(ordered.iloc[-1][column]) - num(ordered.iloc[0][column])


def signed(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "No baseline"
    sign = "+" if value > 0 else ""
    if abs(value) < 1 and suffix == "%":
        return f"{sign}{value:.1%} vs range start"
    return f"{sign}{value:,.0f}{suffix} vs range start"


def risk_tone(value: int, danger_at: int = 10) -> str:
    pressure = num(value)
    if pressure >= danger_at:
        return "danger"
    if pressure > 0:
        return "warn"
    return "good"


def watch_tone(value: int) -> str:
    if value > 0:
        return "warn"
    return "good"


def completion_tone(value: float) -> str:
    if value >= 0.7:
        return "good"
    if value >= 0.45:
        return "warn"
    return "danger"


def render_operating_summary(kpis: pd.DataFrame, trend: pd.DataFrame, projects: pd.DataFrame) -> None:
    if kpis.empty:
        st.info("No current data for the selected filters.")
        return

    row = kpis.iloc[0]
    overdue = int_value(row, "overdue_issues")
    risky_projects = int_value(row, "risky_projects")
    stale = int_value(row, "stale_open_issues")
    unassigned = int_value(row, "unassigned_open_issues")
    due_soon = int_value(row, "due_soon_issues")
    high_priority = int_value(row, "high_priority_open_issues")
    backlog = int_value(row, "backlog_issues")
    todo = int_value(row, "todo_issues")
    in_process = int_value(row, "in_process_issues")
    review = int_value(row, "review_issues")
    completion = completion_ratio(row)
    section_header(
        "Operating cockpit",
        "Current state from the update table, with trend deltas from hourly snapshots.",
    )
    cols = st.columns(6)
    for index, (team_name, ratio, note, has_scope) in enumerate(grouped_project_open_overdue(projects)):
        with cols[index]:
            operation_ratio_card(team_name, ratio, note, "Open not overdue / open.", has_scope)

    with cols[2]:
        card(
            "Open work",
            format_int(row["open_issues"]),
            signed(trend_delta(trend, "open_issues")),
            "info",
            "Open uses Linear lifecycle type; workflow split: Backlog, Todo, In Process, Review.",
        )
    with cols[3]:
        card(
            "Completion",
            format_progress(completion),
            signed(trend_delta(trend, "issue_completion_ratio"), "%"),
            completion_tone(completion),
            "Completed / (total - canceled).",
        )
    with cols[4]:
        card(
            "Overdue",
            format_int(overdue),
            f"{format_int(due_soon)} due in 7 days",
            risk_tone(overdue),
            "Open issue có due date trước hôm nay.",
        )
    with cols[5]:
        card(
            "Risk load",
            format_int(risky_projects),
            f"{format_int(high_priority)} high priority, {format_int(stale)} stale",
            watch_tone(risky_projects + high_priority + stale),
            "Project health at risk/off track; high priority and stale are shown as notice signals.",
        )

    a, b, c, d = st.columns(4)
    with a:
        alert_tile(
            "Unassigned open",
            format_int(unassigned),
            watch_tone(unassigned),
            "Open issue chưa có assignee.",
        )
    with b:
        alert_tile(
            "Stale open",
            format_int(stale),
            watch_tone(stale),
            "Open issue hơn 14 ngày chưa update.",
        )
    with c:
        alert_tile(
            "In Process / Review",
            f"{format_int(in_process)} / {format_int(review)}",
            "info",
            f"Todo {format_int(todo)}; backlog {format_int(backlog)}.",
        )
    with d:
        alert_tile(
            "Avg Linear progress",
            format_progress(row["avg_project_progress"]),
            "good",
            "Trung bình project_progress từ Linear.",
        )


def render_snapshot_trend(trend: pd.DataFrame, snapshot_table: str) -> None:
    section_header(
        "Snapshot trend",
        "Hourly movement of workload, overdue pressure and completion ratio.",
        snapshot_table,
    )
    if trend.empty:
        st.warning("No snapshot data in the selected date range.")
        return

    chart = trend.sort_values("snapshot_hour").copy()
    chart["avg_project_progress_ratio"] = chart["avg_project_progress"].map(
        lambda value: None if pd.isna(value) else num(value) if num(value) <= 1 else num(value) / 100
    )

    left, right = st.columns([1.25, 0.85])
    with left:
        fig = go.Figure()
        for column, label, color, width in [
            ("open_issues", "Open", "#2563eb", 3),
            ("backlog_issues", "Backlog", "#64748b", 2),
            ("todo_issues", "Todo", "#3b82f6", 2),
            ("in_process_issues", "In Process", "#d97706", 2),
            ("review_issues", "Review", "#7c3aed", 2),
            ("done_issues", "Done", "#16a34a", 2),
            ("overdue_issues", "Overdue", "#dc2626", 2),
        ]:
            fig.add_trace(
                go.Scatter(
                    x=chart["snapshot_hour"],
                    y=chart[column],
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=width),
                )
            )
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(apply_chart_style(fig, height=390), width="stretch")

    with right:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=chart["snapshot_hour"],
                y=chart["issue_completion_ratio"],
                mode="lines",
                name="Issue completion",
                line=dict(color="#16a34a", width=3),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=chart["snapshot_hour"],
                y=chart["avg_project_progress_ratio"],
                mode="lines",
                name="Linear progress",
                line=dict(color="#2563eb", width=2),
            )
        )
        fig.update_layout(hovermode="x unified")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(apply_chart_style(fig, height=390), width="stretch")

    latest = chart.sort_values("snapshot_hour", ascending=False).head(12)
    st.dataframe(
        latest,
        width="stretch",
        hide_index=True,
        column_config={
            "issue_completion_ratio": st.column_config.ProgressColumn(
                "issue_completion_ratio",
                min_value=0,
                max_value=1,
                format="%.0f%%",
            ),
            "avg_project_progress": st.column_config.ProgressColumn(
                "avg_project_progress",
                min_value=0,
                max_value=1,
                format="%.0f%%",
            ),
        },
    )


def project_update_frame(projects: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    display = projects.head(limit)[
        [
            "project_name",
            "project_health",
            "project_status_name",
            "project_target_date",
            "project_progress",
            "issue_completion_ratio",
            "open_issues",
            "backlog_issues",
            "todo_issues",
            "in_process_issues",
            "review_issues",
            "done_issues",
            "overdue_issues",
            "due_soon_issues",
            "unassigned_open_issues",
            "stale_open_issues",
            "risk_score",
        ]
    ].copy()
    display["linear_progress_pct"] = display["project_progress"].map(ratio_to_points)
    display["issue_completion_pct"] = display["issue_completion_ratio"].map(ratio_to_points)
    display = display.drop(columns=["project_progress", "issue_completion_ratio"])
    return display


def render_project_portfolio(projects: pd.DataFrame, current_table: str) -> None:
    section_header(
        "Project portfolio",
        "Prioritized by operational risk, open workload and deadline pressure.",
        current_table,
    )
    if projects.empty:
        st.info("No project data for the selected filters.")
        return

    left, right = st.columns([0.9, 1.1])
    with left:
        top_risks = projects.head(12).sort_values("risk_score", ascending=True)
        fig = px.bar(
            top_risks,
            x="risk_score",
            y="project_name",
            orientation="h",
            color="overdue_issues",
            color_continuous_scale=["#dbeafe", "#f59e0b", "#dc2626"],
            labels={"risk_score": "Risk score", "project_name": "Project", "overdue_issues": "Overdue"},
            title="Highest risk projects",
        )
        st.plotly_chart(apply_chart_style(fig, height=410), width="stretch")

    with right:
        fig = px.scatter(
            projects,
            x="open_issues",
            y="issue_completion_ratio",
            size="total_issues",
            color="project_health",
            hover_name="project_name",
            hover_data=["project_status_name", "overdue_issues", "stale_open_issues", "risk_score"],
            labels={
                "open_issues": "Open issues",
                "issue_completion_ratio": "Issue completion",
                "project_health": "Health",
            },
            title="Load vs completion",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(apply_chart_style(fig, height=410), width="stretch")

    st.dataframe(
        project_update_frame(projects),
        width="stretch",
        hide_index=True,
        column_config={
            "linear_progress_pct": st.column_config.ProgressColumn(
                "Linear progress",
                min_value=0,
                max_value=100,
                format="%.0f%%",
            ),
            "issue_completion_pct": st.column_config.ProgressColumn(
                "Issue completion",
                min_value=0,
                max_value=100,
                format="%.0f%%",
            ),
            "risk_score": st.column_config.NumberColumn("risk_score", format="%d"),
        },
    )


def queue_frame(data: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if data.empty:
        return data
    columns = [
        "issue_identifier",
        "issue_title",
        "project_name",
        "assignee_name",
        "issue_priority_label",
        "issue_due_date",
        "days_overdue",
        "days_since_update",
        "workflow_state",
        "issue_url",
    ]
    return data[[column for column in columns if column in data.columns]].head(limit)


def render_attention_queues(
    current_table: str,
    overdue: pd.DataFrame,
    due_soon: pd.DataFrame,
    stale: pd.DataFrame,
    high_priority: pd.DataFrame,
) -> None:
    section_header(
        "Management attention queue",
        "Issues most likely to need ownership, deadline or priority follow-up.",
        current_table,
    )
    tab_overdue, tab_due, tab_stale, tab_priority = st.tabs(
        ["Overdue", "Due soon", "Stale", "High priority"]
    )
    column_config = {"issue_url": st.column_config.LinkColumn("Open")}
    with tab_overdue:
        st.dataframe(queue_frame(overdue), width="stretch", hide_index=True, column_config=column_config)
    with tab_due:
        st.dataframe(queue_frame(due_soon), width="stretch", hide_index=True, column_config=column_config)
    with tab_stale:
        st.dataframe(queue_frame(stale), width="stretch", hide_index=True, column_config=column_config)
    with tab_priority:
        st.dataframe(
            queue_frame(high_priority),
            width="stretch",
            hide_index=True,
            column_config=column_config,
        )


def render_current_mix(state_breakdown: pd.DataFrame, events: pd.DataFrame) -> None:
    section_header("Current work mix", "Workflow state distribution and Done/Canceled movement.")
    left, right = st.columns([1, 1])
    with left:
        state_bar(state_breakdown, "Workflow state mix")
    with right:
        if events.empty:
            st.info("No completion events in the selected snapshot range.")
            return
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=events["event_date"],
                y=events["done_events"] if "done_events" in events else events["completed_events"],
                name="Done",
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
        fig.update_layout(barmode="group", title="Daily workflow closure events")
        st.plotly_chart(apply_chart_style(fig, height=360), width="stretch")


def render_capacity(people: pd.DataFrame, teams: pd.DataFrame, current_table: str) -> None:
    section_header(
        "Capacity and ownership",
        "Where active workload is concentrated by person and team.",
        current_table,
    )
    left, right = st.columns([1, 1])
    with left:
        workflow_stack_bar(
            people,
            "assignee_name",
            "Workflow load by person",
            limit=12,
            height=390,
        )

    with right:
        workflow_stack_bar(
            teams,
            "team_key",
            "Workflow load by team",
            limit=12,
            height=390,
        )


def main() -> None:
    setup_page("Home")
    config = load_config()
    page_header(
        "Fanme Linear Operations",
        "Executive view of project health, task flow, ownership pressure and hourly snapshot trends.",
    )

    filters = render_global_filters(config)

    with st.spinner("Loading Linear operating data from BigQuery..."):
        kpis = load_kpis(config, filters)
        trend = load_snapshot_trend(config, filters)
        projects = load_project_rollup(config, filters, limit=250)
        state_breakdown = load_state_breakdown(config, filters)
        events = load_completion_events(config, filters)
        people = load_people_rollup(config, filters, limit=100)
        teams = load_team_rollup(config, filters)
        overdue = load_issue_queue(config, filters, "overdue", limit=100)
        due_soon = load_issue_queue(config, filters, "due_soon", limit=100)
        stale = load_issue_queue(config, filters, "stale", limit=100)
        high_priority = load_issue_queue(config, filters, "high_priority", limit=100)

    render_operating_summary(kpis, trend, projects)
    render_snapshot_trend(trend, config["snapshot_table"])
    render_project_portfolio(projects, config["current_table"])
    render_attention_queues(config["current_table"], overdue, due_soon, stale, high_priority)
    render_current_mix(state_breakdown, events)
    render_capacity(people, teams, config["current_table"])


if __name__ == "__main__":
    main()
