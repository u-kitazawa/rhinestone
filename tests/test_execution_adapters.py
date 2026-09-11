from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple, cast

import pytest

from rhinestone import DestinationPolicy, Provider
from rhinestone.adapters.execution import (
    ExecutionAdapter,
    GdalAdapter,
    JsonServiceAdapter,
    PyogrioAdapter,
    RasterioAdapter,
)
from rhinestone.errors import (
    DestinationNotAllowedError,
    ResourceAccessError,
    RuntimeCapabilityError,
)
from rhinestone.models import (
    FileAccessPlan,
    Metadata,
    Provenance,
    RemoteDatasetPlan,
    Resource,
    ResourceCandidate,
    Source,
)


def make_resource(
    uri: str,
    format_name: str,
    attributes: Optional[Dict[str, Any]] = None,
    remote: bool = False,
) -> Resource:
    candidate = ResourceCandidate(
        uri=uri,
        format=format_name,
        media_type="application/octet-stream",
        attributes=attributes or {},
    )
    source = Source(
        metadata=Metadata(title="Data", raw={}),
        candidates=(candidate,),
        capabilities=frozenset({"download"}),
        provenance=Provenance(provider="direct", raw={}),
        raw_metadata={},
    )
    plan = (
        RemoteDatasetPlan(uri=uri)
        if remote
        else FileAccessPlan(uri=uri, archive=(attributes or {}).get("archive"))
    )
    return Resource(
        uri=uri,
        format=format_name,
        media_type="application/octet-stream",
        metadata=source.metadata,
        provenance=source.provenance,
        access_plan=plan,
        source=source,
    )


class BasicExecutionAdapter(ExecutionAdapter):
    name = "basic"
    priority = 0

    def supports(self, resource: Resource, dependencies: frozenset[str]) -> bool:
        return True

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        return runtime


def test_execution_adapter_default_authorization_uses_resource_uri() -> None:
    resource = make_resource("https://unlisted.example/data", "custom")

    with pytest.raises(DestinationNotAllowedError):
        BasicExecutionAdapter().authorize(
            resource,
            destination_policy=DestinationPolicy(level="strict"),
        )


class FakeGdal:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Tuple[str, ...]]] = []
        self.allowed_drivers: List[Tuple[str, ...] | None] = []

    def OpenEx(
        self,
        uri: str,
        open_options: Tuple[str, ...] = (),
        allowed_drivers: Tuple[str, ...] | None = None,
    ) -> object:
        self.calls.append((uri, open_options))
        self.allowed_drivers.append(allowed_drivers)
        return {"runtime": "gdal", "uri": uri}


def test_gdal_translates_remote_zip_and_encoding_without_selecting_resource() -> None:
    """選択済みZIP ShapefileをGDAL URI/optionsへ翻訳し、別Resourceを選ばないために必要である。"""
    resource = make_resource(
        "https://files.example/rivers.zip",
        "shapefile",
        {"archive": "zip", "encoding": "cp932"},
    )
    runtime = FakeGdal()

    data = GdalAdapter().open(resource, runtime)

    assert runtime.calls == [
        (
            "/vsizip//vsicurl/https://files.example/rivers.zip",
            ("ENCODING=CP932",),
        )
    ]
    assert data["runtime"] == "gdal"
    assert GdalAdapter().supports(resource, frozenset({"gdal"})) is True


class FakeRasterio:
    def __init__(self) -> None:
        self.calls: List[str] = []
        self.drivers: List[str | None] = []

    def open(self, uri: str, driver: str | None = None) -> object:
        self.calls.append(uri)
        self.drivers.append(driver)
        return {"runtime": "rasterio"}


def test_rasterio_opens_cog_uri_directly() -> None:
    """COGのRemoteDatasetPlanをdownloadせずRasterioへそのまま渡すために必要である。"""
    resource = make_resource("https://files.example/image.tif", "cog", remote=True)
    runtime = FakeRasterio()

    assert RasterioAdapter().open(resource, runtime) == {"runtime": "rasterio"}
    assert runtime.calls == ["https://files.example/image.tif"]
    assert runtime.drivers == [None]


