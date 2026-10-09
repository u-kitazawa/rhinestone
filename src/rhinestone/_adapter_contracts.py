"""Internal capability contracts for composed adapter instances."""

from typing import Protocol, TypeGuard, runtime_checkable

from .models import ProviderSearchResults, Reference, Resource, SearchQuery


class RegisteredSourceAdapter(Protocol):
    """Source adapter bound to an application-local source identity."""

    source_id: str

    def load(self, reference: Reference) -> Resource:
        """Load the unique delivery selected by ``reference``."""
        ...


class SearchParticipant(Protocol):
    """Configured source that can participate in capability discovery."""

    source_id: str


@runtime_checkable
class SearchableRegisteredSourceAdapter(Protocol):
    """Configured source with the complete federated-search capability."""

    source_id: str
    searchable: bool
    search_conditions: frozenset[str]
    required_search_conditions: frozenset[str]
    area_text_fallback: bool

    def search(
        self, query: SearchQuery
    ) -> tuple[Resource, ...] | ProviderSearchResults:
        """Search the configured provider."""
        ...


def is_searchable_source(
    adapter: SearchParticipant,
) -> TypeGuard[SearchableRegisteredSourceAdapter]:
    """Narrow a configured source to the federated-search contract."""
    return isinstance(adapter, SearchableRegisteredSourceAdapter) and adapter.searchable
