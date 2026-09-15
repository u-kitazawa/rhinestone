"""DCAT RDF catalog interpretation using a user-owned RDFLib runtime."""

from collections.abc import Callable, Mapping
from typing import Any

from ....errors import (
    ConfigValidationError,
    DependencyUnavailableError,
    ProviderMetadataError,
    ProviderResponseError,
    ResourceNotFoundError,
    UnsupportedSearchConditionError,
)
from ....models import Config, ResourceCandidate, SearchQuery, SearchResult, Source
from ....representations import canonical_format, format_from_media_type
from ....security import DestinationPolicy
from .._knowledge import source, string
from ..base import SourceAdapterBase

_DCAT = "http://www.w3.org/ns/dcat#"
_DCT = "http://purl.org/dc/terms/"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


class DcatAdapter(SourceAdapterBase):
    """Interpret a DCAT RDF catalog and resolve one Dataset distribution."""

    adapter_type = "dcat"
    search_conditions = frozenset({"text", "limit"})

    def __init__(
        self,
        get_document: Callable[[str], str],
        rdf_runtime_factory: Callable[[], Any],
        catalog_uri: str | None = None,
        serialization: str = "turtle",
        destination_policy: DestinationPolicy | None = None,
    ) -> None:
        super().__init__(
            get_json=lambda url, params: None,
            destination_policy=destination_policy,
        )
        self._document_loader = get_document
        self._rdf_runtime_factory = rdf_runtime_factory
        self._catalog_uri = catalog_uri
        self._serialization = serialization

    def _load_catalog(self, settings: Mapping[str, Any]) -> tuple[Any, Any, str, str]:
        uri = string(settings, "uri")
        if self._catalog_uri is not None and uri != self._catalog_uri:
            raise ConfigValidationError(
                "DCAT catalog URI must match the configured catalog_uri"
            )
        self._destination_policy.authorize(uri)
        serialization = settings.get("serialization", self._serialization)
        if serialization not in ("json-ld", "turtle", "xml"):
            raise ConfigValidationError("Expected json-ld, turtle or xml serialization")
        try:
            rdf = self._rdf_runtime_factory()
        except DependencyUnavailableError:
            raise
        except Exception as error:
            raise DependencyUnavailableError(
                "RDF runtime could not be loaded"
            ) from error
        try:
            document = self._document_loader(uri)
        except Exception as error:
            raise ProviderMetadataError("Could not load RDF catalog") from error
        try:
            graph = rdf.Graph()
            graph.parse(data=document, format=serialization, publicID=uri)
        except Exception as error:
            raise ProviderResponseError("Invalid RDF catalog") from error
        return rdf, graph, document, uri

    @staticmethod
    def _value(rdf: Any, graph: Any, subject: Any, predicate: str) -> str | None:
        values = sorted(
            str(item) for item in graph.objects(subject, rdf.URIRef(predicate))
        )
        return values[0] if values else None

    def load(self, config: Config) -> Source:
        """Load the configured Dataset URI and expose its distribution."""
        settings = self._config_settings(config)
        rdf_runtime, catalog_graph, document, catalog_uri = self._load_catalog(settings)
        dataset_uri = string(settings, "dataset")
        dataset = rdf_runtime.URIRef(dataset_uri)
        if (
            dataset,
            rdf_runtime.URIRef(_RDF_TYPE),
            rdf_runtime.URIRef(_DCAT + "Dataset"),
        ) not in catalog_graph:
            raise ResourceNotFoundError("DCAT Dataset URI was not found")
        candidates: list[ResourceCandidate] = []
        for distribution in sorted(
            set(
                catalog_graph.objects(
                    dataset, rdf_runtime.URIRef(_DCAT + "distribution")
                )
            ),
            key=str,
        ):
            media_type = self._value(
                rdf_runtime, catalog_graph, distribution, _DCAT + "mediaType"
            )
            format_name = canonical_format(
                self._value(rdf_runtime, catalog_graph, distribution, _DCT + "format")
            ) or format_from_media_type(media_type)
            for url in sorted(
                set(
                    catalog_graph.objects(
                        distribution, rdf_runtime.URIRef(_DCAT + "downloadURL")
                    )
                ),
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
                                rdf_runtime,
                                catalog_graph,
                                distribution,
                                _DCT + "license",
                            ),
                        },
                    )
                )
        return source(
            self.adapter_type,
            dataset_uri,
            {"document": document, "catalog_uri": catalog_uri},
            tuple(candidates),
            title=self._value(rdf_runtime, catalog_graph, dataset, _DCT + "title"),
            description=self._value(
                rdf_runtime, catalog_graph, dataset, _DCT + "description"
            ),
            license_name=self._value(
                rdf_runtime, catalog_graph, dataset, _DCT + "license"
            ),
            endpoint=catalog_uri,
            capabilities=("download", "search"),
        )

    def search(self, query: SearchQuery) -> tuple[SearchResult, ...]:
        """Search Dataset subjects by text while preserving their distributions."""
        if query.supplied_conditions - self.search_conditions:
            raise UnsupportedSearchConditionError("Unsupported DCAT search")
        settings: dict[str, Any] = {
            "uri": self._catalog_uri,
            "serialization": self._serialization,
        }
        rdf_runtime, catalog_graph, document, catalog_uri = self._load_catalog(settings)
        results: list[SearchResult] = []
        for dataset in sorted(
            set(
                catalog_graph.subjects(
                    rdf_runtime.URIRef(_RDF_TYPE),
                    rdf_runtime.URIRef(_DCAT + "Dataset"),
                )
            ),
            key=str,
        ):
            if not isinstance(dataset, rdf_runtime.URIRef):
                continue
            title = self._value(
                rdf_runtime, catalog_graph, dataset, _DCT + "title"
            ) or str(dataset)
            description = self._value(
                rdf_runtime, catalog_graph, dataset, _DCT + "description"
            )
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
                endpoint=catalog_uri,
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
                    raw_metadata=item.raw_metadata,
                )
            )
        return tuple(results[: query.limit])
