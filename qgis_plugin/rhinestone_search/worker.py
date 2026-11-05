"""One request per isolated Python process; no QGIS or private Core APIs."""

import errno
import json
import os
import re
import shutil
import sys
import zipfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import urlopen

# -I -S excludes user/system site packages. Never alter QGIS's import paths.
sys.path.insert(0, str(Path(__file__).parent / "vendor"))

from rhinestone import AccessPlan, Format, ProviderId, Resource, configure, search
from rhinestone.adapters.provider import (
    GeospatialJpAdapter,
    MlitDpfAdapter,
    OdptAdapter,
    PlateauAdapter,
    SearchCkanJpAdapter,
    StacAdapter,
    StaticAdapter,
)
from rhinestone.catalogs import BUILTIN
from rhinestone.errors import ConfigValidationError
from rhinestone.models import SearchQuery  # noqa: E402

MAX_MEMBERS = 4096
SUFFIXES = {
    "geojson": ".geojson",
    "json": ".json",
    "csv": ".csv",
    "gpkg": ".gpkg",
    "flatgeobuf": ".fgb",
    "gml": ".gml",
    "citygml": ".gml",
    "kml": ".kml",
    "geotiff": ".tif",
    "cog": ".tif",
    "netcdf": ".nc",
    "shapefile": ".shp",
    "zip": ".zip",
}


class DownloadError(ValueError):
    """A safe, user-readable download rejection."""


def plan_for(resource, app):
    """Keep explicit plans; recognize provider-independent XYZ URL templates."""
    original = resource.access_plan
    if original and (
        original.options
        or original.credential
        or original.service
        or original.kind == "service-query"
    ):
        return app.plan(resource)
    template = resource.uri
    for axis in ("x", "y", "z"):
        template = template.replace("%7B" + axis + "%7D", "{" + axis + "}")
        template = template.replace("%7b" + axis + "%7d", "{" + axis + "}")
    if not all("{" + axis + "}" in template for axis in ("x", "y", "z")):
        return app.plan(resource)
    suffix = Path(urlsplit(template).path).suffix.lower().lstrip(".")
    vector = resource.media_type in {
        "application/vnd.mapbox-vector-tile",
        "application/x-protobuf",
    }
    tile = {
        "scheme": "xyz",
        "url": template,
        "crs": "EPSG:3857",
        "tile_size": 256,
        "format": "pbf"
        if vector
        else suffix
        if suffix in {"png", "jpg", "jpeg", "webp", "pbf", "mvt"}
        else "raster",
        "attribution": resource.metadata.publisher or "",
    }
    return AccessPlan(
        "remote-dataset",
        resource.uri,
        format=resource.format,
        media_type=resource.media_type,
        provider=resource.reference.provider_id,
        options={"tile": tile},
    )


def tile_problem(tile):
    if not isinstance(tile, Mapping) or tile.get("scheme") != "xyz":
        return "XYZ以外のタイル方式は未対応"
    url = tile.get("url")
    if not isinstance(url, str):
        return "タイルURLが不正"
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or any("{" + axis + "}" not in url for axis in ("x", "y", "z"))
    ):
        return "HTTP(S)のXYZタイルURLが必要"
    if tile.get("crs") != "EPSG:3857" or tile.get("tile_size", 256) != 256:
        return "タイルはEPSG:3857・256ピクセルに対応"
    if any(
        key in tile and not isinstance(tile[key], str)
        for key in ("attribution", "coverage", "usage_notes", "usage_url")
    ):
        return "タイルの帰属・利用条件が不正"
    low, high = tile.get("min_zoom"), tile.get("max_zoom")
    if (
        any(
            value is not None and (type(value) is not int or not 0 <= value <= 30)
            for value in (low, high)
        )
        or low is not None
        and high is not None
        and low > high
    ):
        return "タイルのズーム範囲が不正"
    if tile.get("format") not in {"png", "jpg", "jpeg", "webp", "pbf", "mvt", "raster"}:
        return "タイルの画像・MVT形式が未対応"
    return None


