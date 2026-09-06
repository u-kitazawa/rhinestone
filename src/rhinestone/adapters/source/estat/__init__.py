"""e-Stat API 3.0 source adapter."""

from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, cast

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


class EStatAdapter(ProviderAdapter):
    adapter_type = "estat"
    search_conditions = frozenset({"text", "limit"})

    def __init__(
        self,
        app_id: Optional[str] = None,
        get_json: Optional[JsonTransport] = None,
        endpoint: Optional[str] = None,
        language: Optional[str] = None,
        api_key: Optional[str] = None,
        credential_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        if get_json is None:
            raise ConfigValidationError("get_json callback is required")
        configured = sum(
            value is not None for value in (app_id, api_key, credential_factory)
        )
        if configured > 1:
            raise ConfigValidationError(
                "Configure only one of app_id, api_key, or credential_factory"
            )
        credential = app_id if app_id is not None else api_key
        if credential is not None and not credential:
            raise ConfigValidationError("app_id/api_key must be a non-empty string")
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ConfigValidationError("e-Stat endpoint must be configured")
        if language not in {"J", "E"}:
            raise ConfigValidationError("language must be J or E")
        super().__init__(get_json=get_json, endpoint=endpoint)
        self._app_id = credential
        self._credential_factory = credential_factory
        self._language = cast(str, language)

    def _credential(self) -> str:
        if self._credential_factory is not None:
            value = self._credential_factory()
        else:
            value = self._app_id
        if not isinstance(value, str) or not value:
            raise ConfigValidationError("e-Stat credential must be configured")
        return value

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
        endpoint = self._endpoint_from(settings, self._endpoint)
        root = self._estat(
            endpoint,
            "getMetaInfo",
            {
                "appId": self._credential(),
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
            "appId": self._credential(),
            "lang": self._language,
        }
        if query.text is not None:
            params["searchWord"] = query.text
        if query.limit is not None:
            params["limit"] = query.limit
        endpoint = self._endpoint_from({}, self._endpoint)
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
                    settings={"stats_data_id": stats_data_id},
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
