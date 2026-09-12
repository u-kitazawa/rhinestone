"""Deterministic Japanese public-data time adapter."""

import re
from datetime import date
from typing import Optional, cast

from ....errors import KnowledgeResolutionError
from ..models import TimeKind, TimeSemantic

_ERA_STARTS = {
    "明治": date(1868, 1, 25),
    "大正": date(1912, 7, 30),
    "昭和": date(1926, 12, 25),
    "平成": date(1989, 1, 8),
    "令和": date(2019, 5, 1),
}
_ERA_PATTERN = re.compile(r"^(明治|大正|昭和|平成|令和)(元|[1-9][0-9]*)年$")
_ERA_DATE_PATTERN = re.compile(
    r"^(明治|大正|昭和|平成|令和)(元|[1-9][0-9]*)年([1-9][0-9]?)月([1-9][0-9]?)日$"
)
_YEAR_PATTERN = re.compile(r"^([1-9][0-9]{0,3})(年|年度)?$")
_DATE_PATTERN = re.compile(r"^([1-9][0-9]{3})-([0-9]{2})-([0-9]{2})$")


class StandardTimeAdapter:
    """Resolve only explicit year, era-year, fiscal-year, and ISO date forms."""

    def resolve_time(
        self, value: str, *, kind: Optional[TimeKind] = None
    ) -> TimeSemantic:
        """Resolve explicit calendar, fiscal, era, or ISO date expressions."""
        raw_value = cast(object, value)
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise KnowledgeResolutionError(
                "time value must be a non-empty string; provide an explicit year, "
                "era year, or ISO date"
            )
        raw = value.strip()
        era_date_match = _ERA_DATE_PATTERN.fullmatch(raw)
        if era_date_match is not None:
            return self._resolve_era_date(era_date_match, raw, kind)
        era_match = _ERA_PATTERN.fullmatch(raw)
        if era_match is not None:
            if kind not in (None, "calendar_year"):
                raise KnowledgeResolutionError(
                    "era year can only be resolved as a calendar year"
                )
            era = era_match.group(1)
            era_year_text = era_match.group(2)
            era_year = 1 if era_year_text == "元" else int(era_year_text)
            year = _ERA_STARTS[era].year + era_year - 1
            if year > 9999:
                raise KnowledgeResolutionError("era year is outside supported range")
            return TimeSemantic(
                kind="calendar_year",
                year=year,
                era=era,
                era_year=era_year,
                raw=raw,
            )

        date_match = _DATE_PATTERN.fullmatch(raw)
        if date_match is not None:
            if kind not in (None, "as_of_date"):
                raise KnowledgeResolutionError(
                    "ISO date can only be resolved as an as-of date"
                )
            try:
                parsed = date(
                    int(date_match.group(1)),
                    int(date_match.group(2)),
                    int(date_match.group(3)),
                )
            except ValueError as error:
                raise KnowledgeResolutionError("invalid ISO as-of date") from error
            return TimeSemantic(kind="as_of_date", as_of=parsed, raw=raw)

        year_match = _YEAR_PATTERN.fullmatch(raw)
        if year_match is None:
            raise KnowledgeResolutionError(
                "time value must be an explicit year, era year, or ISO date; "
                "ambiguous natural-language dates are not inferred"
            )
        year = int(year_match.group(1))
        suffix = year_match.group(2)
        inferred: TimeKind = "fiscal_year" if suffix == "年度" else "calendar_year"
        selected = inferred if kind is None else kind
        if suffix == "年度" and selected != "fiscal_year":
            raise KnowledgeResolutionError("年度 must be resolved as a fiscal year")
        if suffix == "年" and selected not in {"calendar_year", "survey_year"}:
            raise KnowledgeResolutionError(
                "年 must be resolved as calendar or survey year"
            )
        if suffix is None and selected not in {
            "calendar_year",
            "fiscal_year",
            "survey_year",
        }:
            raise KnowledgeResolutionError("a year cannot be resolved as an as-of date")
        return TimeSemantic(kind=selected, year=year, raw=raw)

    def _resolve_era_date(
        self, match: re.Match[str], raw: str, kind: Optional[TimeKind]
    ) -> TimeSemantic:
        if kind not in (None, "as_of_date"):
            raise KnowledgeResolutionError(
                "era date can only be resolved as an as-of date"
            )
        era = match.group(1)
        era_year_text = match.group(2)
        era_year = 1 if era_year_text == "元" else int(era_year_text)
        try:
            month = int(match.group(3))
            day = int(match.group(4))
            start = _ERA_STARTS[era]
            parsed = date(start.year + era_year - 1, month, day)
        except ValueError as error:
            raise KnowledgeResolutionError("invalid era date") from error
        if parsed < start:
            raise KnowledgeResolutionError("era date precedes the era start date")
        later_starts = [
            candidate for candidate in _ERA_STARTS.values() if candidate > start
        ]
        next_start = min(later_starts, default=None)
        if next_start is not None and parsed >= next_start:
            raise KnowledgeResolutionError("era date is after the era end date")
        return TimeSemantic(
            kind="as_of_date",
            as_of=parsed,
            era=era,
            era_year=era_year,
            raw=raw,
        )


__all__ = ["StandardTimeAdapter"]
