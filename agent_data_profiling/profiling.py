import importlib
from datetime import datetime, timedelta

import pandas as pd

from agent_data_profiling.queries import (
    QueryConfig,
    _credential_provider,
    _get_http_path,
    _get_server_hostname,
    get_source_table_name,
    quote_identifier,
)
from agent_data_profiling.tag_catalog import validate_selected_tags


BASELINE_LOOKBACK_DAYS = 183
HISTOGRAM_BIN_COUNT = 40
GAP_THRESHOLD_MINUTES = 15


def get_profile_baseline_window(end_time: datetime) -> tuple[datetime, datetime]:
    """
    Build the half-year baseline window ending at the selected profiling end time.

    Args:
        end_time: Inclusive baseline end timestamp.

    Returns:
        tuple[datetime, datetime]: Baseline start and end timestamps.
    """
    return end_time - timedelta(days=BASELINE_LOOKBACK_DAYS), end_time


def _validate_profile_window(start_time: datetime, end_time: datetime) -> None:
    """
    Validate a profile aggregation time window.

    Args:
        start_time: Inclusive start timestamp.
        end_time: Inclusive end timestamp.

    Returns:
        None.

    Raises:
        ValueError: If the time window is invalid.
    """
    if start_time >= end_time:
        raise ValueError("Start time must be before end time.")


def _validate_profile_tag(tag: str) -> str:
    """
    Validate and normalize one tag name for profiling queries.

    Args:
        tag: Raw tag column name.

    Returns:
        str: Validated tag name.
    """
    return validate_selected_tags([tag])[0]


def build_tag_profile_stats_query(
    config: QueryConfig,
    tag: str,
    start_time: datetime,
    end_time: datetime,
    period_label: str,
) -> tuple[str, list]:
    """
    Build a SQL-side profile statistics query for one tag and period.

    Args:
        config: Raw PI query configuration.
        tag: Raw tag column name.
        start_time: Inclusive period start timestamp.
        end_time: Inclusive period end timestamp.
        period_label: Output label for this profile period.

    Returns:
        tuple[str, list]: SQL text and positional parameters.
    """
    selected_tag = _validate_profile_tag(tag)
    _validate_profile_window(start_time, end_time)
    tag_column = quote_identifier(selected_tag)
    source_table = get_source_table_name(config)

    query = f"""
        WITH profile_stats AS (
            SELECT
                ? AS period,
                COUNT(*) AS row_count,
                COUNT({tag_column}) AS non_null_count,
                COUNT(*) - COUNT({tag_column}) AS null_count,
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE (COUNT(*) - COUNT({tag_column})) / COUNT(*)
                END AS null_rate,
                AVG(CAST({tag_column} AS DOUBLE)) AS mean_value,
                STDDEV_SAMP(CAST({tag_column} AS DOUBLE)) AS stddev_value,
                MIN(CAST({tag_column} AS DOUBLE)) AS min_value,
                MAX(CAST({tag_column} AS DOUBLE)) AS max_value,
                approx_percentile(
                    CAST({tag_column} AS DOUBLE),
                    array(0.01D, 0.05D, 0.50D, 0.95D, 0.99D)
                ) AS quantiles
            FROM {source_table}
            WHERE `Pi_Timestamp` >= ?
              AND `Pi_Timestamp` <= ?
        )
        SELECT
            period,
            row_count,
            non_null_count,
            null_count,
            null_rate,
            mean_value,
            stddev_value,
            min_value,
            max_value,
            element_at(quantiles, 1) AS p1,
            element_at(quantiles, 2) AS p5,
            element_at(quantiles, 3) AS p50,
            element_at(quantiles, 4) AS p95,
            element_at(quantiles, 5) AS p99
        FROM profile_stats
    """

    return query, [period_label, start_time, end_time]


