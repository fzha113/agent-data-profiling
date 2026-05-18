from datetime import datetime

from config.settings import DEFAULT_SETTINGS, HistoricalDataSettings
from data_quality_monitoring.rules import run_freshness_check
from data_quality_monitoring.schemas import ensure_monitor_quality_log_table
from data_quality_monitoring.utils import get_rule_config, write_monitor_results


def run_freshness_monitoring(
    spark,
    settings: HistoricalDataSettings = DEFAULT_SETTINGS,
    run_dt: datetime | None = None,
) -> None:
    """
    Run source freshness monitoring.

    This entrypoint is kept for live or replayed data sources. The default static
    historical job definition does not schedule it because a fixed 2023 table is
    expected to be stale relative to the current clock.

    Args:
        spark: Active Spark session.
        settings: Historical data table settings.
        run_dt: Optional run timestamp. Uses current wall-clock time when omitted.

    Returns:
        None: Results are appended to the monitor quality log table.

    Raises:
        RuntimeError: If the freshness check fails.
    """
    ensure_monitor_quality_log_table(spark, settings.monitor_quality_log_table)
    effective_run_dt = run_dt or datetime.now()
    rule_config = get_rule_config(settings.station, "freshness_lag")
    results = run_freshness_check(
        spark,
        effective_run_dt,
        settings.station,
        settings.dq_source_table,
        rule_config,
    )
    write_monitor_results(spark, results, settings.monitor_quality_log_table)

    failed_stations = [row["station"] for row in results if row["status"] == "failed"]
    if failed_stations:
        raise RuntimeError(f"Freshness check failed for station(s): {', '.join(failed_stations)}")


if __name__ == "__main__":
    run_freshness_monitoring(spark)
