"""Deterministic conversion from Source candidates to Resource access plans."""

from typing import Callable, Iterable, List, Optional, Tuple

from .errors import AmbiguousResourceError, UnsupportedAccessError
from .models import (
    AccessPlan,
    FileAccessPlan,
    RemoteDatasetPlan,
    Resource,
    ResourceCandidate,
    ServiceQueryPlan,
    Source,
)

ResolutionRule = Callable[[ResourceCandidate], Optional[Tuple[int, str]]]


class Resolver:
    def __init__(self, rules: Iterable[ResolutionRule] = ()) -> None:
        self._rules = tuple(rules)

    def resolve(self, source: Source) -> Resource:
        if len(source.candidates) != 1:
            raise AmbiguousResourceError(
                f"Expected exactly one resource candidate; got {len(source.candidates)}"
            )
        candidate = source.candidates[0]
        if candidate.format is None and candidate.media_type is None:
            raise UnsupportedAccessError(
                "Resource format and media type are unknown; URI suffix is not guessed"
            )
        plan = self._select_plan(candidate)
        return Resource(
            uri=candidate.uri,
            format=candidate.format,
            media_type=candidate.media_type,
            metadata=source.metadata,
            provenance=source.provenance,
            access_plan=plan,
            source=source,
        )

    def _select_plan(self, candidate: ResourceCandidate) -> AccessPlan:
        matches: List[Tuple[int, str]] = []
        for rule in self._rules:
            result = rule(candidate)
            if result is not None:
                matches.append(result)
        if matches:
            _, kind = max(matches, key=lambda match: (match[0], match[1]))
            return self._make_plan(kind, candidate)

        normalized = (candidate.format or "").lower()
        if normalized in {"cog"}:
            return RemoteDatasetPlan(uri=candidate.uri)
        if normalized in {"wms", "wfs", "api"}:
            return ServiceQueryPlan(uri=candidate.uri)
        if normalized:
            archive = candidate.attributes.get("archive")
            if archive is None and normalized in {"shapefile-zip", "zip"}:
                archive = "zip"
            return FileAccessPlan(uri=candidate.uri, archive=archive)
        raise UnsupportedAccessError(
            f"No access plan supports media type {candidate.media_type!r}"
        )

    @staticmethod
    def _make_plan(kind: str, candidate: ResourceCandidate) -> AccessPlan:
        if kind == "file":
            return FileAccessPlan(uri=candidate.uri)
        if kind == "remote-dataset":
            return RemoteDatasetPlan(uri=candidate.uri)
        if kind == "service-query":
            return ServiceQueryPlan(uri=candidate.uri)
        raise UnsupportedAccessError(f"Unknown access plan kind {kind!r}")