def build_tag_profile_histogram_query(
    config: QueryConfig,
    tag: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[str, list[datetime]]:
    """
    Build a SQL-side histogram query for one tag.

    Args:
        config: Raw PI query configuration.
        tag: Raw tag column name.
        start_time: Inclusive baseline start timestamp.
        end_time: Inclusive baseline end timestamp.

    Returns:
        tuple[str, list[datetime]]: SQL text and positional parameters.
    """
    selected_tag = _validate_profile_tag(tag)
    _validate_profile_window(start_time, end_time)
    tag_column = quote_identifier(selected_tag)
    source_table = get_source_table_name(config)

    query = f"""
        WITH histogram AS (
            SELECT histogram_numeric(
                CAST({tag_column} AS DOUBLE),
                {HISTOGRAM_BIN_COUNT}
            ) AS buckets
            FROM {source_table}
            WHERE `Pi_Timestamp` >= ?
              AND `Pi_Timestamp` <= ?
              AND {tag_column} IS NOT NULL
        )
        SELECT
            CAST(bucket.x AS DOUBLE) AS bin_center,
            CAST(bucket.y AS BIGINT) AS value_count
        FROM histogram
        LATERAL VIEW explode(buckets) exploded AS bucket
        ORDER BY bin_center
    """

    return query, [start_time, end_time]


def build_tag_profile_daily_trend_query(
    config: QueryConfig,
    tag: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[str, list[datetime]]:
    """
    Build a daily quantile trend query for one tag.

    Args:
        config: Raw PI query configuration.
        tag: Raw tag column name.
        start_time: Inclusive baseline start timestamp.
        end_time: Inclusive baseline end timestamp.

    Returns:
        tuple[str, list[datetime]]: SQL text and positional parameters.
    """
    selected_tag = _validate_profile_tag(tag)
    _validate_profile_window(start_time, end_time)
    tag_column = quote_identifier(selected_tag)
    source_table = get_source_table_name(config)

    query = f"""
        WITH daily_profile AS (
            SELECT
                date_trunc(
                    'DAY',
                    from_utc_timestamp(`Pi_Timestamp`, 'Pacific/Auckland')
                ) AS profile_date,
                COUNT(*) AS row_count,
                COUNT({tag_column}) AS non_null_count,
                COUNT(*) - COUNT({tag_column}) AS null_count,
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE (COUNT(*) - COUNT({tag_column})) / COUNT(*)
                END AS null_rate,
                approx_percentile(
                    CAST({tag_column} AS DOUBLE),
                    array(0.01D, 0.50D, 0.99D)
                ) AS quantiles
            FROM {source_table}
            WHERE `Pi_Timestamp` >= ?
              AND `Pi_Timestamp` <= ?
            GROUP BY date_trunc(
                'DAY',
                from_utc_timestamp(`Pi_Timestamp`, 'Pacific/Auckland')
            )
        )
        SELECT
            profile_date,
            row_count,
            non_null_count,
            null_count,
            null_rate,
            element_at(quantiles, 1) AS p1,
            element_at(quantiles, 2) AS p50,
            element_at(quantiles, 3) AS p99
        FROM daily_profile
        ORDER BY profile_date
    """

    return query, [start_time, end_time]


def build_tag_profile_gap_query(
    config: QueryConfig,
    tag: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[str, list[datetime]]:
    """
    Build a gap profile query for non-null points of one tag.

    Args:
        config: Raw PI query configuration.
        tag: Raw tag column name.
        start_time: Inclusive baseline start timestamp.
        end_time: Inclusive baseline end timestamp.

    Returns:
        tuple[str, list[datetime]]: SQL text and positional parameters.
    """
    selected_tag = _validate_profile_tag(tag)
    _validate_profile_window(start_time, end_time)
    tag_column = quote_identifier(selected_tag)
    source_table = get_source_table_name(config)

    query = f"""
        WITH ordered_points AS (
            SELECT
                `Pi_Timestamp`,
                LAG(`Pi_Timestamp`) OVER (ORDER BY `Pi_Timestamp`) AS previous_timestamp
            FROM {source_table}
            WHERE `Pi_Timestamp` >= ?
              AND `Pi_Timestamp` <= ?
              AND {tag_column} IS NOT NULL
        ),
        point_gaps AS (
            SELECT
                (
                    unix_timestamp(`Pi_Timestamp`)
                    - unix_timestamp(previous_timestamp)
                ) / 60.0 AS gap_minutes
            FROM ordered_points
            WHERE previous_timestamp IS NOT NULL
        )
        SELECT
            COUNT(*) AS interval_count,
            SUM(CASE WHEN gap_minutes > {GAP_THRESHOLD_MINUTES} THEN 1 ELSE 0 END)
                AS large_gap_count,
            AVG(gap_minutes) AS average_gap_minutes,
            MAX(gap_minutes) AS longest_gap_minutes
        FROM point_gaps
    """

    return query, [start_time, end_time]


def _fetch_dataframe(cursor, query: str, parameters: list) -> pd.DataFrame:
    """
    Execute a Databricks SQL query and return a pandas DataFrame.

    Args:
        cursor: Databricks SQL cursor.
        query: SQL text.
        parameters: Positional query parameters.

    Returns:
        pandas.DataFrame: Query result.
    """
    cursor.execute(query, parameters)
    return cursor.fetchall_arrow().to_pandas()


def fetch_tag_profile(
    config: QueryConfig,
    tag: str,
    baseline_start_time: datetime,
    baseline_end_time: datetime,
    recent_start_time: datetime,
    recent_end_time: datetime,
) -> dict[str, pd.DataFrame]:
    """
    Fetch the four tag profiling datasets used by the Streamlit UI.

    Args:
        config: Raw PI query configuration.
        tag: Raw tag column name.
        baseline_start_time: Inclusive half-year baseline start timestamp.
        baseline_end_time: Inclusive half-year baseline end timestamp.
        recent_start_time: Inclusive recent comparison start timestamp.
        recent_end_time: Inclusive recent comparison end timestamp.

    Returns:
        dict[str, pandas.DataFrame]: Histogram, daily trend, gap, and stats frames.
    """
    baseline_stats_query, baseline_stats_params = build_tag_profile_stats_query(
        config,
        tag,
        baseline_start_time,
        baseline_end_time,
        "baseline",
    )
    recent_stats_query, recent_stats_params = build_tag_profile_stats_query(
        config,
        tag,
        recent_start_time,
        recent_end_time,
        "recent",
    )
    histogram_query, histogram_params = build_tag_profile_histogram_query(
        config,
        tag,
        baseline_start_time,
        baseline_end_time,
    )
    daily_trend_query, daily_trend_params = build_tag_profile_daily_trend_query(
        config,
        tag,
        baseline_start_time,
        baseline_end_time,
    )
    gap_query, gap_params = build_tag_profile_gap_query(
        config,
        tag,
        baseline_start_time,
        baseline_end_time,
    )

    sql = importlib.import_module("databricks.sql")
    with (
        sql.connect(
            server_hostname=_get_server_hostname(),
            http_path=_get_http_path(),
            credentials_provider=_credential_provider,
            user_agent_entry="agent_data_profiling_app",
        ) as connection,
        connection.cursor() as cursor,
    ):
        baseline_stats_df = _fetch_dataframe(cursor, baseline_stats_query, baseline_stats_params)
        recent_stats_df = _fetch_dataframe(cursor, recent_stats_query, recent_stats_params)
        histogram_df = _fetch_dataframe(cursor, histogram_query, histogram_params)
        daily_trend_df = _fetch_dataframe(cursor, daily_trend_query, daily_trend_params)
        gap_df = _fetch_dataframe(cursor, gap_query, gap_params)

    return {
        "stats": pd.concat([baseline_stats_df, recent_stats_df], ignore_index=True),
        "histogram": histogram_df,
        "daily_trend": daily_trend_df,
        "gap": gap_df,
    }
