from collections.abc import Mapping
from typing import Any, cast

import pytest

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Provider, configure
from rhinestone.adapters.source.mlit_dpf import MlitDpfAdapter
from rhinestone.api import (
    _validate_mlit_dpf_targets,  # pyright: ignore[reportPrivateUsage]
)
from rhinestone.errors import (
    ConfigValidationError,
    ExecutionAdapterUnavailableError,
    ProviderResponseError,
    UnsupportedSourceError,
)
from rhinestone.models import Config, SearchQuery
from rhinestone.registry import CredentialRegistry


def _record(**metadata: Any) -> dict[str, Any]:
    return {
        "id": "data-1",
        "title": "道路データ",
        "dataset_id": "dataset-1",
        "catalog_id": "catalog-1",
        "metadata": metadata,
    }


def _response(*records: Mapping[str, Any]) -> dict[str, Any]:
    return {"data": {"search": {"searchResults": list(records)}}}


def _adapter(
    response: Any,
    *,
    target_rules: object = (),
    representations: object = None,
    calls: list[tuple[Any, ...]] | None = None,
) -> MlitDpfAdapter:
    def post_json(*args: Any, **kwargs: Any) -> Any:
        if calls is not None:
            calls.append((*args, kwargs))
        return response

    return MlitDpfAdapter(
        post_json,
        CredentialRegistry({"mlit-dpf": lambda: "top-secret"}),
        "dpf",
        target_rules=target_rules,
        representations=representations,
    )


def test_search_prefers_dataset_specific_native_target_and_builds_graphql() -> None:
    calls: list[tuple[Any, ...]] = []
    rules = [
        {
            "catalog_id": "catalog-1",
            "source_id": "catalog-target",
            "settings": {"resource_id": {"metadata": "native_id"}},
        },
        {
            "catalog_id": "catalog-1",
            "dataset_id": "dataset-1",
            "source_id": "dataset-target",
            "settings": {
                "dataset_id": {"record": "dataset_id"},
                "resource_id": {"metadata": "native_id"},
            },
        },
    ]
    adapter = _adapter(
        _response(_record(native_id="resource-1")),
        target_rules=rules,
        calls=calls,
    )

    results = adapter.search(
        SearchQuery(text='道"路', bbox=(130, 30, 140, 40), limit=3)
    )

    assert len(results) == 1
    assert results[0].target == Config(
        "dataset-target",
        {"dataset_id": "dataset-1", "resource_id": "resource-1"},
    )
    assert results[0].provenance.dataset_identifier == "dataset-1"
    assert results[0].provenance.resource_identifier == "data-1"
    assert results[0].raw_metadata["catalog_id"] == "catalog-1"
    endpoint, body, headers, options = calls[0]
    assert endpoint == "https://data-platform.mlit.go.jp/api/v1"
    assert headers == {"apikey": "top-secret"}
    assert options == {"credential": "mlit-dpf"}
    query = body["query"]
    assert 'term: "道\\"路"' in query
    assert "size: 3" in query
    assert "topLeft: { lat: 40, lon: 130 }" in query
    assert "bottomRight: { lat: 30, lon: 140 }" in query
    assert "top-secret" not in repr(results)


def test_missing_native_value_falls_back_to_explicit_download_representation() -> None:
    adapter = _adapter(
        _response(
            _record(
                **{
                    "DPF:downloadURLs": [
                        "https://downloads.example/roads.gpkg",
                        "https://downloads.example/roads-2.gpkg",
                    ],
                    "DPF:dataURLs": ["https://landing.example/roads"],
                }
            )
        ),
        target_rules=[
            {
                "catalog_id": "catalog-1",
                "source_id": "ckan",
                "settings": {"resource_id": {"metadata": "missing"}},
            }
        ],
        representations={
            "dataset-1": {
                "format": "GeoPackage",
                "media_type": "application/geopackage+sqlite3",
                "archive": "zip",
            }
        },
    )

    results = adapter.search(SearchQuery(limit=1))

    assert len(results) == 1
    assert results[0].target.source_id == "direct"
    assert results[0].target.settings["uri"] == ("https://downloads.example/roads.gpkg")
    assert results[0].target.settings["format"] == "gpkg"
    assert results[0].target.settings["archive"] == "zip"


def test_direct_fallback_accepts_case_insensitive_http_scheme() -> None:
    adapter = _adapter(
        _response(
            _record(**{"DPF:downloadURLs": ["HTTPS://downloads.example/roads.gpkg"]})
        ),
        representations={"dataset-1": {"format": "gpkg"}},
    )

    result = adapter.search(SearchQuery())[0]

    assert result.target.settings["uri"] == "HTTPS://downloads.example/roads.gpkg"


