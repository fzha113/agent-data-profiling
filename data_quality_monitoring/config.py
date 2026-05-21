RULE_CONFIG = {
    "geothermal station": {
        "freshness_lag": {
            "max_lag_minutes": 30,
            "timestamp_col": "Pi_Timestamp",
        },
        "stuck_value": {
            "lookback_minutes": 180,
            "min_expected_rows": 180,
            "max_range": 0.0,
            "timestamp_col": "Pi_Timestamp",
            "zero_filtered_tags": [
                "Vacuum_Pump_40_Current",
                "Vacuum_Pump_60_Current",
                "2nd_Stage_Brip_B_Current",
            ],
        },
        "outlier": {
            "lookback_minutes": 30,
            "history_days": 90,
            "outlier_multiplier": 1.5,
            "timestamp_col": "Pi_Timestamp",
        },
    }
}
