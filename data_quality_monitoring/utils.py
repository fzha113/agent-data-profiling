from datetime import datetime, timedelta

from data_quality_monitoring.config import RULE_CONFIG
from data_quality_monitoring.schemas import get_monitor_log_schema


def get_rule_config(station: str, rule_type: str) -> dict:
    """
    Get a copy of the configured parameters for a monitoring rule.

    Args:
        station: Station identifier.
        rule_type: Monitoring rule identifier.

    Returns:
        dict: Rule configuration values.

    Raises:
        ValueError: If the station or rule type is not configured.
    """
    if station not in RULE_CONFIG:
        raise ValueError(f"Unsupported station: {station}")

    station_config = RULE_CONFIG[station]
    if rule_type not in station_config:
        raise ValueError(f"Unsupported rule type for station {station}: {rule_type}")

    return dict(station_config[rule_type])


def get_source_table_name(
    stream_catalog_raw: str,
    source_schema: str,
    source_table: str,
) -> str:
    """
    Build the full name for the source streaming table.

    Args:
        stream_catalog_raw: Raw catalog name.
        source_schema: Source schema name.
        source_table: Source table name.

    Returns:
        str: Full source table name.
    """
    return f"{stream_catalog_raw}.{source_schema}.{source_table}"


def get_run_id(station: str, run_dt: datetime) -> str:
    """
    Build the workflow run identifier for a station and timestamp.

    Args:
        station: Station identifier.
        run_dt: Run timestamp.

    Returns:
        str: Monitoring run identifier.
    """
    return f"{station}__{run_dt.strftime('%Y%m%d_%H%M%S')}"


def get_window_bounds(run_dt: datetime, window_minutes: int) -> tuple[datetime, datetime]:
    """
    Get the rounded monitoring window boundaries for a run.

    Args:
        run_dt: Run timestamp.
        window_minutes: Window size in minutes.

    Returns:
        tuple[datetime, datetime]: Window start and end timestamps.
    """
    window_end = run_dt.replace(second=0, microsecond=0)
    window_start = window_end - timedelta(minutes=window_minutes)
    return window_start, window_end


def write_monitor_results(spark, rows: list[dict], table_name: str) -> None:
    """
    Append monitoring results to the quality log table.

    Args:
        spark: Active Spark session.
        rows: Monitoring result rows.
        table_name: Fully qualified monitor log table name.

    Returns:
        None: This function writes rows as a side effect.
    """
    result_df = spark.createDataFrame(rows, schema=get_monitor_log_schema())
    result_df.write.mode("append").saveAsTable(table_name)
