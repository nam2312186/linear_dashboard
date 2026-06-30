from __future__ import annotations

from typing import Any

import pandas as pd

from lib.constants import DEV_OPERATION_PROJECT_NAMES
from lib.ui import card, format_int, good_ratio_tone, ratio_label


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


def operation_project_groups(projects: pd.DataFrame) -> list[tuple[str, str, list[str]]]:
    return [
        (team_name, team_note, project_filter_values(team_projects))
        for team_name, team_note, team_projects in split_project_rollup(projects)
    ]


def filters_for_projects(filters: dict[str, Any], project_names: list[str]) -> dict[str, Any]:
    scoped = dict(filters)
    scoped["projects"] = project_names
    return scoped


def operation_ratio_card(
    team_name: str,
    value: float,
    note: str,
    help_text: str,
    has_scope: bool = True,
) -> None:
    if not has_scope:
        card(
            f"{team_name} operating",
            "-",
            "No selected projects",
            "info",
            help_text,
        )
        return

    card(
        f"{team_name} operating",
        ratio_label(value),
        note,
        good_ratio_tone(value),
        help_text,
    )


def open_overdue_ratio(open_issues: int, overdue_issues: int) -> float:
    if open_issues <= 0:
        return 1
    return max(open_issues - overdue_issues, 0) / open_issues


def open_pressure_ratio(open_issues: int, pressure_issues: int) -> float:
    if open_issues <= 0:
        return 1
    return max(open_issues - pressure_issues, 0) / open_issues


def grouped_project_open_overdue(projects: pd.DataFrame) -> list[tuple[str, float, str, bool]]:
    summaries = []
    for team_name, _team_note, team_projects in split_project_rollup(projects):
        has_scope = not team_projects.empty
        open_issues = int(team_projects["open_issues"].sum()) if has_scope else 0
        overdue = int(team_projects["overdue_issues"].sum()) if has_scope else 0
        summaries.append(
            (
                team_name,
                open_overdue_ratio(open_issues, overdue),
                f"{format_int(overdue)} overdue / {format_int(open_issues)} open",
                has_scope,
            )
        )
    return summaries
