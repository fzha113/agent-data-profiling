import sys
from pathlib import Path

import pandas as pd


APP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_ROOT))

import app as app_module  # noqa: E402
from agent_data_profiling.comparison import (  # noqa: E402
    build_comparison_frame,
    build_scatter_comparison_frame,
    get_comparison_plot_mode,
    validate_xy_tags,
)
from app import (  # noqa: E402
    APP_SECTIONS,
    COMPARISON_RESULT_STATE_KEY,
    DEFAULT_SECTION,
    PROFILING_DEFAULT_TAGS,
    PROFILING_END_DATE_WIDGET_KEY,
    PROFILING_RESULT_STATE_KEY,
    PROFILING_START_DATE_WIDGET_KEY,
    PROFILING_TAGS_WIDGET_KEY,
    QUALITY_GRID_VERSION_STATE_KEY,
    QUALITY_INCIDENTS_SECTION,
    QUALITY_RESULT_STATE_KEY,
    TAG_PROFILING_SECTION,
    build_density_distribution_frame,
    build_quality_incident_summary,
    format_period_label,
    format_profile_window_caption,
    get_latest_outlier_thresholds,
    get_profiling_request_signature,
    get_selected_incident_id_from_grid_response,
)


class _SegmentedControlNavigationStub:
    def __init__(self, selected_section: str | None) -> None:
        self.selected_section = selected_section

    def segmented_control(
        self,
        label,
        options,
        selection_mode="single",
        default=None,
        key=None,
        label_visibility="visible",
    ) -> str | None:
        assert label == "Section"
        assert options == APP_SECTIONS
        assert selection_mode == "single"
        assert default == DEFAULT_SECTION
        assert key == "app_section"
        assert label_visibility == "collapsed"
        return self.selected_section


class _RadioNavigationFallbackStub:
    def __init__(self, selected_section: str | None) -> None:
        self.selected_section = selected_section

    def radio(
        self,
        label,
        options,
        index=0,
        horizontal=False,
        label_visibility="visible",
        key=None,
    ) -> str | None:
        assert label == "Section"
        assert options == APP_SECTIONS
        assert index == 0
        assert horizontal is True
        assert label_visibility == "collapsed"
        assert key == "app_section"
        return self.selected_section


class _ProfilingSidebar:
    def __init__(self) -> None:
        self.button_labels = []

    def header(self, _message) -> None:
        pass

    def caption(self, _message) -> None:
        pass

    def subheader(self, _message) -> None:
        pass

    def multiselect(self, *_args, **kwargs):
        assert kwargs["key"] == PROFILING_TAGS_WIDGET_KEY
        return ["Net_Power"]

    def date_input(self, label, value, **_kwargs):
        if label == "Start date":
            return value
        if label == "End date":
            return value
        raise AssertionError(f"Unexpected date input: {label}")

    def button(self, label, **_kwargs):
        self.button_labels.append(label)
        return False


class _ProfilingSidebarStub:
    def __init__(self) -> None:
        self.sidebar = _ProfilingSidebar()


def test_data_quality_incidents_is_the_default_app_section() -> None:
    assert APP_SECTIONS[0] == QUALITY_INCIDENTS_SECTION
    assert DEFAULT_SECTION == QUALITY_INCIDENTS_SECTION


def test_tag_profiling_defaults_to_net_power() -> None:
    assert PROFILING_DEFAULT_TAGS == ("Net_Power",)


def test_render_profiling_sidebar_uses_refresh_button(monkeypatch) -> None:
    stub = _ProfilingSidebarStub()
    monkeypatch.setattr(app_module, "st", stub)

    app_module.render_profiling_sidebar()

    assert stub.sidebar.button_labels == ["Refresh"]


def test_render_section_navigation_uses_streamlit_segmented_control(
    monkeypatch,
) -> None:
    monkeypatch.setattr(app_module, "st", _SegmentedControlNavigationStub("Compare tags"))

    selected_section = app_module.render_section_navigation()

    assert selected_section == "Compare tags"


