"""Application pipeline from Config through Source to user-owned runtime."""

from dataclasses import replace
from typing import Any, Optional

from .errors import ProviderMetadataError, RhinestoneError
from .execution import ExecutionAdapterSelector
from .models import Config, LibraryName, Resource
from .registry import AdapterRegistry, DependencyRegistry
from .resolution import Resolver
from .security import DestinationPolicy


class AccessPipeline:
    def __init__(
        self,
        adapter_registry: AdapterRegistry,
        resolver: Resolver,
        execution_selector: Optional[ExecutionAdapterSelector] = None,
        dependencies: Optional[DependencyRegistry] = None,
        destination_policy: Optional[DestinationPolicy] = None,
    ) -> None:
        self._adapter_registry = adapter_registry
        self._resolver = resolver
        self._execution_selector = execution_selector
        self._dependencies = dependencies
        self._destination_policy = (
            destination_policy or DestinationPolicy.unrestricted()
        )

    def resolve(self, config: Config) -> Resource:
        adapter = self._adapter_registry.source(config.source_id)
        try:
            source = adapter.load(config)
        except RhinestoneError:
            raise
        except Exception as error:
            raise ProviderMetadataError(
                f"Provider metadata for {config.source_id!r} could not be loaded"
            ) from error
        resource = self._resolver.resolve(source)
        if self._execution_selector is None or self._dependencies is None:
            return resource
        selector = self._execution_selector
        dependencies = self._dependencies
        destination_policy = self._destination_policy

        def open_resource(library: LibraryName) -> object:
            return AccessPipeline._open_resource(
                resource,
                library,
                selector,
                dependencies,
                destination_policy,
            )

        return replace(
            resource,
            _opener=open_resource,
        )

    def open(self, config: Config, library: LibraryName) -> object:
        return self.resolve(config).open(library)

    def open_resource(self, resource: Resource, library: LibraryName) -> object:
        """Open an existing Resource using this pipeline's policy and runtimes."""
        if self._execution_selector is None or self._dependencies is None:
            raise ProviderMetadataError("Execution pipeline is not configured")
        return self._open_resource(
            resource,
            library,
            self._execution_selector,
            self._dependencies,
            self._destination_policy,
        )

    @staticmethod
    def _open_resource(
        resource: Resource,
        library: LibraryName,
        selector: ExecutionAdapterSelector,
        dependencies: DependencyRegistry,
        destination_policy: DestinationPolicy,
    ) -> Any:
        selected = selector.select(
            resource,
            dependencies.available,
            requested=library,
        )
        authorize = getattr(selected, "authorize", None)
        if callable(authorize):
            authorize(resource, destination_policy=destination_policy)
        else:
            destination_policy.authorize(resource.uri)
        runtime = dependencies.get(selected.name)
        return selected.open(
            resource,
            runtime,
            destination_policy=destination_policy,
        )
