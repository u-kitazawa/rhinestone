"""Installed metadata selects provider definitions without eager plugin imports."""

import json
import sys
from importlib import metadata
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from rhinestone import Catalog, Provider, Reference, configure
from rhinestone._entry_points import (  # pyright: ignore[reportPrivateUsage]
    GROUPS,
    KNOWLEDGE_GROUP,
    PROVIDER_GROUP,
    RUNTIME_GROUP,
    DefinitionIndex,
    discover,
)
from rhinestone.adapters.contracts import (
    ExecutionAdapterDefinition,
    SourceAdapterDefinition,
)
from rhinestone.errors import (
    AdapterContractError,
    AdapterDiscoveryError,
    AdapterFactoryError,
    AdapterLoadError,
    AdapterRegistrationError,
)
from rhinestone.models import AccessPlan, SearchQuery
from tests.test_custom_adapters import CustomExecution, custom_source


def point(
    name: str,
    value: str = "fixture_provider:definition",
    *,
    group: str = PROVIDER_GROUP,
) -> metadata.EntryPoint:
    return metadata.EntryPoint(name=name, value=value, group=group)


def install_metadata(
    monkeypatch: pytest.MonkeyPatch, *points: metadata.EntryPoint
) -> list[str]:
    calls: list[str] = []
    selected = metadata.EntryPoints(points)

    def entry_points() -> Any:
        calls.append("metadata")
        return selected

    monkeypatch.setattr(metadata, "entry_points", entry_points)
    return calls


def export(monkeypatch: pytest.MonkeyPatch, definition: object) -> None:
    module = ModuleType("fixture_provider")
    module.definition = definition  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)


def index(*points: metadata.EntryPoint) -> DefinitionIndex[SourceAdapterDefinition]:
    return DefinitionIndex(
        {}, points, SourceAdapterDefinition, lambda d: d.adapter_type
    )


def test_discovery_reads_all_groups_once_without_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_metadata(
        monkeypatch,
        *(point(group, "missing_optional:definition", group=group) for group in GROUPS),
    )
    groups = discover()
    assert tuple(groups) == GROUPS
    assert calls == ["metadata"]
    assert groups[PROVIDER_GROUP][0].name == PROVIDER_GROUP
    assert groups[RUNTIME_GROUP][0].name == RUNTIME_GROUP
    assert groups[KNOWLEDGE_GROUP][0].name == KNOWLEDGE_GROUP


def test_identity_iteration_membership_and_cache_do_not_load_other_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = SourceAdapterDefinition("selected", custom_source)
    export(monkeypatch, definition)
    definitions = DefinitionIndex(
        {"explicit": SourceAdapterDefinition("explicit", custom_source)},
        (point("unused", "missing_optional:definition"), point("selected")),
        SourceAdapterDefinition,
        lambda d: d.adapter_type,
    )
    assert len(definitions) == 3
    assert tuple(definitions) == ("explicit", "unused", "selected")
    assert "unused" in definitions
    assert "absent" not in definitions
    assert definitions.origin("explicit") is None
    assert "unknown distribution" in str(definitions.origin("selected"))
    assert definitions["explicit"].adapter_type == "explicit"
    assert definitions["selected"] is definition
    monkeypatch.delitem(sys.modules, "fixture_provider")
    assert definitions["selected"] is definition
    assert tuple(definitions) == ("explicit", "unused", "selected")
    with pytest.raises(KeyError):
        definitions["absent"]


@pytest.mark.parametrize("duplicate", ("direct", "external", "custom"))
def test_duplicates_are_rejected_before_any_export_is_loaded(
    monkeypatch: pytest.MonkeyPatch, duplicate: str
) -> None:
    points = [point(duplicate, "missing_optional:definition")]
    if duplicate == "external":
        points.append(point(duplicate, "another_missing:definition"))
    install_metadata(monkeypatch, *points)
    # Real distribution attribution is retained without invoking its export.
    monkeypatch.setattr(
        metadata.EntryPoint, "dist", metadata.distribution("rhinestone")
    )
    definitions = (
        (SourceAdapterDefinition("custom", custom_source),)
        if duplicate == "custom"
        else ()
    )
    with pytest.raises(AdapterDiscoveryError, match="Duplicate.*rhinestone"):
        configure(adapters=definitions)


