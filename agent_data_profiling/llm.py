import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from databricks.sdk.core import Config

from agent_data_profiling.tag_catalog import TAG_CATALOG


DISPLAY_TIMEZONE = ZoneInfo("Pacific/Auckland")
AI_GATEWAY_PATH = "/ai-gateway/mlflow/v1"
CHAT_COMPLETIONS_PATH = "/chat/completions"
SERVING_ENDPOINTS_PATH = "/serving-endpoints"
PROMPT_DIR_ENV_VAR = "AGENT_DATA_PROFILING_LLM_PROMPT_DIR"
DEFAULT_PROMPT_DIR = Path(__file__).with_name("prompts")
DEFAULT_MAX_TOKENS = 2048
DEFAULT_REASONING_EFFORT = "none"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_SUPERVISOR_TIMEOUT_SECONDS = 180
MAX_DISTRIBUTION_BINS = 5
MAX_QUALITY_LOG_ROWS = 12
APPROVED_SUPERVISOR_TOOL_NAMES = frozenset(
    {
        "app-agent-graph-assistant",
        "app-agent-incident-analysis",
        "app-agent-incident-dba",
        "agent-incident-analysis",
        "agent-incident-dba",
    }
)
MAX_SUPERVISOR_APPROVAL_ROUNDS = 8


@dataclass(frozen=True)
class AiGatewayConfig:
    """
    Runtime configuration for Databricks AI Gateway chat completions.

    Args:
        endpoint_name: Unity AI Gateway endpoint name.
        base_url: AI Gateway base URL ending in `/ai-gateway/mlflow/v1`.
        max_tokens: Maximum model output tokens.
        temperature: Optional sampling temperature. Omit for GPT models that only allow defaults.
        reasoning_effort: Optional reasoning effort for GPT reasoning models.
        timeout_seconds: HTTP request timeout in seconds.
    """

    endpoint_name: str
    base_url: str
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float | None = None
    reasoning_effort: str | None = DEFAULT_REASONING_EFFORT
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class SupervisorAgentConfig:
    """
    Runtime configuration for querying a Databricks Supervisor Agent endpoint.

    Args:
        endpoint_name: Databricks Agent endpoint name.
        responses_url: Workspace Responses API URL for serving endpoints.
        timeout_seconds: HTTP request timeout in seconds.
    """

    endpoint_name: str
    responses_url: str
    timeout_seconds: int = DEFAULT_SUPERVISOR_TIMEOUT_SECONDS


@dataclass(frozen=True)
class LlmPromptConfig:
    """
    Prompt templates for KAG AI analysis.

    Args:
        station_context: Shared KAG station process context.
        tag_profile_system: System prompt template for tag profiling analysis.
        tag_profile_user: User prompt template for tag profiling analysis.
        incident_system: System prompt template for incident analysis.
        incident_user: User prompt template for incident analysis.
    """

    station_context: str
    tag_profile_system: str
    tag_profile_user: str
    incident_system: str
    incident_user: str


def get_ai_gateway_config_from_env() -> AiGatewayConfig:
    """
    Read Databricks AI Gateway settings from app environment variables.

    Args:
        None.

    Returns:
        AiGatewayConfig: Runtime endpoint configuration.

    Raises:
        RuntimeError: If the endpoint name or workspace host is missing.
    """
    endpoint_name = os.getenv("DATABRICKS_AI_GATEWAY_ENDPOINT")
    if not endpoint_name:
        raise RuntimeError("DATABRICKS_AI_GATEWAY_ENDPOINT is not configured.")

    base_url = os.getenv("DATABRICKS_AI_GATEWAY_BASE_URL")
    if base_url:
        base_url = _normalise_gateway_base_url(base_url)
    else:
        host = os.getenv("DATABRICKS_HOST")
        if not host:
            raise RuntimeError("DATABRICKS_HOST is not configured.")
        base_url = f"{_normalise_workspace_host(host)}{AI_GATEWAY_PATH}"

    reasoning_effort = os.getenv(
        "DATABRICKS_AI_GATEWAY_REASONING_EFFORT",
        DEFAULT_REASONING_EFFORT,
    ).strip()

    return AiGatewayConfig(
        endpoint_name=endpoint_name,
        base_url=base_url,
        reasoning_effort=reasoning_effort or None,
    )


