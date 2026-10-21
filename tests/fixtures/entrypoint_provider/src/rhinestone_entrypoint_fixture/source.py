"""Provider export for the independent extension wheel."""

from rhinestone.adapters.contracts import SourceAdapterContext, SourceAdapterDefinition
from rhinestone.adapters.knowledge import KnowledgePort
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

    def __init__(self, knowledge: KnowledgePort) -> None:
        self.knowledge = knowledge

    def load(self, reference: Reference) -> Resource:
        calls.append("load")
        return resource_from_delivery(
            reference=reference,
            uri="https://fixture.example/installed.tif",
            format="geotiff",
            media_type="image/tiff",
            metadata=Metadata(
                title="Installed",
                raw={
                    "package": "independent wheel",
                    "resolved_year": self.knowledge.resolve_time("2020").year,
                },
            ),
            provenance=Provenance(provider="installed-provider"),
        )

    def search(self, query: SearchQuery) -> tuple[Resource, ...]:
        calls.append("search")
        return (self.load(Reference("installed-provider", resource_identifier="one")),)


def factory(provider: Provider, context: SourceAdapterContext) -> InstalledProvider:
    assert context.provider_id == provider.id
    calls.append("factory")
    return InstalledProvider(context.knowledge)


definition = SourceAdapterDefinition("installed-provider", factory)
