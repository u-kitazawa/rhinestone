from datetime import datetime, timezone
from typing import Any, cast

import pytest

from rhinestone.errors import ConfigValidationError, ExecutionAdapterUnavailableError
from rhinestone.models import (
    AccessPlan,
    Config,
    Metadata,
    Provenance,
    Provider,
    Reference,
    Resource,
    SearchDiagnostic,
    SearchExecution,
    SearchQuery,
)


def unresolved_resource(
    uri: object, format_name: object = "csv", media_type: object = None
) -> Resource:
    return Resource(
        uri=cast(Any, uri),
        format=cast(Any, format_name),
        media_type=cast(Any, media_type),
        metadata=Metadata(),
        provenance=Provenance(provider="fixture"),
        access_plan=None,
        reference=Reference("fixture"),
    )


@pytest.mark.parametrize(
    "execution",
    [
        SearchExecution("provider", 0.0, 0),
        SearchExecution("provider", 1.5, 2),
    ],
)
def test_search_execution_accepts_non_negative_provider_measurements(
    execution: SearchExecution,
) -> None:
    assert execution.source_id == "provider"


@pytest.mark.parametrize(
    "arguments",
    [
        ("", 0.0, 0),
        ("provider", -0.1, 0),
        ("provider", 0.0, -1),
        ("provider", float("nan"), 0),
        ("provider", float("inf"), 0),
        ("provider", True, 0),
        ("provider", 0.0, 1.5),
        ("provider", 0.0, True),
    ],
)
def test_search_execution_rejects_invalid_measurements(
    arguments: tuple[Any, Any, Any],
) -> None:
    with pytest.raises(ConfigValidationError):
        SearchExecution(*arguments)


def test_config_is_immutable_and_copies_nested_settings() -> None:
    settings: dict[str, Any] = {
        "resource_id": "resource-1",
        "filters": {"year": 2024},
    }
    config = Config(source_id="ckan", settings=settings)

    cast(dict[str, int], settings["filters"])["year"] = 2025

    assert config.settings["filters"]["year"] == 2024
    with pytest.raises(TypeError):
        cast(dict[str, Any], config.settings)["resource_id"] = "changed"


def test_source_definition_and_config_ids_must_be_non_empty() -> None:
    with pytest.raises(ConfigValidationError, match="source id"):
        Provider("", "ckan")
    with pytest.raises(ConfigValidationError, match="adapter_type"):
        Provider("catalog", "")
    with pytest.raises(ConfigValidationError, match="source_id"):
        Config("", {})


def test_resource_rejects_embedded_http_credentials() -> None:
    with pytest.raises(ConfigValidationError, match="credentials"):
        unresolved_resource("https://user:password@example.jp/data.csv")


@pytest.mark.parametrize(
    "uri",
    (
        "https://exa mple/data.csv",
        "https://%ZZ/data.csv",
        "https://-bad.example/data.csv",
        "https://bad_name.example/data.csv",
        "https://[gggg::1]/data.csv",
    ),
)
def test_resource_rejects_malformed_http_hostnames(uri: str) -> None:
    with pytest.raises(ConfigValidationError, match="authority"):
        unresolved_resource(uri)


def test_resource_accepts_valid_ipv6_http_authority() -> None:
    candidate = unresolved_resource("https://[2001:db8::1]/data.csv")

    assert candidate.uri == "https://[2001:db8::1]/data.csv"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"uri": "", "format": "csv", "media_type": None}, "non-empty"),
        ({"uri": 1, "format": "csv", "media_type": None}, "non-empty"),
        ({"uri": "https://[invalid", "format": "csv", "media_type": None}, "invalid"),
        ({"uri": "https://example.jp/data", "format": 1, "media_type": None}, "format"),
        (
            {"uri": "https://example.jp/data", "format": "csv", "media_type": 1},
            "media_type",
        ),
    ),
)
def test_resource_validates_public_field_shapes(
    kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ConfigValidationError, match=message):
        unresolved_resource(
            kwargs["uri"], kwargs.get("format"), kwargs.get("media_type")
        )


@pytest.mark.parametrize("limit", (-1, True, 1.5, "1"))
def test_search_query_rejects_invalid_limits(limit: object) -> None:
    with pytest.raises(ConfigValidationError, match="limit"):
        SearchQuery(limit=cast(Any, limit))


@pytest.mark.parametrize(
    "bbox",
    (
        (),
        (0, 1, 2),
        (0, 1, 2, 3, 4),
        (0, 1, 2, "3"),
        (False, 1, 2, 3),
        [0, 1, 2, 3],
    ),
)
def test_search_query_rejects_invalid_bboxes(bbox: object) -> None:
    with pytest.raises(ConfigValidationError, match="bbox"):
        SearchQuery(bbox=cast(Any, bbox))


def test_search_query_bbox_error_does_not_call_element_repr() -> None:
    class Unrepresentable:
        def __repr__(self) -> str:
            raise AssertionError("repr must not be called")

    with pytest.raises(ConfigValidationError, match="invalid length or element type"):
        SearchQuery(bbox=cast(Any, (0, 1, 2, Unrepresentable())))