def test_render_section_navigation_falls_back_to_radio_without_segmented_control(
    monkeypatch,
) -> None:
    monkeypatch.setattr(app_module, "st", _RadioNavigationFallbackStub("Tag profiling"))

    selected_section = app_module.render_section_navigation()

    assert selected_section == "Tag profiling"


def test_render_section_navigation_radio_fallback_uses_session_section(monkeypatch) -> None:
    class _SessionRadioNavigationStub:
        session_state = {"app_section": TAG_PROFILING_SECTION}

        def radio(
            self,
            label,
            options,
            index=0,
            horizontal=False,
            label_visibility="visible",
            key=None,
        ) -> str | None:
            assert label == "Section"
            assert options == APP_SECTIONS
            assert index == 1
            assert horizontal is True
            assert label_visibility == "collapsed"
            assert key == "app_section"
            return self.session_state[key]

    monkeypatch.setattr(app_module, "st", _SessionRadioNavigationStub())

    selected_section = app_module.render_section_navigation()

    assert selected_section == TAG_PROFILING_SECTION


def test_render_section_navigation_defaults_when_no_section_is_selected(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "st", _SegmentedControlNavigationStub(None))

    selected_section = app_module.render_section_navigation()

    assert selected_section == QUALITY_INCIDENTS_SECTION


def test_format_period_label_displays_nzt_time() -> None:
    start_time = pd.Timestamp("2026-05-12 12:00", tz="UTC").to_pydatetime()
    end_time = pd.Timestamp("2026-05-12 13:00", tz="UTC").to_pydatetime()

    period_label = format_period_label(start_time, end_time)

    assert period_label == "2026-05-13 00:00 NZT to 2026-05-13 01:00 NZT"


def test_build_density_distribution_frame_converts_count_to_proportion() -> None:
    histogram_df = pd.DataFrame(
        {
            "bin_center": [1.0, 2.0, 3.0],
            "value_count": [2, 3, 5],
        }
    )

    density_df = build_density_distribution_frame(histogram_df)

    assert density_df["density"].to_list() == [0.2, 0.3, 0.5]


def test_format_profile_window_caption_describes_recent_and_baseline_windows() -> None:
    recent_start = pd.Timestamp("2026-05-06 12:00", tz="UTC").to_pydatetime()
    recent_end = pd.Timestamp("2026-05-13 12:00", tz="UTC").to_pydatetime()
    baseline_start = pd.Timestamp("2025-11-11 12:00", tz="UTC").to_pydatetime()
    baseline_end = recent_end

    caption = format_profile_window_caption(
        recent_start,
        recent_end,
        baseline_start,
        baseline_end,
    )

    assert "Recent: 2026-05-07 00:00 NZT to 2026-05-14 00:00 NZT (7 days)" in caption
    assert "Baseline: 2025-11-12 01:00 NZT to 2026-05-14 00:00 NZT (183 days)" in caption


def test_build_quality_incident_summary_orders_recent_updates_first() -> None:
    df = pd.DataFrame(
        {
            "incident_id": ["older", "newer", "newer"],
            "tag_name": ["Net_Power", "Gross_Generator_Output", "Gross_Generator_Output"],
            "rule_type": ["outlier", "stuck_value", "stuck_value"],
            "status": ["failed", "failed", "failed"],
            "incident_start": pd.to_datetime(
                ["2026-05-08 10:00", "2026-05-09 09:00", "2026-05-09 09:00"]
            ),
            "incident_end": pd.to_datetime(
                ["2026-05-08 10:30", "2026-05-09 10:00", "2026-05-09 10:00"]
            ),
            "incident_update_ts": pd.to_datetime(
                ["2026-05-08 10:35", "2026-05-09 10:05", "2026-05-09 10:05"]
            ),
            "log_run_id": ["run-1", "run-2", "run-3"],
            "feedback_count": [None, 1, 1],
            "latest_feedback_ts": pd.to_datetime([None, "2026-05-09 10:30", "2026-05-09 10:30"]),
        }
    )

    summary_df = build_quality_incident_summary(df)

    assert summary_df["incident_id"].to_list() == ["newer", "older"]
    assert summary_df["failed_windows"].to_list() == [2, 1]
    assert summary_df["duration_minutes"].to_list() == [60.0, 30.0]
    assert summary_df["review_status"].to_list() == ["Commented", "Open"]