def get_supervisor_agent_config_from_env() -> SupervisorAgentConfig:
    """
    Read Databricks Supervisor Agent endpoint settings from app environment variables.

    Args:
        None.

    Returns:
        SupervisorAgentConfig: Runtime Supervisor Agent endpoint configuration.

    Raises:
        RuntimeError: If the endpoint name or workspace host is missing.
    """
    endpoint_name = os.getenv("DATABRICKS_SUPERVISOR_AGENT_ENDPOINT")
    if not endpoint_name:
        raise RuntimeError("DATABRICKS_SUPERVISOR_AGENT_ENDPOINT is not configured.")

    host = os.getenv("DATABRICKS_HOST")
    if not host:
        raise RuntimeError("DATABRICKS_HOST is not configured.")

    timeout_seconds = int(
        os.getenv(
            "DATABRICKS_SUPERVISOR_AGENT_TIMEOUT_SECONDS",
            str(DEFAULT_SUPERVISOR_TIMEOUT_SECONDS),
        )
    )

    return SupervisorAgentConfig(
        endpoint_name=endpoint_name,
        responses_url=(
            f"{_normalise_workspace_host(host)}{SERVING_ENDPOINTS_PATH}/{endpoint_name}/invocations"
        ),
        timeout_seconds=timeout_seconds,
    )


def load_llm_prompt_config(prompt_dir: str | Path | None = None) -> LlmPromptConfig:
    """
    Load LLM prompt templates from a Markdown prompt directory.

    Args:
        prompt_dir: Optional prompt directory. If omitted, the app reads
            `AGENT_DATA_PROFILING_LLM_PROMPT_DIR` or the bundled default directory.

    Returns:
        LlmPromptConfig: Prompt templates used by AI analysis buttons.

    Raises:
        RuntimeError: If the prompt directory cannot be read or is incomplete.
    """
    prompt_dir_path = _get_prompt_dir(prompt_dir)

    return LlmPromptConfig(
        station_context=_read_prompt_file(prompt_dir_path, "station_context.md"),
        tag_profile_system=_read_prompt_file(prompt_dir_path, "tag_profile_system.md"),
        tag_profile_user=_read_prompt_file(prompt_dir_path, "tag_profile_user.md"),
        incident_system=_read_prompt_file(prompt_dir_path, "incident_system.md"),
        incident_user=_read_prompt_file(prompt_dir_path, "incident_user.md"),
    )


def get_databricks_oauth_token() -> str:
    """
    Get a bearer token for AI Gateway using Databricks app credentials.

    Args:
        None.

    Returns:
        str: Bearer token value without the `Bearer` prefix.

    Raises:
        RuntimeError: If OAuth credentials are not configured.
    """
    pat_token = os.getenv("DATABRICKS_TOKEN")
    if pat_token:
        return pat_token

    host = os.getenv("DATABRICKS_HOST")
    client_id = os.getenv("DATABRICKS_CLIENT_ID")
    client_secret = os.getenv("DATABRICKS_CLIENT_SECRET")
    if not host or not client_id or not client_secret:
        raise RuntimeError(
            "DATABRICKS_HOST, DATABRICKS_CLIENT_ID, and DATABRICKS_CLIENT_SECRET "
            "are required for AI Gateway OAuth."
        )

    config = Config(
        host=_normalise_workspace_host(host),
        client_id=client_id,
        client_secret=client_secret,
    )
    return config.oauth_token().access_token


