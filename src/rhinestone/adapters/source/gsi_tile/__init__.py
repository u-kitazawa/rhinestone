"""GSI image tile definitions, with explicit XYZ access semantics."""

from string import Formatter
from typing import Any, Dict, List, Mapping, Tuple, cast
from urllib.parse import urlsplit

from ....errors import ConfigValidationError, UnsupportedSearchConditionError
from ....models import Config, ResourceCandidate, SearchQuery, SearchResult, Source
from .._knowledge import source, string
from ..base import ProviderAdapter


class GsiTileAdapter(ProviderAdapter):
    adapter_type = "gsi-tile"
    search_conditions = frozenset({"text", "limit"})

    def __init__(self, specs: Mapping[str, Mapping[str, Any]]) -> None:
        super().__init__(get_json=lambda url, params: None)
        if not isinstance(specs, Mapping) or not specs:
            raise ConfigValidationError("GSI tile catalog must be a non-empty object")
        raw_specs = cast(Mapping[str, Mapping[str, Any]], specs)
        validated: Dict[str, Dict[str, Any]] = {}
        for identifier, raw_spec in raw_specs.items():
            if not isinstance(identifier, str) or not identifier.strip():
                raise ConfigValidationError(
                    "GSI tile catalog ids must be non-empty strings"
                )
            if not isinstance(raw_spec, Mapping):
                raise ConfigValidationError(
                    f"GSI tile catalog item {identifier!r} must be an object"
                )
            validated[identifier] = dict(raw_spec)
        self._specs = validated

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        if "id" in settings:
            identifier = string(settings, "id")
            if identifier not in self._specs:
                raise ConfigValidationError("Unknown GSI tile id")
            spec: Mapping[str, Any] = self._specs[identifier]
        else:
            identifier = string(settings, "url")
            spec = settings
        self._validate(spec)
        candidate = ResourceCandidate(
            uri=spec["url"],
            format=spec["format"],
            media_type=spec["media_type"],
            attributes={
                "access_kind": "remote-dataset",
                "access_options": {"tile": dict(spec)},
            },
        )
        return source(
            self.adapter_type,
            identifier,
            spec,
            (candidate,),
            title=spec.get("title"),
            capabilities=("remote-dataset", "search"),
        )

    @staticmethod
    def _validate(spec: Mapping[str, Any]) -> None:
        template = string(spec, "url")
        try:
            parsed = urlsplit(template)
            fields = tuple(Formatter().parse(template))
        except ValueError:
            raise ConfigValidationError("Invalid tile URL template") from None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.fragment
            or "{" in parsed.netloc
            or {field for _, field, _, _ in fields if field is not None}
            != {"z", "x", "y"}
            or any(fmt or conversion for _, _, fmt, conversion in fields)
        ):
            raise ConfigValidationError("Expected HTTPS template with {z}, {x}, {y}")
        if not 0 <= spec["min_zoom"] <= spec["max_zoom"] <= 30:
            raise ConfigValidationError("Invalid tile zoom range")
        string(spec, "attribution")

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        if query.supplied_conditions - self.search_conditions:
            raise UnsupportedSearchConditionError("Unsupported GSI tile search")
        if query.limit is not None and (
            type(query.limit) is not int or query.limit < 0
        ):
            raise ConfigValidationError("limit must be a non-negative integer")
        results: List[SearchResult] = []
        for identifier in sorted(self._specs):
            item = self.load(Config(self.adapter_type, {"id": identifier}))
            if (
                query.text
                and query.text.casefold()
                not in (identifier + " " + (item.metadata.title or "")).casefold()
            ):
                continue
            results.append(
                SearchResult(
                    item.metadata.title or identifier,
                    item.metadata.description,
                    self.adapter_type,
                    {"id": identifier},
                    item.metadata,
                    item.provenance,
                )
            )
        return tuple(results[: query.limit])
