from config.settings import DEFAULT_SETTINGS, HistoricalDataSettings
from data_quality_monitoring.incidents import merge_failed_incidents
from data_quality_monitoring.rules import run_outlier_check, run_stuck_value_check
from data_quality_monitoring.schemas import (
    ensure_monitor_incident_table,
    ensure_monitor_quality_log_table,
)
from data_quality_monitoring.tag_sets import get_rule_tags
from data_quality_monitoring.utils import (
    get_existing_rule_tags,
    get_rule_config,
    write_monitor_results,
)
from jobs.quality_job_settings import get_historical_hourly_run_datetimes, get_hourly_rule_config


HOURLY_RULE_TYPES = ("outlier", "stuck_value")


def run_sample_quality_monitoring(
    spark,
    settings: HistoricalDataSettings = DEFAULT_SETTINGS,
    flush_window_count: int = 24,
) -> None:
    """
    Run one-hour quality monitoring windows across the configured sample history.

    Args:
        spark: Active Spark session.
        settings: Historical data table settings.
        flush_window_count: Number of hourly windows to buffer before appending logs.

    Returns:
        None: Results are written to monitor log and incident tables.

    Raises:
        ValueError: If flush_window_count is less than one.
    """
    if flush_window_count < 1:
        raise ValueError("flush_window_count must be at least 1")

    ensure_monitor_quality_log_table(spark, settings.monitor_quality_log_table)
    ensure_monitor_incident_table(spark, settings.monitor_incident_table)

    rule_contexts = []
    for rule_type in HOURLY_RULE_TYPES:
        configured_tags = get_rule_tags(settings.station, rule_type)
        existing_tags = get_existing_rule_tags(spark, settings.dq_source_table, configured_tags)
        if not existing_tags:
            print(f"no existing tags found for rule type: {rule_type}")
            continue
        rule_contexts.append(
            (
                rule_type,
                existing_tags,
                get_hourly_rule_config(rule_type, get_rule_config(settings.station, rule_type)),
            )
        )

    buffered_results = []
    for window_index, run_dt in enumerate(get_historical_hourly_run_datetimes(settings), start=1):
        for rule_type, tags, rule_config in rule_contexts:
            if rule_type == "outlier":
                buffered_results.extend(
                    run_outlier_check(
                        spark,
                        run_dt,
                        settings.station,
                        settings.dq_source_table,
                        tags,
                        rule_config,
                    )
                )
            elif rule_type == "stuck_value":
                buffered_results.extend(
                    run_stuck_value_check(
                        spark,
                        run_dt,
                        settings.station,
                        settings.dq_source_table,
                        tags,
                        rule_config,
                    )
                )

        if window_index % flush_window_count == 0:
            write_monitor_results(spark, buffered_results, settings.monitor_quality_log_table)
            buffered_results = []

    write_monitor_results(spark, buffered_results, settings.monitor_quality_log_table)
    merge_failed_incidents(
        spark,
        settings.monitor_quality_log_table,
        settings.monitor_incident_table,
    )


if __name__ == "__main__":
    run_sample_quality_monitoring(spark)
