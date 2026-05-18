import pandas as pd

from agent_data_profiling.tag_catalog import TAG_CATALOG, validate_selected_tags


_COMPARISON_PLOT_MODES = {
    "Line": "line",
    "Scatter": "scatter",
}
XY_TAG_COUNT = 2


def build_comparison_frame(
    df: pd.DataFrame,
    tags: list[str] | tuple[str, ...],
) -> pd.DataFrame:
    """
    Convert selected raw tag columns into a long-form comparison frame.

    Args:
        df: DataFrame containing `Pi_Timestamp` and selected tag columns.
        tags: Raw tag column names to compare.

    Returns:
        pd.DataFrame: Long-form points with timestamp, raw tag, display name, and value.

    Raises:
        ValueError: If the selected tags are invalid.
        KeyError: If the input DataFrame is missing required columns.
    """
    selected_tags = validate_selected_tags(tags)

    comparison_df = df.melt(
        id_vars="Pi_Timestamp",
        value_vars=list(selected_tags),
        var_name="tag",
        value_name="value",
    )
    comparison_df["display_name"] = comparison_df["tag"].map(
        lambda tag: TAG_CATALOG[tag].display_name
    )

    return comparison_df[["Pi_Timestamp", "tag", "display_name", "value"]]


def validate_xy_tags(tags: list[str] | tuple[str, ...]) -> tuple[str, str]:
    """
    Validate comparison tags used as x and y axes.

    Args:
        tags: User-selected raw tag column names.

    Returns:
        tuple[str, str]: Validated x-axis tag followed by y-axis tag.

    Raises:
        ValueError: If the selection does not contain exactly 2 catalog tags.
    """
    selected_tags = tuple(tags)
    if len(selected_tags) != XY_TAG_COUNT:
        raise ValueError(f"Select exactly {XY_TAG_COUNT} tags for comparison.")

    return validate_selected_tags(selected_tags)


def build_scatter_comparison_frame(
    df: pd.DataFrame,
    xy_tags: list[str] | tuple[str, ...],
    colour_tag: str,
) -> pd.DataFrame:
    """
    Build a wide-form comparison frame for x/y scatter plots.

    Args:
        df: DataFrame containing `Pi_Timestamp`, x tag, y tag, and colour tag columns.
        xy_tags: Exactly two raw tag column names for x and y axes.
        colour_tag: Raw tag column name used to colour scatter points.

    Returns:
        pd.DataFrame: Wide-form points with timestamp, x tag, y tag, and colour tag.

    Raises:
        ValueError: If selected tags are invalid.
        KeyError: If the input DataFrame is missing required columns.
    """
    x_tag, y_tag = validate_xy_tags(xy_tags)
    selected_colour_tag = validate_selected_tags([colour_tag])[0]

    return df[["Pi_Timestamp", x_tag, y_tag, selected_colour_tag]]


def get_comparison_plot_mode(plot_type: str) -> str:
    """
    Map a UI comparison plot type to the Plotly rendering mode.

    Args:
        plot_type: UI plot type label.

    Returns:
        str: Plot mode identifier.

    Raises:
        ValueError: If the plot type is unsupported.
    """
    try:
        return _COMPARISON_PLOT_MODES[plot_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported comparison plot type: {plot_type}") from exc
