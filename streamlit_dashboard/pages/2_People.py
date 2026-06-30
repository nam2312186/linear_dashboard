from __future__ import annotations

import plotly.express as px
import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.operation_groups import render_people_operation_by_team
from lib.queries import load_issue_queue, load_people_rollup, load_project_rollup
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
            "Active people without overdue or stale open issues / active people.",
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
            "Stale open",
            format_int(stale),
            f"{format_int(high_priority)} high priority open",
            pressure_tone(stale),
            "Open issue not updated for 14+ days.",
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
        follow_up = people.copy()
        follow_up["follow_up_load"] = (
            follow_up["overdue_issues"].fillna(0) + follow_up["stale_open_issues"].fillna(0)
        )
        follow_up = follow_up[follow_up["follow_up_load"] > 0]
        if follow_up.empty:
            st.info("No overdue or stale open issues for the selected filters.")
            return

        follow_up = follow_up.sort_values("follow_up_load", ascending=False).head(25)
        entity_order = follow_up.sort_values("follow_up_load")["assignee_name"].tolist()
        chart = follow_up.melt(
            id_vars=["assignee_name", "high_priority_open_issues", "open_issues"],
            value_vars=["overdue_issues", "stale_open_issues"],
            var_name="follow_up_type",
            value_name="issue_count",
        )
        chart = chart[chart["issue_count"].fillna(0) > 0]
        chart["follow_up_type"] = chart["follow_up_type"].map(
            {"overdue_issues": "Overdue", "stale_open_issues": "Stale >14 days"}
        )

        fig = px.bar(
            chart,
            x="issue_count",
            y="assignee_name",
            orientation="h",
            color="follow_up_type",
            title="Stale and overdue follow-up",
            category_orders={"assignee_name": entity_order},
            hover_data=["open_issues", "high_priority_open_issues"],
            labels={
                "assignee_name": "Person",
                "issue_count": "Issues",
                "follow_up_type": "Follow-up type",
                "open_issues": "Open",
                "high_priority_open_issues": "High priority",
            },
            color_discrete_map={"Overdue": "#b91c1c", "Stale >14 days": "#b45309"},
        )
        fig.update_layout(barmode="stack")
        st.plotly_chart(apply_chart_style(fig, height=500), width="stretch")


def main() -> None:
    setup_page("People")
    config = load_config()
    page_header("People", "Ownership, workload and follow-up queues")

    filters = render_global_filters(config)
    people = load_people_rollup(config, filters)
    projects = load_project_rollup(config, filters)

    if people.empty:
        st.info("No people data for the selected filters.")
        return

    render_people_kpis(people)
    render_people_operation_by_team(config, filters, projects, config["current_table"])

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
