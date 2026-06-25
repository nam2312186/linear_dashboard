from __future__ import annotations

from datetime import date, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from lib.bq import params_json, run_query


VIETNAM_TZ = timezone(timedelta(hours=7))


def format_vietnam_timestamp(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")

    return str(timestamp.to_pydatetime().astimezone(VIETNAM_TZ))


def sql_list(values: list[str] | tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def filter_clause(alias: str = "", due_reference_date: str = "CURRENT_DATE()") -> str:
    prefix = f"{alias}." if alias else ""
    return f"""
      AND (@project_all OR COALESCE({prefix}project_name, '(blank)') IN UNNEST(@projects))
      AND (@team_all OR COALESCE({prefix}team_key, '(blank)') IN UNNEST(@teams))
      AND (@assignee_all OR COALESCE({prefix}assignee_name, '(unassigned)') IN UNNEST(@assignees))
      AND (@health_all OR COALESCE({prefix}project_health, '(blank)') IN UNNEST(@healths))
      AND (@project_status_all OR COALESCE({prefix}project_status_name, '(blank)') IN UNNEST(@project_statuses))
      AND (@state_all OR COALESCE({prefix}state_type, '(blank)') IN UNNEST(@state_types))
      AND (@priority_all OR COALESCE({prefix}issue_priority_label, '(none)') IN UNNEST(@priorities))
      AND (@cycle_all OR COALESCE({prefix}cycle_name, '(no cycle)') IN UNNEST(@cycles))
      AND (
        @label_all
        OR EXISTS (
          SELECT 1
          FROM UNNEST(IFNULL({prefix}issue_label_names, ARRAY<STRING>[])) AS label_name
          WHERE label_name IN UNNEST(@labels)
        )
      )
      AND (
        @due_bucket_all
        OR ('No due date' IN UNNEST(@due_buckets) AND {prefix}issue_due_date IS NULL)
        OR ('Overdue' IN UNNEST(@due_buckets)
            AND {prefix}issue_due_date < {due_reference_date}
            AND {prefix}state_type IN ('triage', 'backlog', 'unstarted', 'started'))
        OR ('Due next 7 days' IN UNNEST(@due_buckets)
            AND {prefix}issue_due_date BETWEEN {due_reference_date} AND DATE_ADD({due_reference_date}, INTERVAL 7 DAY)
            AND {prefix}state_type IN ('triage', 'backlog', 'unstarted', 'started'))
        OR ('Future due' IN UNNEST(@due_buckets)
            AND {prefix}issue_due_date > DATE_ADD({due_reference_date}, INTERVAL 7 DAY))
      )
      AND (
        @search_text = ''
        OR LOWER(CONCAT(
          COALESCE({prefix}issue_identifier, ''), ' ',
          COALESCE({prefix}issue_title, ''), ' ',
          COALESCE({prefix}project_name, ''), ' ',
          COALESCE({prefix}assignee_name, ''), ' ',
          COALESCE({prefix}team_key, '')
        )) LIKE CONCAT('%', LOWER(@search_text), '%')
      )
    """


def normalize_multiselect(values: list[str]) -> list[str]:
    return [value for value in values if value]


def empty_to_all(values: list[str]) -> list[str]:
    return values or ["__ALL__"]


def query_params(filters: dict[str, Any]) -> dict[str, Any]:
    projects = normalize_multiselect(filters["projects"])
    teams = normalize_multiselect(filters["teams"])
    assignees = normalize_multiselect(filters["assignees"])
    healths = normalize_multiselect(filters["healths"])
    project_statuses = normalize_multiselect(filters["project_statuses"])
    state_types = normalize_multiselect(filters["state_types"])
    priorities = normalize_multiselect(filters["priorities"])
    cycles = normalize_multiselect(filters["cycles"])
    labels = normalize_multiselect(filters["labels"])
    due_buckets = normalize_multiselect(filters["due_buckets"])
    return {
        "projects": empty_to_all(projects),
        "teams": empty_to_all(teams),
        "assignees": empty_to_all(assignees),
        "healths": empty_to_all(healths),
        "project_statuses": empty_to_all(project_statuses),
        "state_types": empty_to_all(state_types),
        "priorities": empty_to_all(priorities),
        "cycles": empty_to_all(cycles),
        "labels": empty_to_all(labels),
        "due_buckets": empty_to_all(due_buckets),
        "project_all": not projects,
        "team_all": not teams,
        "assignee_all": not assignees,
        "health_all": not healths,
        "project_status_all": not project_statuses,
        "state_all": not state_types,
        "priority_all": not priorities,
        "cycle_all": not cycles,
        "label_all": not labels,
        "due_bucket_all": not due_buckets,
        "search_text": str(filters["search_text"]).strip(),
        "snapshot_start_date": str(filters["snapshot_start_date"]),
        "snapshot_end_date": str(filters["snapshot_end_date"]),
    }


def load_dimensions(config: dict[str, str]) -> pd.DataFrame:
    sql = f"""
    SELECT DISTINCT
      COALESCE(project_name, '(blank)') AS project_name,
      COALESCE(team_key, '(blank)') AS team_key,
      COALESCE(assignee_name, '(unassigned)') AS assignee_name,
      COALESCE(project_health, '(blank)') AS project_health,
      COALESCE(project_status_name, '(blank)') AS project_status_name,
      COALESCE(state_type, '(blank)') AS state_type,
      COALESCE(issue_priority_label, '(none)') AS issue_priority_label,
      COALESCE(cycle_name, '(no cycle)') AS cycle_name,
      label_name
    FROM `{config["current_table"]}`
    LEFT JOIN UNNEST(IFNULL(issue_label_names, ARRAY<STRING>[])) AS label_name
    """
    return run_query(sql, "{}", config["location"])


def load_last_sync(config: dict[str, str]) -> pd.DataFrame:
    sql = f"""
    SELECT
      MAX(synced_at) AS last_synced_at,
      COUNT(*) AS row_count
    FROM `{config["current_table"]}`
    """
    return run_query(sql, "{}", config["location"])


def render_global_filters(config: dict[str, str]) -> dict[str, Any]:
    dimensions = load_dimensions(config)
    last_sync = load_last_sync(config)

    if not last_sync.empty:
        synced = format_vietnam_timestamp(last_sync.loc[0, "last_synced_at"])
        rows = int(last_sync.loc[0, "row_count"] or 0)
        st.sidebar.caption(f"Last sync: {synced} | Rows: {rows:,}")

    projects = sorted(dimensions["project_name"].dropna().unique().tolist())
    teams = sorted(dimensions["team_key"].dropna().unique().tolist())
    assignees = sorted(dimensions["assignee_name"].dropna().unique().tolist())
    healths = sorted(dimensions["project_health"].dropna().unique().tolist())
    project_statuses = sorted(dimensions["project_status_name"].dropna().unique().tolist())
    state_types = sorted(dimensions["state_type"].dropna().unique().tolist())
    priorities = sorted(dimensions["issue_priority_label"].dropna().unique().tolist())
    cycles = sorted(dimensions["cycle_name"].dropna().unique().tolist())
    labels = sorted(dimensions["label_name"].dropna().unique().tolist())

    default_snapshot_end = date.today()
    default_snapshot_start = default_snapshot_end - timedelta(days=30)

    st.sidebar.header("Filters")
    search_text = st.sidebar.text_input("Search issue/project/person")
    selected_projects = st.sidebar.multiselect("Projects", projects)
    selected_teams = st.sidebar.multiselect("Teams", teams)
    selected_assignees = st.sidebar.multiselect("People", assignees)

    with st.sidebar.expander("Project filters", expanded=True):
        selected_healths = st.multiselect("Project health", healths)
        selected_project_statuses = st.multiselect("Project status", project_statuses)

    with st.sidebar.expander("Issue filters", expanded=True):
        selected_state_types = st.multiselect("Issue state type", state_types)
        selected_priorities = st.multiselect("Priority", priorities)
        selected_cycles = st.multiselect("Cycle", cycles)
        selected_labels = st.multiselect("Labels", labels)
        selected_due_buckets = st.multiselect(
            "Due bucket",
            ["Overdue", "Due next 7 days", "Future due", "No due date"],
        )

    with st.sidebar.expander("Snapshot filters", expanded=True):
        snapshot_range = st.date_input(
            "Snapshot date range",
            value=(default_snapshot_start, default_snapshot_end),
            help="Applies to trend and snapshot tables only.",
        )
        if isinstance(snapshot_range, tuple) and len(snapshot_range) == 2:
            snapshot_start_date, snapshot_end_date = snapshot_range
        else:
            snapshot_start_date = default_snapshot_start
            snapshot_end_date = default_snapshot_end
        if snapshot_start_date > snapshot_end_date:
            snapshot_start_date, snapshot_end_date = snapshot_end_date, snapshot_start_date

    return {
        "projects": selected_projects,
        "teams": selected_teams,
        "assignees": selected_assignees,
        "healths": selected_healths,
        "project_statuses": selected_project_statuses,
        "state_types": selected_state_types,
        "priorities": selected_priorities,
        "cycles": selected_cycles,
        "labels": selected_labels,
        "due_buckets": selected_due_buckets,
        "search_text": search_text,
        "snapshot_start_date": snapshot_start_date,
        "snapshot_end_date": snapshot_end_date,
    }
