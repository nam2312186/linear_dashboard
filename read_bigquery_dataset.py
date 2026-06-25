#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_KEY_PATH = BASE_DIR / "keys" / "dwh-key.json"
DEFAULT_DATASET_ID = "linear_dwh"


def load_project_id_from_key(key_path: Path) -> str:
    with key_path.open("r", encoding="utf-8") as key_file:
        key_data: dict[str, Any] = json.load(key_file)

    project_id = key_data.get("project_id")
    if not project_id:
        raise RuntimeError(f"Missing project_id in service account key: {key_path}")
    return str(project_id)


def resolve_config() -> tuple[Path, str, str]:
    load_dotenv(BASE_DIR / ".env")

    key_path = Path(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or DEFAULT_KEY_PATH
    ).expanduser()
    if not key_path.is_absolute():
        key_path = (BASE_DIR / key_path).resolve()

    if not key_path.exists():
        raise FileNotFoundError(f"Service account key not found: {key_path}")

    dataset_id = os.getenv("LINEAR_BQ_DATASET") or DEFAULT_DATASET_ID
    project_id = (
        os.getenv("LINEAR_BQ_PROJECT")
        or os.getenv("GCP_PROJECT_ID")
        or load_project_id_from_key(key_path)
    )

    return key_path, project_id, dataset_id


def create_client(key_path: Path, project_id: str) -> bigquery.Client:
    credentials = service_account.Credentials.from_service_account_file(str(key_path))
    return bigquery.Client(project=project_id, credentials=credentials)


def print_dataset_summary(client: bigquery.Client, project_id: str, dataset_id: str) -> None:
    dataset_ref = f"{project_id}.{dataset_id}"
    dataset = client.get_dataset(dataset_ref)
    tables = list(client.list_tables(dataset_ref))

    print(f"Dataset: {dataset.full_dataset_id}")
    print(f"Location: {dataset.location or '-'}")
    print(f"Tables: {len(tables)}")
    print()

    if not tables:
        return

    for table_item in tables:
        table = client.get_table(table_item.reference)
        modified = table.modified.isoformat() if table.modified else "-"
        schema = ", ".join(f"{field.name}:{field.field_type}" for field in table.schema)
        print(f"- {table.table_id}")
        print(f"  type: {table.table_type}")
        print(f"  rows: {table.num_rows}")
        print(f"  modified: {modified}")
        print(f"  schema: {schema or '-'}")


def print_sample_rows(
    client: bigquery.Client, project_id: str, dataset_id: str, table_id: str, limit: int
) -> None:
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    table = client.get_table(table_ref)
    rows = client.list_rows(table, max_results=limit)

    print(f"Sample rows from {table_ref} (limit {limit}):")
    for row in rows:
        print(dict(row.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read metadata and optional sample rows from the Linear BigQuery dataset."
    )
    parser.add_argument(
        "--sample-table",
        help="Optional table ID to print sample rows from.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of sample rows to print when --sample-table is set.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    key_path, project_id, dataset_id = resolve_config()
    client = create_client(key_path, project_id)

    if args.sample_table:
        print_sample_rows(client, project_id, dataset_id, args.sample_table, args.limit)
        return

    print_dataset_summary(client, project_id, dataset_id)


if __name__ == "__main__":
    main()
