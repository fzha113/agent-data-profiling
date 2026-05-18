import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_ROOT))

from agent_data_profiling.profiling import (  # noqa: E402
    BASELINE_LOOKBACK_DAYS,
    HISTOGRAM_BIN_COUNT,
    build_tag_profile_daily_trend_query,
    build_tag_profile_gap_query,
    build_tag_profile_histogram_query,
    build_tag_profile_stats_query,
    get_profile_baseline_window,
)
from agent_data_profiling.queries import QueryConfig  # noqa: E402


def _query_config() -> QueryConfig:
    return QueryConfig(
        stream_catalog_raw="raw",
        source_schema="pi",
        source_table="geothermal_kag_streaming",
    )


def _compact_sql(query: str) -> str:
    return " ".join(query.split())


def test_get_profile_baseline_window_uses_half_year_lookback() -> None:
    end_time = datetime(2026, 5, 13, 23, 59, tzinfo=UTC)

    start_time, baseline_end = get_profile_baseline_window(end_time)

    assert baseline_end == end_time
    assert start_time == end_time - timedelta(days=BASELINE_LOOKBACK_DAYS)


def test_build_tag_profile_stats_query_returns_percentile_columns() -> None:
    start_time = datetime(2025, 11, 12, tzinfo=UTC)
    end_time = datetime(2026, 5, 13, tzinfo=UTC)

    query, parameters = build_tag_profile_stats_query(
        _query_config(),
        "Net_Power",
        start_time,
        end_time,
        "baseline",
    )
    compact_query = _compact_sql(query)

    assert "approx_percentile( CAST(`Net_Power` AS DOUBLE)" in compact_query
    assert "p1" in compact_query
    assert "p99" in compact_query
    assert "`raw`.`pi`.`geothermal_kag_streaming`" in compact_query
    assert parameters == ["baseline", start_time, end_time]


def test_build_tag_profile_histogram_query_aggregates_on_sql_side() -> None:
    start_time = datetime(2025, 11, 12, tzinfo=UTC)
    end_time = datetime(2026, 5, 13, tzinfo=UTC)

    query, parameters = build_tag_profile_histogram_query(
        _query_config(),
        "Net_Power",
        start_time,
        end_time,
    )
    compact_query = _compact_sql(query)

    assert (
        f"histogram_numeric( CAST(`Net_Power` AS DOUBLE), {HISTOGRAM_BIN_COUNT} )" in compact_query
    )
    assert "explode(buckets)" in compact_query
    assert "value_count" in compact_query
    assert parameters == [start_time, end_time]


def test_build_tag_profile_daily_trend_query_returns_rolling_quantiles() -> None:
    start_time = datetime(2025, 11, 12, tzinfo=UTC)
    end_time = datetime(2026, 5, 13, tzinfo=UTC)

    query, parameters = build_tag_profile_daily_trend_query(
        _query_config(),
        "Net_Power",
        start_time,
        end_time,
    )
    compact_query = _compact_sql(query)

    assert (
        "date_trunc( 'DAY', from_utc_timestamp(`Pi_Timestamp`, 'Pacific/Auckland') )"
        in compact_query
    )
    assert "p50" in compact_query
    assert "p99" in compact_query
    assert parameters == [start_time, end_time]


def test_build_tag_profile_gap_query_finds_long_gaps_between_non_null_points() -> None:
    start_time = datetime(2025, 11, 12, tzinfo=UTC)
    end_time = datetime(2026, 5, 13, tzinfo=UTC)

    query, parameters = build_tag_profile_gap_query(
        _query_config(),
        "Net_Power",
        start_time,
        end_time,
    )

    assert "LAG(`Pi_Timestamp`)" in query
    assert "longest_gap_minutes" in query
    assert "large_gap_count" in query
    assert parameters == [start_time, end_time]
