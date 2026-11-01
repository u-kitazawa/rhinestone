"""Validation of the catalog knowledge used by the ODPT adapter."""

from collections.abc import Mapping
from typing import Any, cast

from ....errors import ConfigValidationError


def required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"{name} must be a non-empty string")
    return value


def string_mapping(value: Any, name: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ConfigValidationError(f"{name} must be a non-empty object")
    result: dict[str, str] = {}
    values = cast(Mapping[Any, Any], value)
    for key, item in values.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(item, str):
            raise ConfigValidationError(f"{name} must map strings to strings")
        if not item.strip():
            raise ConfigValidationError(f"{name} values must be non-empty strings")
        result[key] = item
    return result


def filter_mapping(value: Any) -> dict[str, frozenset[str]]:
    if not isinstance(value, Mapping) or not value:
        raise ConfigValidationError("filter_fields must be a non-empty object")
    result: dict[str, frozenset[str]] = {}
    values = cast(Mapping[Any, Any], value)
    for key, raw_fields in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigValidationError("filter_fields keys must be non-empty strings")
        if not isinstance(raw_fields, list | tuple | set | frozenset):
            raise ConfigValidationError("filter_fields values must be arrays")
        fields = cast(Any, raw_fields)
        if any(not isinstance(field, str) or not field.strip() for field in fields):
            raise ConfigValidationError("filter_fields values must contain strings")
        result[key] = frozenset(cast(tuple[str, ...], tuple(fields)))
    return result
