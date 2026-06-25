# Fanme Linear Streamlit Dashboard

Multipage Streamlit dashboard for the Linear BigQuery tables created by `dag.py`.

## Pages

- `Home`: executive overview, current status table, snapshot trend table.
- `Projects`: project progress, risk score, deadlines, current project update table.
- `People`: assignee workload, overdue/high-priority ownership, people update table.
- `Teams`: team workload and concentration.
- `Issues`: overdue, due soon, stale, high-priority and latest issue queues.
- `Trends`: hourly snapshot trend and inferred completion/cancel events.

## Data Sources

- Current state: `linear_project_issues_current`
- History: `linear_project_issues_snapshot_hourly`

## Run

```bash
streamlit run streamlit_dashboard/Home.py --server.baseUrlPath=linear_dashboard
```

The app reads `.env` from the repository root and uses `keys/dwh-key.json` by default.

## Logto Authentication

The dashboard uses Streamlit native OIDC authentication with Logto. Authentication is enforced before any BigQuery dashboard data is loaded.

1. In Logto Console, create a Traditional Web application.
2. Add this redirect URI for local Docker usage:

   ```text
   http://localhost:8501/linear_dashboard/oauth2callback
   ```

   Add this post sign-out redirect URI for local Docker usage:

   ```text
   http://localhost:8501/linear_dashboard/
   ```

   Production redirect URI:

   ```text
   https://datalab.fanme.vn/linear_dashboard/oauth2callback
   ```

   Production post sign-out redirect URI:

   ```text
   https://datalab.fanme.vn/linear_dashboard/
   ```

3. Copy the example secrets file and fill in the Logto values:

   ```bash
   cp .streamlit/secrets.example.toml .streamlit/secrets.toml
   ```

   Use your Logto endpoint in the metadata URL:

   ```toml
   server_metadata_url = "https://your-logto-endpoint/oidc/.well-known/openid-configuration"
   ```

The real `.streamlit/secrets.toml` file is ignored by git and mounted read-only into the Docker container by Compose.

## Docker

Build and run the image:

```bash
docker build -t linear-dashboard .
docker run --rm -p 8501:8501 --env-file .env -e GOOGLE_APPLICATION_CREDENTIALS=/app/keys/dwh-key.json -v "$PWD/keys:/app/keys:ro" -v "$PWD/.streamlit/secrets.toml:/app/.streamlit/secrets.toml:ro" linear-dashboard
```

Or use Compose:

```bash
docker compose up -d --build
```

The image does not include `.env` or `keys/*.json`. Compose reads variables from a root `.env` when it exists and otherwise uses the defaults shown in `.env.example`. Keep the service-account key in `keys/dwh-key.json`, or update `GOOGLE_APPLICATION_CREDENTIALS` and the mounted volume in `docker-compose.yml`.
The image also excludes `.streamlit/secrets.toml`; Compose mounts that local file read-only so Streamlit can read auth secrets at runtime.