def unsupported(plan):
    """Check delivery semantics; actual driver support is queried from QGIS."""
    if (
        plan.credential
        or plan.service
        or plan.kind == "service-query"
        or plan.format in {"wms", "wfs", "wmts", "api", "ogc-api-features"}
    ):
        return "認証・サービス形式は未対応"
    if "tile" in plan.options:
        if set(plan.options) != {"tile"}:
            return "タイルに未対応の追加オプションがあります"
        return tile_problem(plan.options["tile"])
    if set(plan.options) - {"archive", "entry_point", "encoding", "layer"}:
        return "このアクセスオプションは未対応"
    if plan.format in {None, "unknown"} or not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,31}", plan.format
    ):
        return "配信形式が不明、またはファイル形式が未対応"
    if plan.format == "shapefile" and plan.options.get("archive") != "zip":
        return "Shapefileは関連ファイルを含むZIP配布に対応"
    layer = plan.options.get("layer")
    if layer is not None and (
        isinstance(layer, bool) or not isinstance(layer, str | int)
    ):
        return "レイヤー指定が不正"
    if urlsplit(plan.uri).scheme not in {"http", "https"}:
        return "HTTP(S)配布のみ対応"
    return None


def unpack(path, plan):
    """Preserve sidecars and directories; never pick the first archive member."""
    directory = path.parent / "contents"
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise DownloadError("ZIPのエントリー上限（4096件）を超えています")
        destinations = set()
        for member in members:
            relative = PurePosixPath(member.filename)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in member.filename
                or ":" in member.filename
                or (member.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise DownloadError("ZIPに安全に展開できないパスがあります")
            key = str(relative).casefold()
            if key in destinations:
                raise DownloadError("ZIPに重複するパスがあります")
            destinations.add(key)
        directory.mkdir()
        for member in members:
            archive.extract(member, directory)
    entry = plan.options.get("entry_point")
    if entry is not None:
        selected = directory / entry
        if not selected.exists():
            raise DownloadError("ZIP内に指定されたデータがありません")
        return selected
    return directory


PROVIDER_ADAPTERS = {
    "geospatial-jp": GeospatialJpAdapter,
    "plateau": PlateauAdapter,
    "static": StaticAdapter,
    "odpt": OdptAdapter,
    "mlit-dpf": MlitDpfAdapter,
    "search-ckan-jp": SearchCkanJpAdapter,
    "stac": StacAdapter,
}

PROVIDER_LABELS = {
    "search-ckan-jp": "search.ckan.jp",
    "geospatial-jp": "G空間情報センター",
    "gsi": "国土地理院",
    "plateau": "PLATEAU",
    "mlit-dpf": "国土交通DPF",
    "odpt": "公共交通オープンデータ",
    "jaxa-gsmap-preview": "JAXA GSMaP（プレビュー）",
    "jaxa-aw3d-preview": "JAXA AW3D（プレビュー）",
    "jaxa-hrlulc-preview": "JAXA 土地被覆（プレビュー）",
}


def search_conditions(values):
    try:
        dates = values.get("time")
        query = SearchQuery(
            text=values.get("text") or None,
            area=values.get("area") or None,
            bbox=tuple(values["bbox"]) if values.get("bbox") is not None else None,
            time=tuple(
                datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None
                for v in dates
            )
            if dates
            else None,
            format=tuple(Format(v) for v in values["format"])
            if values.get("format")
            else None,
            limit=values.get("limit"),
            providers=values["providers"],
        )
    except (ValueError, TypeError, KeyError) as error:
        raise DownloadError(
            "検索条件を確認してください（日時はISO8601、bboxは西・南・東・北の4数値）"
        ) from error
    except ConfigValidationError as error:
        raise DownloadError("検索条件が不正です: " + str(error)) from error
    return query


def execute(request):
    if request["action"] == "catalog":
        return {
            "providers": [
                {
                    "id": p.id,
                    "label": PROVIDER_LABELS.get(p.id, p.id),
                    "searchable": callable(
                        getattr(PROVIDER_ADAPTERS.get(p.adapter_type), "search", None)
                    ),
                    "default": p.id
                    in {
                        ProviderId.SEARCH_CKAN_JP,
                        ProviderId.GEOSPATIAL_JP,
                        ProviderId.GSI,
                    },
                }
                for p in BUILTIN
            ],
            "formats": [{"id": f.value, "label": f.value} for f in Format],
        }
    if request["action"] == "search":
        query = search_conditions(request["conditions"])
        try:
            results = search(query)
        except ConfigValidationError as error:
            raise DownloadError("検索条件が不正です: " + str(error)) from error
        rows = []
        app = configure()
        for resource in results:
            plan = None
            try:
                plan = plan_for(resource, app)
                reason = unsupported(plan)
            except Exception as error:
                reason = f"AccessPlanを作成できません ({type(error).__name__})"
            rows.append(
                {
                    "resource": resource.to_dict(),
                    "title": resource.title,
                    "provider": resource.metadata.publisher or resource.discovered_by,
                    "source_id": resource.discovered_by,
                    "skipped_conditions": sorted(
                        {
                            condition
                            for d in results.diagnostics
                            if d.source_id == resource.discovered_by
                            for condition in d.skipped_conditions
                        }
                    ),
                    "format": "XYZタイル"
                    if plan and "tile" in plan.options
                    else resource.format or "不明",
                    "reason": reason,
                }
            )
        # Stable partition only: no provider or relevance ranking in the UI.
        rows.sort(key=lambda row: row["reason"] is not None)
        diagnostics = [
            {
                "provider": d.source_id,
                "reason": d.reason,
                "failure_type": d.failure_type,
                "skipped_conditions": sorted(d.skipped_conditions),
                "missing_conditions": sorted(d.missing_conditions),
                "detail": d.detail,
            }
            for d in results.diagnostics
        ]
        return {"rows": rows, "diagnostics": diagnostics}
    if request["action"] != "download":
        raise ValueError("Unknown worker action")
    resource = Resource.from_dict(request["resource"])
    plan = plan_for(resource, configure())
    reason = unsupported(plan)
    if reason:
        raise DownloadError(reason)
    if "tile" in plan.options:
        return {
            "tile": plan.to_dict()["options"]["tile"],
            "resource": resource.to_dict(),
            "plan": plan.to_dict(),
        }
    archive = plan.options.get("archive") == "zip" or plan.format == "zip"
    target = Path(request["target"]).with_suffix(
        ".zip" if archive else SUFFIXES.get(plan.format, "." + plan.format)
    )
    # The GUI supplies an exclusive temporary directory owned by this request.
    partial = target.with_suffix(".part")
    try:
        with urlopen(plan.uri, timeout=30) as response, partial.open("xb") as stream:
            if urlsplit(response.url).scheme not in {"http", "https"}:
                raise ValueError("Unsupported redirect")
            while chunk := response.read(65536):
                stream.write(chunk)
        os.replace(partial, target)
        source = unpack(target, plan) if archive else target
    except Exception as error:
        target.unlink(missing_ok=True)
        shutil.rmtree(target.parent / "contents", ignore_errors=True)
        if isinstance(error, OSError) and error.errno == errno.ENOSPC:
            raise DownloadError("保存先の空き容量が不足しています") from error
        raise
    finally:
        partial.unlink(missing_ok=True)
    return {"path": str(source), "resource": resource.to_dict(), "plan": plan.to_dict()}


def main():
    try:
        result = {"ok": True, "result": execute(json.load(sys.stdin))}
    except Exception as error:
        # Avoid leaking URLs/credentials through exception messages.
        result = {
            "ok": False,
            "error": str(error)
            if isinstance(error, DownloadError)
            else type(error).__name__,
        }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    main()