def query_ai_gateway(
    config: AiGatewayConfig,
    messages: list[dict[str, str]],
    request_tags: dict[str, str] | None = None,
    access_token_provider=get_databricks_oauth_token,
    post=requests.post,
) -> str:
    """
    Query a Databricks AI Gateway chat-completions endpoint.

    Args:
        config: AI Gateway endpoint configuration.
        messages: OpenAI-compatible chat messages.
        request_tags: Optional AI Gateway request tags for tracing.
        access_token_provider: Callable that returns a bearer token.
        post: HTTP POST callable, injected in tests.

    Returns:
        str: Assistant message content.

    Raises:
        ValueError: If the response does not contain assistant content.
        requests.HTTPError: If the gateway returns a non-success HTTP status.
    """
    headers = {
        "Authorization": f"Bearer {access_token_provider()}",
        "Content-Type": "application/json",
    }
    if request_tags:
        headers["Databricks-Ai-Gateway-Request-Tags"] = json.dumps(
            request_tags,
            sort_keys=True,
        )

    request_body = {
        "model": config.endpoint_name,
        "messages": messages,
        "max_tokens": config.max_tokens,
    }
    if config.temperature is not None:
        request_body["temperature"] = config.temperature
    if config.reasoning_effort is not None:
        request_body["reasoning_effort"] = config.reasoning_effort

    response = post(
        f"{config.base_url}{CHAT_COMPLETIONS_PATH}",
        headers=headers,
        json=request_body,
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()

    try:
        choice = payload["choices"][0]
        content = _extract_message_content(choice["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("AI Gateway response did not include assistant content.") from exc

    if not content:
        raise ValueError(_build_empty_content_error_message(payload))
    return str(content)


def query_supervisor_agent(
    config: SupervisorAgentConfig,
    prompt: str,
    conversation_id_provider=lambda: str(uuid.uuid4()),
    user_id: str | None = None,
    access_token_provider=get_databricks_oauth_token,
    post=requests.post,
) -> str:
    """
    Query a Databricks Supervisor Agent through the serving endpoints Responses API.

    Args:
        config: Supervisor Agent endpoint configuration.
        prompt: User prompt sent to the Supervisor Agent.
        conversation_id_provider: Callable that returns a Databricks conversation id.
        user_id: Optional Databricks user id for request context.
        access_token_provider: Callable that returns a bearer token.
        post: HTTP POST callable, injected in tests.

    Returns:
        str: Final assistant output text.

    Raises:
        ValueError: If the response does not contain assistant text.
        requests.HTTPError: If the endpoint returns a non-success HTTP status.
    """
    headers = {
        "Authorization": f"Bearer {access_token_provider()}",
        "Content-Type": "application/json",
    }
    conversation_id = conversation_id_provider()
    input_items = [{"role": "user", "content": prompt}]

    for _ in range(MAX_SUPERVISOR_APPROVAL_ROUNDS):
        response = post(
            config.responses_url,
            headers=headers,
            json=_build_supervisor_request_body(input_items, conversation_id, user_id),
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        approval_requests = _extract_mcp_approval_requests(payload)

        if not approval_requests:
            content = _extract_responses_output_text(payload)
            if not content:
                raise ValueError(_build_empty_responses_content_error_message(payload))
            return str(content)

        input_items.extend(_normalise_responses_output(payload))
        input_items.extend(_build_mcp_approval_responses(approval_requests))

    raise RuntimeError("Supervisor Agent exceeded automatic tool approval rounds.")


def build_tag_profile_llm_context(
    tag: str,
    profile_result: dict[str, pd.DataFrame],
    recent_start_time: datetime,
    recent_end_time: datetime,
    baseline_start_time: datetime,
    baseline_end_time: datetime,
) -> dict:
    """
    Build a compact JSON-safe profile context for LLM analysis.

    Args:
        tag: Raw PI tag column name.
        profile_result: Profile datasets for the tag.
        recent_start_time: Inclusive recent profile start timestamp.
        recent_end_time: Inclusive recent profile end timestamp.
        baseline_start_time: Inclusive baseline profile start timestamp.
        baseline_end_time: Inclusive baseline profile end timestamp.

    Returns:
        dict: Compact profile context suitable for AI Gateway input.
    """
    metadata = TAG_CATALOG.get(tag)
    stats = _build_profile_stats(profile_result.get("stats", pd.DataFrame()))
    return {
        "analysis_type": "tag_profile",
        "tag": {
            "name": tag,
            "display_name": metadata.display_name if metadata else tag,
            "unit": metadata.unit if metadata else None,
            "process_area": metadata.process_area if metadata else None,
            "description": metadata.description if metadata else None,
        },
        "windows": {
            "recent_start_nzt": _format_nzt(recent_start_time),
            "recent_end_nzt": _format_nzt(recent_end_time),
            "baseline_start_nzt": _format_nzt(baseline_start_time),
            "baseline_end_nzt": _format_nzt(baseline_end_time),
        },
        "stats": stats,
        "percentile_shift": _build_percentile_shift(stats),
        "density_distribution": _build_density_distribution_summary(
            profile_result.get("histogram", pd.DataFrame()),
        ),
        "daily_trend": _build_daily_trend_summary(
            profile_result.get("daily_trend", pd.DataFrame()),
        ),
        "gap_profile": _first_record(
            profile_result.get("gap", pd.DataFrame()),
            [
                "interval_count",
                "large_gap_count",
                "average_gap_minutes",
                "longest_gap_minutes",
            ],
        ),
    }


def build_tag_profile_llm_messages(context: dict) -> list[dict[str, str]]:
    """
    Build chat messages for tag profile analysis.

    Args:
        context: Tag profile context from `build_tag_profile_llm_context`.

    Returns:
        list[dict[str, str]]: OpenAI-compatible chat messages.
    """
    prompt_config = load_llm_prompt_config()
    context_json = _json_dumps(context)
    return [
        {
            "role": "system",
            "content": _render_prompt_template(
                prompt_config.tag_profile_system,
                station_context=prompt_config.station_context,
                context_json=context_json,
            ),
        },
        {
            "role": "user",
            "content": _render_prompt_template(
                prompt_config.tag_profile_user,
                station_context=prompt_config.station_context,
                context_json=context_json,
            ),
        },
    ]


def build_incident_llm_context(
    incident_id: str,
    incident_rows: pd.DataFrame,
    context_df: pd.DataFrame | None,
    tag: str,
    incident_start: datetime,
    incident_end: datetime,
    outlier_thresholds: tuple[float, float] | None,
) -> dict:
    """
    Build a compact JSON-safe data quality incident context for LLM analysis.

    Args:
        incident_id: Monitor incident identifier.
        incident_rows: Joined monitor incident and quality log rows.
        context_df: Raw PI context points around the incident.
        tag: Raw PI tag name.
        incident_start: Incident start timestamp.
        incident_end: Incident end timestamp.
        outlier_thresholds: Optional outlier lower and upper thresholds.

    Returns:
        dict: Compact incident context suitable for AI Gateway input.
    """
    incident = incident_rows.iloc[0] if not incident_rows.empty else pd.Series(dtype=object)
    return {
        "analysis_type": "data_quality_incident",
        "incident": {
            "incident_id": incident_id,
            "station": _json_safe_scalar(incident.get("station")),
            "source_table": _json_safe_scalar(incident.get("source_table")),
            "tag_name": tag,
            "rule_type": _json_safe_scalar(incident.get("rule_type")),
            "status": _json_safe_scalar(incident.get("status")),
            "incident_start_nzt": _format_nzt(incident_start),
            "incident_end_nzt": _format_nzt(incident_end),
        },
        "outlier_thresholds": _build_outlier_threshold_context(
            outlier_thresholds,
            incident_rows,
        ),
        "outlier_threshold_windows": _extract_outlier_threshold_windows_from_logs(
            incident_rows,
        ),
        "quality_log_rows": _dataframe_records(
            incident_rows,
            [
                "log_run_id",
                "window_start",
                "window_end",
                "observed_value",
                "log_create_ts",
            ],
            MAX_QUALITY_LOG_ROWS,
        ),
        "raw_context": _build_raw_context_summary(
            context_df,
            tag,
            incident_start,
            incident_end,
        ),
    }


def build_incident_llm_messages(context: dict) -> list[dict[str, str]]:
    """
    Build chat messages for data quality incident analysis.

    Args:
        context: Incident context from `build_incident_llm_context`.

    Returns:
        list[dict[str, str]]: OpenAI-compatible chat messages.
    """
    prompt_config = load_llm_prompt_config()
    context_json = _json_dumps(context)
    return [
        {
            "role": "system",
            "content": _render_prompt_template(
                prompt_config.incident_system,
                station_context=prompt_config.station_context,
                context_json=context_json,
            ),
        },
        {
            "role": "user",
            "content": _render_prompt_template(
                prompt_config.incident_user,
                station_context=prompt_config.station_context,
                context_json=context_json,
            ),
        },
    ]


def build_supervisor_incident_prompt(
    context: dict, available_tags: list[str] | tuple[str, ...]
) -> str:
    """
    Build a Supervisor Agent prompt for a data quality incident from app context.

    Args:
        context: Incident context from `build_incident_llm_context`.
        available_tags: Source-table tag columns that actually exist.

    Returns:
        str: Prompt sent to the Supervisor Agent.
    """
    incident_packet = dict(context)
    incident_packet["available_tags"] = list(available_tags)
    context_json = _json_dumps(incident_packet)
    incident = context.get("incident", {})
    tag_name = incident.get("tag_name", "unknown tag")
    rule_type = incident.get("rule_type", "data quality")
    incident_start = incident.get("incident_start_nzt", "unknown start time")
    incident_end = incident.get("incident_end_nzt", "unknown end time")

    return (
        f"Investigate why tag {tag_name} triggered an {rule_type} incident from "
        f"{incident_start} to {incident_end}.\n"
        "Determine whether the likely explanation is a real process issue, a data quality "
        "issue, or a monitoring-rule threshold/baseline issue, using the configured "
        "multi-agent supervisor workflow.\n\n"
        "Incident packet JSON:\n"
        f"{context_json}\n\n"
        "Use the Supervisor Agent's configured order and specialist agents. "
        "If incident_packet.outlier_thresholds contains lower_threshold and upper_threshold, "
        "treat incident_packet.outlier_thresholds as the configured thresholds for this "
        "incident and use those values when comparing DBA evidence against the rule. "
        "When asking the DBA agent for outlier_threshold_context, pass lower_threshold and "
        "upper_threshold from incident_packet.outlier_thresholds directly; do not ask the DBA "
        "agent to infer or rediscover threshold values. Do not say threshold context is missing "
        "when outlier_thresholds are present; only say baseline/provenance is missing if the "
        "workflow did not retrieve how those thresholds were derived. "
        "Return only the final user-facing conclusion in a concise format. "
        "Do not mention graph knowledge, Graphify, station context, or process context unless "
        "the user explicitly asks. Do not invent SQL results, measurements, thresholds, tags, "
        "or root causes."
    )


def _get_prompt_dir(prompt_dir: str | Path | None) -> Path:
    if prompt_dir:
        return Path(prompt_dir)

    configured_dir = os.getenv(PROMPT_DIR_ENV_VAR)
    if configured_dir:
        return Path(configured_dir)
    return DEFAULT_PROMPT_DIR


def _read_prompt_file(prompt_dir: Path, file_name: str) -> str:
    prompt_path = prompt_dir / file_name
    try:
        prompt_text = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read LLM prompt file: {prompt_path}") from exc

    if not prompt_text.strip():
        raise RuntimeError(f"LLM prompt file must not be empty: {prompt_path}")
    return prompt_text.strip()


def _render_prompt_template(template: str, **values: str) -> str:
    rendered_template = template
    for key, value in values.items():
        rendered_template = rendered_template.replace(f"{{{key}}}", value)
    return rendered_template


def _normalise_gateway_base_url(base_url: str) -> str:
    stripped_url = base_url.rstrip("/")
    stripped_url = _normalise_workspace_host(stripped_url)
    if stripped_url.endswith(CHAT_COMPLETIONS_PATH):
        stripped_url = stripped_url[: -len(CHAT_COMPLETIONS_PATH)]
    return stripped_url


def _normalise_workspace_host(host: str) -> str:
    stripped_host = host.rstrip("/")
    if stripped_host.startswith(("https://", "http://")):
        return stripped_host
    return f"https://{stripped_host}"


def _extract_message_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
        ]
        return "\n".join(part for part in text_parts if part)
    if content is None:
        return ""
    return str(content)


def _build_supervisor_request_body(
    input_items: list[dict],
    conversation_id: str,
    user_id: str | None,
) -> dict:
    request_body = {
        "input": input_items,
        "databricks_options": {
            "conversation_id": conversation_id,
            "return_trace": True,
            "long_task": True,
        },
        "context": {
            "conversation_id": conversation_id,
        },
    }
    if user_id:
        request_body["context"]["user_id"] = user_id
    return request_body


def _extract_responses_output_text(payload: dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return _extract_final_supervisor_text(output_text)

    text_parts = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, str):
            text_parts.append(content)
            continue
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"output_text", "text"} and part.get("text"):
                text_parts.append(str(part["text"]))

    if text_parts:
        return _extract_final_supervisor_text("\n".join(text_parts))

    try:
        choice = payload["choices"][0]
        return _extract_final_supervisor_text(
            _extract_message_content(choice["message"]["content"])
        )
    except (KeyError, IndexError, TypeError):
        return ""


def _extract_final_supervisor_text(text: str) -> str:
    supervisor_marker = "<name>data-incident-supervisor</name>"
    if supervisor_marker not in text:
        return text.strip()
    return text.rsplit(supervisor_marker, maxsplit=1)[-1].strip()


def _normalise_responses_output(payload: dict) -> list[dict]:
    output = payload.get("output", [])
    if not isinstance(output, list):
        return []
    return [item for item in output if isinstance(item, dict)]


def _extract_mcp_approval_requests(payload: dict) -> list[dict]:
    approval_requests = []
    for item in _normalise_responses_output(payload):
        if item.get("type") != "mcp_approval_request":
            continue
        tool_name = item.get("name")
        server_label = item.get("server_label")
        if tool_name not in APPROVED_SUPERVISOR_TOOL_NAMES and server_label not in (
            APPROVED_SUPERVISOR_TOOL_NAMES
        ):
            raise RuntimeError(
                "Supervisor Agent requested approval for an unapproved tool: "
                f"name={tool_name}, server_label={server_label}"
            )
        approval_requests.append(item)
    return approval_requests


def _build_mcp_approval_responses(approval_requests: list[dict]) -> list[dict]:
    approval_responses = []
    for approval_request in approval_requests:
        approval_request_id = approval_request.get("approval_request_id") or approval_request.get(
            "id"
        )
        if not approval_request_id:
            raise RuntimeError("Supervisor Agent approval request did not include an id.")
        approval_responses.append(
            {
                "type": "mcp_approval_response",
                "id": approval_request_id,
                "approval_request_id": approval_request_id,
                "approve": True,
            }
        )
    return approval_responses


def _json_dumps(value) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True)


def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, pd.Timestamp | datetime):
        return _format_nzt(value)
    if hasattr(value, "item"):
        return _json_safe_scalar(value.item())
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _build_empty_content_error_message(payload: dict) -> str:
    choice = payload.get("choices", [{}])[0] if payload.get("choices") else {}
    usage = payload.get("usage")
    return (
        "AI Gateway response content was empty. "
        f"finish_reason={choice.get('finish_reason')}; "
        f"usage={json.dumps(usage, sort_keys=True) if usage else None}"
    )


