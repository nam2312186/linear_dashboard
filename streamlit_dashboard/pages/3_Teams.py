from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.queries import load_team_rollup
from lib.ui import (
    apply_chart_style,
    card,
    format_int,
    notice_tone,
    page_header,
    pressure_tone,
    section_header,
    setup_page,
    workflow_stack_bar,
)


def render_team_kpis(teams) -> None:
    open_issues = int(teams["open_issues"].sum())
    todo = int(teams["todo_issues"].sum())
    in_process = int(teams["in_process_issues"].sum())
    review = int(teams["review_issues"].sum())
    overdue = int(teams["overdue_issues"].sum())
    due_soon = int(teams["due_soon_issues"].sum())
    unassigned = int(teams["unassigned_open_issues"].sum())
    projects_total = int(teams["project_count"].sum())

    cols = st.columns(4)
    with cols[0]:
        card(
            "Teams",
            format_int(len(teams)),
            f"{format_int(projects_total)} project links",
            "info",
            "Teams after filters; project links may duplicate.",
        )
    with cols[1]:
        card(
            "Open work",
            format_int(open_issues),
            f"Todo {format_int(todo)}; In Process/Review {format_int(in_process + review)}",
            "info",
            "Open uses Linear lifecycle type; chart below shows workflow states.",
        )
    with cols[2]:
        card(
            "Deadline pressure",
            format_int(overdue),
            f"{format_int(due_soon)} due soon",
            pressure_tone(overdue),
            "Overdue open; due soon is next 7 days.",
        )
    with cols[3]:
        card(
            "Ownership gap",
            format_int(unassigned),
            "Unassigned open issues",
            notice_tone(unassigned),
            "Open issues without assignee.",
        )


def main() -> None:
    setup_page("Teams")
    config = load_config()
    page_header("Teams", "Team-level workload and operational pressure")

    filters = render_global_filters(config)
    teams = load_team_rollup(config, filters)

    if teams.empty:
        st.info("No team data for the selected filters.")
        return

    render_team_kpis(teams)

    left, right = st.columns([1, 1])
    with left:
        workflow_stack_bar(
            teams,
            "team_key",
            "Workflow load by team",
            limit=25,
            height=500,
        )

    with right:
        fig = px.scatter(
            teams,
            x="contributor_count",
            y="open_issues",
            size="total_issues",
            color="overdue_issues",
            hover_name="team_name",
            labels={
                "contributor_count": "Contributors",
                "open_issues": "Open issues",
                "overdue_issues": "Overdue",
            },
            title="Load concentration",
            color_continuous_scale="Oranges",
        )
        st.plotly_chart(apply_chart_style(fig, height=500), width="stretch")

    section_header("Current team update table", "Team workflow load, project spread and overdue pressure.", config["current_table"])
    st.dataframe(teams, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
