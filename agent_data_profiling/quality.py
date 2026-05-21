import importlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

from agent_data_profiling.queries import (
    QueryConfig,
    _credential_provider,
    _get_http_path,
    _get_server_hostname,
    get_source_table_name,
    quote_identifier,
    validate_time_window,
)


INCIDENT_CONTEXT_HOURS = 1
QUALITY_INCIDENT_LOOKBACK_DAYS = 7
QUALITY_MONITOR_REFRESH_MINUTES = 15


@dataclass(frozen=True)
class DataQualityConfig:
    """
    Runtime configuration for querying data quality monitor tables.

    Args:
        monitor_catalog: Catalog containing monitor tables.
        monitor_schema: Schema containing monitor tables.
        incident_table: Incident SCD table name.
        quality_log_table: Detailed quality log table name.
        feedback_table: Human feedback table name.
        station: Station identifier to display.
        source_table: Monitored source table used to filter incident rows.
    """

    monitor_catalog: str
    monitor_schema: str
    incident_table: str
    quality_log_table: str
    feedback_table: str
    station: str
    source_table: str | None = None


def _get_table_name(config: DataQualityConfig, table_name: str) -> str:
    return ".".join(
        [
            quote_identifier(config.monitor_catalog),
            quote_identifier(config.monitor_schema),
            quote_identifier(table_name),
        ]
    )


def get_incident_table_name(config: DataQualityConfig) -> str:
    """
    Build the fully qualified monitor incident table name.

    Args:
        config: Data quality runtime configuration.

    Returns:
        str: Backtick-quoted three-level table name.
    """
    return _get_table_name(config, config.incident_table)


def get_quality_log_table_name(config: DataQualityConfig) -> str:
    """
    Build the fully qualified monitor quality log table name.

    Args:
        config: Data quality runtime configuration.

    Returns:
        str: Backtick-quoted three-level table name.
    """
    return _get_table_name(config, config.quality_log_table)


def get_feedback_table_name(config: DataQualityConfig) -> str:
    """
    Build the fully qualified monitor incident feedback table name.

    Args:
        config: Data quality runtime configuration.

    Returns:
        str: Backtick-quoted three-level table name.
    """
    return _get_table_name(config, config.feedback_table)


def get_data_quality_config_from_env() -> DataQualityConfig:
    """
    Read data quality table configuration from Databricks App environment variables.

    Args:
        None.

    Returns:
        DataQualityConfig: Runtime data quality configuration.

    Raises:
        RuntimeError: If required environment variables are missing.
    """
    monitor_catalog = os.getenv("MONITOR_CATALOG")
    monitor_schema = os.getenv("MONITOR_SCHEMA", "geothermal")
    monitor_source_table = os.getenv("MONITOR_SOURCE_TABLE")

    if not monitor_catalog:
        raise RuntimeError("MONITOR_CATALOG is not configured.")

    if monitor_source_table is None:
        stream_catalog_raw = os.getenv("STREAM_CATALOG_RAW")
        if stream_catalog_raw:
            monitor_source_table = ".".join(
                [
                    stream_catalog_raw,
                    os.getenv("SOURCE_SCHEMA", "pi"),
                    os.getenv("SOURCE_TABLE", "geothermal_station_streaming"),
                ]
            )

    return DataQualityConfig(
        monitor_catalog=monitor_catalog,
        monitor_schema=monitor_schema,
        incident_table=os.getenv("MONITOR_INCIDENT_TABLE", "monitor_incident"),
        quality_log_table=os.getenv("MONITOR_QUALITY_LOG_TABLE", "monitor_quality_log"),
        feedback_table=os.getenv(
            "MONITOR_INCIDENT_FEEDBACK_TABLE",
            "monitor_incident_feedback",
        ),
        station=os.getenv("STATION", "geothermal station"),
        source_table=monitor_source_table,
    )