def test_landing_page_or_unknown_representation_is_omitted_and_zero_skips_post() -> (
    None
):
    calls: list[tuple[Any, ...]] = []
    adapter = _adapter(
        _response(_record(**{"DPF:dataURLs": ["https://landing.example/data"]})),
        calls=calls,
    )

    assert adapter.search(SearchQuery()) == ()
    assert len(calls) == 1
    calls.clear()
    assert adapter.search(SearchQuery(limit=0)) == ()
    assert calls == []


def test_null_metadata_and_nonmatching_rules_are_safely_omitted() -> None:
    record = _record()
    record["metadata"] = None
    record["title"] = None
    adapter = _adapter(
        _response(record),
        target_rules=[
            {
                "catalog_id": "other-catalog",
                "source_id": "target",
                "settings": {"id": {"record": "id"}},
            },
            {
                "catalog_id": "catalog-1",
                "dataset_id": "other-dataset",
                "source_id": "target",
                "settings": {"id": {"record": "id"}},
            },
        ],
        representations={"dataset-1": {"format": "geojson"}},
    )

    assert adapter.search(SearchQuery()) == ()


@pytest.mark.parametrize(
    "response, message",
    (
        ({"errors": [{"message": "bad"}]}, "contains errors"),
        ([], "response root"),
        ({"data": None}, "data"),
        ({"data": {"search": None}}, "search result"),
        ({"data": {"search": {}}}, "searchResults"),
        (_response({"id": "x"}), "dataset_id"),
        (
            _response(
                {
                    "id": "data-1",
                    "dataset_id": "dataset-1",
                    "catalog_id": "catalog-1",
                    "metadata": [],
                }
            ),
            "record metadata",
        ),
    ),
)
def test_invalid_provider_responses_are_classified(response: Any, message: str) -> None:
    with pytest.raises(ProviderResponseError, match=message):
        _adapter(response).search(SearchQuery())


@pytest.mark.parametrize(
    "metadata, message",
    (
        ({"DPF:downloadURLs": "https://example.test/data"}, "array"),
        ({"DPF:downloadURLs": ["file:///tmp/data"]}, "safe HTTP"),
        ({"DPF:downloadURLs": ["https://user:pass@example.test/data"]}, "safe HTTP"),
    ),
)
def test_direct_fallback_rejects_invalid_download_urls(
    metadata: Mapping[str, Any], message: str
) -> None:
    adapter = _adapter(
        _response(_record(**metadata)),
        representations={"dataset-1": {"format": "geojson"}},
    )
    with pytest.raises(ProviderResponseError, match=message):
        adapter.search(SearchQuery())


@pytest.mark.parametrize(
    "bbox",
    (
        (float("nan"), 0, 1, 1),
        (10, 0, 0, 1),
        (0, -91, 1, 1),
        (0, 0, 181, 1),
    ),
)
def test_bbox_validation_rejects_unsafe_coordinates(
    bbox: tuple[float, float, float, float],
) -> None:
    with pytest.raises(ConfigValidationError, match="bbox"):
        _adapter(_response()).search(SearchQuery(bbox=bbox))


def test_load_is_explicitly_unsupported() -> None:
    with pytest.raises(UnsupportedSourceError, match="discovery-only"):
        _adapter(_response()).load(Config("mlit-dpf", {}))


def test_time_is_reported_as_unsupported_search_diagnostic() -> None:
    app = configure(
        sources=(
            Provider(
                "dpf",
                "mlit-dpf",
                {
                    "endpoint": "https://data-platform.mlit.go.jp/api/v1",
                    "credential": "mlit-dpf",
                    "target_rules": [],
                    "representations": {},
                },
            ),
        ),
        credentials={"mlit-dpf": lambda: "secret"},
    )
    from datetime import datetime

    results = app.search(SearchQuery(time=(datetime(2024, 1, 1), None)))

    assert len(results) == 0
    assert results.diagnostics[0].source_id == "dpf"
    assert results.diagnostics[0].skipped_conditions == frozenset({"time"})


