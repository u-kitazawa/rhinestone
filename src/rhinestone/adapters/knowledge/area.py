"""Administrative-area knowledge adapters."""

from collections.abc import Iterable

from ...errors import KnowledgeResolutionError, KnowledgeValidationError
from .models import AdministrativeArea


class StaticAdministrativeAreaAdapter:
    """Resolve exact administrative-area names, aliases, or codes.

    The adapter owns an immutable snapshot supplied by Rhinestone. It performs
    no network access and deliberately avoids fuzzy matching.
    """

    def __init__(self, areas: Iterable[AdministrativeArea]) -> None:
        self._areas = tuple(areas)
        self._index: dict[str, tuple[AdministrativeArea, ...]] = {}
        for area in self._areas:
            for key in (area.canonical_name, area.code, *area.aliases):
                normalized = key.strip().casefold()
                self._index[normalized] = (*self._index.get(normalized, ()), area)

    def resolve_area(self, value: str) -> AdministrativeArea:
        """Resolve one exact area expression or fail closed."""
        if not isinstance(value, str) or not value.strip():
            raise KnowledgeValidationError("area value must be a non-empty string")
        matches = self._index.get(value.strip().casefold(), ())
        if not matches:
            raise KnowledgeResolutionError(
                f"administrative area {value!r} is not available in the configured "
                "snapshot; use a canonical name, alias, or code"
            )
        unique = tuple(dict.fromkeys(matches))
        if len(unique) != 1:
            raise KnowledgeResolutionError(
                f"administrative area {value!r} is ambiguous in the configured "
                "snapshot; use an explicit code"
            )
        return unique[0]


__all__ = ["StaticAdministrativeAreaAdapter"]
