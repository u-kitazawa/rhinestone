"""Provider-local discovery for G Spatial Information Center CKAN datasets."""

from collections.abc import Mapping
from dataclasses import replace
from itertools import zip_longest
from typing import Any, cast

from ....errors import ConfigValidationError, ProviderResponseError
from ....models import Config, Result, SearchQuery, Source
from ...knowledge._japan_administrative_areas import JAPAN_ADMINISTRATIVE_AREAS
from ..base import JsonObject
from ..ckan import CkanAdapter

# These are regional relationships, not assumptions about indexed Solr fields.
_REGIONS = {
    "北海道": ("北海道",),
    "東北": ("青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"),
    "関東": ("茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"),
    "中部": (
        "新潟県",
        "富山県",
        "石川県",
        "福井県",
        "山梨県",
        "長野県",
        "岐阜県",
        "静岡県",
        "愛知県",
    ),
    "関西": ("三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"),
    "中国": ("鳥取県", "島根県", "岡山県", "広島県", "山口県"),
    "四国": ("徳島県", "香川県", "愛媛県", "高知県"),
    "九州": (
        "福岡県",
        "佐賀県",
        "長崎県",
        "熊本県",
        "大分県",
        "宮崎県",
        "鹿児島県",
        "沖縄県",
    ),
}

# Use verified, prefecture-qualified aliases rather than deleting any text up
# to 郡. This leaves names such as 郡山市 intact and avoids cross-prefecture aliases.
_PROVIDER_AREA_NAMES = {
    area.canonical_name: alias
    for area in JAPAN_ADMINISTRATIVE_AREAS
    for alias in area.aliases
    if "郡" in area.canonical_name
    and "郡" not in alias
    and any(
        area.canonical_name.startswith(prefecture) and alias.startswith(prefecture)
        for names in _REGIONS.values()
        for prefecture in names
    )
}


def _provider_area_name(value: str) -> str:
    normalized = value.replace("_", "")
    return _PROVIDER_AREA_NAMES.get(normalized, normalized)