def test_get_selected_incident_id_from_grid_response_reads_first_selected_row() -> None:
    grid_response = {
        "selected_rows": [
            {"incident_id": "incident-123", "tag_name": "Net_Power"},
        ]
    }

    selected_incident_id = get_selected_incident_id_from_grid_response(grid_response)

    assert selected_incident_id == "incident-123"


def test_get_selected_incident_id_from_grid_response_handles_empty_selection() -> None:
    assert get_selected_incident_id_from_grid_response({"selected_rows": []}) is None
    assert get_selected_incident_id_from_grid_response({}) is None


def test_render_quality_incident_result_opens_selected_grid_row_in_dialog(
    monkeypatch,
) -> None:
    class _QualityConfig:
        monitor_catalog = "generation"
        monitor_schema = "geothermal"

    quality_config = _QualityConfig()
    df = pd.DataFrame(
        {
            "incident_id": ["incident-older", "incident-newer"],
            "tag_name": ["Net_Power", "Gross_Generator_Output"],
            "rule_type": ["outlier", "stuck_value"],
            "status": ["failed", "failed"],
            "incident_start": pd.to_datetime(["2026-05-08 10:00", "2026-05-09 09:00"]),
            "incident_end": pd.to_datetime(["2026-05-08 10:30", "2026-05-09 10:00"]),
            "incident_update_ts": pd.to_datetime(["2026-05-08 10:35", "2026-05-09 10:05"]),
            "log_run_id": ["run-1", "run-2"],
            "feedback_count": [None, 1],
            "latest_feedback_ts": pd.to_datetime([None, "2026-05-09 10:30"]),
        }
    )
    calls = []

    class _QualityResultStub:
        def columns(self, count):
            class _MetricColumn:
                def metric(self, *_args, **_kwargs) -> None:
                    pass

            return [_MetricColumn() for _ in range(count)]

        def caption(self, message) -> None:
            calls.append(("caption", message))

    monkeypatch.setattr(app_module, "st", _QualityResultStub())
    monkeypatch.setattr(
        app_module,
        "render_incident_summary_grid",
        lambda summary_df: summary_df.iloc[0]["incident_id"],
    )
    monkeypatch.setattr(
        app_module,
        "render_quality_incident_dialog",
        lambda incident_id, incident_rows, config: calls.append(
            ("dialog", incident_id, incident_rows["incident_id"].unique().tolist(), config)
        ),
    )

    app_module.render_quality_incident_result(
        {
            "quality_config": quality_config,
            "since_time": pd.Timestamp("2026-05-01 00:00").to_pydatetime(),
            "df": df,
        }
    )

    assert calls[-1] == ("dialog", "incident-newer", ["incident-newer"], quality_config)


def test_get_latest_outlier_thresholds_reads_latest_quality_log_row() -> None:
    incident_rows = pd.DataFrame(
        {
            "rule_type": ["outlier", "outlier"],
            "window_start": pd.to_datetime(["2026-05-08 10:00", "2026-05-08 10:15"]),
            "observed_value": [
                '{"lower_threshold": 10.0, "upper_threshold": 20.0}',
                '{"lower_threshold": 12.5, "upper_threshold": 22.5}',
            ],
        }
    )

    thresholds = get_latest_outlier_thresholds(incident_rows)

    assert thresholds == (12.5, 22.5)


def test_get_latest_outlier_thresholds_returns_none_for_non_outlier_rule() -> None:
    incident_rows = pd.DataFrame(
        {
            "rule_type": ["stuck_value"],
            "window_start": pd.to_datetime(["2026-05-08 10:00"]),
            "observed_value": ['{"lower_threshold": 10.0, "upper_threshold": 20.0}'],
        }
    )

    thresholds = get_latest_outlier_thresholds(incident_rows)

    assert thresholds is None


