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
from rhinestone import ProviderId, SearchResults

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
    reference = SimpleNamespace(
        provider_id="jaxa-gsmap-preview", parameters={"asset_key": "PRECIP"}
    )

    def __init__(self, opened: Any = None) -> None:
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
        'parameters.get("asset_key") == ASSET_KEY',
        'resource.open("rasterio", runtime=rasterio)',
        "out_shape=(PREVIEW_SIZE, PREVIEW_SIZE)",
        "Resampling.average",
        "114a7a10c30880dfb1655d0ce94fb2bf0f917145",
    ):
        assert marker in source
    for cell in notebook.values():
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), NOTEBOOK, "exec")
            assert not any(
                output.get("output_type") == "error" for output in cell["outputs"]
            )


def test_search_uses_bounded_builtin_preview_and_explicit_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = Candidate()
    calls: list[dict[str, Any]] = []

    def search(**kwargs: Any) -> SearchResults:
        calls.append(kwargs)
        return SearchResults.from_grouped({"jaxa-gsmap-preview": (selected,)})  # type: ignore[arg-type]

    monkeypatch.setattr(rhinestone, "search", search)
    namespace: dict[str, Any] = {}
    run("inputs", namespace)
    run("discover", namespace)
    run("select", namespace)

    assert calls == [
        {
            "bbox": (135.0, 30.0, 145.0, 40.0),
            "time": (
                datetime(2021, 2, 1, tzinfo=timezone.utc),
                datetime(2021, 2, 28, 23, 59, 59, tzinfo=timezone.utc),
            ),
            "providers": [ProviderId.JAXA_GSMAP_PREVIEW],
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
        "ProviderId": ProviderId,
        "resource": object(),
    }
    with pytest.raises(ValueError, match="一意"):
        run("select", namespace)
    assert namespace["resource"] is None


def test_open_reads_only_a_small_bbox_preview(monkeypatch: pytest.MonkeyPatch) -> None:
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
                "resampling": "average",
                "masked": True,
            }
            return data

    rasterio = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "rasterio", rasterio)
    monkeypatch.setitem(
        sys.modules,
        "rasterio.enums",
        SimpleNamespace(Resampling=SimpleNamespace(average="average")),
    )
    selected = Candidate(Dataset())
    namespace = {
        "resource": selected,
        "BBOX": (135.0, 30.0, 145.0, 40.0),
        "PREVIEW_SIZE": 64,
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

    run("plot", {"BBOX": bounds, "preview": preview})

    axis.imshow.assert_called_once_with(
        preview, origin="upper", extent=extent, cmap="Blues"
    )
