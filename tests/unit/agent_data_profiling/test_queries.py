import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_ROOT))

from agent_data_profiling.queries import (  # noqa: E402
    MAX_LOOKBACK_DAYS,
    QueryConfig,
    build_tag_history_query,
    get_source_table_name,
    quote_identifier,
)


def test_get_source_table_name_builds_raw_kag_table() -> None:
    config = QueryConfig(
        stream_catalog_raw="raw",
        source_schema="pi",
        source_table="geothermal_kag_streaming",
    )

    assert get_source_table_name(config) == "`raw`.`pi`.`geothermal_kag_streaming`"


def test_quote_identifier_rejects_backticks() -> None:
    try:
        quote_identifier("bad`name")
    except ValueError as exc:
        assert "Invalid identifier" in str(exc)
    else:
        raise AssertionError("Expected unsafe identifier to fail")


def test_build_tag_history_query_uses_only_validated_columns_and_parameters() -> None:
    now = datetime(2026, 5, 8, 0, 0, tzinfo=UTC)
    config = QueryConfig(
        stream_catalog_raw="raw",
        source_schema="pi",
        source_table="geothermal_kag_streaming",
    )

    sql, parameters = build_tag_history_query(
        config=config,
        tags=["Gross_Generator_Output", "Net_Power"],
        start_time=now - timedelta(days=7),
        end_time=now,
    )

    assert "`Pi_Timestamp`" in sql
    assert "`Gross_Generator_Output`" in sql
    assert "`Net_Power`" in sql
    assert "Injected_Bad_Tag" not in sql
    assert "WHERE `Pi_Timestamp` >= ?" in sql
    assert "AND `Pi_Timestamp` <= ?" in sql
    assert parameters == [now - timedelta(days=7), now]


def test_build_tag_history_query_rejects_unknown_tag() -> None:
    now = datetime(2026, 5, 8, 0, 0, tzinfo=UTC)
    config = QueryConfig(
        stream_catalog_raw="raw",
        source_schema="pi",
        source_table="geothermal_kag_streaming",
    )

    try:
        build_tag_history_query(
            config=config,
            tags=["Gross_Generator_Output", "Injected_Bad_Tag"],
            start_time=now - timedelta(days=7),
            end_time=now,
        )
    except ValueError as exc:
        assert "Injected_Bad_Tag" in str(exc)
    else:
        raise AssertionError("Expected unknown tag to fail")


def test_build_tag_history_query_rejects_window_over_90_days() -> None:
    now = datetime(2026, 5, 8, 0, 0, tzinfo=UTC)
    config = QueryConfig(
        stream_catalog_raw="raw",
        source_schema="pi",
        source_table="geothermal_kag_streaming",
    )

    try:
        build_tag_history_query(
            config=config,
            tags=["Gross_Generator_Output"],
            start_time=now - timedelta(days=MAX_LOOKBACK_DAYS + 1),
            end_time=now,
        )
    except ValueError as exc:
        assert "90 days" in str(exc)
    else:
        raise AssertionError("Expected long time window to fail")
