from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.queries import load_issue_queue, load_people_rollup
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
    workflow_stack_bar,
)


def render_people_kpis(people) -> None:
    active_people = people[people["open_issues"] > 0]
    healthy_people = active_people[
        (active_people["overdue_issues"] == 0)
        & (active_people["stale_open_issues"] == 0)
        & (active_people["high_priority_open_issues"] == 0)
    ]
    operating_ratio = safe_ratio(len(healthy_people), len(active_people))
    open_issues = int(people["open_issues"].sum())
    todo = int(people["todo_issues"].sum())
    in_process = int(people["in_process_issues"].sum())
    review = int(people["review_issues"].sum())
    overdue = int(people["overdue_issues"].sum())
    overdue_people = int((people["overdue_issues"] > 0).sum())
    high_priority = int(people["high_priority_open_issues"].sum())
    stale = int(people["stale_open_issues"].sum())

    cols = st.columns(5)
    with cols[0]:
        card(
            "Operating ratio",
            ratio_label(operating_ratio),
            f"{format_int(len(healthy_people))}/{format_int(len(active_people))} active people clear",
            good_ratio_tone(operating_ratio),
            "Clear active people / active people.",
        )
    with cols[1]:
        card(
            "People",
            format_int(len(people)),
            f"{format_int(len(active_people))} with open work",
            "info",
            "Assignees after current filters.",
        )
    with cols[2]:
        card(
            "Open load",
            format_int(open_issues),
            f"{format_int(in_process)} in process, {format_int(review)} review",
            "info",
            f"Todo {format_int(todo)}; open uses Linear lifecycle type.",
        )
    with cols[3]:
        card(
            "Overdue pressure",
            format_int(overdue),
            f"{format_int(overdue_people)} people impacted",
            pressure_tone(overdue),
            "Open issue due date before today.",
        )
    with cols[4]:
        card(
            "Priority & stale",
            format_int(high_priority),
            f"{format_int(stale)} stale open",
            pressure_tone(high_priority + stale),
            "Urgent/high open + stale open.",
        )


def render_people_charts(people):
    left, right = st.columns([1, 1])

    with left:
        workflow_stack_bar(
            people,
            "assignee_name",
            "Workflow load by person",
            limit=25,
            height=500,
        )

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

    render_people_kpis(people)

    render_people_charts(people)

    section_header("Current people update table", "Ownership, workflow load and stale work by assignee.", config["current_table"])
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
