"""Registry for injectable shared knowledge adapters."""

from dataclasses import replace
from typing import Dict, Iterable, Optional, Tuple, cast

from ...errors import (
    AdapterRegistrationError,
    KnowledgeAdapterUnavailableError,
    KnowledgeResolutionError,
)
from .base import (
    IdentityKnowledgeAdapter,
    KnowledgeAdapter,
    KnowledgeAdapterContext,
    KnowledgeAdapterDefinition,
    KnowledgeKind,
    TimeKnowledgeAdapter,
)
from .models import MunicipalityIdentity, TimeKind, TimeSemantic


class KnowledgeAdapterRegistry:
    """Select and lazily instantiate one registered adapter for each kind."""

    def __init__(
        self,
        definitions: Iterable[KnowledgeAdapterDefinition] = (),
        context: Optional[KnowledgeAdapterContext] = None,
    ) -> None:
        self._definitions: Dict[KnowledgeKind, KnowledgeAdapterDefinition] = {}
        self._instances: Dict[KnowledgeKind, KnowledgeAdapter] = {}
        self._context = context
        for definition in definitions:
            if definition.kind in self._definitions:
                raise AdapterRegistrationError(
                    f"Knowledge adapter kind {definition.kind!r} is registered more than once"
                )
            self._definitions[definition.kind] = definition

    @property
    def available(self) -> Tuple[KnowledgeKind, ...]:
        """Return configured knowledge kinds in registration order."""
        return tuple(self._definitions)

    def adapter_type(self, kind: KnowledgeKind) -> str:
        """Return the configured adapter type for one knowledge kind."""
        return self._definition(kind).adapter_type

    def identity(self) -> IdentityKnowledgeAdapter:
        adapter = self._get("identity")
        if not callable(getattr(adapter, "resolve_municipality", None)):
            raise KnowledgeResolutionError(
                "identity knowledge adapter does not implement resolve_municipality"
            )
        return cast(IdentityKnowledgeAdapter, adapter)

    def time(self) -> TimeKnowledgeAdapter:
        adapter = self._get("time")
        if not callable(getattr(adapter, "resolve_time", None)):
            raise KnowledgeResolutionError(
                "time knowledge adapter does not implement resolve_time"
            )
        return cast(TimeKnowledgeAdapter, adapter)

    def resolve_municipality(self, value: str) -> MunicipalityIdentity:
        identity = self.identity().resolve_municipality(value)
        if not isinstance(cast(object, identity), MunicipalityIdentity):
            raise KnowledgeResolutionError(
                "identity knowledge adapter returned an invalid value"
            )
        return identity

    def resolve_time(
        self, value: str, *, kind: Optional[TimeKind] = None
    ) -> TimeSemantic:
        semantic = self.time().resolve_time(value, kind=kind)
        if not isinstance(cast(object, semantic), TimeSemantic):
            raise KnowledgeResolutionError(
                "time knowledge adapter returned an invalid value"
            )
        return semantic

    def _definition(self, kind: KnowledgeKind) -> KnowledgeAdapterDefinition:
        try:
            return self._definitions[kind]
        except KeyError:
            raise KnowledgeAdapterUnavailableError(
                f"Knowledge adapter for {kind!r} is not configured"
            ) from None

    def _get(self, kind: KnowledgeKind) -> KnowledgeAdapter:
        if kind in self._instances:
            return self._instances[kind]
        definition = self._definition(kind)
        if self._context is None:
            raise KnowledgeResolutionError(
                "Knowledge adapter registry has no factory context"
            )
        context = replace(
            self._context,
            dependencies=self._context.dependencies.scoped(definition.dependencies),
        )
        try:
            adapter = definition.factory(context)
        except Exception as error:
            raise KnowledgeResolutionError(
                f"Knowledge adapter {definition.adapter_type!r} could not be loaded"
            ) from error
        self._instances[kind] = adapter
        return adapter


__all__ = ["KnowledgeAdapterRegistry"]
