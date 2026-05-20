-- DBA agent Unity Catalog SQL assets for the data incident multi-agent demo.
-- Run this script in the Databricks SQL Editor against the target workspace.
--
-- The custom DBA agent consumes these functions through the managed MCP server:
--   /api/2.0/mcp/functions/workspace/default
--
-- All functions are read-only and return JSON strings. The agent instruction should
-- treat these results as evidence only, not as hypotheses or final summaries.

USE CATALOG workspace;
USE SCHEMA default;

-- If an older view exists, remove it. The DBA functions should read the physical
-- Delta table below so MCP tool calls do not restack sample_noisy on every request.
DROP VIEW IF EXISTS workspace.default.sample_incident_tag_values;

CREATE OR REPLACE TABLE workspace.default.sample_incident_tag_values
USING DELTA
AS
SELECT
    Pi_Timestamp,
    tag_name,
    CAST(tag_value AS DOUBLE) AS tag_value
FROM workspace.default.sample_noisy
LATERAL VIEW stack(15,
    'Condenser_Pressure_A', CAST(`Condenser_Pressure_A` AS DOUBLE),
    'Condenser_Pressure_B', CAST(`Condenser_Pressure_B` AS DOUBLE),
    'Condenser_Pressure_C', CAST(`Condenser_Pressure_C` AS DOUBLE),
    'Condenser_Pressure_D', CAST(`Condenser_Pressure_D` AS DOUBLE),
    'Cooling_Water_Flow', CAST(`Cooling_Water_Flow` AS DOUBLE),
    'Main_Cooling_Water_Temperature', CAST(`Main_Cooling_Water_Temperature` AS DOUBLE),
    'Cooling_Tower_Inlet_Condensate_Temperature',
        CAST(`Cooling_Tower_Inlet_Condensate_Temperature` AS DOUBLE),
    'Vacuum_Pump_40_Current', CAST(`Vacuum_Pump_40_Current` AS DOUBLE),
    'Vacuum_Pump_60_Current', CAST(`Vacuum_Pump_60_Current` AS DOUBLE),
    'Vacuum_Pump_80_Current', CAST(`Vacuum_Pump_80_Current` AS DOUBLE),
    'Gross_Generator_Output', CAST(`Gross_Generator_Output` AS DOUBLE),
    'Net_Power', CAST(`Net_Power` AS DOUBLE),
    'Total_Turbine_Steam_Flow', CAST(`Total_Turbine_Steam_Flow` AS DOUBLE),
    'Atmospheric_Temperature_Dry', CAST(`Atmospheric_Temperature_Dry` AS DOUBLE),
    'Humidity', CAST(`Humidity` AS DOUBLE)
) tag_stack AS tag_name, tag_value
WHERE Pi_Timestamp IS NOT NULL
  AND tag_value IS NOT NULL;

OPTIMIZE workspace.default.sample_incident_tag_values
ZORDER BY (tag_name, Pi_Timestamp);

CREATE OR REPLACE FUNCTION workspace.default.get_app_tag_catalog()
RETURNS STRING
LANGUAGE SQL
READS SQL DATA
COMMENT 'Return the physical long-form tag catalog used by DBA evidence checks.'
RETURN
SELECT to_json(named_struct(
    'status', 'executed',
    'source_table', 'workspace.default.sample_incident_tag_values',
    'timestamp_col', 'Pi_Timestamp',
    'tag_count', COUNT(DISTINCT tag_name),
    'tags', array_sort(collect_set(tag_name)),
    'min_ts_utc', date_format(MIN(Pi_Timestamp), 'yyyy-MM-dd HH:mm:ss'),
    'max_ts_utc', date_format(MAX(Pi_Timestamp), 'yyyy-MM-dd HH:mm:ss')
))
FROM workspace.default.sample_incident_tag_values;

