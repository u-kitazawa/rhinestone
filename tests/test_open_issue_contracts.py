from typing import Any, Mapping, Optional, cast

import pytest

from rhinestone import Config, Provider, configure
from rhinestone.adapters.contracts import SourceAdapterDefinition
from rhinestone.adapters.knowledge import (
    CRS84,
    AreaCode,
    BoundingBox,
    CRSRef,
    MeshCode,
    MunicipalityIdentity,
    MunicipalityRecord,
    StandardTimeAdapter,
    StaticMunicipalityAdapter,
    require_lossless_crs84,
)
from rhinestone.adapters.source.estat_gis import EstatGisAdapter
from rhinestone.errors import (
    AmbiguousResourceError,
    ConfigValidationError,
    KnowledgeResolutionError,
    KnowledgeValidationError,
    ProviderMetadataError,
    ResourceNotFoundError,
    UnsupportedSearchConditionError,
)
from rhinestone.models import SearchQuery


def municipality_records() -> tuple[MunicipalityRecord, ...]:
    return (
        MunicipalityRecord(
            MunicipalityIdentity(
                code="13101",
                name="千代田区",
                prefecture_code="13",
                prefecture_name="東京都",
                provider_identifiers={"plateau": "13101-tokyo"},
            ),
            codes=(AreaCode("japan-standard-area-code", "13101"),),
            aliases=("千代田区",),
        ),
        MunicipalityRecord(
            MunicipalityIdentity(
                code="14100",
                name="中央区",
                prefecture_code="14",
                prefecture_name="神奈川県",
                provider_identifiers={"plateau": "14100-yokohama"},
            ),
            codes=(AreaCode("japan-standard-area-code", "14100"),),
        ),
    )


def test_snapshot_municipality_resolver_is_strict_and_projects_one_way() -> None:
    adapter = StaticMunicipalityAdapter(
        municipality_records(), snapshot_version="2026-01-01"
    )

    identity = adapter.resolve_municipality("13101")
    assert identity.name == "千代田区"
    assert adapter.resolve_municipality("千代田区") == identity
    assert adapter.project(identity, "plateau") == "13101-tokyo"
    assert adapter.evidence() == {"snapshot_version": "2026-01-01"}

    with pytest.raises(KnowledgeResolutionError, match="unknown"):
        adapter.resolve_municipality("99999")
    with pytest.raises(KnowledgeResolutionError, match="invalid"):
        adapter.resolve_municipality("1310")
    with pytest.raises(KnowledgeResolutionError, match="unsupported"):
        adapter.project(identity, "estat-gis")


@pytest.mark.parametrize(
    "factory",
    (
        lambda: AreaCode("", "1"),
        lambda: AreaCode(" scheme", "1"),
        lambda: AreaCode("scheme", ""),
        lambda: AreaCode("scheme", "1a"),
        lambda: AreaCode("japan-standard-area-code", "１３"),
        lambda: AreaCode("japan-standard-area-code", "1310"),
    ),
)
def test_municipality_value_validation_is_fail_closed(factory: Any) -> None:
    with pytest.raises(KnowledgeValidationError):
        factory()


