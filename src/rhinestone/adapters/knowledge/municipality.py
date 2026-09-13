"""A deterministic, snapshot-backed municipality knowledge adapter."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping, Tuple, Union, cast

from ...errors import KnowledgeResolutionError, KnowledgeValidationError
from .models import MunicipalityIdentity

STANDARD_AREA_CODE = "japan-standard-area-code"


@dataclass(frozen=True)
class AreaCode:
    """A code assignment kept separate from administrative identity."""

    scheme: str
    value: str

    def __post_init__(self) -> None:
        scheme = cast(object, self.scheme)
        if not isinstance(scheme, str) or not scheme.strip():
            raise KnowledgeValidationError("area code scheme must be non-empty")
        if self.scheme != self.scheme.strip():
            raise KnowledgeValidationError("area code scheme must not contain padding")
        if (
            not isinstance(cast(object, self.value), str)
            or not self.value.strip()
            or self.value != self.value.strip()
            or not self.value.isdigit()
        ):
            raise KnowledgeValidationError(
                "area code value must be a non-empty decimal string"
            )


@dataclass(frozen=True)
class MunicipalityRecord:
    """One immutable identity plus its code and provider assignments."""

    identity: MunicipalityIdentity
    codes: Tuple[AreaCode, ...] = ()
    aliases: Tuple[str, ...] = ()
    provider_identifiers: Mapping[str, str] = field(
        default_factory=lambda: dict[str, str]()
    )

    def __post_init__(self) -> None:
        if not isinstance(cast(object, self.identity), MunicipalityIdentity):
            raise KnowledgeValidationError("municipality record identity is invalid")
        codes = tuple(self.codes)
        if not codes:
            codes = (AreaCode(STANDARD_AREA_CODE, self.identity.code),)
        if any(not isinstance(cast(object, code), AreaCode) for code in codes):
            raise KnowledgeValidationError("municipality record codes are invalid")
        aliases = tuple(self.aliases)
        if any(
            not isinstance(cast(object, alias), str) or not alias.strip()
            for alias in aliases
        ):
            raise KnowledgeValidationError(
                "municipality aliases must be non-empty strings"
            )
        projections = self.provider_identifiers or self.identity.provider_identifiers
        if not isinstance(cast(object, projections), Mapping) or any(
            not isinstance(cast(object, key), str)
            or not key.strip()
            or not isinstance(cast(object, value), str)
            or not value.strip()
            for key, value in projections.items()
        ):
            raise KnowledgeValidationError(
                "municipality provider identifiers must contain non-empty strings"
            )
        object.__setattr__(self, "codes", codes)
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(
            self, "provider_identifiers", MappingProxyType(dict(projections))
        )


RecordInput = Union[MunicipalityRecord, MunicipalityIdentity]


class StaticMunicipalityAdapter:
    """Resolve names/codes against one caller-supplied immutable snapshot.

    The adapter intentionally ships no national master data.  Applications
    provide the authoritative records and snapshot version through a factory.
    Name matching is exact after trimming; aliases must be listed in the
    snapshot and no fuzzy or provider fallback lookup is performed.
    """

    _snapshot_version: str
    _records: Tuple[MunicipalityRecord, ...]
    _by_code: Mapping[tuple[str, str], MunicipalityRecord]
    _by_name: Mapping[str, Tuple[MunicipalityRecord, ...]]

    def __init__(
        self,
        records: Iterable[RecordInput],
        *,
        snapshot_version: str,
    ) -> None:
        if (
            not isinstance(cast(object, snapshot_version), str)
            or not snapshot_version.strip()
        ):
            raise KnowledgeValidationError("municipality snapshot_version is required")
        normalized = tuple(
            record
            if isinstance(record, MunicipalityRecord)
            else MunicipalityRecord(record)
            for record in records
        )
        if not normalized:
            raise KnowledgeValidationError("municipality snapshot must not be empty")
        by_code: dict[tuple[str, str], MunicipalityRecord] = {}
        by_name: dict[str, list[MunicipalityRecord]] = {}
        for record in normalized:
            for code in record.codes:
                key = (code.scheme, code.value)
                if key in by_code and by_code[key].identity != record.identity:
                    raise KnowledgeValidationError(
                        "municipality snapshot contains a duplicate active area code"
                    )
                by_code[key] = record
            for name in (record.identity.name, *record.aliases):
                by_name.setdefault(name.strip(), []).append(record)
        object.__setattr__(self, "_snapshot_version", snapshot_version)
        object.__setattr__(self, "_records", normalized)
        object.__setattr__(self, "_by_code", MappingProxyType(by_code))
        object.__setattr__(
            self,
            "_by_name",
            MappingProxyType({key: tuple(value) for key, value in by_name.items()}),
        )

    @property
    def snapshot_version(self) -> str:
        return self._snapshot_version

    def resolve_municipality(self, value: str) -> MunicipalityIdentity:
        """Resolve an exact name or a unique code without guessing."""
        if not isinstance(cast(object, value), str) or not value.strip():
            raise KnowledgeResolutionError("municipality value must be non-empty")
        raw = value.strip()
        code_matches = [
            record for (_scheme, code), record in self._by_code.items() if code == raw
        ]
        name_matches = list(self._by_name.get(raw, ()))
        matches: list[MunicipalityIdentity] = []
        for record in (*code_matches, *name_matches):
            if record.identity not in matches:
                matches.append(record.identity)
        if len(matches) > 1:
            raise KnowledgeResolutionError(
                "municipality is ambiguous; provide an unambiguous code or name"
            )
        if not matches:
            if raw.isdigit() and len(raw) not in {2, 5}:
                raise KnowledgeResolutionError(
                    "municipality code is invalid; expected a two- or five-digit code"
                )
            raise KnowledgeResolutionError("municipality is unknown in this snapshot")
        return matches[0]

    def project(self, identity: MunicipalityIdentity, provider: str) -> str:
        """Project a canonical identity to a declared provider identifier."""
        if not isinstance(
            cast(object, identity), MunicipalityIdentity
        ) or not isinstance(cast(object, provider), str):
            raise KnowledgeResolutionError("municipality projection input is invalid")
        identity_key = _canonical_identity_key(identity)
        for record in self._records:
            if _canonical_identity_key(record.identity) == identity_key:
                projected = record.provider_identifiers.get(provider)
                if projected is not None:
                    return projected
        raise KnowledgeResolutionError(
            f"municipality projection unsupported for provider {provider!r}"
        )

    def evidence(self) -> Mapping[str, str]:
        """Return non-secret snapshot evidence for retained metadata."""
        return {"snapshot_version": self.snapshot_version}


def _canonical_identity_key(
    identity: MunicipalityIdentity,
) -> tuple[str, str, str, str, str]:
    """Return identity fields shared across provider projections."""
    return (
        identity.code,
        identity.name,
        identity.prefecture_code,
        identity.prefecture_name,
        identity.level,
    )


__all__ = [
    "AreaCode",
    "MunicipalityRecord",
    "STANDARD_AREA_CODE",
    "StaticMunicipalityAdapter",
]
