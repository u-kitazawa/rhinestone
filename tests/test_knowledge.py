from datetime import date
from pathlib import Path
from typing import Any, Mapping, cast

import pytest

from rhinestone import (
    Config,
    Provider,
    configure,
)
from rhinestone.adapters.contracts import SourceAdapterDefinition
from rhinestone.adapters.knowledge import (
    KnowledgeAdapterContext,
    KnowledgeAdapterDefinition,
    KnowledgeAdapterRegistry,
    MunicipalityIdentity,
    StandardTimeAdapter,
    TimeSemantic,
)
from rhinestone.adapters.source.gsi_fundamental import GsiFundamentalAdapter
from rhinestone.adapters.source.plateau import PlateauAdapter
from rhinestone.errors import (
    AdapterRegistrationError,
    ConfigValidationError,
    KnowledgeAdapterUnavailableError,
    KnowledgeResolutionError,
    KnowledgeValidationError,
)
from rhinestone.models import Metadata, Provenance, ResourceCandidate, Source
from rhinestone.registry import CredentialRegistry, DependencyRegistry
from rhinestone.security import DestinationPolicy
from tests.test_adapter_expansion import fundamental_settings, plateau_client


class OfficialMunicipalityAdapter:
    def resolve_municipality(self, value: str) -> MunicipalityIdentity:
        if value in {"横浜市", "14100"}:
            return MunicipalityIdentity(
                code="14100",
                name="横浜市",
                prefecture_code="14",
                prefecture_name="神奈川県",
                provider_identifiers={"plateau": "yokohama"},
            )
        raise KnowledgeResolutionError("municipality is unknown")


def knowledge_registry() -> KnowledgeAdapterRegistry:
    return KnowledgeAdapterRegistry(
        (
            KnowledgeAdapterDefinition(
                "official-municipality",
                lambda _context: OfficialMunicipalityAdapter(),
                "identity",
            ),
            KnowledgeAdapterDefinition(
                "standard-time", lambda _context: StandardTimeAdapter(), "time"
            ),
        ),
        knowledge_context(),
    )


def knowledge_context() -> KnowledgeAdapterContext:
    return KnowledgeAdapterContext(
        get_json=lambda *args: {},
        get_text=lambda uri: "",
        credentials=CredentialRegistry({}),
        dependencies=DependencyRegistry({}),
        destination_policy=DestinationPolicy.unrestricted(),
    )


def standard_time_factory(_context: KnowledgeAdapterContext) -> StandardTimeAdapter:
    return StandardTimeAdapter()


def object_factory(_context: KnowledgeAdapterContext) -> Any:
    return object()


def raising_factory(_context: KnowledgeAdapterContext) -> Any:
    raise RuntimeError("failure")


def test_municipality_identity_is_immutable_and_serializable() -> None:
    identity = MunicipalityIdentity(
        code="13101",
        name="千代田区",
        prefecture_code="13",
        prefecture_name="東京都",
        provider_identifiers={"example": "tokyo-01"},
    )

    assert identity.as_mapping() == {
        "code": "13101",
        "name": "千代田区",
        "prefecture_code": "13",
        "prefecture_name": "東京都",
        "level": "municipality",
        "provider_identifiers": {"example": "tokyo-01"},
    }
    with pytest.raises(TypeError):
        identity.provider_identifiers["example"] = "changed"  # type: ignore[index]


@pytest.mark.parametrize(
    "changes",
    (
        {"code": ""},
        {"name": ""},
        {"prefecture_code": ""},
        {"prefecture_name": ""},
        {"level": "ward"},
        {"provider_identifiers": []},
        {"provider_identifiers": {"": "value"}},
        {"provider_identifiers": {"provider": ""}},
    ),
)
def test_municipality_identity_rejects_invalid_values(
    changes: Mapping[str, Any],
) -> None:
    values: dict[str, Any] = {
        "code": "13101",
        "name": "千代田区",
        "prefecture_code": "13",
        "prefecture_name": "東京都",
    }
    values.update(changes)
    with pytest.raises(KnowledgeValidationError):
        MunicipalityIdentity(**values)  # type: ignore[arg-type]


def test_time_semantic_serializes_year_and_date_values() -> None:
    assert TimeSemantic("calendar_year", year=2024, raw="2024").as_mapping() == {
        "kind": "calendar_year",
        "year": 2024,
        "raw": "2024",
    }
    assert TimeSemantic(
        "as_of_date", as_of=date(2024, 1, 2), raw="2024-01-02"
    ).as_mapping() == {
        "kind": "as_of_date",
        "as_of": "2024-01-02",
        "raw": "2024-01-02",
    }
    assert (
        TimeSemantic(
            "calendar_year", year=2020, era="令和", era_year=2, raw="令和2年"
        ).as_mapping()["era_year"]
        == 2
    )