CREATE OR REPLACE FUNCTION workspace.default.get_incident_packet(incident_id STRING)
RETURNS STRING
LANGUAGE SQL
READS SQL DATA
COMMENT 'Return one incident with matched quality log and feedback rows as JSON evidence.'
RETURN
WITH target_incident AS (
    SELECT *
    FROM workspace.default.sample_monitor_incident
    WHERE incident_id = get_incident_packet.incident_id
    LIMIT 1
),
matched_logs AS (
    SELECT
        quality_log.run_id,
        quality_log.station,
        quality_log.source_table,
        quality_log.tag_name,
        quality_log.rule_type,
        quality_log.window_start,
        quality_log.window_end,
        quality_log.status,
        quality_log.observed_value,
        quality_log.create_ts
    FROM workspace.default.sample_monitor_log AS quality_log
    INNER JOIN target_incident AS incident
        ON quality_log.station = incident.station
       AND quality_log.source_table = incident.source_table
       AND quality_log.tag_name = incident.tag_name
       AND quality_log.rule_type = incident.rule_type
       AND quality_log.status = incident.status
       AND quality_log.window_start <= incident.incident_end
       AND quality_log.window_end >= incident.incident_start
),
incident_json AS (
    SELECT named_struct(
        'incident_id', incident_id,
        'station', station,
        'source_table', source_table,
        'tag_name', tag_name,
        'rule_type', rule_type,
        'status', status,
        'incident_start_utc', date_format(incident_start, 'yyyy-MM-dd HH:mm:ss'),
        'incident_end_utc', date_format(incident_end, 'yyyy-MM-dd HH:mm:ss'),
        'first_run_id', first_run_id,
        'last_run_id', last_run_id,
        'create_ts_utc', date_format(create_ts, 'yyyy-MM-dd HH:mm:ss'),
        'update_ts_utc', date_format(update_ts, 'yyyy-MM-dd HH:mm:ss')
    ) AS incident
    FROM target_incident
),
log_json AS (
    SELECT array_sort(collect_list(named_struct(
        'run_id', run_id,
        'station', station,
        'source_table', source_table,
        'tag_name', tag_name,
        'rule_type', rule_type,
        'window_start_utc', date_format(window_start, 'yyyy-MM-dd HH:mm:ss'),
        'window_end_utc', date_format(window_end, 'yyyy-MM-dd HH:mm:ss'),
        'status', status,
        'observed_value', observed_value,
        'create_ts_utc', date_format(create_ts, 'yyyy-MM-dd HH:mm:ss')
    ))) AS quality_log_rows
    FROM matched_logs
),
feedback_json AS (
    SELECT array_sort(collect_list(named_struct(
        'comment', comment,
        'created_by', created_by,
        'create_ts_utc', date_format(create_ts, 'yyyy-MM-dd HH:mm:ss')
    ))) AS feedback_rows
    FROM workspace.default.monitor_incident_feedback
    WHERE incident_id = get_incident_packet.incident_id
)
SELECT to_json(named_struct(
    'status', CASE
        WHEN (SELECT COUNT(*) FROM target_incident) = 0 THEN 'not_found'
        ELSE 'executed'
    END,
    'incident_id', get_incident_packet.incident_id,
    'source_tables', array(
        'workspace.default.sample_monitor_incident',
        'workspace.default.sample_monitor_log',
        'workspace.default.monitor_incident_feedback'
    ),
    'incident', (SELECT incident FROM incident_json),
    'quality_log_rows', log_json.quality_log_rows,
    'feedback_rows', feedback_json.feedback_rows
))
FROM log_json
CROSS JOIN feedback_json;