@pytest.mark.parametrize("format_name", ("cog", "geotiff"))
def test_strict_raster_adapters_pin_gtiff_driver(format_name: str) -> None:
    resource = make_resource("/data/image.tif", format_name)
    policy = strict_files_policy()
    gdal = FakeGdal()
    rasterio = FakeRasterio()

    GdalAdapter(policy).open(resource, gdal)
    RasterioAdapter(policy).open(resource, rasterio)

    assert gdal.allowed_drivers == [("GTiff",)]
    assert rasterio.drivers == ["GTiff"]


def test_strict_driver_pinning_prevents_hostile_vrt_fallback() -> None:
    secondary_destinations: List[str] = []

    class HostileGdal:
        def OpenEx(
            self,
            uri: str,
            open_options: Tuple[str, ...] = (),
            allowed_drivers: Tuple[str, ...] | None = None,
        ) -> object:
            if allowed_drivers != ("GTiff",):
                secondary_destinations.append("https://unlisted.example/secret.tif")
            return object()

    GdalAdapter(strict_files_policy()).open(
        make_resource("/data/disguised.tif", "geotiff"),
        HostileGdal(),
    )

    assert secondary_destinations == []


@pytest.mark.parametrize(
    "format_name", ("shapefile", "netcdf", "wms", "gml", "citygml")
)
def test_strict_gdal_rejects_unpinned_driver_before_runtime(
    format_name: str,
) -> None:
    runtime = FakeGdal()

    with pytest.raises(DestinationNotAllowedError, match="dataset driver"):
        GdalAdapter(strict_files_policy()).open(
            make_resource("/data/file", format_name), runtime
        )

    assert runtime.calls == []


def test_strict_rasterio_rejects_unpinned_driver_before_runtime() -> None:
    runtime = FakeRasterio()
    resource = make_resource("/data/rivers.shp", "shapefile")

    with pytest.raises(DestinationNotAllowedError, match="dataset driver"):
        RasterioAdapter(strict_files_policy()).open(resource, runtime)

    assert runtime.calls == []


class FakePyogrio:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def read_dataframe(self, uri: str, **options: Any) -> object:
        self.calls.append((uri, options))
        return {"runtime": "pyogrio"}


_GDAL_RUNTIME_CASES = (
    (GdalAdapter, FakeGdal, "geotiff"),
    (RasterioAdapter, FakeRasterio, "geotiff"),
    (PyogrioAdapter, FakePyogrio, "geojson"),
)


def strict_files_policy() -> DestinationPolicy:
    return DestinationPolicy.from_catalog(
        (
            Provider(
                "files",
                "direct",
                {"endpoint": "https://allowed.example/data"},
            ),
        ),
        level="strict",
    )


@pytest.mark.parametrize(
    "locator",
    (
        "/vsicurl/https://unlisted.example/data.tif",
        "/vsicurl_streaming/https://unlisted.example/data.geojson",
        "/vsizip//vsicurl/https://unlisted.example/data.zip/member.shp",
        "/vsizip/{/vsicurl/https://unlisted.example/data.zip}/member.shp",
        "/vsicurl/ftp://unlisted.example/data.tif",
        "/vsicurl?use_head=no",
        "/vsicurl?" + "&".join(f"option{index}=x" for index in range(65)),
        "/vsizip//vsicurl?url=https%3A%2F%2Fallowed.example%2Fdata.zip",
        "/vsizip//vsicurl/ftp://allowed.example/data.zip",
        "/vsizip//vsicurl/https://allowed.example/data/file",
        "/vsizip/{/vsicurl/https://allowed.example/data/archive.zip",
        "/vsiunknown/https://allowed.example/data/file.tif",
    ),
)
@pytest.mark.parametrize(
    ("adapter_type", "runtime_type", "format_name"), _GDAL_RUNTIME_CASES
)
def test_strict_execution_rejects_unsafe_gdal_locator_before_runtime(
    locator: str,
    adapter_type: Any,
    runtime_type: Any,
    format_name: str,
) -> None:
    runtime = runtime_type()

    with pytest.raises(DestinationNotAllowedError):
        adapter_type(strict_files_policy()).open(
            make_resource(locator, format_name), runtime
        )

    assert runtime.calls == []


