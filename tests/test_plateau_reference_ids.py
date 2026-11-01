import pytest

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Catalog, Provider, Reference, configure
from rhinestone.errors import AmbiguousResourceError
from tests.provider_support import RecordingJsonClient, fixture_json


@pytest.mark.parametrize(
    ("reference", "dataset_only"),
    [
        (Reference("city", resource_identifier="gpkg"), False),
        (Reference("city", parameters={"resource_id": "gpkg"}), False),
        (Reference("city", dataset_identifier="plateau-fixture"), True),
        (Reference("city", parameters={"dataset_id": "plateau-fixture"}), True),
    ],
    ids=["resource_field", "resource_parameter", "dataset_field", "dataset_parameter"],
)
def test_public_plateau_load_accepts_canonical_and_parameter_identifiers(
    reference: Reference, dataset_only: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    endpoint = "https://fixture.example"
    package_response = fixture_json("expansion/plateau.json")
    resource = package_response["result"]["resources"][1]
    package_url = endpoint + "/api/3/action/package_show"
    resource_url = endpoint + "/api/3/action/resource_show"
    client = RecordingJsonClient(
        {
            package_url: package_response,
            resource_url: {"success": True, "result": resource},
        }
    )
    monkeypatch.setattr(_http, "get_json", client)
    app = configure(
        catalog=Catalog((Provider("city", "plateau", {"endpoint": endpoint}),))
    )

    if dataset_only:
        with pytest.raises(AmbiguousResourceError):
            app.load(reference)
        assert client.calls == [(package_url, {"id": "plateau-fixture"})]
    else:
        loaded = app.load(reference)
        assert loaded.uri == "https://fixture.example/city.gpkg"
        assert loaded.reference.resource_identifier == "gpkg"
        assert loaded.format == "gpkg"
        assert client.calls == [
            (resource_url, {"id": "gpkg"}),
            (package_url, {"id": "plateau-fixture"}),
        ]
