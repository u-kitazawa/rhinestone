"""Bounded HTTP byte ranges around Python's standard ZIP reader.

Only the central directory and model declarations are read before selection.
Payload read-ahead never crosses the selected ZIP member's physical boundary.
"""

import hashlib
import io
import json
import posixpath
import re
import shutil
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from archive_layers import scene_references, tile_bounds, validate_members


class RangeUnsupported(ValueError):
    def __init__(self, size=None):
        super().__init__("配信先がZIPの部分取得に対応していません")
        self.size = size


class ArchiveChanged(ValueError):
    def __init__(self):
        super().__init__("配布物が変更されました。もう一度候補を確認してください")


class RangeFile(io.RawIOBase):
    def __init__(self, url, expected=None):
        super().__init__()
        self.url = url
        self.position = 0
        self.member_end = None
        self.cache_start = 0
        self.cache = b""
        self.received = 0
        self.snapshot = None
        self.expected = expected
        self.cache_start, self.cache, self.size = self.fetch("bytes=-22")

    def fetch(self, byte_range):
        headers = {"Range": byte_range, "Accept-Encoding": "identity"}
        prior = self.snapshot or self.expected
        if prior:
            validator = prior.get("etag")
            if validator and not validator.startswith("W/"):
                headers["If-Range"] = validator
            elif prior.get("modified"):
                headers["If-Range"] = prior["modified"]
        with urlopen(Request(self.url, headers=headers), timeout=30) as response:
            if response.status != 206:
                if prior:
                    raise ArchiveChanged()
                value = response.headers.get("Content-Length", "")
                raise RangeUnsupported(int(value) if value.isdigit() else None)
            match = re.fullmatch(
                r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
            )
            if (
                not match
                or response.headers.get("Content-Encoding", "identity") != "identity"
            ):
                raise ValueError("ZIPの部分取得応答が不正です")
            start, end, size = map(int, match.groups())
            if not 0 <= start <= end < size:
                raise ValueError("ZIPの部分取得範囲が不正です")
            if byte_range.startswith("bytes=-"):
                valid = end == size - 1 and start == max(0, size - int(byte_range[7:]))
            else:
                low, high = map(int, byte_range[6:].split("-"))
                valid = start == low and end == min(high, size - 1)
            if not valid:
                raise ValueError("要求と異なるZIPの部分取得範囲です")
            snapshot = {
                "size": size,
                "etag": response.headers.get("ETag"),
                "modified": response.headers.get("Last-Modified"),
                "url": response.url,
            }
            if prior and any(snapshot[k] != prior[k] for k in snapshot):
                raise ArchiveChanged()
            self.snapshot = snapshot
            data = response.read(end - start + 2)
            if len(data) != end - start + 1:
                raise ValueError("ZIPの部分取得が途中で終了しました")
            self.received += len(data)
            return start, data, size

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset + (
            self.position if whence == 1 else self.size if whence == 2 else 0
        )
        if position < 0:
            raise ValueError("ZIPの読取位置が不正です")
        self.position = position
        return position

    def read(self, size=-1):
        size = (
            self.size - self.position
            if size < 0
            else min(size, self.size - self.position)
        )
        if size <= 0:
            return b""
        if (
            not self.cache_start <= self.position
            or self.position + size > self.cache_start + len(self.cache)
        ):
            count = size
            if self.member_end is not None:
                count = min(max(size, 262144), self.member_end - self.position)
            end = self.position + max(count, size) - 1
            self.cache_start, self.cache, _ = self.fetch(f"bytes={self.position}-{end}")
        offset = self.position - self.cache_start
        data = self.cache[offset : offset + size]
        self.position += len(data)
        return data


def member_name(info):
    return str(PurePosixPath(info.filename))


def directory_token(archive):
    records = [
        (
            i.filename,
            i.CRC,
            i.file_size,
            i.compress_size,
            i.header_offset,
            i.compress_type,
            i.external_attr,
            i.flag_bits,
        )
        for i in archive.infolist()
    ]
    return hashlib.sha256(json.dumps(records, ensure_ascii=False).encode()).hexdigest()


def member_limits(archive):
    offsets = sorted(i.header_offset for i in archive.infolist()) + [archive.start_dir]
    return dict(zip(offsets, offsets[1:]))


