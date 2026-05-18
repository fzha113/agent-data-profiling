from pyspark.sql.types import StringType, StructField, StructType, TimestampType


def get_monitor_log_schema() -> StructType:
    """
    Get the schema for the quality monitoring log table.

    Args:
        None.

    Returns:
        StructType: Schema for quality monitoring log rows.
    """
    return StructType(
        [
            StructField("run_id", StringType(), True),
            StructField("station", StringType(), True),
            StructField("source_table", StringType(), True),
            StructField("tag_name", StringType(), True),
            StructField("rule_type", StringType(), True),
            StructField("window_start", TimestampType(), True),
            StructField("window_end", TimestampType(), True),
            StructField("status", StringType(), True),
            StructField("observed_value", StringType(), True),
            StructField("create_ts", TimestampType(), True),
        ]
    )


def get_monitor_incident_schema() -> StructType:
    """
    Get the schema for the incident monitoring table.

    Args:
        None.

    Returns:
        StructType: Schema for incident rows.
    """
    return StructType(
        [
            StructField("incident_id", StringType(), True),
            StructField("station", StringType(), True),
            StructField("source_table", StringType(), True),
            StructField("tag_name", StringType(), True),
            StructField("rule_type", StringType(), True),
            StructField("status", StringType(), True),
            StructField("incident_start", TimestampType(), True),
            StructField("incident_end", TimestampType(), True),
            StructField("first_run_id", StringType(), True),
            StructField("last_run_id", StringType(), True),
            StructField("create_ts", TimestampType(), True),
            StructField("update_ts", TimestampType(), True),
        ]
    )


def ensure_monitor_quality_log_table(spark, table_name: str) -> None:
    """
    Create the quality monitoring log table if it does not exist.

    Args:
        spark: Active Spark session.
        table_name: Fully qualified monitor log table name.

    Returns:
        None: This function creates the table as a side effect.
    """
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            run_id STRING,
            station STRING,
            source_table STRING,
            tag_name STRING,
            rule_type STRING,
            window_start TIMESTAMP,
            window_end TIMESTAMP,
            status STRING,
            observed_value STRING,
            create_ts TIMESTAMP
        ) USING DELTA
        """
    )


def ensure_monitor_incident_table(spark, table_name: str) -> None:
    """
    Create the incident monitoring table if it does not exist.

    Args:
        spark: Active Spark session.
        table_name: Fully qualified incident table name.

    Returns:
        None: This function creates the table as a side effect.
    """
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            incident_id STRING,
            station STRING,
            source_table STRING,
            tag_name STRING,
            rule_type STRING,
            status STRING,
            incident_start TIMESTAMP,
            incident_end TIMESTAMP,
            first_run_id STRING,
            last_run_id STRING,
            create_ts TIMESTAMP,
            update_ts TIMESTAMP
        ) USING DELTA
        """
    )