def _build_empty_responses_content_error_message(payload: dict) -> str:
    usage = payload.get("usage")
    return (
        "Supervisor Agent response content was empty. "
        f"status={payload.get('status')}; "
        f"usage={json.dumps(usage, sort_keys=True) if usage else None}"
    )


def _format_nzt(value) -> str | None:
    if value is None or pd.isna(value):
        return None

    timestamp = _to_utc_timestamp(value)
    return f"{timestamp.tz_convert(DISPLAY_TIMEZONE):%Y-%m-%d %H:%M} NZT"


def _to_utc_timestamp(value) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(UTC)
    return timestamp.tz_convert(UTC)


def _to_utc_series(values: pd.Series) -> pd.Series:
    timestamps = pd.to_datetime(values)
    if timestamps.dt.tz is None:
        return timestamps.dt.tz_localize(UTC)
    return timestamps.dt.tz_convert(UTC)


def _json_safe_scalar(value):
    result = value
    if value is None:
        result = None
    elif isinstance(value, dict | list | tuple):
        result = value
    elif pd.isna(value):
        result = None
    elif isinstance(value, pd.Timestamp | datetime):
        result = _format_nzt(value)
    elif hasattr(value, "item"):
        result = _json_safe_scalar(value.item())
    elif isinstance(value, float):
        result = round(value, 6)
    return result


