from __future__ import annotations

from typing import Any

import pandas as pd

from lib.bq import params_json, run_query
from lib.constants import HIGH_PRIORITY_LABELS, OPEN_STATE_TYPES
from lib.filters import filter_clause, query_params, sql_list


def load_kpis(config: dict[str, str], filters: dict[str, Any]) -> pd.DataFrame:
    sql = f"""
    WITH filtered AS (
      SELECT *
      FROM `{config["current_table"]}`
      WHERE TRUE
      {filter_clause()}
    ),
    projects AS (
      SELECT
        project_id,
        ANY_VALUE(project_name) AS project_name,
        ANY_VALUE(project_health) AS project_health,
        ANY_VALUE(project_progress) AS project_progress,
        ANY_VALUE(project_status_type) AS project_status_type,
        ANY_VALUE(project_target_date) AS project_target_date
      FROM filtered
      WHERE project_id IS NOT NULL
      GROUP BY project_id
    )
    SELECT
      COUNT(*) AS total_issues,
      COUNTIF(state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS open_issues,
      COUNTIF(state_type = 'started') AS in_progress_issues,
      COUNTIF(state_type = 'completed') AS completed_issues,
      COUNTIF(state_type = 'canceled') AS canceled_issues,
      COUNTIF(assignee_id IS NULL AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS unassigned_open_issues,
      COUNTIF(issue_due_date < CURRENT_DATE() AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS overdue_issues,
      COUNTIF(issue_due_date BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY)
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS due_soon_issues,
      COUNTIF(LOWER(issue_priority_label) IN ({sql_list(HIGH_PRIORITY_LABELS)})
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS high_priority_open_issues,
      COUNTIF(issue_updated_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS stale_open_issues,
      (SELECT COUNT(*) FROM projects) AS total_projects,
      (SELECT COUNTIF(LOWER(COALESCE(project_health, '')) IN ('atrisk', 'at risk', 'offtrack', 'off track')) FROM projects) AS risky_projects,
      (SELECT COUNTIF(project_target_date < CURRENT_DATE()
                      AND LOWER(COALESCE(project_status_type, '')) NOT IN ('completed', 'canceled')) FROM projects) AS overdue_projects,
      (SELECT AVG(project_progress) FROM projects WHERE project_progress IS NOT NULL) AS avg_project_progress
    FROM filtered
    """
    return run_query(sql, params_json(**query_params(filters)), config["location"])


def load_state_breakdown(config: dict[str, str], filters: dict[str, Any]) -> pd.DataFrame:
    sql = f"""
    SELECT
      COALESCE(state_type, '(blank)') AS state_type,
      COALESCE(state_name, '(blank)') AS state_name,
      COUNT(*) AS issue_count
    FROM `{config["current_table"]}`
    WHERE TRUE
    {filter_clause()}
    GROUP BY 1, 2
    ORDER BY issue_count DESC
    """
    return run_query(sql, params_json(**query_params(filters)), config["location"])


def load_project_rollup(config: dict[str, str], filters: dict[str, Any], limit: int = 250) -> pd.DataFrame:
    params = query_params(filters)
    params["limit"] = limit
    sql = f"""
    WITH filtered AS (
      SELECT *
      FROM `{config["current_table"]}`
      WHERE project_id IS NOT NULL
      {filter_clause()}
    ),
    project_rollup AS (
      SELECT
        project_id,
        ANY_VALUE(project_name) AS project_name,
        COALESCE(ANY_VALUE(project_health), '(blank)') AS project_health,
        ANY_VALUE(project_status_name) AS project_status_name,
        ANY_VALUE(project_status_type) AS project_status_type,
        ANY_VALUE(project_start_date) AS project_start_date,
        ANY_VALUE(project_target_date) AS project_target_date,
        ANY_VALUE(project_progress) AS project_progress,
        ANY_VALUE(project_priority) AS project_priority,
        COUNT(*) AS total_issues,
        COUNTIF(state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS open_issues,
        COUNTIF(state_type = 'started') AS started_issues,
        COUNTIF(state_type = 'completed') AS completed_issues,
        COUNTIF(state_type = 'canceled') AS canceled_issues,
        COUNTIF(issue_due_date < CURRENT_DATE()
                AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS overdue_issues,
        COUNTIF(issue_due_date BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY)
                AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS due_soon_issues,
        COUNTIF(assignee_id IS NULL
                AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS unassigned_open_issues,
        COUNTIF(issue_updated_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
                AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS stale_open_issues,
        COUNT(DISTINCT assignee_id) AS contributor_count,
        MAX(issue_updated_at) AS last_issue_updated_at
      FROM filtered
      GROUP BY project_id
    )
    SELECT *,
      SAFE_DIVIDE(completed_issues, NULLIF(total_issues - canceled_issues, 0)) AS issue_completion_ratio,
      (
        4 * overdue_issues
        + 3 * unassigned_open_issues
        + 2 * stale_open_issues
        + 2 * due_soon_issues
        + CASE WHEN LOWER(project_health) IN ('atrisk', 'at risk') THEN 8 ELSE 0 END
        + CASE WHEN LOWER(project_health) IN ('offtrack', 'off track') THEN 14 ELSE 0 END
        + CASE WHEN project_target_date < CURRENT_DATE()
               AND LOWER(COALESCE(project_status_type, '')) NOT IN ('completed', 'canceled')
               THEN 10 ELSE 0 END
      ) AS risk_score
    FROM project_rollup
    ORDER BY risk_score DESC, open_issues DESC, total_issues DESC
    LIMIT @limit
    """
    return run_query(sql, params_json(**params), config["location"])