def test_municipality_snapshot_validation_and_lookup_errors() -> None:
    with pytest.raises(KnowledgeValidationError):
        MunicipalityRecord(None)  # type: ignore[arg-type]
    with pytest.raises(KnowledgeValidationError):
        MunicipalityRecord(municipality_records()[0].identity, codes=(None,))  # type: ignore[arg-type]
    with pytest.raises(KnowledgeValidationError, match="identity level"):
        MunicipalityRecord(
            municipality_records()[0].identity,
            codes=(AreaCode("japan-standard-area-code", "13"),),
        )
    with pytest.raises(KnowledgeValidationError, match="identity level"):
        MunicipalityRecord(
            MunicipalityIdentity("13", "東京都", "13", "東京都", level="prefecture"),
            codes=(AreaCode("japan-standard-area-code", "13101"),),
        )
    with pytest.raises(KnowledgeValidationError):
        MunicipalityRecord(municipality_records()[0].identity, aliases=(None,))  # type: ignore[arg-type]
    with pytest.raises(KnowledgeValidationError):
        MunicipalityRecord(
            municipality_records()[0].identity,
            provider_identifiers=cast(Any, {"x": None}),
        )
    with pytest.raises(KnowledgeValidationError, match="mapping"):
        MunicipalityRecord(
            municipality_records()[0].identity,
            provider_identifiers=cast(Any, []),
        )
    merged = MunicipalityRecord(
        municipality_records()[0].identity,
        provider_identifiers={"other": "external-13101"},
    )
    assert merged.provider_identifiers == {
        "plateau": "13101-tokyo",
        "other": "external-13101",
    }
    with pytest.raises(KnowledgeValidationError, match="conflict"):
        MunicipalityRecord(
            municipality_records()[0].identity,
            provider_identifiers={"plateau": "different-13101"},
        )
    with pytest.raises(KnowledgeValidationError):
        StaticMunicipalityAdapter((), snapshot_version="v1")
    with pytest.raises(KnowledgeValidationError):
        StaticMunicipalityAdapter(municipality_records(), snapshot_version=" ")

    adapter = StaticMunicipalityAdapter(municipality_records(), snapshot_version="v1")
    for value, message in (
        ("", "non-empty"),
        ("1310", "invalid"),
        ("unknown", "unknown"),
    ):
        with pytest.raises(KnowledgeResolutionError, match=message):
            adapter.resolve_municipality(value)
    with pytest.raises(KnowledgeResolutionError, match="invalid"):
        adapter.project(None, "plateau")  # type: ignore[arg-type]
    with pytest.raises(KnowledgeResolutionError, match="unsupported"):
        adapter.project(municipality_records()[0].identity, "estat-gis")
    with pytest.raises(KnowledgeResolutionError, match="unsupported"):
        adapter.project(
            MunicipalityIdentity("99999", "未登録", "99", "未登録県"), "plateau"
        )
    independent = StaticMunicipalityAdapter(
        (
            MunicipalityRecord(
                MunicipalityIdentity("01101", "中央区", "01", "北海道"),
                provider_identifiers={"provider": "external-01101"},
            ),
        ),
        snapshot_version="v2",
    )
    assert (
        independent.project(
            MunicipalityIdentity("01101", "中央区", "01", "北海道"), "provider"
        )
        == "external-01101"
    )


def test_duplicate_names_are_ambiguous_and_duplicate_codes_rejected() -> None:
    first = municipality_records()[0]
    second = MunicipalityRecord(
        MunicipalityIdentity(
            code="27101",
            name="千代田区",
            prefecture_code="27",
            prefecture_name="大阪府",
        )
    )
    adapter = StaticMunicipalityAdapter((first, second), snapshot_version="v1")
    with pytest.raises(KnowledgeResolutionError, match="ambiguous"):
        adapter.resolve_municipality("千代田区")

    duplicate = MunicipalityRecord(
        MunicipalityIdentity(
            code="13102",
            name="別の区",
            prefecture_code="13",
            prefecture_name="東京都",
        ),
        codes=(AreaCode("japan-standard-area-code", "13101"),),
    )
    with pytest.raises(KnowledgeValidationError, match="duplicate"):
        StaticMunicipalityAdapter((first, duplicate), snapshot_version="v1")


def test_bbox_is_a_separate_explicit_space_value() -> None:
    assert BoundingBox(139, 35, 140, 36).as_tuple() == (139, 35, 140, 36)
    assert BoundingBox(139, 35, 140, 36, CRS84).crs == CRS84


