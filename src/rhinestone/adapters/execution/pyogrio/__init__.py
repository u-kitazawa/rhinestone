"""Pyogrio execution adapter."""

from typing import Any, Dict, FrozenSet

from ....errors import ResourceAccessError
from ....models import Resource
from ....security import DestinationPolicy
from .._locator import authorize_runtime_locator
from .._resource import resource_attributes
from ..base import ExecutionAdapter


class PyogrioAdapter(ExecutionAdapter):
    """Delegate vector Resources to a supplied pyogrio module."""

    name = "pyogrio"
    priority = 10
    _formats = frozenset({"shapefile", "geojson", "gpkg", "flatgeobuf"})

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        super().__init__(destination_policy)

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        return (
            resource.format or ""
        ).lower() in self._formats and self.name in dependencies

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        authorize_runtime_locator(
            resource.uri, destination_policy or self._destination_policy
        )
        attributes = resource_attributes(resource)
        options: Dict[str, Any] = {}
        encoding = attributes.get("encoding")
        if isinstance(encoding, str):
            options["encoding"] = encoding
        try:
            return runtime.read_dataframe(resource.uri, **options)
        except Exception as error:
            raise ResourceAccessError(
                f"pyogrio could not open {resource.uri!r}"
            ) from error