def test_empty_identity_is_rejected_from_metadata() -> None:
    with pytest.raises(AdapterDiscoveryError, match="Empty adapter identity"):
        index(point(" "))


def test_selected_import_error_is_distinct_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_metadata(monkeypatch, point("broken", "missing_optional:definition"))
    configure()  # The unused broken package does not affect normal setup.
    with pytest.raises(AdapterLoadError, match="broken") as error:
        configure(catalog=Catalog((Provider("chosen", "broken"),)))
    assert error.value.__suppress_context__
    assert isinstance(error.value, AdapterRegistrationError)


@pytest.mark.parametrize(
    "value", (object(), SourceAdapterDefinition("wrong", custom_source))
)
def test_selected_export_contract_and_identity_are_checked(
    monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    install_metadata(monkeypatch, point("selected"))
    export(monkeypatch, value)
    with pytest.raises(AdapterContractError, match="selected"):
        configure(catalog=Catalog((Provider("chosen", "selected"),)))


def test_selected_factory_error_is_distinct_and_does_not_expose_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory(provider: Any, context: Any) -> Any:
        raise ValueError("secret-in-factory")

    install_metadata(monkeypatch, point("selected"))
    export(monkeypatch, SourceAdapterDefinition("selected", factory))
    with pytest.raises(AdapterFactoryError, match="selected") as error:
        configure(catalog=Catalog((Provider("chosen", "selected"),)))
    assert "secret-in-factory" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("installed", (False, True))
def test_all_provider_factories_require_the_same_load_contract(
    monkeypatch: pytest.MonkeyPatch, installed: bool
) -> None:
    definition = SourceAdapterDefinition("selected", lambda provider, context: object())  # type: ignore[arg-type]
    install_metadata(monkeypatch, *((point("selected"),) if installed else ()))
    export(monkeypatch, definition)
    with pytest.raises(AdapterContractError, match="implementing load"):
        configure(
            catalog=Catalog((Provider("chosen", "selected"),)),
            adapters=() if installed else (definition,),
        )


def test_installed_provider_uses_the_public_pipeline_and_instance_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made: list[str] = []

    class Searchable:
        search_conditions = frozenset({"text", "limit"})

        def __init__(self, provider: Any, context: Any) -> None:
            self.inner = custom_source(provider, context)

        def load(self, reference: Reference) -> Any:
            return self.inner.load(reference)

        def search(self, query: SearchQuery) -> Any:
            return (self.load(Reference("selected", parameters={"title": query.text})),)

    def factory(provider: Any, context: Any) -> Any:
        made.append(provider.id)
        return Searchable(provider, context)

    install_metadata(
        monkeypatch, point("selected"), point("unused", "missing:definition")
    )
    export(monkeypatch, SourceAdapterDefinition("selected", factory))
    catalog = Catalog((Provider("chosen", "selected"),))
    first, second = configure(catalog=catalog), configure(catalog=catalog)
    assert made == ["chosen", "chosen"]
    assert first is not second
    resource = first.search(text="Installed")["chosen"][0]
    assert resource.reference.provider_id == "chosen"
    assert resource.metadata.title == "Installed"
    assert first.load(resource.reference).uri == resource.uri
    assert resource.access_plan is not None
    plan = AccessPlan.from_dict(json.loads(json.dumps(first.plan(resource).to_dict())))
    # Independent receiver uses no selected Provider or source metadata.
    receiver = configure(
        catalog=Catalog((Provider("file", "direct", {"uri": resource.uri}),)),
        adapters=(
            ExecutionAdapterDefinition(
                "custom-runtime", lambda context: CustomExecution()
            ),
        ),
    )

    def open_uri(uri: str) -> str:
        return uri

    runtime = SimpleNamespace(open=open_uri)
    assert receiver.open(plan, "custom-runtime", runtime=runtime) == resource.uri
    assert made == ["chosen", "chosen"]
