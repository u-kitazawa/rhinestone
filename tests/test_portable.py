import json
import subprocess
import sys
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
    Metadata,
    Provenance,
    Resource,
    ResourceCandidate,
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
    assert encoded["version"] == 2
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
    assert restored.access_plan.kind == "remote-dataset"
    assert restored.source.raw_metadata["metadata"]["title"] == "Static dataset"


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
def test_resource_round_trip_preserves_access_plan(plan: AccessPlan) -> None:
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
    assert type(restored.access_plan) is AccessPlan


def test_access_plan_is_a_versioned_standalone_cross_process_contract() -> None:
    plan = AccessPlan(
        kind="service-query",
        uri="https://api.example.test/v1/items",
        format="api",
        media_type="application/json",
        options={
            "params": {"limit": 10, "score": 0.5},
            "response_type": "array",
            "fields": ["id"],
        },
        provider="catalog",
        service="items",
        credential="items-key",
    )

    encoded = plan.to_dict()
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json,sys; from rhinestone.models import AccessPlan; "
                "plan=AccessPlan.from_dict(json.load(sys.stdin)); "
                "print(plan.kind, plan.uri, plan.credential)"
            ),
        ],
        input=json.dumps(encoded),
        text=True,
        capture_output=True,
        check=True,
    )

    assert encoded["schema"] == "rhinestone.access-plan"
    assert encoded["version"] == 1
    assert process.stdout.strip() == (
        "service-query https://api.example.test/v1/items items-key"
    )
    assert AccessPlan.from_dict(json.loads(json.dumps(encoded))) == plan


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"kind": "custom", "uri": "/data"}, "kind"),
        ({"kind": "file", "uri": ""}, "uri"),
        ({"kind": "file", "uri": 1}, "uri"),
        ({"kind": "file", "uri": "https:///missing"}, "authority"),
        ({"kind": "file", "uri": "/data", "format": ""}, "format"),
        ({"kind": "file", "uri": "/data", "options": []}, "mapping"),
        (
            {"kind": "file", "uri": "/data", "options": {"archive": "tar"}},
            "archive",
        ),
        (
            {
                "kind": "file",
                "uri": "/data",
                "options": {"entry_point": "data.shp"},
            },
            "entry_point",
        ),
        (
            {
                "kind": "file",
                "uri": "/data",
                "options": {"archive": "zip", "entry_point": "../data.shp"},
            },
            "safe relative",
        ),
        (
            {"kind": "file", "uri": "/data", "options": {"encoding": ""}},
            "encoding",
        ),
        (
            {"kind": "file", "uri": "/data", "options": {"token": "secret"}},
            "credential value",
        ),
        (
            {"kind": "file", "uri": "/data", "options": {1: "bad"}},
            "string keys",
        ),
        (
            {"kind": "file", "uri": "/data", "options": {"bad": object()}},
            "non-JSON",
        ),
        (
            {"kind": "file", "uri": "/data", "options": {"bad": float("nan")}},
            "finite",
        ),
    ],
)
def test_access_plan_rejects_invalid_or_nonportable_values(
    kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ConfigValidationError, match=message):
        AccessPlan(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ("schema", "version"))
def test_access_plan_from_dict_rejects_unknown_envelope(field: str) -> None:
    data = AccessPlan(kind="file", uri="/data").to_dict()
    data[field] = "invalid"

    with pytest.raises(ConfigValidationError, match=field):
        AccessPlan.from_dict(data)


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
