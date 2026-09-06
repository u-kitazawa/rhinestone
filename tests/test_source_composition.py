from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pytest
import rdflib

from rhinestone import _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Config, SearchQuery, SourceDefinition, configure, sources
from rhinestone.api import _build_source_adapter  # pyright: ignore[reportPrivateUsage]
from rhinestone.errors import ConfigValidationError
from rhinestone.registry import CredentialRegistry, DependencyRegistry
from tests.provider_support import fixture_json


@pytest.mark.parametrize(
    "source",
    (
        SourceDefinition("stac-source", "stac", {"endpoint": "https://stac.test"}),
        SourceDefinition(
            "ogc-source",
            "ogc-features",
            {"endpoint": "https://ogc.test", "collection_id": "rivers"},
        ),
        SourceDefinition("plateau-source", "plateau", sources.PLATEAU.settings),
        SourceDefinition("fundamental-source", "gsi-fundamental"),
        SourceDefinition("dcat-source", "dcat"),
        SourceDefinition("odpt-source", "odpt", sources.ODPT.settings),
    ),
)
def test_advanced_source_definitions_compose(source: SourceDefinition) -> None:
    configure(sources=(source,))


def test_dcat_dependencies_are_lazy_and_source_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = (
        Path(__file__).parent / "fixtures" / "expansion" / "catalog.ttl"
    ).read_text()

    def get_document(uri: str) -> str:
        return document

    monkeypatch.setattr(_http, "get_text", get_document)
    app = configure(
        sources=(SourceDefinition("catalog", "dcat"),),
        dependencies={"rdflib": lambda: rdflib},
    )
    resource = app.resolve(
        Config(
            "catalog",
            {
                "uri": "https://fixture.example/catalog",
                "dataset": "https://fixture.example/dataset",
                "distribution": "https://fixture.example/geojson",
                "serialization": "turtle",
            },
        )
    )
    assert resource.uri == "https://fixture.example/rivers.geojson"


def test_source_options_reject_unknown_values() -> None:
    with pytest.raises(ConfigValidationError, match="typo"):
        configure(
            sources=(
                SourceDefinition(
                    "catalog", "ckan", {"endpoint": "https://example.test", "typo": 1}
                ),
            )
        )


def test_configured_json_transport_supports_adapter_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = "https://catalog.example"
    search_url = endpoint + "/api/3/action/package_search"
    seen: Dict[str, Any] = {}

    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        seen["headers"] = headers
        return fixture_json("ckan/package_search.json")

    monkeypatch.setattr(_http, "get_json", get_json)
    adapter = _build_source_adapter(
        SourceDefinition("catalog", "ckan", {"endpoint": endpoint}),
        DependencyRegistry({}),
        CredentialRegistry({}),
    )
    adapter._headers["X-Test"] = "value"  # type: ignore[attr-defined]
    adapter.search(SearchQuery(limit=1))  # type: ignore[attr-defined]
    assert seen["headers"] == {"X-Test": "value"}
    assert search_url