def test_space_values_fail_closed_without_reprojection() -> None:
    with pytest.raises(KnowledgeValidationError, match="antimeridian"):
        BoundingBox(170, -10, -170, 10)
    with pytest.raises(KnowledgeValidationError):
        BoundingBox(139, 35, 140, 91)
    with pytest.raises(KnowledgeResolutionError, match="unsupported"):
        require_lossless_crs84(BoundingBox(1, 2, 3, 4, CRSRef("EPSG", "6677")))
    assert require_lossless_crs84(BoundingBox(1, 2, 3, 4)) == (1, 2, 3, 4)
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", 3, "5339")
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", True, "5339")  # type: ignore[arg-type]
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", 1.0, "5339")  # type: ignore[arg-type]
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", 1, "５３３９")
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", 2, "533988")
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", 3, "53398800")
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", 4, "533945679")
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", 5, "5339456791")
    with pytest.raises(KnowledgeValidationError):
        MeshCode("JIS-X-0410", 6, "53394567129")
    assert MeshCode("JIS-X-0410", 3, "53394567").code == "53394567"
    assert tuple(BoundingBox(139, 35, 140, 36)) == (139, 35, 140, 36)


@pytest.mark.parametrize(
    "factory",
    (
        lambda: CRSRef.parse("EPSG"),
        lambda: CRSRef.parse("EPSG:6677:extra"),
        lambda: CRSRef("1EPSG", "6677"),
        lambda: CRSRef("EPSG", ""),
        lambda: BoundingBox(True, 1, 2, 3),
        lambda: BoundingBox(float("inf"), 1, 2, 3),
        lambda: BoundingBox(1, 2, 3, 4, None),  # type: ignore[arg-type]
        lambda: BoundingBox.from_tuple((1, 2, 3)),  # type: ignore[arg-type]
        lambda: BoundingBox.from_tuple([1, 2, 3, 4]),  # type: ignore[arg-type]
        lambda: BoundingBox.from_tuple(("x", 2, 3, 4)),  # type: ignore[arg-type]
        lambda: MeshCode("", 3, "53394567"),
        lambda: MeshCode("unknown", 3, "53394567"),
        lambda: MeshCode("JIS-X-0410", 7, "53394567"),  # type: ignore[arg-type]
        lambda: MeshCode("JIS-X-0410", 3, "5339"),
        lambda: MeshCode("JIS-X-0410", 3, "5339456x"),
    ),
)
def test_space_value_validation_is_explicit(factory: Any) -> None:
    with pytest.raises(KnowledgeValidationError):
        factory()


def test_space_crs_serialization_and_non_crs84_validation() -> None:
    crs = CRSRef.parse("EPSG:6677")
    assert crs.as_string() == "EPSG:6677"
    bbox = BoundingBox(1, 2, 3, 4, crs)
    assert bbox.as_tuple() == (1, 2, 3, 4)


