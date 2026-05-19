import importlib


DEFAULT_SAMPLE_JSON_VOLUME_DIR = "/Volumes/workspace/default/history_kag_sample/sample data/"
DEFAULT_SAMPLE_ORIGINAL_TABLE = "workspace.default.sample_original"
SUPPORTED_WRITE_MODES = {"append", "overwrite"}
PI_TIMESTAMP_FORMAT = "yyyy-MM-dd'T'HH:mm:ss.SSSSSSSXXX"

KAG_MEASUREMENT_COLUMN_MAPPINGS = (
    ("Lp Steam Pressure Set Point", "Lp_Steam_Pressure_Set_Point"),
    ("Kgl To Tp Rtu Mw Net", "Kgl_To_Tp_Rtu_Mw_Net"),
    ("1st Brip A Motor Speed", "1st_Brip_A_Motor_Speed"),
    ("1st Brip B Motor Speed", "1st_Brip_B_Motor_Speed"),
    ("2nd Stage Brip A Current", "2nd_Stage_Brip_A_Current"),
    ("2nd Stage Brip B Current", "2nd_Stage_Brip_B_Current"),
    ("Brine Flow To Reinjection", "Brine_Flow_To_Reinjection"),
    ("Brine Flow To Reinjection  Pressure", "Brine_Flow_To_Reinjection_Pressure"),
    ("Total Brine Reinjection Flow", "Total_Brine_Reinjection_Flow"),
    ("Hp Brine Flow", "Hp_Brine_Flow"),
    ("Ka61 Prod Well Two Phase Flow", "KA61_Prod_Well_Two_Phase_Flow"),
    ("Ka52 Prod Well 2 Phase Flow", "Ka52_Prod_Well_2_Phase_Flow"),
    ("Ka46 Prod Well 2 Phase Flow", "Ka46_Prod_Well_2_Phase_Flow"),
    ("Ka45 Prod Well 2 Phase Flow", "Ka45_Prod_Well_2_Phase_Flow"),
    ("Ka41 Prod Well 2 Phase Flow", "Ka41_Prod_Well_2_Phase_Flow"),
    ("Ka42 Prod Well 2 Phase Flow", "Ka42_Prod_Well_2_Phase_Flow"),
    ("Pk06 Prod Well 2 Phase Flow", "Pk06_Prod_Well_2_Phase_Flow"),
    ("Pk07 Prod Well 2 Phase Flow", "Pk07_Prod_Well_2_Phase_Flow"),
    ("Ntga Steam Flow Demand", "Ntga_Steam_Flow_Demand"),
    ("Hp Seperator Pressure 1", "Hp_Seperator_Pressure_1"),
    ("Hp Steam Flow To Turbine", "Hp_Steam_Flow_To_Turbine"),
    ("Lp Seperator Pressure 1", "Lp_Seperator_Pressure_1"),
    ("Lp Steam Flow To Turbine", "Lp_Steam_Flow_To_Turbine"),
    ("Ges Motive Steam Flow", "Ges_Motive_Steam_Flow"),
    ("Condenser Hotwell Temperature", "Condenser_Hotwell_Temperature"),
    (
        "Cooling Tower Inlet Condensate Temperature",
        "Cooling_Tower_Inlet_Condensate_Temperature",
    ),
    ("Cooling Water Flow", "Cooling_Water_Flow"),
    ("Main Cooling Water Temperature", "Main_Cooling_Water_Temperature"),
    ("Total Turbine Steam Flow", "Total_Turbine_Steam_Flow"),
    ("Turbine Hp Chamber Pressure", "Turbine_Hp_Chamber_Pressure"),
    ("Turbine Lp Chamber Pressure", "Turbine_Lp_Chamber_Pressure"),
    ("Condenser Pressure A", "Condenser_Pressure_A"),
    ("Condenser Pressure B", "Condenser_Pressure_B"),
    ("Condenser Pressure C", "Condenser_Pressure_C"),
    ("Condenser Pressure D", "Condenser_Pressure_D"),
    ("Vacuum Pump 40  Current", "Vacuum_Pump_40_Current"),
    ("Vacuum Pump 60  Current", "Vacuum_Pump_60_Current"),
    ("Vacuum Pump 80  Current", "Vacuum_Pump_80_Current"),
    ("Ncg Discharge Flow", "Ncg_Discharge_Flow"),
    (
        "Generator Cooling Air Temperature Cold Turbine Side",
        "Generator_Cooling_Air_Temperature_Cold_Turbine_Side",
    ),
    ("Gross Generator Output", "Gross_Generator_Output"),
    ("Cooling Tower Fan A Current", "Cooling_Tower_Fan_A_Current"),
    ("Cooling Tower Fan B Current", "Cooling_Tower_Fan_B_Current"),
    ("Cooling Tower Fan C Current", "Cooling_Tower_Fan_C_Current"),
    ("Cooling Tower Fan D Current", "Cooling_Tower_Fan_D_Current"),
    ("Cooling Tower Fan E Current", "Cooling_Tower_Fan_E_Current"),
    ("Cooling Tower Fan F Current", "Cooling_Tower_Fan_F_Current"),
    ("Cooling Tower Fan G Current", "Cooling_Tower_Fan_G_Current"),
    ("Cooling Tower Fan H Current", "Cooling_Tower_Fan_H_Current"),
    ("Cooling Tower Fan I Current", "Cooling_Tower_Fan_I_Current"),
    ("Cooling Tower Fan J Current", "Cooling_Tower_Fan_J_Current"),
    ("Stg Cooling Water Supply Pressure", "Stg_Cooling_Water_Supply_Pressure"),
    ("Atmospheric Temperature Dry", "Atmospheric_Temperature_Dry"),
    ("Humidity", "Humidity"),
    ("Kawerau Total Mw", "Kawerau_Total_Mw"),
    ("Net Power", "Net_Power"),
    ("Parasitic Load", "Parasitic_Load"),
    ("Station Enthalpy", "Station_Enthalpy"),
    ("Lp Demister Steam Pressure", "LP_STEAM_PRESSURE_2"),
    ("Ka45 Wellhead Pressure", "KA45_Wellhead_Pressure"),
    ("Ka45 Production Well Enthalpy", "KA45_Production_Well_Enthalpy"),
    ("Ka46 Wellhead Pressure", "KA46_Wellhead_Pressure"),
    ("Ka46 Production Well Enthalpy", "KA46_Production_Well_Enthalpy"),
    ("Ka41 Wellhead Pressure", "KA41_Wellhead_Pressure"),
    ("Ka41 Production Well Enthalpy", "KA41_Production_Well_Enthalpy"),
    ("Ka42 Wellhead Pressure", "KA42_Wellhead_Pressure"),
    ("Ka42 Production Well Enthalpy", "KA42_Production_Well_Enthalpy"),
    ("Pk07 Wellhead Pressure", "PK07_Wellhead_Pressure"),
    ("Pk07 Production Well Enthalpy", "PK07_Production_Well_Enthalpy"),
    ("Ka61 Production Wellhead Pressure", "KA61_Production_Wellhead_Pressure"),
    ("Ka61 Prod Well Enthalpy", "KA61_Prod_Well_Enthalpy"),
    ("Kgl 11kv Generator Voltage", "KGL_11kV_Generator_Voltage"),
    ("Kgl 110kv Transmission Voltage", "KGL_110kV_Transmission_Voltage"),
    ("Condensate Flow", "Condensate_Flow"),
    (
        "Condensate Re Injection Pump A Motor Winding Temperature U",
        "Condensate_Re_Injection_Pump_A_Motor_Winding_Temperature_U",
    ),
    (
        "Condensate Re Injection Pump B Motor Winding Temperature U",
        "Condensate_Re_Injection_Pump_B_Motor_Winding_Temperature_U",
    ),
)


