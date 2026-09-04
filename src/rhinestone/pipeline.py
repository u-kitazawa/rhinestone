"""Application pipeline from Config through Source to user-owned runtime."""

from dataclasses import replace
from typing import Any, Iterable, Optional

from .errors import ProviderMetadataError, RhinestoneError, UnsupportedSourceError
from .execution import ExecutionAdapterSelector
from .models import Config, Resource
from .registry import DependencyRegistry
from .resolution import Resolver


class AccessPipeline:
    def __init__(
        self,
        source_adapters: Iterable[Any],
        resolver: Resolver,
        execution_selector: Optional[ExecutionAdapterSelector] = None,
        dependencies: Optional[DependencyRegistry] = None,
    ) -> None:
        self._source_adapters = tuple(source_adapters)
        self._resolver = resolver
        self._execution_selector = execution_selector
        self._dependencies = dependencies

    def resolve(self, config: Config) -> Resource:
        matches = [
            adapter
            for adapter in self._source_adapters
            if adapter.source_type == config.source_type
        ]
        if not matches:
            raise UnsupportedSourceError(
                f"Source type {config.source_type!r} is not supported"
            )
        if len(matches) > 1:
            raise UnsupportedSourceError(
                f"Source type {config.source_type!r} is ambiguous"
            )
        try:
            source = matches[0].load(config)
        except RhinestoneError:
            raise
        except Exception as error:
            raise ProviderMetadataError(
                f"Provider metadata for {config.source_type!r} could not be loaded"
            ) from error
        resource = self._resolver.resolve(source)
        if self._execution_selector is None or self._dependencies is None:
            return resource
        selector = self._execution_selector
        dependencies = self._dependencies

        def open_resource(requested: Optional[str]) -> Any:
            return self._open_resource(resource, requested, selector, dependencies)

        return replace(
            resource,
            _opener=open_resource,
        )

    def open(self, config: Config, adapter: Optional[str] = None) -> Any:
        return self.resolve(config).open(adapter=adapter)

    @staticmethod
    def _open_resource(
        resource: Resource,
        requested: Optional[str],
        selector: ExecutionAdapterSelector,
        dependencies: DependencyRegistry,
    ) -> Any:
        selected = selector.select(
            resource,
            dependencies.available,
            requested=requested,
        )
        runtime = dependencies.get(selected.name)
        return selected.open(resource, runtime)
