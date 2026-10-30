import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import pytest

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import AccessPlan, Provider, configure
from rhinestone.catalogs import BUILTIN, Catalog
from tests.provider_support import RecordingJsonClient, fixture_json


class RecordingRasterio:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def open(self, uri: str) -> str:
        self.calls.append(uri)
        return "opened:" + uri


def test_builtin_jaxa_preview_searches_the_bounded_level_zero_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = next(
        candidate for candidate in BUILTIN if candidate.id == "jaxa-gsmap-preview"
    )
    catalog_uri = provider.settings["catalog_uri"]
    assert isinstance(catalog_uri, str)
    item = dict(fixture_json("stac/jaxa_items.json")["gsmap"])
    item.pop("period")
    item_uri = urljoin(catalog_uri, "./S90.00-N90.00.json")
    client = RecordingJsonClient(
        {
            catalog_uri: {
                "type": "Catalog",
                "stac_version": "1.0.0",
                "id": "jaxa-gsmap-preview",
                "description": "Fixture catalog",
                "links": [{"rel": "item", "href": "./S90.00-N90.00.json"}],
            },
            item_uri: item,
        }
    )
    monkeypatch.setattr(_http, "get_json", client)
    app = configure(catalog=Catalog((provider,)))

    results = app.search(
        bbox=(139.0, 35.0, 140.0, 36.0),
        time=(
            datetime(2021, 2, 1, tzinfo=timezone.utc),
            datetime(2021, 2, 28, tzinfo=timezone.utc),
        ),
        limit=1,
    )

    assert len(results) == 1
    resource = results[0]
    assert resource.reference.provider_id == "jaxa-gsmap-preview"
    assert resource.reference.parameters["asset_key"] == "PRECIP"
    assert app.load(resource.reference).uri == resource.uri
    assert client.calls == [(catalog_uri, {}), (item_uri, {}), (item_uri, {})]


@pytest.mark.parametrize(
    "name,asset_key,format_name,year",
    [
        ("aw3d", "DSM", "cog", 2021),
        ("gsmap", "PRECIP", "geotiff", 2021),
        ("hrlulc", "HRLULC", "geotiff", 2024),
    ],
)
def test_jaxa_sample_search_open_and_independent_plan(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    asset_key: str,
    format_name: str,
    year: int,
) -> None:
    # Reduced snapshots of the official level-0 Items, not a built-in Provider.
    item: dict[str, Any] = dict(fixture_json("stac/jaxa_items.json")[name])
    period = item.pop("period")
    base = "https://s3.ap-northeast-1.wasabisys.com/je-pds/cog/v1/"
    catalog_uri = f"{base}{item['collection']}/{period}/0/E000.00-E180.00/catalog.json"
    item_uri = urljoin(catalog_uri, "./S90.00-N90.00.json")
    asset_uri = urljoin(item_uri, item["assets"][asset_key]["href"])
    client = RecordingJsonClient(
        {
            catalog_uri: {
                "type": "Catalog",
                "stac_version": "1.0.0",
                "id": "fixture",
                "description": "Fixture catalog",
                "links": [{"rel": "item", "href": "./S90.00-N90.00.json"}],
            },
            item_uri: item,
        }
    )
    monkeypatch.setattr(_http, "get_json", client)
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    id="jaxa-sample",
                    adapter_type="stac",
                    settings={"catalog_uri": catalog_uri, "max_documents": 2},
                ),
            )
        )
    )
    results = app.search(
        bbox=(139.0, 35.0, 140.0, 36.0),
        time=(
            datetime(year, 2, 1, tzinfo=timezone.utc),
            datetime(year, 2, 1, tzinfo=timezone.utc),
        ),
        limit=1,
    )
    assert len(results) == 1
    assert results.diagnostics == ()
    resource = results[0]
    assert resource.uri == asset_uri
    assert resource.format == format_name
    assert resource.reference.parameters["asset_key"] == asset_key
    assert resource.metadata.raw["stac_version"] == item["stac_version"]
    assert resource.metadata.raw["assets"][asset_key]["href"].startswith("./")
    runtime = RecordingRasterio()
    assert resource.open("rasterio", runtime=runtime) == "opened:" + asset_uri
    plan = AccessPlan.from_dict(json.loads(json.dumps(app.plan(resource).to_dict())))
    # The receiver authorizes the selected URI, but has no STAC Provider.
    receiver = configure(
        catalog=Catalog(
            (
                Provider(
                    id="permitted-raster",
                    adapter_type="direct",
                    settings={"uri": asset_uri, "format": format_name},
                ),
            )
        )
    )
    assert receiver.open(plan, "rasterio", runtime=runtime) == "opened:" + asset_uri
    assert runtime.calls == [asset_uri, asset_uri]
    assert client.calls == [(catalog_uri, {}), (item_uri, {})]