@pytest.mark.parametrize(
    "time",
    (
        (),
        (None,),
        (None, None, None),
        ("2024-01-01", None),
        [None, None],
    ),
)
def test_search_query_rejects_invalid_time_ranges(time: object) -> None:
    with pytest.raises(ConfigValidationError, match="time"):
        SearchQuery(time=cast(Any, time))


def test_search_query_time_error_does_not_call_element_repr() -> None:
    class Unrepresentable:
        def __repr__(self) -> str:
            raise AssertionError("repr must not be called")

    with pytest.raises(ConfigValidationError, match="invalid length or element type"):
        SearchQuery(time=cast(Any, (Unrepresentable(), None)))


def test_search_query_accepts_valid_boundary_values() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    query = SearchQuery(
        bbox=(0, 1.5, 2, 3.5),
        time=(start, None),
        limit=0,
    )

    assert query.bbox == (0, 1.5, 2, 3.5)
    assert query.time == (start, None)
    assert query.limit == 0


def test_source_definition_is_deeply_immutable() -> None:
    settings: dict[str, Any] = {"endpoint": "https://example.jp", "nested": {"x": 1}}
    source = Provider("catalog", "ckan", settings)
    cast(dict[str, int], settings["nested"])["x"] = 2

    assert source.settings["nested"]["x"] == 1
    with pytest.raises(TypeError):
        cast(dict[str, Any], source.settings)["endpoint"] = "changed"


def test_config_freezes_all_mutable_container_shapes() -> None:
    config = Config(
        source_id="fixture",
        settings={"list": [1], "tuple": ({"nested": True},), "set": {1, 2}},
    )

    assert config.settings == {
        "list": (1,),
        "tuple": ({"nested": True},),
        "set": frozenset({1, 2}),
    }


def test_resource_preserves_source_metadata_and_provenance() -> None:
    raw = {"provider_only": {"encoding": "cp932"}}
    metadata = Metadata(title="River", raw=raw)
    provenance = Provenance(
        provider="example-ckan",
        resource_identifier="resource-1",
        retrieved_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        raw={"request_id": "req-1"},
    )
    resource = Resource(
        uri="https://example.jp/river.zip",
        format="shapefile",
        media_type="application/zip",
        metadata=metadata,
        provenance=provenance,
        access_plan=AccessPlan(
            kind="file",
            uri="https://example.jp/river.zip",
            format="shapefile",
            media_type="application/zip",
            options={"archive": "zip"},
        ),
        reference=Reference("example-ckan", "dataset-1", "resource-1"),
    )

    assert resource.metadata is metadata
    assert resource.provenance is provenance
    assert resource.metadata.raw == raw


def test_resource_reference_retains_delivery_identity_without_losing_knowledge() -> (
    None
):
    metadata = Metadata(title="Dataset", raw={"table": "raw-value"})
    provenance = Provenance(provider="catalog", raw={"query": "dataset"})
    resource = Resource(
        uri="https://example.jp/data.csv",
        format=None,
        media_type=None,
        metadata=metadata,
        provenance=provenance,
        access_plan=None,
        reference=Reference("catalog", "dataset-1", "resource-1"),
    )

    assert resource.reference == Reference("catalog", "dataset-1", "resource-1")
    assert resource.metadata is metadata
    assert resource.provenance is provenance


def test_unbound_resource_cannot_open_without_execution_context() -> None:
    resource = Resource(
        uri="/data/a.csv",
        format="csv",
        media_type="text/csv",
        metadata=Metadata(title="A", raw={}),
        provenance=Provenance(provider="direct", raw={}),
        access_plan=AccessPlan(
            kind="file", uri="/data/a.csv", format="csv", media_type="text/csv"
        ),
        reference=Reference("direct", resource_identifier="/data/a.csv"),
    )

    with pytest.raises(ExecutionAdapterUnavailableError, match="not bound"):
        resource.open("gdal")


def test_reference_requires_a_provider_id() -> None:
    with pytest.raises(ConfigValidationError, match="provider_id"):
        Reference("")


def test_search_diagnostic_requires_a_source_id() -> None:
    with pytest.raises(ConfigValidationError, match="search diagnostic source_id"):
        SearchDiagnostic(source_id="", skipped_conditions=frozenset({"text"}))


def test_search_diagnostic_freezes_missing_conditions() -> None:
    diagnostic = SearchDiagnostic(
        source_id="source",
        skipped_conditions=frozenset({"bbox"}),
        reason="missing_required",
        missing_conditions=frozenset({"text"}),
    )

    assert diagnostic.missing_conditions == frozenset({"text"})


def test_search_diagnostic_can_describe_provider_failure() -> None:
    diagnostic = SearchDiagnostic(
        source_id="source",
        skipped_conditions=frozenset(),
        reason="provider_failure",
        failure_type="response",
    )

    assert diagnostic.failure_type == "response"