def test_direct_result_resolves_with_discovery_and_requires_explicit_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[Any, ...]] = []

    def post_json(*args: Any, **kwargs: Any) -> Any:
        requests.append((*args, kwargs))
        return _response(
            _record(**{"DPF:downloadURLs": ["https://downloads.example/roads.gpkg"]})
        )

    class PyogrioRuntime:
        def read_dataframe(self, uri: str, **options: Any) -> str:
            assert options == {}
            return "opened:" + uri

    monkeypatch.setattr(_http, "post_json", post_json)
    app = configure(
        sources=(
            Provider(
                "dpf",
                "mlit-dpf",
                {
                    "endpoint": "https://data-platform.mlit.go.jp/api/v1",
                    "credential": "mlit-dpf",
                    "target_rules": [],
                    "representations": {"dataset-1": {"format": "gpkg"}},
                },
            ),
        ),
        credentials={"mlit-dpf": lambda: "secret-value"},
        dependencies={"pyogrio": PyogrioRuntime()},
    )

    result = app.search(text="道路", limit=1)[0]
    resource = app.resolve(result)

    assert result.discovered_by == "dpf"
    assert resource.discovery is not None
    assert resource.discovery.source_id == "dpf"
    assert resource.discovery.provenance.provider == "dpf"
    assert resource.open("pyogrio") == ("opened:https://downloads.example/roads.gpkg")
    with pytest.raises(ExecutionAdapterUnavailableError):
        app.open(result, "rasterio")
    assert "secret-value" not in repr(result)
    assert requests[0][2] == {"apikey": "secret-value"}


def test_configure_rejects_unknown_and_self_delegation_targets() -> None:
    settings: dict[str, Any] = {
        "endpoint": "https://data-platform.mlit.go.jp/api/v1",
        "credential": "mlit-dpf",
        "representations": {},
    }
    with pytest.raises(ConfigValidationError, match="unconfigured source"):
        configure(
            sources=(
                Provider(
                    "dpf",
                    "mlit-dpf",
                    {
                        **settings,
                        "target_rules": [
                            {
                                "catalog_id": "c",
                                "source_id": "missing",
                                "settings": {"id": {"record": "id"}},
                            }
                        ],
                    },
                ),
            )
        )
    with pytest.raises(ConfigValidationError, match="itself"):
        configure(
            sources=(
                Provider(
                    "dpf",
                    "mlit-dpf",
                    {
                        **settings,
                        "target_rules": [
                            {
                                "catalog_id": "c",
                                "source_id": "dpf",
                                "settings": {"id": {"record": "id"}},
                            }
                        ],
                    },
                ),
            )
        )
    with pytest.raises(ConfigValidationError, match="must not target direct"):
        configure(
            sources=(
                Provider(
                    "dpf",
                    "mlit-dpf",
                    {
                        **settings,
                        "target_rules": [
                            {
                                "catalog_id": "c",
                                "source_id": "direct",
                                "settings": {"uri": {"record": "id"}},
                            }
                        ],
                    },
                ),
            )
        )
    with pytest.raises(ConfigValidationError, match="discovery-only Provider"):
        configure(
            sources=(
                Provider(
                    "dpf-a",
                    "mlit-dpf",
                    {
                        **settings,
                        "target_rules": [
                            {
                                "catalog_id": "c",
                                "source_id": "dpf-b",
                                "settings": {"id": {"record": "id"}},
                            }
                        ],
                    },
                ),
                Provider(
                    "dpf-b",
                    "mlit-dpf",
                    {**settings, "target_rules": []},
                ),
            )
        )
    with pytest.raises(ConfigValidationError, match="discovery-only Provider"):
        configure(
            sources=(
                Provider(
                    "dpf",
                    "mlit-dpf",
                    {
                        **settings,
                        "target_rules": [
                            {
                                "catalog_id": "c",
                                "source_id": "search",
                                "settings": {"id": {"record": "id"}},
                            }
                        ],
                    },
                ),
                Provider(
                    "search",
                    "search-ckan-jp",
                    {"endpoint": "https://search.ckan.jp/backend/api"},
                ),
            )
        )


