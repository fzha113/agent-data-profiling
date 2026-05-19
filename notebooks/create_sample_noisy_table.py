# Databricks notebook source
# MAGIC %md
# MAGIC # Create Demo Noisy Sample Table
# MAGIC
# MAGIC This notebook creates `workspace.default.sample_noisy` from `workspace.default.sample_original`.
# MAGIC It keeps timestamp and non-numeric columns unchanged, and applies one-sided 0-2% noise to
# MAGIC numeric columns using `x + rand() * 0.02 * x`.

# COMMAND ----------

from pyspark.sql import functions as F


SOURCE_TABLE = "workspace.default.sample_original"
TARGET_TABLE = "workspace.default.sample_noisy"
TIMESTAMP_COL = "Pi_Timestamp"
NOISE_RATE = 0.02

# `rand()` returns a random value in [0, 1).

NUMERIC_TYPE_PREFIXES = (
    "byte",
    "short",
    "int",
    "integer",
    "long",
    "bigint",
    "float",
    "double",
    "decimal",
)


def is_numeric_type(type_name: str) -> bool:
    normalized_type = type_name.strip().lower()
    return normalized_type.startswith(NUMERIC_TYPE_PREFIXES)


# COMMAND ----------

source_df = spark.table(SOURCE_TABLE)

select_exprs = []
noisy_column_count = 0
for field in source_df.schema.fields:
    source_col = F.col(f"`{field.name}`")
    if field.name != TIMESTAMP_COL and is_numeric_type(field.dataType.simpleString()):
        noisy_col = source_col.cast("double") + (F.rand() * NOISE_RATE * source_col.cast("double"))
        select_exprs.append(noisy_col.alias(field.name))
        noisy_column_count += 1
    else:
        select_exprs.append(source_col)

noisy_df = source_df.select(*select_exprs)

(noisy_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET_TABLE))

print(
    f"Created {TARGET_TABLE} from {SOURCE_TABLE} with {noisy_column_count} noised numeric columns."
)

# COMMAND ----------

display(spark.table(TARGET_TABLE).limit(10))
