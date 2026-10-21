"""Independent wheel used to verify the installed Provider extension contract."""

from rhinestone.adapters.contracts import SourceAdapterContext, SourceAdapterDefinition
from rhinestone.models import (
    Metadata,
    Provenance,
    Provider,
    Reference,
    Resource,
    SearchQuery,
)
from rhinestone.resolution import resource_from_delivery

calls: list[str] = []


class InstalledProvider:
    search_conditions = frozenset({"text", "limit"})

    def load(self, reference: Reference) -> Resource:
        calls.append("load")
        return resource_from_delivery(
            reference=reference,
            uri="https://fixture.example/installed.tif",
            format="geotiff",
            media_type="image/tiff",
            metadata=Metadata(title="Installed", raw={"package": "independent wheel"}),
            provenance=Provenance(provider="installed-provider"),
        )

    def search(self, query: SearchQuery) -> tuple[Resource, ...]:
        calls.append("search")
        return (self.load(Reference("installed-provider", resource_identifier="one")),)


def factory(provider: Provider, context: SourceAdapterContext) -> InstalledProvider:
    assert context.provider_id == provider.id
    calls.append("factory")
    return InstalledProvider()


definition = SourceAdapterDefinition("installed-provider", factory)
