from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalDataSettings:
    """
    Static table settings for the standalone historical KAG dataset.

    Args:
        source_table: Fully qualified real KAG source table.
        base_table: Fully qualified 2023 history table without noise.
        noisy_table: Fully qualified 2023 history table with numeric noise.
        monitor_quality_log_table: Fully qualified quality log output table.
        monitor_incident_table: Fully qualified merged incident output table.
        monitor_incident_feedback_table: Fully qualified app feedback table.
        history_start_ts: Inclusive source timestamp lower bound.
        history_end_ts: Exclusive source timestamp upper bound.
        timestamp_col: Source timestamp column.
        station: Station identifier.
        noise_rate: Maximum one-sided noise rate applied to numeric columns.
        noise_seed: Seed used for deterministic Databricks rand expressions.
    """

    source_table: str = "workspace.default.geothermal_kag_streaming"
    base_table: str = "workspace.default.kag_streaming_history_base"
    noisy_table: str = "workspace.default.kag_streaming_history_noisy"
    monitor_quality_log_table: str = "workspace.default.monitor_quality_log"
    monitor_incident_table: str = "workspace.default.monitor_incident"
    monitor_incident_feedback_table: str = "workspace.default.monitor_incident_feedback"
    history_start_ts: str = "2023-01-01 00:00:00"
    history_end_ts: str = "2024-01-01 00:00:00"
    timestamp_col: str = "Pi_Timestamp"
    station: str = "KAG"
    noise_rate: float = 0.02
    noise_seed: int = 42

    @property
    def dq_source_table(self) -> str:
        """
        Get the table used by data quality monitoring.

        Args:
            None.

        Returns:
            str: Fully qualified base table name.
        """
        return self.base_table

    @property
    def app_profile_source_table(self) -> str:
        """
        Get the table used by app profiling and comparison queries.

        Args:
            None.

        Returns:
            str: Fully qualified noisy table name.
        """
        return self.noisy_table


DEFAULT_SETTINGS = HistoricalDataSettings()
