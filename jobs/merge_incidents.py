from config.settings import DEFAULT_SETTINGS, HistoricalDataSettings
from data_quality_monitoring.incidents import merge_failed_incidents
from data_quality_monitoring.schemas import ensure_monitor_incident_table


def run_incident_merge(spark, settings: HistoricalDataSettings = DEFAULT_SETTINGS) -> None:
    """
    Merge failed quality log rows into incident ranges.

    Args:
        spark: Active Spark session.
        settings: Historical data table settings.

    Returns:
        None: Incident table is updated as a side effect.
    """
    ensure_monitor_incident_table(spark, settings.monitor_incident_table)
    merge_failed_incidents(
        spark,
        settings.monitor_quality_log_table,
        settings.monitor_incident_table,
    )


if __name__ == "__main__":
    run_incident_merge(spark)
