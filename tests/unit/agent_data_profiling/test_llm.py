import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd


APP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_ROOT))

from agent_data_profiling.llm import (  # noqa: E402
    DEFAULT_MAX_TOKENS,
    DEFAULT_REASONING_EFFORT,
    AiGatewayConfig,
    build_incident_llm_context,
    build_incident_llm_messages,
    build_tag_profile_llm_context,
    build_tag_profile_llm_messages,
    get_ai_gateway_config_from_env,
    load_llm_prompt_config,
    query_ai_gateway,
)


class _FakeGatewayResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_get_ai_gateway_config_from_env_builds_default_gateway_base_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_HOST", "https://example.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_AI_GATEWAY_ENDPOINT", "agent-data-profiling")

    config = get_ai_gateway_config_from_env()

    assert config.endpoint_name == "agent-data-profiling"
    assert config.base_url == "https://example.cloud.databricks.com/ai-gateway/mlflow/v1"


def test_get_ai_gateway_config_from_env_adds_https_to_hostname(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_HOST", "example.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_AI_GATEWAY_ENDPOINT", "agent-data-profiling")

    config = get_ai_gateway_config_from_env()

    assert config.base_url == "https://example.cloud.databricks.com/ai-gateway/mlflow/v1"


def test_query_ai_gateway_posts_chat_completion_payload() -> None:
    requests = []

    def _fake_post(url, headers, json, timeout):
        requests.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return _FakeGatewayResponse(
            {"choices": [{"message": {"content": "Profile summary"}}]},
        )

    config = AiGatewayConfig(
        endpoint_name="agent-data-profiling",
        base_url="https://example.cloud.databricks.com/ai-gateway/mlflow/v1",
        max_tokens=500,
        timeout_seconds=30,
    )

    content = query_ai_gateway(
        config,
        messages=[{"role": "user", "content": "Summarise this profile."}],
        access_token_provider=lambda: "oauth-token",
        post=_fake_post,
        request_tags={"feature": "tag_profiling", "tag": "Net_Power"},
    )

    assert content == "Profile summary"
    assert requests == [
        {
            "url": "https://example.cloud.databricks.com/ai-gateway/mlflow/v1/chat/completions",
            "headers": {
                "Authorization": "Bearer oauth-token",
                "Content-Type": "application/json",
                "Databricks-Ai-Gateway-Request-Tags": (
                    '{"feature": "tag_profiling", "tag": "Net_Power"}'
                ),
            },
            "json": {
                "model": "agent-data-profiling",
                "messages": [{"role": "user", "content": "Summarise this profile."}],
                "max_tokens": 500,
                "reasoning_effort": "none",
            },
            "timeout": 30,
        }
    ]


def test_default_ai_gateway_max_tokens_leaves_room_for_gpt_reasoning() -> None:
    assert DEFAULT_MAX_TOKENS == 2048


def test_default_ai_gateway_reasoning_effort_disables_hidden_reasoning() -> None:
    assert DEFAULT_REASONING_EFFORT == "none"


def test_query_ai_gateway_empty_content_error_includes_response_metadata() -> None:
    def _fake_post(url, headers, json, timeout):
        assert url
        assert headers
        assert json
        assert timeout
        return _FakeGatewayResponse(
            {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": ""},
                    }
                ],
                "usage": {
                    "completion_tokens": 900,
                    "completion_tokens_details": {"reasoning_tokens": 900},
                },
            }
        )

    config = AiGatewayConfig(
        endpoint_name="agent-data-profiling",
        base_url="https://example.cloud.databricks.com/ai-gateway/mlflow/v1",
    )

    try:
        query_ai_gateway(
            config,
            messages=[{"role": "user", "content": "Summarise this profile."}],
            access_token_provider=lambda: "oauth-token",
            post=_fake_post,
        )
    except ValueError as exc:
        assert "AI Gateway response content was empty" in str(exc)
        assert "finish_reason=length" in str(exc)
        assert "reasoning_tokens" in str(exc)
    else:
        raise AssertionError("Expected empty AI Gateway content to fail")


