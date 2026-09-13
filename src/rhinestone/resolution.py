"""Deterministic conversion from Source candidates to Resource access plans."""

from pathlib import PurePosixPath
from typing import Any, Callable, Iterable, List, Mapping, Optional, Tuple, cast

from .errors import (
    AmbiguousResourceError,
    ResourceNotFoundError,
    UnsupportedAccessError,
)
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
    """Choose exactly one candidate and construct its explicit AccessPlan."""

    def __init__(self, rules: Iterable[ResolutionRule] = ()) -> None:
        self._rules = tuple(rules)

    def resolve(self, source: Source) -> Resource:
        """Resolve a normalized Source into one Resource.

        Candidates marked ``matches_config=False`` remain in the Source but are
        excluded from selection. Exactly one remaining candidate is required;
        representation and access kind must be explicit enough to build a plan.
        """
        candidates: List[ResourceCandidate] = []
        for item in source.candidates:
            matches = item.attributes.get("matches_config", True)
            if not isinstance(matches, bool):
                raise UnsupportedAccessError(
                    "Resource candidate attribute 'matches_config' must be a "
                    f"boolean; got {type(matches).__name__}"
                )
            if matches:
                candidates.append(item)
        if not candidates:
            raise ResourceNotFoundError(
                "No resource matches the requested selection; verify the "
                "provider-specific identifiers and Config settings"
            )
        if len(candidates) != 1:
            raise AmbiguousResourceError(
                "Expected exactly one resource candidate after selection; "
                f"got {len(candidates)}; add an explicit resource selector"
            )
        candidate = candidates[0]
        if candidate.format is None and candidate.media_type is None:
            raise UnsupportedAccessError(
                "Resource format and media type are unknown; URI suffix is not "
                "guessed, so provide an explicit representation"
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
        explicit = candidate.attributes.get("access_kind")
        if explicit is not None:
            if not isinstance(explicit, str):
                raise UnsupportedAccessError(
                    "access_kind must be a string naming file, remote-dataset, "
                    f"or service-query; got {type(explicit).__name__}"
                )
            return self._make_plan(explicit, candidate)
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
        if normalized in {"wms", "wfs", "api", "ogc-api-features"}:
            return ServiceQueryPlan(uri=candidate.uri)
        if normalized:
            return self._make_plan("file", candidate)
        raise UnsupportedAccessError(
            f"No access plan supports media type {candidate.media_type!r}; "
            "provide a known format or explicit access_kind"
        )

    @staticmethod
    def _make_plan(kind: str, candidate: ResourceCandidate) -> AccessPlan:
        options = candidate.attributes.get("access_options", {})
        if not isinstance(options, Mapping):
            raise UnsupportedAccessError(
                "access_options must be an object containing adapter options; "
                f"got {type(options).__name__}"
            )
        options = cast(Mapping[str, Any], options)
        if kind == "file":
            archive = candidate.attributes.get("archive")
            if archive is None and (candidate.format or "").lower() in {
                "shapefile-zip",
                "zip",
            }:
                archive = "zip"
            if archive not in (None, "zip"):
                raise UnsupportedAccessError(
                    "Only archive='zip' is supported; provide an explicit ZIP "
                    "access plan"
                )
            entry_point = options.get("entry_point")
            if entry_point is not None:
                if archive != "zip" or not isinstance(entry_point, str):
                    raise UnsupportedAccessError(
                        "entry_point requires archive='zip' and a string path"
                    )
                path = PurePosixPath(entry_point)
                if (
                    not entry_point.strip()
                    or path.is_absolute()
                    or ".." in path.parts
                    or "\\" in entry_point
                ):
                    raise UnsupportedAccessError(
                        "entry_point must be a safe relative archive path"
                    )
            return FileAccessPlan(
                uri=candidate.uri,
                archive=archive,
                options=options,
            )
        if kind == "remote-dataset":
            return RemoteDatasetPlan(uri=candidate.uri, options=options)
        if kind == "service-query":
            return ServiceQueryPlan(uri=candidate.uri, options=options)
        raise UnsupportedAccessError(
            f"Unknown access plan kind {kind!r}; expected file, remote-dataset, "
            "or service-query"
        )
