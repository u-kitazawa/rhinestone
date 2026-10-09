import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pytest

from rhinestone import Reference, configure
from rhinestone.errors import ConfigValidationError, ExecutionAdapterUnavailableError
from rhinestone.models import AccessPlan, DiscoveryRecord, Resource


class FakeRasterio:
    def open(self, uri: str) -> str:
        return "opened:" + uri


def direct_config() -> Reference:
    return Reference(
        "direct",
        parameters={
            "uri": "https://example.test/data.tif",
            "format": "geotiff",
            "media_type": "image/tiff",
        },
    )


def portable_resource() -> Resource:
    original = configure().load(direct_config())
    return replace(
        original,
        local_path="/tmp/cache/data.tif",
        discovery=DiscoveryRecord(
            source_id="catalog",
            metadata=replace(
                original.metadata,
                title="Portable dataset",
                updated_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
                raw={"keywords": ["river", "tokyo"]},
            ),
            provenance=replace(
                original.provenance,
                provider="catalog",
                retrieved_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
                raw={"page": 1},
            ),
            raw_metadata={"record": {"id": "dataset-1"}},
        ),
    )


def test_resource_json_round_trip_is_versioned_detached_and_rebindable() -> None:
    original = portable_resource()

    encoded = original.to_dict()
    detached = Resource.from_dict(json.loads(json.dumps(encoded)))

    assert encoded["schema"] == "rhinestone.resource"
    assert encoded["version"] == 3
    assert encoded["reference"]["provider_id"] == "direct"
    assert "_opener" not in json.dumps(encoded)
    assert detached == original
    with pytest.raises(ExecutionAdapterUnavailableError, match="not bound"):
        detached.open("rasterio", runtime=FakeRasterio())

    rebound = configure().bind(detached)
    assert rebound.open("rasterio", runtime=FakeRasterio()) == (
        "opened:https://example.test/data.tif"
    )


@pytest.mark.parametrize(
    "plan",
    [
        AccessPlan(
            kind="file",
            uri="https://example.test/data.zip",
            options={"archive": "zip"},
        ),
        AccessPlan(kind="remote-dataset", uri="https://example.test/data.tif"),
        AccessPlan(kind="service-query", uri="https://example.test/wfs"),
    ],
)
def test_access_plan_json_round_trip_preserves_each_kind(plan: AccessPlan) -> None:
    restored = AccessPlan.from_dict(json.loads(json.dumps(plan.to_dict())))

    assert restored == plan


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "other", "schema"),
        ("version", 2, "version"),
        ("version", True, "version"),
        ("uri", 1, "uri"),
        ("reference", [], "reference"),
        ("access_plan", [], "access_plan"),
    ],
)
def test_resource_from_dict_rejects_invalid_contracts(
    field: str, value: Any, message: str
) -> None:
    data = portable_resource().to_dict()
    data[field] = value

    with pytest.raises(ConfigValidationError, match=message):
        Resource.from_dict(data)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"bad": float("nan")}, "finite"),
        ({1: "bad"}, "string keys"),
        ({"bad": object()}, "non-JSON"),
    ],
)
def test_to_dict_rejects_non_json_metadata(raw: dict[Any, Any], message: str) -> None:
    value = replace(
        portable_resource(),
        metadata=replace(portable_resource().metadata, raw=raw),
    )

    with pytest.raises(ConfigValidationError, match=message):
        value.to_dict()


def test_resource_from_dict_accepts_utc_z_datetime() -> None:
    data = portable_resource().to_dict()
    data["metadata"]["updated_at"] = "2026-10-05T00:00:00Z"

    restored = Resource.from_dict(data)

    assert restored.metadata.updated_at == datetime(2026, 10, 5, tzinfo=timezone.utc)
