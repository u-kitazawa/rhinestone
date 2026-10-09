"""Versioned JSON-safe representations for public result values."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from math import isfinite
from typing import Any, cast

from .errors import ConfigValidationError
from .models import (
    AccessPlan,
    DiscoveryRecord,
    Metadata,
    Provenance,
    Reference,
    Resource,
)

_ACCESS_PLAN_SCHEMA = "rhinestone.access-plan"
_ACCESS_PLAN_VERSION = 1
_RESOURCE_SCHEMA = "rhinestone.resource"
_RESOURCE_VERSION = 3


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


def _reference_to_dict(value: Reference) -> dict[str, Any]:
    return {
        "provider_id": value.provider_id,
        "dataset_identifier": value.dataset_identifier,
        "resource_identifier": value.resource_identifier,
        "parameters": _json_value(value.parameters, "reference.parameters"),
    }


def _reference_from_dict(value: Any) -> Reference:
    data = _mapping(value, "reference")
    return Reference(
        provider_id=_required_string(data, "provider_id", "reference"),
        dataset_identifier=_optional_string(data, "dataset_identifier", "reference"),
        resource_identifier=_optional_string(data, "resource_identifier", "reference"),
        parameters=_mapping(data.get("parameters", {}), "reference.parameters"),
    )


def _check_envelope(data: Mapping[str, Any], schema: str, version: int) -> None:
    if data.get("schema") != schema:
        raise ConfigValidationError(f"portable data schema must be {schema!r}")
    actual_version = data.get("version")
    if type(actual_version) is not int or actual_version != version:
        raise ConfigValidationError(
            f"portable data version must be {version}; got {actual_version!r}"
        )


def access_plan_to_dict(value: AccessPlan) -> dict[str, Any]:
    """Return a versioned, JSON-safe standalone AccessPlan contract."""
    return {
        "schema": _ACCESS_PLAN_SCHEMA,
        "version": _ACCESS_PLAN_VERSION,
        "kind": value.kind,
        "uri": value.uri,
        "format": value.format,
        "media_type": value.media_type,
        "options": _json_value(value.options, "access_plan.options"),
        "provider": value.provider,
        "service": value.service,
        "credential": value.credential,
    }


def access_plan_from_dict(value: Mapping[str, Any]) -> AccessPlan:
    """Validate and restore a standalone AccessPlan contract."""
    data = _mapping(value, "access_plan")
    _check_envelope(data, _ACCESS_PLAN_SCHEMA, _ACCESS_PLAN_VERSION)
    return AccessPlan(
        kind=_required_string(data, "kind", "access_plan"),
        uri=_required_string(data, "uri", "access_plan"),
        format=_optional_string(data, "format", "access_plan"),
        media_type=_optional_string(data, "media_type", "access_plan"),
        options=_mapping(data.get("options", {}), "access_plan.options"),
        provider=_optional_string(data, "provider", "access_plan"),
        service=_optional_string(data, "service", "access_plan"),
        credential=_optional_string(data, "credential", "access_plan"),
    )


def _access_plan_to_dict(value: AccessPlan) -> dict[str, Any]:
    return access_plan_to_dict(value)


def _access_plan_from_dict(value: Any) -> AccessPlan:
    return access_plan_from_dict(_mapping(value, "access_plan"))


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
        "version": _RESOURCE_VERSION,
        "uri": value.uri,
        "format": value.format,
        "media_type": value.media_type,
        "metadata": _metadata_to_dict(value.metadata),
        "provenance": _provenance_to_dict(value.provenance),
        "access_plan": (
            None
            if value.access_plan is None
            else _access_plan_to_dict(value.access_plan)
        ),
        "reference": _reference_to_dict(value.reference),
        "local_path": value.local_path,
        "discovery": None
        if value.discovery is None
        else _discovery_to_dict(value.discovery),
    }


def resource_from_dict(value: Mapping[str, Any]) -> Resource:
    """Restore a detached Resource from its versioned JSON representation."""
    data = _mapping(value, "resource")
    _check_envelope(data, _RESOURCE_SCHEMA, _RESOURCE_VERSION)
    discovery = data.get("discovery")
    access_plan = data.get("access_plan")
    return Resource(
        uri=_required_string(data, "uri", "resource"),
        format=_optional_string(data, "format", "resource"),
        media_type=_optional_string(data, "media_type", "resource"),
        metadata=_metadata_from_dict(data.get("metadata")),
        provenance=_provenance_from_dict(data.get("provenance")),
        access_plan=(
            None if access_plan is None else _access_plan_from_dict(access_plan)
        ),
        reference=_reference_from_dict(data.get("reference")),
        local_path=_optional_string(data, "local_path", "resource"),
        discovery=None if discovery is None else _discovery_from_dict(discovery),
    )
