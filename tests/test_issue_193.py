"""Focused contracts for the Reference-to-Resource provider boundary."""

from typing import Any, cast

import pytest

from rhinestone import Config, configure
from rhinestone.adapters.source.static import StaticAdapter
from rhinestone.errors import (
    AmbiguousResourceError,
    ConfigValidationError,
    ExecutionAdapterUnavailableError,
    ResourceNotFoundError,
)
from rhinestone.models import (
    AccessPlan,
    Metadata,
    Provenance,
    Reference,
    Resource,
)


def unresolved(
    *,
    reference: Reference | None = None,
    uri: str = "https://example.test/data",
    format_name: str | None = None,
    media_type: str | None = None,
    metadata: Metadata | None = None,
) -> Resource:
    return Resource(
        uri=uri,
        format=format_name,
        media_type=media_type,
        metadata=metadata or Metadata(),
        provenance=Provenance(provider="fixture"),
        access_plan=None,
        reference=reference or Reference("fixture"),
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dataset_identifier": ""},
        {"resource_identifier": ""},
        {"parameters": cast(Any, [])},
        {"parameters": cast(Any, {1: "bad"})},
        {"parameters": {"score": float("nan")}},
    ],
)
def test_reference_rejects_invalid_identity_and_parameters(
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ConfigValidationError):
        Reference("fixture", **kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"uri": ""},
        {"uri": "https://user:secret@example.test/data"},
        {"format": ""},
        {"options": cast(Any, [])},
        {"options": {"archive": "tar"}},
        {"options": {"entry_point": "file.gml"}},
        {"options": {"archive": "zip", "entry_point": "../file.gml"}},
        {"options": {"encoding": ""}},
    ],
)
def test_access_plan_rejects_invalid_delivery_contract(kwargs: dict[str, Any]) -> None:
    values: dict[str, Any] = {"kind": "file", "uri": "https://example.test/data"}
    values.update(kwargs)
    with pytest.raises(ConfigValidationError):
        AccessPlan(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"uri": "https://example.test/other"},
        {"format": "geojson"},
        {"media_type": "application/json"},
    ],
)
def test_resource_rejects_access_plan_identity_mismatches(
    changes: dict[str, str],
) -> None:
    plan = AccessPlan(
        "file",
        "https://example.test/data",
        "csv",
        "text/csv",
    )
    values: dict[str, Any] = {
        "uri": plan.uri,
        "format": plan.format,
        "media_type": plan.media_type,
        "metadata": Metadata(description="description"),
        "provenance": Provenance(provider="fixture"),
        "access_plan": plan,
        "reference": Reference("fixture"),
    }
    values.update(changes)
    with pytest.raises(ConfigValidationError):
        Resource(**values)


def test_resource_description_reads_normalized_metadata() -> None:
    assert unresolved(metadata=Metadata(description="description")).description == (
        "description"
    )


def test_resource_portable_contract_validates_datetime_and_optional_strings() -> None:
    data = unresolved(metadata=Metadata(raw={"score": 0.5})).to_dict()
    assert data["metadata"]["raw"]["score"] == 0.5

    data["metadata"]["updated_at"] = 1
    with pytest.raises(ConfigValidationError, match="ISO 8601"):
        Resource.from_dict(data)

    data["metadata"]["updated_at"] = "not-a-date"
    with pytest.raises(ConfigValidationError, match="valid ISO 8601"):
        Resource.from_dict(data)

    data = unresolved().to_dict()
    data["media_type"] = 1
    with pytest.raises(ConfigValidationError, match="media_type"):
        Resource.from_dict(data)


def test_static_load_selects_one_distribution_by_reference() -> None:
    adapter = StaticAdapter(
        {
            "dataset": {
                "metadata": {"title": "Dataset"},
                "candidates": [
                    {"id": "csv", "uri": "https://example.test/a.csv", "format": "csv"},
                    {
                        "id": "geojson",
                        "uri": "https://example.test/a.geojson",
                        "format": "geojson",
                    },
                ],
            }
        }
    )

    selected = adapter.load(Reference("static", "dataset", "1"))
    assert selected.format == "geojson"
    with pytest.raises(ResourceNotFoundError, match="missing"):
        adapter.load(Reference("static", "dataset", "missing"))
    with pytest.raises(AmbiguousResourceError, match="2 distributions"):
        adapter.load(Reference("static", "dataset"))


