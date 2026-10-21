"""Provider-owned identity and transport survive shared CKAN operations."""

import json
from collections.abc import Mapping
from typing import Any

import pytest

import rhinestone._http as http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Catalog, Format, Provider, Reference, configure
from rhinestone.adapters.source.plateau import PlateauAdapter
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import AccessPlan, SearchQuery
from tests.provider_support import fixture_json


@pytest.mark.parametrize("adapter_type", ("ckan", "geospatial-jp", "plateau"))
def test_ckan_composition_preserves_configured_identity_and_portable_selection(
    monkeypatch: pytest.MonkeyPatch, adapter_type: str
) -> None:
    package = fixture_json("expansion/plateau.json")["result"]
    selected = package["resources"][1]
    calls: list[tuple[str, Mapping[str, Any], Mapping[str, str]]] = []
    secrets: list[bool] = []

    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        calls.append((url, dict(params), headers or {}))
        if url.endswith("package_search"):
            return {"success": True, "result": {"count": 1, "results": [package]}}
        if url.endswith("resource_show"):
            assert params == {"id": "gpkg"}
            return {"success": True, "result": selected}
        assert url.endswith("package_show")
        assert params == {"id": "plateau-fixture"}
        return {"success": True, "result": package}

    monkeypatch.setattr(http, "get_json", get_json)
    producer = configure(
        catalog=Catalog(
            (
                Provider(
                    "chosen-provider",
                    adapter_type,
                    {"endpoint": "https://fixture.example", "credential": "key"},
                ),
            )
        ),
        credentials={"key": lambda: secrets.append(True) or "request-only-secret"},
    )
    assert secrets == []
    resource = producer.search(format=(Format.GPKG,), limit=1)["chosen-provider"][0]
    assert resource.reference.provider_id == "chosen-provider"
    assert resource.reference.resource_identifier == "gpkg"
    assert resource.uri == selected["url"]
    assert resource.to_dict()["metadata"]["raw"]["extras"] == package["extras"]
    assert resource.provenance.raw["resource"] == selected
    assert calls[0][2] == {"Authorization": "request-only-secret"}
    assert (calls[0][1].get("fq") == "tags:PLATEAU") == (adapter_type == "plateau")

    loaded = producer.load(resource.reference)
    assert loaded.uri == resource.uri
    assert loaded.reference.provider_id == "chosen-provider"
    assert loaded.to_dict()["provenance"]["raw"]["package"] == package
    assert len(calls) == 3
    assert len(secrets) == 3

    assert "request-only-secret" not in repr(loaded)

    assert resource.access_plan is not None
    plan = AccessPlan.from_dict(json.loads(json.dumps(resource.access_plan.to_dict())))
    receiver = configure(
        catalog=Catalog(
            (Provider("selected-file", "direct", {"uri": selected["url"]}),)
        )
    )

    class Runtime:
        def read_dataframe(self, uri: str, **kwargs: Any) -> str:
            return uri

    assert receiver.open(plan, "pyogrio", runtime=Runtime()) == selected["url"]
    assert len(calls) == 3
    assert len(secrets) == 3


@pytest.mark.parametrize("adapter_type", ("ckan", "geospatial-jp"))
def test_ckan_composition_rejects_a_non_object_action_result(
    monkeypatch: pytest.MonkeyPatch, adapter_type: str
) -> None:
    def get_json(
        url: str, params: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Mapping[str, Any]:
        return {"success": True, "result": []}

    monkeypatch.setattr(http, "get_json", get_json)
    app = configure(
        catalog=Catalog(
            (Provider("chosen", adapter_type, {"endpoint": "https://fixture.example"}),)
        )
    )
    with pytest.raises(ProviderResponseError, match="CKAN resource must be an object"):
        app.load(Reference("chosen", resource_identifier="gpkg"))


def test_plateau_rejects_unsupported_search_before_ckan_request() -> None:
    calls: list[str] = []

    def request(url: str, params: Mapping[str, Any]) -> Any:
        calls.append(url)
        raise AssertionError("Unsupported queries must not reach CKAN")

    adapter = PlateauAdapter(request, endpoint="https://fixture.example")
    with pytest.raises(
        ConfigValidationError, match="Unsupported CKAN search conditions"
    ):
        adapter.search(SearchQuery(bbox=(130, 30, 140, 40)))
    assert calls == []