def load_team_rollup(config: dict[str, str], filters: dict[str, Any]) -> pd.DataFrame:
    sql = f"""
    SELECT
      COALESCE(team_key, '(blank)') AS team_key,
      COALESCE(team_name, '(blank)') AS team_name,
      COUNT(*) AS total_issues,
      COUNTIF(state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS open_issues,
      COUNTIF(state_type = 'started') AS started_issues,
      COUNTIF(state_type = 'completed') AS completed_issues,
      COUNTIF(issue_due_date < CURRENT_DATE()
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS overdue_issues,
      COUNTIF(issue_due_date BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY)
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS due_soon_issues,
      COUNTIF(assignee_id IS NULL
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS unassigned_open_issues,
      COUNT(DISTINCT project_id) AS project_count,
      COUNT(DISTINCT assignee_id) AS contributor_count
    FROM `{config["current_table"]}`
    WHERE TRUE
    {filter_clause()}
    GROUP BY 1, 2
    ORDER BY open_issues DESC, total_issues DESC
    """
    return run_query(sql, params_json(**query_params(filters)), config["location"])


def load_people_rollup(config: dict[str, str], filters: dict[str, Any], limit: int = 200) -> pd.DataFrame:
    params = query_params(filters)
    params["limit"] = limit
    sql = f"""
    SELECT
      COALESCE(assignee_name, '(unassigned)') AS assignee_name,
      COUNT(*) AS total_issues,
      COUNTIF(state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS open_issues,
      COUNTIF(state_type = 'started') AS started_issues,
      COUNTIF(state_type = 'completed') AS completed_issues,
      COUNTIF(state_type = 'canceled') AS canceled_issues,
      COUNTIF(issue_due_date < CURRENT_DATE()
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS overdue_issues,
      COUNTIF(issue_due_date BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY)
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS due_soon_issues,
      COUNTIF(LOWER(issue_priority_label) IN ({sql_list(HIGH_PRIORITY_LABELS)})
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS high_priority_open_issues,
      COUNTIF(issue_updated_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS stale_open_issues,
      COUNT(DISTINCT project_id) AS project_count,
      COUNT(DISTINCT team_key) AS team_count,
      SAFE_DIVIDE(COUNTIF(state_type = 'completed'), NULLIF(COUNTIF(state_type != 'canceled'), 0)) AS completion_ratio
    FROM `{config["current_table"]}`
    WHERE TRUE
    {filter_clause()}
    GROUP BY 1
    ORDER BY open_issues DESC, started_issues DESC
    LIMIT @limit
    """
    return run_query(sql, params_json(**params), config["location"])


def load_issue_queue(config: dict[str, str], filters: dict[str, Any], queue: str, limit: int = 200) -> pd.DataFrame:
    params = query_params(filters)
    params["limit"] = limit
    where_by_queue = {
        "overdue": f"issue_due_date < CURRENT_DATE() AND state_type IN ({sql_list(OPEN_STATE_TYPES)})",
        "due_soon": f"issue_due_date BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 7 DAY) AND state_type IN ({sql_list(OPEN_STATE_TYPES)})",
        "stale": f"issue_updated_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY) AND state_type IN ({sql_list(OPEN_STATE_TYPES)})",
        "high_priority": f"LOWER(issue_priority_label) IN ({sql_list(HIGH_PRIORITY_LABELS)}) AND state_type IN ({sql_list(OPEN_STATE_TYPES)})",
        "open": f"state_type IN ({sql_list(OPEN_STATE_TYPES)})",
    }
    order_by_queue = {
        "overdue": "days_overdue DESC, issue_priority ASC",
        "due_soon": "issue_due_date ASC, issue_priority ASC",
        "stale": "days_since_update DESC",
        "high_priority": "issue_priority ASC, issue_due_date ASC",
        "open": "issue_updated_at DESC",
    }
    where_clause = where_by_queue.get(queue, where_by_queue["open"])
    order_clause = order_by_queue.get(queue, order_by_queue["open"])

    sql = f"""
    SELECT
      issue_identifier,
      issue_title,
      project_name,
      team_key,
      COALESCE(assignee_name, '(unassigned)') AS assignee_name,
      state_name,
      issue_priority_label,
      issue_due_date,
      DATE_DIFF(CURRENT_DATE(), issue_due_date, DAY) AS days_overdue,
      TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), issue_updated_at, DAY) AS days_since_update,
      issue_updated_at,
      issue_url
    FROM `{config["current_table"]}`
    WHERE {where_clause}
    {filter_clause()}
    ORDER BY {order_clause}
    LIMIT @limit
    """
    return run_query(sql, params_json(**params), config["location"])


