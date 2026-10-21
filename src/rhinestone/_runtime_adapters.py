"""Application-local instances of selected Runtime Adapter definitions."""

from collections.abc import Callable, Iterator, Mapping
from threading import RLock

from .adapters.contracts import RuntimeAdapter, RuntimeAdapterDefinition


class RuntimeInstances(Mapping[str, RuntimeAdapter]):
    """Keep metadata identities separate from selected adapter construction."""

    def __init__(
        self,
        definitions: Mapping[str, RuntimeAdapterDefinition],
        build: Callable[[RuntimeAdapterDefinition], RuntimeAdapter],
        instances: Mapping[str, RuntimeAdapter],
    ) -> None:
        self._definitions = definitions
        self._build = build
        self._instances = dict(instances)
        self._lock = RLock()

    def __iter__(self) -> Iterator[str]:
        return iter(self._definitions)

    def __len__(self) -> int:
        return len(self._definitions)

    def __contains__(self, name: object) -> bool:
        return name in self._definitions

    def __getitem__(self, name: str) -> RuntimeAdapter:
        with self._lock:
            if name not in self._instances:
                definition = self._definitions[name]
                self._instances[name] = self._build(definition)
            return self._instances[name]
