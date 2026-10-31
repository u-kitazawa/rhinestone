"""Exercise the public JAXA raster Showcase without live services or Rasterio."""

import json
import sys
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

import rhinestone
from rhinestone import (
    Catalog,
    Provider,
    ProviderId,
    Reference,
    SearchResults,
    configure,
)

ROOT = Path(__file__).parents[1] / "showcase"
NOTEBOOK = "05_open_raster.ipynb"
URI = (
    "https://s3.ap-northeast-1.wasabisys.com/je-pds/cog/v1/"
    "JAXA.EORC_GSMaP_standard.Gauge.00Z-23Z.v6_monthly/2021-02/0/"
    "E000.00-E180.00/E000.00-S90.00-E180.00-N90.00-PRECIP.tiff"
)


def cells() -> dict[str, dict[str, Any]]:
    value = json.loads((ROOT / NOTEBOOK).read_text(encoding="utf-8"))
    return {cell["id"]: cell for cell in value["cells"]}


def run(cell_id: str, namespace: dict[str, Any]) -> None:
    source = "".join(cells()[cell_id]["source"])
    exec(compile(source, f"{NOTEBOOK}:{cell_id}", "exec"), namespace)


class Candidate:
    title = "JAXA GSMaP monthly precipitation"
    format = "geotiff"
    uri = URI

    def __init__(
        self,
        opened: Any = None,
        provider_id: ProviderId = ProviderId.JAXA_GSMAP_PREVIEW,
        asset_key: str = "PRECIP",
    ) -> None:
        self.reference = SimpleNamespace(
            provider_id=provider_id, parameters={"asset_key": asset_key}
        )
        self.opened = opened
        self.calls: list[tuple[str, Any]] = []

    def open(self, name: str, *, runtime: Any) -> Any:
        self.calls.append((name, runtime))
        return nullcontext(self.opened)


def test_raster_notebook_contract_and_compilation() -> None:
    notebook = cells()
    source = "".join("".join(cell["source"]) for cell in notebook.values())
    for marker in (
        "ProviderId.JAXA_GSMAP_PREVIEW",
        "ProviderId.JAXA_AW3D_PREVIEW",
        "ProviderId.JAXA_HRLULC_PREVIEW",
        "Resampling.nearest",
        "AccessPlan.from_dict(json.loads(plan_json))",
        'parameters.get("asset_key") == ASSET_KEY',
        'resource.open("rasterio", runtime=rasterio)',
        "out_shape=(PREVIEW_SIZE, PREVIEW_SIZE)",
        "Resampling.average",
        "bf4b7d98a73f6871b1301c184386abf83cff29a9",
    ):
        assert marker in source
    for cell in notebook.values():
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), NOTEBOOK, "exec")
            assert not any(
                output.get("output_type") == "error" for output in cell["outputs"]
            )


@pytest.mark.parametrize(
    "name,provider_id,asset_key,year,month,last_day",
    [
        ("gsmap", ProviderId.JAXA_GSMAP_PREVIEW, "PRECIP", 2021, 2, 28),
        ("aw3d", ProviderId.JAXA_AW3D_PREVIEW, "DSM", 2021, 2, 28),
        ("hrlulc", ProviderId.JAXA_HRLULC_PREVIEW, "HRLULC", 2024, 1, 31),
    ],
)
def test_search_uses_bounded_builtin_preview_and_explicit_asset(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    provider_id: ProviderId,
    asset_key: str,
    year: int,
    month: int,
    last_day: int,
) -> None:
    selected = Candidate(provider_id=provider_id, asset_key=asset_key)
    calls: list[dict[str, Any]] = []

    def search(**kwargs: Any) -> SearchResults:
        calls.append(kwargs)
        return SearchResults.from_grouped({provider_id.value: (selected,)})  # type: ignore[arg-type]

    monkeypatch.setattr(rhinestone, "search", search)
    namespace: dict[str, Any] = {}
    run("inputs", namespace)
    namespace["DATASET"] = name
    run("preset", namespace)
    run("discover", namespace)
    run("select", namespace)

    assert calls == [
        {
            "bbox": (135.0, 30.0, 145.0, 40.0),
            "time": (
                datetime(year, month, 1, tzinfo=timezone.utc),
                datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc),
            ),
            "providers": [provider_id],
            "limit": 1,
        }
    ]
    assert namespace["resource"] is selected


@pytest.mark.parametrize("matches", [0, 2])
def test_raster_selection_never_falls_back_to_first(matches: int) -> None:
    namespace: dict[str, Any] = {
        "results": SearchResults.from_grouped(
            {"jaxa-gsmap-preview": tuple(Candidate() for _ in range(matches))}  # type: ignore[arg-type]
        ),
        "ASSET_KEY": "PRECIP",
        "PROVIDER_ID": ProviderId.JAXA_GSMAP_PREVIEW,
        "resource": object(),
    }
    with pytest.raises(ValueError, match="一意"):
        run("select", namespace)
    assert namespace["resource"] is None


