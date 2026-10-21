"""Metadata-only discovery and selected Definition loading via Python packaging."""

from collections.abc import Callable, Iterator, Mapping
from importlib import metadata
from threading import RLock
from typing import Generic, TypeVar

from .errors import (
    AdapterContractError,
    AdapterDiscoveryError,
    AdapterLoadError,
)

PROVIDER_GROUP = "rhinestone.provider_adapters"
RUNTIME_GROUP = "rhinestone.runtime_adapters"
KNOWLEDGE_GROUP = "rhinestone.knowledge_adapters"
GROUPS = (PROVIDER_GROUP, RUNTIME_GROUP, KNOWLEDGE_GROUP)

_Definition = TypeVar("_Definition")


def discover() -> Mapping[str, tuple[metadata.EntryPoint, ...]]:
    """Read package metadata once without loading any exported Python objects."""
    points = metadata.entry_points()
    return {group: tuple(points.select(group=group)) for group in GROUPS}


def _origin(point: metadata.EntryPoint) -> str:
    distribution = point.dist
    name = distribution.name if distribution is not None else "unknown distribution"
    return f"{name!r}, group {point.group!r}, identity {point.name!r}"


class DefinitionIndex(Mapping[str, _Definition], Generic[_Definition]):
    """Combine explicit definitions and lazy exports in an application-local index.

    Iteration exposes identities only. Access by identity loads and validates
    the selected export once; unused exports and optional dependencies stay
    untouched. Factories are executed by the normal composition path.
    """

    def __init__(
        self,
        definitions: Mapping[str, _Definition],
        points: tuple[metadata.EntryPoint, ...],
        definition_type: type[_Definition],
        identity: Callable[[_Definition], str],
    ) -> None:
        self._definitions = dict(definitions)
        self._points: dict[str, metadata.EntryPoint] = {}
        self._loaded: dict[str, _Definition] = {}
        self._type = definition_type
        self._identity = identity
        self._lock = RLock()
        for point in points:
            if not point.name.strip():
                raise AdapterDiscoveryError(f"Empty adapter identity: {_origin(point)}")
            if point.name in self._definitions:
                raise AdapterDiscoveryError(
                    f"Duplicate adapter identity: {_origin(point)} conflicts with "
                    "an explicit or built-in definition"
                )
            if point.name in self._points:
                previous = self._points[point.name]
                raise AdapterDiscoveryError(
                    f"Duplicate adapter identity: {_origin(point)} conflicts with "
                    f"{_origin(previous)}"
                )
            self._points[point.name] = point

    def __iter__(self) -> Iterator[str]:
        # Loading a definition must not change iteration order.
        return iter((*self._definitions, *self._points))

    def __len__(self) -> int:
        return len(self._definitions) + len(self._points)

    def __contains__(self, name: object) -> bool:
        return name in self._definitions or name in self._points

    def origin(self, name: str) -> str | None:
        """Return installed metadata context without importing the export."""
        point = self._points.get(name)
        return None if point is None else _origin(point)

    def __getitem__(self, name: str) -> _Definition:
        with self._lock:
            if name in self._definitions:
                return self._definitions[name]
            if name in self._loaded:
                return self._loaded[name]
            point = self._points[name]
            try:
                exported = point.load()
            except Exception:
                # Plugin import errors may contain arbitrary payloads or secrets.
                raise AdapterLoadError(
                    f"Cannot import adapter export: {_origin(point)}; inspect the "
                    "installed package and its dependencies"
                ) from None
            if not isinstance(exported, self._type):
                raise AdapterContractError(
                    f"Invalid adapter export: {_origin(point)}; expected "
                    f"{self._type.__name__}"
                )
            if self._identity(exported) != name:
                raise AdapterContractError(
                    f"Adapter export identity does not match its entry point: "
                    f"{_origin(point)}"
                )
            self._loaded[name] = exported
            return exported