def test_build_tag_profile_llm_context_summarises_profile_frames() -> None:
    profile_result = {
        "stats": pd.DataFrame(
            [
                {
                    "period": "baseline",
                    "row_count": 100,
                    "non_null_count": 98,
                    "null_count": 2,
                    "null_rate": 0.02,
                    "mean_value": 90.0,
                    "stddev_value": 4.0,
                    "min_value": 75.0,
                    "max_value": 110.0,
                    "p1": 80.0,
                    "p50": 91.0,
                    "p99": 105.0,
                },
                {
                    "period": "recent",
                    "row_count": 10,
                    "non_null_count": 10,
                    "null_count": 0,
                    "null_rate": 0.0,
                    "mean_value": 94.0,
                    "stddev_value": 2.0,
                    "min_value": 90.0,
                    "max_value": 98.0,
                    "p1": 90.0,
                    "p50": 95.0,
                    "p99": 98.0,
                },
            ]
        ),
        "histogram": pd.DataFrame(
            {
                "bin_center": [80.0, 90.0, 100.0],
                "value_count": [10, 70, 20],
            }
        ),
        "daily_trend": pd.DataFrame(
            {
                "profile_date": pd.to_datetime(["2026-05-12", "2026-05-13"]),
                "row_count": [48, 48],
                "null_rate": [0.0, 0.05],
                "p1": [83.0, 84.0],
                "p50": [90.0, 92.0],
                "p99": [104.0, 106.0],
            }
        ),
        "gap": pd.DataFrame(
            {
                "interval_count": [99],
                "large_gap_count": [2],
                "average_gap_minutes": [10.0],
                "longest_gap_minutes": [45.0],
            }
        ),
    }

    context = build_tag_profile_llm_context(
        tag="Net_Power",
        profile_result=profile_result,
        recent_start_time=datetime(2026, 5, 6, tzinfo=UTC),
        recent_end_time=datetime(2026, 5, 13, tzinfo=UTC),
        baseline_start_time=datetime(2025, 11, 11, tzinfo=UTC),
        baseline_end_time=datetime(2026, 5, 13, tzinfo=UTC),
    )

    assert context["tag"]["name"] == "Net_Power"
    assert context["stats"]["recent"]["p50"] == 95.0
    assert context["percentile_shift"]["p50"] == 4.0
    assert context["density_distribution"]["top_bins"][0] == {
        "bin_center": 90.0,
        "value_count": 70,
        "density": 0.7,
    }
    assert context["daily_trend"]["latest_day"]["p99"] == 106.0
    assert context["gap_profile"]["large_gap_count"] == 2


def test_build_tag_profile_llm_messages_accepts_decimal_values() -> None:
    context = {
        "analysis_type": "tag_profile",
        "stats": {
            "baseline": {
                "p50": Decimal("91.25"),
            },
        },
    }

    messages = build_tag_profile_llm_messages(context)

    assert '"p50": 91.25' in messages[1]["content"]


def _write_prompt_pack(prompt_dir: Path) -> None:
    prompt_dir.mkdir()
    (prompt_dir / "station_context.md").write_text(
        "KAG station context from config",
        encoding="utf-8",
    )
    (prompt_dir / "tag_profile_system.md").write_text(
        "Profile system prompt: {station_context}",
        encoding="utf-8",
    )
    (prompt_dir / "tag_profile_user.md").write_text(
        "Profile user prompt: {context_json}",
        encoding="utf-8",
    )
    (prompt_dir / "incident_system.md").write_text(
        "Incident system prompt: {station_context}",
        encoding="utf-8",
    )
    (prompt_dir / "incident_user.md").write_text(
        "Incident user prompt: {context_json}",
        encoding="utf-8",
    )


def test_build_tag_profile_llm_messages_reads_external_prompt_pack(
    tmp_path,
    monkeypatch,
) -> None:
    prompt_dir = tmp_path / "prompts"
    _write_prompt_pack(prompt_dir)
    monkeypatch.setenv("AGENT_DATA_PROFILING_LLM_PROMPT_DIR", str(prompt_dir))

    messages = build_tag_profile_llm_messages({"analysis_type": "tag_profile"})

    assert messages[0]["content"] == "Profile system prompt: KAG station context from config"
    assert messages[1]["content"] == 'Profile user prompt: {"analysis_type": "tag_profile"}'


def test_build_incident_llm_messages_reads_external_prompt_pack(
    tmp_path,
    monkeypatch,
) -> None:
    prompt_dir = tmp_path / "prompts"
    _write_prompt_pack(prompt_dir)
    monkeypatch.setenv("AGENT_DATA_PROFILING_LLM_PROMPT_DIR", str(prompt_dir))

    messages = build_incident_llm_messages({"analysis_type": "data_quality_incident"})

    assert messages[0]["content"] == "Incident system prompt: KAG station context from config"
    assert messages[1]["content"] == (
        'Incident user prompt: {"analysis_type": "data_quality_incident"}'
    )


