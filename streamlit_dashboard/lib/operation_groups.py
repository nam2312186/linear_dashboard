from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from lib.constants import DEV_OPERATION_PROJECT_NAMES
from lib.queries import load_kpis, load_people_rollup, load_snapshot_trend, load_team_rollup
from lib.ui import (
    card,
    format_int,
    format_progress,
    good_ratio_tone,
    notice_tone,
    pressure_tone,
    ratio_label,
    safe_ratio,
    section_header,
)


BLANK_PROJECT_NAME = "(blank)"
OPERATION_GROUPS = (
    ("Dev", "Fanme App + Fanme Web"),
    ("Marketing", "All other named projects"),
)


def _project_names(projects: pd.DataFrame) -> pd.Series:
    if projects.empty or "project_name" not in projects:
        return pd.Series(dtype="string")
    return projects["project_name"].fillna(BLANK_PROJECT_NAME).astype(str)


def split_project_rollup(projects: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    if projects.empty or "project_name" not in projects:
        empty = projects.iloc[0:0]
        return [(name, note, empty) for name, note in OPERATION_GROUPS]

    project_names = _project_names(projects)
    normalized = project_names.str.casefold()
    dev_projects = normalized.isin(DEV_OPERATION_PROJECT_NAMES)
    named_projects = normalized.ne(BLANK_PROJECT_NAME.casefold())

    return [
        ("Dev", "Fanme App + Fanme Web", projects[dev_projects]),
        ("Marketing", "All other named projects", projects[named_projects & ~dev_projects]),
    ]


def project_filter_values(projects: pd.DataFrame) -> list[str]:
    if projects.empty or "project_name" not in projects:
        return []
    names = _project_names(projects)
    names = names[names.str.casefold().ne(BLANK_PROJECT_NAME.casefold())]
    return sorted(names.dropna().unique().tolist(), key=str.casefold)


def filters_for_projects(filters: dict[str, Any], project_names: list[str]) -> dict[str, Any]:
    scoped = dict(filters)
    scoped["projects"] = project_names
    return scoped


def _empty_summary() -> dict[str, float]:
    return {
        "project_count": 0,
        "open_issues": 0,
        "overdue_issues": 0,
        "due_soon_issues": 0,
        "stale_open_issues": 0,
        "unassigned_open_issues": 0,
        "operating_ratio": 0,
        "completion_ratio": 0,
    }


def summarize_project_rollup(projects: pd.DataFrame) -> dict[str, float]:
    if projects.empty:
        return _empty_summary()

    total_issues = int(projects["total_issues"].sum())
    canceled = int(projects["canceled_issues"].sum())
    completed = int(projects["completed_issues"].sum())
    open_issues = int(projects["open_issues"].sum())
    overdue = int(projects["overdue_issues"].sum())
    stale = int(projects["stale_open_issues"].sum())

    return {
        "project_count": len(projects),
        "open_issues": open_issues,
        "overdue_issues": overdue,
        "due_soon_issues": int(projects["due_soon_issues"].sum()),
        "stale_open_issues": stale,
        "unassigned_open_issues": int(projects["unassigned_open_issues"].sum()),
        "operating_ratio": safe_ratio(open_issues - overdue - stale, open_issues),
        "completion_ratio": safe_ratio(completed, total_issues - canceled),
    }


def render_project_operation_by_team(projects: pd.DataFrame, source: str) -> None:
    section_header(
        "Operation by team",
        "Dev is Fanme App/Fanme Web; Marketing is every other named project.",
        source,
    )
    if projects.empty:
        st.info("No project data for the selected filters.")
        return

    columns = st.columns(2)
    for column, (team_name, team_note, team_projects) in zip(columns, split_project_rollup(projects)):
        summary = summarize_project_rollup(team_projects)
        with column:
            st.markdown(f"#### {team_name}")
            top_left, top_right = st.columns(2)
            with top_left:
                card(
                    "Operating ratio",
                    ratio_label(summary["operating_ratio"]),
                    f"{format_int(summary['open_issues'])} open issues",
                    good_ratio_tone(summary["operating_ratio"]),
                    "Open minus overdue/stale, divided by open.",
                )
            with top_right:
                card(
                    "Projects",
                    format_int(summary["project_count"]),
                    team_note,
                    "info",
                    "Project grouping used for this operating slice.",
                )

            bottom_left, bottom_right = st.columns(2)
            with bottom_left:
                card(
                    "Overdue",
                    format_int(summary["overdue_issues"]),
                    f"{format_int(summary['due_soon_issues'])} due in 7 days",
                    pressure_tone(summary["overdue_issues"]),
                    "Open issue due date before today.",
                )
            with bottom_right:
                card(
                    "Stale / ownership",
                    format_int(summary["stale_open_issues"]),
                    f"{format_int(summary['unassigned_open_issues'])} unassigned open",
                    pressure_tone(summary["stale_open_issues"])
                    if summary["stale_open_issues"]
                    else notice_tone(summary["unassigned_open_issues"]),
                    "Stale open issues and ownership gaps.",
                )


def _render_empty_team(team_name: str, team_note: str) -> None:
    st.markdown(f"#### {team_name}")
    left, right = st.columns(2)
    with left:
        card("Operating ratio", "0%", "No selected projects", "info", team_note)
    with right:
        card("Open work", "0", "No selected projects", "info", team_note)


def _operation_project_groups(projects: pd.DataFrame) -> list[tuple[str, str, list[str]]]:
    return [
        (team_name, team_note, project_filter_values(team_projects))
        for team_name, team_note, team_projects in split_project_rollup(projects)
    ]


def render_people_operation_by_team(
    config: dict[str, str], filters: dict[str, Any], projects: pd.DataFrame, source: str
) -> None:
    section_header(
        "Operation by team",
        "Active people clear means no overdue or stale open issues.",
        source,
    )
    columns = st.columns(2)
    for column, (team_name, team_note, project_names) in zip(columns, _operation_project_groups(projects)):
        with column:
            if not project_names:
                _render_empty_team(team_name, team_note)
                continue

            people = load_people_rollup(config, filters_for_projects(filters, project_names))
            active_people = people[people["open_issues"] > 0]
            clear_people = active_people[
                (active_people["overdue_issues"] == 0)
                & (active_people["stale_open_issues"] == 0)
            ]
            open_issues = int(people["open_issues"].sum()) if not people.empty else 0
            overdue = int(people["overdue_issues"].sum()) if not people.empty else 0
            stale = int(people["stale_open_issues"].sum()) if not people.empty else 0
            high_priority = int(people["high_priority_open_issues"].sum()) if not people.empty else 0

            st.markdown(f"#### {team_name}")
            top_left, top_right = st.columns(2)
            with top_left:
                card(
                    "Operating ratio",
                    ratio_label(safe_ratio(len(clear_people), len(active_people))),
                    f"{format_int(len(clear_people))}/{format_int(len(active_people))} active people clear",
                    good_ratio_tone(safe_ratio(len(clear_people), len(active_people))),
                    "No overdue or stale open issues.",
                )
            with top_right:
                card(
                    "Open load",
                    format_int(open_issues),
                    f"{format_int(len(project_names))} projects",
                    "info",
                    team_note,
                )

            bottom_left, bottom_right = st.columns(2)
            with bottom_left:
                card(
                    "Overdue",
                    format_int(overdue),
                    "Open issue due date before today",
                    pressure_tone(overdue),
                    "People follow-up pressure.",
                )
            with bottom_right:
                card(
                    "Stale open",
                    format_int(stale),
                    f"{format_int(high_priority)} high priority open",
                    pressure_tone(stale),
                    "Open issue not updated for 14+ days.",
                )


def render_team_operation_by_team(
    config: dict[str, str], filters: dict[str, Any], projects: pd.DataFrame, source: str
) -> None:
    section_header(
        "Operation by team",
        "Team workload split by Dev and Marketing project groups.",
        source,
    )
    columns = st.columns(2)
    for column, (team_name, team_note, project_names) in zip(columns, _operation_project_groups(projects)):
        with column:
            if not project_names:
                _render_empty_team(team_name, team_note)
                continue

            teams = load_team_rollup(config, filters_for_projects(filters, project_names))
            active_teams = teams[teams["open_issues"] > 0]
            clear_teams = active_teams[
                (active_teams["overdue_issues"] == 0)
                & (active_teams["unassigned_open_issues"] == 0)
            ]
            open_issues = int(teams["open_issues"].sum()) if not teams.empty else 0
            overdue = int(teams["overdue_issues"].sum()) if not teams.empty else 0
            unassigned = int(teams["unassigned_open_issues"].sum()) if not teams.empty else 0
            due_soon = int(teams["due_soon_issues"].sum()) if not teams.empty else 0

            st.markdown(f"#### {team_name}")
            top_left, top_right = st.columns(2)
            with top_left:
                card(
                    "Operating ratio",
                    ratio_label(safe_ratio(len(clear_teams), len(active_teams))),
                    f"{format_int(len(clear_teams))}/{format_int(len(active_teams))} active teams clear",
                    good_ratio_tone(safe_ratio(len(clear_teams), len(active_teams))),
                    "No overdue or unassigned open issues.",
                )
            with top_right:
                card("Open work", format_int(open_issues), team_note, "info", team_note)

            bottom_left, bottom_right = st.columns(2)
            with bottom_left:
                card(
                    "Overdue",
                    format_int(overdue),
                    f"{format_int(due_soon)} due in 7 days",
                    pressure_tone(overdue),
                    "Open issue due date before today.",
                )
            with bottom_right:
                card(
                    "Ownership gap",
                    format_int(unassigned),
                    "Unassigned open issues",
                    notice_tone(unassigned),
                    "Open issues without assignee.",
                )


def _kpi_row(kpis: pd.DataFrame) -> pd.Series | None:
    if kpis.empty:
        return None
    return kpis.iloc[0]


def render_issue_operation_by_team(
    config: dict[str, str], filters: dict[str, Any], projects: pd.DataFrame, source: str
) -> None:
    section_header(
        "Operation by team",
        "Issue follow-up pressure split by Dev and Marketing project groups.",
        source,
    )
    columns = st.columns(2)
    for column, (team_name, team_note, project_names) in zip(columns, _operation_project_groups(projects)):
        with column:
            if not project_names:
                _render_empty_team(team_name, team_note)
                continue

            row = _kpi_row(load_kpis(config, filters_for_projects(filters, project_names)))
            if row is None:
                _render_empty_team(team_name, team_note)
                continue

            open_issues = int(row["open_issues"] or 0)
            overdue = int(row["overdue_issues"] or 0)
            stale = int(row["stale_open_issues"] or 0)
            due_soon = int(row["due_soon_issues"] or 0)
            high_priority = int(row["high_priority_open_issues"] or 0)
            operating_ratio = safe_ratio(open_issues - overdue - stale, open_issues)

            st.markdown(f"#### {team_name}")
            top_left, top_right = st.columns(2)
            with top_left:
                card(
                    "Operating ratio",
                    ratio_label(operating_ratio),
                    f"{format_int(open_issues)} open issues",
                    good_ratio_tone(operating_ratio),
                    "Open without overdue or stale pressure.",
                )
            with top_right:
                card(
                    "Due soon",
                    format_int(due_soon),
                    f"{format_int(high_priority)} high priority",
                    notice_tone(due_soon + high_priority),
                    team_note,
                )

            bottom_left, bottom_right = st.columns(2)
            with bottom_left:
                card("Overdue", format_int(overdue), "Open overdue", pressure_tone(overdue), team_note)
            with bottom_right:
                card("Stale", format_int(stale), ">14 days no update", pressure_tone(stale), team_note)


def _trend_summary(trend: pd.DataFrame) -> dict[str, float] | None:
    if trend.empty:
        return None
    ordered = trend.sort_values("snapshot_hour")
    first = ordered.iloc[0]
    latest = ordered.iloc[-1]
    open_issues = int(latest["open_issues"] or 0)
    overdue = int(latest["overdue_issues"] or 0)
    return {
        "open_issues": open_issues,
        "overdue_issues": overdue,
        "open_delta": float(latest["open_issues"] - first["open_issues"]),
        "overdue_delta": float(latest["overdue_issues"] - first["overdue_issues"]),
        "completion_ratio": latest["issue_completion_ratio"],
        "operating_ratio": safe_ratio(open_issues - overdue, open_issues),
    }


def _signed(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.0f} vs range start"


def render_trend_operation_by_team(
    config: dict[str, str], filters: dict[str, Any], projects: pd.DataFrame, source: str
) -> None:
    section_header(
        "Operation by team",
        "Latest trend snapshot split by Dev and Marketing project groups.",
        source,
    )
    columns = st.columns(2)
    for column, (team_name, team_note, project_names) in zip(columns, _operation_project_groups(projects)):
        with column:
            if not project_names:
                _render_empty_team(team_name, team_note)
                continue

            summary = _trend_summary(load_snapshot_trend(config, filters_for_projects(filters, project_names)))
            if summary is None:
                _render_empty_team(team_name, team_note)
                continue

            st.markdown(f"#### {team_name}")
            top_left, top_right = st.columns(2)
            with top_left:
                card(
                    "Operating ratio",
                    ratio_label(summary["operating_ratio"]),
                    f"{format_int(summary['overdue_issues'])} overdue now",
                    good_ratio_tone(summary["operating_ratio"]),
                    "Latest open not overdue / latest open.",
                )
            with top_right:
                card(
                    "Open trend",
                    format_int(summary["open_issues"]),
                    _signed(summary["open_delta"]),
                    notice_tone(summary["open_delta"]),
                    team_note,
                )

            bottom_left, bottom_right = st.columns(2)
            with bottom_left:
                card(
                    "Completion",
                    format_progress(summary["completion_ratio"]),
                    "Latest snapshot",
                    good_ratio_tone(safe_ratio(summary["completion_ratio"], 1), warn_at=0.45, good_at=0.7),
                    team_note,
                )
            with bottom_right:
                card(
                    "Overdue trend",
                    format_int(summary["overdue_issues"]),
                    _signed(summary["overdue_delta"]),
                    pressure_tone(summary["overdue_issues"]),
                    team_note,
                )
