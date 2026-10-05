import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pytest

from rhinestone import Catalog, Config, Provider, Result, configure
from rhinestone.errors import ConfigValidationError, ExecutionAdapterUnavailableError
from rhinestone.models import (
    AccessPlan,
    DiscoveryRecord,
    FileAccessPlan,
    Metadata,
    Provenance,
    RemoteDatasetPlan,
    Resource,
    ResourceCandidate,
    ServiceQueryPlan,
    Source,
)


class FakeRasterio:
    def open(self, uri: str) -> str:
        return "opened:" + uri


def direct_config() -> Config:
    return Config(
        "direct",
        {
            "uri": "https://example.test/data.tif",
            "format": "geotiff",
            "media_type": "image/tiff",
        },
    )


def portable_result() -> Result:
    retrieved = datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc)
    return Result(
        title="Portable dataset",
        description="Transferred between applications",
        discovered_by="catalog",
        target=direct_config(),
        metadata=Metadata(
            title="Portable dataset",
            publisher="Publisher",
            updated_at=retrieved,
            raw={"keywords": ["river", "tokyo"]},
        ),
        provenance=Provenance(
            provider="catalog",
            dataset_identifier="dataset-1",
            resource_identifier="resource-1",
            api_endpoint="https://catalog.example/api",
            original_url="https://catalog.example/dataset-1",
            query_parameters={"q": "river", "rows": 1},
            retrieved_at=retrieved,
            checksum="sha256:abc",
            adapter="fixture",
            adapter_version="1",
            raw={"page": 1},
        ),
        formats=frozenset({"geotiff", "cog"}),
        raw_metadata={"record": {"id": "dataset-1"}},
    )


def test_result_json_round_trip_is_versioned_and_detached() -> None:
    value = portable_result()

    encoded = value.to_dict()
    decoded = Result.from_dict(json.loads(json.dumps(encoded)))

    assert encoded["schema"] == "rhinestone.result"
    assert encoded["version"] == 1
    assert "_resolver" not in json.dumps(encoded)
    assert decoded == value
    with pytest.raises(ConfigValidationError, match="not bound"):
        decoded.resolve()


def test_result_can_be_rebound_to_a_different_application() -> None:
    detached = Result.from_dict(portable_result().to_dict())
    receiving_app = configure()

    rebound = receiving_app.bind(detached)
    resource = rebound.resolve()

    assert resource.uri == "https://example.test/data.tif"
    assert resource.provenance.provider == "direct"


def test_resource_json_round_trip_excludes_opener_and_rebinds() -> None:
    producing_app = configure()
    original = producing_app.resolve(direct_config())
    original = replace(
        original,
        local_path="/tmp/cache/data.tif",
        discovery=DiscoveryRecord(
            source_id="catalog",
            metadata=portable_result().metadata,
            provenance=portable_result().provenance,
            raw_metadata={"record": {"id": "dataset-1"}},
        ),
    )

    encoded = original.to_dict()
    detached = Resource.from_dict(json.loads(json.dumps(encoded)))

    assert encoded["schema"] == "rhinestone.resource"
    assert "_opener" not in json.dumps(encoded)
    assert detached == original
    with pytest.raises(ExecutionAdapterUnavailableError, match="not bound"):
        detached.open("rasterio", runtime=FakeRasterio())

    rebound = configure().bind(detached)
    assert rebound.open("rasterio", runtime=FakeRasterio()) == (
        "opened:https://example.test/data.tif"
    )


def test_resource_round_trip_preserves_a_second_source_shape() -> None:
    item = {
        "metadata": {
            "title": "Static dataset",
            "raw": {"keywords": ["static"]},
        },
        "candidates": [
            {
                "uri": "https://example.test/static.geojson",
                "format": "geojson",
                "media_type": "application/geo+json",
                "attributes": {
                    "access_kind": "remote-dataset",
                    "access_options": {"encoding": "utf-8"},
                },
            }
        ],
        "capabilities": ["remote-dataset", "search"],
        "provenance": {"dataset_identifier": "static-1"},
    }
    app = configure(
        catalog=Catalog(
            (Provider("static-source", "static", {"items": {"one": item}}),)
        )
    )
    original = app.resolve(Config("static-source", {"id": "one"}))

    restored = Resource.from_dict(json.loads(json.dumps(original.to_dict())))

    assert restored == original
    assert isinstance(restored.access_plan, RemoteDatasetPlan)
    assert restored.source.raw_metadata["metadata"]["title"] == "Static dataset"


