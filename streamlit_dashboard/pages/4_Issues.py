from __future__ import annotations

import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.queries import load_issue_queue, load_kpis, load_raw_issues, load_state_breakdown
from lib.ui import (
    card,
    format_int,
    good_ratio_tone,
    page_header,
    pressure_tone,
    ratio_label,
    safe_ratio,
    section_header,
    setup_page,
    state_bar,
)


def render_issue_kpis(kpis) -> None:
    if kpis.empty:
        return

    row = kpis.iloc[0]
    open_issues = int(row["open_issues"] or 0)
    overdue = int(row["overdue_issues"] or 0)
    due_soon = int(row["due_soon_issues"] or 0)
    stale = int(row["stale_open_issues"] or 0)
    high_priority = int(row["high_priority_open_issues"] or 0)
    unassigned = int(row["unassigned_open_issues"] or 0)
    todo = int(row["todo_issues"] or 0)
    in_process = int(row["in_process_issues"] or 0)
    review = int(row["review_issues"] or 0)
    on_time_ratio = safe_ratio(open_issues - overdue, open_issues)

    cols = st.columns(5)
    with cols[0]:
        card(
            "Operating ratio",
            ratio_label(on_time_ratio),
            f"{format_int(overdue)} overdue",
            good_ratio_tone(on_time_ratio),
            "Open not overdue / open.",
        )
    with cols[1]:
        card(
            "Open issues",
            format_int(open_issues),
            f"Todo {format_int(todo)}; In Process/Review {format_int(in_process)}/{format_int(review)}",
            "info",
            f"{format_int(unassigned)} unassigned open issues.",
        )
    with cols[2]:
        card(
            "Due soon",
            format_int(due_soon),
            "Next 7 days",
            pressure_tone(due_soon),
            "Open issue due today through next 7 days.",
        )
    with cols[3]:
        card(
            "Stale",
            format_int(stale),
            ">14 days no update",
            pressure_tone(stale),
            "Open issue not updated for 14+ days.",
        )
    with cols[4]:
        card(
            "High priority",
            format_int(high_priority),
            "Urgent/high open",
            pressure_tone(high_priority),
            "Open issue priority urgent or high.",
        )


def issue_table(title: str, data, source: str) -> None:
    section_header(title, "Current issue queue for follow-up.", source)
    st.dataframe(
        data,
        width="stretch",
        hide_index=True,
        column_config={"issue_url": st.column_config.LinkColumn("issue_url")},
    )


def main() -> None:
    setup_page("Issues")
    config = load_config()
    page_header("Issues", "Follow-up queues from the current issue table")

    filters = render_global_filters(config)
    kpis = load_kpis(config, filters)
    render_issue_kpis(kpis)

    section_header("Workflow state mix", "Current issue distribution by workflow state.", config["current_table"])
    state_bar(load_state_breakdown(config, filters), "Workflow state mix")

    tab_overdue, tab_due, tab_stale, tab_priority, tab_all = st.tabs(
        ["Overdue", "Due soon", "Stale", "High priority", "Explorer"]
    )

    with tab_overdue:
        issue_table("Overdue open issues", load_issue_queue(config, filters, "overdue"), config["current_table"])

    with tab_due:
        issue_table("Due in the next 7 days", load_issue_queue(config, filters, "due_soon"), config["current_table"])

    with tab_stale:
        issue_table("Stale open issues", load_issue_queue(config, filters, "stale"), config["current_table"])

    with tab_priority:
        issue_table("High-priority open issues", load_issue_queue(config, filters, "high_priority"), config["current_table"])

    with tab_all:
        limit = st.slider("Rows", min_value=25, max_value=500, value=100, step=25)
        issue_table("Latest updated issues", load_raw_issues(config, filters, limit), config["current_table"])


if __name__ == "__main__":
    main()
