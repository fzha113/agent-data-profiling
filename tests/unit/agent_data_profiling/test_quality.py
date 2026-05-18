import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_ROOT))

from agent_data_profiling.quality import (  # noqa: E402
    DataQualityConfig,
    build_feedback_insert_query,
    build_feedback_table_ddl,
    build_incident_tag_history_query,
    build_recent_incidents_query,
    get_feedback_table_name,
    get_incident_plot_window,
    get_incident_table_name,
    get_quality_log_table_name,
)
from agent_data_profiling.queries import QueryConfig  # noqa: E402


def test_monitor_table_names_are_quoted() -> None:
    config = DataQualityConfig(
        monitor_catalog="dev_generation",
        monitor_schema="geothermal",
        incident_table="monitor_incident",
        quality_log_table="monitor_quality_log",
        feedback_table="monitor_incident_feedback",
        station="KAG",
    )

    assert get_incident_table_name(config) == "`dev_generation`.`geothermal`.`monitor_incident`"
    assert (
        get_quality_log_table_name(config) == "`dev_generation`.`geothermal`.`monitor_quality_log`"
    )
    assert (
        get_feedback_table_name(config)
        == "`dev_generation`.`geothermal`.`monitor_incident_feedback`"
    )


def test_build_recent_incidents_query_joins_logs_for_recent_failed_incidents() -> None:
    since_time = datetime(2026, 5, 1, 0, 0, tzinfo=UTC)
    config = DataQualityConfig(
        monitor_catalog="generation",
        monitor_schema="geothermal",
        incident_table="monitor_incident",
        quality_log_table="monitor_quality_log",
        feedback_table="monitor_incident_feedback",
        station="KAG",
    )

    sql, parameters = build_recent_incidents_query(config, since_time)

    assert "WITH feedback AS" in sql
    assert "FROM `generation`.`geothermal`.`monitor_incident_feedback`" in sql
    assert "FROM `generation`.`geothermal`.`monitor_incident` AS incident" in sql
    assert "LEFT JOIN `generation`.`geothermal`.`monitor_quality_log` AS quality_log" in sql
    assert "LEFT JOIN feedback" in sql
    assert "feedback.feedback_count" in sql
    assert "feedback.latest_feedback_ts" in sql
    assert "incident.station = ?" in sql
    assert "(incident.update_ts >= ? OR feedback.feedback_count IS NULL)" in sql
    assert "quality_log.window_start <= incident.incident_end" in sql
    assert "quality_log.window_end >= incident.incident_start" in sql
    assert "ORDER BY incident.update_ts DESC" in sql
    assert parameters == ["KAG", since_time]


def test_get_incident_plot_window_adds_context_before_and_after_incident() -> None:
    incident_start = datetime(2026, 5, 8, 10, 30, tzinfo=UTC)
    incident_end = datetime(2026, 5, 8, 11, 45, tzinfo=UTC)

    start_time, end_time = get_incident_plot_window(incident_start, incident_end)

    assert start_time == incident_start - timedelta(hours=1)
    assert end_time == incident_end + timedelta(hours=1)


def test_build_incident_tag_history_query_allows_monitor_tag_columns() -> None:
    raw_config = QueryConfig(
        stream_catalog_raw="raw",
        source_schema="pi",
        source_table="geothermal_kag_streaming",
    )
    start_time = datetime(2026, 5, 8, 9, 30, tzinfo=UTC)
    end_time = datetime(2026, 5, 8, 12, 45, tzinfo=UTC)

    sql, parameters = build_incident_tag_history_query(
        raw_config,
        tag_name="HP_BRINE_FLOW",
        start_time=start_time,
        end_time=end_time,
    )

    assert "`Pi_Timestamp`" in sql
    assert "`HP_BRINE_FLOW`" in sql
    assert "FROM `raw`.`pi`.`geothermal_kag_streaming`" in sql
    assert parameters == [start_time, end_time]


def test_build_feedback_table_ddl_creates_expected_delta_table() -> None:
    config = DataQualityConfig(
        monitor_catalog="generation",
        monitor_schema="geothermal",
        incident_table="monitor_incident",
        quality_log_table="monitor_quality_log",
        feedback_table="monitor_incident_feedback",
        station="KAG",
    )

    sql = build_feedback_table_ddl(config)

    assert "CREATE TABLE IF NOT EXISTS `generation`.`geothermal`.`monitor_incident_feedback`" in sql
    assert "incident_id STRING" in sql
    assert "comment STRING" in sql
    assert "created_by STRING" in sql
    assert "create_ts TIMESTAMP" in sql
    assert "USING DELTA" in sql


def test_build_feedback_insert_query_uses_parameters_and_current_user() -> None:
    config = DataQualityConfig(
        monitor_catalog="generation",
        monitor_schema="geothermal",
        incident_table="monitor_incident",
        quality_log_table="monitor_quality_log",
        feedback_table="monitor_incident_feedback",
        station="KAG",
    )

    sql, parameters = build_feedback_insert_query(
        config,
        incident_id="incident-123",
        comment="Sensor was isolated during maintenance.",
    )

    assert "INSERT INTO `generation`.`geothermal`.`monitor_incident_feedback`" in sql
    assert "current_user()" in sql
    assert "current_timestamp()" in sql
    assert parameters == ["incident-123", "Sensor was isolated during maintenance."]


def test_build_feedback_insert_query_rejects_empty_comment() -> None:
    config = DataQualityConfig(
        monitor_catalog="generation",
        monitor_schema="geothermal",
        incident_table="monitor_incident",
        quality_log_table="monitor_quality_log",
        feedback_table="monitor_incident_feedback",
        station="KAG",
    )

    try:
        build_feedback_insert_query(config, incident_id="incident-123", comment="  ")
    except ValueError as exc:
        assert "Comment cannot be empty" in str(exc)
    else:
        raise AssertionError("Expected empty feedback comment to fail")