CREATE OR REPLACE FUNCTION workspace.default.get_raw_points_sample(
    tag_names ARRAY<STRING>,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP
)
RETURNS STRING
LANGUAGE SQL
READS SQL DATA
COMMENT 'Return capped raw long-form points for requested tags and UTC window.'
RETURN
WITH filtered AS (
    SELECT
        tag_name,
        Pi_Timestamp,
        tag_value
    FROM workspace.default.sample_incident_tag_values
    WHERE array_contains(get_raw_points_sample.tag_names, tag_name)
      AND Pi_Timestamp >= get_raw_points_sample.start_ts
      AND Pi_Timestamp < get_raw_points_sample.end_ts
),
ranked AS (
    SELECT
        tag_name,
        Pi_Timestamp,
        tag_value,
        ROW_NUMBER() OVER (PARTITION BY tag_name ORDER BY Pi_Timestamp) AS point_rank
    FROM filtered
),
samples AS (
    SELECT
        tag_name,
        Pi_Timestamp,
        tag_value
    FROM ranked
    WHERE point_rank <= 200
),
counts AS (
    SELECT
        tag_name,
        COUNT(*) AS total_points
    FROM filtered
    GROUP BY tag_name
),
count_json AS (
    SELECT array_sort(collect_list(named_struct(
        'tag_name', tag_name,
        'total_points', total_points
    ))) AS total_points_by_tag
    FROM counts
),
sample_json AS (
    SELECT
        COUNT(*) AS returned_points,
        array_sort(collect_list(named_struct(
            'tag_name', tag_name,
            'ts_utc', date_format(Pi_Timestamp, 'yyyy-MM-dd HH:mm:ss'),
            'value', tag_value
        ))) AS points
    FROM samples
)
SELECT to_json(named_struct(
    'status', 'executed',
    'check_type', 'raw_points_sample',
    'source_table', 'workspace.default.sample_incident_tag_values',
    'input', named_struct(
        'tag_names', get_raw_points_sample.tag_names,
        'start_ts_utc', date_format(get_raw_points_sample.start_ts, 'yyyy-MM-dd HH:mm:ss'),
        'end_ts_utc', date_format(get_raw_points_sample.end_ts, 'yyyy-MM-dd HH:mm:ss')
    ),
    'max_points_per_tag', 200,
    'total_points_by_tag', count_json.total_points_by_tag,
    'returned_points', sample_json.returned_points,
    'points', sample_json.points
))
FROM count_json
CROSS JOIN sample_json;

CREATE OR REPLACE FUNCTION workspace.default.get_related_tag_window_stats(
    tag_names ARRAY<STRING>,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP
)
RETURNS STRING
LANGUAGE SQL
READS SQL DATA
COMMENT 'Return per-tag descriptive stats for a requested UTC window.'
RETURN
WITH filtered AS (
    SELECT
        tag_name,
        Pi_Timestamp,
        tag_value
    FROM workspace.default.sample_incident_tag_values
    WHERE array_contains(get_related_tag_window_stats.tag_names, tag_name)
      AND Pi_Timestamp >= get_related_tag_window_stats.start_ts
      AND Pi_Timestamp < get_related_tag_window_stats.end_ts
),
stats AS (
    SELECT
        tag_name,
        COUNT(*) AS point_count,
        MIN(Pi_Timestamp) AS first_ts,
        MAX(Pi_Timestamp) AS last_ts,
        MIN(tag_value) AS min_value,
        PERCENTILE_APPROX(tag_value, 0.25) AS p25_value,
        AVG(tag_value) AS avg_value,
        PERCENTILE_APPROX(tag_value, 0.50) AS median_value,
        PERCENTILE_APPROX(tag_value, 0.75) AS p75_value,
        MAX(tag_value) AS max_value,
        STDDEV_SAMP(tag_value) AS stddev_value
    FROM filtered
    GROUP BY tag_name
)
SELECT to_json(named_struct(
    'status', 'executed',
    'check_type', 'related_tag_window_stats',
    'source_table', 'workspace.default.sample_incident_tag_values',
    'input', named_struct(
        'tag_names', get_related_tag_window_stats.tag_names,
        'start_ts_utc', date_format(get_related_tag_window_stats.start_ts, 'yyyy-MM-dd HH:mm:ss'),
        'end_ts_utc', date_format(get_related_tag_window_stats.end_ts, 'yyyy-MM-dd HH:mm:ss')
    ),
    'stats', array_sort(collect_list(named_struct(
        'tag_name', tag_name,
        'point_count', point_count,
        'first_ts_utc', date_format(first_ts, 'yyyy-MM-dd HH:mm:ss'),
        'last_ts_utc', date_format(last_ts, 'yyyy-MM-dd HH:mm:ss'),
        'min_value', min_value,
        'p25_value', p25_value,
        'avg_value', avg_value,
        'median_value', median_value,
        'p75_value', p75_value,
        'max_value', max_value,
        'stddev_value', stddev_value
    )))
))
FROM stats;