@pytest.mark.parametrize(
    "kwargs",
    (
        {"kind": "unknown", "raw": "x"},
        {"kind": "calendar_year", "raw": ""},
        {"kind": "calendar_year", "year": 0, "raw": "0"},
        {
            "kind": "calendar_year",
            "year": 2024,
            "as_of": date(2024, 1, 1),
            "raw": "2024",
        },
        {"kind": "as_of_date", "year": 2024, "as_of": date(2024, 1, 1), "raw": "2024"},
        {"kind": "calendar_year", "year": 2024, "era_year": 2, "raw": "2024"},
        {
            "kind": "fiscal_year",
            "year": 2024,
            "era": "令和",
            "era_year": 6,
            "raw": "2024年度",
        },
        {
            "kind": "calendar_year",
            "year": 2024,
            "era": "令和",
            "era_year": 0,
            "raw": "令和0年",
        },
    ),
)
def test_time_semantic_rejects_invalid_values(kwargs: Mapping[str, Any]) -> None:
    with pytest.raises(KnowledgeValidationError):
        TimeSemantic(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    (
        ("2024", None, {"kind": "calendar_year", "year": 2024}),
        ("2020年度", None, {"kind": "fiscal_year", "year": 2020}),
        ("2020年", "survey_year", {"kind": "survey_year", "year": 2020}),
        ("令和元年", None, {"kind": "calendar_year", "year": 2019, "era_year": 1}),
        (
            "令和元年5月1日",
            None,
            {"kind": "as_of_date", "as_of": date(2019, 5, 1), "era_year": 1},
        ),
        (
            "平成31年4月30日",
            None,
            {"kind": "as_of_date", "as_of": date(2019, 4, 30), "era_year": 31},
        ),
        ("2024-01-02", None, {"kind": "as_of_date", "as_of": date(2024, 1, 2)}),
    ),
)
def test_standard_time_adapter_resolves_explicit_values(
    value: str, kind: Any, expected: Mapping[str, Any]
) -> None:
    result = StandardTimeAdapter().resolve_time(value, kind=kind)
    for name, expected_value in expected.items():
        assert getattr(result, name) == expected_value


@pytest.mark.parametrize(
    "value",
    (
        "",
        "2024/01/02",
        "令和0年",
        "令和10000年",
        "2024年4月",
        "2024-02-30",
        "令和元年4月30日",
        "平成31年5月1日",
        "令和元年2月30日",
    ),
)
def test_standard_time_adapter_rejects_ambiguous_or_invalid_values(value: str) -> None:
    with pytest.raises(KnowledgeResolutionError):
        StandardTimeAdapter().resolve_time(value)


@pytest.mark.parametrize(
    ("value", "kind"),
    (
        ("令和2年", "fiscal_year"),
        ("2024年度", "calendar_year"),
        ("2024年", "fiscal_year"),
        ("2024-01-02", "survey_year"),
        ("2024", "as_of_date"),
        ("令和元年5月1日", "calendar_year"),
    ),
)
def test_standard_time_adapter_rejects_conflicting_kinds(value: str, kind: Any) -> None:
    with pytest.raises(KnowledgeResolutionError):
        StandardTimeAdapter().resolve_time(value, kind=kind)


def test_knowledge_registry_is_lazy_and_resolves_both_kinds() -> None:
    calls: list[str] = []

    def identity_factory(
        _context: KnowledgeAdapterContext,
    ) -> OfficialMunicipalityAdapter:
        calls.append("identity")
        return OfficialMunicipalityAdapter()

    registry = KnowledgeAdapterRegistry(
        (
            KnowledgeAdapterDefinition("official", identity_factory, "identity"),
            KnowledgeAdapterDefinition("standard", standard_time_factory, "time"),
        ),
        knowledge_context(),
    )
    assert registry.available == ("identity", "time")
    assert registry.adapter_type("identity") == "official"
    assert calls == []
    assert registry.resolve_municipality("横浜市").code == "14100"
    assert registry.resolve_municipality("14100").code == "14100"
    assert registry.resolve_time("令和2年").year == 2020
    assert calls == ["identity"]


