"""Internal helpers for declarative provider knowledge (not an extension API)."""

from pathlib import PurePosixPath
from typing import Any, Mapping, Optional, Tuple

from ...errors import ConfigValidationError
from ...models import Metadata, Provenance, ResourceCandidate, Source


def string(settings: Mapping[str, Any], name: str) -> str:
    value = settings.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"{name} must be a non-empty string")
    return value


def entry_point(settings: Mapping[str, Any]) -> Optional[str]:
    value = settings.get("entry_point")
    if value is None:
        if settings.get("archive") == "zip":
            raise ConfigValidationError("ZIP input requires entry_point")
        return None
    value = string(settings, "entry_point")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ConfigValidationError("entry_point must be a relative archive path")
    return value


def source(
    provider: str,
    identifier: str,
    raw: Mapping[str, Any],
    candidates: Tuple[ResourceCandidate, ...],
    title: Optional[str] = None,
    description: Optional[str] = None,
    license_name: Optional[str] = None,
    endpoint: Optional[str] = None,
    capabilities: Tuple[str, ...] = (),
) -> Source:
    return Source(
        metadata=Metadata(
            title=title or identifier,
            description=description,
            publisher=provider,
            license=license_name,
            raw=raw,
        ),
        candidates=candidates,
        capabilities=frozenset(capabilities),
        provenance=Provenance(
            provider=provider,
            dataset_identifier=identifier,
            api_endpoint=endpoint,
            adapter=provider,
            raw=raw,
        ),
        raw_metadata=raw,
    )