CREATE OR REPLACE FUNCTION workspace.default.get_before_during_after_stats(
    tag_names ARRAY<STRING>,
    before_start_ts TIMESTAMP,
    incident_start_ts TIMESTAMP,
    incident_end_ts TIMESTAMP,
    after_end_ts TIMESTAMP
)
RETURNS STRING
LANGUAGE SQL
READS SQL DATA
COMMENT 'Return before, during, and after stats for requested tags around an incident.'
RETURN
WITH filtered AS (
    SELECT
        tag_name,
        Pi_Timestamp,
        tag_value,
        CASE
            WHEN Pi_Timestamp >= get_before_during_after_stats.before_start_ts
             AND Pi_Timestamp < get_before_during_after_stats.incident_start_ts THEN 'before'
            WHEN Pi_Timestamp >= get_before_during_after_stats.incident_start_ts
             AND Pi_Timestamp < get_before_during_after_stats.incident_end_ts THEN 'during'
            WHEN Pi_Timestamp >= get_before_during_after_stats.incident_end_ts
             AND Pi_Timestamp < get_before_during_after_stats.after_end_ts THEN 'after'
            ELSE NULL
        END AS window_phase
    FROM workspace.default.sample_incident_tag_values
    WHERE array_contains(get_before_during_after_stats.tag_names, tag_name)
      AND Pi_Timestamp >= get_before_during_after_stats.before_start_ts
      AND Pi_Timestamp < get_before_during_after_stats.after_end_ts
),
stats AS (
    SELECT
        tag_name,
        window_phase,
        COUNT(*) AS point_count,
        MIN(Pi_Timestamp) AS first_ts,
        MAX(Pi_Timestamp) AS last_ts,
        MIN(tag_value) AS min_value,
        AVG(tag_value) AS avg_value,
        MAX(tag_value) AS max_value,
        STDDEV_SAMP(tag_value) AS stddev_value
    FROM filtered
    WHERE window_phase IS NOT NULL
    GROUP BY tag_name, window_phase
)
SELECT to_json(named_struct(
    'status', 'executed',
    'check_type', 'before_during_after_stats',
    'source_table', 'workspace.default.sample_incident_tag_values',
    'input', named_struct(
        'tag_names', get_before_during_after_stats.tag_names,
        'before_start_ts_utc',
            date_format(get_before_during_after_stats.before_start_ts, 'yyyy-MM-dd HH:mm:ss'),
        'incident_start_ts_utc',
            date_format(get_before_during_after_stats.incident_start_ts, 'yyyy-MM-dd HH:mm:ss'),
        'incident_end_ts_utc',
            date_format(get_before_during_after_stats.incident_end_ts, 'yyyy-MM-dd HH:mm:ss'),
        'after_end_ts_utc',
            date_format(get_before_during_after_stats.after_end_ts, 'yyyy-MM-dd HH:mm:ss')
    ),
    'stats', array_sort(collect_list(named_struct(
        'tag_name', tag_name,
        'window_phase', window_phase,
        'point_count', point_count,
        'first_ts_utc', date_format(first_ts, 'yyyy-MM-dd HH:mm:ss'),
        'last_ts_utc', date_format(last_ts, 'yyyy-MM-dd HH:mm:ss'),
        'min_value', min_value,
        'avg_value', avg_value,
        'max_value', max_value,
        'stddev_value', stddev_value
    )))
))
FROM stats;

