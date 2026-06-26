from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from airflow import DAG
from airflow.sdk import task
from google.cloud import bigquery


# =========================================================
# CONFIG
# =========================================================
PROJECT_ID = os.getenv("GCP_PROJECT_ID") or "fanme-data-warehouse"
DATASET_ID = os.getenv("LINEAR_BQ_DATASET") or "linear_dwh"
CURRENT_TABLE_ID = os.getenv("LINEAR_CURRENT_TABLE") or "linear_project_issues_current"
SNAPSHOT_TABLE_ID = os.getenv("LINEAR_SNAPSHOT_TABLE") or "linear_project_issues_snapshot_hourly"
BQ_LOCATION = os.getenv("BQ_LOCATION") or "asia-southeast1"

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_API_URL = os.getenv("LINEAR_API_URL") or "https://api.linear.app/graphql"
LINEAR_PAGE_SIZE = min(max(int(os.getenv("LINEAR_PAGE_SIZE", "100")), 1), 250)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
DEBUG_VERBOSE = os.getenv("DEBUG_VERBOSE", "true").lower() == "true"
DEBUG_PRINT_FIRST_ROWS = int(os.getenv("LINEAR_DEBUG_PRINT_FIRST_ROWS", "0"))

DAG_SCHEDULE = os.getenv("LINEAR_DAG_SCHEDULE") or "0 */1 * * *"

CURRENT_TABLE_FQN = f"{PROJECT_ID}.{DATASET_ID}.{CURRENT_TABLE_ID}"
SNAPSHOT_TABLE_FQN = f"{PROJECT_ID}.{DATASET_ID}.{SNAPSHOT_TABLE_ID}"