def test_render_profiling_section_reuses_stored_result_without_plot_button(
    monkeypatch,
) -> None:
    start_time = pd.Timestamp("2026-05-08 00:00").to_pydatetime()
    end_time = pd.Timestamp("2026-05-09 00:00").to_pydatetime()
    stored_result = {
        "df": pd.DataFrame({"Pi_Timestamp": [], "Net_Power": []}),
        "request_signature": get_profiling_request_signature(
            ["Net_Power"],
            start_time,
            end_time,
        ),
    }
    calls = []

    class _ProfilingStateStub:
        session_state = {PROFILING_RESULT_STATE_KEY: stored_result}

        def info(self, message) -> None:
            calls.append(("info", message))

    monkeypatch.setattr(app_module, "st", _ProfilingStateStub())
    monkeypatch.setattr(
        app_module,
        "load_profiling_result",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("profiling data should not reload")
        ),
    )
    monkeypatch.setattr(
        app_module,
        "render_profiling_result",
        lambda result: calls.append(("render", result)),
    )

    app_module.render_profiling_section(
        ["Net_Power"],
        start_time,
        end_time,
        run_query=False,
    )

    assert calls == [("render", stored_result)]


def test_render_profiling_section_auto_loads_without_stored_result(
    monkeypatch,
) -> None:
    loaded_result = {"df": pd.DataFrame({"Pi_Timestamp": [], "Net_Power": []})}
    calls = []

    class _ProfilingStateStub:
        session_state = {}

        def info(self, message) -> None:
            calls.append(("info", message))

    monkeypatch.setattr(app_module, "st", _ProfilingStateStub())
    monkeypatch.setattr(
        app_module,
        "load_profiling_result",
        lambda *_args, **_kwargs: loaded_result,
    )
    monkeypatch.setattr(
        app_module,
        "render_profiling_result",
        lambda result: calls.append(("render", result)),
    )

    app_module.render_profiling_section(
        ["Net_Power"],
        pd.Timestamp("2026-05-08 00:00").to_pydatetime(),
        pd.Timestamp("2026-05-09 00:00").to_pydatetime(),
        run_query=False,
    )

    assert app_module.st.session_state[PROFILING_RESULT_STATE_KEY] == loaded_result
    assert calls == [("render", loaded_result)]


def test_render_profiling_section_does_not_render_stale_result_when_reload_fails(
    monkeypatch,
) -> None:
    old_start_time = pd.Timestamp("2026-05-08 00:00").to_pydatetime()
    old_end_time = pd.Timestamp("2026-05-09 00:00").to_pydatetime()
    new_start_time = pd.Timestamp("2026-05-10 00:00").to_pydatetime()
    new_end_time = pd.Timestamp("2026-05-11 00:00").to_pydatetime()
    stored_result = {
        "df": pd.DataFrame({"Pi_Timestamp": [], "Net_Power": []}),
        "request_signature": get_profiling_request_signature(
            ["Net_Power"],
            old_start_time,
            old_end_time,
        ),
    }
    calls = []

    class _ProfilingStateStub:
        session_state = {PROFILING_RESULT_STATE_KEY: stored_result}

        def info(self, message) -> None:
            calls.append(("info", message))

    monkeypatch.setattr(app_module, "st", _ProfilingStateStub())
    monkeypatch.setattr(app_module, "load_profiling_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        app_module,
        "render_profiling_result",
        lambda result: calls.append(("render", result)),
    )

    app_module.render_profiling_section(
        ["Net_Power"],
        new_start_time,
        new_end_time,
        run_query=False,
    )

    assert calls == []


def test_open_tag_profiling_detail_selects_tag_and_switches_section(monkeypatch) -> None:
    class _DetailNavigationStub:
        session_state = {
            PROFILING_RESULT_STATE_KEY: {"old": "result"},
            QUALITY_GRID_VERSION_STATE_KEY: 3,
        }

    monkeypatch.setattr(app_module, "st", _DetailNavigationStub())

    app_module.open_tag_profiling_detail("Net_Power")

    assert app_module.st.session_state["app_section"] == TAG_PROFILING_SECTION
    assert app_module.st.session_state[PROFILING_TAGS_WIDGET_KEY] == ["Net_Power"]
    assert PROFILING_START_DATE_WIDGET_KEY in app_module.st.session_state
    assert PROFILING_END_DATE_WIDGET_KEY in app_module.st.session_state
    assert PROFILING_RESULT_STATE_KEY not in app_module.st.session_state
    assert app_module.st.session_state[QUALITY_GRID_VERSION_STATE_KEY] == 4