CREATE OR REPLACE FUNCTION workspace.default.get_missingness_gap_profile(
    tag_names ARRAY<STRING>,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP
)
RETURNS STRING
LANGUAGE SQL
READS SQL DATA
COMMENT 'Return point counts and timestamp gap stats for requested tags and UTC window.'
RETURN
WITH target_tags AS (
    SELECT explode(get_missingness_gap_profile.tag_names) AS tag_name
),
filtered AS (
    SELECT
        tag_name,
        Pi_Timestamp,
        tag_value
    FROM workspace.default.sample_incident_tag_values
    WHERE array_contains(get_missingness_gap_profile.tag_names, tag_name)
      AND Pi_Timestamp >= get_missingness_gap_profile.start_ts
      AND Pi_Timestamp < get_missingness_gap_profile.end_ts
),
ordered AS (
    SELECT
        tag_name,
        Pi_Timestamp,
        tag_value,
        LAG(Pi_Timestamp) OVER (PARTITION BY tag_name ORDER BY Pi_Timestamp) AS prev_ts
    FROM filtered
),
gaps AS (
    SELECT
        tag_name,
        Pi_Timestamp,
        tag_value,
        CASE
            WHEN prev_ts IS NULL THEN NULL
            ELSE unix_timestamp(Pi_Timestamp) - unix_timestamp(prev_ts)
        END AS gap_seconds
    FROM ordered
),
stats AS (
    SELECT
        target_tags.tag_name,
        COUNT(gaps.tag_value) AS point_count,
        MIN(gaps.Pi_Timestamp) AS first_ts,
        MAX(gaps.Pi_Timestamp) AS last_ts,
        MAX(gaps.gap_seconds) AS max_gap_seconds,
        AVG(gaps.gap_seconds) AS avg_gap_seconds,
        SUM(CASE WHEN gaps.gap_seconds > 300 THEN 1 ELSE 0 END) AS gaps_over_5m,
        SUM(CASE WHEN gaps.gap_seconds > 900 THEN 1 ELSE 0 END) AS gaps_over_15m
    FROM target_tags
    LEFT JOIN gaps
        ON gaps.tag_name = target_tags.tag_name
    GROUP BY target_tags.tag_name
)
SELECT to_json(named_struct(
    'status', 'executed',
    'check_type', 'missingness_gap_profile',
    'source_table', 'workspace.default.sample_incident_tag_values',
    'input', named_struct(
        'tag_names', get_missingness_gap_profile.tag_names,
        'start_ts_utc', date_format(get_missingness_gap_profile.start_ts, 'yyyy-MM-dd HH:mm:ss'),
        'end_ts_utc', date_format(get_missingness_gap_profile.end_ts, 'yyyy-MM-dd HH:mm:ss')
    ),
    'stats', array_sort(collect_list(named_struct(
        'tag_name', tag_name,
        'point_count', point_count,
        'first_ts_utc', date_format(first_ts, 'yyyy-MM-dd HH:mm:ss'),
        'last_ts_utc', date_format(last_ts, 'yyyy-MM-dd HH:mm:ss'),
        'max_gap_seconds', max_gap_seconds,
        'avg_gap_seconds', avg_gap_seconds,
        'gaps_over_5m', gaps_over_5m,
        'gaps_over_15m', gaps_over_15m
    )))
))
FROM stats;