def _optional_column(sample_df, candidate_columns: tuple[str, ...], cast_type: str):
    """
    Select the first existing source column, or produce a typed NULL column.

    Args:
        sample_df: Source Spark DataFrame.
        candidate_columns: Candidate source column names in priority order.
        cast_type: Spark SQL type name for the resulting column.

    Returns:
        pyspark.sql.column.Column: Selected or NULL fallback expression.
    """
    spark_functions = importlib.import_module("pyspark.sql.functions")

    for column_name in candidate_columns:
        if column_name in sample_df.columns:
            return spark_functions.col(f"`{column_name}`").cast(cast_type)
    return spark_functions.lit(None).cast(cast_type)


def apply_kinesis_field_mapping(sample_df):
    """
    Apply the same field projection and renaming used by the Kinesis ingestion notebook.

    Args:
        sample_df: Raw JSON DataFrame loaded from sample files.

    Returns:
        pyspark.sql.dataframe.DataFrame: Mapped DataFrame ready for table write.
    """
    spark_functions = importlib.import_module("pyspark.sql.functions")

    measurement_columns = [
        _optional_column(sample_df, (source_name, target_name), "double").alias(target_name)
        for source_name, target_name in KAG_MEASUREMENT_COLUMN_MAPPINGS
    ]
    projected_df = sample_df.select(
        *measurement_columns,
        _optional_column(sample_df, ("Timestamp", "Pi_Timestamp"), "string").alias("Pi_Timestamp"),
    )
    return projected_df.withColumn(
        "Current_Timestamp", spark_functions.current_timestamp()
    ).withColumn(
        "Pi_Timestamp",
        spark_functions.to_timestamp(spark_functions.col("Pi_Timestamp"), PI_TIMESTAMP_FORMAT),
    )