def test_estat_gis_distribution_is_resolved_as_general_gis_resource() -> None:
    distributions = [
        {
            "distribution_id": "census-2020-small-area-tokyo-gml",
            "dataset_id": "census-2020",
            "boundary_kind": "small-area",
            "survey_year": 2020,
            "level": "municipality",
            "region_code": "13",
            "format": "GML",
            "media_type": "application/gml+xml",
            "uri": "https://www.e-stat.go.jp/gis/download/census-2020.gml",
            "title": "国勢調査 2020 小地域 東京都",
            "matches_config": False,
        },
        {
            "distribution_id": "census-2020-small-area-tokyo-shp",
            "dataset_id": "census-2020",
            "boundary_kind": "small-area",
            "survey_year": 2020,
            "level": "municipality",
            "region_code": "13",
            "format": "shapefile",
            "media_type": "application/zip",
            "archive": "zip",
            "entry_point": "tokyo.shp",
            "uri": "https://www.e-stat.go.jp/gis/download/census-2020.zip",
            "title": "国勢調査 2020 小地域 東京都 Shape",
        },
    ]
    app = configure(
        sources=(Provider("estat", "estat-gis", {"distributions": distributions}),)
    )

    resource = app.resolve(
        Config(
            "estat",
            {
                "dataset_id": "census-2020",
                "boundary_kind": "small-area",
                "survey_year": 2020,
                "level": "municipality",
                "region_code": "13",
                "format": "gml",
            },
        )
    )
    assert resource.format == "gml"
    assert resource.access_plan.kind == "file"
    assert resource.provenance.adapter == "estat-gis"
    assert resource.source.raw_metadata["distribution_index"][0]["format"] == "GML"
    assert (
        resource.source.raw_metadata["distribution_index"][0]["matches_config"] is False
    )
    assert resource.source.metadata.raw["distribution_index"][0]["format"] == "GML"
    assert resource.provenance.raw["distribution"]["format"] == "GML"
    assert (
        resource.source.candidates[0].attributes["dataset_identity"]["dataset_id"]
        == "census-2020"
    )
    assert "matches_config" not in resource.source.candidates[0].attributes

    with pytest.raises(AmbiguousResourceError, match="exactly one"):
        app.resolve(Config("estat", {"dataset_id": "census-2020"}))

    zip_resource = app.resolve(
        Config("estat", {"distribution_id": "census-2020-small-area-tokyo-shp"})
    )
    assert zip_resource.access_plan.options["entry_point"] == "tokyo.shp"

    timed = app.resolve(
        Config(
            "estat",
            {
                "distribution_id": "census-2020-small-area-tokyo-gml",
                "time": "2020",
                "time_kind": "survey_year",
            },
        )
    )
    assert timed.provenance.raw["knowledge"]["time"]["kind"] == "survey_year"
    with pytest.raises(ConfigValidationError, match="survey_year"):
        app.resolve(
            Config(
                "estat",
                {
                    "distribution_id": "census-2020-small-area-tokyo-gml",
                    "time": "2020",
                    "time_kind": "calendar_year",
                },
            )
        )
    with pytest.raises(ConfigValidationError, match="time_kind"):
        app.resolve(Config("estat", {"time_kind": "survey_year"}))
    with pytest.raises(ConfigValidationError, match="survey_year"):
        app.resolve(Config("estat", {"survey_year": "2020"}))
    with pytest.raises(ConfigValidationError, match="unexpected"):
        app.resolve(Config("estat", {"unexpected": "value"}))
    with pytest.raises(ResourceNotFoundError, match="No e-Stat"):
        app.resolve(Config("estat", {"distribution_id": "missing"}))
    with pytest.raises(ResourceNotFoundError, match="No e-Stat"):
        app.resolve(
            Config(
                "estat",
                {
                    "distribution_id": "census-2020-small-area-tokyo-gml",
                    "survey_year": 2019,
                },
            )
        )
    with pytest.raises(ResourceNotFoundError, match="No e-Stat"):
        app.resolve(
            Config(
                "estat",
                {
                    "distribution_id": "census-2020-small-area-tokyo-gml",
                    "time": "2019",
                    "time_kind": "survey_year",
                },
            )
        )
    with pytest.raises(ConfigValidationError, match="survey_year"):
        app.resolve(Config("estat", {"time": "2019"}))
    with pytest.raises(ConfigValidationError, match="survey_year"):
        app.resolve(Config("estat", {"boundary_kind": "missing", "time": "2019"}))

    adapter = EstatGisAdapter(distributions)
    assert len(adapter.search(SearchQuery(text="Shape", limit=1))) == 1
    assert len(adapter.search(SearchQuery(limit=1))) == 1
    app_results = app.search(text="Shape", limit=1)
    assert app_results[0].target.source_id == "estat"
    with pytest.raises(UnsupportedSearchConditionError):
        adapter.search(SearchQuery(bbox=(1, 2, 3, 4)))

    adapter.config_schema = lambda: None  # type: ignore[method-assign]
    with pytest.raises(ConfigValidationError, match="Unknown"):
        adapter.load(Config("estat-gis", {"unexpected": "value"}))
    calendar_adapter = EstatGisAdapter(
        distributions, knowledge=cast(Any, StandardTimeAdapter())
    )
    calendar_adapter.config_schema = lambda: None  # type: ignore[method-assign]
    with pytest.raises(ConfigValidationError, match="survey_year"):
        calendar_adapter.load(
            Config("estat-gis", {"time": "2020", "time_kind": "calendar_year"})
        )


