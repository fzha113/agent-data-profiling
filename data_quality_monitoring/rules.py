import json
from datetime import datetime, timedelta

from data_quality_monitoring.utils import get_run_id, get_window_bounds


def run_stuck_value_check(
    spark,
    run_dt: datetime,
    station: str,
    source_table: str,
    tags: list[str],
    rule_config: dict,
) -> list[dict]:
    """
    Run the stuck value rule across the configured tags.

    Args:
        spark: Active Spark session.
        run_dt: Run timestamp.
        station: Station identifier.
        source_table: Full source table name.
        tags: Tags monitored by the rule.
        rule_config: Rule configuration values.

    Returns:
        list[dict]: Monitoring log rows for the stuck value rule.
    """
    run_id = get_run_id(station, run_dt)

    lookback_minutes = int(rule_config["lookback_minutes"])
    min_expected_rows = int(rule_config["min_expected_rows"])
    max_range = float(rule_config["max_range"])
    timestamp_col = rule_config["timestamp_col"]
    zero_filtered_tags = set(rule_config.get("zero_filtered_tags", []))

    window_start, window_end = get_window_bounds(run_dt, lookback_minutes)

    agg_exprs = []
    for tag in tags:
        tag_expr = f"`{tag}`"
        if tag in zero_filtered_tags:
            tag_expr = f"CASE WHEN `{tag}` <> 0 THEN `{tag}` END"

        agg_exprs.append(f"COUNT({tag_expr}) AS `{tag}_valid_count`")
        agg_exprs.append(f"MIN({tag_expr}) AS `{tag}_min_value`")
        agg_exprs.append(f"MAX({tag_expr}) AS `{tag}_max_value`")

    agg_sql = ",\n        ".join(agg_exprs)

    df_tag_check = spark.sql(f"""
        SELECT
            {agg_sql}
        FROM {source_table}
        WHERE {timestamp_col} >= TIMESTAMP('{window_start.strftime("%Y-%m-%d %H:%M:%S")}')
          AND {timestamp_col} < TIMESTAMP('{window_end.strftime("%Y-%m-%d %H:%M:%S")}')
    """)

    row = df_tag_check.first()
    results = []

    for tag in tags:
        valid_count = int(row[f"{tag}_valid_count"])
        min_value = row[f"{tag}_min_value"]
        max_value = row[f"{tag}_max_value"]

        if valid_count < min_expected_rows or min_value is None or max_value is None:
            status = "skipped"
            observed_value = json.dumps(
                {
                    "valid_count": valid_count,
                    "min_value": min_value,
                    "max_value": max_value,
                    "range": None,
                }
            )
        else:
            observed_range = float(max_value) - float(min_value)
            status = "failed" if observed_range <= max_range else "pass"
            observed_value = json.dumps(
                {
                    "valid_count": valid_count,
                    "min_value": float(min_value),
                    "max_value": float(max_value),
                    "range": observed_range,
                }
            )

        results.append(
            {
                "run_id": run_id,
                "station": station,
                "source_table": source_table,
                "tag_name": tag,
                "rule_type": "stuck_value",
                "window_start": window_start,
                "window_end": window_end,
                "status": status,
                "observed_value": observed_value,
                "create_ts": run_dt,
            }
        )

    return results


