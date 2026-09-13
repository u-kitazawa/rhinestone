"""Small read-only service ports exposed to user-owned adapters."""

from typing import Any, FrozenSet, Mapping, Optional, Protocol


class CredentialPort(Protocol):
    """Read-only credential lookup exposed to external adapters."""

    def get(self, name: str) -> str:
        """Resolve one logical credential without exposing registry storage."""
        ...


class DependencyPort(Protocol):
    """Read-only runtime dependency lookup exposed to external adapters."""

    @property
    def available(self) -> FrozenSet[str]:
        """Return dependency names visible to this adapter."""
        ...

    def get(self, name: str) -> Any:
        """Resolve one visible dependency."""
        ...


class TransportPort(Protocol):
    """Core-managed HTTP transport with policy and error normalization."""

    def get_json(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """Fetch and decode one JSON response."""
        ...

    def get_text(self, url: str) -> str:
        """Fetch one text response."""
        ...


__all__ = ["CredentialPort", "DependencyPort", "TransportPort"]
