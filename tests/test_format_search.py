from rhinestone import Format, FormatPreset, Provider, configure
from rhinestone.errors import ConfigValidationError
from rhinestone.models import Config, SearchQuery


def _app():
    return configure(
        sources=(
            Provider(
                "formats",
                "static",
                {
                    "items": {
                        "vector": {
                            "metadata": {"title": "Vector"},
                            "candidates": [
                                {
                                    "uri": "https://example.test/a.geojson",
                                    "format": "GeoJSON",
                                }
                            ],
                        },
                        "table": {
                            "metadata": {"title": "Table"},
                            "candidates": [
                                {"uri": "https://example.test/a.csv", "format": "csv"}
                            ],
                        },
                        "unknown": {
                            "metadata": {"title": "Unknown"},
                            "candidates": [
                                {"uri": "https://example.test/a", "format": None}
                            ],
                        },
                    }
                },
            ),
        )
    )


def test_format_search_post_filters_with_or_semantics() -> None:
    results = _app().search(format=(Format.GEOJSON, Format.CSV))
    assert {result.title for result in results} == {"Vector", "Table"}


def test_format_preset_uses_execution_format_registry() -> None:
    results = _app().search(format=(FormatPreset.PYOGRIO,))
    assert [result.title for result in results] == ["Vector"]


def test_unknown_format_is_only_included_explicitly() -> None:
    assert [result.title for result in _app().search(format=(Format.UNKNOWN,))] == [
        "Unknown"
    ]
    assert not _app().search(format=(Format.GEOTIFF,))


def test_post_filter_applies_limit_after_filtering() -> None:
    results = _app().search(format=(Format.CSV,), limit=1)
    assert [result.title for result in results] == ["Table"]


def test_format_query_requires_non_empty_typed_tuple() -> None:
    query = SearchQuery(format=(Format.GML, FormatPreset.PYOGRIO))
    assert Format.GML in query.expanded_formats


def test_format_query_rejects_invalid_values() -> None:
    import pytest

    with pytest.raises(ConfigValidationError, match="format must"):
        SearchQuery(format=())


def test_unregistered_explicit_format_counts_as_unknown() -> None:
    from dataclasses import replace
    from importlib import import_module

    search_module = import_module("rhinestone.search")

    result = _app().search()[0]
    result = replace(
        result,
        target=Config("formats", {"format": "vendor-format"}),
        raw_metadata={"format": 1, "nested": [{"format": ""}]},
    )
    assert not search_module._result_formats(result)  # pyright: ignore[reportPrivateUsage]