def run_outlier_check(
    spark,
    run_dt: datetime,
    station: str,
    source_table: str,
    tags: list[str],
    rule_config: dict,
) -> list[dict]:
    """
    Run the outlier rule across the configured tags.

    Args:
        spark: Active Spark session.
        run_dt: Run timestamp.
        station: Station identifier.
        source_table: Full source table name.
        tags: Tags monitored by the rule.
        rule_config: Rule configuration values.

    Returns:
        list[dict]: Monitoring log rows for the outlier rule.
    """
    run_id = get_run_id(station, run_dt)

    lookback_minutes = int(rule_config["lookback_minutes"])
    history_days = int(rule_config["history_days"])
    outlier_multiplier = float(rule_config["outlier_multiplier"])
    timestamp_col = rule_config["timestamp_col"]

    window_start, window_end = get_window_bounds(run_dt, lookback_minutes)
    history_end = window_start
    history_start = history_end - timedelta(days=history_days)

    recent_agg_exprs = []
    history_bounds_exprs = []
    history_threshold_exprs = []
    bounds_exprs = []

    for tag in tags:
        recent_agg_exprs.append(f"MIN(`{tag}`) AS `{tag}_recent_min`")
        recent_agg_exprs.append(f"MAX(`{tag}`) AS `{tag}_recent_max`")
        history_bounds_exprs.append(f"PERCENTILE_APPROX(`{tag}`, 0.25) AS `{tag}_history_q1`")
        history_bounds_exprs.append(f"PERCENTILE_APPROX(`{tag}`, 0.75) AS `{tag}_history_q3`")
        history_threshold_exprs.append(
            f"PERCENTILE_APPROX(CASE "
            f"WHEN `{tag}` BETWEEN bounds.`{tag}_lower_fence` AND bounds.`{tag}_upper_fence` "
            f"THEN `{tag}` END, 0.01) AS `{tag}_history_p1`"
        )
        history_threshold_exprs.append(
            f"PERCENTILE_APPROX(CASE "
            f"WHEN `{tag}` BETWEEN bounds.`{tag}_lower_fence` AND bounds.`{tag}_upper_fence` "
            f"THEN `{tag}` END, 0.99) AS `{tag}_history_p99`"
        )
        bounds_exprs.append(
            f"`{tag}_history_q1` - ((`{tag}_history_q3` - `{tag}_history_q1`) * 1.5) AS `{tag}_lower_fence`"
        )
        bounds_exprs.append(
            f"`{tag}_history_q3` + ((`{tag}_history_q3` - `{tag}_history_q1`) * 1.5) AS `{tag}_upper_fence`"
        )

    recent_agg_sql = ",\n        ".join(recent_agg_exprs)
    history_bounds_sql = ",\n        ".join(history_bounds_exprs)
    history_threshold_sql = ",\n        ".join(history_threshold_exprs)
    bounds_sql = ",\n            ".join(bounds_exprs)

    df_recent_check = spark.sql(f"""
        SELECT
            {recent_agg_sql}
        FROM {source_table}
        WHERE {timestamp_col} >= TIMESTAMP('{window_start.strftime("%Y-%m-%d %H:%M:%S")}')
          AND {timestamp_col} < TIMESTAMP('{window_end.strftime("%Y-%m-%d %H:%M:%S")}')
    """)

    df_history_check = spark.sql(f"""
        WITH history_source AS (
            SELECT *
            FROM {source_table}
            WHERE {timestamp_col} >= TIMESTAMP('{history_start.strftime("%Y-%m-%d %H:%M:%S")}')
              AND {timestamp_col} < TIMESTAMP('{history_end.strftime("%Y-%m-%d %H:%M:%S")}')
        ),
        history_bounds AS (
            SELECT
                {history_bounds_sql}
            FROM history_source
        ),
        bounds AS (
            SELECT
                {bounds_sql}
            FROM history_bounds
        )
        SELECT
            {history_threshold_sql}
        FROM history_source
        CROSS JOIN bounds
    """)

    recent_row = df_recent_check.first()
    history_row = df_history_check.first()
    results = []

    for tag in tags:
        recent_min = recent_row[f"{tag}_recent_min"]
        recent_max = recent_row[f"{tag}_recent_max"]
        history_p1 = history_row[f"{tag}_history_p1"]
        history_p99 = history_row[f"{tag}_history_p99"]

        if None in (recent_min, recent_max, history_p1, history_p99):
            status = "skipped"
            observed_value = json.dumps(
                {
                    "recent_min": recent_min,
                    "recent_max": recent_max,
                    "history_p1": history_p1,
                    "history_p99": history_p99,
                }
            )
        else:
            upper_threshold = float(history_p99) * outlier_multiplier
            lower_threshold = float(history_p1) - (
                abs(float(history_p1)) * (outlier_multiplier - 1.0)
            )
            failed_upper = float(recent_max) > upper_threshold
            failed_lower = float(recent_min) < lower_threshold
            status = "failed" if failed_upper or failed_lower else "pass"
            observed_value = json.dumps(
                {
                    "recent_min": float(recent_min),
                    "recent_max": float(recent_max),
                    "history_p1": float(history_p1),
                    "history_p99": float(history_p99),
                    "lower_threshold": lower_threshold,
                    "upper_threshold": upper_threshold,
                }
            )

        results.append(
            {
                "run_id": run_id,
                "station": station,
                "source_table": source_table,
                "tag_name": tag,
                "rule_type": "outlier",
                "window_start": window_start,
                "window_end": window_end,
                "status": status,
                "observed_value": observed_value,
                "create_ts": run_dt,
            }
        )

    return results


def run_freshness_check(
    spark,
    run_dt: datetime,
    station: str,
    source_table: str,
    rule_config: dict,
) -> list[dict]:
    """
    Run the freshness rule for the source table.

    Args:
        spark: Active Spark session.
        run_dt: Run timestamp.
        station: Station identifier.
        source_table: Full source table name.
        rule_config: Rule configuration values.

    Returns:
        list[dict]: Monitoring log rows for the freshness rule.
    """
    run_id = get_run_id(station, run_dt)

    window_size_minutes = int(rule_config["max_lag_minutes"])
    timestamp_col = rule_config["timestamp_col"]
    window_start, window_end = get_window_bounds(run_dt, window_size_minutes)

    df_quality = spark.sql(
        f"""
        WITH source_data AS (
            SELECT COALESCE(MAX({timestamp_col}), timestamp('1900-01-01')) AS max_pi_ts
            FROM {source_table}
        )
        SELECT
            '{station}' AS station,
            '{source_table}' AS source_table,
            max_pi_ts AS latest_batch_ts,
            current_timestamp() AS current_ts,
            timestampdiff(second, max_pi_ts, current_timestamp()) / 60.0 AS lag_in_minutes,
            max_pi_ts < current_timestamp() - INTERVAL {window_size_minutes} MINUTES AS is_failed
        FROM source_data
        """
    )

    return [
        {
            "run_id": run_id,
            "station": row["station"],
            "source_table": row["source_table"],
            "tag_name": "_table_",
            "rule_type": "freshness_lag",
            "window_start": window_start,
            "window_end": window_end,
            "observed_value": json.dumps(
                {
                    "late_in_minutes": float(row["lag_in_minutes"]),
                    "latest_batch_ts": row["latest_batch_ts"].strftime("%Y-%m-%d %H:%M:%S"),
                    "current_ts": row["current_ts"].strftime("%Y-%m-%d %H:%M:%S"),
                }
            ),
            "status": "failed" if row["is_failed"] else "pass",
            "create_ts": run_dt,
        }
        for row in df_quality.collect()
    ]
