import json
import os
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from rhinestone import Catalog, _http, configure
from rhinestone.catalogs import BUILTIN
from rhinestone.errors import (
    DestinationNotAllowedError,
    ExecutionAdapterUnavailableError,
    ProviderMetadataError,
    ResourceAccessError,
)
from rhinestone.models import AccessPlan, RuntimeFactory
from rhinestone.pipeline import AccessPipeline
from rhinestone.registry import AdapterRegistry
from rhinestone.resolution import Resolver


@pytest.mark.parametrize(
    "library,method,format_name,options,expected,kwargs",
    [
        (
            "gdal",
            "OpenEx",
            "shapefile",
            {"archive": "zip", "entry_point": "data/a.shp", "encoding": "cp932"},
            "/vsizip//data/a.zip/data/a.shp",
            {"open_options": ("ENCODING=CP932",)},
        ),
        (
            "pyogrio",
            "read_dataframe",
            "shapefile",
            {"archive": "zip", "entry_point": "data/a.shp", "encoding": "cp932"},
            "/vsizip//data/a.zip/data/a.shp",
            {"encoding": "cp932"},
        ),
        ("rasterio", "open", "cog", {}, "/data/a.zip", {}),
    ],
)
def test_restored_plan_runs_without_resource_or_provider(
    library: str,
    method: str,
    format_name: str,
    options: dict[str, Any],
    expected: str,
    kwargs: dict[str, Any],
) -> None:
    plan = AccessPlan.from_dict(
        json.loads(
            json.dumps(
                AccessPlan(
                    kind="file", uri="/data/a.zip", format=format_name, options=options
                ).to_dict()
            )
        )
    )
    calls: list[Any] = []

    def record(uri: str, **kw: Any) -> str:
        calls.append((uri, kw))
        return "data"

    runtime = SimpleNamespace(**{method: record})
    assert configure(catalog=Catalog(())).open(plan, library, runtime=runtime) == "data"
    assert calls == [(expected, kwargs)]


@pytest.mark.parametrize("runtime", [None, RuntimeFactory(lambda: object())])
def test_plan_requires_runtime_object(runtime: object) -> None:
    with pytest.raises(ExecutionAdapterUnavailableError, match="must be supplied"):
        configure(catalog=Catalog(())).open(
            AccessPlan(kind="file", uri="/a.tif", format="cog"),
            "rasterio",
            runtime=runtime,
        )


def test_received_plan_authorized_before_runtime_or_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(_http, "JsonServiceRuntime", lambda: calls.append("runtime"))
    plan = AccessPlan(
        kind="service-query",
        uri="https://evil.example/api",
        media_type="application/json",
        provider="odpt",
        service="odpt",
        credential="odpt",
    )
    app = configure(
        credentials={"odpt": lambda: calls.append("credential") or "secret"}
    )
    with pytest.raises(DestinationNotAllowedError):
        app.open(plan, "json-service")
    assert calls == []


def test_restored_service_plan_uses_internal_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    def get(uri: str, **kwargs: Any) -> object:
        calls.append((uri, kwargs))
        return SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: list[dict[str, Any]](),
        )

    monkeypatch.setattr(_http, "JsonServiceRuntime", lambda: SimpleNamespace(get=get))
    plan = AccessPlan.from_dict(
        AccessPlan(
            kind="service-query",
            uri="https://api.odpt.org/api/v4/odpt:Station",
            media_type="application/json",
            service="odpt",
            provider="odpt",
            credential="odpt",
            options={
                "response_type": "array",
                "params": {},
                "endpoint": "https://api.odpt.org/api/v4/odpt:Station",
            },
        ).to_dict()
    )
    app = configure(
        catalog=Catalog((BUILTIN[3],)), credentials={"odpt": lambda: "secret"}
    )
    assert app.open(plan, "json-service") == []
    assert calls[0][1]["allow_redirects"] is False
    with pytest.raises(ExecutionAdapterUnavailableError, match="omit runtime"):
        app.open(plan, "json-service", runtime=object())


def test_plan_executes_in_separate_process() -> None:
    plan = AccessPlan(kind="file", uri="/data/a.tif", format="cog")
    code = """import json, sys
from types import SimpleNamespace
from rhinestone import Catalog, configure
from rhinestone.models import AccessPlan
app = configure(catalog=Catalog(()))
print(app.open(AccessPlan.from_dict(json.loads(sys.stdin.read())), "rasterio", runtime=SimpleNamespace(open=lambda uri: uri)))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps(plan.to_dict()),
        text=True,
        capture_output=True,
        check=True,
        env=os.environ.copy(),
    )
    assert result.stdout.strip() == "/data/a.tif"


def test_unconfigured_pipeline_rejects_plan_execution() -> None:
    pipeline = AccessPipeline(AdapterRegistry((), ()), Resolver())
    with pytest.raises(ProviderMetadataError, match="Execution pipeline"):
        pipeline.open_plan(
            AccessPlan(kind="file", uri="/a.tif", format="cog"), "rasterio"
        )


@pytest.mark.parametrize("missing", ["min_zoom", "max_zoom"])
def test_received_tile_translation_failure_is_classified(missing: str) -> None:
    tile = {
        "scheme": "xyz",
        "url": "https://tiles.example/{z}/{x}/{y}.png",
        "min_zoom": 0,
        "max_zoom": 18,
    }
    del tile[missing]
    plan = AccessPlan.from_dict(
        AccessPlan(
            kind="remote-dataset", uri="https://tiles.example", options={"tile": tile}
        ).to_dict()
    )
    calls: list[str] = []

    def open_ex(uri: str, **kwargs: Any) -> bool:
        calls.append(uri)
        return True

    # Authorization is independent of translation; this fixture explicitly opts out.
    app = configure(catalog=Catalog(()), network_policy="none")
    with pytest.raises(ResourceAccessError) as error:
        app.open(plan, "gdal", runtime=SimpleNamespace(OpenEx=open_ex))
    assert isinstance(error.value.__cause__, KeyError)
    assert calls == []
