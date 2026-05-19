# Agent Data Profiling

Standalone Databricks Streamlit app and data quality monitoring jobs for KAG historical PI tag profiling.

This repository does not use Databricks Asset Bundles. Runtime settings are centralized in
`config/settings.py` and `app.yaml`.

## Data Design

The monitoring job reads the sample table and writes dedicated sample monitor outputs. The
repository also keeps historical base/noisy table helpers for app profiling workflows:

| Table | Purpose |
| --- | --- |
| `workspace.default.sample_original` | One-year sample table used by the data quality monitoring job. |
| `workspace.default.sample_monitor_log` | Hourly outlier and stuck-value monitoring results for the sample table. |
| `workspace.default.sample_monitor_incident` | Merged failed monitoring windows for the sample table. |
| `workspace.default.kag_streaming_history_base` | 2023 source slice without noise, retained for historical table helpers. |
| `workspace.default.kag_streaming_history_noisy` | 2023 source slice with one-sided 0-2% numeric noise. The app reads this table for profiling and comparison. |

The noisy table uses:

```text
x + rand(seed) * 0.02 * x
```

`Pi_Timestamp` and non-numeric columns are not changed in the noisy profiling table. Data quality
monitoring reads `workspace.default.sample_original` directly.

## Repository Layout

```text
agent_data_profiling/       Streamlit app modules
data_quality_monitoring/    Spark data quality rules and incident merge logic
jobs/                       Databricks Spark Python task entrypoints
config/settings.py          Central table and historical window configuration
app.py                      Streamlit app entrypoint
app.yaml                    Databricks App runtime configuration
databricks_job.example.json Example Databricks Jobs API payload
```

## Databricks Setup

Create or grant access to these Unity Catalog objects in the target workspace. This version assumes all source and generated tables live under `workspace.default`:

```sql
GRANT SELECT ON TABLE workspace.default.geothermal_kag_streaming TO `<job-runner>`;
GRANT SELECT ON TABLE workspace.default.sample_original TO `<job-runner>`;
GRANT USE CATALOG ON CATALOG workspace TO `<job-runner>`;
GRANT USE SCHEMA ON SCHEMA workspace.default TO `<job-runner>`;
GRANT CREATE TABLE ON SCHEMA workspace.default TO `<job-runner>`;
GRANT MODIFY ON SCHEMA workspace.default TO `<job-runner>`;
```

After the app is created, grant the app service principal access:

```sql
GRANT SELECT ON TABLE workspace.default.kag_streaming_history_noisy TO `<app-service-principal>`;
GRANT SELECT ON TABLE workspace.default.sample_monitor_incident TO `<app-service-principal>`;
GRANT SELECT ON TABLE workspace.default.sample_monitor_log TO `<app-service-principal>`;
GRANT SELECT ON TABLE workspace.default.monitor_incident_feedback TO `<app-service-principal>`;
GRANT MODIFY ON TABLE workspace.default.monitor_incident_feedback TO `<app-service-principal>`;
GRANT CREATE TABLE ON SCHEMA workspace.default TO `<app-service-principal>`;
```

## Job Deployment

Create a Databricks job from `databricks_job.example.json`, or recreate the same task in the Jobs UI. The default workflow is:

1. `jobs/run_sample_quality_monitoring.py`

The sample monitoring job reads `workspace.default.sample_original`, evaluates `outlier` and
`stuck_value` checks for every one-hour window from `2023-01-01 00:00:00` through
`2024-01-01 00:00:00`, writes detailed rows to `workspace.default.sample_monitor_log`, and
merges failed windows into `workspace.default.sample_monitor_incident`. It intentionally excludes
`freshness_lag` because the fixed one-year sample table is expected to be stale relative to the
current clock.

`jobs/run_freshness_check.py` remains available for live or replayed data sources, but it is not
part of this sample historical workflow.

To load sample JSON files from `/Volumes/workspace/default/history_kag_sample/sample data/` into
`workspace.default.sample_original`, run `jobs/kag_stream_station_data.py`. It reads `*.json`
recursively, applies the same field renaming as the Kinesis ingestion notebook, and writes with
`overwrite` mode by default.

## App Deployment

Deploy this directory as a Databricks App. The app uses `app.yaml` to run:

```bash
streamlit run app.py
```

Add a SQL warehouse resource to the app with the resource key `sql-warehouse`. `app.yaml` injects that warehouse ID into `DATABRICKS_WAREHOUSE_ID` using `valueFrom`.

Databricks app configuration reference:

- App runtime configuration: https://docs.databricks.com/gcp/en/dev-tools/databricks-apps/app-runtime
- App environment variables and `valueFrom`: https://docs.databricks.com/gcp/en/dev-tools/databricks-apps/environment-variables
- App resources: https://docs.databricks.com/gcp/en/dev-tools/databricks-apps/resources

## Local Checks

```bash
pytest tests/unit -v
ruff check .
ruff format . --check
```
