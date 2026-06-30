from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.operation_groups import render_project_operation_by_team
from lib.queries import load_project_rollup, load_project_timeline
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
    workflow_stack_bar,
)


RISKY_HEALTHS = {"atrisk", "at risk", "offtrack", "off track"}


def render_project_kpis(projects: pd.DataFrame) -> None:
    project_count = len(projects)
    open_issues = int(projects["open_issues"].sum())
    overdue_issues = int(projects["overdue_issues"].sum())
    unassigned_open = int(projects["unassigned_open_issues"].sum())
    stale_open = int(projects["stale_open_issues"].sum())
    risky_projects = int(projects["project_health"].str.lower().isin(RISKY_HEALTHS).sum())
    completed = int(projects["completed_issues"].sum())
    todo = int(projects["todo_issues"].sum())
    in_flow = int((projects["in_process_issues"] + projects["review_issues"]).sum())
    non_canceled = int((projects["total_issues"] - projects["canceled_issues"]).sum())
    completion = safe_ratio(completed, non_canceled)
    stable_projects = projects[
        (projects["overdue_issues"] == 0)
        & (projects["stale_open_issues"] == 0)
        & (projects["unassigned_open_issues"] == 0)
        & ~projects["project_health"].str.lower().isin(RISKY_HEALTHS)
    ]
    operating_ratio = safe_ratio(len(stable_projects), project_count)

    cols = st.columns(5)
    with cols[0]:
        card(
            "Operating ratio",
            ratio_label(operating_ratio),
            f"{format_int(len(stable_projects))}/{format_int(project_count)} stable projects",
            good_ratio_tone(operating_ratio),
            "Stable projects / total projects shown.",
        )
    with cols[1]:
        card(
            "Project load",
            format_int(project_count),
            f"{format_int(open_issues)} open issues",
            "info",
            f"Todo {format_int(todo)}; In Process/Review {format_int(in_flow)}.",
        )
    with cols[2]:
        card(
            "Issue completion",
            format_progress(completion),
            f"{format_int(completed)} completed",
            good_ratio_tone(completion, warn_at=0.45, good_at=0.7),
            "Completed / (total - canceled).",
        )
    with cols[3]:
        card(
            "Deadline pressure",
            format_int(overdue_issues),
            f"{format_int(risky_projects)} risky projects",
            pressure_tone(overdue_issues) if overdue_issues else notice_tone(risky_projects),
            "Overdue open issues; risky projects are shown as notice when there is no overdue work.",
        )
    with cols[4]:
        card(
            "Ownership gap",
            format_int(unassigned_open),
            f"{format_int(stale_open)} stale open",
            pressure_tone(stale_open) if stale_open else notice_tone(unassigned_open),
            "Stale open drives warning; unassigned open is shown as notice.",
        )


def render_project_maps(projects: pd.DataFrame) -> None:
    left, right = st.columns([1.1, 1])

    with left:
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
                "issue_completion_ratio": "Issue completion %",
                "project_health": "Health",
            },
            title="Project load vs issue completion",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(apply_chart_style(fig, height=430), width="stretch")

    with right:
        top_risks = projects.head(15).sort_values("risk_score", ascending=True)
        fig = px.bar(
            top_risks,
            x="risk_score",
            y="project_name",
            orientation="h",
            color="project_health",
            title="Highest risk projects",
            labels={"risk_score": "Risk score", "project_name": "Project"},
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(apply_chart_style(fig, height=430), width="stretch")


def render_project_table(projects: pd.DataFrame, current_table: str) -> None:
    section_header("Current project update table", "Progress, completion and risk per project.", current_table)

    display = projects[
        [
            "project_name",
            "project_health",
            "project_status_name",
            "project_start_date",
            "project_target_date",
            "project_progress",
            "issue_completion_ratio",
            "total_issues",
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
            "contributor_count",
            "risk_score",
            "last_issue_updated_at",
        ]
    ].copy()
    display["linear_progress_pct"] = display["project_progress"].map(progress_points)
    display["issue_completion_pct"] = display["issue_completion_ratio"].map(progress_points)
    display = display.drop(columns=["project_progress", "issue_completion_ratio"])

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "linear_progress_pct": st.column_config.ProgressColumn(
                "linear_progress_pct",
                min_value=0,
                max_value=100,
                format="%.0f%%",
            ),
            "issue_completion_pct": st.column_config.ProgressColumn(
                "issue_completion_pct",
                min_value=0,
                max_value=100,
                format="%.0f%%",
            ),
            "risk_score": st.column_config.NumberColumn("risk_score", format="%d"),
        },
    )


def render_timeline(timeline: pd.DataFrame) -> None:
    if timeline.empty:
        return

    chart = timeline.copy()
    today = date.today().isoformat()
    chart["start"] = chart["project_start_date"].fillna(today)
    chart["finish"] = chart["project_target_date"].fillna(today)
    chart = chart[chart["start"] <= chart["finish"]]
    if chart.empty:
        return

    fig = px.timeline(
        chart.head(80),
        x_start="start",
        x_end="finish",
        y="project_name",
        color="project_health",
        hover_data=[
            "project_status_name",
            "project_progress",
            "open_issues",
            "backlog_issues",
            "todo_issues",
            "in_process_issues",
            "review_issues",
            "done_issues",
            "overdue_issues",
        ],
        title="Project schedule",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(apply_chart_style(fig, height=560), width="stretch")


def main() -> None:
    setup_page("Projects")
    config = load_config()
    page_header("Projects", "Project health, progress, deadlines and risk")

    filters = render_global_filters(config)
    projects = load_project_rollup(config, filters)

    if projects.empty:
        st.info("No projects for the selected filters.")
        return

    render_project_kpis(projects)
    render_project_operation_by_team(projects, config["current_table"])
    render_project_maps(projects)
    section_header("Workflow mix by project", "Backlog, Todo, In Process, Review and Done per project.", config["current_table"])
    workflow_stack_bar(projects, "project_name", "Workflow state mix by project", limit=20, height=460)
    render_project_table(projects, config["current_table"])
    render_timeline(load_project_timeline(config, filters))


if __name__ == "__main__":
    main()