def _first_record(df: pd.DataFrame, columns: list[str]) -> dict:
    if df.empty:
        return {}
    return {column: _json_safe_scalar(df.iloc[0].get(column)) for column in columns}


def _dataframe_records(
    df: pd.DataFrame,
    columns: list[str],
    limit: int,
) -> list[dict]:
    if df.empty:
        return []

    available_columns = [column for column in columns if column in df.columns]
    display_df = df[available_columns].head(limit)
    return [
        {column: _json_safe_scalar(row[column]) for column in available_columns}
        for _, row in display_df.iterrows()
    ]


def _build_profile_stats(stats_df: pd.DataFrame) -> dict:
    stats = {}
    columns = [
        "row_count",
        "non_null_count",
        "null_count",
        "null_rate",
        "mean_value",
        "stddev_value",
        "min_value",
        "max_value",
        "p1",
        "p5",
        "p50",
        "p95",
        "p99",
    ]
    if stats_df.empty or "period" not in stats_df.columns:
        return stats

    for period in ("baseline", "recent"):
        period_rows = stats_df.loc[stats_df["period"] == period]
        if period_rows.empty:
            continue
        row = period_rows.iloc[0]
        stats[period] = {
            column: _json_safe_scalar(row[column])
            for column in columns
            if column in stats_df.columns
        }
    return stats