@pytest.mark.parametrize(
    "locator",
    (
        "/data/local-file.tif",
        "/vsizip//data/local.zip/member.shp",
        "/vsimem/in-memory.tif",
    ),
)
@pytest.mark.parametrize(
    ("adapter_type", "runtime_type", "format_name"), _GDAL_RUNTIME_CASES
)
def test_strict_execution_allows_authorized_or_local_gdal_locator(
    locator: str,
    adapter_type: Any,
    runtime_type: Any,
    format_name: str,
) -> None:
    runtime = runtime_type()

    adapter_type(strict_files_policy()).open(
        make_resource(locator, format_name), runtime
    )

    assert len(runtime.calls) == 1


@pytest.mark.parametrize(
    ("adapter_type", "runtime_type", "format_name"), _GDAL_RUNTIME_CASES
)
@pytest.mark.parametrize(
    "locator",
    (
        "https://allowed.example/data/file.tif",
        "/vsicurl/https://allowed.example/data/file.tif",
        "/vsicurl_streaming/https://allowed.example/data/file.geojson",
        "/vsizip//vsicurl/https://allowed.example/data/archive.zip/member.shp",
        "/vsizip/vsicurl/https://allowed.example/data/archive.zip/member.shp",
        "/vsizip/{/vsicurl/https://allowed.example/data/archive.zip}/member.shp",
        "/vsizip/{https://allowed.example/data/archive.zip}/member.shp",
        "/vsizip/https://allowed.example/data/archive.zip/member.shp",
        "/vsizip//vsicurl/https://allowed.example/data/archive.zipx/file.tar/member.shp",
        "/vsizip/{/vsizip/{/vsicurl/https://allowed.example/data/archive.zip}}/member.shp",
        "/vsicurl?use_head=no&url=https%3A%2F%2Fallowed.example%2Fdata%2Ffile.tif",
    ),
)
def test_strict_execution_rejects_remote_runtime_handoff(
    locator: str,
    adapter_type: Any,
    runtime_type: Any,
    format_name: str,
) -> None:
    runtime = runtime_type()

    with pytest.raises(RuntimeCapabilityError, match="redirects"):
        adapter_type(strict_files_policy()).open(
            make_resource(locator, format_name), runtime
        )

    assert runtime.calls == []


def test_strict_archive_authorizes_archive_url_not_member_path() -> None:
    runtime = FakeGdal()
    policy = DestinationPolicy.from_catalog(
        (
            Provider(
                "files",
                "direct",
                {"endpoint": "https://allowed.example/data.zip/member.shp"},
            ),
        ),
        level="strict",
    )

    with pytest.raises(DestinationNotAllowedError):
        GdalAdapter(policy).open(
            make_resource(
                "/vsizip//vsicurl/https://allowed.example/data.zip/member.shp",
                "shapefile",
            ),
            runtime,
        )

    assert runtime.calls == []


def test_pyogrio_receives_explicit_encoding() -> None:
    """Sourceで確定したencodingを失わずpyogrioの既存I/Oへ委譲するために必要である。"""
    resource = make_resource("/data/rivers.shp", "shapefile", {"encoding": "cp932"})
    runtime = FakePyogrio()

    assert PyogrioAdapter().open(resource, runtime) == {"runtime": "pyogrio"}
    assert runtime.calls == [("/data/rivers.shp", {"encoding": "cp932"})]


def test_execution_adapter_preserves_runtime_failure_as_cause() -> None:
    """OSSアクセス失敗をResourceAccessErrorへ分類しつつ元の例外を診断可能にするために必要である。"""
    runtime_error = OSError("cannot open dataset")

    class BrokenRasterio:
        def open(self, uri: str) -> object:
            raise runtime_error

    resource = make_resource("https://files.example/image.tif", "cog", remote=True)

    with pytest.raises(ResourceAccessError) as captured:
        RasterioAdapter().open(resource, BrokenRasterio())

    assert captured.value.__cause__ is runtime_error


