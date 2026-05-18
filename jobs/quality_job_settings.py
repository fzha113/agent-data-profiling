from datetime import datetime

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
