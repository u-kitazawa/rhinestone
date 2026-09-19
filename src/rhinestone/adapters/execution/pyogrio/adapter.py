"""Pyogrio execution adapter."""

from typing import Any
from urllib.parse import urlparse

from ....errors import ResourceAccessError
from ....models import FileAccessPlan, Resource
from ....representations import FORMAT_CATEGORIES, canonical_format
from ....security import DestinationPolicy
from .._resource import resource_attributes
from ..base import ExecutionAdapter


class PyogrioAdapter(ExecutionAdapter):
    """Delegate vector Resources to a supplied pyogrio module."""

    name = "pyogrio"
    priority = 10
    # Source adapters must declare ``Resource.format``; this registry never
    # infers a format from a URI or from an archive member.  Keeping the
    # compatibility boundary in the shared representation vocabulary lets new
    # explicitly supported vector formats reach the injected pyogrio runtime.
    _formats = frozenset(
        format_name
        for format_name, category in FORMAT_CATEGORIES.items()
        if category == "vector"
    )

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        super().__init__(destination_policy)

    def supports(self, resource: Resource, dependencies: frozenset[str]) -> bool:
        """Return whether pyogrio can be tried for an explicit vector format.

        Runtime driver availability is environment-specific.  This selection
        check admits only the maintained, explicitly declared vector registry;
        a missing driver or an unsupported geometry/field type is reported by
        :meth:`open` as :class:`~rhinestone.errors.ResourceAccessError`.
        """
        return (
            canonical_format(resource.format) in self._formats
            and self.name in dependencies
        )

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        """Read the selected vector Resource with ``runtime.read_dataframe``."""
        attributes = resource_attributes(resource)
        options: dict[str, Any] = {}
        encoding = attributes.get("encoding")
        if isinstance(encoding, str):
            options["encoding"] = encoding
        try:
            return runtime.read_dataframe(self._runtime_uri(resource), **options)
        except Exception as error:
            raise ResourceAccessError(
                f"pyogrio could not open {resource.uri!r}"
            ) from error

    @staticmethod
    def _runtime_uri(resource: Resource) -> str:
        """Translate an explicit ZIP access plan to GDAL's VSI URI syntax."""
        attributes = resource_attributes(resource)
        archive = attributes.get("archive")
        if isinstance(resource.access_plan, FileAccessPlan):
            archive = resource.access_plan.archive or archive
        if archive != "zip":
            return resource.uri

        uri = resource.uri
        prefix = (
            "/vsizip//vsicurl/"
            if urlparse(uri).scheme.casefold()
            in {
                "http",
                "https",
            }
            else "/vsizip/"
        )
        member = resource.access_plan.options.get("entry_point")
        return prefix + uri + ("/" + member if isinstance(member, str) else "")
