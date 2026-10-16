import pytest

from rhinestone import Catalog, Provider, Reference, Resource, configure
from rhinestone.adapters.contracts import SourceAdapterDefinition
from rhinestone.errors import ExecutionAdapterUnavailableError
from rhinestone.models import Metadata, Provenance, SearchQuery
from rhinestone.resolution import resource_from_delivery


class DeferredSource:
    search_conditions = frozenset({"text"})

    def __init__(self, resolved_format: str | None) -> None:
        self.resolved_format = resolved_format
        self.loads: list[Reference] = []

    def search(self, query: SearchQuery) -> tuple[Resource, ...]:
        return (self.resource(Reference("deferred-source", "dataset", "data"), None),)

    def load(self, reference: Reference) -> Resource:
        self.loads.append(reference)
        return self.resource(reference, self.resolved_format)

    @staticmethod
    def resource(reference: Reference, format_name: str | None) -> Resource:
        return resource_from_delivery(
            reference=reference,
            uri="https://data.example/data.tif",
            format=format_name,
            media_type="image/tiff" if format_name else None,
            metadata=Metadata(title="Deferred data"),
            provenance=Provenance(provider="deferred-source"),
        )


class RecordingRasterio:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def open(self, uri: str) -> str:
        self.calls.append(uri)
        return "opened:" + uri


@pytest.mark.parametrize("resolved_format", ["geotiff", None])
def test_bound_search_resource_loads_lazily_before_open(
    resolved_format: str | None,
) -> None:
    source = DeferredSource(resolved_format)
    app = configure(
        catalog=Catalog((Provider("catalog", "deferred-source"),)),
        adapters=(SourceAdapterDefinition("deferred-source", lambda p, c: source),),
        network_policy="none",
    )
    resource = app.search(text="data")[0]
    runtime = RecordingRasterio()
    assert resource.access_plan is None
    assert source.loads == []

    if resolved_format is None:
        with pytest.raises(ExecutionAdapterUnavailableError, match="no AccessPlan"):
            resource.open("rasterio", runtime=runtime)
        assert runtime.calls == []
    else:
        assert resource.open("rasterio", runtime=runtime) == "opened:" + resource.uri
        assert runtime.calls == [resource.uri]

    assert len(source.loads) == 1
    assert source.loads[0].resource_identifier == "data"
    assert resource.access_plan is None


def test_detached_deferred_resource_requires_rebinding_before_lazy_open() -> None:
    source = DeferredSource("geotiff")
    app = configure(
        catalog=Catalog((Provider("catalog", "deferred-source"),)),
        adapters=(SourceAdapterDefinition("deferred-source", lambda p, c: source),),
        network_policy="none",
    )
    original = app.search(text="data")[0]
    detached = Resource.from_dict(original.to_dict())
    runtime = RecordingRasterio()

    with pytest.raises(ExecutionAdapterUnavailableError, match="not bound"):
        detached.open("rasterio", runtime=runtime)
    assert source.loads == []
    assert runtime.calls == []

    rebound = app.bind(detached)
    assert rebound.open("rasterio", runtime=runtime) == "opened:" + original.uri
    assert len(source.loads) == 1
    assert runtime.calls == [original.uri]
    assert detached.access_plan is None
