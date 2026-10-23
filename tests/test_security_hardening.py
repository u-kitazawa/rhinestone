"""Regression tests for DCAT document references and credentialed service URLs."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from rhinestone import Provider
from rhinestone.adapters.execution.json_service import JsonServiceAdapter
from rhinestone.adapters.source.dcat import DcatAdapter
from rhinestone.adapters.source.dcat.adapter import (
    _reject_external_jsonld_contexts,  # pyright: ignore[reportPrivateUsage]
)
from rhinestone.errors import DestinationNotAllowedError, ProviderResponseError
from rhinestone.models import AccessPlan, SearchQuery
from rhinestone.registry import CredentialRegistry
from rhinestone.security import DestinationPolicy


@pytest.mark.parametrize(
    "context",
    (
        "file:///etc/rhinestone-context.json",
        ["https://example.test/context.jsonld"],
        {"name": {"@context": "https://example.test/inner.jsonld"}},
        {"@import": "file:///etc/rhinestone-context.json"},
    ),
)
def test_dcat_rejects_external_context_before_rdf_parsing(context: Any) -> None:
    class GraphMustNotParse:
        def parse(self, **kwargs: Any) -> None:
            raise AssertionError("External context reached RDFLib")

    document = json.dumps({"@context": context, "@id": "https://example.test/dataset"})
    adapter = DcatAdapter(
        lambda uri: document,
        lambda: SimpleNamespace(Graph=GraphMustNotParse),
        catalog_uri="https://example.test/catalog",
        serialization="json-ld",
    )

    with pytest.raises(ProviderResponseError, match="external contexts"):
        adapter.search(SearchQuery())


def test_dcat_rejects_invalid_json_before_rdf_parsing() -> None:
    adapter = DcatAdapter(
        lambda uri: '{"@context":',
        lambda: SimpleNamespace(Graph=lambda: None),
        catalog_uri="https://example.test/catalog",
        serialization="json-ld",
    )

    with pytest.raises(ProviderResponseError, match="Invalid RDF catalog"):
        adapter.search(SearchQuery())


@pytest.mark.parametrize(
    "uri",
    (
        "file:///etc/hosts",
        "/tmp/data",
        "gopher://example.test/resource",
    ),
)
def test_json_service_rejects_non_http_before_credential_release(uri: str) -> None:
    credential_calls: list[bool] = []
    runtime_calls: list[bool] = []
    preparer_calls: list[bool] = []

    def prepare(
        plan: AccessPlan, credentials: CredentialRegistry
    ) -> tuple[dict[str, Any], dict[str, str]]:
        preparer_calls.append(True)
        return {"key": credentials.get("secret")}, {}

    def get(**kwargs: Any) -> None:
        runtime_calls.append(True)

    policy = DestinationPolicy.from_catalog(
        (Provider("private", "odpt", {"endpoint": "https://example.test/api"}),)
    )
    adapter = JsonServiceAdapter(
        prepare,
        "odpt",
        CredentialRegistry(
            {"secret": lambda: credential_calls.append(True) or "sensitive"}
        ),
        policy,
    )
    plan = AccessPlan(
        kind="service-query",
        uri=uri,
        media_type="application/json",
        provider="private",
        service="odpt",
        credential="secret",
    )

    with pytest.raises(DestinationNotAllowedError, match="HTTP\\(S\\)"):
        adapter.open(plan, SimpleNamespace(get=get))
    assert credential_calls == []
    assert preparer_calls == []
    assert runtime_calls == []


def test_dcat_preserves_json_literal_keys_as_data() -> None:
    document = json.dumps(
        {
            "@context": {"ex": "https://example.test/"},
            "@id": "https://example.test/dataset",
            "ex:metadata": {
                "@type": "@json",
                "@value": {
                    "@context": "literal, not a URL",
                    "@import": "also literal",
                    "nested": [{"@context": "still literal"}],
                },
            },
        }
    )
    _reject_external_jsonld_contexts(document)
