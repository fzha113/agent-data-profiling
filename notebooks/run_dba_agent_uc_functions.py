# Databricks notebook source
# MAGIC %md
# MAGIC # Rebuild DBA Evidence Tag Table
# MAGIC
# MAGIC This notebook rebuilds `workspace.default.sample_incident_tag_values` from
# MAGIC `workspace.default.sample_noisy` with the full KAG monitored tag set.
# MAGIC
# MAGIC Run this when DBA evidence checks return empty results for tags that exist in
# MAGIC `sample_noisy`, such as `2nd_Stage_Brip_A_Current`.

# COMMAND ----------

SOURCE_TABLE = "workspace.default.sample_noisy"
TARGET_TABLE = "workspace.default.sample_incident_tag_values"

# COMMAND ----------

spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")

spark.sql(f"""
CREATE TABLE {TARGET_TABLE}
USING DELTA
AS
SELECT
    Pi_Timestamp,
    tag_name,
    CAST(tag_value AS DOUBLE) AS tag_value
FROM {SOURCE_TABLE}
LATERAL VIEW stack(45,
    '1ST_BRIP_A_MOTOR_SPEED', CAST(`1ST_BRIP_A_MOTOR_SPEED` AS DOUBLE),
    '1ST_BRIP_B_MOTOR_SPEED', CAST(`1ST_BRIP_B_MOTOR_SPEED` AS DOUBLE),
    '2nd_Stage_Brip_A_Current', CAST(`2nd_Stage_Brip_A_Current` AS DOUBLE),
    '2nd_Stage_Brip_B_Current', CAST(`2nd_Stage_Brip_B_Current` AS DOUBLE),
    'Atmospheric_Temperature_Dry', CAST(`Atmospheric_Temperature_Dry` AS DOUBLE),
    'COOLING_TOWER_FAN_A_CURRENT', CAST(`COOLING_TOWER_FAN_A_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_B_CURRENT', CAST(`COOLING_TOWER_FAN_B_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_C_CURRENT', CAST(`COOLING_TOWER_FAN_C_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_D_CURRENT', CAST(`COOLING_TOWER_FAN_D_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_E_CURRENT', CAST(`COOLING_TOWER_FAN_E_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_F_CURRENT', CAST(`COOLING_TOWER_FAN_F_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_G_CURRENT', CAST(`COOLING_TOWER_FAN_G_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_H_CURRENT', CAST(`COOLING_TOWER_FAN_H_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_I_CURRENT', CAST(`COOLING_TOWER_FAN_I_CURRENT` AS DOUBLE),
    'COOLING_TOWER_FAN_J_CURRENT', CAST(`COOLING_TOWER_FAN_J_CURRENT` AS DOUBLE),
    'Condenser_Hotwell_Temperature', CAST(`Condenser_Hotwell_Temperature` AS DOUBLE),
    'Condenser_Pressure_A', CAST(`Condenser_Pressure_A` AS DOUBLE),
    'Condenser_Pressure_B', CAST(`Condenser_Pressure_B` AS DOUBLE),
    'Condenser_Pressure_C', CAST(`Condenser_Pressure_C` AS DOUBLE),
    'Condenser_Pressure_D', CAST(`Condenser_Pressure_D` AS DOUBLE),
    'Cooling_Tower_Inlet_Condensate_Temperature', CAST(`Cooling_Tower_Inlet_Condensate_Temperature` AS DOUBLE),
    'Cooling_Water_Flow', CAST(`Cooling_Water_Flow` AS DOUBLE),
    'Generator_Cooling_Air_Temperature_Cold_Turbine_Side', CAST(`Generator_Cooling_Air_Temperature_Cold_Turbine_Side` AS DOUBLE),
    'Gross_Generator_Output', CAST(`Gross_Generator_Output` AS DOUBLE),
    'HP_BRINE_FLOW', CAST(`HP_BRINE_FLOW` AS DOUBLE),
    'Hp_Seperator_Pressure_1', CAST(`Hp_Seperator_Pressure_1` AS DOUBLE),
    'Hp_Steam_Flow_To_Turbine', CAST(`Hp_Steam_Flow_To_Turbine` AS DOUBLE),
    'Humidity', CAST(`Humidity` AS DOUBLE),
    'KA61_Prod_Well_Two_Phase_Flow', CAST(`KA61_Prod_Well_Two_Phase_Flow` AS DOUBLE),
    'Kawerau_Total_Mw', CAST(`Kawerau_Total_Mw` AS DOUBLE),
    'Kgl_To_Tp_Rtu_Mw_Net', CAST(`Kgl_To_Tp_Rtu_Mw_Net` AS DOUBLE),
    'LP_STEAM_PRESSURE_2', CAST(`LP_STEAM_PRESSURE_2` AS DOUBLE),
    'Lp_Seperator_Pressure_1', CAST(`Lp_Seperator_Pressure_1` AS DOUBLE),
    'Lp_Steam_Flow_To_Turbine', CAST(`Lp_Steam_Flow_To_Turbine` AS DOUBLE),
    'Main_Cooling_Water_Temperature', CAST(`Main_Cooling_Water_Temperature` AS DOUBLE),
    'Net_Power', CAST(`Net_Power` AS DOUBLE),
    'PARASITIC_LOAD', CAST(`PARASITIC_LOAD` AS DOUBLE),
    'Station_Enthalpy', CAST(`Station_Enthalpy` AS DOUBLE),
    'Stg_Cooling_Water_Supply_Pressure', CAST(`Stg_Cooling_Water_Supply_Pressure` AS DOUBLE),
    'Total_Turbine_Steam_Flow', CAST(`Total_Turbine_Steam_Flow` AS DOUBLE),
    'Turbine_Hp_Chamber_Pressure', CAST(`Turbine_Hp_Chamber_Pressure` AS DOUBLE),
    'Turbine_Lp_Chamber_Pressure', CAST(`Turbine_Lp_Chamber_Pressure` AS DOUBLE),
    'Vacuum_Pump_40_Current', CAST(`Vacuum_Pump_40_Current` AS DOUBLE),
    'Vacuum_Pump_60_Current', CAST(`Vacuum_Pump_60_Current` AS DOUBLE),
    'Vacuum_Pump_80_Current', CAST(`Vacuum_Pump_80_Current` AS DOUBLE)
) tag_stack AS tag_name, tag_value
WHERE Pi_Timestamp IS NOT NULL
  AND tag_value IS NOT NULL
""")

# COMMAND ----------

spark.sql(f"OPTIMIZE {TARGET_TABLE} ZORDER BY (tag_name, Pi_Timestamp)")

# COMMAND ----------

display(
    spark.sql(f"""
        SELECT
            COUNT(*) AS row_count,
            COUNT(DISTINCT tag_name) AS tag_count,
            MIN(Pi_Timestamp) AS min_ts,
            MAX(Pi_Timestamp) AS max_ts
        FROM {TARGET_TABLE}
    """)
)

# COMMAND ----------

display(
    spark.sql(f"""
        SELECT
            tag_name,
            COUNT(*) AS row_count,
            MIN(Pi_Timestamp) AS min_ts,
            MAX(Pi_Timestamp) AS max_ts
        FROM {TARGET_TABLE}
        WHERE tag_name IN (
            '2nd_Stage_Brip_A_Current',
            '2nd_Stage_Brip_B_Current',
            '1ST_BRIP_A_MOTOR_SPEED',
            '1ST_BRIP_B_MOTOR_SPEED'
        )
        GROUP BY tag_name
        ORDER BY tag_name
    """)
)

# COMMAND ----------

display(spark.sql(f"SELECT * FROM {TARGET_TABLE} LIMIT 10"))