LINEAR_ISSUES_QUERY = """
query LinearIssues($first: Int!, $after: String) {
  issues(first: $first, after: $after) {
    nodes {
      id
      createdAt
      updatedAt
      archivedAt
      number
      identifier
      title
      description
      priority
      priorityLabel
      estimate
      startedAt
      completedAt
      canceledAt
      dueDate
      trashed
      url
      activitySummary
      summary {
        id
        content
        generationStatus
        generatedAt
      }
      previousIdentifiers
      labelIds
      team {
        id
        key
        name
      }
      state {
        id
        name
        type
        position
        color
      }
      assignee {
        id
        name
        displayName
        email
        active
      }
      creator {
        id
        name
        displayName
        email
        active
      }
      project {
        id
        name
        slugId
        description
        url
        health
        priority
        progress
        scope
        currentProgress
        startDate
        targetDate
        createdAt
        updatedAt
        completedAt
        canceledAt
        archivedAt
        status {
          id
          name
          type
        }
        lead {
          id
          name
          displayName
          email
          active
        }
        teams(first: 20) {
          nodes {
            id
            key
            name
          }
        }
      }
      cycle {
        id
        number
        name
        startsAt
        endsAt
        completedAt
        progress
      }
      labels(first: 50) {
        nodes {
          id
          name
          color
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


# =========================================================
# BIGQUERY SCHEMA
# =========================================================
COMMON_SCHEMA = [
    bigquery.SchemaField("issue_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("issue_number", "INT64", mode="NULLABLE"),
    bigquery.SchemaField("issue_identifier", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("issue_title", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("issue_description", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("issue_summary", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("issue_activity_summary", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("issue_url", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("issue_priority", "INT64", mode="NULLABLE"),
    bigquery.SchemaField("issue_priority_label", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("issue_estimate", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("issue_trashed", "BOOL", mode="NULLABLE"),
    bigquery.SchemaField("issue_created_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("issue_updated_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("issue_archived_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("issue_started_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("issue_completed_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("issue_canceled_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("issue_due_date", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("issue_previous_identifiers", "STRING", mode="REPEATED"),
    bigquery.SchemaField("issue_label_ids", "STRING", mode="REPEATED"),
    bigquery.SchemaField("issue_label_names", "STRING", mode="REPEATED"),
    bigquery.SchemaField("issue_labels_json", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("team_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("team_key", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("team_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("state_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("state_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("state_type", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("state_position", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("state_color", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("assignee_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("assignee_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("assignee_display_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("assignee_email", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("assignee_active", "BOOL", mode="NULLABLE"),
    bigquery.SchemaField("creator_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("creator_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("creator_display_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("creator_email", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("creator_active", "BOOL", mode="NULLABLE"),
    bigquery.SchemaField("project_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_slug", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_description", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_url", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_status_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_status_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_status_type", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_health", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_priority", "INT64", mode="NULLABLE"),
    bigquery.SchemaField("project_progress", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("project_scope", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("project_current_progress_json", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_start_date", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("project_target_date", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("project_created_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("project_updated_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("project_completed_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("project_canceled_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("project_archived_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("project_lead_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_lead_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_lead_display_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_lead_email", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("project_lead_active", "BOOL", mode="NULLABLE"),
    bigquery.SchemaField("project_team_ids", "STRING", mode="REPEATED"),
    bigquery.SchemaField("project_team_keys", "STRING", mode="REPEATED"),
    bigquery.SchemaField("project_team_names", "STRING", mode="REPEATED"),
    bigquery.SchemaField("cycle_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("cycle_number", "INT64", mode="NULLABLE"),
    bigquery.SchemaField("cycle_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("cycle_starts_at", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("cycle_ends_at", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("cycle_completed_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("cycle_progress", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("raw_json", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("synced_at", "TIMESTAMP", mode="REQUIRED"),
]

CURRENT_SCHEMA = COMMON_SCHEMA
SNAPSHOT_SCHEMA = [
    bigquery.SchemaField("snapshot_time", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("snapshot_hour", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED"),
    *COMMON_SCHEMA,
]


# =========================================================
# HELPERS
# =========================================================
def dbg(message: str) -> None:
    if DEBUG_VERBOSE:
        print(f"[DEBUG] {message}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except Exception:
        try:
            return int(float(str(value).strip()))
        except Exception:
            return None


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return float(int(value))
    try:
        return float(value)
    except Exception:
        return None


def to_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "t"}:
        return True
    if text in {"false", "0", "no", "n", "f"}:
        return False
    return None


def to_json_string(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def to_string_array(values: Any) -> list[str]:
    if values in (None, ""):
        return []
    if not isinstance(values, list):
        values = [values]
    return [str(item) for item in values if item not in (None, "")]


def to_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    return text[:10]


def to_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None

    try:
        normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return text


def validate_config() -> None:
    if not LINEAR_API_KEY:
        raise ValueError("Missing LINEAR_API_KEY environment variable")


def auth_header_value() -> str:
    token = LINEAR_API_KEY or ""
    return token if token.lower().startswith("bearer ") else token


def linear_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    headers = {
        "Authorization": auth_header_value(),
        "Content-Type": "application/json",
    }
    payload = {"query": query, "variables": variables}

    for attempt in range(1, 6):
        response = requests.post(
            LINEAR_API_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "2"))
            print(f"[LINEAR] rate limited, sleep={retry_after}s attempt={attempt}")
            time.sleep(retry_after)
            continue

        if response.status_code >= 500 and attempt < 5:
            sleep_seconds = min(2**attempt, 30)
            print(
                f"[LINEAR] server error status={response.status_code}, "
                f"sleep={sleep_seconds}s attempt={attempt}"
            )
            time.sleep(sleep_seconds)
            continue

        response.raise_for_status()
        data = response.json()
        errors = data.get("errors")
        if errors:
            raise RuntimeError(f"Linear GraphQL errors: {json.dumps(errors, ensure_ascii=False)[:4000]}")
        return data["data"]

    raise RuntimeError("Linear GraphQL request failed after retries")


def fetch_all_issues() -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    after = None
    page = 1

    while True:
        data = linear_graphql(
            LINEAR_ISSUES_QUERY,
            {
                "first": LINEAR_PAGE_SIZE,
                "after": after,
            },
        )
        connection = data.get("issues") or {}
        nodes = connection.get("nodes") or []
        page_info = connection.get("pageInfo") or {}

        print(f"[LINEAR] page={page} rows={len(nodes)}")
        issues.extend(nodes)

        if not page_info.get("hasNextPage"):
            break

        after = page_info.get("endCursor")
        if not after:
            break
        page += 1

    print(f"[LINEAR] total_issues={len(issues)}")
    return issues


def user_fields(user: dict[str, Any] | None, prefix: str) -> dict[str, Any]:
    user = user or {}
    return {
        f"{prefix}_id": norm(user.get("id")),
        f"{prefix}_name": norm(user.get("name")),
        f"{prefix}_display_name": norm(user.get("displayName")),
        f"{prefix}_email": norm(user.get("email")),
        f"{prefix}_active": to_bool(user.get("active")),
    }


def normalize_issue(issue: dict[str, Any], synced_at: datetime) -> dict[str, Any]:
    team = issue.get("team") or {}
    state = issue.get("state") or {}
    summary = issue.get("summary") or {}
    project = issue.get("project") or {}
    project_status = project.get("status") or {}
    project_lead = project.get("lead") or {}
    project_teams = ((project.get("teams") or {}).get("nodes") or [])
    cycle = issue.get("cycle") or {}
    labels = ((issue.get("labels") or {}).get("nodes") or [])

    row: dict[str, Any] = {
        "issue_id": norm(issue.get("id")),
        "issue_number": to_int(issue.get("number")),
        "issue_identifier": norm(issue.get("identifier")),
        "issue_title": norm(issue.get("title")),
        "issue_description": norm(issue.get("description")),
        "issue_summary": norm(summary.get("content")) if isinstance(summary, dict) else norm(summary),
        "issue_activity_summary": norm(issue.get("activitySummary")),
        "issue_url": norm(issue.get("url")),
        "issue_priority": to_int(issue.get("priority")),
        "issue_priority_label": norm(issue.get("priorityLabel")),
        "issue_estimate": to_float(issue.get("estimate")),
        "issue_trashed": to_bool(issue.get("trashed")),
        "issue_created_at": to_timestamp(issue.get("createdAt")),
        "issue_updated_at": to_timestamp(issue.get("updatedAt")),
        "issue_archived_at": to_timestamp(issue.get("archivedAt")),
        "issue_started_at": to_timestamp(issue.get("startedAt")),
        "issue_completed_at": to_timestamp(issue.get("completedAt")),
        "issue_canceled_at": to_timestamp(issue.get("canceledAt")),
        "issue_due_date": to_date(issue.get("dueDate")),
        "issue_previous_identifiers": to_string_array(issue.get("previousIdentifiers")),
        "issue_label_ids": to_string_array(issue.get("labelIds")),
        "issue_label_names": to_string_array([label.get("name") for label in labels]),
        "issue_labels_json": to_json_string(labels),
        "team_id": norm(team.get("id")),
        "team_key": norm(team.get("key")),
        "team_name": norm(team.get("name")),
        "state_id": norm(state.get("id")),
        "state_name": norm(state.get("name")),
        "state_type": norm(state.get("type")),
        "state_position": to_float(state.get("position")),
        "state_color": norm(state.get("color")),
        "project_id": norm(project.get("id")),
        "project_name": norm(project.get("name")),
        "project_slug": norm(project.get("slugId")),
        "project_description": norm(project.get("description")),
        "project_url": norm(project.get("url")),
        "project_status_id": norm(project_status.get("id")),
        "project_status_name": norm(project_status.get("name")),
        "project_status_type": norm(project_status.get("type")),
        "project_health": norm(project.get("health")),
        "project_priority": to_int(project.get("priority")),
        "project_progress": to_float(project.get("progress")),
        "project_scope": to_float(project.get("scope")),
        "project_current_progress_json": to_json_string(project.get("currentProgress")),
        "project_start_date": to_date(project.get("startDate")),
        "project_target_date": to_date(project.get("targetDate")),
        "project_created_at": to_timestamp(project.get("createdAt")),
        "project_updated_at": to_timestamp(project.get("updatedAt")),
        "project_completed_at": to_timestamp(project.get("completedAt")),
        "project_canceled_at": to_timestamp(project.get("canceledAt")),
        "project_archived_at": to_timestamp(project.get("archivedAt")),
        "project_team_ids": to_string_array([team_item.get("id") for team_item in project_teams]),
        "project_team_keys": to_string_array([team_item.get("key") for team_item in project_teams]),
        "project_team_names": to_string_array([team_item.get("name") for team_item in project_teams]),
        "cycle_id": norm(cycle.get("id")),
        "cycle_number": to_int(cycle.get("number")),
        "cycle_name": norm(cycle.get("name")),
        "cycle_starts_at": to_date(cycle.get("startsAt")),
        "cycle_ends_at": to_date(cycle.get("endsAt")),
        "cycle_completed_at": to_timestamp(cycle.get("completedAt")),
        "cycle_progress": to_float(cycle.get("progress")),
        "raw_json": to_json_string(issue),
        "synced_at": synced_at.isoformat(),
    }
    row.update(user_fields(issue.get("assignee"), "assignee"))
    row.update(user_fields(issue.get("creator"), "creator"))
    row.update(user_fields(project_lead, "project_lead"))
    return row


def snapshot_row(row: dict[str, Any], snapshot_time: datetime, snapshot_hour: datetime) -> dict[str, Any]:
    return {
        "snapshot_time": snapshot_time.isoformat(),
        "snapshot_hour": snapshot_hour.isoformat(),
        "snapshot_date": snapshot_hour.date().isoformat(),
        **row,
    }


def schema_field_names(schema: list[bigquery.SchemaField]) -> list[str]:
    return [field.name for field in schema]


def ensure_dataset_exists(client: bigquery.Client) -> None:
    dataset = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset.location = BQ_LOCATION
    client.create_dataset(dataset, exists_ok=True)
    print(f"[BQ] ensured dataset exists: {PROJECT_ID}.{DATASET_ID}")


def ensure_current_table_exists(client: bigquery.Client) -> None:
    table = bigquery.Table(CURRENT_TABLE_FQN, schema=CURRENT_SCHEMA)
    table.clustering_fields = ["project_id", "team_key", "state_name", "assignee_id"]
    client.create_table(table, exists_ok=True)
    print(f"[BQ] ensured current table exists: {CURRENT_TABLE_FQN}")


def ensure_snapshot_table_exists(client: bigquery.Client) -> None:
    table = bigquery.Table(SNAPSHOT_TABLE_FQN, schema=SNAPSHOT_SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(field="snapshot_date")
    table.clustering_fields = ["project_id", "team_key", "state_name", "assignee_id"]
    client.create_table(table, exists_ok=True)
    print(f"[BQ] ensured snapshot table exists: {SNAPSHOT_TABLE_FQN}")


def build_temp_table_fqn(base_table_id: str) -> str:
    ts = utc_now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{PROJECT_ID}.{DATASET_ID}.{base_table_id}__tmp_{ts}_{suffix}"


def create_temp_table(
    client: bigquery.Client,
    table_fqn: str,
    schema: list[bigquery.SchemaField],
    clustering_fields: list[str] | None = None,
) -> None:
    table = bigquery.Table(table_fqn, schema=schema)
    if clustering_fields:
        table.clustering_fields = clustering_fields
    client.create_table(table, exists_ok=False)
    print(f"[BQ] created temp table: {table_fqn}")


def drop_table_if_exists(client: bigquery.Client, table_fqn: str) -> None:
    client.delete_table(table_fqn, not_found_ok=True)
    print(f"[BQ] dropped temp table if exists: {table_fqn}")


def load_rows(
    client: bigquery.Client,
    rows: list[dict[str, Any]],
    table_fqn: str,
    schema: list[bigquery.SchemaField],
    write_disposition: str,
) -> int:
    if not rows:
        return 0

    job = client.load_table_from_json(
        rows,
        table_fqn,
        job_config=bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=write_disposition,
            create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            ignore_unknown_values=False,
        ),
        location=BQ_LOCATION,
    )
    job.result()
    table = client.get_table(table_fqn)
    print(f"[BQ] loaded rows={len(rows)} table_rows={table.num_rows} table={table_fqn}")
    return int(table.num_rows)


def overwrite_current_from_temp(client: bigquery.Client, temp_table_fqn: str) -> int:
    copy_job = client.copy_table(
        temp_table_fqn,
        CURRENT_TABLE_FQN,
        job_config=bigquery.CopyJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
        location=BQ_LOCATION,
    )
    copy_job.result()
    table = client.get_table(CURRENT_TABLE_FQN)
    print(f"[BQ] current table overwritten rows={table.num_rows}")
    return int(table.num_rows)


def merge_snapshot_from_temp(client: bigquery.Client, temp_table_fqn: str) -> None:
    columns = schema_field_names(SNAPSHOT_SCHEMA)
    update_columns = [column for column in columns if column not in {"snapshot_hour", "issue_id"}]
    update_clause = ",\n        ".join(f"T.`{column}` = S.`{column}`" for column in update_columns)
    insert_columns = ", ".join(f"`{column}`" for column in columns)
    insert_values = ", ".join(f"S.`{column}`" for column in columns)

    merge_sql = f"""
    MERGE `{SNAPSHOT_TABLE_FQN}` T
    USING `{temp_table_fqn}` S
    ON T.snapshot_hour = S.snapshot_hour
       AND T.issue_id = S.issue_id
    WHEN MATCHED THEN
      UPDATE SET
        {update_clause}
    WHEN NOT MATCHED THEN
      INSERT ({insert_columns})
      VALUES ({insert_values})
    """

    print("[BQ] starting snapshot MERGE temp -> target")
    client.query(merge_sql, location=BQ_LOCATION).result()
    print("[BQ] snapshot MERGE finished")


def load_current_and_snapshot(rows: list[dict[str, Any]], snapshot_rows: list[dict[str, Any]]) -> None:
    client = bigquery.Client(project=PROJECT_ID)
    ensure_dataset_exists(client)
    ensure_current_table_exists(client)
    ensure_snapshot_table_exists(client)

    if not rows:
        print("[DONE] no Linear issues found, keep current and snapshot tables unchanged")
        return

    current_temp_fqn = build_temp_table_fqn(CURRENT_TABLE_ID)
    snapshot_temp_fqn = build_temp_table_fqn(SNAPSHOT_TABLE_ID)

    try:
        create_temp_table(
            client,
            current_temp_fqn,
            CURRENT_SCHEMA,
            clustering_fields=["project_id", "team_key", "state_name", "assignee_id"],
        )
        create_temp_table(client, snapshot_temp_fqn, SNAPSHOT_SCHEMA)

        current_rows = load_rows(
            client,
            rows,
            current_temp_fqn,
            CURRENT_SCHEMA,
            bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        snapshot_loaded_rows = load_rows(
            client,
            snapshot_rows,
            snapshot_temp_fqn,
            SNAPSHOT_SCHEMA,
            bigquery.WriteDisposition.WRITE_TRUNCATE,
        )

        if current_rows <= 0:
            print("[DONE] temp current table has 0 rows, target tables remain unchanged")
            return

        target_rows = overwrite_current_from_temp(client, current_temp_fqn)
        if snapshot_loaded_rows > 0:
            merge_snapshot_from_temp(client, snapshot_temp_fqn)

        print(
            f"[DONE] Linear DWH load completed | "
            f"current_rows={target_rows} | snapshot_rows={snapshot_loaded_rows} | "
            f"current_table={CURRENT_TABLE_FQN} | snapshot_table={SNAPSHOT_TABLE_FQN}"
        )

    finally:
        drop_table_if_exists(client, current_temp_fqn)
        drop_table_if_exists(client, snapshot_temp_fqn)


# =========================================================
# DAG
# =========================================================
default_args = {
    "owner": "fanme",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="linear_project_issues_dwh",
    start_date=datetime(2026, 6, 1),
    schedule=DAG_SCHEDULE,
    catchup=False,
    default_args=default_args,
    tags=["linear", "bigquery", "dwh", "issues", "projects", "snapshot", "current"],
) as dag:

    @task
    def run_pipeline():
        validate_config()

        snapshot_time = utc_now()
        snapshot_hour = snapshot_time.replace(minute=0, second=0, microsecond=0)

        print(f"[PIPELINE] dataset={PROJECT_ID}.{DATASET_ID}")
        print(f"[PIPELINE] current_table={CURRENT_TABLE_FQN}")
        print(f"[PIPELINE] snapshot_table={SNAPSHOT_TABLE_FQN}")
        print(f"[PIPELINE] snapshot_hour={snapshot_hour.isoformat()}")

        issues = fetch_all_issues()
        rows = [normalize_issue(issue, snapshot_time) for issue in issues]
        snapshot_rows = [snapshot_row(row, snapshot_time, snapshot_hour) for row in rows]

        if DEBUG_PRINT_FIRST_ROWS > 0 and rows:
            preview = [
                {
                    "issue_identifier": row.get("issue_identifier"),
                    "project_name": row.get("project_name"),
                    "state_type": row.get("state_type"),
                    "state_name": row.get("state_name"),
                    "assignee_name": row.get("assignee_name"),
                }
                for row in rows[:DEBUG_PRINT_FIRST_ROWS]
            ]
            print(f"[LINEAR] first_rows_preview={json.dumps(preview, ensure_ascii=False)[:5000]}")

        load_current_and_snapshot(rows, snapshot_rows)

    run_pipeline()
