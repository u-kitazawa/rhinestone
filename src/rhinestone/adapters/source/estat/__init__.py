"""e-Stat API 3.0 source adapter."""

from typing import Any, Dict, List, Mapping, Optional, Tuple, cast

from ....errors import ConfigValidationError, ProviderResponseError
from ....models import (
    Config,
    Metadata,
    Provenance,
    ResourceCandidate,
    SearchQuery,
    SearchResult,
    Source,
)
from ..base import JsonObject, JsonTransport, ProviderAdapter

DEFAULT_ENDPOINT = "https://api.e-stat.go.jp/rest/3.0/app/json"


class EStatAdapter(ProviderAdapter):
    adapter_type = "estat"
    search_conditions = frozenset({"text", "limit"})

    def __init__(
        self,
        app_id: Optional[str] = None,
        get_json: Optional[JsonTransport] = None,
        endpoint: str = DEFAULT_ENDPOINT,
        language: str = "J",
        api_key: Optional[str] = None,
    ) -> None:
        if get_json is None:
            raise ConfigValidationError("get_json callback is required")
        if app_id is not None and api_key is not None:
            raise ConfigValidationError("Configure either app_id or api_key, not both")
        credential = app_id if app_id is not None else api_key
        super().__init__(get_json=get_json, endpoint=endpoint)
        if not credential:
            raise ConfigValidationError("app_id/api_key must be a non-empty string")
        if language not in {"J", "E"}:
            raise ConfigValidationError("language must be J or E")
        self._app_id = credential
        self._language = language

    def _estat(
        self, endpoint: str, operation: str, params: Mapping[str, Any]
    ) -> JsonObject:
        response = self._request(f"{endpoint}/{operation}", params)
        root_name = {
            "getMetaInfo": "GET_META_INFO",
            "getStatsList": "GET_STATS_LIST",
        }[operation]
        root = self._object(response.get(root_name), f"e-Stat {root_name}")
        result = self._object(root.get("RESULT"), "e-Stat RESULT")
        if result.get("STATUS") != 0:
            raise ProviderResponseError(str(result.get("ERROR_MSG", "e-Stat error")))
        return root

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        stats_data_id = self._required_string(settings, "stats_data_id")
        endpoint = self._endpoint_from(settings, DEFAULT_ENDPOINT)
        root = self._estat(
            endpoint,
            "getMetaInfo",
            {
                "appId": self._app_id,
                "statsDataId": stats_data_id,
                "lang": self._language,
            },
        )
        metadata_information = self._object(
            root.get("METADATA_INF"), "e-Stat METADATA_INF"
        )
        table = self._object(metadata_information.get("TABLE_INF"), "e-Stat TABLE_INF")
        title = _localized(table.get("TITLE"))
        publisher = _localized(table.get("GOV_ORG"))
        data_url = f"{endpoint}/getStatsData"
        candidate = ResourceCandidate(
            uri=data_url,
            format="estat-api",
            media_type="application/json",
            attributes={"stats_data_id": stats_data_id},
        )
        provenance = Provenance(
            provider="estat",
            dataset_identifier=stats_data_id,
            api_endpoint=endpoint,
            query_parameters={"stats_data_id": stats_data_id, "lang": self._language},
            adapter="estat",
            raw=metadata_information,
        )
        return Source(
            metadata=Metadata(
                title=title,
                publisher=publisher,
                raw=metadata_information,
            ),
            candidates=(candidate,),
            capabilities=frozenset({"service-query", "search"}),
            provenance=provenance,
            raw_metadata=root,
        )

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported e-Stat search conditions: {', '.join(sorted(unsupported))}"
            )
        params: Dict[str, Any] = {
            "appId": self._app_id,
            "lang": self._language,
        }
        if query.text is not None:
            params["searchWord"] = query.text
        if query.limit is not None:
            params["limit"] = query.limit
        endpoint = self._endpoint_from({}, DEFAULT_ENDPOINT)
        root = self._estat(endpoint, "getStatsList", params)
        data_list = self._object(root.get("DATALIST_INF"), "e-Stat DATALIST_INF")
        tables = self._objects(data_list.get("TABLE_INF"), "e-Stat TABLE_INF")
        found: List[SearchResult] = []
        for table in tables:
            stats_data_id = self._required_string(table, "@id")
            title = _localized(table.get("TITLE")) or stats_data_id
            found.append(
                SearchResult(
                    title=title,
                    description=_optional_string(table.get("DESCRIPTION")),
                    source_id=self.adapter_type,
                    provider_settings={"stats_data_id": stats_data_id},
                    metadata=Metadata(
                        title=title,
                        publisher=_localized(table.get("GOV_ORG")),
                        raw=table,
                    ),
                    provenance=Provenance(
                        provider="estat",
                        dataset_identifier=stats_data_id,
                        api_endpoint=endpoint,
                        query_parameters={"search_word": query.text},
                        adapter="estat",
                        raw=table,
                    ),
                )
            )
        return tuple(found)


def _localized(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        localized = cast(Dict[str, Any], value).get("$")
        return localized if isinstance(localized, str) else None
    return None


def _optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None