def test_render_view_profile_button_switches_section_and_reruns_app(monkeypatch) -> None:
    calls = []

    class _ViewDetailsStub:
        session_state = {
            PROFILING_RESULT_STATE_KEY: {"old": "result"},
            QUALITY_GRID_VERSION_STATE_KEY: 1,
        }

        def button(self, label, **kwargs):
            calls.append(("button", label, kwargs))
            return True

        def rerun(self, **kwargs) -> None:
            calls.append(("rerun", kwargs))

    monkeypatch.setattr(app_module, "st", _ViewDetailsStub())

    app_module.render_view_profile_button("incident-1", "Net_Power")

    assert app_module.st.session_state["app_section"] == TAG_PROFILING_SECTION
    assert app_module.st.session_state[PROFILING_TAGS_WIDGET_KEY] == ["Net_Power"]
    assert app_module.st.session_state[QUALITY_GRID_VERSION_STATE_KEY] == 2
    assert calls[-1] == ("rerun", {"scope": "app"})


def test_load_profiling_result_loads_profile_summary_for_each_selected_tag(
    monkeypatch,
) -> None:
    class _Config:
        stream_catalog_raw = "raw"
        source_schema = "pi"
        source_table = "geothermal_kag_streaming"

    raw_df = pd.DataFrame(
        {
            "Pi_Timestamp": pd.to_datetime(["2026-05-08 00:00"]),
            "Net_Power": [95.0],
            "Gross_Generator_Output": [101.0],
        }
    )
    loaded_profiles = []

    def _load_tag_history_for_ui(**_kwargs):
        return _Config(), raw_df

    monkeypatch.setattr(
        app_module,
        "load_tag_history_for_ui",
        _load_tag_history_for_ui,
    )

    def _load_tag_profile_for_ui(
        tag, baseline_start_time, baseline_end_time, recent_start_time, recent_end_time
    ):
        loaded_profiles.append(
            (
                tag,
                baseline_start_time,
                baseline_end_time,
                recent_start_time,
                recent_end_time,
            )
        )
        return {"tag": tag}

    monkeypatch.setattr(
        app_module,
        "load_tag_profile_for_ui",
        _load_tag_profile_for_ui,
    )

    start_time = pd.Timestamp("2026-05-08 00:00", tz="UTC").to_pydatetime()
    end_time = pd.Timestamp("2026-05-15 00:00", tz="UTC").to_pydatetime()

    result = app_module.load_profiling_result(
        ["Net_Power", "Gross_Generator_Output"],
        start_time,
        end_time,
    )

    assert result["tag_profiles"] == {
        "Net_Power": {"tag": "Net_Power"},
        "Gross_Generator_Output": {"tag": "Gross_Generator_Output"},
    }
    assert [profile[0] for profile in loaded_profiles] == [
        "Net_Power",
        "Gross_Generator_Output",
    ]
    assert all(profile[2] == end_time for profile in loaded_profiles)
    assert all(profile[3] == start_time for profile in loaded_profiles)
    assert all(profile[4] == end_time for profile in loaded_profiles)


def test_load_llm_analysis_for_ui_queries_ai_gateway(monkeypatch) -> None:
    calls = []

    class _Spinner:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    class _LlmStateStub:
        def spinner(self, message):
            calls.append(("spinner", message))
            return _Spinner()

    gateway_config = object()
    messages = [{"role": "user", "content": "Summarise this profile."}]
    request_tags = {"feature": "tag_profiling", "tag": "Net_Power"}

    monkeypatch.setattr(app_module, "st", _LlmStateStub())
    monkeypatch.setattr(
        app_module,
        "get_ai_gateway_config_from_env",
        lambda: gateway_config,
    )

    def _query_ai_gateway(config, prompt_messages, request_tags=None):
        calls.append(("query", config, prompt_messages, request_tags))
        return "LLM analysis"

    monkeypatch.setattr(app_module, "query_ai_gateway", _query_ai_gateway)

    analysis = app_module.load_llm_analysis_for_ui(
        messages=messages,
        request_tags=request_tags,
        spinner_message="Generating AI profile summary...",
        error_message="Failed to generate AI profile summary.",
    )

    assert analysis == "LLM analysis"
    assert calls == [
        ("spinner", "Generating AI profile summary..."),
        ("query", gateway_config, messages, request_tags),
    ]


