"""Immutable canonical values shared by knowledge adapters."""

from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any, Literal, Mapping, Optional, cast

from ...errors import KnowledgeValidationError

TimeKind = Literal["calendar_year", "fiscal_year", "survey_year", "as_of_date"]
MunicipalityLevel = Literal["prefecture", "municipality"]


@dataclass(frozen=True)
class MunicipalityIdentity:
    """A canonical municipality identity independent of provider identifiers.

    ``provider_identifiers`` preserves source-specific IDs while ``code`` and
    the names provide a shared value for downstream consumers.
    """

    code: str
    name: str
    prefecture_code: str
    prefecture_name: str
    level: MunicipalityLevel = "municipality"
    provider_identifiers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "code",
            "name",
            "prefecture_code",
            "prefecture_name",
        ):
            value = cast(object, getattr(self, field_name))
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeValidationError(
                    f"municipality {field_name} must be a non-empty string"
                )
        if self.level not in {"prefecture", "municipality"}:
            raise KnowledgeValidationError(
                "municipality level must be 'prefecture' or 'municipality'"
            )
        provider_identifiers = cast(object, self.provider_identifiers)
        if not isinstance(provider_identifiers, Mapping):
            raise KnowledgeValidationError(
                "municipality provider_identifiers must be a mapping"
            )
        if any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or not value.strip()
            for key, value in cast(Mapping[Any, Any], provider_identifiers).items()
        ):
            raise KnowledgeValidationError(
                "municipality provider identifiers must contain non-empty strings"
            )
        object.__setattr__(
            self,
            "provider_identifiers",
            MappingProxyType(dict(self.provider_identifiers)),
        )

    def as_mapping(self) -> Mapping[str, object]:
        """Return a JSON-compatible mapping suitable for retained metadata."""
        return {
            "code": self.code,
            "name": self.name,
            "prefecture_code": self.prefecture_code,
            "prefecture_name": self.prefecture_name,
            "level": self.level,
            "provider_identifiers": dict(self.provider_identifiers),
        }


@dataclass(frozen=True)
class TimeSemantic:
    """A time value whose public-data meaning is explicit.

    Year-based kinds use ``year``; ``as_of_date`` uses ``as_of``. Japanese era
    information is retained in ``era`` and ``era_year`` when supplied.
    """

    kind: TimeKind
    year: Optional[int] = None
    as_of: Optional[date] = None
    era: Optional[str] = None
    era_year: Optional[int] = None
    raw: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {
            "calendar_year",
            "fiscal_year",
            "survey_year",
            "as_of_date",
        }:
            raise KnowledgeValidationError(f"unsupported time kind: {self.kind!r}")
        raw = cast(object, self.raw)
        if not isinstance(raw, str) or not raw.strip():
            raise KnowledgeValidationError("time raw value must be a non-empty string")
        if self.kind == "as_of_date":
            if not isinstance(self.as_of, date) or self.year is not None:
                raise KnowledgeValidationError(
                    "as_of_date requires a date and cannot contain a year"
                )
        else:
            if type(self.year) is not int or not 1 <= self.year <= 9999:
                raise KnowledgeValidationError(
                    "year-based time values require a year from 1 to 9999"
                )
            if self.as_of is not None:
                raise KnowledgeValidationError(
                    "year-based time values cannot contain an as_of date"
                )
        if self.era is None and self.era_year is not None:
            raise KnowledgeValidationError("era_year requires era")
        if self.era is not None and (
            self.kind not in {"calendar_year", "as_of_date"}
            or type(self.era_year) is not int
            or self.era_year < 1
        ):
            raise KnowledgeValidationError(
                "era is only valid for calendar years with a positive era year"
            )

    def as_mapping(self) -> Mapping[str, object]:
        """Return a JSON-compatible mapping suitable for retained metadata."""
        result: dict[str, object] = {"kind": self.kind, "raw": self.raw}
        if self.year is not None:
            result["year"] = self.year
        if self.as_of is not None:
            result["as_of"] = self.as_of.isoformat()
        if self.era is not None:
            result["era"] = self.era
            result["era_year"] = self.era_year
        return result


__all__ = ["MunicipalityIdentity", "TimeKind", "TimeSemantic"]