@pytest.mark.parametrize(
    "options, message",
    cast(
        tuple[tuple[Mapping[str, Any], str], ...],
        (
            ({"credential": ""}, "credential"),
            ({"credential": 1}, "credential"),
            ({"target_rules": {}}, "target_rules"),
            ({"target_rules": [1]}, "each mlit-dpf target rule"),
            (
                {
                    "target_rules": [
                        {
                            "catalog_id": "c",
                            "source_id": "s",
                            "settings": {"id": {"record": "id"}},
                            "extra": True,
                        }
                    ]
                },
                "unknown mlit-dpf target rule",
            ),
            (
                {
                    "target_rules": [
                        {
                            "catalog_id": "c",
                            "dataset_id": 1,
                            "source_id": "s",
                            "settings": {"id": {"record": "id"}},
                        }
                    ]
                },
                "dataset_id",
            ),
            (
                {
                    "target_rules": [
                        {
                            "catalog_id": "c",
                            "source_id": "s",
                            "settings": {"id": {"record": "id"}},
                        },
                        {
                            "catalog_id": "c",
                            "source_id": "s2",
                            "settings": {"id": {"record": "id"}},
                        },
                    ]
                },
                "ambiguous duplicate",
            ),
            (
                {
                    "target_rules": [
                        {"catalog_id": "c", "source_id": "s", "settings": {}}
                    ]
                },
                "settings must be",
            ),
            (
                {
                    "target_rules": [
                        {
                            "catalog_id": "c",
                            "source_id": "s",
                            "settings": {1: {"record": "id"}},
                        }
                    ]
                },
                "named objects",
            ),
            (
                {
                    "target_rules": [
                        {
                            "catalog_id": "c",
                            "source_id": "s",
                            "settings": {"id": {"record": "id", "metadata": "id"}},
                        }
                    ]
                },
                "exactly one",
            ),
            (
                {
                    "target_rules": [
                        {
                            "catalog_id": "c",
                            "source_id": "s",
                            "settings": {"id": {"record": ""}},
                        }
                    ]
                },
                "selector value",
            ),
            (
                {
                    "target_rules": [
                        {
                            "catalog_id": "",
                            "source_id": "s",
                            "settings": {"id": {"record": "id"}},
                        }
                    ]
                },
                "catalog_id",
            ),
            ({"representations": []}, "representations must"),
            ({"representations": {1: {"format": "gpkg"}}}, "dataset ids"),
            ({"representations": {"d": "gpkg"}}, "representation must"),
            (
                {"representations": {"d": {"format": "gpkg", "extra": 1}}},
                "unknown mlit-dpf representation",
            ),
            ({"representations": {"d": {}}}, "format"),
            (
                {"representations": {"d": {"format": "gpkg", "media_type": ""}}},
                "media_type",
            ),
        ),
    ),
)
def test_invalid_adapter_configuration_is_rejected(
    options: Mapping[str, Any], message: str
) -> None:
    with pytest.raises(ConfigValidationError, match=message):
        MlitDpfAdapter(
            lambda *_args, **_kwargs: _response(),
            CredentialRegistry({"mlit-dpf": lambda: "secret"}),
            "dpf",
            **options,
        )


def test_source_transport_failure_is_metadata_diagnostic_without_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("secret-value")

    monkeypatch.setattr(_http, "post_json", fail)
    app = configure(
        sources=(
            Provider(
                "dpf",
                "mlit-dpf",
                {
                    "endpoint": "https://data-platform.mlit.go.jp/api/v1",
                    "credential": "mlit-dpf",
                    "target_rules": [],
                    "representations": {},
                },
            ),
        ),
        credentials={"mlit-dpf": lambda: "secret-value"},
    )

    results = app.search(text="roads")

    assert results.diagnostics[0].failure_type == "metadata"
    assert "secret-value" not in repr(results.diagnostics)


def test_missing_default_dpf_credential_is_isolated_as_search_diagnostic() -> None:
    app = configure(
        sources=(
            Provider(
                "dpf",
                "mlit-dpf",
                {
                    "endpoint": "https://data-platform.mlit.go.jp/api/v1",
                    "credential": "mlit-dpf",
                    "target_rules": [],
                    "representations": {},
                },
            ),
        )
    )

    results = app.search(text="roads")

    assert len(results) == 0
    assert results.diagnostics[0].source_id == "dpf"
    assert results.diagnostics[0].failure_type == "credential"


def test_target_prevalidation_ignores_malformed_rules_for_adapter_validation() -> None:
    _validate_mlit_dpf_targets(
        (
            Provider("other", "static", {"items": {}}),
            Provider("dpf", "mlit-dpf", {"target_rules": "bad"}),
            Provider("dpf-2", "mlit-dpf", {"target_rules": [1]}),
            Provider(
                "dpf-3",
                "mlit-dpf",
                {
                    "target_rules": [
                        {
                            "catalog_id": "catalog",
                            "source_id": "native",
                            "settings": {"uri": {"record": "id"}},
                        }
                    ]
                },
            ),
            Provider("native", "ckan", {"endpoint": "https://example.test/ckan"}),
        )
    )
