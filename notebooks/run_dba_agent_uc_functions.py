# Databricks notebook source
# MAGIC %md
# MAGIC # Rebuild DBA Evidence Tag Table
# MAGIC
# MAGIC This notebook rebuilds `workspace.default.sample_incident_tag_values` from
# MAGIC `workspace.default.sample_noisy`.
# MAGIC
# MAGIC It only expands tags that actually exist as columns in `sample_noisy`, and reports monitored
# MAGIC tags that are missing from the table. This avoids failing when the monitoring tag list contains
# MAGIC tags that are not present in the sample dataset.

# COMMAND ----------

SOURCE_TABLE = "workspace.default.sample_noisy"
TARGET_TABLE = "workspace.default.sample_incident_tag_values"
TIMESTAMP_COL = "Pi_Timestamp"

MONITORED_TAGS = [
    "1ST_BRIP_A_MOTOR_SPEED",
    "1ST_BRIP_B_MOTOR_SPEED",
    "2nd_Stage_Brip_A_Current",
    "2nd_Stage_Brip_B_Current",
    "Atmospheric_Temperature_Dry",
    "COOLING_TOWER_FAN_A_CURRENT",
    "COOLING_TOWER_FAN_B_CURRENT",
    "COOLING_TOWER_FAN_C_CURRENT",
    "COOLING_TOWER_FAN_D_CURRENT",
    "COOLING_TOWER_FAN_E_CURRENT",
    "COOLING_TOWER_FAN_F_CURRENT",
    "COOLING_TOWER_FAN_G_CURRENT",
    "COOLING_TOWER_FAN_H_CURRENT",
    "COOLING_TOWER_FAN_I_CURRENT",
    "COOLING_TOWER_FAN_J_CURRENT",
    "Condenser_Hotwell_Temperature",
    "Condenser_Pressure_A",
    "Condenser_Pressure_B",
    "Condenser_Pressure_C",
    "Condenser_Pressure_D",
    "Cooling_Tower_Inlet_Condensate_Temperature",
    "Cooling_Water_Flow",
    "Generator_Cooling_Air_Temperature_Cold_Turbine_Side",
    "Gross_Generator_Output",
    "HP_BRINE_FLOW",
    "Hp_Seperator_Pressure_1",
    "Hp_Steam_Flow_To_Turbine",
    "Humidity",
    "KA61_Prod_Well_Two_Phase_Flow",
    "Kawerau_Total_Mw",
    "Kgl_To_Tp_Rtu_Mw_Net",
    "LP_STEAM_PRESSURE_2",
    "Lp_Seperator_Pressure_1",
    "Lp_Steam_Flow_To_Turbine",
    "Main_Cooling_Water_Temperature",
    "Net_Power",
    "PARASITIC_LOAD",
    "Station_Enthalpy",
    "Stg_Cooling_Water_Supply_Pressure",
    "Total_Turbine_Steam_Flow",
    "Turbine_Hp_Chamber_Pressure",
    "Turbine_Lp_Chamber_Pressure",
    "Vacuum_Pump_40_Current",
    "Vacuum_Pump_60_Current",
    "Vacuum_Pump_80_Current",
]

# COMMAND ----------

source_columns = set(spark.table(SOURCE_TABLE).columns)

if TIMESTAMP_COL not in source_columns:
    raise ValueError(f"{SOURCE_TABLE} does not contain timestamp column {TIMESTAMP_COL}")

available_tags = [tag for tag in MONITORED_TAGS if tag in source_columns]
missing_tags = [tag for tag in MONITORED_TAGS if tag not in source_columns]

print(f"Source table: {SOURCE_TABLE}")
print(f"Target table: {TARGET_TABLE}")
print(f"Available monitored tags: {len(available_tags)}")
print(f"Missing monitored tags: {len(missing_tags)}")
for tag in missing_tags:
    print(f"Missing from {SOURCE_TABLE}: {tag}")

if not available_tags:
    raise ValueError(f"No monitored tag columns were found in {SOURCE_TABLE}")

# COMMAND ----------

display(
    spark.createDataFrame(
        [(tag,) for tag in missing_tags],
        "missing_tag STRING",
    )
)

# COMMAND ----------


def quote_identifier(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"


stack_items = ",\n    ".join(
    f"'{tag}', CAST({quote_identifier(tag)} AS DOUBLE)" for tag in available_tags
)

spark.sql(f"DROP TABLE IF EXISTS {TARGET_TABLE}")

spark.sql(f"""
CREATE TABLE {TARGET_TABLE}
USING DELTA
AS
SELECT
    {quote_identifier(TIMESTAMP_COL)} AS Pi_Timestamp,
    tag_name,
    CAST(tag_value AS DOUBLE) AS tag_value
FROM {SOURCE_TABLE}
LATERAL VIEW stack({len(available_tags)},
    {stack_items}
) tag_stack AS tag_name, tag_value
WHERE {quote_identifier(TIMESTAMP_COL)} IS NOT NULL
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
