import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_ROOT))

from agent_data_profiling.tag_catalog import (  # noqa: E402
    DEFAULT_TAGS,
    MAX_SELECTED_TAGS,
    TAG_CATALOG,
    TagMetadata,
    get_catalog_tags,
    validate_selected_tags,
)


def test_catalog_contains_defaults() -> None:
    assert DEFAULT_TAGS == ()

    for tag in DEFAULT_TAGS:
        assert tag in TAG_CATALOG


def test_catalog_tags_are_unique_and_metadata_is_complete() -> None:
    tags = get_catalog_tags()

    assert len(tags) == len(set(tags))
    assert len(tags) >= 40

    for tag in tags:
        metadata = TAG_CATALOG[tag]
        assert isinstance(metadata, TagMetadata)
        assert metadata.name == tag
        assert metadata.display_name
        assert metadata.unit is not None
        assert metadata.process_area is not None
        assert metadata.description is not None
        assert isinstance(metadata.related_tags, tuple)
        assert metadata.kg_node_id is None or metadata.kg_node_id


def test_validate_selected_tags_accepts_one_to_four_catalog_tags() -> None:
    selected = validate_selected_tags(["Gross_Generator_Output", "Net_Power"])

    assert selected == ("Gross_Generator_Output", "Net_Power")


def test_validate_selected_tags_rejects_empty_selection() -> None:
    try:
        validate_selected_tags([])
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("Expected empty tag selection to fail")


def test_validate_selected_tags_rejects_more_than_four_tags() -> None:
    selected = list(get_catalog_tags()[: MAX_SELECTED_TAGS + 1])

    try:
        validate_selected_tags(selected)
    except ValueError as exc:
        assert "no more than 4" in str(exc)
    else:
        raise AssertionError("Expected too many selected tags to fail")


def test_validate_selected_tags_rejects_unknown_tags() -> None:
    try:
        validate_selected_tags(["Gross_Generator_Output", "Injected_Bad_Tag"])
    except ValueError as exc:
        assert "Injected_Bad_Tag" in str(exc)
    else:
        raise AssertionError("Expected unknown tag selection to fail")
