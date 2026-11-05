"""Find logical tile datasets in an extracted distribution, without QGIS imports."""

import json
import math
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


def validate_members(members):
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
            raise ValueError("ZIPに安全に展開できないパスがあります")
        key = str(relative).casefold()
        if key in destinations:
            raise ValueError("ZIPに重複するパスがあります")
        destinations.add(key)


def local_reference(base, uri, root):
    parsed = urlsplit(uri)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("ZIP内の3D Tilesは同梱された相対参照に対応しています")
    path = (base / unquote(parsed.path)).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("3D Tilesの参照先がZIP内にありません")
    return path


def scene_references(document):
    stack = [document["root"]]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            raise ValueError("3D Tilesの構造が不正です")
        stack.extend(node.get("children", []))
        contents = node.get("contents", [])
        if "content" in node:
            contents = [*contents, node["content"]]
        for content in contents:
            uri = content.get("uri", content.get("url"))
            if not isinstance(uri, str):
                raise ValueError("3D Tilesの参照先が不正です")
            yield uri


def tile_bounds(value):
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bounds = [float(v) for v in value]
    except (ValueError, TypeError):
        return None
    west, south, east, north = bounds
    if (
        not all(math.isfinite(v) for v in bounds)
        or not -180 <= west <= east <= 180
        or not -90 <= south <= north <= 90
    ):
        return None
    return bounds


def discover_tiles(path):
    root = Path(path).resolve()
    if root.is_file() and root.suffix.lower() == ".json":
        documents = [root]
        root = root.parent
    elif root.is_dir():
        documents = sorted(root.rglob("*.json"))
    else:
        return {"tile_layers": [], "tile_roots": []}
    scenes, vectors, roots, referenced = [], [], set(), set()
    for source in documents:
        try:
            document = json.loads(source.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(document, dict):
            continue
        name = str(source.parent.relative_to(root))
        if name == ".":
            name = source.parent.name
        if isinstance(document.get("asset"), dict) and "root" in document:
            candidate = {"kind": "scene", "path": str(source), "name": name}
            try:
                region = document["root"].get("boundingVolume", {}).get("region")
                if isinstance(region, list) and len(region) == 6:
                    candidate["bounds"] = tile_bounds(
                        [math.degrees(v) for v in region[:4]]
                    )
                for uri in scene_references(document):
                    target = local_reference(source.parent, uri, root)
                    if target.suffix.lower() == ".json":
                        referenced.add(str(target))
            except (ValueError, TypeError, AttributeError) as error:
                candidate["reason"] = (
                    str(error)
                    if isinstance(error, ValueError)
                    else "3D Tilesの構造が不正です"
                )
            scenes.append(candidate)
            roots.add(str(source.parent))
        elif document.get("format") in {"pbf", "mvt"}:
            # Tippecanoe directory metadata declares MVT. Derive the local
            # template only from files actually present in its z/x/y hierarchy.
            tiles = [
                p
                for p in source.parent.glob("*/*/*")
                if p.is_file()
                and re.fullmatch(
                    r"\d+/\d+/\d+\.(?:mvt|pbf)", p.relative_to(source.parent).as_posix()
                )
            ]
            if not tiles:
                continue
            roots.add(str(source.parent))
            suffixes = {p.suffix for p in tiles}
            candidate = {"kind": "vector-tile", "path": str(source), "name": name}
            low, high = document.get("minzoom"), document.get("maxzoom")
            if (
                len(suffixes) != 1
                or document.get("scheme", "xyz") != "xyz"
                or type(low) is not int
                or type(high) is not int
                or not 0 <= low <= high <= 30
            ):
                candidate["reason"] = "MVTの方式・ズーム範囲・拡張子を特定できません"
            else:
                candidate.update(
                    url=source.parent.as_uri() + "/{z}/{x}/{y}" + next(iter(suffixes)),
                    min_zoom=low,
                    max_zoom=high,
                    bounds=tile_bounds(document.get("bounds")),
                )
            vectors.append(candidate)
    return {
        "tile_layers": [c for c in scenes if c["path"] not in referenced] + vectors,
        "tile_roots": sorted(roots),
    }
