"""Provider-neutral spatial value objects.

These values deliberately do not consult a CRS database, perform reprojection,
or derive geometry from a mesh code.  Interpretation and provider projection
belong to the adapter that has the relevant advertised capability.
"""

import re
from dataclasses import dataclass
from math import isfinite
from typing import Iterator, Literal, Tuple, cast

from ...errors import KnowledgeResolutionError, KnowledgeValidationError

MeshLevel = Literal[1, 2, 3, 4, 5, 6]

_CRS_AUTHORITY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_CRS_CODE = re.compile(r"^[A-Za-z0-9_.-]+$")
_MESH_LENGTHS = {1: 4, 2: 6, 3: 8, 4: 9, 5: 10, 6: 11}
_MESH_DIGIT_RULES = {
    1: (0, 4, "0123456789"),
    2: (4, 6, "01234567"),
    3: (6, 8, "0123456789"),
    4: (8, 9, "1234"),
    5: (8, 10, "1234"),
    6: (8, 11, "1234"),
}


@dataclass(frozen=True)
class CRSRef:
    """An explicit CRS identifier, without a CRS definition lookup."""

    authority: str
    code: str

    def __post_init__(self) -> None:
        if not isinstance(
            cast(object, self.authority), str
        ) or not _CRS_AUTHORITY.fullmatch(self.authority):
            raise KnowledgeValidationError(
                "CRS authority must be a non-empty identifier"
            )
        if not isinstance(cast(object, self.code), str) or not _CRS_CODE.fullmatch(
            self.code
        ):
            raise KnowledgeValidationError("CRS code must be a non-empty identifier")

    @classmethod
    def parse(cls, value: str) -> "CRSRef":
        """Parse ``AUTHORITY:CODE`` without resolving its definition."""
        if not isinstance(cast(object, value), str) or value.count(":") != 1:
            raise KnowledgeValidationError(
                "CRS must use an explicit AUTHORITY:CODE identifier"
            )
        authority, code = value.split(":")
        return cls(authority, code)

    def as_string(self) -> str:
        return f"{self.authority}:{self.code}"


CRS84 = CRSRef("OGC", "CRS84")


@dataclass(frozen=True)
class BoundingBox:
    """An immutable bbox with explicit axis order and CRS."""

    west: float
    south: float
    east: float
    north: float
    crs: CRSRef = CRS84

    def __post_init__(self) -> None:
        values = (self.west, self.south, self.east, self.north)
        if any(
            isinstance(cast(object, value), bool)
            or not isinstance(cast(object, value), (int, float))
            for value in values
        ):
            raise KnowledgeValidationError("bbox coordinates must be finite numbers")
        if any(not isfinite(float(value)) for value in values):
            raise KnowledgeValidationError("bbox coordinates must be finite numbers")
        if not isinstance(cast(object, self.crs), CRSRef):
            raise KnowledgeValidationError("bbox crs must be an explicit CRSRef")
        if self.west > self.east or self.south > self.north:
            raise KnowledgeValidationError(
                "bbox must satisfy west <= east and south <= north; "
                "antimeridian crossing is not inferred"
            )
        if self.crs == CRS84 and (
            self.west < -180 or self.east > 180 or self.south < -90 or self.north > 90
        ):
            raise KnowledgeValidationError(
                "CRS84 bbox must use longitude [-180, 180] and latitude [-90, 90]"
            )

    @classmethod
    def from_tuple(
        cls, value: Tuple[float, float, float, float], crs: CRSRef = CRS84
    ) -> "BoundingBox":
        if not isinstance(cast(object, value), tuple) or len(value) != 4:
            raise KnowledgeValidationError("bbox must be a tuple of four numbers")
        return cls(*value, crs=crs)

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)

    def __iter__(self) -> Iterator[float]:
        """Keep existing provider query serializers compatible with this value."""
        return iter(self.as_tuple())


@dataclass(frozen=True)
class MeshCode:
    """A Japanese mesh identity; no geometry is derived from it."""

    system: str
    level: MeshLevel
    code: str

    def __post_init__(self) -> None:
        if not isinstance(cast(object, self.system), str) or not self.system.strip():
            raise KnowledgeValidationError("mesh system must be non-empty")
        if self.system != "JIS-X-0410":
            raise KnowledgeValidationError(f"unsupported mesh system: {self.system!r}")
        if type(self.level) is not int or self.level not in _MESH_LENGTHS:
            raise KnowledgeValidationError("mesh level must be an integer from 1 to 6")
        if (
            not isinstance(cast(object, self.code), str)
            or not self.code.isascii()
            or not self.code.isdigit()
            or len(self.code) != _MESH_LENGTHS[cast(int, self.level)]
        ):
            raise KnowledgeValidationError(
                "mesh code has an invalid length for its explicit level"
            )
        start, end, allowed = _MESH_DIGIT_RULES[cast(int, self.level)]
        if any(digit not in allowed for digit in self.code[start:end]):
            raise KnowledgeValidationError(
                "mesh code contains an invalid digit for its explicit level"
            )


def require_lossless_crs84(bbox: BoundingBox) -> Tuple[float, float, float, float]:
    """Return a bbox for providers whose contract is explicitly CRS84 only."""
    if bbox.crs != CRS84:
        raise KnowledgeResolutionError(
            "spatial projection unsupported: provider accepts CRS84 only"
        )
    return bbox.as_tuple()


__all__ = [
    "BoundingBox",
    "CRS84",
    "CRSRef",
    "MeshCode",
    "MeshLevel",
    "require_lossless_crs84",
]
