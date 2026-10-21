"""Explicit Runtime names select installed adapters without touching siblings."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from rhinestone import Catalog, Provider, configure
from rhinestone._entry_points import (
    RUNTIME_GROUP,  # pyright: ignore[reportPrivateUsage]
)
from rhinestone._runtime_adapters import (
    RuntimeInstances,  # pyright: ignore[reportPrivateUsage]
)
from rhinestone.adapters.contracts import RuntimeAdapterDefinition
from rhinestone.errors import (
    AdapterContractError,
    AdapterDiscoveryError,
    AdapterFactoryError,
    AdapterLoadError,
    ConfigValidationError,
    RuntimeAdapterUnavailableError,
)
from rhinestone.models import AccessPlan
from rhinestone.registry import AdapterRegistry
from rhinestone.security import DestinationPolicy
from tests.test_custom_adapters import CustomExecution
from tests.test_entry_points import export, install_metadata, point


def plan() -> AccessPlan:
    return AccessPlan(
        kind="file", uri="https://data.example/selected.bin", format="custom"
    )


def app() -> Any:
    return configure(
        catalog=Catalog((Provider("file", "direct", {"uri": plan().uri}),))
    )


def runtime() -> object:
    def open_uri(uri: str) -> str:
        return uri

    return SimpleNamespace(open=open_uri)


def test_installed_runtime_is_loaded_only_when_its_name_is_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made: list[str] = []

    def factory(context: Any) -> CustomExecution:
        made.append("factory")
        return CustomExecution()

    install_metadata(
        monkeypatch,
        point("custom-runtime", group=RUNTIME_GROUP),
        point("unused", "missing_optional:definition", group=RUNTIME_GROUP),
    )
    export(monkeypatch, RuntimeAdapterDefinition("custom-runtime", factory))
    first, second = app(), app()
    assert made == []
    with pytest.raises(RuntimeAdapterUnavailableError, match="unknown"):
        first.open(plan(), "unknown", runtime=runtime())
    assert made == []
    assert first.open(plan(), "custom-runtime", runtime=runtime()) == plan().uri
    assert first.open(plan(), "custom-runtime", runtime=runtime()) == plan().uri
    assert made == ["factory"]
    assert second.open(plan(), "custom-runtime", runtime=runtime()) == plan().uri
    assert made == ["factory", "factory"]
    with pytest.raises(AdapterLoadError, match="unused"):
        first.open(plan(), "unused", runtime=runtime())


@pytest.mark.parametrize("name", ("gdal", "custom-runtime"))
def test_runtime_metadata_collision_is_rejected_before_load(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    install_metadata(
        monkeypatch, point(name, "missing:definition", group=RUNTIME_GROUP)
    )
    custom = (
        (RuntimeAdapterDefinition(name, lambda context: CustomExecution()),)
        if name == "custom-runtime"
        else ()
    )
    with pytest.raises(AdapterDiscoveryError, match=name):
        configure(adapters=custom)


@pytest.mark.parametrize(
    "definition",
    (object(), RuntimeAdapterDefinition("wrong", lambda context: CustomExecution())),
)
def test_runtime_export_contract_is_checked_on_selection(
    monkeypatch: pytest.MonkeyPatch, definition: object
) -> None:
    install_metadata(monkeypatch, point("selected", group=RUNTIME_GROUP))
    export(monkeypatch, definition)
    configured = app()
    with pytest.raises(AdapterContractError, match="selected"):
        configured.open(plan(), "selected", runtime=runtime())


def test_runtime_factory_failure_is_classified_without_its_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory(context: Any) -> Any:
        raise ValueError("factory-secret")

    install_metadata(monkeypatch, point("selected", group=RUNTIME_GROUP))
    export(monkeypatch, RuntimeAdapterDefinition("selected", factory))
    configured = app()
    with pytest.raises(AdapterFactoryError, match="selected") as error:
        configured.open(plan(), "selected", runtime=runtime())
    assert "factory-secret" not in str(error.value)
    assert error.value.__suppress_context__


def test_explicit_runtime_factory_retains_its_existing_error_boundary() -> None:
    def factory(context: Any) -> Any:
        raise ValueError("application factory failed")

    with pytest.raises(ValueError, match="application factory failed"):
        configure(adapters=(RuntimeAdapterDefinition("explicit", factory),))


def test_incompatible_installed_runtime_does_not_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_metadata(monkeypatch, point("custom-runtime", group=RUNTIME_GROUP))
    export(
        monkeypatch,
        RuntimeAdapterDefinition("custom-runtime", lambda context: CustomExecution()),
    )
    incompatible = AccessPlan(kind="file", uri=plan().uri, format="geotiff")
    with pytest.raises(RuntimeAdapterUnavailableError, match="custom-runtime"):
        app().open(incompatible, "custom-runtime", runtime=runtime())


@pytest.mark.parametrize(
    "value",
    (
        object(),
        SimpleNamespace(
            name="selected", priority=True, supports=object(), open=object()
        ),
    ),
)
def test_runtime_factory_result_contract_is_checked(
    monkeypatch: pytest.MonkeyPatch, value: Any
) -> None:
    install_metadata(monkeypatch, point("selected", group=RUNTIME_GROUP))
    export(monkeypatch, RuntimeAdapterDefinition("selected", lambda context: value))
    with pytest.raises(AdapterContractError):
        app().open(plan(), "selected", runtime=runtime())


def test_installed_runtime_name_cannot_be_injected_as_a_provider_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_metadata(
        monkeypatch, point("selected", "missing:definition", group=RUNTIME_GROUP)
    )
    with pytest.raises(ConfigValidationError, match="selected"):
        configure(dependencies={"selected": object()})


def test_selected_runtime_keeps_pre_open_authorization_and_json_plan_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Authorizing(CustomExecution):
        def authorize(
            self,
            value: AccessPlan,
            *,
            destination_policy: DestinationPolicy | None = None,
        ) -> None:
            assert destination_policy is not None
            destination_policy.authorize_plan(value)
            calls.append("authorize")

        def open(
            self,
            plan: AccessPlan,
            runtime: Any,
            *,
            destination_policy: Any = None,
        ) -> Any:
            calls.append("open")
            return runtime.open(plan.uri)

    install_metadata(monkeypatch, point("custom-runtime", group=RUNTIME_GROUP))
    export(
        monkeypatch,
        RuntimeAdapterDefinition("custom-runtime", lambda context: Authorizing()),
    )
    transferred = AccessPlan.from_dict(json.loads(json.dumps(plan().to_dict())))
    configured = app()
    with pytest.raises(RuntimeAdapterUnavailableError, match="supplied as an object"):
        configured.open(transferred, "custom-runtime")
    assert calls == ["authorize"]
    assert (
        configured.open(transferred, "custom-runtime", runtime=runtime()) == plan().uri
    )
    assert calls == ["authorize", "authorize", "open"]


def test_instance_catalog_metadata_and_registry_access_are_lazy() -> None:
    built: list[str] = []
    definition = RuntimeAdapterDefinition(
        "custom-runtime", lambda context: CustomExecution()
    )

    def build(value: RuntimeAdapterDefinition) -> CustomExecution:
        built.append(value.name)
        return CustomExecution()

    catalog = RuntimeInstances({definition.name: definition}, build, {})
    registry = AdapterRegistry((), catalog)
    assert len(catalog) == 1
    assert tuple(registry.runtime_adapters) == ("custom-runtime",)
    assert "custom-runtime" in catalog
    assert built == []
    assert registry.runtime("custom-runtime").name == "custom-runtime"
    assert registry.runtime("custom-runtime").name == "custom-runtime"
    assert built == ["custom-runtime"]
