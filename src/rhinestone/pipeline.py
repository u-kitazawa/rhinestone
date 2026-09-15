"""Application pipeline from Config through Source to user-owned runtime."""

from dataclasses import replace
from typing import Any

from .errors import ProviderMetadataError, RhinestoneError
from .execution import ExecutionAdapterSelector
from .models import Config, LibraryName, Resource
from .registry import AdapterRegistry, DependencyRegistry
from .resolution import Resolver
from .security import DestinationPolicy


class AccessPipeline:
    """Run Config through Source, resolution, and execution boundaries."""

    def __init__(
        self,
        adapter_registry: AdapterRegistry,
        resolver: Resolver,
        execution_selector: ExecutionAdapterSelector | None = None,
        dependencies: DependencyRegistry | None = None,
        destination_policy: DestinationPolicy | None = None,
    ) -> None:
        self._adapter_registry = adapter_registry
        self._resolver = resolver
        self._execution_adapter_selector = execution_selector
        self._dependency_registry = dependencies
        self._destination_policy = (
            destination_policy or DestinationPolicy.unrestricted()
        )

    def resolve(self, config: Config) -> Resource:
        """Load provider metadata and resolve ``config`` into a Resource."""
        adapter = self._adapter_registry.source(config.source_id)
        try:
            source = adapter.load(config)
        except RhinestoneError:
            raise
        except Exception as error:
            raise ProviderMetadataError(
                f"Provider metadata for source {config.source_id!r} could not be "
                "loaded; inspect the endpoint and provider availability"
            ) from error
        resource = self._resolver.resolve(source)
        if (
            self._execution_adapter_selector is None
            or self._dependency_registry is None
        ):
            return resource
        selector = self._execution_adapter_selector
        dependencies = self._dependency_registry
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
        """Resolve ``config`` and open its Resource through ``library``."""
        return self.resolve(config).open(library)

    def open_resource(self, resource: Resource, library: LibraryName) -> object:
        """Open an existing Resource using this pipeline's policy and runtimes."""
        if (
            self._execution_adapter_selector is None
            or self._dependency_registry is None
        ):
            raise ProviderMetadataError(
                "Execution pipeline is not configured; construct the public "
                "application with configure() before opening a Resource"
            )
        return self._open_resource(
            resource,
            library,
            self._execution_adapter_selector,
            self._dependency_registry,
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