def test_knowledge_registry_rejects_duplicates_and_missing_adapters() -> None:
    definition = KnowledgeAdapterDefinition("standard", standard_time_factory, "time")
    with pytest.raises(AdapterRegistrationError, match="time"):
        KnowledgeAdapterRegistry((definition, definition), knowledge_context())
    with pytest.raises(KnowledgeAdapterUnavailableError, match="identity"):
        KnowledgeAdapterRegistry().resolve_municipality("横浜市")
    with pytest.raises(KnowledgeAdapterUnavailableError, match="time"):
        KnowledgeAdapterRegistry().resolve_time("2024")


def test_knowledge_registry_requires_factory_context() -> None:
    registry = KnowledgeAdapterRegistry(
        (KnowledgeAdapterDefinition("standard", standard_time_factory, "time"),)
    )
    with pytest.raises(KnowledgeResolutionError, match="factory context"):
        registry.resolve_time("2024")


@pytest.mark.parametrize(
    "factory",
    (
        raising_factory,
        object_factory,
    ),
)
def test_knowledge_registry_rejects_failed_or_invalid_adapters(factory: Any) -> None:
    registry = KnowledgeAdapterRegistry(
        (KnowledgeAdapterDefinition("broken", factory, "identity"),),
        knowledge_context(),
    )
    with pytest.raises(KnowledgeResolutionError):
        registry.resolve_municipality("横浜市")


def test_knowledge_registry_rejects_wrong_time_adapter_shape() -> None:
    registry = KnowledgeAdapterRegistry(
        (KnowledgeAdapterDefinition("broken", object_factory, "time"),),
        knowledge_context(),
    )
    with pytest.raises(KnowledgeResolutionError, match="resolve_time"):
        registry.resolve_time("2024")


class InvalidIdentityAdapter:
    def resolve_municipality(self, value: str) -> object:
        return object()


class InvalidTimeAdapter:
    def resolve_time(self, value: str, *, kind: Any = None) -> object:
        return object()


def invalid_identity_factory(_context: KnowledgeAdapterContext) -> Any:
    return InvalidIdentityAdapter()


def invalid_time_factory(_context: KnowledgeAdapterContext) -> Any:
    return InvalidTimeAdapter()


def test_knowledge_registry_rejects_invalid_resolver_results() -> None:
    identity = KnowledgeAdapterRegistry(
        (
            KnowledgeAdapterDefinition(
                "broken",
                invalid_identity_factory,
                "identity",
            ),
        ),
        knowledge_context(),
    )
    with pytest.raises(KnowledgeResolutionError, match="invalid value"):
        identity.resolve_municipality("横浜市")

    time = KnowledgeAdapterRegistry(
        (
            KnowledgeAdapterDefinition(
                "broken",
                invalid_time_factory,
                "time",
            ),
        ),
        knowledge_context(),
    )
    with pytest.raises(KnowledgeResolutionError, match="invalid value"):
        time.resolve_time("2024")


