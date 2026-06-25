from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.queries import load_team_rollup
from lib.ui import apply_chart_style, page_header, section_header, setup_page


def main() -> None:
    setup_page("Teams")
    config = load_config()
    page_header("Teams", "Team-level workload and operational pressure")

    filters = render_global_filters(config)
    teams = load_team_rollup(config, filters)

    if teams.empty:
        st.info("No team data for the selected filters.")
        return

    cols = st.columns(4)
    cols[0].metric("Teams", f"{len(teams):,}")
    cols[1].metric("Open issues", f"{int(teams['open_issues'].sum()):,}")
    cols[2].metric("Overdue", f"{int(teams['overdue_issues'].sum()):,}")
    cols[3].metric("Projects", f"{int(teams['project_count'].sum()):,}")

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