@pytest.mark.parametrize(
    "name,resampling",
    [("gsmap", "average"), ("aw3d", "average"), ("hrlulc", "nearest")],
)
def test_open_reads_only_a_small_bbox_preview(
    monkeypatch: pytest.MonkeyPatch, name: str, resampling: str
) -> None:
    class Preview:
        shape = (64, 64)

        @staticmethod
        def count() -> int:
            return 4096

        @staticmethod
        def min() -> float:
            return 0.1

        @staticmethod
        def max() -> float:
            return 0.9

    data = Preview()

    class Dataset:
        width = 900
        height = 900
        count = 1
        crs = "EPSG:4326"

        def window(self, *bounds: float) -> tuple[float, ...]:
            assert bounds == (135.0, 30.0, 145.0, 40.0)
            return bounds

        def read(self, index: int, **kwargs: Any) -> Preview:
            assert index == 1
            assert kwargs == {
                "window": (135.0, 30.0, 145.0, 40.0),
                "out_shape": (64, 64),
                "resampling": resampling,
                "masked": True,
            }
            return data

    rasterio = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "rasterio", rasterio)
    monkeypatch.setitem(
        sys.modules,
        "rasterio.enums",
        SimpleNamespace(
            Resampling=SimpleNamespace(average="average", nearest="nearest")
        ),
    )
    selected = Candidate(Dataset())
    namespace = {
        "resource": selected,
        "BBOX": (135.0, 30.0, 145.0, 40.0),
        "PREVIEW_SIZE": 64,
        "DATASET": name,
    }
    run("open", namespace)
    assert selected.calls == [("rasterio", rasterio)]
    assert namespace["preview"] is data


@pytest.mark.parametrize(
    ("bounds", "extent"),
    [
        ((135.0, 30.0, 145.0, 40.0), (135.0, 145.0, 30.0, 40.0)),
        ((130.0, 31.0, 139.0, 37.0), (130.0, 139.0, 31.0, 37.0)),
    ],
)
def test_plot_preserves_longitude_and_latitude_bounds(
    monkeypatch: pytest.MonkeyPatch,
    bounds: tuple[float, float, float, float],
    extent: tuple[float, float, float, float],
) -> None:
    pyplot = MagicMock()
    figure, axis = MagicMock(), MagicMock()
    pyplot.subplots.return_value = (figure, axis)
    monkeypatch.setitem(sys.modules, "matplotlib", SimpleNamespace(pyplot=pyplot))
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", pyplot)
    preview = object()

    run(
        "plot",
        {
            "BBOX": bounds,
            "preview": preview,
            "CMAP": "Blues",
            "DATASET": "gsmap",
            "TITLE": "GSMaP",
            "VALUE_LABEL": "Stored value (mm/hr)",
        },
    )

    axis.imshow.assert_called_once_with(
        preview, origin="upper", extent=extent, cmap="Blues", interpolation="nearest"
    )


def test_land_cover_plot_uses_class_ids_without_image_smoothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pyplot = MagicMock()
    figure, axis = MagicMock(), MagicMock()
    pyplot.subplots.return_value = (figure, axis)
    monkeypatch.setitem(sys.modules, "matplotlib", SimpleNamespace(pyplot=pyplot))
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", pyplot)
    run(
        "plot",
        {
            "BBOX": (135, 30, 145, 40),
            "preview": "classes",
            "CMAP": "tab20",
            "DATASET": "hrlulc",
            "TITLE": "HRLULC",
            "VALUE_LABEL": "Land-cover class ID",
        },
    )
    assert axis.imshow.call_args.kwargs["interpolation"] == "nearest"
    assert axis.imshow.call_args.kwargs["vmin"] == 0.5
    assert axis.imshow.call_args.kwargs["vmax"] == 15.5
    assert figure.colorbar.call_args.kwargs["ticks"] == list(range(1, 16))


def test_portable_raster_opens_json_with_only_direct_receiver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = configure(
        catalog=Catalog((Provider("fixture", "direct", {"uri": URI, "format": "cog"}),))
    ).load(Reference("fixture", parameters={"uri": URI, "format": "cog"}))
    calls: list[str] = []
    dataset = object()

    def open_raster(uri: str) -> Any:
        calls.append(uri)
        return nullcontext(dataset)

    preview = SimpleNamespace(shape=(64, 64), count=lambda: 16)

    def read_preview(value: Any) -> Any:
        assert value is dataset
        return preview

    def no_search(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("portable receiver must not search")

    monkeypatch.setattr(rhinestone, "search", no_search)
    namespace: dict[str, Any] = {
        "resource": selected,
        "rasterio": SimpleNamespace(open=open_raster),
        "read_preview": read_preview,
    }
    run("portable", namespace)
    assert calls == [URI]
    assert namespace["received_plan"] == selected.access_plan
    assert namespace["plan_preview"] is preview
