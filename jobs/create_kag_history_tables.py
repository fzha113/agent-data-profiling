from dataclasses import dataclass

from config.settings import DEFAULT_SETTINGS, HistoricalDataSettings


NUMERIC_TYPE_PREFIXES = (
    "byte",
    "short",
    "int",
    "integer",
    "long",
    "bigint",
    "float",
    "double",
    "decimal",
)


@dataclass(frozen=True)
class ColumnSpec:
    """
    Minimal column metadata needed to build the noisy table projection.

    Args:
        name: Column name from the base table.
        type_name: Databricks SQL type string from DESCRIBE.
    """

    name: str
    type_name: str


def quote_identifier(identifier: str) -> str:
    """
    Quote a SQL identifier component.

    Args:
        identifier: Identifier component.

    Returns:
        str: Backtick-quoted identifier.

    Raises:
        ValueError: If the identifier contains a backtick.
    """
    if "`" in identifier:
        raise ValueError(f"Invalid identifier: {identifier}")
    return f"`{identifier}`"


def is_numeric_type_name(type_name: str) -> bool:
    """
    Check whether a Databricks SQL type string is numeric.

    Args:
        type_name: Databricks SQL type string.

    Returns:
        bool: True when the type is numeric.
    """
    normalized_type = type_name.strip().lower()
    return normalized_type.startswith(NUMERIC_TYPE_PREFIXES)


def build_create_base_table_sql(settings: HistoricalDataSettings = DEFAULT_SETTINGS) -> str:
    """
    Build SQL that creates the unmodified historical base table.

    Args:
        settings: Historical data table settings.

    Returns:
        str: CREATE TABLE AS SELECT SQL.
    """
    timestamp_col = quote_identifier(settings.timestamp_col)
    return f"""
        CREATE OR REPLACE TABLE {settings.base_table} AS
        SELECT *
        FROM {settings.source_table}
        WHERE {timestamp_col} >= TIMESTAMP('{settings.history_start_ts}')
          AND {timestamp_col} < TIMESTAMP('{settings.history_end_ts}')
    """


def build_create_noisy_table_sql(
    settings: HistoricalDataSettings,
    columns: list[ColumnSpec],
) -> str:
    """
    Build SQL that creates the noisy historical table from the base table.

    Args:
        settings: Historical data table settings.
        columns: Ordered base table columns.

    Returns:
        str: CREATE TABLE AS SELECT SQL.
    """
    select_exprs = []
    noisy_column_count = 0
    for column in columns:
        column_name = quote_identifier(column.name)
        if column.name != settings.timestamp_col and is_numeric_type_name(column.type_name):
            seed = settings.noise_seed + noisy_column_count
            noisy_column_count += 1
            select_exprs.append(
                f"(CAST({column_name} AS DOUBLE) + rand({seed}) * "
                f"{settings.noise_rate}D * CAST({column_name} AS DOUBLE)) AS {column_name}"
            )
        else:
            select_exprs.append(column_name)

    projection_sql = ",\n            ".join(select_exprs)
    return f"""
        CREATE OR REPLACE TABLE {settings.noisy_table} AS
        SELECT
            {projection_sql}
        FROM {settings.base_table}
    """


def get_base_table_columns(spark, settings: HistoricalDataSettings) -> list[ColumnSpec]:
    """
    Read base table column metadata from Databricks SQL.

    Args:
        spark: Active Spark session.
        settings: Historical data table settings.

    Returns:
        list[ColumnSpec]: Ordered column metadata for ordinary table columns.
    """
    rows = spark.sql(f"DESCRIBE {settings.base_table}").collect()
    columns = []
    for row in rows:
        column_name = row["col_name"]
        type_name = row["data_type"]
        if not column_name or column_name.startswith("#"):
            continue
        columns.append(ColumnSpec(name=column_name, type_name=type_name))
    return columns


def create_history_tables(spark, settings: HistoricalDataSettings = DEFAULT_SETTINGS) -> None:
    """
    Create the base and noisy KAG historical tables.

    Args:
        spark: Active Spark session.
        settings: Historical data table settings.

    Returns:
        None: Tables are created as a side effect.
    """
    spark.sql(build_create_base_table_sql(settings))
    columns = get_base_table_columns(spark, settings)
    spark.sql(build_create_noisy_table_sql(settings, columns))


if __name__ == "__main__":
    create_history_tables(spark)