def _build_percentile_shift(stats: dict) -> dict:
    baseline = stats.get("baseline", {})
    recent = stats.get("recent", {})
    shifts = {}
    for percentile in ("p1", "p50", "p99"):
        baseline_value = baseline.get(percentile)
        recent_value = recent.get(percentile)
        if baseline_value is None or recent_value is None:
            shifts[percentile] = None
        else:
            shifts[percentile] = round(float(recent_value) - float(baseline_value), 6)
    return shifts


def _build_density_distribution_summary(histogram_df: pd.DataFrame) -> dict:
    if histogram_df.empty or "value_count" not in histogram_df.columns:
        return {"bin_count": 0, "total_count": 0, "top_bins": []}

    total_count = histogram_df["value_count"].sum()
    histogram = histogram_df.copy()
    histogram["density"] = 0.0 if total_count <= 0 else histogram["value_count"] / total_count
    top_bins = histogram.sort_values("value_count", ascending=False).head(MAX_DISTRIBUTION_BINS)

    return {
        "bin_count": int(len(histogram_df)),
        "total_count": _json_safe_scalar(total_count),
        "top_bins": _dataframe_records(
            top_bins,
            ["bin_center", "value_count", "density"],
            MAX_DISTRIBUTION_BINS,
        ),
    }