def get_incident_plot_window(
    incident_start: datetime,
    incident_end: datetime,
) -> tuple[datetime, datetime]:
    """
    Add context around an incident for raw PI plotting.

    Args:
        incident_start: Incident start timestamp.
        incident_end: Incident end timestamp.

    Returns:
        tuple[datetime, datetime]: Plot start and end timestamps.
    """
    context = timedelta(hours=INCIDENT_CONTEXT_HOURS)
    return incident_start - context, incident_end + context


def build_incident_tag_history_query(
    raw_config: QueryConfig,
    tag_name: str,
    start_time: datetime,
    end_time: datetime,
) -> tuple[str, list[object]]:
    """
    Build a raw PI query for one monitor incident tag.

    Args:
        raw_config: Raw PI table query configuration.
        tag_name: Raw PI tag column from the monitor incident.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        tuple[str, list[object]]: SQL text and positional parameters.

    Raises:
        ValueError: If the tag identifier or time window is invalid.
    """
    validate_time_window(start_time, end_time)
    tag_column = quote_identifier(tag_name)
    source_table = get_source_table_name(raw_config)
    sql = f"""
        SELECT `Pi_Timestamp`, {tag_column}
        FROM {source_table}
        WHERE `Pi_Timestamp` >= ?
          AND `Pi_Timestamp` <= ?
        ORDER BY `Pi_Timestamp`
    """
    return sql, [start_time, end_time]


def build_recent_incidents_query(
    config: DataQualityConfig,
    since_time: datetime,
) -> tuple[str, list[object]]:
    """
    Build a query for recent failed data quality incidents and matched log rows.

    Args:
        config: Data quality runtime configuration.
        since_time: Lower bound for recently updated incidents.

    Returns:
        tuple[str, list[object]]: SQL text and positional parameters.
    """
    incident_table = get_incident_table_name(config)
    quality_log_table = get_quality_log_table_name(config)
    feedback_table = get_feedback_table_name(config)
    source_filter_sql = ""
    parameters: list[object] = []
    if config.source_table:
        source_filter_sql = "\n          AND incident.source_table = ?"
        parameters.append(config.source_table)

    sql = f"""
        WITH feedback AS (
            SELECT
                incident_id,
                COUNT(*) AS feedback_count,
                MAX(create_ts) AS latest_feedback_ts
            FROM {feedback_table}
            GROUP BY incident_id
        )
        SELECT
            incident.incident_id,
            incident.station,
            incident.source_table,
            incident.tag_name,
            incident.rule_type,
            incident.status,
            incident.incident_start,
            incident.incident_end,
            incident.first_run_id,
            incident.last_run_id,
            incident.create_ts AS incident_create_ts,
            incident.update_ts AS incident_update_ts,
            quality_log.run_id AS log_run_id,
            quality_log.window_start,
            quality_log.window_end,
            quality_log.observed_value,
            quality_log.create_ts AS log_create_ts,
            feedback.feedback_count,
            feedback.latest_feedback_ts
        FROM {incident_table} AS incident
        LEFT JOIN {quality_log_table} AS quality_log
          ON quality_log.station = incident.station
         AND quality_log.source_table = incident.source_table
         AND quality_log.tag_name = incident.tag_name
         AND quality_log.rule_type = incident.rule_type
         AND quality_log.status = incident.status
         AND quality_log.window_start <= incident.incident_end
         AND quality_log.window_end >= incident.incident_start
        LEFT JOIN feedback
          ON feedback.incident_id = incident.incident_id
        WHERE incident.status = 'failed'{source_filter_sql}
          AND (incident.update_ts >= ? OR feedback.feedback_count IS NULL)
        ORDER BY incident.update_ts DESC, incident.incident_start DESC, quality_log.window_start
    """

    parameters.append(since_time)
    return sql, parameters


