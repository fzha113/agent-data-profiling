from datetime import datetime, timedelta

from config.settings import DEFAULT_SETTINGS, HistoricalDataSettings


def get_historical_run_datetime(
    settings: HistoricalDataSettings = DEFAULT_SETTINGS,
) -> datetime:
    """
    Get the logical monitoring timestamp for the fixed historical dataset.

    Args:
        settings: Historical data table settings.

    Returns:
        datetime: Parsed history end timestamp.
    """
    return datetime.fromisoformat(settings.history_end_ts)


def get_historical_hourly_run_datetimes(
    settings: HistoricalDataSettings = DEFAULT_SETTINGS,
) -> list[datetime]:
    """
    Get one logical monitoring timestamp per one-hour historical window.

    Args:
        settings: Historical data table settings.

    Returns:
        list[datetime]: Hour-ending timestamps covering the half-open history range.

    Raises:
        ValueError: If either history bound is not aligned to a whole hour.
    """
    history_start = datetime.fromisoformat(settings.history_start_ts)
    history_end = datetime.fromisoformat(settings.history_end_ts)
    if (
        history_start.minute
        or history_start.second
        or history_start.microsecond
        or history_end.minute
        or history_end.second
        or history_end.microsecond
    ):
        raise ValueError("history_start_ts and history_end_ts must align to whole hours")

    run_datetimes = []
    current_run_dt = history_start
    while current_run_dt < history_end:
        current_run_dt = current_run_dt + timedelta(hours=1)
        run_datetimes.append(current_run_dt)
    return run_datetimes


def get_hourly_rule_config(rule_type: str, rule_config: dict) -> dict:
    """
    Return a rule config copy that evaluates a one-hour monitoring window.

    Args:
        rule_type: Monitoring rule identifier.
        rule_config: Base rule configuration.

    Returns:
        dict: Rule configuration adjusted for hourly backfill monitoring.
    """
    hourly_config = dict(rule_config)
    if rule_type in {"outlier", "stuck_value"}:
        hourly_config["lookback_minutes"] = 60
    if rule_type == "stuck_value":
        hourly_config["min_expected_rows"] = 60
    return hourly_config