def test_estat_gis_requires_and_validates_an_explicit_index() -> None:
    with pytest.raises(ConfigValidationError, match="requires distributions"):
        configure(sources=(Provider("estat", "estat-gis"),)).resolve(
            Config("estat", {})
        )

    valid = {
        "distribution_id": "d1",
        "dataset_id": "ds1",
        "boundary_kind": "municipality",
        "survey_year": 2020,
        "level": "municipality",
        "uri": "https://example.test/d.gml",
        "format": "gml",
    }
    invalid = [
        None,
        {key: value for key, value in valid.items() if key != "distribution_id"},
        {**valid, "distribution_id": ""},
        {**valid, "distribution_id": "d1", "survey_year": 0},
        {**valid, "distribution_id": "d2", "region_code": 13},
        {**valid, "distribution_id": "d2", "format": "csv"},
        {**valid, "distribution_id": "d2", "title": " "},
        {**valid, "distribution_id": "d2", "description": 123},
        {**valid, "distribution_id": "d2", "uri": "http://example.test/d.gml"},
        {**valid, "distribution_id": "d2", "uri": "https://"},
        {**valid, "distribution_id": "d2", "uri": "https:///download.gml"},
        {**valid, "distribution_id": "d2", "uri": "https://[invalid/d.gml"},
        {**valid, "distribution_id": "d2", "media_type": 1},
        {**valid, "distribution_id": "d2", "media_type": "application/zip"},
        {
            **valid,
            "distribution_id": "d2",
            "media_type": "application/zip; charset=binary",
        },
        {**valid, "distribution_id": "d2", "archive": "tar"},
        {**valid, "distribution_id": "d2", "archive": "zip"},
        {**valid, "distribution_id": "d2", "archive": "zip", "entry_point": "../d.gml"},
        {**valid, "distribution_id": "d2", "archive": "zip", "entry_point": "."},
        {**valid, "distribution_id": "d2", "entry_point": "d.gml"},
        {
            **valid,
            "distribution_id": "d2",
            "uri": "https://user:password@example.test/d.gml",
        },
        {
            **valid,
            "distribution_id": "d2",
            "uri": "https://example.test/d.gml?token=secret",
        },
        {
            **valid,
            "distribution_id": "d2",
            "uri": "https://example.test/d.gml#access_token=secret",
        },
        {**valid, "distribution_id": "d2", "uri": "https://exa mple/d.gml"},
        {**valid, "distribution_id": "d2", "uri": "https://%ZZ/data.gml"},
    ]
    for value in invalid:
        with pytest.raises(ConfigValidationError):
            EstatGisAdapter([value])  # type: ignore[list-item]
    EstatGisAdapter([{**valid, "uri": "HTTPS://example.test/d.gml"}])
    with pytest.raises(ConfigValidationError, match="array"):
        EstatGisAdapter(None)  # type: ignore[arg-type]
    with pytest.raises(ConfigValidationError, match="must not be empty"):
        EstatGisAdapter([])
    with pytest.raises(ConfigValidationError, match="unique"):
        EstatGisAdapter([valid, valid])


def test_estat_gis_deep_copies_nested_raw_distribution_metadata() -> None:
    extension: dict[str, Any] = {
        "tags": ["original"],
        "tuple": ("original",),
        "set": {"original"},
        "frozen_set": frozenset({"original"}),
    }
    distribution = {
        "distribution_id": "d1",
        "dataset_id": "ds1",
        "boundary_kind": "municipality",
        "survey_year": 2020,
        "level": "municipality",
        "uri": "https://example.test/d.gml",
        "format": "gml",
        "extension": extension,
    }
    adapter = EstatGisAdapter([distribution])
    extension["tags"].append("mutated")

    source = adapter.load(Config("estat-gis", {"distribution_id": "d1"}))

    assert source.raw_metadata["distribution_index"][0]["extension"]["tags"] == (
        "original",
    )
    assert source.provenance.raw["distribution"]["extension"]["tags"] == ("original",)


