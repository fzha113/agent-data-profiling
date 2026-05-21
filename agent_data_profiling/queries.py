import importlib
import os
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from databricks.sdk.core import Config, oauth_service_principal

from agent_data_profiling.tag_catalog import validate_selected_tags


MAX_LOOKBACK_DAYS = 90


@dataclass(frozen=True)
class QueryConfig:
    """
    Runtime configuration for querying the geothermal station raw PI table.

    Args:
        stream_catalog_raw: Raw stream catalog for the active bundle target.
        source_schema: Source schema name.
        source_table: Source table name.
    """

    stream_catalog_raw: str
    source_schema: str
    source_table: str


def quote_identifier(identifier: str) -> str:
    """
    Quote a Unity Catalog identifier component.

    Args:
        identifier: Catalog, schema, table, or column identifier component.

    Returns:
        str: Backtick-quoted identifier.

    Raises:
        ValueError: If the identifier contains a backtick.
    """
    if "`" in identifier:
        raise ValueError(f"Invalid identifier: {identifier}")

    return f"`{identifier}`"


def get_source_table_name(config: QueryConfig) -> str:
    """
    Build the fully qualified geothermal station source table name.

    Args:
        config: Query runtime configuration.

    Returns:
        str: Backtick-quoted three-level table name.
    """
    return ".".join(
        [
            quote_identifier(config.stream_catalog_raw),
            quote_identifier(config.source_schema),
            quote_identifier(config.source_table),
        ]
    )


def validate_time_window(start_time: datetime, end_time: datetime) -> None:
    """
    Validate app time-window limits.

    Args:
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        None.

    Raises:
        ValueError: If the time window is invalid or exceeds 90 days.
    """
    if start_time >= end_time:
        raise ValueError("Start time must be before end time.")

    if (end_time - start_time).days > MAX_LOOKBACK_DAYS:
        raise ValueError(f"Time window must be no more than {MAX_LOOKBACK_DAYS} days.")


def build_tag_history_query(
    config: QueryConfig,
    tags: list[str] | tuple[str, ...],
    start_time: datetime,
    end_time: datetime,
) -> tuple[str, list[datetime]]:
    """
    Build a parameterized raw tag history query.

    Args:
        config: Query runtime configuration.
        tags: Selected raw tag columns.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        tuple[str, list[datetime]]: SQL text and positional parameters.

    Raises:
        ValueError: If tags or time window are invalid.
    """
    selected_tags = validate_selected_tags(tags)
    validate_time_window(start_time, end_time)

    columns = [quote_identifier("Pi_Timestamp")]
    columns.extend(quote_identifier(tag) for tag in selected_tags)
    source_table = get_source_table_name(config)

    sql = f"""
        SELECT {", ".join(columns)}
        FROM {source_table}
        WHERE `Pi_Timestamp` >= ?
          AND `Pi_Timestamp` <= ?
        ORDER BY `Pi_Timestamp`
    """

    return sql, [start_time, end_time]


def build_source_columns_query(config: QueryConfig) -> str:
    """
    Build a source-table schema query.

    Args:
        config: Query runtime configuration.

    Returns:
        str: SQL text for describing the configured source table.
    """
    return f"DESCRIBE TABLE {get_source_table_name(config)}"


def get_query_config_from_env() -> QueryConfig:
    """
    Read query configuration from Databricks App environment variables.

    Args:
        None.

    Returns:
        QueryConfig: Runtime query configuration.

    Raises:
        RuntimeError: If required environment variables are missing.
    """
    stream_catalog_raw = os.getenv("STREAM_CATALOG_RAW")
    source_schema = os.getenv("SOURCE_SCHEMA", "pi")
    source_table = os.getenv("SOURCE_TABLE", "geothermal_station_streaming")

    if not stream_catalog_raw:
        raise RuntimeError("STREAM_CATALOG_RAW is not configured.")

    return QueryConfig(
        stream_catalog_raw=stream_catalog_raw,
        source_schema=source_schema,
        source_table=source_table,
    )


def _get_server_hostname() -> str:
    host = os.getenv("DATABRICKS_HOST")
    if not host:
        raise RuntimeError("DATABRICKS_HOST is not configured.")

    parsed_host = urlparse(host).netloc or host
    return parsed_host.removeprefix("https://").removeprefix("http://")


def _get_http_path() -> str:
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID is not configured.")

    return f"/sql/1.0/warehouses/{warehouse_id}"


def _credential_provider():
    host = os.getenv("DATABRICKS_HOST")
    if not host:
        raise RuntimeError("DATABRICKS_HOST is not configured.")

    config = Config(
        host=host,
        client_id=os.getenv("DATABRICKS_CLIENT_ID"),
        client_secret=os.getenv("DATABRICKS_CLIENT_SECRET"),
    )
    return oauth_service_principal(config)


def fetch_tag_history(
    config: QueryConfig,
    tags: list[str] | tuple[str, ...],
    start_time: datetime,
    end_time: datetime,
):
    """
    Fetch raw tag history from Databricks SQL as a pandas DataFrame.

    Args:
        config: Query runtime configuration.
        tags: Selected raw tag columns.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        pandas.DataFrame: Raw tag points ordered by `Pi_Timestamp`.
    """
    query, parameters = build_tag_history_query(config, tags, start_time, end_time)
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


def fetch_source_table_columns(config: QueryConfig) -> tuple[str, ...]:
    """
    Fetch source table column names from Databricks SQL.

    Args:
        config: Query runtime configuration.

    Returns:
        tuple[str, ...]: Source table column names in table order.
    """
    query = build_source_columns_query(config)
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
        cursor.execute(query)
        rows = cursor.fetchall()

    columns = []
    for row in rows:
        column_name = row[0] if row else None
        if not column_name or str(column_name).startswith("#"):
            continue
        columns.append(str(column_name))
    return tuple(columns)