def inventory(archive, reader, only=None):
    members = archive.infolist()
    validate_members(members)
    names = {member_name(i) for i in members}
    records = [(member_name(i), i) for i in members]
    limits = member_limits(archive)
    models, referenced = [], set()
    for info in members:
        path = PurePosixPath(member_name(info))
        group = str(path.parent)
        if (
            info.is_dir()
            or path.name not in {"tileset.json", "metadata.json"}
            or group == "."
            or only is not None
            and group not in only
        ):
            continue
        reader.member_end = limits[info.header_offset]
        try:
            with archive.open(info) as stream:
                document = json.load(stream)
        except (UnicodeError, json.JSONDecodeError):
            continue
        finally:
            reader.member_end = None
        if not isinstance(document, dict):
            continue
        candidate = {"id": group, "name": group, "path": str(path)}
        if isinstance(document.get("asset"), dict) and "root" in document:
            candidate["kind"] = "scene"
            try:
                for uri in scene_references(document):
                    parsed = urlsplit(uri)
                    target = posixpath.normpath(
                        posixpath.join(group, unquote(parsed.path))
                    )
                    if (
                        parsed.scheme
                        or parsed.netloc
                        or parsed.query
                        or parsed.fragment
                        or parsed.path.startswith("/")
                        or target.startswith("../")
                        or target not in names
                        or not target.startswith(group + "/")
                    ):
                        raise ValueError("3D Tilesの参照先が同梱されていません")
                    if target.endswith(".json"):
                        referenced.add(target)
            except (ValueError, TypeError, AttributeError):
                candidate["reason"] = "3D Tilesの参照・構造が未対応です"
        elif document.get("format") in {"pbf", "mvt"}:
            candidate["kind"] = "vector-tile"
            tiles = [
                n
                for n in names
                if n.startswith(group + "/")
                and re.fullmatch(r"\d+/\d+/\d+\.(?:mvt|pbf)", n[len(group) + 1 :])
            ]
            if not tiles:
                continue
            suffixes = {PurePosixPath(n).suffix for n in tiles}
            low, high = document.get("minzoom"), document.get("maxzoom")
            if (
                len(suffixes) != 1
                or document.get("scheme", "xyz") != "xyz"
                or type(low) is not int
                or type(high) is not int
                or not 0 <= low <= high <= 30
            ):
                candidate["reason"] = "MVTの方式・ズーム範囲・拡張子が未対応です"
            candidate["bounds"] = tile_bounds(document.get("bounds"))
        else:
            continue
        # A model is a complete directory, including textures and sidecars.
        selected = [i for name, i in records if name.startswith(group + "/")]
        candidate["compressed_size"] = sum(i.compress_size for i in selected)
        candidate["unpacked_size"] = sum(i.file_size for i in selected)
        models.append(candidate)
    models = [m for m in models if m["path"] not in referenced]
    counts = Counter(m["id"] for m in models)
    for model in models:
        if counts[model["id"]] > 1:
            model["reason"] = "同じディレクトリの複数の入口を分離して部分取得できません"
    return models


def inspect(url):
    with RangeFile(url) as reader, zipfile.ZipFile(reader) as archive:
        models = inventory(archive, reader)
        return {
            "models": models,
            "snapshot": {**reader.snapshot, "directory": directory_token(archive)},
            "size": reader.size,
            "received": reader.received,
        }


def extract_selected(url, snapshot, groups, target):
    if (
        not isinstance(groups, list)
        or not groups
        or any(not isinstance(g, str) or not g or g == "." for g in groups)
    ):
        raise ValueError("取得するモデルを選択してください")
    directory = Path(target)
    created = False
    try:
        with RangeFile(url, snapshot) as reader, zipfile.ZipFile(reader) as archive:
            if directory_token(archive) != snapshot.get("directory"):
                raise ArchiveChanged()
            models = inventory(archive, reader, set(groups))
            if set(groups) != {m["id"] for m in models if not m.get("reason")}:
                raise ValueError("指定モデルを部分取得できません")
            members = archive.infolist()
            limits = member_limits(archive)
            directory.mkdir()
            created = True
            for info in members:
                if any(member_name(info).startswith(g + "/") for g in groups):
                    reader.member_end = limits[info.header_offset]
                    archive.extract(info, directory)
            return reader.received
    except Exception:
        if created:
            shutil.rmtree(directory, ignore_errors=True)
        raise
