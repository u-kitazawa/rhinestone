"""Knowledge discovery never implicitly changes an application's interpretation."""

from typing import Any

import pytest

from rhinestone import Catalog, Provider, Rhinestone, configure
from rhinestone._entry_points import (
    KNOWLEDGE_GROUP,  # pyright: ignore[reportPrivateUsage]
)
from rhinestone.adapters.contracts import SourceAdapterDefinition
from rhinestone.adapters.knowledge import (
    KnowledgeAdapterDefinition,
    KnowledgePort,
    StandardTimeAdapter,
    TimeKind,
    TimeSemantic,
)
from rhinestone.errors import (
    AdapterContractError,
    AdapterDiscoveryError,
    AdapterFactoryError,
    AdapterLoadError,
    AdapterRegistrationError,
    ConfigValidationError,
    KnowledgeAdapterUnavailableError,
)
from tests.test_custom_adapters import custom_source
from tests.test_entry_points import export, install_metadata, point


def configured(**kwargs: Any) -> tuple[Rhinestone, KnowledgePort]:
    seen: list[KnowledgePort] = []

    def factory(provider: Any, context: Any) -> Any:
        seen.append(context.knowledge)
        return custom_source(provider, context)

    definitions = tuple(kwargs.pop("adapters", ()))
    app = configure(
        catalog=Catalog((Provider("capture", "capture"),)),
        adapters=(SourceAdapterDefinition("capture", factory), *definitions),
        **kwargs,
    )
    return app, seen[0]


class SelectedTime:
    def resolve_time(self, value: str, *, kind: TimeKind | None = None) -> TimeSemantic:
        return TimeSemantic("calendar_year", year=2099, raw=value)


def test_unselected_knowledge_exports_and_registered_candidates_do_not_replace_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_metadata(
        monkeypatch, point("broken", "missing:definition", group=KNOWLEDGE_GROUP)
    )
    definitions = (
        KnowledgeAdapterDefinition("first", lambda context: SelectedTime(), "time"),
        KnowledgeAdapterDefinition("second", lambda context: SelectedTime(), "time"),
    )
    _, knowledge = configured(adapters=definitions)
    assert knowledge.adapter_type("time") == "standard-time"
    assert knowledge.resolve_time("2020").year == 2020
    assert knowledge.adapter_type("area") == "japan-administrative-area"
    assert knowledge.available == ("area", "time")
    with pytest.raises(KnowledgeAdapterUnavailableError):
        knowledge.resolve_municipality("14100")


def test_explicit_choice_is_independent_of_registration_order() -> None:
    definitions = (
        KnowledgeAdapterDefinition("first", lambda context: SelectedTime(), "time"),
        KnowledgeAdapterDefinition(
            "second", lambda context: StandardTimeAdapter(), "time"
        ),
    )
    for order in (definitions, tuple(reversed(definitions))):
        _, knowledge = configured(adapters=order, knowledge={"time": "first"})
        assert knowledge.adapter_type("time") == "first"
        assert knowledge.resolve_time("2020").year == 2099


def test_selected_installed_knowledge_loads_its_factory_only_on_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def factory(context: Any) -> SelectedTime:
        assert context.dependencies.available == frozenset({"selected-data"})
        assert context.dependencies.get("selected-data") == "lookup"
        calls.append("factory")
        return SelectedTime()

    install_metadata(monkeypatch, point("external-time", group=KNOWLEDGE_GROUP))
    export(
        monkeypatch,
        KnowledgeAdapterDefinition(
            "external-time", factory, "time", frozenset({"selected-data"})
        ),
    )
    options = {
        "knowledge": {"time": "external-time"},
        "dependencies": {"selected-data": "lookup", "unrelated": object()},
    }
    _, first = configured(**options)
    _, second = configured(**options)
    assert calls == []
    assert first.resolve_time("2020").year == 2099
    assert first.resolve_time("2021").year == 2099
    assert calls == ["factory"]
    assert second.resolve_time("2020").year == 2099
    assert calls == ["factory", "factory"]


@pytest.mark.parametrize(
    "selection", ([], "time", {"unknown": "one"}, {"time": ""}, {"time": 1})
)
def test_invalid_selection_is_rejected(selection: Any) -> None:
    with pytest.raises(ConfigValidationError):
        configure(knowledge=selection)


def test_missing_selected_identity_is_a_configuration_error() -> None:
    with pytest.raises(KnowledgeAdapterUnavailableError, match="absent"):
        configure(knowledge={"time": "absent"})


@pytest.mark.parametrize("identity", ("standard-time", "custom"))
def test_knowledge_collision_is_rejected_before_import(
    monkeypatch: pytest.MonkeyPatch, identity: str
) -> None:
    install_metadata(
        monkeypatch, point(identity, "missing:definition", group=KNOWLEDGE_GROUP)
    )
    definitions = (
        (KnowledgeAdapterDefinition("custom", lambda context: SelectedTime(), "time"),)
        if identity == "custom"
        else ()
    )
    with pytest.raises(AdapterDiscoveryError, match=identity):
        configure(adapters=definitions)


def test_builtin_knowledge_identity_cannot_be_overwritten_by_explicit_registration() -> (
    None
):
    with pytest.raises(AdapterRegistrationError, match="standard-time"):
        configure(
            adapters=(
                KnowledgeAdapterDefinition(
                    "standard-time", lambda context: SelectedTime(), "time"
                ),
            )
        )


def test_selected_knowledge_import_failure_is_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_metadata(
        monkeypatch, point("broken", "missing:definition", group=KNOWLEDGE_GROUP)
    )
    with pytest.raises(AdapterLoadError, match="broken"):
        configure(knowledge={"time": "broken"})


@pytest.mark.parametrize(
    "definition",
    (
        object(),
        KnowledgeAdapterDefinition("wrong", lambda context: SelectedTime(), "time"),
        KnowledgeAdapterDefinition("selected", lambda context: SelectedTime(), "area"),
    ),
)
def test_selected_knowledge_export_identity_and_kind_are_checked(
    monkeypatch: pytest.MonkeyPatch, definition: object
) -> None:
    install_metadata(monkeypatch, point("selected", group=KNOWLEDGE_GROUP))
    export(monkeypatch, definition)
    with pytest.raises(AdapterContractError, match="selected"):
        configure(knowledge={"time": "selected"})


def test_installed_knowledge_factory_error_does_not_expose_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory(context: Any) -> Any:
        raise ValueError("factory-secret")

    install_metadata(monkeypatch, point("selected", group=KNOWLEDGE_GROUP))
    export(monkeypatch, KnowledgeAdapterDefinition("selected", factory, "time"))
    _, knowledge = configured(knowledge={"time": "selected"})
    with pytest.raises(AdapterFactoryError, match="selected") as error:
        knowledge.resolve_time("2020")
    assert "factory-secret" not in str(error.value)
    assert error.value.__suppress_context__


def test_installed_knowledge_factory_must_implement_its_kind_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_factory(context: Any) -> Any:
        return object()

    install_metadata(monkeypatch, point("selected", group=KNOWLEDGE_GROUP))
    export(
        monkeypatch,
        KnowledgeAdapterDefinition("selected", invalid_factory, "time"),
    )
    _, knowledge = configured(knowledge={"time": "selected"})
    with pytest.raises(AdapterContractError, match="resolve_time"):
        knowledge.resolve_time("2020")
