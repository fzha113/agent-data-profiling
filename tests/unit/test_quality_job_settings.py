from datetime import datetime

from config.settings import HistoricalDataSettings
from jobs.quality_job_settings import get_historical_run_datetime


def test_get_historical_run_datetime_uses_history_end_timestamp() -> None:
    settings = HistoricalDataSettings(history_end_ts="2024-01-01 00:00:00")

    assert get_historical_run_datetime(settings) == datetime(2024, 1, 1, 0, 0, 0)