def test_load_llm_prompt_config_fails_when_required_prompt_file_is_missing(tmp_path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "station_context.md").write_text(
        "KAG station context from config",
        encoding="utf-8",
    )

    try:
        load_llm_prompt_config(prompt_dir)
    except RuntimeError as exc:
        assert "tag_profile_system.md" in str(exc)
    else:
        raise AssertionError("Expected incomplete prompt config to fail")


def test_prompt_templates_allow_literal_braces(
    tmp_path,
    monkeypatch,
) -> None:
    prompt_dir = tmp_path / "prompts"
    _write_prompt_pack(prompt_dir)
    (prompt_dir / "tag_profile_user.md").write_text(
        'Return JSON like {"summary": "..."} before {context_json}',
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_DATA_PROFILING_LLM_PROMPT_DIR", str(prompt_dir))

    messages = build_tag_profile_llm_messages({"analysis_type": "tag_profile"})

    assert messages[1]["content"] == (
        'Return JSON like {"summary": "..."} before {"analysis_type": "tag_profile"}'
    )


def test_default_prompt_pack_includes_kag_process_context() -> None:
    prompt_config = load_llm_prompt_config()

    assert "HP_TURBINE_STEAM_FLOW" in prompt_config.station_context
    assert "Condenser_Pressure_A" in prompt_config.station_context
    assert "Gross_Generator_Output" in prompt_config.station_context


def test_default_ai_prompts_keep_output_focused_on_hypotheses_and_checks() -> None:
    prompt_config = load_llm_prompt_config()

    for prompt_text in (
        prompt_config.incident_system,
        prompt_config.tag_profile_system,
    ):
        assert "Summary: 1-2 sentences" in prompt_text
        assert "Process-aware hypotheses" in prompt_text
        assert "Recommended next checks" in prompt_text
        assert "only the most important" in prompt_text
        assert "Evidence from supplied data" not in prompt_text
        assert "Data quality assessment" not in prompt_text
        assert "Confidence and missing context" not in prompt_text
        assert "2 bullets" not in prompt_text
        assert "3 bullets" not in prompt_text


def test_build_incident_llm_context_summarises_logs_and_raw_context() -> None:
    incident_rows = pd.DataFrame(
        {
            "incident_id": ["incident-1", "incident-1"],
            "station": ["KAG", "KAG"],
            "source_table": ["raw.pi.geothermal_kag_streaming", "raw.pi.geothermal_kag_streaming"],
            "tag_name": ["Net_Power", "Net_Power"],
            "rule_type": ["outlier", "outlier"],
            "status": ["failed", "failed"],
            "incident_start": pd.to_datetime(["2026-05-12 10:00", "2026-05-12 10:00"]),
            "incident_end": pd.to_datetime(["2026-05-12 10:30", "2026-05-12 10:30"]),
            "log_run_id": ["run-1", "run-2"],
            "window_start": pd.to_datetime(["2026-05-12 10:00", "2026-05-12 10:15"]),
            "window_end": pd.to_datetime(["2026-05-12 10:15", "2026-05-12 10:30"]),
            "observed_value": ["95.0", "120.0"],
            "log_create_ts": pd.to_datetime(["2026-05-12 10:20", "2026-05-12 10:35"]),
        }
    )
    context_df = pd.DataFrame(
        {
            "Pi_Timestamp": pd.to_datetime(
                [
                    "2026-05-12 09:00",
                    "2026-05-12 10:00",
                    "2026-05-12 10:15",
                    "2026-05-12 11:00",
                ]
            ),
            "Net_Power": [90.0, 95.0, 120.0, 93.0],
        }
    )

    context = build_incident_llm_context(
        incident_id="incident-1",
        incident_rows=incident_rows,
        context_df=context_df,
        tag="Net_Power",
        incident_start=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        incident_end=datetime(2026, 5, 12, 10, 30, tzinfo=UTC),
        outlier_thresholds=(80.0, 110.0),
    )

    assert context["incident"]["incident_id"] == "incident-1"
    assert context["incident"]["rule_type"] == "outlier"
    assert context["quality_log_rows"][1]["observed_value"] == "120.0"
    assert context["outlier_thresholds"] == {
        "lower_threshold": 80.0,
        "upper_threshold": 110.0,
    }
    assert context["raw_context"]["row_count"] == 4
    assert context["raw_context"]["incident_window"]["max_value"] == 120.0
    assert context["raw_context"]["overall_window"]["mean_value"] == 99.5
