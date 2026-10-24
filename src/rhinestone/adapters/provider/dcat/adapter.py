"""DCAT RDF catalog interpretation using a user-owned RDFLib runtime."""

from collections.abc import Callable, Mapping
from typing import Any

from ....errors import (
    AmbiguousResourceError,
    ConfigValidationError,
    DependencyUnavailableError,
    ProviderMetadataError,
    ProviderResponseError,
    ResourceNotFoundError,
    UnsupportedSearchConditionError,
)
from ....models import Metadata, Provenance, Reference, Resource, SearchQuery
from ....representations import canonical_format, format_from_media_type
from ....resolution import resource_from_delivery
from ....security import DestinationPolicy
from .._knowledge import string
from ..base import ProviderAdapter

_DCAT = "http://www.w3.org/ns/dcat#"
_DCT = "http://purl.org/dc/terms/"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


class DcatAdapter(ProviderAdapter):
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

    def load(self, reference: Reference) -> Resource:
        """Load the configured Dataset URI and expose its distribution."""
        settings = self._reference_parameters(reference)
        rdf_runtime, catalog_graph, document, catalog_uri = self._load_catalog(settings)
        dataset_uri = string(settings, "dataset")
        dataset = rdf_runtime.URIRef(dataset_uri)
        if (
            dataset,
            rdf_runtime.URIRef(_RDF_TYPE),
            rdf_runtime.URIRef(_DCAT + "Dataset"),
        ) not in catalog_graph:
            raise ResourceNotFoundError("DCAT Dataset URI was not found")
        resources = self._dataset_resources(
            reference,
            rdf_runtime,
            catalog_graph,
            dataset,
            document,
            catalog_uri,
        )
        selected_distribution = reference.resource_identifier or (
            settings.get("distribution")
            if isinstance(settings.get("distribution"), str)
            else None
        )
        if selected_distribution is not None:
            resources = tuple(
                resource
                for resource in resources
                if resource.reference.resource_identifier == selected_distribution
                or resource.reference.parameters.get("distribution")
                == selected_distribution
            )
        if not resources:
            raise ResourceNotFoundError("DCAT Dataset has no matching distribution")
        if len(resources) != 1:
            raise AmbiguousResourceError(
                f"DCAT Dataset has {len(resources)} distributions; set "
                "Reference.resource_identifier"
            )
        return resources[0]

    def _dataset_resources(
        self,
        reference: Reference,
        rdf_runtime: Any,
        catalog_graph: Any,
        dataset: Any,
        document: str,
        catalog_uri: str,
    ) -> tuple[Resource, ...]:
        dataset_uri = str(dataset)
        title = self._value(rdf_runtime, catalog_graph, dataset, _DCT + "title")
        description = self._value(
            rdf_runtime, catalog_graph, dataset, _DCT + "description"
        )
        license_name = self._value(
            rdf_runtime, catalog_graph, dataset, _DCT + "license"
        )
        raw = {"document": document, "catalog_uri": catalog_uri}
        metadata = Metadata(
            title=title or dataset_uri,
            description=description,
            publisher=self.adapter_type,
            license=license_name,
            raw=raw,
        )
        resources: list[Resource] = []
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
            download_urls = sorted(
                set(
                    catalog_graph.objects(
                        distribution, rdf_runtime.URIRef(_DCAT + "downloadURL")
                    )
                ),
                key=str,
            )
            for index, url in enumerate(download_urls, start=1):
                uri = str(url)
                distribution_uri = str(distribution)
                distribution_id = (
                    distribution_uri
                    if len(download_urls) == 1
                    else f"{distribution_uri}#delivery-{index}"
                )
                provenance = Provenance(
                    provider=self.adapter_type,
                    dataset_identifier=dataset_uri,
                    resource_identifier=distribution_id,
                    api_endpoint=catalog_uri,
                    original_url=uri,
                    adapter=self.adapter_type,
                    raw=raw,
                )
                resources.append(
                    resource_from_delivery(
                        reference=Reference(
                            reference.provider_id,
                            dataset_identifier=dataset_uri,
                            resource_identifier=distribution_id,
                            parameters={
                                "uri": catalog_uri,
                                "serialization": self._serialization,
                                "dataset": dataset_uri,
                                "distribution": distribution_uri,
                            },
                        ),
                        uri=uri,
                        format=format_name,
                        media_type=media_type,
                        metadata=metadata,
                        provenance=provenance,
                    )
                )
        return tuple(resources)

    def search(self, query: SearchQuery) -> tuple[Resource, ...]:
        """Search Dataset subjects by text while preserving their distributions."""
        if query.supplied_conditions - self.search_conditions:
            raise UnsupportedSearchConditionError("Unsupported DCAT search")
        settings: dict[str, Any] = {
            "uri": self._catalog_uri,
            "serialization": self._serialization,
        }
        rdf_runtime, catalog_graph, document, catalog_uri = self._load_catalog(settings)
        results: list[Resource] = []
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
            haystack = (title + " " + (description or "")).casefold()
            if any(term.casefold() not in haystack for term in query.text_terms):
                continue
            reference = Reference(
                self.adapter_type,
                dataset_identifier=str(dataset),
                parameters=dict(settings, dataset=str(dataset)),
            )
            results.extend(
                self._dataset_resources(
                    reference,
                    rdf_runtime,
                    catalog_graph,
                    dataset,
                    document,
                    catalog_uri,
                )
            )
            if query.limit is not None and len(results) >= query.limit:
                return tuple(results[: query.limit])
        return tuple(results[: query.limit])