def _literal(value: str) -> str:
    """Quote user text as a Solr literal, including embedded quotes/backslashes."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _tags(package: JsonObject) -> frozenset[str]:
    values = package.get("tags", ())
    if not isinstance(values, list | tuple):
        return frozenset()
    tags: set[str] = set()
    for item in cast(tuple[Any, ...], values):
        if isinstance(item, Mapping):
            name = cast(JsonObject, item).get("name")
            if isinstance(name, str):
                tags.add(name)
    return frozenset(tags)


def _area_priority(package: JsonObject, area: str | None) -> int:
    if area is None:
        return 0
    values = set(_tags(package))
    declared = package.get("area")
    if isinstance(declared, str):
        values.update(value.strip() for value in declared.split(",") if value.strip())
    # Normalize only the documented prefecture_municipality separator.
    normalized = {_provider_area_name(value) for value in values}
    area = _provider_area_name(area)
    if area in normalized:
        return 0
    prefecture = next(
        (
            name
            for names in _REGIONS.values()
            for name in names
            if area.startswith(name)
        ),
        None,
    )
    if prefecture is not None:
        if prefecture in normalized or (
            area == prefecture
            and any(value.startswith(prefecture) for value in normalized)
        ):
            return 1
        regions = {name for name, names in _REGIONS.items() if prefecture in names}
        if normalized & (regions | {name + "地方" for name in regions}):
            return 2
    if normalized & {"全国", "日本全国"}:
        return 3
    # Unknown or unrelated metadata cannot verify a regional candidate.
    return 4


def _area_searches(
    area: str, text: str
) -> tuple[tuple[tuple[dict[str, str], frozenset[int]], ...], ...]:
    """Build scoped field/text searches with verifiable regional relationships."""
    area = _provider_area_name(area)
    prefecture = next(
        (
            name
            for names in _REGIONS.values()
            for name in names
            if area.startswith(name)
        ),
        None,
    )

    def searches(
        names: tuple[str, ...], priorities: frozenset[int], prefix: str | None = None
    ) -> tuple[tuple[dict[str, str], frozenset[int]], ...]:
        clauses = [
            f"{field}:{_literal(name)}" for field in ("area", "tags") for name in names
        ]
        if prefix is not None:
            # Prefix comes from the administrative snapshot, never user syntax.
            clauses.extend(f"{field}:{prefix}_*" for field in ("area", "tags"))
        regional_text = " OR ".join(_literal(name) for name in names)
        if len(names) > 1:
            regional_text = "(" + regional_text + ")"
        return (
            ({"q": text, "fq": "(" + " OR ".join(clauses) + ")"}, priorities),
            ({"q": text + " AND " + regional_text}, priorities),
        )

    names = (area,)
    if prefecture is not None and area != prefecture:
        names = (prefecture + "_" + area[len(prefecture) :], area)
    groups = [
        searches(
            names,
            frozenset({0, 1}) if area == prefecture else frozenset({0}),
            prefecture if area == prefecture else None,
        )
    ]
    if prefecture is not None:
        if area != prefecture:
            groups.append(searches((prefecture,), frozenset({1})))
        region = next(name for name, names in _REGIONS.items() if prefecture in names)
        groups.append(searches((region, region + "地方"), frozenset({2})))
    groups.append(searches(("全国", "日本全国"), frozenset({3})))
    return tuple(groups)


class GeospatialJpAdapter(CkanAdapter):
    """Rank G Spatial candidates locally while retaining resource-level results.

    Area filters run from the requested area to containing regions and Japan.
    No unrestricted text search is added when an area is specified. Resource
    expansion is round-robin within each page, after format matching.
    """

    adapter_type = "geospatial-jp"
    search_conditions = frozenset({"text", "area", "format", "limit"})

    def load(self, config: Config) -> Source:
        source = super().load(config)
        return replace(
            source,
            provenance=replace(
                source.provenance, provider=self.adapter_type, adapter=self.adapter_type
            ),
        )

    def search(self, query: SearchQuery) -> tuple[Result, ...]:
        endpoint = self._endpoint_from({}, self._endpoint)
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported G Spatial search conditions: {', '.join(sorted(unsupported))}"
            )
        if query.limit == 0:
            return ()
        terms = tuple(dict.fromkeys((query.text or "").split()))
        # Explicit AND avoids depending on the site's default whitespace operator.
        base: dict[str, Any] = {
            "q": " AND ".join(_literal(term) for term in terms) or "*:*",
            "rows": 100,
        }
        stages: tuple[tuple[tuple[dict[str, str], frozenset[int]], ...], ...] = (
            _area_searches(query.area, base["q"])
            if query.area is not None
            else ((({}, frozenset({0})),),)
        )
        seen_packages: set[str] = set()
        seen_resources: set[str] = set()
        found: list[Result] = []
        for stage in stages:
            offsets = [0] * len(stage)
            active = [True] * len(stage)
            while any(active):
                candidates: list[tuple[JsonObject, dict[str, Any]]] = []
                for index, (params, priorities) in enumerate(stage):
                    if not active[index]:
                        continue
                    request = {**base, **params, "start": offsets[index]}
                    response = self._object(
                        self._action(endpoint, "package_search", request),
                        "G Spatial search result",
                    )
                    packages = self._objects(
                        response.get("results"), "G Spatial packages"
                    )
                    count = response.get("count")
                    if type(count) is not int or count < 0:
                        raise ProviderResponseError(
                            "G Spatial count must be an integer"
                        )
                    if not packages and offsets[index] < count:
                        raise ProviderResponseError(
                            "G Spatial page is empty before its count"
                        )
                    offsets[index] += len(packages)
                    active[index] = offsets[index] < count
                    for package in packages:
                        if _area_priority(package, query.area) not in priorities:
                            continue
                        identifier = self._required_string(package, "id")
                        if identifier in seen_packages:
                            continue
                        seen_packages.add(identifier)
                        candidates.append((package, request))
                candidates.sort(
                    key=lambda item: (
                        _area_priority(item[0], query.area),
                        -len(_tags(item[0]) & set(terms)),
                    )
                )
                groups: list[list[Result]] = []
                for package, request in candidates:
                    group: list[Result] = []
                    for resource in self._objects(
                        package.get("resources"), "CKAN resources"
                    ):
                        item = self._resource_result(package, resource, endpoint, query)
                        if item is None:
                            continue
                        identifier = self._required_string(resource, "id")
                        if identifier in seen_resources:
                            continue
                        seen_resources.add(identifier)
                        group.append(
                            replace(
                                item,
                                provenance=replace(
                                    item.provenance,
                                    provider=self.adapter_type,
                                    adapter=self.adapter_type,
                                    query_parameters=request,
                                ),
                            )
                        )
                    groups.append(group)
                for row in zip_longest(*groups, fillvalue=None):
                    for item in cast(tuple[Result | None, ...], row):
                        if item is None:
                            continue
                        found.append(item)
                        if query.limit is not None and len(found) == query.limit:
                            return tuple(found)
                if query.limit is None:
                    break
        return tuple(found)
