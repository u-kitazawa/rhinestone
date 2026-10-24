"""Search and portable-plan execution expose the same failure categories."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from rhinestone import AccessPlan, Catalog, Provider, Resource, Rhinestone, configure
from rhinestone.errors import ResourceAccessError, RuntimeAdapterUnavailableError


def searched_resource(format_name: str) -> tuple[Rhinestone, Resource]:
    """Use a searchable fixture, without live provider or data dependencies."""
    provider = Provider(
        "fixture",
        "static",
        {
            "items": {
                "selected": {
                    "metadata": {"title": "Selected dataset"},
                    "candidates": [
                        {
                            "uri": "https://files.example/selected",
                            "format": format_name,
                            "attributes": {
                                "archive": "zip",
                                "access_options": {"entry_point": "data/selected.shp"},
                            }
                            if format_name == "shapefile"
                            else {},
                        }
                    ],
                }
            }
        },
    )
    # Policy is tested separately; these tests isolate execution error boundaries.
    app = configure(catalog=Catalog((provider,)), network_policy="none")
    results = app.search(text="Selected", limit=1)
    assert len(results) == 1
    assert not results.diagnostics
    return app, results[0]


def open_selected(
    app: Rhinestone,
    resource: Resource,
    route: str,
    library: str,
    runtime: object | None,
) -> object:
    if route == "resource":
        return resource.open(library, runtime=runtime)
    received = AccessPlan.from_dict(
        json.loads(json.dumps(app.plan(resource).to_dict()))
    )
    # No original Provider exists in the receiving context.
    receiver = configure(catalog=Catalog(()), network_policy="none")
    return receiver.open(received, library, runtime=runtime)


@pytest.mark.parametrize("route", ["resource", "plan"])
@pytest.mark.parametrize(
    "library,method,format_name",
    [
        ("gdal", "OpenEx", "shapefile"),
        ("pyogrio", "read_dataframe", "shapefile"),
        ("rasterio", "open", "cog"),
    ],
)
@pytest.mark.parametrize(
    "failure",
    [
        ValueError("driver unavailable"),
        OSError("broken ZIP archive"),
        ConnectionError("data endpoint unreachable"),
        PermissionError("data authentication failed: secret-marker"),
    ],
    ids=["driver", "archive", "connection", "authentication"],
)
def test_selected_access_failures_preserve_the_runtime_cause(
    route: str, library: str, method: str, format_name: str, failure: Exception
) -> None:
    app, resource = searched_resource(format_name)
    calls: list[str] = []

    def fail(uri: str, **options: Any) -> object:
        calls.append(uri)
        raise failure

    runtime = SimpleNamespace(**{method: fail})
    with pytest.raises(ResourceAccessError) as captured:
        open_selected(app, resource, route, library, runtime)

    assert captured.value.__cause__ is failure
    assert "secret-marker" not in str(captured.value)
    expected_uri = (
        resource.uri
        if library == "rasterio"
        else "/vsizip//vsicurl/" + resource.uri + "/data/selected.shp"
    )
    assert calls == [expected_uri]
    assert resource.metadata.title == "Selected dataset"
    assert resource.provenance.provider == "fixture"


@pytest.mark.parametrize("route", ["resource", "plan"])
@pytest.mark.parametrize("format_name", ["cog", "unknown"])
def test_execution_preparation_failures_do_not_call_runtime(
    route: str, format_name: str
) -> None:
    app, resource = searched_resource(format_name)
    calls: list[str] = []

    def record(uri: str) -> object:
        calls.append(uri)
        return object()

    runtime = SimpleNamespace(open=record) if format_name == "unknown" else None
    with pytest.raises(RuntimeAdapterUnavailableError):
        open_selected(app, resource, route, "rasterio", runtime)
    assert calls == []


@pytest.mark.parametrize("route", ["resource", "plan"])
def test_supported_search_resource_still_opens_successfully(route: str) -> None:
    app, resource = searched_resource("cog")
    calls: list[str] = []
    data = object()

    def record(uri: str) -> object:
        calls.append(uri)
        return data

    assert (
        open_selected(app, resource, route, "rasterio", SimpleNamespace(open=record))
        is data
    )
    assert calls == [resource.uri]
