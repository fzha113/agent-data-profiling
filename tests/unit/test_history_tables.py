from config.settings import DEFAULT_SETTINGS, HistoricalDataSettings
from jobs.create_kag_history_tables import (
    ColumnSpec,
    build_create_base_table_sql,
    build_create_noisy_table_sql,
    is_numeric_type_name,
)


def test_default_settings_use_base_table_for_quality_and_noisy_table_for_app() -> None:
    assert DEFAULT_SETTINGS.dq_source_table == DEFAULT_SETTINGS.base_table
    assert DEFAULT_SETTINGS.app_profile_source_table == DEFAULT_SETTINGS.noisy_table
    assert DEFAULT_SETTINGS.history_start_ts == "2023-01-01 00:00:00"
    assert DEFAULT_SETTINGS.history_end_ts == "2024-01-01 00:00:00"


def test_build_create_base_table_sql_filters_2023_calendar_year() -> None:
    settings = HistoricalDataSettings(
        source_table="raw.pi.geothermal_kag_streaming",
        base_table="generation.geothermal.kag_streaming_history_base",
        noisy_table="generation.geothermal.kag_streaming_history_noisy",
        history_start_ts="2023-01-01 00:00:00",
        history_end_ts="2024-01-01 00:00:00",
    )

    sql = build_create_base_table_sql(settings)

    assert "CREATE OR REPLACE TABLE generation.geothermal.kag_streaming_history_base AS" in sql
    assert "FROM raw.pi.geothermal_kag_streaming" in sql
    assert "`Pi_Timestamp` >= TIMESTAMP('2023-01-01 00:00:00')" in sql
    assert "`Pi_Timestamp` < TIMESTAMP('2024-01-01 00:00:00')" in sql


def test_build_create_noisy_table_sql_noises_only_numeric_non_timestamp_columns() -> None:
    settings = HistoricalDataSettings(
        source_table="raw.pi.geothermal_kag_streaming",
        base_table="generation.geothermal.kag_streaming_history_base",
        noisy_table="generation.geothermal.kag_streaming_history_noisy",
        noise_rate=0.02,
        noise_seed=42,
    )
    columns = [
        ColumnSpec(name="Pi_Timestamp", type_name="timestamp"),
        ColumnSpec(name="Net_Power", type_name="double"),
        ColumnSpec(name="Station_Name", type_name="string"),
        ColumnSpec(name="Quality_Count", type_name="bigint"),
    ]

    sql = build_create_noisy_table_sql(settings, columns)

    assert "CREATE OR REPLACE TABLE generation.geothermal.kag_streaming_history_noisy AS" in sql
    assert "FROM generation.geothermal.kag_streaming_history_base" in sql
    assert "`Pi_Timestamp`" in sql
    assert "`Station_Name`" in sql
    assert "rand(42)" in sql
    assert "rand(43)" in sql
    assert "0.02D * CAST(`Net_Power` AS DOUBLE)" in sql
    assert "0.02D * CAST(`Quality_Count` AS DOUBLE)" in sql
    assert "0.02D * CAST(`Pi_Timestamp` AS DOUBLE)" not in sql
    assert "0.02D * CAST(`Station_Name` AS DOUBLE)" not in sql


def test_is_numeric_type_name_accepts_databricks_numeric_types() -> None:
    assert is_numeric_type_name("double")
    assert is_numeric_type_name("decimal(18,2)")
    assert is_numeric_type_name("BIGINT")
    assert not is_numeric_type_name("timestamp")
    assert not is_numeric_type_name("string")
