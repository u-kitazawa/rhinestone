from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import rdflib

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Format, FormatPreset, Provider, configure
from rhinestone.adapters.source._ckan import matches_query_formats
from rhinestone.adapters.source.ckan import CkanAdapter
from rhinestone.adapters.source.search_ckan_jp import SearchCkanJpAdapter
from rhinestone.catalogs import Catalog
from rhinestone.errors import ConfigValidationError
from rhinestone.models import SearchQuery


def _app():
    return configure(
        catalog=Catalog(
            (
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
                                    {
                                        "uri": "https://example.test/a.csv",
                                        "format": "csv",
                                    }
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
    )


def test_format_search_post_filters_with_or_semantics() -> None:
    results = _app().search(format=(Format.GEOJSON, Format.CSV))
    assert {result.title for result in results} == {"Vector", "Table"}


def test_dcat_search_filters_declared_distribution_format_before_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = (
        Path(__file__).parent / "fixtures" / "expansion" / "catalog.ttl"
    ).read_text(encoding="utf-8")

    def get_document(uri: str) -> str:
        return document

    monkeypatch.setattr(_http, "get_text", get_document)
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "rdf",
                    "dcat",
                    {"catalog_uri": "https://fixture.example/catalog"},
                ),
            )
        ),
        dependencies={"rdflib": rdflib},
    )

    assert app.search(limit=1)[0].format == "geojson"
    results = app.search(format=(Format.GPKG,), limit=1)
    assert [resource.format for resource in results] == ["gpkg"]
    assert results[0].formats == frozenset({"gpkg"})
    assert not app.search(format=(Format.UNKNOWN,))


def test_estat_gis_search_filters_index_format_before_limit() -> None:
    distributions = [
        {
            "distribution_id": name,
            "dataset_id": "boundaries",
            "boundary_kind": "administrative",
            "survey_year": 2020,
            "level": "municipality",
            "uri": f"https://fixture.example/{name}",
            "format": name,
        }
        for name in ("gml", "kml")
    ]
    app = configure(
        catalog=Catalog(
            (Provider("gis", "estat-gis", {"distributions": distributions}),)
        )
    )

    assert app.search(limit=1)[0].format == "gml"
    results = app.search(format=(Format.KML,), limit=1)
    assert [resource.format for resource in results] == ["kml"]
    assert results[0].formats == frozenset({"kml"})
    assert not app.search(format=(Format.UNKNOWN,))


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
    result = replace(result, format="vendor-format", access_plan=None)
    assert not search_module._result_formats(result)  # pyright: ignore[reportPrivateUsage]


def test_ckan_format_filter_uses_selected_resource_and_keeps_paging() -> None:
    calls: list[dict[str, object]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, object]:
        calls.append(dict(params))
        start = params.get("start", 0)
        resource = (
            {"id": "csv", "url": "https://example.test/a.csv", "format": "CSV"}
            if start == 0
            else {
                "id": "geojson",
                "url": "https://example.test/a.geojson",
                "format": "GeoJSON",
            }
        )
        sibling = {
            "id": "sibling",
            "url": "https://example.test/sibling.geojson",
            "format": "GeoJSON",
        }
        return {
            "success": True,
            "result": {
                "count": 2,
                "results": [
                    {
                        "id": f"package-{start}",
                        "resources": [resource, sibling] if start == 0 else [resource],
                    }
                ],
            },
        }

    results = CkanAdapter(get_json, endpoint="https://example.test").search(
        SearchQuery(format=(Format.GEOJSON,), limit=1)
    )
    assert results[0].provenance.resource_identifier == "sibling"
    assert results[0].formats == frozenset({"geojson"})


def test_native_format_matchers_handle_unknown_explicitly() -> None:
    query = SearchQuery(format=(Format.UNKNOWN,))
    assert matches_query_formats(frozenset(), query)
    assert SearchCkanJpAdapter._matches_query_formats(  # pyright: ignore[reportPrivateUsage]
        frozenset(), query
    )


def test_search_ckan_format_filter_rejects_non_matching_resource() -> None:
    response = {
        "success": True,
        "result": {
            "count": 1,
            "results": [
                {
                    "id": "package",
                    "title": "Dataset",
                    "resources": [
                        {
                            "id": "csv",
                            "url": "https://example.test/a.csv",
                            "format": "CSV",
                        }
                    ],
                }
            ],
        },
    }
    adapter = SearchCkanJpAdapter(lambda url, params: response)
    assert not adapter.search(
        SearchQuery(text="dataset", format=(Format.GEOJSON,), limit=1)
    )
