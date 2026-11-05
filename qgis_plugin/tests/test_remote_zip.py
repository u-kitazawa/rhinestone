"""Exercise actual HTTP ranges, ZIP validation, and selection boundaries."""

import importlib.util
import io
import json
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "rhinestone_search"))
import remote_zip  # noqa: E402


def fixture_bytes():
    data = io.BytesIO(
        (ROOT / "tests/fixtures/plateau-saitama-2023-sample.zip").read_bytes()
    )
    with zipfile.ZipFile(data, "a") as archive:
        archive.writestr(
            "unused/tileset.json",
            json.dumps(
                {"asset": {"version": "1.0"}, "root": {"content": {"uri": "tile.b3dm"}}}
            ),
        )
        archive.writestr(
            "unused/tile.b3dm",
            b"x" * (5 * 1024 * 1024),
            compress_type=zipfile.ZIP_STORED,
        )
    return data.getvalue()


class Server:
    def __init__(self, data, ranges=True):
        self.data = data
        self.ranges = ranges
        self.etag = '"version-one"'
        self.requests = []
        self.bad_range = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                header = self.headers.get("Range")
                owner.requests.append(header)
                if header and owner.ranges:
                    low, high = header[6:].split("-")
                    start = int(low) if low else max(0, len(owner.data) - int(high))
                    end = (
                        min(int(high), len(owner.data) - 1)
                        if low
                        else len(owner.data) - 1
                    )
                    self.send_response(206)
                    declared = start + 1 if owner.bad_range else start
                    self.send_header(
                        "Content-Range", f"bytes {declared}-{end}/{len(owner.data)}"
                    )
                    body = owner.data[start : end + 1]
                else:
                    self.send_response(200)
                    body = owner.data
                self.send_header("ETag", owner.etag)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self.server.server_port}/data.zip"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def test_preview_and_selection_never_fetch_unselected_model_payload(tmp_path):
    data = fixture_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        info = original.getinfo("unused/tile.b3dm")
        payload_start = info.header_offset + 30 + len(info.filename.encode())
        payload_end = payload_start + info.compress_size - 1
    with Server(data) as server:
        preview = remote_zip.inspect(server.url)
        assert len(preview["models"]) == 3
        assert preview["received"] < len(data) / 2
        groups = [m["id"] for m in preview["models"] if m["id"] != "unused"]
        received = remote_zip.extract_selected(
            server.url, preview["snapshot"], groups, tmp_path / "selected"
        )
        assert received < len(data) / 2
        assert not (tmp_path / "selected/unused").exists()
        with zipfile.ZipFile(io.BytesIO(data)) as original:
            for path in (tmp_path / "selected").rglob("*"):
                if path.is_file():
                    assert path.read_bytes() == original.read(
                        path.relative_to(tmp_path / "selected").as_posix()
                    )
        for header in server.requests:
            assert header is not None
            low, high = header[6:].split("-")
            if low:
                start, end = int(low), int(high)
            else:
                start, end = len(data) - int(high), len(data) - 1
            assert end < payload_start or start > payload_end


def test_unsupported_ranges_do_not_fall_back_to_reading_entire_zip():
    with Server(fixture_bytes(), ranges=False) as server:
        with pytest.raises(remote_zip.RangeUnsupported) as error:
            remote_zip.inspect(server.url)
        assert error.value.size == len(server.data)
        assert server.requests == ["bytes=-22"]


def test_changed_archive_is_rejected_before_extracting(tmp_path):
    with Server(fixture_bytes()) as server:
        preview = remote_zip.inspect(server.url)
        server.etag = '"version-two"'
        with pytest.raises(remote_zip.ArchiveChanged):
            remote_zip.extract_selected(
                server.url,
                preview["snapshot"],
                [preview["models"][0]["id"]],
                tmp_path / "selected",
            )
        assert not (tmp_path / "selected").exists()


def test_change_during_declaration_read_aborts_preview(monkeypatch):
    original = remote_zip.RangeFile.fetch
    with Server(fixture_bytes()) as server:

        def changed_fetch(reader, byte_range):
            if reader.member_end is not None:
                server.etag = '"version-two"'
            return original(reader, byte_range)

        monkeypatch.setattr(remote_zip.RangeFile, "fetch", changed_fetch)
        with pytest.raises(remote_zip.ArchiveChanged):
            remote_zip.inspect(server.url)


def test_changed_directory_is_rejected_even_if_validator_is_reused(tmp_path):
    with Server(fixture_bytes()) as server:
        preview = remote_zip.inspect(server.url)
        preview["snapshot"]["directory"] = "not-the-same-directory"
        with pytest.raises(remote_zip.ArchiveChanged):
            remote_zip.extract_selected(
                server.url,
                preview["snapshot"],
                [preview["models"][0]["id"]],
                tmp_path / "selected",
            )
        assert not (tmp_path / "selected").exists()


def test_ranges_disabled_after_selection_do_not_trigger_whole_download(tmp_path):
    with Server(fixture_bytes()) as server:
        preview = remote_zip.inspect(server.url)
        server.ranges = False
        with pytest.raises(remote_zip.ArchiveChanged):
            remote_zip.extract_selected(
                server.url,
                preview["snapshot"],
                [preview["models"][0]["id"]],
                tmp_path / "selected",
            )
        assert not (tmp_path / "selected").exists()
        assert all(h is not None for h in server.requests)


def test_corrupted_selected_payload_is_rejected_and_removed(tmp_path):
    data = fixture_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo("unused/tile.b3dm")
        offset = info.header_offset + 30 + len(info.filename.encode())
    with Server(data) as server:
        preview = remote_zip.inspect(server.url)
        server.data = data[:offset] + b"y" + data[offset + 1 :]
        with pytest.raises(zipfile.BadZipFile, match="CRC"):
            remote_zip.extract_selected(
                server.url, preview["snapshot"], ["unused"], tmp_path / "selected"
            )
        assert not (tmp_path / "selected").exists()


def test_wrong_content_range_is_rejected():
    with Server(fixture_bytes()) as server:
        server.bad_range = True
        with pytest.raises(ValueError, match="範囲"):
            remote_zip.inspect(server.url)


@pytest.mark.parametrize("groups", [[], ["../outside"], ["not-a-model"]])
def test_invalid_selection_cannot_extract_other_files(tmp_path, groups):
    with Server(fixture_bytes()) as server:
        preview = remote_zip.inspect(server.url)
        with pytest.raises(ValueError):
            remote_zip.extract_selected(
                server.url, preview["snapshot"], groups, tmp_path / "selected"
            )
        assert not (tmp_path / "selected").exists()


def test_worker_reports_required_confirmation_for_ordinary_zip():
    spec = importlib.util.spec_from_file_location(
        "range_worker", ROOT / "rhinestone_search/worker.py"
    )
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("data.csv", "name\npark")
    with Server(buffer.getvalue()) as server:
        from rhinestone import Reference, configure

        selected = configure().load(
            Reference("direct", parameters={"uri": server.url, "format": "zip"})
        )
        result = worker.execute(
            {"action": "inspect_archive", "resource": selected.to_dict()}
        )
        assert result["archive_preview"]["whole_required"]
        assert all(h is not None for h in server.requests)