def test_render_comparison_section_reuses_stored_result_without_plot_button(
    monkeypatch,
) -> None:
    stored_result = {
        "df": pd.DataFrame(
            {
                "Pi_Timestamp": [],
                "Gross_Generator_Output": [],
                "Net_Power": [],
            }
        )
    }
    calls = []

    class _ComparisonStateStub:
        session_state = {COMPARISON_RESULT_STATE_KEY: stored_result}

        def info(self, message) -> None:
            calls.append(("info", message))

    monkeypatch.setattr(app_module, "st", _ComparisonStateStub())
    monkeypatch.setattr(
        app_module,
        "load_comparison_result",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("comparison data should not reload")
        ),
    )
    monkeypatch.setattr(
        app_module,
        "render_comparison_result",
        lambda result: calls.append(("render", result)),
    )

    app_module.render_comparison_section(
        ["Gross_Generator_Output", "Net_Power"],
        pd.Timestamp("2026-05-08 00:00").to_pydatetime(),
        pd.Timestamp("2026-05-09 00:00").to_pydatetime(),
        "Line",
        None,
        run_comparison=False,
    )

    assert calls == [("render", stored_result)]


def test_render_comparison_result_uses_stored_comparison_tags(monkeypatch) -> None:
    class _Config:
        stream_catalog_raw = "raw"
        source_schema = "pi"
        source_table = "geothermal_kag_streaming"

    result = {
        "config": _Config(),
        "df": pd.DataFrame(
            {
                "Pi_Timestamp": pd.to_datetime(["2026-05-08 00:00"]),
                "Gross_Generator_Output": [101.0],
                "Net_Power": [94.0],
            }
        ),
        "comparison_tags": ["Gross_Generator_Output", "Net_Power"],
        "comparison_start_time": pd.Timestamp("2026-05-08 00:00").to_pydatetime(),
        "comparison_end_time": pd.Timestamp("2026-05-09 00:00").to_pydatetime(),
        "comparison_plot_type": "Line",
        "comparison_colour_tag": None,
    }
    calls = []

    class _ComparisonResultStub:
        def subheader(self, message) -> None:
            calls.append(("subheader", message))

        def caption(self, message) -> None:
            calls.append(("caption", message))

    monkeypatch.setattr(app_module, "st", _ComparisonResultStub())

    def _render_comparison_plot(
        df,
        tags,
        plot_type,
        start_time,
        end_time,
        colour_tag,
    ) -> None:
        calls.append(("plot", len(df), tags, plot_type, start_time, end_time, colour_tag))

    monkeypatch.setattr(app_module, "render_comparison_plot", _render_comparison_plot)

    app_module.render_comparison_result(result)

    assert calls[1][0] == "plot"
    assert calls[1][1] == 1
    assert calls[1][2] == ["Gross_Generator_Output", "Net_Power"]


def test_render_quality_incidents_section_reuses_stored_result_without_refresh(
    monkeypatch,
) -> None:
    stored_result = {
        "quality_config": object(),
        "since_time": pd.Timestamp("2026-05-01 00:00").to_pydatetime(),
        "df": pd.DataFrame({"incident_id": ["incident-1"]}),
    }
    calls = []

    class _QualityStateStub:
        session_state = {QUALITY_RESULT_STATE_KEY: stored_result}

        def subheader(self, message) -> None:
            calls.append(("subheader", message))

        def caption(self, message) -> None:
            calls.append(("caption", message))

    monkeypatch.setattr(app_module, "st", _QualityStateStub())
    monkeypatch.setattr(
        app_module,
        "load_quality_incident_result",
        lambda: (_ for _ in ()).throw(AssertionError("quality incidents should not reload")),
    )
    monkeypatch.setattr(
        app_module,
        "render_quality_incident_result",
        lambda result: calls.append(("render", result)),
    )

    app_module.render_quality_incidents_section(refresh_incidents=False)

    assert calls[-1] == ("render", stored_result)