def normalise_quality_incident_display_columns(df, config: DataQualityConfig):
    """
    Replace stored monitor identifiers with safe app display labels.

    Args:
        df: Incident rows returned by the monitor query.
        config: Data quality runtime configuration.

    Returns:
        pandas.DataFrame: Copy of the input rows with display-safe identifier columns.
    """
    normalised_df = df.copy()
    if "station" in normalised_df.columns:
        normalised_df["station"] = config.station
    if config.source_table and "source_table" in normalised_df.columns:
        normalised_df["source_table"] = config.source_table
    return normalised_df


def build_feedback_table_ddl(config: DataQualityConfig) -> str:
    """
    Build DDL for the monitor incident feedback table.

    Args:
        config: Data quality runtime configuration.

    Returns:
        str: SQL DDL statement.
    """
    feedback_table = get_feedback_table_name(config)
    return f"""
        CREATE TABLE IF NOT EXISTS {feedback_table} (
            incident_id STRING,
            comment STRING,
            created_by STRING,
            create_ts TIMESTAMP
        ) USING DELTA
    """


def build_feedback_insert_query(
    config: DataQualityConfig,
    incident_id: str,
    comment: str,
) -> tuple[str, list[object]]:
    """
    Build an insert statement for one incident feedback comment.

    Args:
        config: Data quality runtime configuration.
        incident_id: Incident identifier.
        comment: Human investigation comment.

    Returns:
        tuple[str, list[object]]: SQL text and positional parameters.

    Raises:
        ValueError: If the comment is empty.
    """
    stripped_comment = comment.strip()
    if not stripped_comment:
        raise ValueError("Comment cannot be empty.")

    feedback_table = get_feedback_table_name(config)
    sql = f"""
        INSERT INTO {feedback_table} (
            incident_id,
            comment,
            created_by,
            create_ts
        )
        VALUES (?, ?, current_user(), current_timestamp())
    """
    return sql, [incident_id, stripped_comment]


def _fetch_dataframe(query: str, parameters: list[object]):
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
        cursor.execute(query, parameters)
        return cursor.fetchall_arrow().to_pandas()


def _execute_statement(query: str, parameters: list[object] | None = None) -> None:
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
        cursor.execute(query, parameters or [])


def fetch_recent_quality_incidents(
    config: DataQualityConfig,
    since_time: datetime,
):
    """
    Fetch recent failed monitor incidents and their matched quality log rows.

    Args:
        config: Data quality runtime configuration.
        since_time: Lower bound for recently updated incidents.

    Returns:
        pandas.DataFrame: Joined incident and quality log rows.
    """
    query, parameters = build_recent_incidents_query(config, since_time)
    df = _fetch_dataframe(query, parameters)
    return normalise_quality_incident_display_columns(df, config)


def fetch_incident_tag_history(
    raw_config: QueryConfig,
    tag_name: str,
    start_time: datetime,
    end_time: datetime,
):
    """
    Fetch raw PI history for one monitor incident tag.

    Args:
        raw_config: Raw PI table query configuration.
        tag_name: Raw PI tag column from the monitor incident.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        pandas.DataFrame: Raw tag points ordered by `Pi_Timestamp`.
    """
    query, parameters = build_incident_tag_history_query(
        raw_config,
        tag_name,
        start_time,
        end_time,
    )
    return _fetch_dataframe(query, parameters)


def ensure_monitor_incident_feedback_table(config: DataQualityConfig) -> None:
    """
    Create the incident feedback table if it does not exist.

    Args:
        config: Data quality runtime configuration.

    Returns:
        None: This function creates the table as a side effect.
    """
    _execute_statement(build_feedback_table_ddl(config))


def insert_incident_feedback(
    config: DataQualityConfig,
    incident_id: str,
    comment: str,
) -> None:
    """
    Insert a human feedback comment for one incident.

    Args:
        config: Data quality runtime configuration.
        incident_id: Incident identifier.
        comment: Human investigation comment.

    Returns:
        None: This function writes one feedback row as a side effect.
    """
    query, parameters = build_feedback_insert_query(config, incident_id, comment)
    _execute_statement(query, parameters)