def test_gdal_handles_local_archive_and_resources_without_options() -> None:
    """local ZIPと通常Resourceをremote扱いせず、不要なoptionを付加しないために必要である。"""
    local = make_resource("/data/rivers.zip", "shapefile", {"archive": "zip"})
    local = replace(local, access_plan=FileAccessPlan(uri=local.uri))
    plain = make_resource("/data/rivers.shp", "shapefile")
    remote = make_resource("https://files.example/a.tif", "cog", remote=True)
    runtime = FakeGdal()

    GdalAdapter().open(local, runtime)
    GdalAdapter().open(plain, runtime)
    GdalAdapter().open(remote, runtime)

    assert runtime.calls == [
        ("/vsizip//data/rivers.zip", ()),
        ("/data/rivers.shp", ()),
        ("https://files.example/a.tif", ()),
    ]


def test_execution_support_requires_both_format_and_dependency() -> None:
    """format対応だけで未供給runtimeを選ばず、無関係formatにもfallbackしないために必要である。"""
    raster = make_resource("/data/a.tif", "cog", remote=True)
    vector = make_resource("/data/a.shp", "shapefile")

    assert RasterioAdapter().supports(raster, frozenset()) is False
    assert RasterioAdapter().supports(vector, frozenset({"rasterio"})) is False
    assert PyogrioAdapter().supports(vector, frozenset()) is False
    assert PyogrioAdapter().supports(raster, frozenset({"pyogrio"})) is False
    assert GdalAdapter().supports(vector, frozenset()) is False


def test_gdal_and_pyogrio_failures_are_classified() -> None:
    """各vector runtimeの外部例外を一貫してResourceAccessErrorへ変換するために必要である。"""
    failure = OSError("broken")

    class BrokenGdal:
        def OpenEx(self, uri: str, open_options: Tuple[str, ...] = ()) -> object:
            raise failure

    class BrokenPyogrio:
        def read_dataframe(self, uri: str, **options: Any) -> object:
            raise failure

    resource = make_resource("/data/a.shp", "shapefile")

    with pytest.raises(ResourceAccessError) as gdal_error:
        GdalAdapter().open(resource, BrokenGdal())
    with pytest.raises(ResourceAccessError) as pyogrio_error:
        PyogrioAdapter().open(resource, BrokenPyogrio())
    assert gdal_error.value.__cause__ is failure
    assert pyogrio_error.value.__cause__ is failure


def test_execution_uses_empty_attributes_when_candidate_is_not_retained() -> None:
    """不整合SourceでもExecution Adapterが別候補を選び直さず選択済みURIだけを使うために必要である。"""
    resource = make_resource("/data/selected.shp", "shapefile")
    other = ResourceCandidate("/data/other.shp", "shapefile", None)
    mismatched_source = Source(
        metadata=resource.metadata,
        candidates=(other,),
        capabilities=frozenset(),
        provenance=resource.provenance,
        raw_metadata={},
    )
    mismatched = Resource(
        uri=resource.uri,
        format=resource.format,
        media_type=resource.media_type,
        metadata=resource.metadata,
        provenance=resource.provenance,
        access_plan=resource.access_plan,
        source=mismatched_source,
    )
    runtime = FakePyogrio()

    PyogrioAdapter().open(mismatched, runtime)

    assert runtime.calls == [("/data/selected.shp", {})]


@pytest.mark.parametrize(
    "adapter",
    (GdalAdapter, JsonServiceAdapter, PyogrioAdapter, RasterioAdapter),
)
def test_builtin_execution_adapters_implement_the_public_base(adapter: Any) -> None:
    assert issubclass(adapter, ExecutionAdapter)


def test_public_execution_base_requires_its_contract() -> None:
    class IncompleteAdapter(ExecutionAdapter):
        pass

    with pytest.raises(TypeError, match="abstract"):
        cast(Any, IncompleteAdapter)()
