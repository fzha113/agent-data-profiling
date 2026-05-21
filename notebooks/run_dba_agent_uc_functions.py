# Databricks notebook source
# MAGIC %md
# MAGIC # Deploy DBA Agent Unity Catalog Functions
# MAGIC
# MAGIC This notebook executes `sql/dba_agent_uc_functions.sql` from this repository.
# MAGIC It rebuilds `workspace.default.sample_incident_tag_values`, optimizes it, and recreates
# MAGIC the read-only JSON evidence functions consumed by `agent-incident-dba`.
# MAGIC
# MAGIC Run this after `workspace.default.sample_noisy`, `workspace.default.sample_monitor_incident`,
# MAGIC `workspace.default.sample_monitor_log`, and `workspace.default.monitor_incident_feedback`
# MAGIC already exist.

# COMMAND ----------

from pathlib import Path


DEFAULT_SQL_RELATIVE_PATH = "sql/dba_agent_uc_functions.sql"


def find_repo_root(start_path: Path) -> Path:
    """
    Find the repository root that contains the DBA SQL asset.

    Args:
        start_path: Directory to start searching from.

    Returns:
        Path: Repository root path.

    Raises:
        FileNotFoundError: If the SQL file cannot be found from start_path or parents.
    """
    for candidate in [start_path, *start_path.parents]:
        sql_path = candidate / DEFAULT_SQL_RELATIVE_PATH
        if sql_path.exists():
            return candidate

    raise FileNotFoundError(
        f"Could not find {DEFAULT_SQL_RELATIVE_PATH} from {start_path}. "
        "Set the sql_file_path widget to the full path of dba_agent_uc_functions.sql."
    )


def strip_sql_line_comments(sql_text: str) -> str:
    """
    Remove standalone SQL line comments before statement splitting.

    Args:
        sql_text: SQL script text.

    Returns:
        str: SQL text without standalone comment lines.
    """
    return "\n".join(line for line in sql_text.splitlines() if not line.lstrip().startswith("--"))


def split_sql_statements(sql_text: str) -> list[str]:
    """
    Split SQL text into semicolon-terminated statements.

    Args:
        sql_text: SQL script text.

    Returns:
        list[str]: Individual SQL statements.
    """
    statements = []
    buffer = []
    in_single_quote = False
    in_backtick = False
    index = 0

    while index < len(sql_text):
        char = sql_text[index]
        next_char = sql_text[index + 1] if index + 1 < len(sql_text) else ""

        if char == "'" and not in_backtick:
            buffer.append(char)
            if in_single_quote and next_char == "'":
                buffer.append(next_char)
                index += 2
                continue
            in_single_quote = not in_single_quote
            index += 1
            continue

        if char == "`" and not in_single_quote:
            in_backtick = not in_backtick
            buffer.append(char)
            index += 1
            continue

        if char == ";" and not in_single_quote and not in_backtick:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    statement = "".join(buffer).strip()
    if statement:
        statements.append(statement)

    return statements


# COMMAND ----------

dbutils.widgets.text(
    "sql_file_path",
    "",
    "Optional full path to sql/dba_agent_uc_functions.sql",
)
dbutils.widgets.dropdown("run_smoke_tests", "true", ["true", "false"], "Run smoke tests")

sql_file_path_param = dbutils.widgets.get("sql_file_path").strip()
run_smoke_tests = dbutils.widgets.get("run_smoke_tests").strip().lower() == "true"

if sql_file_path_param:
    sql_file_path = Path(sql_file_path_param)
else:
    repo_root = find_repo_root(Path.cwd())
    sql_file_path = repo_root / DEFAULT_SQL_RELATIVE_PATH

if not sql_file_path.exists():
    raise FileNotFoundError(f"SQL file does not exist: {sql_file_path}")

print(f"Using SQL file: {sql_file_path}")

# COMMAND ----------

sql_text = sql_file_path.read_text()
statements = split_sql_statements(strip_sql_line_comments(sql_text))

print(f"Executing {len(statements)} SQL statements")

for statement_index, statement in enumerate(statements, start=1):
    first_line = statement.splitlines()[0]
    print(f"[{statement_index}/{len(statements)}] {first_line[:120]}")
    spark.sql(statement)

print("DBA agent UC SQL assets deployed.")

# COMMAND ----------

if run_smoke_tests:
    display(
        spark.sql("""
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT tag_name) AS tag_count,
                MIN(Pi_Timestamp) AS min_ts,
                MAX(Pi_Timestamp) AS max_ts
            FROM workspace.default.sample_incident_tag_values
        """)
    )

# COMMAND ----------

if run_smoke_tests:
    display(
        spark.sql("""
            SELECT
                tag_name,
                COUNT(*) AS row_count,
                MIN(Pi_Timestamp) AS min_ts,
                MAX(Pi_Timestamp) AS max_ts
            FROM workspace.default.sample_incident_tag_values
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

if run_smoke_tests:
    display(
        spark.sql("""
            SELECT workspace.default.get_app_tag_catalog() AS tag_catalog_json
        """)
    )

# COMMAND ----------

if run_smoke_tests:
    display(
        spark.sql("""
            SELECT workspace.default.get_raw_points_sample(
                array('2nd_Stage_Brip_A_Current'),
                TIMESTAMP('2024-08-07 23:00:00'),
                TIMESTAMP('2024-08-08 04:00:00')
            ) AS raw_points_json
        """)
    )