def test_static_rejects_non_mapping_access_options() -> None:
    with pytest.raises(ConfigValidationError, match="access_options"):
        StaticAdapter(
            {
                "dataset": {
                    "candidates": [
                        {
                            "uri": "https://example.test/a.csv",
                            "format": "csv",
                            "attributes": {"access_options": []},
                        }
                    ]
                }
            }
        ).load(Reference("static", "dataset"))


def test_unresolved_resource_is_loaded_or_rejected_before_open() -> None:
    app = configure()
    target = Reference(
        "direct",
        resource_identifier="data",
        parameters={"uri": "https://example.test/data.csv", "format": "csv"},
    )
    value = unresolved(reference=target)

    assert app.resolve(value).format == "csv"
    bound = app.bind(unresolved())
    with pytest.raises(ExecutionAdapterUnavailableError, match="no AccessPlan"):
        bound.open("gdal", runtime=object())
    with pytest.raises(ExecutionAdapterUnavailableError, match="no AccessPlan"):
        app._pipeline.open_resource(unresolved(), "gdal", runtime=object())  # pyright: ignore[reportPrivateUsage]


def test_pipeline_open_resolves_a_reference_before_execution() -> None:
    class Runtime:
        def open(self, uri: str) -> str:
            return uri

    app = configure()
    assert (
        app._pipeline.open(  # pyright: ignore[reportPrivateUsage]
            Config(
                "direct",
                {"uri": "https://example.test/data.tif", "format": "geotiff"},
            ),
            "rasterio",
            runtime=Runtime(),
        )
        == "https://example.test/data.tif"
    )


def test_reference_preserves_finite_json_numbers() -> None:
    assert Reference("fixture", parameters={"score": 1.5}).parameters["score"] == 1.5


def test_unknown_format_does_not_match_a_format_preset() -> None:
    from rhinestone.search import _result_formats  # pyright: ignore[reportPrivateUsage]

    assert _result_formats(unresolved(format_name="unknown-format")) == frozenset()


def test_dcat_explicit_missing_distribution_is_not_found() -> None:
    from tests.test_adapter_expansion import dcat_adapter, dcat_config

    with pytest.raises(ResourceNotFoundError, match="no matching distribution"):
        dcat_adapter().load(
            Reference.from_config(dcat_config(distribution="https://missing.test"))
        )


def test_estat_reference_identifies_the_distribution() -> None:
    from rhinestone.adapters.source.estat_gis import EstatGisAdapter

    adapter = EstatGisAdapter(
        [
            {
                "distribution_id": "d1",
                "dataset_id": "ds1",
                "boundary_kind": "municipality",
                "survey_year": 2020,
                "level": "municipality",
                "uri": "https://example.test/d.gml",
                "format": "gml",
            }
        ]
    )
    assert adapter.load(Reference("estat-gis", "ds1", "d1")).format == "gml"


def test_geospatial_direct_reference_preserves_provider_on_access_plan() -> None:
    from rhinestone.adapters.source import GeospatialJpAdapter

    def client(url: str, params: Any) -> Any:
        if url.endswith("resource_show"):
            return {
                "success": True,
                "result": {
                    "id": "r1",
                    "package_id": "p1",
                    "url": "https://example.test/a.csv",
                    "format": "CSV",
                },
            }
        return {"success": True, "result": {"id": "p1", "title": "Dataset"}}

    resource = GeospatialJpAdapter(client, endpoint="https://example.test").load(
        Reference("geospatial-jp", "p1", "r1")
    )
    assert resource.provenance.provider == "geospatial-jp"
    assert resource.access_plan is not None
    assert resource.access_plan.provider == "geospatial-jp"


def test_stac_opaque_resource_id_uses_explicit_item_and_asset() -> None:
    from rhinestone.adapters.source.stac import StacAdapter
    from tests.provider_support import RecordingJsonClient, fixture_json

    endpoint = "https://stac.example"
    client = RecordingJsonClient(
        {
            endpoint + "/collections/sentinel-2/items/scene-1": fixture_json(
                "stac/item.json"
            )
        }
    )
    resource = StacAdapter(get_json=client).load(
        Reference(
            "stac",
            "sentinel-2",
            "opaque",
            {
                "endpoint": endpoint,
                "item_id": "scene-1",
                "asset_key": "visual",
            },
        )
    )
    assert resource.uri == "https://assets.example/scene-1.tif"
