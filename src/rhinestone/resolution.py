"""Deterministic conversion from Source candidates to Resource access plans."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any, cast

from .errors import (
    AmbiguousResourceError,
    ResourceNotFoundError,
    UnsupportedAccessError,
)
from .models import (
    AccessPlan,
    Resource,
    ResourceCandidate,
    Source,
)
from .representations import canonical_format

ResolutionRule = Callable[[ResourceCandidate], tuple[int, str] | None]


class Resolver:
    """Choose exactly one candidate and construct its explicit AccessPlan."""

    def __init__(self, rules: Iterable[ResolutionRule] = ()) -> None:
        self._resolution_rules = tuple(rules)

    def resolve(self, source: Source) -> Resource:
        """Resolve a normalized Source into one Resource.

        Candidates marked ``matches_config=False`` remain in the Source but are
        excluded from selection. Exactly one remaining candidate is required;
        representation and access kind must be explicit enough to build a plan.
        """
        matching_candidates: list[ResourceCandidate] = []
        for candidate in source.candidates:
            matches = candidate.attributes.get("matches_config", True)
            if not isinstance(matches, bool):
                raise UnsupportedAccessError(
                    "Resource candidate attribute 'matches_config' must be a "
                    f"boolean; got {type(matches).__name__}"
                )
            if matches:
                matching_candidates.append(candidate)
        if not matching_candidates:
            raise ResourceNotFoundError(
                "No resource matches the requested selection; verify the "
                "provider-specific identifiers and Config settings"
            )
        if len(matching_candidates) != 1:
            raise AmbiguousResourceError(
                "Expected exactly one resource candidate after selection; "
                f"got {len(matching_candidates)}; add an explicit resource selector"
            )
        candidate = matching_candidates[0]
        format_name = canonical_format(candidate.format)
        if format_name != candidate.format:
            candidate = replace(candidate, format=format_name)
        if candidate.format is None and candidate.media_type is None:
            raise UnsupportedAccessError(
                "Resource format and media type are unknown; URI suffix is not "
                "guessed, so provide an explicit representation"
            )
        plan = self._select_plan(candidate, provider=source.provenance.provider)
        return Resource(
            uri=candidate.uri,
            format=format_name,
            media_type=candidate.media_type,
            metadata=source.metadata,
            provenance=source.provenance,
            access_plan=plan,
            source=source,
        )

    def _select_plan(
        self, candidate: ResourceCandidate, *, provider: str
    ) -> AccessPlan:
        explicit = candidate.attributes.get("access_kind")
        if explicit is not None:
            if not isinstance(explicit, str):
                raise UnsupportedAccessError(
                    "access_kind must be a string naming file, remote-dataset, "
                    f"or service-query; got {type(explicit).__name__}"
                )
            return self._make_plan(explicit, candidate, provider=provider)
        matches: list[tuple[int, str]] = []
        for rule in self._resolution_rules:
            result = rule(candidate)
            if result is not None:
                matches.append(result)
        if matches:
            _, kind = max(matches, key=lambda match: (match[0], match[1]))
            return self._make_plan(kind, candidate, provider=provider)

        normalized = (candidate.format or "").lower()
        if normalized in {"cog"}:
            return self._make_plan("remote-dataset", candidate, provider=provider)
        if normalized in {"wms", "wfs", "api", "ogc-api-features"}:
            return self._make_plan("service-query", candidate, provider=provider)
        if normalized:
            return self._make_plan("file", candidate, provider=provider)
        raise UnsupportedAccessError(
            f"No access plan supports media type {candidate.media_type!r}; "
            "provide a known format or explicit access_kind"
        )

    @staticmethod
    def _make_plan(
        kind: str, candidate: ResourceCandidate, *, provider: str
    ) -> AccessPlan:
        options = candidate.attributes.get("access_options", {})
        if not isinstance(options, Mapping):
            raise UnsupportedAccessError(
                "access_options must be an object containing adapter options; "
                f"got {type(options).__name__}"
            )
        options = dict(cast(Mapping[str, Any], options))
        service = options.pop("service", None)
        credential = options.pop("credential", None)
        if service is not None and not isinstance(service, str):
            raise UnsupportedAccessError("access_options.service must be a string")
        if credential is not None and not isinstance(credential, str):
            raise UnsupportedAccessError(
                "access_options.credential must be a logical credential name"
            )
        encoding = candidate.attributes.get("encoding")
        if encoding is not None:
            options.setdefault("encoding", encoding)
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
                    or not path.parts
                    or path.is_absolute()
                    or ".." in path.parts
                    or "\\" in entry_point
                ):
                    raise UnsupportedAccessError(
                        "entry_point must be a safe relative archive path"
                    )
            if archive is not None:
                options["archive"] = archive
            return AccessPlan(
                kind=kind,
                uri=candidate.uri,
                format=candidate.format,
                media_type=candidate.media_type,
                options=options,
                provider=provider,
                service=service,
                credential=credential,
            )
        if kind in {"remote-dataset", "service-query"}:
            return AccessPlan(
                kind=kind,
                uri=candidate.uri,
                format=candidate.format,
                media_type=candidate.media_type,
                options=options,
                provider=provider,
                service=service,
                credential=credential,
            )
        raise UnsupportedAccessError(
            f"Unknown access plan kind {kind!r}; expected file, remote-dataset, "
            "or service-query"
        )
