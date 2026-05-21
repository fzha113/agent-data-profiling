import importlib
import json
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

from agent_data_profiling.comparison import (
    build_comparison_frame,
    build_scatter_comparison_frame,
    get_comparison_plot_mode,
    validate_xy_tags,
)
from agent_data_profiling.llm import (
    build_incident_llm_context,
    build_supervisor_incident_prompt,
    build_tag_profile_llm_context,
    build_tag_profile_llm_messages,
    get_ai_gateway_config_from_env,
    get_supervisor_agent_config_from_env,
    query_ai_gateway,
    query_supervisor_agent,
)
from agent_data_profiling.profiling import (
    BASELINE_LOOKBACK_DAYS,
    fetch_tag_profile,
    get_profile_baseline_window,
)
from agent_data_profiling.quality import (
    QUALITY_INCIDENT_LOOKBACK_DAYS,
    QUALITY_MONITOR_REFRESH_MINUTES,
    ensure_monitor_incident_feedback_table,
    fetch_incident_tag_history,
    fetch_recent_quality_incidents,
    get_data_quality_config_from_env,
    get_incident_plot_window,
    insert_incident_feedback,
)
from agent_data_profiling.queries import (
    MAX_LOOKBACK_DAYS,
    fetch_source_table_columns,
    fetch_tag_history,
    get_query_config_from_env,
)
from agent_data_profiling.tag_catalog import DEFAULT_TAGS, TAG_CATALOG, get_catalog_tags


DEFAULT_START_DATE = date(2024, 6, 10)
DEFAULT_END_DATE = date(2024, 6, 17)
DATE_PICKER_MIN_DATE = date(2024, 6, 1)
DATE_PICKER_MAX_DATE = date(2024, 10, 1)
LARGE_WINDOW_WARNING_DAYS = 30
COMPARISON_PLOT_TYPES = ("Line", "Scatter")
PROFILING_DEFAULT_TAGS = ("Net_Power",)
DISPLAY_TIMEZONE = ZoneInfo("Pacific/Auckland")
DISPLAY_TIMEZONE_LABEL = "NZT"
PI_TIMESTAMP_DISPLAY_COLUMN = "Pi_Timestamp_NZT"
QUALITY_INCIDENTS_SECTION = "Data quality incidents"
TAG_PROFILING_SECTION = "Tag profiling"
COMPARE_TAGS_SECTION = "Compare tags"
APP_SECTIONS = (
    QUALITY_INCIDENTS_SECTION,
    TAG_PROFILING_SECTION,
    COMPARE_TAGS_SECTION,
)
DEFAULT_SECTION = QUALITY_INCIDENTS_SECTION
QUALITY_RESULT_STATE_KEY = "quality_incident_result"
QUALITY_CONTEXT_RESULT_STATE_KEY = "quality_incident_context_results"
QUALITY_GRID_VERSION_STATE_KEY = "quality_incident_grid_version"
PROFILING_RESULT_STATE_KEY = "profiling_result"
COMPARISON_RESULT_STATE_KEY = "comparison_result"
LLM_PROFILE_ANALYSIS_STATE_KEY = "llm_profile_analyses"
LLM_INCIDENT_ANALYSIS_STATE_KEY = "llm_incident_analyses"
PROFILING_TAGS_WIDGET_KEY = "profiling_tags"
PROFILING_START_DATE_WIDGET_KEY = "profiling_start_date"
PROFILING_END_DATE_WIDGET_KEY = "profiling_end_date"
CHART_COLOR_SEQUENCE = (
    "#2563EB",
    "#059669",
    "#D97706",
    "#7C3AED",
    "#DC2626",
    "#0891B2",
)
CHART_COLOR_MAP = {
    "p1": "#2563EB",
    "p50": "#059669",
    "p99": "#D97706",
    "baseline": "#2563EB",
    "recent": "#D97706",
    "non_null_count": "#2563EB",
    "null_count": "#DC2626",
}
QUALITY_INCIDENT_SUMMARY_COLUMNS = [
    "incident_id",
    "tag_name",
    "rule_type",
    "status",
    "incident_start",
    "incident_end",
    "duration_minutes",
    "failed_windows",
    "review_status",
    "latest_feedback_ts",
    "incident_update_ts",
]


def _get_default_dates() -> tuple[datetime, datetime]:
    start_time = datetime.combine(DEFAULT_START_DATE, time.min, tzinfo=UTC)
    end_time = datetime.combine(DEFAULT_END_DATE, time.max, tzinfo=UTC)
    return start_time, end_time


def _combine_date_with_bound(selected_date, bound: time) -> datetime:
    return datetime.combine(selected_date, bound, tzinfo=UTC)


def _get_date_picker_bounds() -> tuple[date, date]:
    return DATE_PICKER_MIN_DATE, DATE_PICKER_MAX_DATE


def to_nzt_display_datetime(value) -> datetime:
    """
    Convert a UTC timestamp-like value to a timezone-naive NZT display datetime.

    Args:
        value: Timestamp-like scalar.

    Returns:
        datetime: Local display datetime in Pacific/Auckland.
    """
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(UTC)
    else:
        timestamp = timestamp.tz_convert(UTC)

    return timestamp.tz_convert(DISPLAY_TIMEZONE).to_pydatetime().replace(tzinfo=None)


def format_nzt_datetime(value) -> str:
    """
    Format one timestamp-like value for NZT display.

    Args:
        value: Timestamp-like scalar.

    Returns:
        str: Human-readable NZT timestamp.
    """
    if value is None or pd.isna(value):
        return "n/a"

    return f"{to_nzt_display_datetime(value):%Y-%m-%d %H:%M} {DISPLAY_TIMEZONE_LABEL}"


def with_nzt_display_column(
    df: pd.DataFrame,
    source_column: str,
    display_column: str,
) -> pd.DataFrame:
    """
    Add a timezone-naive NZT display column derived from a UTC timestamp column.

    Args:
        df: Source DataFrame.
        source_column: UTC timestamp column.
        display_column: Output local display column.

    Returns:
        pandas.DataFrame: Copy of `df` with the local display column.
    """
    display_df = df.copy()
    if display_df.empty:
        display_df[display_column] = pd.Series(dtype="datetime64[ns]")
        return display_df

    timestamps = pd.to_datetime(display_df[source_column])
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(UTC)
    else:
        timestamps = timestamps.dt.tz_convert(UTC)

    display_df[display_column] = timestamps.dt.tz_convert(DISPLAY_TIMEZONE).dt.tz_localize(None)
    return display_df


