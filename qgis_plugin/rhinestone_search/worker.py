"""One request per isolated Python process; no QGIS or private Core APIs."""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

# -I -S excludes user/system site packages. Never alter QGIS's import paths.
sys.path.insert(0, str(Path(__file__).parent / "vendor"))

from rhinestone import ProviderId, Resource, configure, search  # noqa: E402

MAX_BYTES = 50 * 1024 * 1024


class DownloadError(ValueError):
    """A safe, user-readable download rejection."""


def unsupported(plan):
    """Only explicitly declared standalone HTTP(S) GeoJSON is supported."""
    if plan.credential or plan.service or plan.kind == "service-query":
        return "認証・サービス形式は未対応"
    if plan.options:
        return "ZIP・追加オプション付きの配布は未対応"
    if plan.format != "geojson":
        return "初期版はGeoJSONのみ対応"
    if urlsplit(plan.uri).scheme not in {"http", "https"}:
        return "HTTP(S)配布のみ対応"
    # QGIS OGR URI separators must never be interpreted as provider options.
    return None


def execute(request):
    if request["action"] == "search":
        results = search(
            providers=[ProviderId.SEARCH_CKAN_JP], text=request["text"], limit=20
        )
        rows = []
        app = configure()
        for resource in results:
            try:
                reason = unsupported(app.plan(resource))
            except Exception as error:
                reason = f"AccessPlanを作成できません ({type(error).__name__})"
            rows.append(
                {
                    "resource": resource.to_dict(),
                    "title": resource.title,
                    "provider": resource.metadata.publisher or resource.discovered_by,
                    "format": resource.format or "不明",
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
            }
            for d in results.diagnostics
        ]
        return {"rows": rows, "diagnostics": diagnostics}
    if request["action"] != "download":
        raise ValueError("Unknown worker action")
    resource = Resource.from_dict(request["resource"])
    plan = configure().plan(resource)
    reason = unsupported(plan)
    if reason:
        raise DownloadError(reason)
    target = Path(request["target"])
    # The GUI supplies an exclusive temporary directory owned by this request.
    partial = target.with_suffix(".part")
    try:
        with urlopen(plan.uri, timeout=30) as response, partial.open("xb") as stream:
            if urlsplit(response.url).scheme not in {"http", "https"}:
                raise ValueError("Unsupported redirect")
            total = 0
            while chunk := response.read(65536):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise DownloadError("50 MiBを超える配布は未対応")
                stream.write(chunk)
        # Check JSON syntax before handing the local file to OGR; no conversion.
        with partial.open(encoding="utf-8-sig") as stream:
            document = json.load(stream)
        if not isinstance(document, dict) or document.get("type") not in {
            "FeatureCollection",
            "Feature",
            "Point",
            "MultiPoint",
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
            "GeometryCollection",
        }:
            raise DownloadError("GeoJSONではない応答")
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return {"path": str(target), "resource": resource.to_dict(), "plan": plan.to_dict()}


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
