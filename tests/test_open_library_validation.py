"""Reject invalid explicit adapter names before loading or executing data."""

from dataclasses import replace
from typing import Any

import pytest

from rhinestone import AccessPlan, Catalog, Provider, Reference, Resource, configure
from rhinestone.adapters.contracts import ProviderAdapterDefinition
from rhinestone.errors import ConfigValidationError
from rhinestone.models import Metadata, Provenance


@pytest.mark.parametrize("entry", ("reference", "resource", "plan", "bound"))
@pytest.mark.parametrize(
    "library",
    (None, 123, False, [], {}, object(), "", "   "),
    ids=("none", "number", "boolean", "list", "mapping", "object", "empty", "blank"),
)
def test_invalid_library_is_rejected_before_load_or_runtime(
    entry: str, library: Any
) -> None:
    calls: list[str] = []
    reference = Reference("example")
    plan = AccessPlan(
        kind="file", uri="https://example.test/data.tif", format="geotiff"
    )
    resource = Resource(
        reference=reference,
        uri=plan.uri,
        format=plan.format,
        media_type=None,
        metadata=Metadata(),
        provenance=Provenance(provider="example"),
        access_plan=None,
    )

    class Source:
        def load(self, reference: Reference) -> Resource:
            calls.append("load")
            return replace(resource, reference=reference, access_plan=plan)

    class Runtime:
        def OpenEx(self, uri: str, **kwargs: Any) -> object:
            calls.append("runtime")
            return object()

    app = configure(
        catalog=Catalog((Provider("example", "test-source"),)),
        adapters=(
            ProviderAdapterDefinition(
                "test-source", lambda provider, context: Source()
            ),
        ),
    )

    with pytest.raises(ConfigValidationError) as raised:
        if entry == "bound":
            app.bind(resource).open(library, runtime=Runtime())
        else:
            value = {"reference": reference, "resource": resource, "plan": plan}[entry]
            app.open(value, library, runtime=Runtime())

    assert str(raised.value) == "library must be a non-empty runtime adapter name"
    assert calls == []