@pytest.mark.parametrize(
    "plan",
    [
        FileAccessPlan(uri="https://example.test/data.zip", archive="zip"),
        RemoteDatasetPlan(uri="https://example.test/data.tif"),
        ServiceQueryPlan(uri="https://example.test/wfs"),
        AccessPlan(kind="custom", uri="https://example.test/custom"),
    ],
)
def test_resource_round_trip_preserves_access_plan_subtypes(plan: AccessPlan) -> None:
    source = Source(
        metadata=Metadata(title="Dataset"),
        candidates=(ResourceCandidate(plan.uri, None, None),),
        capabilities=frozenset(),
        provenance=Provenance(provider="fixture"),
        raw_metadata={},
    )
    resource = Resource(
        uri=plan.uri,
        format=None,
        media_type=None,
        metadata=source.metadata,
        provenance=source.provenance,
        access_plan=plan,
        source=source,
    )

    restored = Resource.from_dict(resource.to_dict())

    assert restored.access_plan == plan
    assert type(restored.access_plan) is type(plan)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "other", "schema"),
        ("version", 2, "version"),
        ("version", True, "version"),
        ("version", 1.0, "version"),
        ("title", 1, "title"),
        ("description", 1, "description"),
        ("target", [], "target"),
        ("formats", "geotiff", "formats"),
        ("formats", [1], "formats"),
    ],
)
def test_result_from_dict_rejects_invalid_contracts(
    field: str, value: Any, message: str
) -> None:
    data = deepcopy(portable_result().to_dict())
    data[field] = value

    with pytest.raises(ConfigValidationError, match=message):
        Result.from_dict(data)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"bad": float("nan")}, "finite"),
        ({1: "bad"}, "string keys"),
        ({"bad": object()}, "non-JSON"),
    ],
)
def test_to_dict_rejects_non_json_raw_values(raw: dict[Any, Any], message: str) -> None:
    value = replace(portable_result(), raw_metadata=raw)

    with pytest.raises(ConfigValidationError, match=message):
        value.to_dict()


def test_to_dict_accepts_finite_float_raw_values() -> None:
    value = replace(portable_result(), raw_metadata={"score": 0.5})

    assert value.to_dict()["raw_metadata"] == {"score": 0.5}


@pytest.mark.parametrize(
    ("updated_at", "message"),
    [(1, "ISO 8601"), ("not-a-date", "valid ISO 8601")],
)
def test_result_from_dict_rejects_invalid_datetime(
    updated_at: Any, message: str
) -> None:
    data = portable_result().to_dict()
    data["metadata"]["updated_at"] = updated_at

    with pytest.raises(ConfigValidationError, match=message):
        Result.from_dict(data)


def test_result_from_dict_accepts_utc_z_datetime_on_python_310() -> None:
    data = portable_result().to_dict()
    data["metadata"]["updated_at"] = "2026-10-05T00:00:00Z"
    data["provenance"]["retrieved_at"] = "2026-10-05T00:00:00Z"

    restored = Result.from_dict(data)

    expected = datetime(2026, 10, 5, tzinfo=timezone.utc)
    assert restored.metadata.updated_at == expected
    assert restored.provenance.retrieved_at == expected


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("candidates", {}, "candidates"),
        ("capabilities", {}, "capabilities"),
        ("capabilities", [1], "capabilities"),
    ],
)
def test_resource_from_dict_rejects_invalid_source_collections(
    field: str, value: Any, message: str
) -> None:
    data = configure().resolve(direct_config()).to_dict()
    data["source"][field] = value

    with pytest.raises(ConfigValidationError, match=message):
        Resource.from_dict(data)
