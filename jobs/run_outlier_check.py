from config.settings import DEFAULT_SETTINGS, HistoricalDataSettings
from data_quality_monitoring.rules import run_outlier_check
from data_quality_monitoring.schemas import ensure_monitor_quality_log_table
from data_quality_monitoring.tag_sets import get_rule_tags
from data_quality_monitoring.utils import get_rule_config, write_monitor_results
from jobs.quality_job_settings import get_historical_run_datetime


def run_outlier_monitoring(spark, settings: HistoricalDataSettings = DEFAULT_SETTINGS) -> None:
    """
    Run outlier monitoring against the unmodified historical base table.

    Args:
        spark: Active Spark session.
        settings: Historical data table settings.

    Returns:
        None: Results are appended to the monitor quality log table.
    """
    ensure_monitor_quality_log_table(spark, settings.monitor_quality_log_table)
    run_dt = get_historical_run_datetime(settings)
    rule_config = get_rule_config(settings.station, "outlier")
    tags = get_rule_tags(settings.station, "outlier")
    results = run_outlier_check(
        spark,
        run_dt,
        settings.station,
        settings.dq_source_table,
        tags,
        rule_config,
    )
    write_monitor_results(spark, results, settings.monitor_quality_log_table)


if __name__ == "__main__":
    run_outlier_monitoring(spark)
