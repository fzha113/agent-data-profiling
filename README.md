# Agent Data Profiling

Standalone Databricks Streamlit app and data quality monitoring jobs for KAG historical PI tag profiling.

This repository does not use Databricks Asset Bundles. Runtime settings are centralized in
`config/settings.py` and `app.yaml`.

## Data Design

The app and monitoring job read the sample table and write dedicated sample monitor outputs. The
repository also keeps historical base/noisy table helpers:

| Table | Purpose |
| --- | --- |
| `workspace.default.sample_original` | One-year sample table loaded from JSON files and kept unchanged. |
| `workspace.default.sample_noisy` | Demo-safe sample table with 0-2% one-sided numeric noise. The app and data quality monitoring read this table. |
| `workspace.default.sample_monitor_log` | Hourly outlier and stuck-value monitoring results for the sample table. |
| `workspace.default.sample_monitor_incident` | Merged failed monitoring windows for the sample table. |
| `workspace.default.kag_streaming_history_base` | 2023 source slice without noise, retained for historical table helpers. |
| `workspace.default.kag_streaming_history_noisy` | 2023 source slice with one-sided 0-2% numeric noise, retained for historical table helpers. |

The noisy table uses:

```text
x + rand(seed) * 0.02 * x
```

`Pi_Timestamp` and non-numeric columns are not changed in noisy demo tables.

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
GRANT SELECT ON TABLE workspace.default.sample_noisy TO `<job-runner>`;
GRANT USE CATALOG ON CATALOG workspace TO `<job-runner>`;
GRANT USE SCHEMA ON SCHEMA workspace.default TO `<job-runner>`;
GRANT CREATE TABLE ON SCHEMA workspace.default TO `<job-runner>`;
GRANT MODIFY ON SCHEMA workspace.default TO `<job-runner>`;
```

After the app is created, grant the app service principal access:

```sql
GRANT SELECT ON TABLE workspace.default.sample_noisy TO `<app-service-principal>`;
GRANT SELECT ON TABLE workspace.default.sample_monitor_incident TO `<app-service-principal>`;
GRANT SELECT ON TABLE workspace.default.sample_monitor_log TO `<app-service-principal>`;
GRANT SELECT ON TABLE workspace.default.monitor_incident_feedback TO `<app-service-principal>`;
GRANT MODIFY ON TABLE workspace.default.monitor_incident_feedback TO `<app-service-principal>`;
GRANT CREATE TABLE ON SCHEMA workspace.default TO `<app-service-principal>`;
```

## DBA Agent UC Function Setup

The Databricks data incident multi-agent demo uses DBA evidence tools exposed through the managed
Unity Catalog function MCP server for `workspace.default`:

```text
/api/2.0/mcp/functions/workspace/default
```

Run `sql/dba_agent_uc_functions.sql` in the Databricks SQL Editor after `workspace.default.sample_noisy`,
`workspace.default.sample_monitor_incident`, `workspace.default.sample_monitor_log`, and
`workspace.default.monitor_incident_feedback` exist. The script creates the physical Delta table
`workspace.default.sample_incident_tag_values`, optimizes it with `ZORDER BY (tag_name, Pi_Timestamp)`,
and creates these read-only JSON evidence functions:

```text
workspace.default.get_app_tag_catalog()
workspace.default.get_incident_packet(incident_id STRING)
workspace.default.get_raw_points_sample(tag_names ARRAY<STRING>, start_ts TIMESTAMP, end_ts TIMESTAMP)
workspace.default.get_related_tag_window_stats(tag_names ARRAY<STRING>, start_ts TIMESTAMP, end_ts TIMESTAMP)
workspace.default.get_before_during_after_stats(tag_names ARRAY<STRING>, before_start_ts TIMESTAMP, incident_start_ts TIMESTAMP, incident_end_ts TIMESTAMP, after_end_ts TIMESTAMP)
workspace.default.get_missingness_gap_profile(tag_names ARRAY<STRING>, start_ts TIMESTAMP, end_ts TIMESTAMP)
workspace.default.get_outlier_threshold_context(tag_names ARRAY<STRING>, start_ts TIMESTAMP, end_ts TIMESTAMP, lower_threshold DOUBLE, upper_threshold DOUBLE)
```

Smoke test the slow path before testing the DBA agent:

```sql
SELECT workspace.default.get_raw_points_sample(
  array('Condenser_Pressure_A'),
  TIMESTAMP('2024-07-10 09:45:00'),
  TIMESTAMP('2024-07-10 10:30:00')
);
```

The DBA agent app service principal needs `SELECT` on the four source/evidence tables plus
`EXECUTE` on each function above. In the Databricks app resources, add the functions with short
resource keys matching the function names, for example `get_raw_points_sample`.

## Job Deployment

Create a Databricks job from `databricks_job.example.json`, or recreate the same task in the Jobs UI. The default workflow is:

1. `jobs/run_sample_quality_monitoring.py`

Before running the monitoring job, open and run
`notebooks/create_sample_noisy_table.py` in the Databricks GUI. It creates
`workspace.default.sample_noisy` from `workspace.default.sample_original` with
`x + rand() * 0.02 * x` applied to numeric columns only. `rand()` returns values in `[0, 1)`.

The sample monitoring job reads `workspace.default.sample_noisy`, evaluates `outlier` and
`stuck_value` checks for every one-hour window from `2024-06-01 00:00:00` through
`2024-10-01 00:00:00`, writes detailed rows to `workspace.default.sample_monitor_log`, and
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
