"""Built-in adapters consume public service contracts, not registry internals."""

import json
from collections.abc import Mapping
from typing import Any

import pytest

from rhinestone import Reference
from rhinestone.adapters.execution.json_service import JsonServiceAdapter
from rhinestone.adapters.execution.json_service.odpt import prepare_odpt_request
from rhinestone.adapters.knowledge import (
    AdministrativeArea,
    KnowledgeKind,
    MunicipalityIdentity,
    StandardTimeAdapter,
    TimeKind,
    TimeSemantic,
)
from rhinestone.adapters.source.estat_gis import EstatGisAdapter
from rhinestone.adapters.source.gsi_fundamental import GsiFundamentalAdapter
from rhinestone.adapters.source.plateau import PlateauAdapter
from rhinestone.models import AccessPlan
from rhinestone.security import DestinationPolicy
from tests.test_adapter_expansion import (
    fundamental_settings,
    odpt_adapter,
    plateau_client,
)
from tests.test_knowledge import OfficialMunicipalityAdapter


class ExternalKnowledge:
    """Application-owned service with no registry storage or inheritance."""

    available: tuple[KnowledgeKind, ...] = ("identity", "time")

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, TimeKind | None]] = []

    def __bool__(self) -> bool:
        return False

    def adapter_type(self, kind: KnowledgeKind) -> str:
        return "external-" + kind

    def resolve_area(self, value: str) -> AdministrativeArea:
        raise AssertionError("These providers do not request area knowledge")

    def resolve_municipality(self, value: str) -> MunicipalityIdentity:
        self.calls.append(("identity", value, None))
        return OfficialMunicipalityAdapter().resolve_municipality(value)

    def resolve_time(self, value: str, *, kind: TimeKind | None = None) -> TimeSemantic:
        self.calls.append(("time", value, kind))
        return StandardTimeAdapter().resolve_time(value, kind=kind)


@pytest.mark.parametrize("provider", ("plateau", "gsi-fundamental", "estat-gis"))
def test_providers_preserve_an_injected_falsey_knowledge_port(provider: str) -> None:
    knowledge = ExternalKnowledge()
    if provider == "plateau":
        adapter = PlateauAdapter(
            plateau_client, endpoint="https://fixture.example", knowledge=knowledge
        )
        settings: dict[str, Any] = {"resource_id": "citygml"}
    elif provider == "gsi-fundamental":
        adapter = GsiFundamentalAdapter(knowledge=knowledge)
        settings = fundamental_settings()
    else:
        adapter = EstatGisAdapter(
            (
                {
                    "distribution_id": "yokohama-2020",
                    "dataset_id": "census-2020",
                    "boundary_kind": "small-area",
                    "survey_year": 2020,
                    "level": "municipality",
                    "region_code": "14100",
                    "format": "gml",
                    "uri": "https://fixture.example/boundaries.gml",
                },
            ),
            knowledge=knowledge,
        )
        settings = {"distribution_id": "yokohama-2020"}
    # e-Stat accepts time selectors; PLATEAU/GSI also resolve municipality.
    settings.update({"time": "2020年", "time_kind": "survey_year"})
    if provider != "estat-gis":
        settings["municipality"] = "横浜市"
    resource = adapter.load(Reference(provider, parameters=settings))
    assert resource.metadata.raw["knowledge"]["time"]["kind"] == "survey_year"
    assert knowledge.calls[-1] == ("time", "2020年", "survey_year")
    if provider != "estat-gis":
        assert knowledge.calls[0] == ("identity", "横浜市", None)
        assert resource.metadata.raw["knowledge"]["identity"]["code"] == "14100"
    assert resource.access_plan is not None
    assert resource.access_plan.uri == resource.uri


class ExternalCredentials:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __bool__(self) -> bool:
        return False

    def get(self, name: str) -> str:
        self.calls.append(name)
        return "request-only-secret"


def test_odpt_execution_uses_a_credential_port_after_plan_json_transfer() -> None:
    resource = odpt_adapter().load(
        Reference(
            "odpt",
            parameters={
                "dataset": "station",
                "credential": "key",
                "filters": {"dc:title": "東京"},
            },
        )
    )
    assert resource.access_plan is not None
    serialized = json.dumps(resource.access_plan.to_dict())
    plan = AccessPlan.from_dict(json.loads(serialized))
    credentials = ExternalCredentials()
    adapter = JsonServiceAdapter(
        prepare_odpt_request,
        "odpt",
        credentials,
        DestinationPolicy.unrestricted(),
    )
    calls: list[Mapping[str, Any]] = []

    class Response:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> list[Mapping[str, str]]:
            return [{"dc:title": "東京"}]

    class Runtime:
        def get(self, uri: str, **kwargs: Any) -> Response:
            assert credentials.calls == ["key"]
            assert uri == plan.uri
            calls.append(kwargs)
            return Response()

    assert credentials.calls == []
    assert adapter.open(plan, Runtime()) == [{"dc:title": "東京"}]
    assert calls[0]["params"] == {
        "dc:title": "東京",
        "acl:consumerKey": "request-only-secret",
    }
    assert calls[0]["allow_redirects"] is False
    assert "request-only-secret" not in json.dumps(plan.to_dict())
    assert "request-only-secret" not in repr(resource)
