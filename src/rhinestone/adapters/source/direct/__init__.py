"""Source adapter for an explicitly described direct resource."""

from typing import Any, Mapping, Optional, cast

from ....errors import ConfigValidationError
from ....models import Config, Metadata, Provenance, ResourceCandidate, Source
from ..base import ProviderAdapter


class DirectAdapter(ProviderAdapter):
    """Interpret a complete direct-resource declaration without guessing."""

    source_type = "direct"

    def __init__(self) -> None:
        super().__init__(get_json=lambda url, params: None)

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        for forbidden in ("gdal", "rasterio", "pyogrio", "http_client"):
            if forbidden in settings:
                raise ConfigValidationError(
                    f"Runtime or transport detail {forbidden!r} is not allowed"
                )
        uri = self._required_string(settings, "uri")
        format_name = self._required_string(settings, "format")
        media_type = _optional_string(settings.get("media_type"))
        supplied_metadata = settings.get("metadata", {})
        if not isinstance(supplied_metadata, Mapping):
            raise ConfigValidationError("metadata must be an object")
        raw_metadata = cast(Mapping[str, Any], supplied_metadata)
        attributes = {
            key: settings[key]
            for key in ("archive", "encoding", "layer", "subdataset")
            if key in settings
        }
        candidate = ResourceCandidate(
            uri=uri,
            format=format_name,
            media_type=media_type,
            attributes=attributes,
        )
        provenance = Provenance(
            provider="direct",
            original_url=uri,
            adapter="direct",
            raw=settings,
        )
        return Source(
            metadata=Metadata(
                title=_optional_string(raw_metadata.get("title")),
                description=_optional_string(raw_metadata.get("description")),
                publisher=_optional_string(raw_metadata.get("publisher")),
                license=_optional_string(raw_metadata.get("license")),
                raw=raw_metadata,
            ),
            candidates=(candidate,),
            capabilities=frozenset({"download"}),
            provenance=provenance,
            raw_metadata=settings,
        )


def _optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None