def test_estat_gis_accepts_provider_frozen_distribution_settings() -> None:
    distribution = {
        "distribution_id": "d1",
        "dataset_id": "ds1",
        "boundary_kind": "municipality",
        "survey_year": 2020,
        "level": "municipality",
        "uri": "https://example.test/d.gml",
        "format": "gml",
        "extension": {"nested": {"tags": ["original"]}},
    }
    provider = Provider("estat", "estat-gis", {"distributions": [distribution]})

    resource = configure(sources=(provider,)).resolve(
        Config("estat", {"distribution_id": "d1"})
    )

    assert resource.source.raw_metadata["distribution_index"][0]["extension"]["nested"][
        "tags"
    ] == ("original",)


def test_custom_adapter_context_uses_public_ports_only() -> None:
    seen: list[tuple[bool, bool]] = []

    def source_factory(provider: Provider, context: Any) -> Any:
        seen.append(
            (hasattr(context.credentials, "get"), hasattr(context.dependencies, "get"))
        )

        class Adapter:
            def load(self, config: Config) -> Any:
                from rhinestone.models import (
                    Metadata,
                    Provenance,
                    ResourceCandidate,
                    Source,
                )

                return Source(
                    metadata=Metadata(title="public"),
                    candidates=(
                        ResourceCandidate("https://example.test/a", "gml", None),
                    ),
                    capabilities=frozenset(),
                    provenance=Provenance(provider=provider.id),
                    raw_metadata={},
                )

        return Adapter()

    app = configure(
        sources=(Provider("external", "external-source"),),
        adapters=(SourceAdapterDefinition("external-source", source_factory),),
    )
    app.resolve(Config("external", {}))
    assert seen == [(True, True)]


def test_municipality_projection_ignores_provider_specific_identity_fields() -> None:
    snapshot = StaticMunicipalityAdapter(municipality_records(), snapshot_version="v1")
    projected = MunicipalityIdentity(
        code="13101",
        name="千代田区",
        prefecture_code="13",
        prefecture_name="東京都",
        provider_identifiers={"other": "external-13101"},
    )
    assert snapshot.project(projected, "plateau") == "13101-tokyo"


def test_municipality_projection_checks_all_canonical_matching_records() -> None:
    identity = MunicipalityIdentity("13101", "千代田区", "13", "東京都")
    snapshot = StaticMunicipalityAdapter(
        (
            MunicipalityRecord(
                MunicipalityIdentity(
                    "13101",
                    "千代田区",
                    "13",
                    "東京都",
                    provider_identifiers={"first": "first-13101"},
                ),
            ),
            MunicipalityRecord(
                MunicipalityIdentity(
                    "13101",
                    "千代田区",
                    "13",
                    "東京都",
                    provider_identifiers={"second": "second-13101"},
                ),
            ),
        ),
        snapshot_version="v1",
    )
    assert snapshot.resolve_municipality("千代田区").code == "13101"
    assert snapshot.project(identity, "second") == "second-13101"
    split_identity = snapshot.resolve_municipality("13101")
    assert split_identity.provider_identifiers == {
        "first": "first-13101",
        "second": "second-13101",
    }
    with pytest.raises(KnowledgeValidationError, match="conflicting"):
        StaticMunicipalityAdapter(
            (
                MunicipalityRecord(
                    MunicipalityIdentity(
                        "13101",
                        "千代田区",
                        "13",
                        "東京都",
                        provider_identifiers={"same": "first-13101"},
                    )
                ),
                MunicipalityRecord(
                    MunicipalityIdentity(
                        "13101",
                        "千代田区",
                        "13",
                        "東京都",
                        provider_identifiers={"same": "second-13101"},
                    )
                ),
            ),
            snapshot_version="v1",
        )