def _build_daily_trend_summary(daily_df: pd.DataFrame) -> dict:
    if daily_df.empty:
        return {"day_count": 0}

    sorted_df = daily_df.sort_values("profile_date") if "profile_date" in daily_df else daily_df
    summary = {
        "day_count": int(len(sorted_df)),
        "latest_day": _first_record(
            sorted_df.tail(1),
            [
                "profile_date",
                "row_count",
                "non_null_count",
                "null_count",
                "null_rate",
                "p1",
                "p50",
                "p99",
            ],
        ),
    }
    for column in ("p1", "p50", "p99", "null_rate"):
        if column not in sorted_df.columns:
            continue
        values = pd.to_numeric(sorted_df[column], errors="coerce").dropna()
        if values.empty:
            continue
        summary[f"min_{column}"] = _json_safe_scalar(values.min())
        summary[f"max_{column}"] = _json_safe_scalar(values.max())
    return summary


def _build_outlier_threshold_context(
    outlier_thresholds: tuple[float, float] | None,
    incident_rows: pd.DataFrame | None = None,
) -> dict | None:
    context = _extract_outlier_threshold_context_from_logs(incident_rows)

    if outlier_thresholds is None:
        return context or None

    lower_threshold, upper_threshold = outlier_thresholds
    context.setdefault("lower_threshold", _json_safe_threshold_number(lower_threshold))
    context.setdefault("upper_threshold", _json_safe_threshold_number(upper_threshold))
    return context


