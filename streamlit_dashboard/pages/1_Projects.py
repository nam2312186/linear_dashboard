from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.queries import load_project_rollup, load_project_timeline
from lib.ui import apply_chart_style, page_header, progress_points, section_header, setup_page


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
            "started_issues",
            "completed_issues",
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
        hover_data=["project_status_name", "project_progress", "open_issues", "overdue_issues"],
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

    render_project_maps(projects)
    render_project_table(projects, config["current_table"])
    render_timeline(load_project_timeline(config, filters))


if __name__ == "__main__":
    main()
