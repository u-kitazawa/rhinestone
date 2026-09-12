from types import SimpleNamespace
from typing import Any, FrozenSet

import pytest

from rhinestone import (
    Config,
    Provider,
    configure,
)
from rhinestone.adapters.contracts import (
    ExecutionAdapterDefinition,
    SourceAdapterDefinition,
)
from rhinestone.api import _build_source_adapter  # pyright: ignore[reportPrivateUsage]
from rhinestone.errors import AdapterRegistrationError
from rhinestone.models import (
    Metadata,
    Provenance,
    Resource,
    ResourceCandidate,
    RuntimeFactory,
    Source,
)
from rhinestone.security import DestinationPolicy


def custom_source(provider: Provider, context: Any) -> Any:
    assert context.provider_id == provider.id

    class Adapter:
        def load(self, config: Config) -> Source:
            return Source(
                metadata=Metadata(title=config.settings["title"]),
                candidates=(
                    ResourceCandidate(
                        uri="https://data.example/item.bin",
                        format="custom",
                        media_type="application/octet-stream",
                    ),
                ),
                capabilities=frozenset(),
                provenance=Provenance(provider=provider.id, adapter="custom"),
                raw_metadata={"provider": provider.id},
            )

    return Adapter()


class CustomExecution:
    name = "custom-runtime"
    priority = 100

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        return resource.format == "custom" and "custom-runtime" in dependencies

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: Any = None,
    ) -> Any:
        return runtime.open(resource.uri)


def test_custom_source_and_execution_share_the_public_pipeline() -> None:
    def open_runtime(uri: str) -> tuple[str, str]:
        return ("opened", uri)

    runtime = SimpleNamespace(open=open_runtime)
    app = configure(
        sources=(Provider("custom", "custom-source"),),
        adapters=(
            SourceAdapterDefinition("custom-source", custom_source),
            ExecutionAdapterDefinition(
                "custom-runtime", lambda context: CustomExecution()
            ),
        ),
        dependencies={"custom-runtime": runtime},
    )

    resource = app.resolve(Config("custom", {"title": "Example"}))

    assert resource.metadata.title == "Example"
    assert resource.provenance.provider == "custom"
    assert resource.source.raw_metadata["provider"] == "custom"
    assert app.open(Config("custom", {"title": "Example"}), "custom-runtime") == (
        "opened",
        "https://data.example/item.bin",
    )


def test_source_definition_can_declare_a_lazy_source_dependency() -> None:
    loaded: list[bool] = []

    def factory() -> object:
        loaded.append(True)
        return object()

    definition = SourceAdapterDefinition(
        "custom-source",
        lambda provider, context: custom_source(provider, context),
        dependencies=frozenset({"custom-source-runtime"}),
    )
    app = configure(
        sources=(Provider("custom", "custom-source"),),
        adapters=(definition,),
        dependencies={"custom-source-runtime": RuntimeFactory(factory)},
    )
    assert loaded == []
    app.resolve(Config("custom", {"title": "Example"}))
    assert loaded == []


def test_source_dependencies_are_scoped_to_each_definition() -> None:
    seen: dict[str, FrozenSet[str]] = {}

    def factory(provider: Provider, context: Any) -> Any:
        seen[provider.id] = context.dependencies.available
        return custom_source(provider, context)

    app = configure(
        sources=(
            Provider("first", "first-source"),
            Provider("second", "second-source"),
        ),
        adapters=(
            SourceAdapterDefinition(
                "first-source", factory, dependencies=frozenset({"first-runtime"})
            ),
            SourceAdapterDefinition(
                "second-source", factory, dependencies=frozenset({"second-runtime"})
            ),
        ),
        dependencies={"first-runtime": object(), "second-runtime": object()},
    )

    app.resolve(Config("first", {"title": "First"}))
    assert seen == {
        "first": frozenset({"first-runtime"}),
        "second": frozenset({"second-runtime"}),
    }


def test_source_dependency_instances_are_cached_across_provider_contexts() -> None:
    calls: list[bool] = []
    runtime = object()

    def load_runtime() -> object:
        calls.append(True)
        return runtime

    def factory(provider: Provider, context: Any) -> Any:
        assert context.dependencies.get("shared-runtime") is runtime
        return custom_source(provider, context)

    app = configure(
        sources=(
            Provider("first", "shared-source"),
            Provider("second", "shared-source"),
        ),
        adapters=(
            SourceAdapterDefinition(
                "shared-source", factory, dependencies=frozenset({"shared-runtime"})
            ),
        ),
        dependencies={"shared-runtime": RuntimeFactory(load_runtime)},
    )

    app.resolve(Config("first", {"title": "First"}))
    app.resolve(Config("second", {"title": "Second"}))
    assert len(calls) == 1


def test_custom_provider_credentials_are_authorized_by_default_policy() -> None:
    provider = Provider(
        "custom",
        "custom-source",
        {"endpoint": "https://custom.example/api", "credential": "custom-key"},
    )
    policy = DestinationPolicy.from_catalog((provider,))

    policy.authorize(
        "https://custom.example/api/items",
        credentialed=True,
        provider="custom",
        service="custom-source",
        credential="custom-key",
    )


def test_unregistered_source_type_fails_during_context_composition() -> None:
    with pytest.raises(AdapterRegistrationError, match="unknown-source"):
        configure(sources=(Provider("unknown", "unknown-source"),))

    with pytest.raises(AdapterRegistrationError, match="unknown-source"):
        _build_source_adapter(  # pyright: ignore[reportPrivateUsage]
            Provider("unknown", "unknown-source"),
            {},
            object(),  # type: ignore[arg-type]
        )


def test_builtin_and_custom_duplicate_types_are_rejected() -> None:
    with pytest.raises(AdapterRegistrationError, match="ckan"):
        configure(adapters=(SourceAdapterDefinition("ckan", custom_source),))

    with pytest.raises(AdapterRegistrationError, match="gdal"):
        configure(
            adapters=(
                ExecutionAdapterDefinition("gdal", lambda context: CustomExecution()),
            )
        )

    with pytest.raises(AdapterRegistrationError, match="custom-source"):
        configure(
            adapters=(
                SourceAdapterDefinition("custom-source", custom_source),
                SourceAdapterDefinition("custom-source", custom_source),
            )
        )

    with pytest.raises(AdapterRegistrationError, match="expected 'declared'"):
        configure(
            adapters=(
                ExecutionAdapterDefinition(
                    "declared", lambda context: CustomExecution()
                ),
            )
        )


def test_adapter_definition_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        SourceAdapterDefinition("", custom_source)
    with pytest.raises(ValueError):
        SourceAdapterDefinition("custom", object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ExecutionAdapterDefinition("", lambda context: CustomExecution())
    with pytest.raises(ValueError):
        ExecutionAdapterDefinition("custom", object())  # type: ignore[arg-type]
    with pytest.raises(AdapterRegistrationError, match="Unknown adapter"):
        configure(adapters=(object(),))  # type: ignore[arg-type]
