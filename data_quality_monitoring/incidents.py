from pyspark.sql import functions as F
from pyspark.sql.window import Window


def merge_failed_incidents(
    spark,
    monitor_quality_log_table: str,
    monitor_incident_table: str,
    merge_gap_seconds: int = 60,
) -> None:
    """
    Merge newly failed quality log rows into incident ranges.

    Args:
        spark: Active Spark session.
        monitor_quality_log_table: Full quality log table name.
        monitor_incident_table: Full incident table name.
        merge_gap_seconds: Maximum allowed gap between failed windows.

    Returns:
        None: This function updates the incident table as a side effect.
    """
    df_failed_source = spark.sql(
        f"""
        WITH watermark AS (
            SELECT COALESCE(MAX(update_ts), timestamp('1900-01-01')) AS max_update_ts
            FROM {monitor_incident_table}
        )
        SELECT
            run_id,
            station,
            source_table,
            tag_name,
            rule_type,
            status,
            window_start,
            window_end,
            create_ts
        FROM {monitor_quality_log_table}
        WHERE status = 'failed'
          AND create_ts > (SELECT max_update_ts FROM watermark)
        """
    )

    if not df_failed_source.head(1):
        print("no failed quality log updates to merge")
        return

    partition_cols = ["station", "source_table", "tag_name", "rule_type", "status"]
    gap_expr = F.expr(f"INTERVAL {merge_gap_seconds} SECONDS")
    window_spec = Window.partitionBy(*partition_cols).orderBy("window_start", "window_end")

    df_failed_grouped = (
        df_failed_source.withColumn("prev_window_end", F.lag("window_end").over(window_spec))
        .withColumn(
            "new_group_flag",
            F.when(F.col("prev_window_end").isNull(), F.lit(1))
            .when(F.col("prev_window_end") >= F.col("window_start") - gap_expr, F.lit(0))
            .otherwise(F.lit(1)),
        )
        .withColumn(
            "incident_group",
            F.sum("new_group_flag").over(
                window_spec.rowsBetween(Window.unboundedPreceding, Window.currentRow)
            ),
        )
        .groupBy(*partition_cols, "incident_group")
        .agg(
            F.min("window_start").alias("incident_start"),
            F.max("window_end").alias("incident_end"),
            F.min("run_id").alias("first_run_id"),
            F.max("run_id").alias("last_run_id"),
            F.min("create_ts").alias("create_ts"),
            F.max("create_ts").alias("update_ts"),
        )
        .withColumn("incident_id", F.expr("uuid()"))
        .select(
            "incident_id",
            "station",
            "source_table",
            "tag_name",
            "rule_type",
            "status",
            "incident_start",
            "incident_end",
            "first_run_id",
            "last_run_id",
            "create_ts",
            "update_ts",
        )
    )

    df_failed_grouped.createOrReplaceTempView("current_failed_grouped")

    spark.sql(f"""
        MERGE INTO {monitor_incident_table} AS incident
        USING current_failed_grouped AS grouped
        ON  incident.station = grouped.station
        AND incident.source_table = grouped.source_table
        AND incident.tag_name = grouped.tag_name
        AND incident.rule_type = grouped.rule_type
        AND incident.status = grouped.status
        AND incident.incident_end >= grouped.incident_start - INTERVAL {merge_gap_seconds} SECONDS
        AND incident.incident_start <= grouped.incident_end + INTERVAL {merge_gap_seconds} SECONDS

        WHEN MATCHED THEN UPDATE SET
            incident.incident_start = LEAST(incident.incident_start, grouped.incident_start),
            incident.incident_end = GREATEST(incident.incident_end, grouped.incident_end),
            incident.first_run_id = CASE
                WHEN incident.incident_start <= grouped.incident_start THEN incident.first_run_id
                ELSE grouped.first_run_id
            END,
            incident.last_run_id = CASE
                WHEN incident.incident_end >= grouped.incident_end THEN incident.last_run_id
                ELSE grouped.last_run_id
            END,
            incident.update_ts = GREATEST(incident.update_ts, grouped.update_ts)

        WHEN NOT MATCHED THEN INSERT (
            incident_id,
            station,
            source_table,
            tag_name,
            rule_type,
            status,
            incident_start,
            incident_end,
            first_run_id,
            last_run_id,
            create_ts,
            update_ts
        )
        VALUES (
            grouped.incident_id,
            grouped.station,
            grouped.source_table,
            grouped.tag_name,
            grouped.rule_type,
            grouped.status,
            grouped.incident_start,
            grouped.incident_end,
            grouped.first_run_id,
            grouped.last_run_id,
            grouped.create_ts,
            grouped.update_ts
        )
    """)