def test_custom_source_receives_one_core_managed_transport_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rhinestone._http as http
    from rhinestone.models import Metadata, Provenance, ResourceCandidate, Source

    calls: list[tuple[str, object, object]] = []

    def get_json(
        url: str, params: object, headers: Optional[Mapping[str, str]] = None
    ) -> dict[str, object]:
        calls.append((url, params, headers))
        return {"ok": True}

    monkeypatch.setattr(http, "get_json", get_json)

    def factory(provider: Provider, context: Any) -> Any:
        assert hasattr(context, "transport")
        assert not hasattr(context, "get_json")
        assert not hasattr(context, "get_text")
        context.transport.get_json("https://custom.example/data", {})
        context.transport.get_json(
            "https://custom.example/data",
            {},
            {"Authorization": "secret"},
            credential="custom-key",
        )

        class Adapter:
            def load(self, config: Config) -> Any:
                return Source(
                    metadata=Metadata(title="target"),
                    candidates=(
                        ResourceCandidate(
                            "https://custom.example/data",
                            "GeoPackage",
                            "application/octet-stream",
                        ),
                    ),
                    capabilities=frozenset(),
                    provenance=Provenance(provider=provider.id),
                    raw_metadata={},
                )

        return Adapter()

    configure(
        sources=(
            Provider("custom", "custom-source", {"endpoint": "https://custom.example"}),
        ),
        adapters=(SourceAdapterDefinition("custom-source", factory),),
    )
    assert calls[0] == ("https://custom.example/data", {}, None)
    assert calls[1][0:2] == ("https://custom.example/data", {})
    assert calls[1][2] == {"Authorization": "secret"}
    assert getattr(calls[1][2], "_rhinestone_no_redirects") is True


def test_custom_transport_preserves_text_headers_and_normalizes_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rhinestone._http as http

    seen: dict[str, object] = {}

    def get_text(url: str, headers: object) -> str:
        seen["url"] = url
        seen["headers"] = headers
        return "document"

    monkeypatch.setattr(http, "get_text", get_text)

    def factory(provider: Provider, context: Any) -> Any:
        class Adapter:
            def load(self, config: Config) -> Any:
                assert (
                    context.transport.get_text(
                        "https://custom.example/catalog",
                        {"Authorization": "secret"},
                        credential="custom-key",
                    )
                    == "document"
                )
                from rhinestone.models import (
                    Metadata,
                    Provenance,
                    ResourceCandidate,
                    Source,
                )

                return Source(
                    metadata=Metadata(title="target"),
                    candidates=(
                        ResourceCandidate(
                            "https://custom.example/data", "geojson", None
                        ),
                    ),
                    capabilities=frozenset(),
                    provenance=Provenance(provider=provider.id),
                    raw_metadata={},
                )

        return Adapter()

    app = configure(
        sources=(
            Provider(
                "custom",
                "custom-source",
                {"endpoint": "https://custom.example", "credential": "custom-key"},
            ),
        ),
        adapters=(SourceAdapterDefinition("custom-source", factory),),
    )
    app.resolve(Config("custom", {}))
    assert seen == {
        "url": "https://custom.example/catalog",
        "headers": {"Authorization": "secret"},
    }


def test_custom_transport_normalizes_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rhinestone._http as http

    def fail_json(url: str, params: object) -> object:
        raise OSError("offline")

    monkeypatch.setattr(http, "get_json", fail_json)

    def factory(provider: Provider, context: Any) -> Any:
        class Adapter:
            def load(self, config: Config) -> Any:
                context.transport.get_json("https://custom.example/data", {})
                raise AssertionError("transport should have failed")

        return Adapter()

    app = configure(
        sources=(
            Provider("custom", "custom-source", {"endpoint": "https://custom.example"}),
        ),
        adapters=(SourceAdapterDefinition("custom-source", factory),),
    )
    with pytest.raises(ProviderMetadataError, match="Provider metadata request failed"):
        app.resolve(Config("custom", {}))


def test_discovery_record_rejects_empty_source_and_exposes_alias() -> None:
    from rhinestone.models import DiscoveryRecord, Metadata, Provenance

    record = DiscoveryRecord(
        "catalog",
        Metadata(title="found"),
        Provenance(provider="catalog"),
        {"source": "raw"},
    )
    assert record.discovered_by == "catalog"
    assert record.raw_metadata == {"source": "raw"}
    with pytest.raises(ConfigValidationError, match="source_id"):
        DiscoveryRecord("", Metadata(), Provenance(provider="catalog"))
