"""Internal helpers for declarative provider knowledge (not an extension API)."""

from pathlib import PurePosixPath
from typing import Any, Mapping, Optional, Tuple, cast

from ...errors import ConfigValidationError
from ...models import Metadata, Provenance, ResourceCandidate, Source
from ..knowledge import KnowledgeAdapterRegistry, TimeKind


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


def resolve_knowledge(
    settings: Mapping[str, Any], registry: KnowledgeAdapterRegistry
) -> Mapping[str, Mapping[str, object]]:
    """Resolve explicit shared knowledge settings without guessing provider data."""
    resolved: dict[str, Mapping[str, object]] = {}
    if "municipality" in settings:
        value = string(settings, "municipality")
        resolved["identity"] = registry.resolve_municipality(value).as_mapping()
    if "time" in settings:
        value = string(settings, "time")
        time_kind = settings.get("time_kind")
        if time_kind is not None and time_kind not in {
            "calendar_year",
            "fiscal_year",
            "survey_year",
            "as_of_date",
        }:
            raise ConfigValidationError("time_kind must be a supported time kind")
        resolved["time"] = registry.resolve_time(
            value, kind=cast(Optional[TimeKind], time_kind)
        ).as_mapping()
    return resolved
