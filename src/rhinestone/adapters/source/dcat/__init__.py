"""DCAT RDF catalog interpretation using a user-owned RDFLib runtime."""

from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from ....errors import (
    ConfigValidationError,
    ProviderMetadataError,
    ProviderResponseError,
    ResourceNotFoundError,
    UnsupportedSearchConditionError,
)
from ....models import Config, ResourceCandidate, SearchQuery, SearchResult, Source
from .._knowledge import source, string
from ..base import ProviderAdapter

_DCAT = "http://www.w3.org/ns/dcat#"
_DCT = "http://purl.org/dc/terms/"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_FORMATS = {
    "application/geo+json": "geojson",
    "application/geopackage+sqlite3": "gpkg",
}


class DcatAdapter(ProviderAdapter):
    adapter_type = "dcat"
    search_conditions = frozenset({"text", "limit"})

    def __init__(
        self,
        get_document: Callable[[str], str],
        rdf_runtime_factory: Callable[[], Any],
        catalog_uri: Optional[str] = None,
        serialization: str = "turtle",
    ) -> None:
        super().__init__(get_json=lambda url, params: None)
        self._get_document = get_document
        self._rdf_runtime_factory = rdf_runtime_factory
        self._catalog_uri = catalog_uri
        self._serialization = serialization

    def _catalog(self, settings: Mapping[str, Any]) -> Tuple[Any, Any, str, str]:
        uri = string(settings, "uri")
        serialization = settings.get("serialization", self._serialization)
        if serialization not in ("json-ld", "turtle", "xml"):
            raise ConfigValidationError("Expected json-ld, turtle or xml serialization")
        rdf = self._rdf_runtime_factory()
        try:
            document = self._get_document(uri)
        except Exception as error:
            raise ProviderMetadataError("Could not load RDF catalog") from error
        try:
            graph = rdf.Graph()
            graph.parse(data=document, format=serialization, publicID=uri)
        except Exception as error:
            raise ProviderResponseError("Invalid RDF catalog") from error
        return rdf, graph, document, uri

    @staticmethod
    def _value(rdf: Any, graph: Any, subject: Any, predicate: str) -> Optional[str]:
        values = sorted(
            str(item) for item in graph.objects(subject, rdf.URIRef(predicate))
        )
        return values[0] if values else None

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        rdf, graph, document, uri = self._catalog(settings)
        dataset_uri = string(settings, "dataset")
        dataset = rdf.URIRef(dataset_uri)
        if (dataset, rdf.URIRef(_RDF_TYPE), rdf.URIRef(_DCAT + "Dataset")) not in graph:
            raise ResourceNotFoundError("DCAT Dataset URI was not found")
        candidates: List[ResourceCandidate] = []
        for distribution in sorted(
            set(graph.objects(dataset, rdf.URIRef(_DCAT + "distribution"))), key=str
        ):
            media_type = self._value(rdf, graph, distribution, _DCAT + "mediaType")
            format_name = self._value(rdf, graph, distribution, _DCT + "format")
            format_name = _FORMATS.get(media_type or "", format_name)
            if format_name is not None:
                format_name = format_name.lower()
            for url in sorted(
                set(graph.objects(distribution, rdf.URIRef(_DCAT + "downloadURL"))),
                key=str,
            ):
                candidates.append(
                    ResourceCandidate(
                        str(url),
                        format_name,
                        media_type,
                        {
                            "distribution": str(distribution),
                            "matches_config": settings.get(
                                "distribution", str(distribution)
                            )
                            == str(distribution),
                            "access_kind": "file",
                            "license": self._value(
                                rdf, graph, distribution, _DCT + "license"
                            ),
                        },
                    )
                )
        return source(
            self.adapter_type,
            dataset_uri,
            {"document": document, "catalog_uri": uri},
            tuple(candidates),
            title=self._value(rdf, graph, dataset, _DCT + "title"),
            description=self._value(rdf, graph, dataset, _DCT + "description"),
            license_name=self._value(rdf, graph, dataset, _DCT + "license"),
            endpoint=uri,
            capabilities=("download", "search"),
        )

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        if query.supplied_conditions - self.search_conditions:
            raise UnsupportedSearchConditionError("Unsupported DCAT search")
        settings: Dict[str, Any] = {
            "uri": self._catalog_uri,
            "serialization": self._serialization,
        }
        rdf, graph, document, uri = self._catalog(settings)
        results: List[SearchResult] = []
        for dataset in sorted(
            set(graph.subjects(rdf.URIRef(_RDF_TYPE), rdf.URIRef(_DCAT + "Dataset"))),
            key=str,
        ):
            if not isinstance(dataset, rdf.URIRef):
                continue
            title = self._value(rdf, graph, dataset, _DCT + "title") or str(dataset)
            description = self._value(rdf, graph, dataset, _DCT + "description")
            if (
                query.text
                and query.text.casefold()
                not in (title + " " + (description or "")).casefold()
            ):
                continue
            item = source(
                self.adapter_type,
                str(dataset),
                {"document": document},
                (),
                title=title,
                description=description,
                endpoint=uri,
            )
            results.append(
                SearchResult(
                    title=title,
                    description=description,
                    discovered_by=self.adapter_type,
                    target=Config(
                        self.adapter_type, dict(settings, dataset=str(dataset))
                    ),
                    metadata=item.metadata,
                    provenance=item.provenance,
                )
            )
        return tuple(results[: query.limit])