def load_snapshot_trend(config: dict[str, str], filters: dict[str, Any]) -> pd.DataFrame:
    sql = f"""
    WITH filtered AS (
      SELECT *
      FROM `{config["snapshot_table"]}`
      WHERE DATE(snapshot_hour) BETWEEN DATE(@snapshot_start_date) AND DATE(@snapshot_end_date)
      {filter_clause(due_reference_date="DATE(snapshot_hour)")}
    ),
    issue_metrics AS (
      SELECT
        snapshot_hour,
        COUNT(*) AS total_issues,
        COUNTIF(state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS open_issues,
        COUNTIF(state_type = 'started') AS started_issues,
        COUNTIF(state_type = 'completed') AS completed_issues,
        COUNTIF(state_type = 'canceled') AS canceled_issues,
        COUNTIF(issue_due_date < DATE(snapshot_hour)
                AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS overdue_issues,
        COUNT(DISTINCT project_id) AS project_count
      FROM filtered
      GROUP BY snapshot_hour
    ),
    project_metrics AS (
      SELECT
        snapshot_hour,
        AVG(project_progress) AS avg_project_progress
      FROM (
        SELECT
          snapshot_hour,
          project_id,
          ANY_VALUE(project_progress) AS project_progress
        FROM filtered
        WHERE project_id IS NOT NULL AND project_progress IS NOT NULL
        GROUP BY snapshot_hour, project_id
      )
      GROUP BY snapshot_hour
    )
    SELECT
      issue_metrics.*,
      SAFE_DIVIDE(completed_issues, NULLIF(total_issues - canceled_issues, 0)) AS issue_completion_ratio,
      project_metrics.avg_project_progress
    FROM issue_metrics
    LEFT JOIN project_metrics USING (snapshot_hour)
    ORDER BY snapshot_hour
    """
    return run_query(sql, params_json(**query_params(filters)), config["location"])


def load_completion_events(config: dict[str, str], filters: dict[str, Any]) -> pd.DataFrame:
    sql = f"""
    WITH snapshots AS (
      SELECT
        snapshot_hour,
        issue_id,
        state_type,
        LAG(state_type) OVER (PARTITION BY issue_id ORDER BY snapshot_hour) AS previous_state_type
      FROM `{config["snapshot_table"]}`
      WHERE DATE(snapshot_hour) BETWEEN DATE(@snapshot_start_date) AND DATE(@snapshot_end_date)
      {filter_clause(due_reference_date="DATE(snapshot_hour)")}
    )
    SELECT
      DATE(snapshot_hour) AS event_date,
      COUNTIF(state_type = 'completed'
              AND COALESCE(previous_state_type, '') != 'completed') AS completed_events,
      COUNTIF(state_type = 'canceled'
              AND COALESCE(previous_state_type, '') != 'canceled') AS canceled_events
    FROM snapshots
    GROUP BY event_date
    ORDER BY event_date
    """
    return run_query(sql, params_json(**query_params(filters)), config["location"])


def load_project_timeline(config: dict[str, str], filters: dict[str, Any]) -> pd.DataFrame:
    sql = f"""
    WITH filtered AS (
      SELECT *
      FROM `{config["current_table"]}`
      WHERE project_id IS NOT NULL
      {filter_clause()}
    )
    SELECT
      project_id,
      ANY_VALUE(project_name) AS project_name,
      ANY_VALUE(project_health) AS project_health,
      ANY_VALUE(project_status_name) AS project_status_name,
      ANY_VALUE(project_start_date) AS project_start_date,
      ANY_VALUE(project_target_date) AS project_target_date,
      ANY_VALUE(project_progress) AS project_progress,
      COUNTIF(state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS open_issues,
      COUNTIF(issue_due_date < CURRENT_DATE()
              AND state_type IN ({sql_list(OPEN_STATE_TYPES)})) AS overdue_issues
    FROM filtered
    GROUP BY project_id
    HAVING project_start_date IS NOT NULL OR project_target_date IS NOT NULL
    ORDER BY COALESCE(project_target_date, DATE '9999-12-31'), project_name
    LIMIT 120
    """
    return run_query(sql, params_json(**query_params(filters)), config["location"])


def load_raw_issues(config: dict[str, str], filters: dict[str, Any], limit: int) -> pd.DataFrame:
    params = query_params(filters)
    params["limit"] = limit
    sql = f"""
    SELECT
      issue_identifier,
      issue_title,
      project_name,
      team_key,
      state_type,
      state_name,
      assignee_name,
      issue_priority_label,
      issue_due_date,
      issue_updated_at,
      issue_url
    FROM `{config["current_table"]}`
    WHERE TRUE
    {filter_clause()}
    ORDER BY issue_updated_at DESC
    LIMIT @limit
    """
    return run_query(sql, params_json(**params), config["location"])
