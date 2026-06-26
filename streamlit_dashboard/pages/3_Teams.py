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
    good_ratio_tone,
    page_header,
    pressure_tone,
    ratio_label,
    safe_ratio,
    section_header,
    setup_page,
)


def render_team_kpis(teams) -> None:
    active_teams = teams[teams["open_issues"] > 0]
    healthy_teams = active_teams[
        (active_teams["overdue_issues"] == 0)
        & (active_teams["unassigned_open_issues"] == 0)
    ]
    operating_ratio = safe_ratio(len(healthy_teams), len(active_teams))
    open_issues = int(teams["open_issues"].sum())
    overdue = int(teams["overdue_issues"].sum())
    due_soon = int(teams["due_soon_issues"].sum())
    unassigned = int(teams["unassigned_open_issues"].sum())
    projects = int(teams["project_count"].sum())

    cols = st.columns(5)
    with cols[0]:
        card(
            "Operating ratio",
            ratio_label(operating_ratio),
            f"{format_int(len(healthy_teams))}/{format_int(len(active_teams))} active teams clear",
            good_ratio_tone(operating_ratio),
            "Clear active teams / active teams.",
        )
    with cols[1]:
        card(
            "Teams",
            format_int(len(teams)),
            f"{format_int(projects)} project links",
            "info",
            "Teams after filters; project links may duplicate.",
        )
    with cols[2]:
        card(
            "Open work",
            format_int(open_issues),
            "Current active workload",
            "info",
            "Open = triage + backlog + unstarted + started.",
        )
    with cols[3]:
        card(
            "Deadline pressure",
            format_int(overdue),
            f"{format_int(due_soon)} due soon",
            pressure_tone(overdue),
            "Overdue open; due soon is next 7 days.",
        )
    with cols[4]:
        card(
            "Ownership gap",
            format_int(unassigned),
            "Unassigned open issues",
            pressure_tone(unassigned),
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
        top = teams.head(25).sort_values("open_issues", ascending=True)
        fig = px.bar(
            top,
            x="open_issues",
            y="team_key",
            orientation="h",
            color="overdue_issues",
            color_continuous_scale="Reds",
            title="Open workload by team",
            labels={"team_key": "Team", "open_issues": "Open issues", "overdue_issues": "Overdue"},
        )
        st.plotly_chart(apply_chart_style(fig, height=500), width="stretch")

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

    section_header("Current team update table", "Team workload, project spread and overdue pressure.", config["current_table"])
    st.dataframe(teams, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
