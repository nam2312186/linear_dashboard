from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_KEY_PATH = ROOT_DIR / "keys" / "dwh-key.json"
DEFAULT_PROJECT_ID = "fanme-data-warehouse"
DEFAULT_DATASET_ID = "linear_dwh"
DEFAULT_CURRENT_TABLE_ID = "linear_project_issues_current"
DEFAULT_SNAPSHOT_TABLE_ID = "linear_project_issues_snapshot_hourly"
DEFAULT_BQ_LOCATION = "asia-southeast1"


@st.cache_resource(show_spinner=False)
def load_config() -> dict[str, str]:
    load_dotenv(ROOT_DIR / ".env")

    key_path = Path(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or DEFAULT_KEY_PATH
    ).expanduser()
    if not key_path.is_absolute():
        key_path = (ROOT_DIR / key_path).resolve()

    project_id = (
        os.getenv("LINEAR_BQ_PROJECT")
        or os.getenv("GCP_PROJECT_ID")
        or DEFAULT_PROJECT_ID
    )
    dataset_id = os.getenv("LINEAR_BQ_DATASET") or DEFAULT_DATASET_ID
    current_table_id = os.getenv("LINEAR_CURRENT_TABLE") or DEFAULT_CURRENT_TABLE_ID
    snapshot_table_id = os.getenv("LINEAR_SNAPSHOT_TABLE") or DEFAULT_SNAPSHOT_TABLE_ID
    location = os.getenv("BQ_LOCATION") or DEFAULT_BQ_LOCATION

    return {
        "key_path": str(key_path),
        "project_id": project_id,
        "dataset_id": dataset_id,
        "current_table_id": current_table_id,
        "snapshot_table_id": snapshot_table_id,
        "location": location,
        "current_table": f"{project_id}.{dataset_id}.{current_table_id}",
        "snapshot_table": f"{project_id}.{dataset_id}.{snapshot_table_id}",
    }


@st.cache_resource(show_spinner=False)
def get_client(config: dict[str, str]) -> bigquery.Client:
    key_path = Path(config["key_path"])
    if key_path.exists():
        credentials = service_account.Credentials.from_service_account_file(str(key_path))
        return bigquery.Client(project=config["project_id"], credentials=credentials)
    return bigquery.Client(project=config["project_id"])


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str, params_json: str, location: str) -> pd.DataFrame:
    config = load_config()
    client = get_client(config)
    params = json.loads(params_json)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[to_query_parameter(key, value) for key, value in params.items()]
    )
    job = client.query(sql, job_config=job_config, location=location)
    return job.to_dataframe(create_bqstorage_client=False)


def to_query_parameter(key: str, value: Any) -> bigquery.QueryParameter:
    if isinstance(value, bool):
        return bigquery.ScalarQueryParameter(key, "BOOL", value)
    if isinstance(value, int):
        return bigquery.ScalarQueryParameter(key, "INT64", value)
    if isinstance(value, float):
        return bigquery.ScalarQueryParameter(key, "FLOAT64", value)
    if isinstance(value, list):
        if all(isinstance(item, int) for item in value):
            return bigquery.ArrayQueryParameter(key, "INT64", value)
        return bigquery.ArrayQueryParameter(key, "STRING", value)
    return bigquery.ScalarQueryParameter(key, "STRING", value)


def params_json(**params: Any) -> str:
    return json.dumps(params, sort_keys=True, default=str)