def normalize_directory_path(directory_path: str) -> str:
    """
    Normalize a source directory for Spark file loading.

    Args:
        directory_path: Volume directory containing JSON files.

    Returns:
        str: Directory path with surrounding whitespace removed and a trailing slash.

    Raises:
        ValueError: If the directory path is empty.
    """
    normalized_path = directory_path.strip()
    if not normalized_path:
        raise ValueError("directory_path must not be empty.")

    return normalized_path if normalized_path.endswith("/") else f"{normalized_path}/"


def validate_write_mode(write_mode: str) -> str:
    """
    Validate the Spark write mode used for table loading.

    Args:
        write_mode: Requested write mode.

    Returns:
        str: Lowercase validated write mode.

    Raises:
        ValueError: If the write mode is unsupported.
    """
    normalized_mode = write_mode.strip().lower()
    if normalized_mode not in SUPPORTED_WRITE_MODES:
        allowed_modes = ", ".join(sorted(SUPPORTED_WRITE_MODES))
        raise ValueError(
            f"Unsupported write_mode '{write_mode}'. Expected one of: {allowed_modes}."
        )

    return normalized_mode


def load_sample_json_to_table(
    spark,
    source_directory: str = DEFAULT_SAMPLE_JSON_VOLUME_DIR,
    target_table: str = DEFAULT_SAMPLE_ORIGINAL_TABLE,
    write_mode: str = "overwrite",
) -> None:
    """
    Load sample JSON files from a Databricks Volume into a Unity Catalog table.

    Args:
        spark: Active Spark session.
        source_directory: Directory containing sample JSON files.
        target_table: Fully qualified Unity Catalog table name.
        write_mode: Spark write mode. Supports `overwrite` and `append`.

    Returns:
        None: Data is written to the target table as a side effect.
    """
    normalized_source_directory = normalize_directory_path(source_directory)
    normalized_target_table = target_table.strip()
    if not normalized_target_table:
        raise ValueError("target_table must not be empty.")

    normalized_write_mode = validate_write_mode(write_mode)

    sample_df = (
        spark.read.option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "*.json")
        .option("multiLine", "true")
        .json(normalized_source_directory)
    )
    if not sample_df.take(1):
        raise ValueError(
            f"No JSON rows loaded from source_directory: {normalized_source_directory}"
        )

    mapped_df = apply_kinesis_field_mapping(sample_df)
    mapped_df.write.mode(normalized_write_mode).saveAsTable(normalized_target_table)


if __name__ == "__main__":
    load_sample_json_to_table(spark)