def _extract_outlier_threshold_context_from_logs(
    incident_rows: pd.DataFrame | None,
) -> dict:
    windows = _extract_outlier_threshold_windows_from_logs(incident_rows)
    if not windows:
        return {}

    return {
        key: value
        for key, value in windows[-1].items()
        if key
        in {
            "recent_min",
            "recent_max",
            "history_p1",
            "history_p99",
            "lower_threshold",
            "upper_threshold",
        }
    }


def _extract_outlier_threshold_windows_from_logs(
    incident_rows: pd.DataFrame | None,
) -> list[dict]:
    if incident_rows is None or incident_rows.empty:
        return []
    if "observed_value" not in incident_rows.columns:
        return []

    log_rows = incident_rows.dropna(subset=["observed_value"])
    if log_rows.empty:
        return []
    if "window_start" in log_rows.columns:
        log_rows = log_rows.sort_values("window_start")

    windows = []
    for row in log_rows.to_dict("records"):
        try:
            payload = json.loads(row.get("observed_value"))
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue

        threshold_context = {
            key: _json_safe_scalar(row[key])
            for key in ("log_run_id", "window_start", "window_end")
            if key in row and _json_safe_scalar(row[key]) is not None
        }
        for key in (
            "recent_min",
            "recent_max",
            "history_p1",
            "history_p99",
            "lower_threshold",
            "upper_threshold",
        ):
            if key in payload:
                threshold_context[key] = _json_safe_threshold_number(payload[key])
        if any(
            key in threshold_context
            for key in (
                "recent_min",
                "recent_max",
                "history_p1",
                "history_p99",
                "lower_threshold",
                "upper_threshold",
            )
        ):
            windows.append(threshold_context)
    return windows


def _json_safe_threshold_number(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return _json_safe_scalar(value)


def _build_raw_context_summary(
    context_df: pd.DataFrame | None,
    tag: str,
    incident_start: datetime,
    incident_end: datetime,
) -> dict:
    if context_df is None or context_df.empty or tag not in context_df.columns:
        return {"row_count": 0}

    raw_df = pd.DataFrame(
        {
            "timestamp": _to_utc_series(context_df["Pi_Timestamp"]),
            "value": pd.to_numeric(context_df[tag], errors="coerce"),
        }
    ).dropna(subset=["value"])
    if raw_df.empty:
        return {"row_count": 0}

    raw_df = raw_df.sort_values("timestamp")
    incident_start_utc = _to_utc_timestamp(incident_start)
    incident_end_utc = _to_utc_timestamp(incident_end)
    incident_df = raw_df.loc[
        (raw_df["timestamp"] >= incident_start_utc) & (raw_df["timestamp"] <= incident_end_utc)
    ]

    return {
        "row_count": int(len(raw_df)),
        "first_timestamp_nzt": _format_nzt(raw_df.iloc[0]["timestamp"]),
        "last_timestamp_nzt": _format_nzt(raw_df.iloc[-1]["timestamp"]),
        "overall_window": _numeric_summary(raw_df["value"]),
        "incident_window": _numeric_summary(incident_df["value"]),
        "latest_value": _json_safe_scalar(raw_df.iloc[-1]["value"]),
    }


def _numeric_summary(values: pd.Series) -> dict:
    clean_values = pd.to_numeric(values, errors="coerce").dropna()
    if clean_values.empty:
        return {}
    return {
        "min_value": _json_safe_scalar(clean_values.min()),
        "max_value": _json_safe_scalar(clean_values.max()),
        "mean_value": _json_safe_scalar(clean_values.mean()),
    }
