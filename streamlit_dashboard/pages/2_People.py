from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.queries import load_issue_queue, load_people_rollup
from lib.ui import apply_chart_style, page_header, section_header, setup_page


def render_people_charts(people):
    left, right = st.columns([1, 1])

    with left:
        top_open = people.head(25).sort_values("open_issues", ascending=True)
        fig = px.bar(
            top_open,
            x="open_issues",
            y="assignee_name",
            orientation="h",
            color="started_issues",
            color_continuous_scale="Blues",
            title="Open workload by person",
            labels={"assignee_name": "Person", "open_issues": "Open issues", "started_issues": "Started"},
        )
        st.plotly_chart(apply_chart_style(fig, height=500), width="stretch")

    with right:
        risk = people.sort_values(["overdue_issues", "high_priority_open_issues"], ascending=True).tail(25)
        fig = px.bar(
            risk,
            x="overdue_issues",
            y="assignee_name",
            orientation="h",
            color="high_priority_open_issues",
            color_continuous_scale="Reds",
            title="Overdue and high-priority load",
            labels={
                "assignee_name": "Person",
                "overdue_issues": "Overdue",
                "high_priority_open_issues": "High priority",
            },
        )
        st.plotly_chart(apply_chart_style(fig, height=500), width="stretch")


def main() -> None:
    setup_page("People")
    config = load_config()
    page_header("People", "Ownership, workload and follow-up queues")

    filters = render_global_filters(config)
    people = load_people_rollup(config, filters)

    if people.empty:
        st.info("No people data for the selected filters.")
        return

    cols = st.columns(4)
    cols[0].metric("People", f"{len(people):,}")
    cols[1].metric("Open issues", f"{int(people['open_issues'].sum()):,}")
    cols[2].metric("Overdue", f"{int(people['overdue_issues'].sum()):,}")
    cols[3].metric("High priority", f"{int(people['high_priority_open_issues'].sum()):,}")

    render_people_charts(people)

    section_header("Current people update table", "Ownership, open load and stale work by assignee.", config["current_table"])
    st.dataframe(people, width="stretch", hide_index=True)

    section_header("Unassigned and overdue queues", "Open issues requiring management follow-up.", config["current_table"])
    overdue = load_issue_queue(config, filters, "overdue", limit=100)
    st.dataframe(
        overdue,
        width="stretch",
        hide_index=True,
        column_config={"issue_url": st.column_config.LinkColumn("issue_url")},
    )


if __name__ == "__main__":
    main()
