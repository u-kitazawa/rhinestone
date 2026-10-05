"""Versioned JSON-safe representations for public result values."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from math import isfinite
from typing import Any, cast

from .errors import ConfigValidationError
from .models import (
    AccessPlan,
    Config,
    DiscoveryRecord,
    FileAccessPlan,
    Metadata,
    Provenance,
    RemoteDatasetPlan,
    Resource,
    ResourceCandidate,
    Result,
    ServiceQueryPlan,
    Source,
)

_RESULT_SCHEMA = "rhinestone.result"
_RESOURCE_SCHEMA = "rhinestone.resource"
_SCHEMA_VERSION = 1


def _json_value(value: Any, path: str) -> Any:
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ConfigValidationError(f"{path} must contain finite JSON numbers")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in cast(Mapping[Any, Any], value).items():
            if not isinstance(key, str):
                raise ConfigValidationError(f"{path} must contain only string keys")
            result[key] = _json_value(item, f"{path}.{key}")
        return result
    if isinstance(value, tuple | list):
        items = cast(list[Any] | tuple[Any, ...], value)
        return [
            _json_value(item, f"{path}[{index}]") for index, item in enumerate(items)
        ]
    raise ConfigValidationError(
        f"{path} contains non-JSON value {type(value).__name__}; "
        "use strings, finite numbers, booleans, null, lists, and string-keyed mappings"
    )


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(f"{path} must be a JSON object")
    return cast(dict[str, Any], _json_value(value, path))


def _required_string(data: Mapping[str, Any], name: str, path: str) -> str:
    value = data.get(name)
    if not isinstance(value, str):
        raise ConfigValidationError(f"{path}.{name} must be a string")
    return value


def _optional_string(data: Mapping[str, Any], name: str, path: str) -> str | None:
    value = data.get(name)
    if value is not None and not isinstance(value, str):
        raise ConfigValidationError(f"{path}.{name} must be a string or null")
    return value


def _datetime_to_string(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _datetime_from_string(value: Any, path: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigValidationError(f"{path} must be an ISO 8601 string or null")
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        return datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ConfigValidationError(
            f"{path} must be a valid ISO 8601 datetime"
        ) from error


def _metadata_to_dict(value: Metadata) -> dict[str, Any]:
    return {
        "title": value.title,
        "description": value.description,
        "publisher": value.publisher,
        "license": value.license,
        "updated_at": _datetime_to_string(value.updated_at),
        "raw": _json_value(value.raw, "metadata.raw"),
    }


def _metadata_from_dict(value: Any, path: str = "metadata") -> Metadata:
    data = _mapping(value, path)
    return Metadata(
        title=_optional_string(data, "title", path),
        description=_optional_string(data, "description", path),
        publisher=_optional_string(data, "publisher", path),
        license=_optional_string(data, "license", path),
        updated_at=_datetime_from_string(data.get("updated_at"), f"{path}.updated_at"),
        raw=_mapping(data.get("raw", {}), f"{path}.raw"),
    )


def _provenance_to_dict(value: Provenance) -> dict[str, Any]:
    return {
        "provider": value.provider,
        "dataset_identifier": value.dataset_identifier,
        "resource_identifier": value.resource_identifier,
        "api_endpoint": value.api_endpoint,
        "original_url": value.original_url,
        "query_parameters": _json_value(
            value.query_parameters, "provenance.query_parameters"
        ),
        "retrieved_at": _datetime_to_string(value.retrieved_at),
        "checksum": value.checksum,
        "adapter": value.adapter,
        "adapter_version": value.adapter_version,
        "raw": _json_value(value.raw, "provenance.raw"),
    }


def _provenance_from_dict(value: Any, path: str = "provenance") -> Provenance:
    data = _mapping(value, path)
    return Provenance(
        provider=_required_string(data, "provider", path),
        dataset_identifier=_optional_string(data, "dataset_identifier", path),
        resource_identifier=_optional_string(data, "resource_identifier", path),
        api_endpoint=_optional_string(data, "api_endpoint", path),
        original_url=_optional_string(data, "original_url", path),
        query_parameters=_mapping(
            data.get("query_parameters", {}), f"{path}.query_parameters"
        ),
        retrieved_at=_datetime_from_string(
            data.get("retrieved_at"), f"{path}.retrieved_at"
        ),
        checksum=_optional_string(data, "checksum", path),
        adapter=_optional_string(data, "adapter", path),
        adapter_version=_optional_string(data, "adapter_version", path),
        raw=_mapping(data.get("raw", {}), f"{path}.raw"),
    )


def _config_to_dict(value: Config) -> dict[str, Any]:
    return {
        "source_id": value.source_id,
        "settings": _json_value(value.settings, "target.settings"),
    }


def _config_from_dict(value: Any, path: str = "target") -> Config:
    data = _mapping(value, path)
    return Config(
        source_id=_required_string(data, "source_id", path),
        settings=_mapping(data.get("settings", {}), f"{path}.settings"),
    )


def result_to_dict(value: Result) -> dict[str, Any]:
    """Return a versioned JSON-safe Result representation without its resolver."""
    return {
        "schema": _RESULT_SCHEMA,
        "version": _SCHEMA_VERSION,
        "title": value.title,
        "description": value.description,
        "discovered_by": value.discovered_by,
        "target": _config_to_dict(value.target),
        "metadata": _metadata_to_dict(value.metadata),
        "provenance": _provenance_to_dict(value.provenance),
        "formats": sorted(value.formats),
        "raw_metadata": _json_value(value.raw_metadata, "raw_metadata"),
    }


def _check_envelope(data: Mapping[str, Any], schema: str) -> None:
    if data.get("schema") != schema:
        raise ConfigValidationError(f"portable data schema must be {schema!r}")
    version = data.get("version")
    if type(version) is not int or version != _SCHEMA_VERSION:
        raise ConfigValidationError(
            f"portable data version must be {_SCHEMA_VERSION}; got {version!r}"
        )


def result_from_dict(value: Mapping[str, Any]) -> Result:
    """Restore a detached Result from its versioned JSON representation."""
    data = _mapping(value, "result")
    _check_envelope(data, _RESULT_SCHEMA)
    formats = data.get("formats", [])
    if not isinstance(formats, list):
        raise ConfigValidationError("result.formats must be a list of strings")
    format_items = cast(list[Any], formats)
    if any(not isinstance(item, str) for item in format_items):
        raise ConfigValidationError("result.formats must be a list of strings")
    return Result(
        title=_required_string(data, "title", "result"),
        description=_optional_string(data, "description", "result"),
        discovered_by=_required_string(data, "discovered_by", "result"),
        target=_config_from_dict(data.get("target")),
        metadata=_metadata_from_dict(data.get("metadata")),
        provenance=_provenance_from_dict(data.get("provenance")),
        formats=frozenset(cast(list[str], format_items)),
        raw_metadata=_mapping(data.get("raw_metadata", {}), "result.raw_metadata"),
    )


def _candidate_to_dict(value: ResourceCandidate) -> dict[str, Any]:
    return {
        "uri": value.uri,
        "format": value.format,
        "media_type": value.media_type,
        "attributes": _json_value(value.attributes, "source.candidate.attributes"),
    }


def _candidate_from_dict(value: Any, path: str) -> ResourceCandidate:
    data = _mapping(value, path)
    return ResourceCandidate(
        uri=_required_string(data, "uri", path),
        format=_optional_string(data, "format", path),
        media_type=_optional_string(data, "media_type", path),
        attributes=_mapping(data.get("attributes", {}), f"{path}.attributes"),
    )


def _source_to_dict(value: Source) -> dict[str, Any]:
    return {
        "metadata": _metadata_to_dict(value.metadata),
        "candidates": [_candidate_to_dict(item) for item in value.candidates],
        "capabilities": sorted(value.capabilities),
        "provenance": _provenance_to_dict(value.provenance),
        "raw_metadata": _json_value(value.raw_metadata, "source.raw_metadata"),
    }


def _source_from_dict(value: Any) -> Source:
    data = _mapping(value, "source")
    candidates = data.get("candidates", [])
    capabilities = data.get("capabilities", [])
    if not isinstance(candidates, list):
        raise ConfigValidationError("source.candidates must be a list")
    candidate_items = cast(list[Any], candidates)
    if not isinstance(capabilities, list):
        raise ConfigValidationError("source.capabilities must be a list of strings")
    capability_items = cast(list[Any], capabilities)
    if any(not isinstance(item, str) for item in capability_items):
        raise ConfigValidationError("source.capabilities must be a list of strings")
    return Source(
        metadata=_metadata_from_dict(data.get("metadata"), "source.metadata"),
        candidates=tuple(
            _candidate_from_dict(item, f"source.candidates[{index}]")
            for index, item in enumerate(candidate_items)
        ),
        capabilities=frozenset(cast(list[str], capability_items)),
        provenance=_provenance_from_dict(data.get("provenance"), "source.provenance"),
        raw_metadata=_mapping(data.get("raw_metadata", {}), "source.raw_metadata"),
    )


def _access_plan_to_dict(value: AccessPlan) -> dict[str, Any]:
    result = {
        "kind": value.kind,
        "uri": value.uri,
        "options": _json_value(value.options, "access_plan.options"),
    }
    if isinstance(value, FileAccessPlan):
        result["archive"] = value.archive
    return result


def _access_plan_from_dict(value: Any) -> AccessPlan:
    data = _mapping(value, "access_plan")
    kind = _required_string(data, "kind", "access_plan")
    uri = _required_string(data, "uri", "access_plan")
    options = _mapping(data.get("options", {}), "access_plan.options")
    if kind == "file":
        return FileAccessPlan(
            uri=uri,
            options=options,
            archive=_optional_string(data, "archive", "access_plan"),
        )
    if kind == "remote-dataset":
        return RemoteDatasetPlan(uri=uri, options=options)
    if kind == "service-query":
        return ServiceQueryPlan(uri=uri, options=options)
    return AccessPlan(kind=kind, uri=uri, options=options)


def _discovery_to_dict(value: DiscoveryRecord) -> dict[str, Any]:
    return {
        "source_id": value.source_id,
        "metadata": _metadata_to_dict(value.metadata),
        "provenance": _provenance_to_dict(value.provenance),
        "raw_metadata": _json_value(value.raw_metadata, "discovery.raw_metadata"),
    }


def _discovery_from_dict(value: Any) -> DiscoveryRecord:
    data = _mapping(value, "discovery")
    return DiscoveryRecord(
        source_id=_required_string(data, "source_id", "discovery"),
        metadata=_metadata_from_dict(data.get("metadata"), "discovery.metadata"),
        provenance=_provenance_from_dict(
            data.get("provenance"), "discovery.provenance"
        ),
        raw_metadata=_mapping(data.get("raw_metadata", {}), "discovery.raw_metadata"),
    )


def resource_to_dict(value: Resource) -> dict[str, Any]:
    """Return a versioned JSON-safe Resource representation without its opener."""
    return {
        "schema": _RESOURCE_SCHEMA,
        "version": _SCHEMA_VERSION,
        "uri": value.uri,
        "format": value.format,
        "media_type": value.media_type,
        "metadata": _metadata_to_dict(value.metadata),
        "provenance": _provenance_to_dict(value.provenance),
        "access_plan": _access_plan_to_dict(value.access_plan),
        "source": _source_to_dict(value.source),
        "local_path": value.local_path,
        "discovery": None
        if value.discovery is None
        else _discovery_to_dict(value.discovery),
    }


def resource_from_dict(value: Mapping[str, Any]) -> Resource:
    """Restore a detached Resource from its versioned JSON representation."""
    data = _mapping(value, "resource")
    _check_envelope(data, _RESOURCE_SCHEMA)
    discovery = data.get("discovery")
    return Resource(
        uri=_required_string(data, "uri", "resource"),
        format=_optional_string(data, "format", "resource"),
        media_type=_optional_string(data, "media_type", "resource"),
        metadata=_metadata_from_dict(data.get("metadata")),
        provenance=_provenance_from_dict(data.get("provenance")),
        access_plan=_access_plan_from_dict(data.get("access_plan")),
        source=_source_from_dict(data.get("source")),
        local_path=_optional_string(data, "local_path", "resource"),
        discovery=None if discovery is None else _discovery_from_dict(discovery),
    )