def convert_columns_to_nzt_display(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Convert existing timestamp columns to timezone-naive NZT display values.

    Args:
        df: Source DataFrame.
        columns: Timestamp columns to convert when present.

    Returns:
        pandas.DataFrame: Copy of `df` with converted timestamp columns.
    """
    display_df = df.copy()
    for column in columns:
        if column not in display_df.columns:
            continue
        display_df[column] = display_df[column].map(
            lambda value: (
                None if value is None or pd.isna(value) else to_nzt_display_datetime(value)
            )
        )
    return display_df


def get_session_result(state_key: str):
    """
    Read one cached result from the current Streamlit session.

    Args:
        state_key: Streamlit session state key.

    Returns:
        object | None: Cached result when present.
    """
    return st.session_state.get(state_key)


def set_session_result(state_key: str, result) -> None:
    """
    Store one result in the current Streamlit session.

    Args:
        state_key: Streamlit session state key.
        result: Result payload to keep for later reruns.

    Returns:
        None.
    """
    st.session_state[state_key] = result


def get_profiling_request_signature(
    selected_tags: list[str],
    start_time: datetime,
    end_time: datetime,
) -> tuple[tuple[str, ...], str, str]:
    """
    Build a stable signature for a profiling request.

    Args:
        selected_tags: Selected raw tag column names.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        tuple: Selected tags and ISO-formatted time window.
    """
    return tuple(selected_tags), start_time.isoformat(), end_time.isoformat()


def open_tag_profiling_detail(tag: str) -> None:
    """
    Set the next rerun to open Tag profiling for one incident tag.

    Args:
        tag: Raw tag column name.

    Returns:
        None.
    """
    if tag not in TAG_CATALOG:
        st.warning("This incident does not map to a profiling tag.")
        return

    default_start, default_end = _get_default_dates()
    st.session_state["app_section"] = TAG_PROFILING_SECTION
    st.session_state[PROFILING_TAGS_WIDGET_KEY] = [tag]
    st.session_state[PROFILING_START_DATE_WIDGET_KEY] = default_start.date()
    st.session_state[PROFILING_END_DATE_WIDGET_KEY] = default_end.date()
    st.session_state.pop(PROFILING_RESULT_STATE_KEY, None)
    st.session_state[QUALITY_GRID_VERSION_STATE_KEY] = (
        st.session_state.get(QUALITY_GRID_VERSION_STATE_KEY, 0) + 1
    )


def rerun_app() -> None:
    """
    Rerun the full Streamlit app, including from dialog fragments.

    Args:
        None.

    Returns:
        None.
    """
    try:
        st.rerun(scope="app")
    except TypeError:
        st.rerun()


def render_view_profile_button(incident_id: str, tag: str) -> None:
    """
    Render a button that opens Tag profiling for one incident tag.

    Args:
        incident_id: Monitor incident identifier used for widget key stability.
        tag: Raw tag column name.

    Returns:
        None.
    """
    if not st.button("View details", key=f"view_profile_{incident_id}"):
        return

    open_tag_profiling_detail(tag)
    rerun_app()


def render_section_navigation() -> str:
    """
    Render the top-level app section selector.

    Args:
        None.

    Returns:
        str: Selected app section label.
    """
    if hasattr(st, "segmented_control"):
        selected_section = st.segmented_control(
            "Section",
            options=APP_SECTIONS,
            selection_mode="single",
            default=DEFAULT_SECTION,
            key="app_section",
            label_visibility="collapsed",
        )
    else:
        session_section = getattr(st, "session_state", {}).get("app_section", DEFAULT_SECTION)
        selected_index = (
            APP_SECTIONS.index(session_section)
            if session_section in APP_SECTIONS
            else APP_SECTIONS.index(DEFAULT_SECTION)
        )
        selected_section = st.radio(
            "Section",
            options=APP_SECTIONS,
            index=selected_index,
            horizontal=True,
            key="app_section",
            label_visibility="collapsed",
        )
    return selected_section or DEFAULT_SECTION


def render_sidebar_header() -> None:
    """
    Render shared sidebar heading text.

    Args:
        None.

    Returns:
        None.
    """
    st.sidebar.header("KAG tag profiling")
    st.sidebar.caption("Station: KAG")


def render_profiling_sidebar() -> tuple[list[str], datetime, datetime, bool]:
    """
    Render sidebar controls for tag profiling.

    Args:
        None.

    Returns:
        tuple: Selected tags, start time, end time, and run button state.
    """
    render_sidebar_header()
    catalog_tags = list(get_catalog_tags())
    st.sidebar.subheader("Profiling tags")
    selected_tags = st.sidebar.multiselect(
        "tags",
        options=catalog_tags,
        default=list(PROFILING_DEFAULT_TAGS),
        max_selections=4,
        key=PROFILING_TAGS_WIDGET_KEY,
        placeholder="Select tags",
    )

    default_start, default_end = _get_default_dates()
    earliest_allowed, latest_allowed = _get_date_picker_bounds()

    start_date = st.sidebar.date_input(
        "Start date",
        value=default_start.date(),
        min_value=earliest_allowed,
        max_value=latest_allowed,
        key=PROFILING_START_DATE_WIDGET_KEY,
    )
    end_date = st.sidebar.date_input(
        "End date",
        value=default_end.date(),
        min_value=earliest_allowed,
        max_value=latest_allowed,
        key=PROFILING_END_DATE_WIDGET_KEY,
    )

    start_time = _combine_date_with_bound(start_date, time.min)
    end_time = _combine_date_with_bound(end_date, time.max)

    run_query = st.sidebar.button("Refresh", type="primary")

    return selected_tags, start_time, end_time, run_query


def render_comparison_sidebar() -> tuple[
    list[str],
    datetime,
    datetime,
    str,
    str | None,
    bool,
]:
    """
    Render sidebar controls for tag comparison.

    Args:
        None.

    Returns:
        tuple: Comparison tags, start time, end time, plot type, colour tag, and run button state.
    """
    render_sidebar_header()
    catalog_tags = list(get_catalog_tags())
    default_start, default_end = _get_default_dates()
    earliest_allowed, latest_allowed = _get_date_picker_bounds()

    st.sidebar.subheader("Compare tags")

    comparison_tags = st.sidebar.multiselect(
        "X/Y tags",
        options=catalog_tags,
        default=list(DEFAULT_TAGS),
        max_selections=2,
        key="comparison_tags",
        placeholder="Select tags",
    )
    comparison_colour_tag = st.sidebar.selectbox(
        "Colour tag",
        options=[tag for tag in catalog_tags if tag not in comparison_tags],
        index=None,
        placeholder="Select colour tag",
    )
    comparison_start_date = st.sidebar.date_input(
        "Comparison start date",
        value=default_start.date(),
        min_value=earliest_allowed,
        max_value=latest_allowed,
    )
    comparison_end_date = st.sidebar.date_input(
        "Comparison end date",
        value=default_end.date(),
        min_value=earliest_allowed,
        max_value=latest_allowed,
    )

    comparison_start_time = _combine_date_with_bound(comparison_start_date, time.min)
    comparison_end_time = _combine_date_with_bound(comparison_end_date, time.max)
    comparison_plot_type = st.sidebar.radio(
        "Plot type",
        options=COMPARISON_PLOT_TYPES,
        horizontal=True,
    )
    run_comparison = st.sidebar.button("Plot comparison", type="primary")

    return (
        comparison_tags,
        comparison_start_time,
        comparison_end_time,
        comparison_plot_type,
        comparison_colour_tag,
        run_comparison,
    )


def render_quality_sidebar() -> bool:
    """
    Render sidebar controls for data quality incidents.

    Args:
        None.

    Returns:
        bool: True when the user requested an immediate incident refresh.
    """
    render_sidebar_header()
    st.sidebar.subheader("Data quality incidents")
    st.sidebar.caption(
        f"Shows failed incidents updated in the last {QUALITY_INCIDENT_LOOKBACK_DAYS} days. "
        f"Monitor jobs refresh every {QUALITY_MONITOR_REFRESH_MINUTES} minutes."
    )
    return st.sidebar.button("Refresh incidents", type="primary")


def render_tag_plot(df, tag: str) -> None:
    """
    Render one raw point time-series plot.

    Args:
        df: DataFrame containing `Pi_Timestamp` and the selected tag.
        tag: Raw tag column name.

    Returns:
        None.
    """
    metadata = TAG_CATALOG[tag]
    title = metadata.display_name
    y_label = f"{tag} ({metadata.unit})" if metadata.unit else tag
    display_df = with_nzt_display_column(df, "Pi_Timestamp", PI_TIMESTAMP_DISPLAY_COLUMN)

    fig = px.line(
        display_df,
        x=PI_TIMESTAMP_DISPLAY_COLUMN,
        y=tag,
        title=title,
        labels={
            PI_TIMESTAMP_DISPLAY_COLUMN: f"PI timestamp ({DISPLAY_TIMEZONE_LABEL})",
            tag: y_label,
        },
    )
    fig.update_traces(
        mode="lines+markers",
        line={"color": CHART_COLOR_SEQUENCE[0]},
        marker={"color": CHART_COLOR_SEQUENCE[0], "size": 3},
    )
    fig.update_layout(height=320, margin={"l": 10, "r": 10, "t": 50, "b": 10})
    st.plotly_chart(fig, use_container_width=True)

    metadata_items = []
    if metadata.unit:
        metadata_items.append(f"Unit: `{metadata.unit}`")
    if metadata.process_area:
        metadata_items.append(f"Process area: `{metadata.process_area}`")
    if metadata.description:
        metadata_items.append(metadata.description)

    if metadata_items:
        st.caption(" | ".join(metadata_items))


def format_profile_value(value) -> str:
    """
    Format a numeric profiling value for display.

    Args:
        value: Numeric scalar returned by a profiling query.

    Returns:
        str: Human-readable value, or `n/a` for missing values.
    """
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.2f}"


def calculate_profile_shift(recent_value, baseline_value) -> float | None:
    """
    Calculate a recent-minus-baseline shift for two profile values.

    Args:
        recent_value: Recent period value.
        baseline_value: Baseline period value.

    Returns:
        float | None: Difference when both values are available.
    """
    if recent_value is None or baseline_value is None:
        return None
    if pd.isna(recent_value) or pd.isna(baseline_value):
        return None
    return float(recent_value) - float(baseline_value)


def build_density_distribution_frame(histogram_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert histogram counts into 0-1 density proportions.

    Args:
        histogram_df: Histogram DataFrame with `value_count`.

    Returns:
        pandas.DataFrame: Histogram DataFrame with a `density` column.
    """
    density_df = histogram_df.copy()
    if density_df.empty:
        density_df["density"] = pd.Series(dtype="float64")
        return density_df

    total_count = density_df["value_count"].sum()
    if total_count <= 0:
        density_df["density"] = 0.0
        return density_df

    density_df["density"] = density_df["value_count"] / total_count
    return density_df


def get_period_stats(stats_df: pd.DataFrame, period: str) -> pd.Series | None:
    """
    Read one period row from a profile stats DataFrame.

    Args:
        stats_df: Stats DataFrame with a `period` column.
        period: Period label to find.

    Returns:
        pandas.Series | None: Matching stats row when present.
    """
    if stats_df.empty or "period" not in stats_df.columns:
        return None

    period_rows = stats_df.loc[stats_df["period"] == period]
    if period_rows.empty:
        return None

    return period_rows.iloc[0]


def render_distribution_profile(
    tag: str,
    profile_result: dict,
    baseline_start_time: datetime,
    baseline_end_time: datetime,
) -> None:
    """
    Render the baseline value distribution for one tag.

    Args:
        tag: Raw tag column name.
        profile_result: Profile datasets for the tag.
        baseline_start_time: Inclusive baseline start timestamp.
        baseline_end_time: Inclusive baseline end timestamp.

    Returns:
        None.
    """
    histogram_df = build_density_distribution_frame(profile_result["histogram"])
    baseline_stats = get_period_stats(profile_result["stats"], "baseline")

    st.markdown("##### Tag density distribution")
    st.caption(
        f"Baseline: {format_period_label(baseline_start_time, baseline_end_time)} "
        f"({BASELINE_LOOKBACK_DAYS} days)"
    )

    if histogram_df.empty:
        st.warning("No histogram data returned for the baseline window.")
        return

    fig = px.bar(
        histogram_df,
        x="bin_center",
        y="density",
        title="Tag density distribution",
        color_discrete_sequence=[CHART_COLOR_SEQUENCE[0]],
        hover_data={"value_count": True, "density": ":.4f"},
        labels={
            "bin_center": TAG_CATALOG[tag].display_name,
            "density": "Density (0-1)",
            "value_count": "Count",
        },
    )
    if baseline_stats is not None:
        for percentile in ("p1", "p50", "p99"):
            value = baseline_stats[percentile]
            if value is not None and not pd.isna(value):
                fig.add_vline(
                    x=float(value),
                    line_dash="dash",
                    line_color=CHART_COLOR_MAP[percentile],
                    annotation_text=percentile.upper(),
                )
    fig.update_layout(
        height=320,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        yaxis={"range": [0, 1]},
    )
    st.plotly_chart(fig, use_container_width=True)

    if baseline_stats is None:
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("P1", format_profile_value(baseline_stats["p1"]))
    metric_cols[1].metric("P50", format_profile_value(baseline_stats["p50"]))
    metric_cols[2].metric("P99", format_profile_value(baseline_stats["p99"]))
    metric_cols[3].metric(
        "P1-P99 range",
        f"{format_profile_value(baseline_stats['p1'])} to "
        f"{format_profile_value(baseline_stats['p99'])}",
    )


def render_rolling_quantile_profile(tag: str, profile_result: dict) -> None:
    """
    Render daily P1/P50/P99 trends for one tag.

    Args:
        tag: Raw tag column name.
        profile_result: Profile datasets for the tag.

    Returns:
        None.
    """
    daily_df = profile_result["daily_trend"]

    st.markdown("##### Rolling percentile trend")
    if daily_df.empty:
        st.warning("No daily quantile data returned for the baseline window.")
        return

    profile_date_column = "profile_date_nzt"
    trend_source_df = daily_df.rename(columns={"profile_date": profile_date_column})
    trend_df = trend_source_df.melt(
        id_vars=[profile_date_column],
        value_vars=["p1", "p50", "p99"],
        var_name="percentile",
        value_name="value",
    ).dropna(subset=["value"])

    fig = px.line(
        trend_df,
        x=profile_date_column,
        y="value",
        color="percentile",
        title="Daily P1 / P50 / P99",
        color_discrete_map=CHART_COLOR_MAP,
        labels={
            profile_date_column: f"Date ({DISPLAY_TIMEZONE_LABEL})",
            "value": TAG_CATALOG[tag].display_name,
            "percentile": "Percentile",
        },
    )
    fig.update_layout(height=320, margin={"l": 10, "r": 10, "t": 50, "b": 10})
    st.plotly_chart(fig, use_container_width=True)


def render_availability_profile(profile_result: dict) -> None:
    """
    Render daily availability and gap metrics for one tag.

    Args:
        profile_result: Profile datasets for the tag.

    Returns:
        None.
    """
    daily_df = profile_result["daily_trend"]
    baseline_stats = get_period_stats(profile_result["stats"], "baseline")
    gap_df = profile_result["gap"]

    st.markdown("##### Missingness and gap profile")
    if daily_df.empty:
        st.warning("No daily availability data returned for the baseline window.")
        return

    profile_date_column = "profile_date_nzt"
    availability_df = daily_df[["profile_date", "non_null_count", "null_count"]].copy()
    availability_df = availability_df.rename(columns={"profile_date": profile_date_column})
    availability_df = availability_df.melt(
        id_vars=[profile_date_column],
        value_vars=["non_null_count", "null_count"],
        var_name="point_type",
        value_name="point_count",
    )
    fig = px.bar(
        availability_df,
        x=profile_date_column,
        y="point_count",
        color="point_type",
        title="Daily point availability",
        color_discrete_map=CHART_COLOR_MAP,
        labels={
            profile_date_column: f"Date ({DISPLAY_TIMEZONE_LABEL})",
            "point_count": "Points",
            "point_type": "Point type",
        },
    )
    fig.update_layout(height=320, margin={"l": 10, "r": 10, "t": 50, "b": 10})
    st.plotly_chart(fig, use_container_width=True)

    gap_stats = gap_df.iloc[0] if not gap_df.empty else None
    metric_cols = st.columns(4)
    null_rate = baseline_stats["null_rate"] if baseline_stats is not None else None
    metric_cols[0].metric(
        "Baseline null rate",
        "n/a" if null_rate is None or pd.isna(null_rate) else f"{float(null_rate):.2%}",
    )
    metric_cols[1].metric(
        "Large gaps",
        "n/a"
        if gap_stats is None or pd.isna(gap_stats["large_gap_count"])
        else f"{int(gap_stats['large_gap_count']):,}",
    )
    metric_cols[2].metric(
        "Longest gap min",
        "n/a"
        if gap_stats is None or pd.isna(gap_stats["longest_gap_minutes"])
        else format_profile_value(gap_stats["longest_gap_minutes"]),
    )
    metric_cols[3].metric(
        "Average gap min",
        "n/a"
        if gap_stats is None or pd.isna(gap_stats["average_gap_minutes"])
        else format_profile_value(gap_stats["average_gap_minutes"]),
    )


def render_drift_profile(
    tag: str,
    profile_result: dict,
    recent_start_time: datetime,
    recent_end_time: datetime,
    baseline_start_time: datetime,
    baseline_end_time: datetime,
) -> None:
    """
    Render recent-vs-baseline percentile comparison for one tag.

    Args:
        tag: Raw tag column name.
        profile_result: Profile datasets for the tag.
        recent_start_time: Inclusive recent period start timestamp.
        recent_end_time: Inclusive recent period end timestamp.
        baseline_start_time: Inclusive baseline period start timestamp.
        baseline_end_time: Inclusive baseline period end timestamp.

    Returns:
        None.
    """
    stats_df = profile_result["stats"]
    baseline_stats = get_period_stats(stats_df, "baseline")
    recent_stats = get_period_stats(stats_df, "recent")

    st.markdown("##### Recent vs baseline percentile profiling")
    st.caption(
        format_profile_window_caption(
            recent_start_time,
            recent_end_time,
            baseline_start_time,
            baseline_end_time,
        )
    )
    if baseline_stats is None or recent_stats is None:
        st.warning("No drift comparison data returned for this tag.")
        return

    drift_df = stats_df.melt(
        id_vars=["period"],
        value_vars=["p1", "p50", "p99"],
        var_name="percentile",
        value_name="value",
    ).dropna(subset=["value"])
    fig = px.bar(
        drift_df,
        x="percentile",
        y="value",
        color="period",
        barmode="group",
        title="Recent vs baseline percentile profiling",
        color_discrete_map=CHART_COLOR_MAP,
        labels={
            "percentile": "Percentile",
            "value": TAG_CATALOG[tag].display_name,
            "period": "Period",
        },
    )
    fig.update_layout(height=320, margin={"l": 10, "r": 10, "t": 50, "b": 10})
    st.plotly_chart(fig, use_container_width=True)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Recent P50", format_profile_value(recent_stats["p50"]))
    metric_cols[1].metric(
        "P50 shift",
        format_profile_value(calculate_profile_shift(recent_stats["p50"], baseline_stats["p50"])),
    )
    metric_cols[2].metric("Recent P99", format_profile_value(recent_stats["p99"]))
    metric_cols[3].metric(
        "P99 shift",
        format_profile_value(calculate_profile_shift(recent_stats["p99"], baseline_stats["p99"])),
    )


def render_tag_profile(
    tag: str,
    profile_result: dict,
    recent_start_time: datetime,
    recent_end_time: datetime,
    baseline_start_time: datetime,
    baseline_end_time: datetime,
) -> None:
    """
    Render all default profiling blocks for one tag.

    Args:
        tag: Raw tag column name.
        profile_result: Profile datasets for the tag.
        recent_start_time: Inclusive recent period start timestamp.
        recent_end_time: Inclusive recent period end timestamp.
        baseline_start_time: Inclusive half-year baseline start timestamp.
        baseline_end_time: Inclusive half-year baseline end timestamp.

    Returns:
        None.
    """
    render_distribution_profile(tag, profile_result, baseline_start_time, baseline_end_time)
    render_rolling_quantile_profile(tag, profile_result)
    render_availability_profile(profile_result)
    render_drift_profile(
        tag,
        profile_result,
        recent_start_time,
        recent_end_time,
        baseline_start_time,
        baseline_end_time,
    )
    render_tag_profile_ai_analysis(
        tag,
        profile_result,
        recent_start_time,
        recent_end_time,
        baseline_start_time,
        baseline_end_time,
    )


def load_llm_analysis_for_ui(
    messages: list[dict[str, str]],
    request_tags: dict[str, str],
    spinner_message: str,
    error_message: str,
) -> str | None:
    """
    Query AI Gateway and render Streamlit error details on failure.

    Args:
        messages: OpenAI-compatible chat messages.
        request_tags: AI Gateway request tags for tracing.
        spinner_message: Message shown while the model is running.
        error_message: Message shown if model analysis fails.

    Returns:
        str | None: Assistant analysis text, or None if loading failed.
    """
    try:
        config = get_ai_gateway_config_from_env()
        with st.spinner(spinner_message):
            return query_ai_gateway(config, messages, request_tags=request_tags)
    except Exception as exc:
        st.error(error_message)
        with st.expander("Technical detail"):
            st.exception(exc)
        return None


def build_supervisor_available_tags(
    source_columns: list[str] | tuple[str, ...],
    incident_tag: str,
) -> list[str]:
    """
    Build the Supervisor available_tags list from real source table columns.

    Args:
        source_columns: Source table columns returned by Databricks SQL.
        incident_tag: Current incident tag name.

    Returns:
        list[str]: Existing tag columns to pass to the Supervisor Agent.
    """
    catalog_tag_names = {tag.lower() for tag in get_catalog_tags()}
    available_tags = [
        column
        for column in source_columns
        if column.lower() in catalog_tag_names and column != "Pi_Timestamp"
    ]

    source_column_lookup = {column.lower(): column for column in source_columns}
    incident_source_tag = source_column_lookup.get(incident_tag.lower())
    if incident_source_tag and incident_source_tag not in available_tags:
        available_tags.append(incident_source_tag)

    return available_tags


def load_supervisor_available_tags_for_ui(incident_tag: str) -> list[str]:
    """
    Load real source-table tags for the Supervisor Agent, with a conservative fallback.

    Args:
        incident_tag: Current incident tag name.

    Returns:
        list[str]: Existing source tags for downstream agent validation.
    """
    try:
        raw_config = get_query_config_from_env()
        source_columns = fetch_source_table_columns(raw_config)
    except Exception as exc:
        st.warning("Could not load source table schema; passing only the incident tag to AI.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return [incident_tag]

    available_tags = build_supervisor_available_tags(source_columns, incident_tag)
    return available_tags or [incident_tag]


def load_supervisor_incident_analysis_for_ui(
    context: dict,
    available_tags: list[str],
) -> str | None:
    """
    Query the Databricks Supervisor Agent and render Streamlit error details on failure.

    Args:
        context: Incident context from `build_incident_llm_context`.
        available_tags: Existing source-table tag columns.

    Returns:
        str | None: Supervisor final answer, or None if loading failed.
    """
    try:
        config = get_supervisor_agent_config_from_env()
        prompt = build_supervisor_incident_prompt(context, available_tags)
        with st.spinner("Running Supervisor Agent incident investigation..."):
            return query_supervisor_agent(config, prompt)
    except Exception as exc:
        st.error("Failed to generate Supervisor Agent incident analysis.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return None


def render_tag_profile_ai_analysis(
    tag: str,
    profile_result: dict,
    recent_start_time: datetime,
    recent_end_time: datetime,
    baseline_start_time: datetime,
    baseline_end_time: datetime,
) -> None:
    """
    Render an AI-generated analysis for one tag profile when requested.

    Args:
        tag: Raw tag column name.
        profile_result: Profile datasets for the tag.
        recent_start_time: Inclusive recent period start timestamp.
        recent_end_time: Inclusive recent period end timestamp.
        baseline_start_time: Inclusive baseline period start timestamp.
        baseline_end_time: Inclusive baseline period end timestamp.

    Returns:
        None.
    """
    analysis_key = (
        f"{tag}|{recent_start_time.isoformat()}|{recent_end_time.isoformat()}|"
        f"{baseline_start_time.isoformat()}|{baseline_end_time.isoformat()}"
    )
    analyses = st.session_state.setdefault(LLM_PROFILE_ANALYSIS_STATE_KEY, {})

    if st.button(
        "AI explain profile",
        key=f"ai_profile_{analysis_key}",
        type="secondary",
    ):
        context = build_tag_profile_llm_context(
            tag,
            profile_result,
            recent_start_time,
            recent_end_time,
            baseline_start_time,
            baseline_end_time,
        )
        analysis = load_llm_analysis_for_ui(
            messages=build_tag_profile_llm_messages(context),
            request_tags={"feature": "tag_profiling", "tag": tag},
            spinner_message="Generating AI profile summary...",
            error_message="Failed to generate AI profile summary.",
        )
        if analysis is not None:
            analyses[analysis_key] = analysis

    if analysis_key in analyses:
        st.markdown("##### AI profile summary")
        st.markdown(analyses[analysis_key])


def format_period_label(start_time: datetime, end_time: datetime) -> str:
    """
    Format a query period for chart titles.

    Args:
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        str: Human-readable NZT period label.
    """
    return f"{format_nzt_datetime(start_time)} to {format_nzt_datetime(end_time)}"


def format_profile_window_caption(
    recent_start_time: datetime,
    recent_end_time: datetime,
    baseline_start_time: datetime,
    baseline_end_time: datetime,
) -> str:
    """
    Format recent and baseline profile windows for display.

    Args:
        recent_start_time: Inclusive recent period start timestamp.
        recent_end_time: Inclusive recent period end timestamp.
        baseline_start_time: Inclusive baseline period start timestamp.
        baseline_end_time: Inclusive baseline period end timestamp.

    Returns:
        str: Human-readable NZT profile window summary.
    """
    recent_days = (recent_end_time - recent_start_time).days
    baseline_days = (baseline_end_time - baseline_start_time).days
    return (
        f"Recent: {format_period_label(recent_start_time, recent_end_time)} "
        f"({recent_days} days) | "
        f"Baseline: {format_period_label(baseline_start_time, baseline_end_time)} "
        f"({baseline_days} days)"
    )


def render_comparison_plot(
    df,
    tags: list[str],
    plot_type: str,
    start_time: datetime,
    end_time: datetime,
    colour_tag: str | None,
) -> None:
    """
    Render selected tags in one comparison plot.

    Args:
        df: DataFrame containing `Pi_Timestamp` and selected tag columns.
        tags: Raw tag column names to compare.
        plot_type: UI plot type label.
        start_time: Inclusive comparison start time.
        end_time: Inclusive comparison end time.
        colour_tag: Raw tag column name used to colour scatter points.

    Returns:
        None.
    """
    plot_mode = get_comparison_plot_mode(plot_type)
    period_label = format_period_label(start_time, end_time)
    display_df = with_nzt_display_column(df, "Pi_Timestamp", PI_TIMESTAMP_DISPLAY_COLUMN)
    display_df["Pi_Timestamp"] = display_df[PI_TIMESTAMP_DISPLAY_COLUMN]

    if plot_mode == "line":
        comparison_df = build_comparison_frame(display_df, tags)
        fig = px.line(
            comparison_df,
            x="Pi_Timestamp",
            y="value",
            color="display_name",
            title=f"Tag comparison | Period: {period_label}",
            labels={
                "Pi_Timestamp": f"PI timestamp ({DISPLAY_TIMEZONE_LABEL})",
                "value": "Value",
                "display_name": "Tag",
            },
            hover_data={"tag": True, "display_name": False},
        )
    else:
        if colour_tag is None:
            raise ValueError("Colour tag is required for scatter comparison.")

        x_tag, y_tag = validate_xy_tags(tags)
        comparison_df = build_scatter_comparison_frame(display_df, tags, colour_tag)
        fig = px.scatter(
            comparison_df,
            x=x_tag,
            y=y_tag,
            color=colour_tag,
            title=f"Tag comparison | Period: {period_label}",
            labels={
                x_tag: TAG_CATALOG[x_tag].display_name,
                y_tag: TAG_CATALOG[y_tag].display_name,
                colour_tag: TAG_CATALOG[colour_tag].display_name,
                "Pi_Timestamp": f"PI timestamp ({DISPLAY_TIMEZONE_LABEL})",
            },
            hover_data={"Pi_Timestamp": True},
            color_continuous_scale="Viridis",
        )

    fig.update_layout(height=420, margin={"l": 10, "r": 10, "t": 50, "b": 10})
    st.plotly_chart(fig, use_container_width=True)


def render_incident_tag_plot(
    df,
    tag: str,
    incident_start: datetime,
    incident_end: datetime,
    outlier_thresholds: tuple[float, float] | None = None,
) -> None:
    """
    Render one raw point time-series plot with the incident period highlighted.

    Args:
        df: DataFrame containing `Pi_Timestamp` and the incident tag.
        tag: Raw tag column name.
        incident_start: Incident start timestamp.
        incident_end: Incident end timestamp.
        outlier_thresholds: Lower and upper threshold values for outlier incidents.

    Returns:
        None.
    """
    metadata = TAG_CATALOG.get(tag)
    display_name = metadata.display_name if metadata is not None else tag
    display_df = with_nzt_display_column(df, "Pi_Timestamp", PI_TIMESTAMP_DISPLAY_COLUMN)
    incident_start_nzt = to_nzt_display_datetime(incident_start)
    incident_end_nzt = to_nzt_display_datetime(incident_end)

    fig = px.line(
        display_df,
        x=PI_TIMESTAMP_DISPLAY_COLUMN,
        y=tag,
        title=f"{display_name} | Data quality incident context",
        labels={
            PI_TIMESTAMP_DISPLAY_COLUMN: f"PI timestamp ({DISPLAY_TIMEZONE_LABEL})",
            tag: display_name,
        },
    )
    fig.update_traces(mode="lines+markers", marker={"size": 3})
    fig.add_vrect(
        x0=incident_start_nzt,
        x1=incident_end_nzt,
        fillcolor="rgba(214, 39, 40, 0.16)",
        line_width=0,
    )
    if outlier_thresholds is not None:
        lower_threshold, upper_threshold = outlier_thresholds
        fig.add_hline(
            y=lower_threshold,
            line_dash="dash",
            line_color="#d62728",
            annotation_text="lower threshold",
        )
        fig.add_hline(
            y=upper_threshold,
            line_dash="dash",
            line_color="#d62728",
            annotation_text="upper threshold",
        )
    fig.update_layout(height=340, margin={"l": 10, "r": 10, "t": 50, "b": 10})
    st.plotly_chart(fig, use_container_width=True)


def validate_run_inputs(
    selected_tags: list[str],
    start_time: datetime,
    end_time: datetime,
    empty_selection_message: str,
    end_before_start_message: str,
    max_window_message: str,
    large_window_message: str,
) -> int | None:
    """
    Validate selected tags and date window for a user-triggered query.

    Args:
        selected_tags: Selected raw tag column names.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.
        empty_selection_message: Message shown when no tags are selected.
        end_before_start_message: Message shown when the window is inverted.
        max_window_message: Message shown when the window exceeds the app limit.
        large_window_message: Message shown when the window may be slow.

    Returns:
        int | None: Selected window length in days, or None if invalid.
    """
    if not selected_tags:
        st.info(empty_selection_message)
        return None

    if end_time <= start_time:
        st.error(end_before_start_message)
        return None

    selected_days = (end_time - start_time).days
    if selected_days > MAX_LOOKBACK_DAYS:
        st.error(max_window_message)
        return None

    if selected_days > LARGE_WINDOW_WARNING_DAYS:
        st.warning(large_window_message)

    return selected_days


def load_tag_history_for_ui(
    selected_tags: list[str],
    start_time: datetime,
    end_time: datetime,
    spinner_message: str,
    error_message: str,
):
    """
    Fetch tag history and render Streamlit error details on failure.

    Args:
        selected_tags: Selected raw tag column names.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.
        spinner_message: Message shown while loading data.
        error_message: Message shown if loading fails.

    Returns:
        tuple: Query config and DataFrame, or None values if loading failed.
    """
    try:
        config = get_query_config_from_env()
        with st.spinner(spinner_message):
            df = fetch_tag_history(config, selected_tags, start_time, end_time)
    except Exception as exc:
        st.error(error_message)
        with st.expander("Technical detail"):
            st.exception(exc)
        return None, None

    return config, df


def load_tag_profile_for_ui(
    tag: str,
    baseline_start_time: datetime,
    baseline_end_time: datetime,
    recent_start_time: datetime,
    recent_end_time: datetime,
):
    """
    Fetch aggregated profile datasets for one tag and render Streamlit errors on failure.

    Args:
        tag: Raw tag column name.
        baseline_start_time: Inclusive half-year baseline start timestamp.
        baseline_end_time: Inclusive half-year baseline end timestamp.
        recent_start_time: Inclusive recent comparison start timestamp.
        recent_end_time: Inclusive recent comparison end timestamp.

    Returns:
        dict | None: Profile datasets, or None if loading failed.
    """
    try:
        config = get_query_config_from_env()
        metadata = TAG_CATALOG[tag]
        with st.spinner(f"Loading {metadata.display_name} profile..."):
            return fetch_tag_profile(
                config,
                tag,
                baseline_start_time,
                baseline_end_time,
                recent_start_time,
                recent_end_time,
            )
    except Exception as exc:
        st.error(f"Failed to load profile summary for {tag}.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return None


def load_profiling_result(
    selected_tags: list[str],
    start_time: datetime,
    end_time: datetime,
) -> dict | None:
    """
    Load the profiling query result for one user-triggered request.

    Args:
        selected_tags: Selected raw tag column names.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        dict | None: Profiling result payload, or None when validation/loading fails.
    """
    selected_days = validate_run_inputs(
        selected_tags=selected_tags,
        start_time=start_time,
        end_time=end_time,
        empty_selection_message="Select 1 to 4 profiling tags from the sidebar.",
        end_before_start_message="End date must be after start date.",
        max_window_message=f"Select a window of no more than {MAX_LOOKBACK_DAYS} days.",
        large_window_message=(
            "This query uses raw points over a large window and may take longer to run."
        ),
    )
    if selected_days is None:
        return None

    config, df = load_tag_history_for_ui(
        selected_tags=selected_tags,
        start_time=start_time,
        end_time=end_time,
        spinner_message="Loading raw PI data...",
        error_message="Failed to load tag history.",
    )
    if df is None:
        return None

    request_signature = get_profiling_request_signature(
        selected_tags,
        start_time,
        end_time,
    )
    baseline_start_time, baseline_end_time = get_profile_baseline_window(end_time)
    tag_profiles = {}
    for tag in selected_tags:
        tag_profile = load_tag_profile_for_ui(
            tag,
            baseline_start_time,
            baseline_end_time,
            start_time,
            end_time,
        )
        if tag_profile is None:
            return None
        tag_profiles[tag] = tag_profile

    return {
        "config": config,
        "df": df,
        "selected_tags": list(selected_tags),
        "start_time": start_time,
        "end_time": end_time,
        "selected_days": selected_days,
        "request_signature": request_signature,
        "baseline_start_time": baseline_start_time,
        "baseline_end_time": baseline_end_time,
        "tag_profiles": tag_profiles,
    }


def render_profiling_result(result: dict) -> None:
    """
    Render a stored profiling query result.

    Args:
        result: Profiling result payload from `load_profiling_result`.

    Returns:
        None.
    """
    config = result["config"]
    df = result["df"]
    selected_tags = result["selected_tags"]
    start_time = result["start_time"]
    end_time = result["end_time"]
    selected_days = result["selected_days"]
    baseline_start_time = result["baseline_start_time"]
    baseline_end_time = result["baseline_end_time"]
    tag_profiles = result["tag_profiles"]

    if df.empty:
        st.warning("No raw PI data returned for the selected tags and time window.")
        return

    latest_ts = df["Pi_Timestamp"].max()
    metric_cols = st.columns(4)
    metric_cols[0].metric("Selected tags", len(selected_tags))
    metric_cols[1].metric("Rows", f"{len(df):,}")
    metric_cols[2].metric("Window days", selected_days)
    metric_cols[3].metric("Latest PI timestamp", format_nzt_datetime(latest_ts))

    st.caption(
        f"Source: `{config.stream_catalog_raw}.{config.source_schema}.{config.source_table}`"
    )

    for tag in selected_tags:
        st.subheader(TAG_CATALOG[tag].display_name)
        render_tag_plot(df, tag)
        render_tag_profile(
            tag,
            tag_profiles[tag],
            start_time,
            end_time,
            baseline_start_time,
            baseline_end_time,
        )


def render_profiling_section(
    selected_tags: list[str],
    start_time: datetime,
    end_time: datetime,
    run_query: bool = False,
) -> None:
    """
    Render the profiling section, preserving the last successful result across tab switches.

    Args:
        selected_tags: Selected raw tag column names.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.
        run_query: True when the user clicked Plot profiling.

    Returns:
        None.
    """
    request_signature = get_profiling_request_signature(selected_tags, start_time, end_time)
    stored_result = get_session_result(PROFILING_RESULT_STATE_KEY)
    needs_load = (
        run_query
        or stored_result is None
        or stored_result.get("request_signature") != request_signature
    )

    if needs_load:
        result = load_profiling_result(selected_tags, start_time, end_time)
        if result is not None:
            set_session_result(PROFILING_RESULT_STATE_KEY, result)
            stored_result = result
        elif stored_result is None or stored_result.get("request_signature") != request_signature:
            return

    if stored_result is None:
        st.info("Select profiling tags, then click Refresh.")
        return

    render_profiling_result(stored_result)


def load_comparison_result(
    comparison_tags: list[str],
    comparison_start_time: datetime,
    comparison_end_time: datetime,
    comparison_plot_type: str,
    comparison_colour_tag: str | None,
) -> dict | None:
    """
    Load the comparison query result for one user-triggered request.

    Args:
        comparison_tags: Selected raw tag column names.
        comparison_start_time: Inclusive comparison start time.
        comparison_end_time: Inclusive comparison end time.
        comparison_plot_type: UI plot type label.
        comparison_colour_tag: Raw tag column name used to colour scatter points.

    Returns:
        dict | None: Comparison result payload, or None when validation/loading fails.
    """
    try:
        xy_tags = validate_xy_tags(comparison_tags)
    except ValueError as exc:
        st.info(str(exc))
        return None

    plot_mode = get_comparison_plot_mode(comparison_plot_type)
    query_tags = list(xy_tags)
    if plot_mode == "scatter":
        if comparison_colour_tag is None:
            st.info("Select a colour tag for scatter comparison.")
            return None
        query_tags.append(comparison_colour_tag)

    comparison_days = validate_run_inputs(
        selected_tags=query_tags,
        start_time=comparison_start_time,
        end_time=comparison_end_time,
        empty_selection_message="Select exactly 2 comparison tags from the sidebar.",
        end_before_start_message=("Comparison end date must be after comparison start date."),
        max_window_message=(
            f"Select a comparison window of no more than {MAX_LOOKBACK_DAYS} days."
        ),
        large_window_message=(
            "This comparison uses raw points over a large window and may take longer to run."
        ),
    )
    if comparison_days is None:
        return None

    config, comparison_df = load_tag_history_for_ui(
        selected_tags=query_tags,
        start_time=comparison_start_time,
        end_time=comparison_end_time,
        spinner_message="Loading comparison data...",
        error_message="Failed to load comparison tag history.",
    )
    if comparison_df is None:
        return None

    return {
        "config": config,
        "df": comparison_df,
        "comparison_tags": list(xy_tags),
        "comparison_start_time": comparison_start_time,
        "comparison_end_time": comparison_end_time,
        "comparison_plot_type": comparison_plot_type,
        "comparison_colour_tag": comparison_colour_tag,
        "comparison_days": comparison_days,
    }


def render_comparison_result(result: dict) -> None:
    """
    Render a stored comparison query result.

    Args:
        result: Comparison result payload from `load_comparison_result`.

    Returns:
        None.
    """
    config = result["config"]
    comparison_df = result["df"]
    comparison_start_time = result["comparison_start_time"]
    comparison_end_time = result["comparison_end_time"]
    comparison_plot_type = result["comparison_plot_type"]
    comparison_colour_tag = result["comparison_colour_tag"]
    comparison_tags = result["comparison_tags"]

    st.subheader("Tag comparison")
    if comparison_df.empty:
        st.warning("No raw PI data returned for the comparison tags and time window.")
        return

    render_comparison_plot(
        comparison_df,
        list(comparison_tags),
        comparison_plot_type,
        comparison_start_time,
        comparison_end_time,
        comparison_colour_tag,
    )
    st.caption(
        f"Source: `{config.stream_catalog_raw}.{config.source_schema}.{config.source_table}`"
    )


def render_comparison_section(
    comparison_tags: list[str],
    comparison_start_time: datetime,
    comparison_end_time: datetime,
    comparison_plot_type: str,
    comparison_colour_tag: str | None,
    run_comparison: bool = False,
) -> None:
    """
    Render the comparison section, preserving the last result across tab switches.

    Args:
        comparison_tags: Selected raw tag column names.
        comparison_start_time: Inclusive comparison start time.
        comparison_end_time: Inclusive comparison end time.
        comparison_plot_type: UI plot type label.
        comparison_colour_tag: Raw tag column name used to colour scatter points.
        run_comparison: True when the user clicked Plot comparison.

    Returns:
        None.
    """
    if run_comparison:
        result = load_comparison_result(
            comparison_tags,
            comparison_start_time,
            comparison_end_time,
            comparison_plot_type,
            comparison_colour_tag,
        )
        if result is not None:
            set_session_result(COMPARISON_RESULT_STATE_KEY, result)

    stored_result = get_session_result(COMPARISON_RESULT_STATE_KEY)
    if stored_result is None:
        st.info("Select comparison inputs, then click Plot comparison.")
        return

    render_comparison_result(stored_result)


@st.cache_data(ttl=QUALITY_MONITOR_REFRESH_MINUTES * 60, show_spinner=False)
def load_quality_incidents_for_ui():
    """
    Fetch recent data quality incidents using the monitor refresh cadence as cache TTL.

    Args:
        None.

    Returns:
        tuple: Data quality config, lower-bound timestamp, and incident DataFrame.
    """
    config = get_data_quality_config_from_env()
    since_time = datetime.now(UTC) - timedelta(days=QUALITY_INCIDENT_LOOKBACK_DAYS)
    ensure_monitor_incident_feedback_table(config)
    df = fetch_recent_quality_incidents(config, since_time)
    return config, since_time, df


@st.cache_data(ttl=QUALITY_MONITOR_REFRESH_MINUTES * 60, show_spinner=False)
def load_incident_tag_history_for_ui(
    tag: str,
    start_time: datetime,
    end_time: datetime,
):
    """
    Fetch raw PI history for one data quality incident tag.

    Args:
        tag: Raw tag column name.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        tuple: Raw query config and DataFrame.
    """
    raw_config = get_query_config_from_env()
    df = fetch_incident_tag_history(raw_config, tag, start_time, end_time)
    return raw_config, df


def load_quality_incident_result() -> dict:
    """
    Load the data quality incident list for the current app session.

    Args:
        None.

    Returns:
        dict: Data quality config, lower-bound timestamp, and incident DataFrame.
    """
    with st.spinner("Loading data quality incidents..."):
        quality_config, since_time, df = load_quality_incidents_for_ui()

    return {
        "quality_config": quality_config,
        "since_time": since_time,
        "df": df,
    }


def get_incident_context_state_key(
    tag: str,
    start_time: datetime,
    end_time: datetime,
) -> str:
    """
    Build a stable session key for one incident raw context query.

    Args:
        tag: Raw tag column name.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        str: Incident context session cache key.
    """
    return f"{tag}|{start_time.isoformat()}|{end_time.isoformat()}"


def load_incident_context_result(
    tag: str,
    start_time: datetime,
    end_time: datetime,
) -> dict:
    """
    Load or reuse raw PI history for one incident context plot.

    Args:
        tag: Raw tag column name.
        start_time: Inclusive query start time.
        end_time: Inclusive query end time.

    Returns:
        dict: Raw query config and context DataFrame.
    """
    context_results = st.session_state.setdefault(QUALITY_CONTEXT_RESULT_STATE_KEY, {})
    context_key = get_incident_context_state_key(tag, start_time, end_time)
    if context_key in context_results:
        return context_results[context_key]

    with st.spinner("Loading raw PI context..."):
        raw_config, df = load_incident_tag_history_for_ui(tag, start_time, end_time)

    result = {
        "raw_config": raw_config,
        "df": df,
    }
    context_results[context_key] = result
    return result


def build_quality_incident_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build one summary row per data quality incident.

    Args:
        df: Joined incident and quality log DataFrame.

    Returns:
        pandas.DataFrame: Incident summary rows for display.
    """
    summary_df = (
        df.groupby("incident_id", sort=False, as_index=False)
        .agg(
            tag_name=("tag_name", "first"),
            rule_type=("rule_type", "first"),
            status=("status", "first"),
            incident_start=("incident_start", "first"),
            incident_end=("incident_end", "first"),
            incident_update_ts=("incident_update_ts", "first"),
            failed_windows=("log_run_id", "count"),
            feedback_count=("feedback_count", "max"),
            latest_feedback_ts=("latest_feedback_ts", "max"),
        )
        .copy()
    )
    summary_df["feedback_count"] = summary_df["feedback_count"].fillna(0).astype(int)
    summary_df["review_status"] = summary_df["feedback_count"].map(
        lambda feedback_count: "Commented" if feedback_count > 0 else "Open"
    )
    summary_df["duration_minutes"] = (
        pd.to_datetime(summary_df["incident_end"]) - pd.to_datetime(summary_df["incident_start"])
    ).dt.total_seconds() / 60.0
    return summary_df.sort_values(
        ["incident_update_ts", "incident_start"],
        ascending=[False, False],
    ).reset_index(drop=True)


def render_quality_incident_metrics(summary_df: pd.DataFrame) -> None:
    """
    Render high-level metrics for recent quality incidents.

    Args:
        summary_df: One row per incident.

    Returns:
        None.
    """
    problem_tags = summary_df.loc[summary_df["tag_name"] != "_table_", "tag_name"]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Incidents", f"{len(summary_df):,}")
    metric_cols[1].metric("Problem tags", f"{problem_tags.nunique():,}")
    metric_cols[2].metric("Rule types", f"{summary_df['rule_type'].nunique():,}")
    metric_cols[3].metric("Refresh cadence", f"{QUALITY_MONITOR_REFRESH_MINUTES} min")


def _get_first_selected_grid_row(selected_rows):
    """
    Read the first selected row from an AgGrid selected rows payload.

    Args:
        selected_rows: AgGrid selected rows payload.

    Returns:
        object | None: First selected row when available.
    """
    if selected_rows is None:
        return None
    if isinstance(selected_rows, pd.DataFrame):
        return None if selected_rows.empty else selected_rows.iloc[0]
    if isinstance(selected_rows, list | tuple):
        return None if not selected_rows else selected_rows[0]
    return None


def _get_incident_id_from_grid_row(selected_row) -> str | None:
    """
    Read an incident identifier from one selected AgGrid row.

    Args:
        selected_row: One selected row returned by AgGrid.

    Returns:
        str | None: Incident identifier when present.
    """
    if not isinstance(selected_row, dict | pd.Series):
        return None

    incident_id = selected_row.get("incident_id")
    if incident_id is None or pd.isna(incident_id):
        return None
    return str(incident_id)


def get_selected_incident_id_from_grid_response(grid_response) -> str | None:
    """
    Read the selected incident identifier from an AgGrid response.

    Args:
        grid_response: Response object returned by `st_aggrid.AgGrid`.

    Returns:
        str | None: Selected incident identifier when a row is selected.
    """
    if not grid_response:
        return None

    if isinstance(grid_response, dict):
        selected_rows = grid_response.get("selected_rows")
    else:
        selected_rows = getattr(grid_response, "selected_rows", None)

    selected_row = _get_first_selected_grid_row(selected_rows)
    return _get_incident_id_from_grid_row(selected_row)


def _get_selected_incident_id_from_native_dataframe(
    display_summary_df: pd.DataFrame,
    selection_event,
) -> str | None:
    """
    Read the selected incident identifier from native Streamlit dataframe selection.

    Args:
        display_summary_df: Incident summary rows shown in the table.
        selection_event: Response returned by `st.dataframe` with selection enabled.

    Returns:
        str | None: Selected incident identifier when a row is selected.
    """
    if isinstance(selection_event, dict):
        selected_rows = selection_event.get("selection", {}).get("rows", [])
    else:
        selection = getattr(selection_event, "selection", None)
        selected_rows = getattr(selection, "rows", []) if selection is not None else []

    if not selected_rows:
        return None

    selected_position = selected_rows[0]
    if selected_position >= len(display_summary_df):
        return None
    return str(display_summary_df.iloc[selected_position]["incident_id"])


def render_incident_summary_grid(display_summary_df: pd.DataFrame) -> str | None:
    """
    Render the interactive incident summary grid and return the selected row id.

    Args:
        display_summary_df: One incident per row with display-ready values.

    Returns:
        str | None: Selected incident identifier.
    """
    grid_df = display_summary_df[QUALITY_INCIDENT_SUMMARY_COLUMNS].copy()
    grid_height = min(520, max(180, 72 + (len(grid_df) + 1) * 36))
    grid_key = f"quality_incident_grid_{st.session_state.get(QUALITY_GRID_VERSION_STATE_KEY, 0)}"

    try:
        st_aggrid = importlib.import_module("st_aggrid")
    except ImportError:
        selection_event = st.dataframe(
            grid_df,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key=grid_key,
        )
        return _get_selected_incident_id_from_native_dataframe(grid_df, selection_event)

    builder = st_aggrid.GridOptionsBuilder.from_dataframe(grid_df)
    builder.configure_default_column(
        editable=False,
        filterable=True,
        resizable=True,
        sorteable=True,
    )
    builder.configure_selection(selection_mode="single", use_checkbox=False)
    builder.configure_pagination(
        enabled=True,
        paginationAutoPageSize=False,
        paginationPageSize=12,
    )
    builder.configure_column("incident_id", header_name="Incident ID", pinned="left", width=190)
    builder.configure_column("tag_name", header_name="Tag", pinned="left", width=210)
    builder.configure_column("rule_type", header_name="Rule", width=130)
    builder.configure_column("status", header_name="Status", width=100)
    builder.configure_column("incident_start", header_name="Start NZT", width=165)
    builder.configure_column("incident_end", header_name="End NZT", width=165)
    builder.configure_column("duration_minutes", header_name="Minutes", width=105)
    builder.configure_column("failed_windows", header_name="Failed windows", width=130)
    builder.configure_column("review_status", header_name="Review", width=110)
    builder.configure_column("latest_feedback_ts", header_name="Latest feedback NZT", width=175)
    builder.configure_column("incident_update_ts", header_name="Updated NZT", width=165)
    builder.configure_grid_options(
        rowHeight=34,
        suppressCellFocus=True,
        rowSelection="single",
    )
    grid_options = builder.build()

    grid_response = st_aggrid.AgGrid(
        grid_df,
        gridOptions=grid_options,
        height=grid_height,
        fit_columns_on_grid_load=True,
        update_on=["selectionChanged"],
        data_return_mode=st_aggrid.DataReturnMode.FILTERED_AND_SORTED,
        allow_unsafe_jscode=False,
        enable_enterprise_modules=False,
        theme="streamlit",
        custom_css={
            ".ag-row-hover": {
                "background-color": "rgba(37, 99, 235, 0.10) !important",
                "box-shadow": "0 2px 8px rgba(15, 23, 42, 0.18)",
                "cursor": "pointer",
                "transform": "translateY(-1px)",
                "z-index": "2",
            },
            ".ag-row-selected": {
                "background-color": "rgba(37, 99, 235, 0.16) !important",
            },
            ".ag-header-cell-label": {
                "font-weight": "600",
            },
        },
        key=grid_key,
    )
    return get_selected_incident_id_from_grid_response(grid_response)


def render_quality_log_rows(incident_rows: pd.DataFrame) -> None:
    """
    Render matched quality log rows for one incident.

    Args:
        incident_rows: Rows for a single incident.

    Returns:
        None.
    """
    log_rows = incident_rows.dropna(subset=["log_run_id", "observed_value"], how="all")
    if log_rows.empty:
        st.info("No matched quality log rows were returned for this incident.")
        return

    display_log_rows = convert_columns_to_nzt_display(
        log_rows,
        ["window_start", "window_end", "log_create_ts"],
    )
    st.dataframe(
        display_log_rows[
            [
                "log_run_id",
                "window_start",
                "window_end",
                "observed_value",
                "log_create_ts",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


def get_latest_outlier_thresholds(incident_rows: pd.DataFrame) -> tuple[float, float] | None:
    """
    Extract lower and upper thresholds from the latest outlier quality log row.

    Args:
        incident_rows: Rows for a single incident.

    Returns:
        tuple[float, float] | None: Lower and upper thresholds when available.
    """
    if incident_rows.empty:
        return None

    if str(incident_rows.iloc[0]["rule_type"]) != "outlier":
        return None

    log_rows = incident_rows.dropna(subset=["observed_value"]).sort_values("window_start")
    if log_rows.empty:
        return None

    observed_value = log_rows.iloc[-1]["observed_value"]
    try:
        threshold_payload = json.loads(observed_value)
        lower_threshold = threshold_payload["lower_threshold"]
        upper_threshold = threshold_payload["upper_threshold"]
    except (TypeError, ValueError, KeyError):
        return None

    if lower_threshold is None or upper_threshold is None:
        return None

    return float(lower_threshold), float(upper_threshold)


def render_incident_feedback_form(incident_id: str, quality_config) -> None:
    """
    Render a manual feedback form for one incident.

    Args:
        incident_id: Incident identifier.
        quality_config: Data quality runtime configuration.

    Returns:
        None.
    """
    with st.form(f"feedback_{incident_id}", clear_on_submit=True):
        comment = st.text_area(
            "Reason / investigation comment",
            key=f"comment_{incident_id}",
        )
        submitted = st.form_submit_button("Confirm", type="primary")

    if not submitted:
        return

    if not comment.strip():
        st.warning("Comment cannot be empty.")
        return

    try:
        ensure_monitor_incident_feedback_table(quality_config)
        insert_incident_feedback(quality_config, incident_id, comment)
    except ValueError as exc:
        st.warning(str(exc))
        return
    except Exception as exc:
        st.error("Failed to submit incident feedback.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return

    st.success("Feedback comment submitted.")


def render_incident_context_plot(
    tag: str,
    incident_start: datetime,
    incident_end: datetime,
    outlier_thresholds: tuple[float, float] | None,
) -> pd.DataFrame | None:
    """
    Render the raw PI context plot for one incident when requested.

    Args:
        tag: Raw tag column name.
        incident_start: Incident start timestamp.
        incident_end: Incident end timestamp.
        outlier_thresholds: Lower and upper threshold values for outlier incidents.

    Returns:
        pandas.DataFrame | None: Raw context rows when available.
    """
    if tag == "_table_":
        st.info("Freshness incidents are table-level; there is no single tag plot.")
        return None

    plot_start, plot_end = get_incident_plot_window(incident_start, incident_end)

    try:
        context_result = load_incident_context_result(tag, plot_start, plot_end)
    except Exception as exc:
        st.error("Failed to load raw PI context for this incident.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return None

    raw_config = context_result["raw_config"]
    df = context_result["df"]
    if df.empty:
        st.warning("No raw PI data returned for this incident context window.")
        return None

    render_incident_tag_plot(df, tag, incident_start, incident_end, outlier_thresholds)
    st.caption(
        f"Raw source: `{raw_config.stream_catalog_raw}.{raw_config.source_schema}."
        f"{raw_config.source_table}` | Plot window: {format_period_label(plot_start, plot_end)}"
    )
    return df


def render_incident_ai_analysis(
    incident_id: str,
    incident_rows: pd.DataFrame,
    context_df: pd.DataFrame | None,
    tag: str,
    incident_start: datetime,
    incident_end: datetime,
    outlier_thresholds: tuple[float, float] | None,
) -> None:
    """
    Render an AI-generated incident analysis when requested.

    Args:
        incident_id: Monitor incident identifier.
        incident_rows: Joined monitor incident and quality log rows.
        context_df: Raw PI context rows around the incident.
        tag: Raw PI tag name.
        incident_start: Incident start timestamp.
        incident_end: Incident end timestamp.
        outlier_thresholds: Optional outlier lower and upper thresholds.

    Returns:
        None.
    """
    analyses = st.session_state.setdefault(LLM_INCIDENT_ANALYSIS_STATE_KEY, {})
    if st.button(
        "AI draft analysis",
        key=f"ai_incident_{incident_id}",
        type="secondary",
    ):
        available_tags = load_supervisor_available_tags_for_ui(tag)
        context = build_incident_llm_context(
            incident_id,
            incident_rows,
            context_df,
            tag,
            incident_start,
            incident_end,
            outlier_thresholds,
        )
        analysis = load_supervisor_incident_analysis_for_ui(
            context=context,
            available_tags=available_tags,
        )
        if analysis is not None:
            analyses[incident_id] = analysis

    if incident_id in analyses:
        st.markdown("##### AI incident analysis")
        st.markdown(analyses[incident_id])


def render_quality_incident_detail(
    incident_id: str,
    incident_rows: pd.DataFrame,
    quality_config,
) -> None:
    """
    Render the detail controls and plots for one selected incident.

    Args:
        incident_id: Monitor incident identifier.
        incident_rows: Joined monitor incident and quality log rows.
        quality_config: Data quality runtime configuration.

    Returns:
        None.
    """
    incident = incident_rows.iloc[0]
    tag = str(incident["tag_name"])
    rule_type = str(incident["rule_type"])
    incident_start = pd.to_datetime(incident["incident_start"]).to_pydatetime()
    incident_end = pd.to_datetime(incident["incident_end"]).to_pydatetime()

    detail_cols = st.columns(4)
    detail_cols[0].metric("Rule", rule_type)
    detail_cols[1].metric("Status", str(incident["status"]))
    detail_cols[2].metric("Tag", tag)
    detail_cols[3].metric("Failed windows", len(incident_rows.dropna(subset=["log_run_id"])))

    if tag in TAG_CATALOG:
        render_view_profile_button(incident_id, tag)

    render_quality_log_rows(incident_rows)
    outlier_thresholds = get_latest_outlier_thresholds(incident_rows)
    context_df = render_incident_context_plot(
        tag,
        incident_start,
        incident_end,
        outlier_thresholds,
    )
    render_incident_ai_analysis(
        str(incident_id),
        incident_rows,
        context_df,
        tag,
        incident_start,
        incident_end,
        outlier_thresholds,
    )

    render_incident_feedback_form(str(incident_id), quality_config)


def render_quality_incident_dialog(
    incident_id: str,
    incident_rows: pd.DataFrame,
    quality_config,
) -> None:
    """
    Render one selected incident inside a dismissible modal dialog.

    Args:
        incident_id: Monitor incident identifier.
        incident_rows: Joined monitor incident and quality log rows.
        quality_config: Data quality runtime configuration.

    Returns:
        None.
    """
    incident = incident_rows.iloc[0]
    tag = str(incident["tag_name"])
    rule_type = str(incident["rule_type"])
    incident_start_label = format_nzt_datetime(incident["incident_start"])
    incident_end_label = format_nzt_datetime(incident["incident_end"])
    title = f"{tag} | {rule_type} | {incident_start_label} to {incident_end_label}"

    if not hasattr(st, "dialog"):
        with st.expander(title, expanded=True):
            render_quality_incident_detail(incident_id, incident_rows, quality_config)
        return

    @st.dialog(title, width="large")
    def _dialog() -> None:
        render_quality_incident_detail(incident_id, incident_rows, quality_config)
        if st.button("Close details", key=f"close_incident_{incident_id}"):
            st.session_state[QUALITY_GRID_VERSION_STATE_KEY] = (
                st.session_state.get(QUALITY_GRID_VERSION_STATE_KEY, 0) + 1
            )
            st.rerun()

    _dialog()


def clear_quality_incident_cache() -> None:
    """
    Clear cached incident and raw context queries.

    Args:
        None.

    Returns:
        None.
    """
    load_quality_incidents_for_ui.clear()
    load_incident_tag_history_for_ui.clear()
    st.session_state.pop(QUALITY_CONTEXT_RESULT_STATE_KEY, None)


def render_quality_incident_result(result: dict) -> None:
    """
    Render a stored data quality incident result.

    Args:
        result: Data quality result payload from `load_quality_incident_result`.

    Returns:
        None.
    """
    quality_config = result["quality_config"]
    since_time = result["since_time"]
    df = result["df"]

    if df.empty:
        st.info("No failed data quality incidents were updated in the last week.")
        return

    summary_df = build_quality_incident_summary(df)
    render_quality_incident_metrics(summary_df)
    st.caption(
        f"Monitor source: `{quality_config.monitor_catalog}.{quality_config.monitor_schema}` "
        f"| Since: {format_period_label(since_time, datetime.now(UTC))}"
    )

    display_summary_df = convert_columns_to_nzt_display(
        summary_df,
        [
            "incident_start",
            "incident_end",
            "latest_feedback_ts",
            "incident_update_ts",
        ],
    )
    selected_incident_id = render_incident_summary_grid(display_summary_df)
    incident_groups = dict(tuple(df.groupby("incident_id", sort=False)))
    if selected_incident_id is None:
        st.caption("Select an incident row to open its details, plot, AI draft, and feedback form.")
        return

    if selected_incident_id not in incident_groups:
        st.warning("The selected incident is no longer available in the current result set.")
        return

    render_quality_incident_dialog(
        selected_incident_id,
        incident_groups[selected_incident_id],
        quality_config,
    )


def render_quality_incidents_section(refresh_incidents: bool = False) -> None:
    """
    Render recent failed data quality incidents and manual feedback controls.

    Args:
        refresh_incidents: Reload incident results when requested.

    Returns:
        None.
    """
    st.subheader("Data quality incidents")
    st.caption(
        f"Failed KAG monitor incidents updated in the last {QUALITY_INCIDENT_LOOKBACK_DAYS} days. "
        f"The monitoring job runs every {QUALITY_MONITOR_REFRESH_MINUTES} minutes."
    )

    stored_result = get_session_result(QUALITY_RESULT_STATE_KEY)
    if refresh_incidents or stored_result is None:
        if refresh_incidents:
            clear_quality_incident_cache()

        try:
            loaded_result = load_quality_incident_result()
        except Exception as exc:
            st.error("Failed to load data quality incidents.")
            with st.expander("Technical detail"):
                st.exception(exc)
            if stored_result is None:
                return
        else:
            set_session_result(QUALITY_RESULT_STATE_KEY, loaded_result)
            stored_result = loaded_result
            if refresh_incidents:
                st.toast("Incident data refreshed.")

    render_quality_incident_result(stored_result)


def main() -> None:
    """
    Run the KAG agent data profiling Streamlit app.

    Args:
        None.

    Returns:
        None.
    """
    st.set_page_config(page_title="KAG Agent Data Profiling", layout="wide")
    st.title("KAG Agent Data Profiling")
    selected_section = render_section_navigation()

    if selected_section == QUALITY_INCIDENTS_SECTION:
        refresh_incidents = render_quality_sidebar()
        render_quality_incidents_section(refresh_incidents)
        return

    if selected_section == TAG_PROFILING_SECTION:
        selected_tags, start_time, end_time, run_query = render_profiling_sidebar()
        render_profiling_section(selected_tags, start_time, end_time, run_query)
        return

    (
        comparison_tags,
        comparison_start_time,
        comparison_end_time,
        comparison_plot_type,
        comparison_colour_tag,
        run_comparison,
    ) = render_comparison_sidebar()
    render_comparison_section(
        comparison_tags,
        comparison_start_time,
        comparison_end_time,
        comparison_plot_type,
        comparison_colour_tag,
        run_comparison,
    )


if __name__ == "__main__":
    main()
