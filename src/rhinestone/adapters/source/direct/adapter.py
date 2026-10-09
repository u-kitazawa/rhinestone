"""Source adapter for an explicitly described direct resource."""

from collections.abc import Mapping
from typing import Any, cast

from ....models import Metadata, Provenance, Reference, Resource
from ....resolution import resource_from_delivery
from ..base import ProviderAdapter


class DirectAdapter(ProviderAdapter):
    """Interpret a complete direct-resource declaration without guessing."""

    adapter_type = "direct"

    def __init__(self) -> None:
        super().__init__(get_json=lambda url, params: None)

    def load(self, reference: Reference) -> Resource:
        """Build a Resource from a complete, explicitly described delivery."""
        settings = self._reference_parameters(reference)
        uri = self._required_string(settings, "uri")
        format_name = self._required_string(settings, "format")
        media_type = _optional_string(settings.get("media_type"))
        raw_metadata = cast(Mapping[str, Any], settings.get("metadata", {}))
        options = {
            key: settings[key] for key in ("layer", "subdataset") if key in settings
        }
        metadata = Metadata(
            title=_optional_string(raw_metadata.get("title")),
            description=_optional_string(raw_metadata.get("description")),
            publisher=_optional_string(raw_metadata.get("publisher")),
            license=_optional_string(raw_metadata.get("license")),
            raw=raw_metadata,
        )
        provenance = Provenance(
            provider="direct",
            original_url=uri,
            adapter="direct",
            raw=settings,
        )
        return resource_from_delivery(
            reference=reference,
            uri=uri,
            format=format_name,
            media_type=media_type,
            metadata=metadata,
            provenance=provenance,
            options=options,
            archive=_optional_string(settings.get("archive")),
            encoding=_optional_string(settings.get("encoding")),
        )


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