def test_build_comparison_frame_returns_long_format_points_with_display_names() -> None:
    df = pd.DataFrame(
        {
            "Pi_Timestamp": pd.to_datetime(["2026-05-08 00:00", "2026-05-08 01:00"]),
            "Gross_Generator_Output": [101.0, 102.0],
            "Net_Power": [94.0, 95.0],
        }
    )

    comparison_df = build_comparison_frame(
        df,
        ["Gross_Generator_Output", "Net_Power"],
    )

    assert comparison_df.to_dict("records") == [
        {
            "Pi_Timestamp": pd.Timestamp("2026-05-08 00:00"),
            "tag": "Gross_Generator_Output",
            "display_name": "Gross Generator Output",
            "value": 101.0,
        },
        {
            "Pi_Timestamp": pd.Timestamp("2026-05-08 01:00"),
            "tag": "Gross_Generator_Output",
            "display_name": "Gross Generator Output",
            "value": 102.0,
        },
        {
            "Pi_Timestamp": pd.Timestamp("2026-05-08 00:00"),
            "tag": "Net_Power",
            "display_name": "Net Power",
            "value": 94.0,
        },
        {
            "Pi_Timestamp": pd.Timestamp("2026-05-08 01:00"),
            "tag": "Net_Power",
            "display_name": "Net Power",
            "value": 95.0,
        },
    ]


def test_get_comparison_plot_mode_maps_supported_options() -> None:
    assert get_comparison_plot_mode("Line") == "line"
    assert get_comparison_plot_mode("Scatter") == "scatter"


def test_get_comparison_plot_mode_rejects_unknown_option() -> None:
    try:
        get_comparison_plot_mode("Bars")
    except ValueError as exc:
        assert "Unsupported comparison plot type" in str(exc)
    else:
        raise AssertionError("Expected unsupported plot type to fail")


def test_validate_xy_tags_accepts_exactly_two_tags() -> None:
    selected_tags = validate_xy_tags(["Gross_Generator_Output", "Net_Power"])

    assert selected_tags == ("Gross_Generator_Output", "Net_Power")


def test_validate_xy_tags_rejects_other_counts() -> None:
    try:
        validate_xy_tags(["Gross_Generator_Output"])
    except ValueError as exc:
        assert "Select exactly 2 tags" in str(exc)
    else:
        raise AssertionError("Expected one selected tag to fail")


def test_build_scatter_comparison_frame_keeps_xy_colour_and_timestamp() -> None:
    df = pd.DataFrame(
        {
            "Pi_Timestamp": pd.to_datetime(["2026-05-08 00:00", "2026-05-08 01:00"]),
            "Gross_Generator_Output": [101.0, 102.0],
            "Net_Power": [94.0, 95.0],
            "Station_Enthalpy": [1280.0, 1290.0],
        }
    )

    scatter_df = build_scatter_comparison_frame(
        df,
        ["Gross_Generator_Output", "Net_Power"],
        "Station_Enthalpy",
    )

    assert list(scatter_df.columns) == [
        "Pi_Timestamp",
        "Gross_Generator_Output",
        "Net_Power",
        "Station_Enthalpy",
    ]
    assert scatter_df.to_dict("records") == [
        {
            "Pi_Timestamp": pd.Timestamp("2026-05-08 00:00"),
            "Gross_Generator_Output": 101.0,
            "Net_Power": 94.0,
            "Station_Enthalpy": 1280.0,
        },
        {
            "Pi_Timestamp": pd.Timestamp("2026-05-08 01:00"),
            "Gross_Generator_Output": 102.0,
            "Net_Power": 95.0,
            "Station_Enthalpy": 1290.0,
        },
    ]
