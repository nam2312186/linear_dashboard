from __future__ import annotations

import streamlit as st

from lib.bq import load_config
from lib.filters import render_global_filters
from lib.queries import load_issue_queue, load_raw_issues
from lib.ui import page_header, section_header, setup_page


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
