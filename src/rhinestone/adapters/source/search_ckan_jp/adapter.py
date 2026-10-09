"""Discovery adapter for the Japanese cross-CKAN search service."""

from collections import Counter, deque
from typing import Any

from ....errors import (
    ConfigValidationError,
    ProviderResponseError,
    UnsupportedSourceError,
)
from ....models import (
    DiscoveryRecord,
    Metadata,
    Provenance,
    Reference,
    Resource,
    SearchQuery,
)
from ....resolution import resource_from_delivery
from ....security import DestinationPolicy
from ...knowledge._japan_administrative_areas import JAPAN_ADMINISTRATIVE_AREAS
from .._uri import has_embedded_credentials
from ..base import JsonObject, JsonTransport, ProviderAdapter
from .parsing import optional_string, organization_title, resource_format

DEFAULT_ENDPOINT = "https://search.ckan.jp/backend/api"


class SearchCkanJpAdapter(ProviderAdapter):
    """Discover executable direct resources from search.ckan.jp metadata."""

    adapter_type = "search-ckan-jp"
    search_conditions = frozenset({"text", "format", "limit"})
    required_search_conditions = frozenset({"text"})

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: str | None = DEFAULT_ENDPOINT,
        destination_policy: DestinationPolicy | None = None,
    ) -> None:
        super().__init__(
            get_json=get_json,
            endpoint=endpoint,
            destination_policy=destination_policy,
        )

    def load(self, reference: Reference) -> Resource:
        """Reject direct loading because this adapter is discovery-only."""
        raise UnsupportedSourceError(
            "search-ckan-jp is a discovery-only source and cannot resolve resources"
        )

    def search(self, query: SearchQuery) -> tuple[Resource, ...]:
        """Search the official search.ckan.jp endpoint using text criteria."""
        if query.text is None:
            raise ConfigValidationError(
                "search-ckan-jp requires a text condition for discovery"
            )
        if query.limit == 0:
            return ()
        endpoint = self._endpoint_from({}, DEFAULT_ENDPOINT)
        terms = _search_terms(query.text)
        if not terms:
            return ()
        resource_terms = tuple(term for term in terms if term not in _AREA_NAMES)
        params: dict[str, Any] = {"q": _text_query(terms)}
        if query.limit is not None:
            params["rows"] = min(100, max(10, query.limit))
        found: list[Resource] = []
        start = 0
        seen: set[tuple[str | None, str | None, str | None, str | None, str | None]] = (
            set()
        )
        while True:
            page_params = dict(params)
            if start:
                page_params["start"] = start
            response = self._request(f"{endpoint}/package_search", page_params)
            if response.get("success") is not True:
                raise ProviderResponseError("search.ckan.jp search was not successful")
            result = self._object(response.get("result"), "search.ckan.jp result")
            packages = self._objects(result.get("results"), "search.ckan.jp results")
            batches: list[deque[Resource]] = []
            for package in packages:
                items: deque[Resource] = deque()
                for item in self._package_results(package, endpoint, page_params):
                    if query.format is not None and not self._matches_query_formats(
                        item.formats, query
                    ):
                        continue
                    identity = (
                        optional_string(package.get("xckan_id"))
                        or optional_string(package.get("id")),
                        optional_string(package.get("xckan_site_url")),
                        item.provenance.dataset_identifier,
                        item.provenance.resource_identifier,
                        item.uri,
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    items.append(item)
                if items:
                    batches.append(
                        deque(
                            sorted(
                                items,
                                key=lambda item: _resource_priority(
                                    item, resource_terms
                                ),
                            )
                        )
                    )
            # Keep native Dataset relevance while giving each Dataset a turn.
            while batches:
                remaining: list[deque[Resource]] = []
                for items in batches:
                    found.append(items.popleft())
                    if query.limit is not None and len(found) == query.limit:
                        return tuple(found)
                    if items:
                        remaining.append(items)
                batches = remaining
            if query.limit is None:
                return tuple(found)
            total = result.get("count")
            if type(total) is not int or total < 0:
                raise ProviderResponseError(
                    "search.ckan.jp result count must be an integer"
                )
            if start + len(packages) >= total:
                return tuple(found)
            if not packages:
                raise ProviderResponseError(
                    "search.ckan.jp result is empty before its declared count"
                )
            start += len(packages)

    def _package_results(
        self,
        package: JsonObject,
        endpoint: str,
        params: dict[str, Any],
    ) -> tuple[Resource, ...]:
        package_id = optional_string(package.get("xckan_original_id"))
        if package_id is None:
            package_id = optional_string(package.get("id"))
        title = (
            optional_string(package.get("xckan_title"))
            or optional_string(package.get("title"))
            or package_id
        )
        if title is None:
            return ()
        description = optional_string(package.get("notes"))
        publisher = organization_title(package.get("organization"))
        license_name = optional_string(package.get("license_title"))
        site_url = optional_string(package.get("xckan_site_url"))
        resources = self._objects(package.get("resources"), "search.ckan.jp resources")
        found: list[Resource] = []
        for resource in resources:
            resource_id = optional_string(resource.get("id"))
            uri = optional_string(resource.get("url"))
            format_name = resource_format(resource)
            if resource_id is None or uri is None or format_name is None:
                continue
            if has_embedded_credentials(uri):
                raise ProviderResponseError(
                    "search.ckan.jp resource URL must not contain embedded credentials"
                )
            metadata = Metadata(
                title=title,
                description=description,
                publisher=publisher,
                license=license_name,
                raw=package,
            )
            provenance = Provenance(
                provider=optional_string(package.get("xckan_site_name"))
                or "search-ckan-jp",
                dataset_identifier=package_id,
                resource_identifier=resource_id,
                api_endpoint=endpoint,
                original_url=site_url or uri,
                query_parameters=params,
                adapter=self.adapter_type,
                raw={"catalog": package, "resource": resource},
            )
            target_parameters: dict[str, Any] = {
                "uri": uri,
                "format": format_name,
                "metadata": {
                    "title": title,
                    "description": description,
                    "publisher": publisher,
                    "license": license_name,
                    "raw": package,
                },
            }
            media_type = optional_string(resource.get("mimetype"))
            if media_type is not None:
                target_parameters["media_type"] = media_type
            target_metadata = Metadata(
                title=title,
                description=description,
                publisher=publisher,
                license=license_name,
                raw=package,
            )
            target_provenance = Provenance(
                provider="direct",
                dataset_identifier=package_id,
                resource_identifier=resource_id,
                original_url=uri,
                adapter="direct",
                raw={"catalog": package, "resource": resource},
            )
            found.append(
                resource_from_delivery(
                    reference=Reference(
                        "direct",
                        dataset_identifier=package_id,
                        resource_identifier=resource_id,
                        parameters=target_parameters,
                    ),
                    uri=uri,
                    format=format_name,
                    media_type=media_type,
                    metadata=target_metadata,
                    provenance=target_provenance,
                    discovery=DiscoveryRecord(
                        source_id=self.adapter_type,
                        metadata=metadata,
                        provenance=provenance,
                        raw_metadata={"catalog": package, "resource": resource},
                    ),
                )
            )
        return tuple(found)

    @staticmethod
    def _matches_query_formats(formats: frozenset[str], query: SearchQuery) -> bool:
        requested = {value.value for value in query.expanded_formats}
        return bool(formats & requested) or (not formats and "unknown" in requested)


_PREFECTURES = tuple(
    area.canonical_name for area in JAPAN_ADMINISTRATIVE_AREAS if len(area.code) == 2
)
# A globally unique snapshot alias avoids requiring an omitted prefecture name.
# Ambiguous municipality names retain both prefecture and municipality criteria.
_ALIAS_COUNTS = Counter(
    alias for area in JAPAN_ADMINISTRATIVE_AREAS for alias in area.aliases
)
_AREA_TERMS = {
    area.canonical_name: (
        (min(aliases, key=len),)
        if (
            aliases := tuple(
                alias for alias in area.aliases if _ALIAS_COUNTS[alias] == 1
            )
        )
        else (prefecture, area.canonical_name[len(prefecture) :])
    )
    for area in JAPAN_ADMINISTRATIVE_AREAS
    for prefecture in _PREFECTURES
    if len(area.code) > 2 and area.canonical_name.startswith(prefecture)
}

_AREA_NAMES = {
    name
    for area in JAPAN_ADMINISTRATIVE_AREAS
    for name in (area.canonical_name, *area.aliases)
}


def _search_terms(text: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            part for term in text.split() for part in _AREA_TERMS.get(term, (term,))
        )
    )


def _text_query(terms: tuple[str, ...]) -> str:
    """Use the service's guaranteed title field and Standard Query Parser."""
    clauses: list[str] = []
    for term in terms:
        # Quotes preserve each user word as a phrase; escape query syntax so
        # user input cannot introduce fields, operators, boosts or wildcards.
        escaped = "".join(
            "\\" + char if char in '+-&|!(){}[]^"~*?:\\/' else char for char in term
        )
        phrase = f'"{escaped}"'
        clauses.append(
            f"(xckan_title:{phrase}^8 OR xckan_title:*{escaped}*^4 OR {phrase})"
        )
    return " AND ".join(clauses)


def _resource_priority(item: Resource, terms: tuple[str, ...]) -> tuple[int, int]:
    """Prefer declared Resource names matching the query inside each Dataset."""
    assert item.discovery is not None
    resource = item.discovery.raw_metadata["resource"]
    name = (optional_string(resource.get("name")) or "").casefold()
    description = (optional_string(resource.get("description")) or "").casefold()
    return (
        -sum(term.casefold() in name for term in terms),
        -sum(term.casefold() in description for term in terms),
    )
