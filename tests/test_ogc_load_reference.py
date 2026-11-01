import pytest

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Catalog, Provider, Reference, configure
from rhinestone.errors import ConfigValidationError
from tests.provider_support import RecordingJsonClient, fixture_json


@pytest.mark.parametrize(
    "reference",
    [
        Reference("features", parameters={"feature_id": "river-1"}),
        Reference(
            "features",
            parameters={"collection_id": "rivers", "feature_id": "river-1"},
        ),
        Reference(
            "features",
            dataset_identifier="rivers",
            parameters={"feature_id": "river-1"},
        ),
    ],
    ids=["missing", "parameters", "dataset_identifier"],
)
def test_direct_load_requires_collection_on_reference_not_search_provider(
    reference: Reference, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = "https://features.example"
    collection_url = endpoint + "/collections/rivers"
    client = RecordingJsonClient({collection_url: fixture_json("ogc/collection.json")})
    monkeypatch.setattr(_http, "get_json", client)
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "features",
                    "ogc-features",
                    {"endpoint": endpoint, "collection_id": "search-only"},
                ),
            )
        )
    )

    if (
        reference.dataset_identifier is None
        and "collection_id" not in reference.parameters
    ):
        with pytest.raises(ConfigValidationError, match="collection_id"):
            app.load(reference)
        assert client.calls == []
    else:
        resource = app.load(reference)
        assert client.calls == [(collection_url, {})]
        assert resource.uri == collection_url + "/items/river-1"
        assert resource.reference.dataset_identifier == "rivers"


@pytest.mark.parametrize("feature_id", [None, "river-1"])
def test_loaded_ogc_reference_preserves_collection_or_feature(
    feature_id: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = "https://features.example"
    collection_url = endpoint + "/collections/rivers"
    client = RecordingJsonClient({collection_url: fixture_json("ogc/collection.json")})
    monkeypatch.setattr(_http, "get_json", client)
    app = configure(
        catalog=Catalog((Provider("features", "ogc-features", {"endpoint": endpoint}),))
    )
    resource = app.load(
        Reference(
            "features", dataset_identifier="rivers", resource_identifier=feature_id
        )
    )

    reloaded = app.load(resource.reference)

    assert resource.reference.resource_identifier == feature_id
    assert reloaded.uri == resource.uri
    assert reloaded.reference == resource.reference
    assert reloaded.provenance == resource.provenance
