"""The normal and portable execution workflows share one public contract."""

from dataclasses import replace
from typing import Any

import pytest

from rhinestone import AccessPlan, Catalog, Provider, Reference, Resource, configure
from rhinestone.errors import (
    DestinationNotAllowedError,
    ExecutionAdapterUnavailableError,
)
from rhinestone.models import DiscoveryRecord, Metadata, Provenance


def direct(*, planned: bool) -> Resource:
    reference = Reference(
        "direct",
        resource_identifier="delivery",
        parameters={
            "uri": "https://example.test/data.zip",
            "format": "shapefile",
            "archive": "zip",
            "encoding": "cp932",
        },
    )
    resource = configure().load(reference)
    return replace(
        resource,
        access_plan=resource.access_plan if planned else None,
        discovery=DiscoveryRecord(
            source_id="discovery",
            metadata=Metadata(title="発見した河川"),
            provenance=Provenance(provider="discovery"),
            raw_metadata={"id": "別のID"},
        ),
    )


@pytest.mark.parametrize("planned", [False, True])
def test_search_resource_and_transferred_plan_open_the_same_archive(
    planned: bool,
) -> None:
    resource = direct(planned=planned)
    app = configure()
    plan = app.plan(resource)
    assert plan.options["archive"] == "zip"
    assert plan.options["encoding"] == "cp932"
    assert app.load(resource).discovery == resource.discovery

    calls: list[tuple[str, dict[str, Any]]] = []

    class Runtime:
        def read_dataframe(self, uri: str, **kwargs: Any) -> str:
            calls.append((uri, kwargs))
            return "opened"

    assert app.open(resource, "pyogrio", runtime=Runtime()) == "opened"
    assert app.bind(resource).open("pyogrio", runtime=Runtime()) == "opened"
    # Receiving context has no target Provider configured; only the plan executes.
    received = AccessPlan.from_dict(plan.to_dict())
    with pytest.raises(DestinationNotAllowedError):
        configure().open(received, "pyogrio", runtime=Runtime())
    receiver = configure(
        catalog=Catalog(
            (
                Provider(
                    "allowed",
                    "ckan",
                    {
                        "endpoint": "https://example.test",
                    },
                ),
            )
        )
    )
    assert receiver.open(received, "pyogrio", runtime=Runtime()) == "opened"
    assert calls[0] == calls[1] == calls[2]
    assert calls[0][1]["encoding"] == "cp932"


def test_plan_does_not_reload_a_ready_resource() -> None:
    resource = direct(planned=True)
    # A portable ready Resource remains executable without its original Provider.
    resource = replace(resource, reference=Reference("unconfigured"))
    assert configure().plan(resource) is resource.access_plan


def test_plan_rejects_a_provider_that_cannot_declare_an_access_plan() -> None:
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "fixture",
                    "static",
                    {
                        "items": {
                            "data": {
                                "candidates": [{"uri": "https://example.test/data"}]
                            }
                        },
                    },
                ),
            )
        )
    )
    resource = app.load(Reference("fixture", "data"))
    with pytest.raises(ExecutionAdapterUnavailableError, match="no AccessPlan"):
        app.plan(resource)


def test_legacy_public_operations_are_removed() -> None:
    app = configure()
    assert not hasattr(app, "resolve")
    assert not hasattr(Reference, "from_config")
