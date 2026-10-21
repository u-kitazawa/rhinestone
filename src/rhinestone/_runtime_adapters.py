"""Application-local instances of selected Runtime Adapter definitions."""

from collections.abc import Callable, Iterator, Mapping
from threading import RLock

from .adapters.contracts import ExecutionAdapter, ExecutionAdapterDefinition


class ExecutionInstances(Mapping[str, ExecutionAdapter]):
    """Keep metadata identities separate from selected adapter construction."""

    def __init__(
        self,
        definitions: Mapping[str, ExecutionAdapterDefinition],
        build: Callable[[ExecutionAdapterDefinition], ExecutionAdapter],
        instances: Mapping[str, ExecutionAdapter],
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

    def __getitem__(self, name: str) -> ExecutionAdapter:
        with self._lock:
            if name not in self._instances:
                definition = self._definitions[name]
                self._instances[name] = self._build(definition)
            return self._instances[name]
