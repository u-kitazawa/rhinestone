"""Explicit local access to downloaded GSI fundamental vector data."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from ....errors import ResourceNotFoundError
from ....models import Metadata, Provenance, Reference, Resource
from ....resolution import resource_from_delivery
from ...knowledge import KnowledgeAdapterRegistry
from .._knowledge import entry_point, resolve_knowledge, string
from ..base import ProviderAdapter


class GsiFundamentalAdapter(ProviderAdapter):
    """Resolve local GSI Fundamental geospatial data declarations."""

    adapter_type = "gsi-fundamental"

    def __init__(self, knowledge: KnowledgeAdapterRegistry | None = None) -> None:
        super().__init__(get_json=lambda url, params: None)
        self._knowledge = knowledge or KnowledgeAdapterRegistry()

    def load(self, reference: Reference) -> Resource:
        """Build a Resource for the configured local GML data file."""
        settings = self._reference_parameters(reference)
        path = Path(string(settings, "path")).absolute()
        if not path.is_file():
            raise ResourceNotFoundError("Local fundamental data file does not exist")
        metadata = cast(Mapping[str, Any], settings["metadata"])
        archive = settings.get("archive")
        member = entry_point(settings)
        knowledge = resolve_knowledge(settings, self._knowledge)
        raw = {"metadata": metadata, "knowledge": knowledge}
        identifier = str(metadata["mesh"])
        provenance = Provenance(
            provider=self.adapter_type,
            dataset_identifier=identifier,
            original_url=str(path),
            adapter=self.adapter_type,
            raw=raw,
        )
        return resource_from_delivery(
            reference=Reference(
                reference.provider_id,
                dataset_identifier=identifier,
                resource_identifier=str(path),
                parameters=reference.parameters,
            ),
            uri=str(path),
            format="gml",
            media_type="application/gml+xml",
            metadata=Metadata(
                title=identifier,
                publisher=self.adapter_type,
                raw=raw,
            ),
            provenance=provenance,
            kind="file",
            archive=archive if isinstance(archive, str) else None,
            options={} if member is None else {"entry_point": member},
        )