CREATE OR REPLACE FUNCTION workspace.default.get_outlier_threshold_context(
    tag_names ARRAY<STRING>,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP,
    lower_threshold DOUBLE,
    upper_threshold DOUBLE
)
RETURNS STRING
LANGUAGE SQL
READS SQL DATA
COMMENT 'Return counts and extrema relative to supplied lower and upper outlier thresholds.'
RETURN
WITH params AS (
    SELECT
        get_outlier_threshold_context.tag_names AS tag_names,
        get_outlier_threshold_context.start_ts AS start_ts,
        get_outlier_threshold_context.end_ts AS end_ts,
        get_outlier_threshold_context.lower_threshold AS lower_threshold_value,
        get_outlier_threshold_context.upper_threshold AS upper_threshold_value
),
filtered AS (
    SELECT
        tag_values.tag_name,
        tag_values.Pi_Timestamp,
        tag_values.tag_value,
        params.lower_threshold_value,
        params.upper_threshold_value
    FROM workspace.default.sample_incident_tag_values AS tag_values
    CROSS JOIN params
    WHERE array_contains(params.tag_names, tag_values.tag_name)
      AND tag_values.Pi_Timestamp >= params.start_ts
      AND tag_values.Pi_Timestamp < params.end_ts
),
stats AS (
    SELECT
        tag_name,
        COUNT(*) AS point_count,
        MIN(Pi_Timestamp) AS first_ts,
        MAX(Pi_Timestamp) AS last_ts,
        MIN(tag_value) AS min_value,
        AVG(tag_value) AS avg_value,
        MAX(tag_value) AS max_value,
        MIN(lower_threshold_value) AS lower_threshold_value,
        MAX(upper_threshold_value) AS upper_threshold_value,
        SUM(CASE WHEN tag_value < lower_threshold_value THEN 1 ELSE 0 END)
            AS below_lower_threshold_count,
        SUM(CASE WHEN tag_value > upper_threshold_value THEN 1 ELSE 0 END)
            AS above_upper_threshold_count
    FROM filtered
    GROUP BY tag_name
)
SELECT to_json(named_struct(
    'status', 'executed',
    'check_type', 'outlier_threshold_context',
    'source_table', 'workspace.default.sample_incident_tag_values',
    'input', named_struct(
        'tag_names', get_outlier_threshold_context.tag_names,
        'start_ts_utc', date_format(get_outlier_threshold_context.start_ts, 'yyyy-MM-dd HH:mm:ss'),
        'end_ts_utc', date_format(get_outlier_threshold_context.end_ts, 'yyyy-MM-dd HH:mm:ss'),
        'lower_threshold', get_outlier_threshold_context.lower_threshold,
        'upper_threshold', get_outlier_threshold_context.upper_threshold
    ),
    'stats', array_sort(collect_list(named_struct(
        'tag_name', tag_name,
        'point_count', point_count,
        'first_ts_utc', date_format(first_ts, 'yyyy-MM-dd HH:mm:ss'),
        'last_ts_utc', date_format(last_ts, 'yyyy-MM-dd HH:mm:ss'),
        'min_value', min_value,
        'avg_value', avg_value,
        'max_value', max_value,
        'lower_threshold', lower_threshold_value,
        'upper_threshold', upper_threshold_value,
        'below_lower_threshold_count', below_lower_threshold_count,
        'above_upper_threshold_count', above_upper_threshold_count
    )))
))
FROM stats;

-- Smoke tests to run manually after executing the script:
--
-- SELECT workspace.default.get_app_tag_catalog();
--
-- SELECT workspace.default.get_raw_points_sample(
--   array('Condenser_Pressure_A'),
--   TIMESTAMP('2024-07-10 09:45:00'),
--   TIMESTAMP('2024-07-10 10:30:00')
-- );
--
-- SELECT workspace.default.get_related_tag_window_stats(
--   array('Condenser_Pressure_A', 'Condenser_Pressure_B'),
--   TIMESTAMP('2024-07-10 09:45:00'),
--   TIMESTAMP('2024-07-10 10:30:00')
-- );
--
-- Required app service principal permissions:
-- GRANT SELECT ON TABLE workspace.default.sample_noisy TO `<app-service-principal>`;
-- GRANT SELECT ON TABLE workspace.default.sample_incident_tag_values TO `<app-service-principal>`;
-- GRANT SELECT ON TABLE workspace.default.sample_monitor_incident TO `<app-service-principal>`;
-- GRANT SELECT ON TABLE workspace.default.sample_monitor_log TO `<app-service-principal>`;
-- GRANT SELECT ON TABLE workspace.default.monitor_incident_feedback TO `<app-service-principal>`;
-- GRANT EXECUTE ON FUNCTION workspace.default.get_app_tag_catalog TO `<app-service-principal>`;
-- GRANT EXECUTE ON FUNCTION workspace.default.get_incident_packet TO `<app-service-principal>`;
-- GRANT EXECUTE ON FUNCTION workspace.default.get_raw_points_sample TO `<app-service-principal>`;
-- GRANT EXECUTE ON FUNCTION workspace.default.get_related_tag_window_stats TO `<app-service-principal>`;
-- GRANT EXECUTE ON FUNCTION workspace.default.get_before_during_after_stats TO `<app-service-principal>`;
-- GRANT EXECUTE ON FUNCTION workspace.default.get_missingness_gap_profile TO `<app-service-principal>`;
-- GRANT EXECUTE ON FUNCTION workspace.default.get_outlier_threshold_context TO `<app-service-principal>`;