def test_knowledge_registry_rejects_invalid_definition_values() -> None:
    with pytest.raises(ValueError):
        KnowledgeAdapterDefinition(
            "adapter",
            object_factory,
            "other",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        KnowledgeAdapterDefinition("", standard_time_factory, "time")
    with pytest.raises(ValueError):
        KnowledgeAdapterDefinition("adapter", cast(Any, None), "time")


def test_two_source_adapters_consume_the_same_knowledge_registry() -> None:
    registry = knowledge_registry()
    plateau = PlateauAdapter(
        plateau_client,
        endpoint="https://fixture.example",
        knowledge=registry,
    )
    plateau_source = plateau.load(
        Config(
            "plateau",
            {
                "dataset_id": "fixture",
                "municipality": "横浜市",
                "time": "2020年度",
            },
        )
    )
    plateau_knowledge = plateau_source.candidates[0].attributes["knowledge"]
    assert plateau_knowledge["identity"]["code"] == "14100"
    assert plateau_knowledge["time"]["kind"] == "fiscal_year"

    gsi = GsiFundamentalAdapter(knowledge=registry)
    settings = fundamental_settings()
    settings.update({"municipality": "14100", "time": "令和2年"})
    gsi_source = gsi.load(Config("gsi-fundamental", settings))
    gsi_knowledge = gsi_source.candidates[0].attributes["knowledge"]
    assert gsi_knowledge["identity"]["name"] == "横浜市"
    assert gsi_knowledge["time"]["year"] == 2020


def test_source_adapters_preserve_explicit_time_kind() -> None:
    registry = knowledge_registry()
    plateau_source = PlateauAdapter(
        plateau_client,
        endpoint="https://fixture.example",
        knowledge=registry,
    ).load(
        Config(
            "plateau",
            {
                "dataset_id": "fixture",
                "time": "2020年",
                "time_kind": "survey_year",
            },
        )
    )
    assert (
        plateau_source.candidates[0].attributes["knowledge"]["time"]["kind"]
        == "survey_year"
    )

    settings = fundamental_settings()
    settings.update({"time": "2020", "time_kind": "survey_year"})
    gsi_source = GsiFundamentalAdapter(knowledge=registry).load(
        Config("gsi-fundamental", settings)
    )
    assert (
        gsi_source.candidates[0].attributes["knowledge"]["time"]["kind"]
        == "survey_year"
    )


def test_source_knowledge_rejects_unknown_time_kind() -> None:
    from rhinestone.adapters.source._knowledge import resolve_knowledge

    with pytest.raises(ConfigValidationError, match="time_kind"):
        resolve_knowledge(
            {"time": "2020", "time_kind": "unknown"}, knowledge_registry()
        )


def test_knowledge_factory_is_not_loaded_until_source_uses_it() -> None:
    calls: list[str] = []

    def identity_factory(
        _context: KnowledgeAdapterContext,
    ) -> OfficialMunicipalityAdapter:
        calls.append("identity")
        return OfficialMunicipalityAdapter()

    app = configure(
        adapters=(
            KnowledgeAdapterDefinition("official", identity_factory, "identity"),
        ),
    )
    app.resolve(Config("direct", {"uri": str(Path("/tmp/data.csv")), "format": "csv"}))
    assert calls == []


def test_public_source_context_receives_the_shared_knowledge_registry() -> None:
    seen: list[KnowledgeAdapterRegistry] = []

    def source_factory(provider: Provider, context: Any) -> Any:
        seen.append(context.knowledge)

        class Adapter:
            def load(self, config: Config) -> Source:
                candidate = ResourceCandidate("/data.csv", "csv", "text/csv")
                return Source(
                    metadata=Metadata(raw={}),
                    candidates=(candidate,),
                    capabilities=frozenset({"file"}),
                    provenance=Provenance(provider=provider.id, raw={}),
                    raw_metadata={},
                )

        return Adapter()

    registry_definition = KnowledgeAdapterDefinition(
        "standard", standard_time_factory, "time"
    )
    app = configure(
        sources=(Provider("custom", "custom-knowledge"),),
        adapters=(
            SourceAdapterDefinition("custom-knowledge", source_factory),
            registry_definition,
        ),
    )
    app.resolve(Config("custom", {}))
    assert len(seen) == 1
    assert seen[0].available == ("time",)


def test_public_builtin_source_receives_knowledge_adapters() -> None:
    settings = fundamental_settings()
    settings.update({"municipality": "14100", "time": "令和2年"})
    app = configure(
        sources=(Provider("fundamental", "gsi-fundamental"),),
        adapters=(
            KnowledgeAdapterDefinition(
                "official", lambda _context: OfficialMunicipalityAdapter(), "identity"
            ),
            KnowledgeAdapterDefinition("standard", standard_time_factory, "time"),
        ),
    )

    resource = app.resolve(Config("fundamental", settings))

    assert (
        resource.source.candidates[0].attributes["knowledge"]["identity"]["code"]
        == "14100"
    )


def test_public_application_auto_registers_standard_time_adapter() -> None:
    settings = fundamental_settings()
    settings["time"] = "令和2年"
    app = configure(
        sources=(Provider("fundamental", "gsi-fundamental"),),
    )

    resource = app.resolve(Config("fundamental", settings))

    assert resource.source.candidates[0].attributes["knowledge"]["time"] == {
        "kind": "calendar_year",
        "year": 2020,
        "era": "令和",
        "era_year": 2,
        "raw": "令和2年",
    }


def test_custom_time_definition_replaces_the_preinstalled_adapter() -> None:
    class CustomTimeAdapter:
        def resolve_time(self, value: str, *, kind: Any = None) -> TimeSemantic:
            return TimeSemantic("calendar_year", year=2099, raw=value)

    app = configure(
        sources=(Provider("fundamental", "gsi-fundamental"),),
        adapters=(
            KnowledgeAdapterDefinition(
                "custom-time", lambda _context: CustomTimeAdapter(), "time"
            ),
        ),
    )
    settings = fundamental_settings()
    settings["time"] = "任意の時点"

    resource = app.resolve(Config("fundamental", settings))

    assert resource.source.candidates[0].attributes["knowledge"]["time"]["year"] == 2099


def test_public_knowledge_definitions_reject_duplicate_kinds() -> None:
    definition = KnowledgeAdapterDefinition(
        "custom-time", standard_time_factory, "time"
    )

    with pytest.raises(AdapterRegistrationError, match="time"):
        configure(adapters=(definition, definition))
