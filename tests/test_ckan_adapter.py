import pytest

from rhinestone.adapters.execution.pyogrio import PyogrioAdapter
from rhinestone.adapters.source.ckan import CkanAdapter
from rhinestone.errors import ProviderResponseError
from rhinestone.models import Config, SearchQuery
from rhinestone.resolution import Resolver
from tests.provider_support import RecordingJsonClient, fixture_json


def test_ckan_resource_and_package_responses_become_a_complete_source() -> None:
    endpoint = "https://catalog.example"
    resource_url = endpoint + "/api/3/action/resource_show"
    package_url = endpoint + "/api/3/action/package_show"
    client = RecordingJsonClient(
        {
            resource_url: fixture_json("ckan/resource_show.json"),
            package_url: fixture_json("ckan/package_show.json"),
        }
    )
    adapter = CkanAdapter(get_json=client)
    source = adapter.load(
        Config("ckan", {"endpoint": endpoint, "resource_id": "resource-1"})
    )
    assert client.calls == [
        (resource_url, {"id": "resource-1"}),
        (package_url, {"id": "dataset-1"}),
    ]
    assert source.metadata.title == "River Dataset"
    assert source.metadata.publisher == "River Agency"
    assert source.metadata.license == "CC BY 4.0"
    assert source.candidates[0].uri == "https://files.example/river.csv"
    assert source.candidates[0].format == "csv"
    assert source.provenance.dataset_identifier == "dataset-1"
    assert source.provenance.resource_identifier == "resource-1"
    assert source.raw_metadata["resource"]["encoding"] == "utf-8"
    assert source.raw_metadata["package"]["extras"][0]["key"] == "frequency"


@pytest.mark.parametrize(
    ("advertised", "expected"),
    (
        ("GeoPackage", "gpkg"),
        ("gpkg", "gpkg"),
        ("GeoJSON", "geojson"),
        ("FlatGeobuf", "flatgeobuf"),
        ("Shapefile", "shapefile"),
        (None, None),
    ),
)
def test_ckan_canonicalizes_formats_without_losing_provider_metadata(
    advertised: object, expected: object
) -> None:
    endpoint = "https://catalog.example"
    resource_url = endpoint + "/api/3/action/resource_show"
    package_url = endpoint + "/api/3/action/package_show"
    client = RecordingJsonClient(
        {
            resource_url: {
                "success": True,
                "result": {
                    "id": "resource-1",
                    "package_id": "dataset-1",
                    "format": advertised,
                    "mimetype": "application/octet-stream",
                    "url": "https://files.example/vector",
                },
            },
            package_url: {"success": True, "result": {"id": "dataset-1"}},
        }
    )

    source = CkanAdapter(get_json=client).load(
        Config("ckan", {"endpoint": endpoint, "resource_id": "resource-1"})
    )

    assert source.candidates[0].format == expected
    assert source.candidates[0].attributes["format"] == advertised
    assert source.raw_metadata["resource"]["format"] == advertised
    if expected is not None:
        resource = Resolver().resolve(source)
        assert resource.format == expected
        assert PyogrioAdapter().supports(resource, frozenset({"pyogrio"}))


def test_ckan_search_uses_package_search_and_returns_resolvable_config() -> None:
    endpoint = "https://catalog.example"
    search_url = endpoint + "/api/3/action/package_search"
    client = RecordingJsonClient({search_url: fixture_json("ckan/package_search.json")})
    adapter = CkanAdapter(endpoint=endpoint, get_json=client)
    results = adapter.search(SearchQuery(text="river", limit=5))
    assert client.calls == [(search_url, {"q": "river", "rows": 5})]
    assert len(results) == 1
    assert results[0].to_config() == Config("ckan", {"resource_id": "resource-1"})
    assert "endpoint" not in results[0].target.settings
    assert results[0].metadata.raw["id"] == "dataset-1"


def test_ckan_unsuccessful_action_response_is_rejected() -> None:
    endpoint = "https://catalog.example"
    resource_url = endpoint + "/api/3/action/resource_show"
    client = RecordingJsonClient(
        {
            resource_url: {
                "success": False,
                "error": {"message": "Not found"},
            }
        }
    )
    with pytest.raises(ProviderResponseError, match="Not found"):
        CkanAdapter(get_json=client).load(
            Config("ckan", {"endpoint": endpoint, "resource_id": "missing"})
        )
