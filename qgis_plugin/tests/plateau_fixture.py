"""Opt-in live fixture from the user's reported PLATEAU distribution.

Fetch complete road-LOD3 and square-LOD2 models through ZIP byte ranges. No
model/tile bytes are rewritten. The 2.19 GB archive need not be copied to CI.
Source: Saitama City 2023, Project PLATEAU, resource
6c1e9342-c282-462d-9b16-2da5513db3ce; PLATEAU site policy applies.
"""

import io
import re
import zipfile
from urllib.request import Request, urlopen

URL = "https://assets.cms.plateau.reearth.io/assets/f7/838da1-f754-4325-86ef-5b62c788dd94/11100_saitama-shi_city_2023_3dtiles_mvt_1_op.zip"
PREFIX = "11100_saitama-shi_city_2023_citygml_1_op_"
MODELS = (PREFIX + "tran_3dtiles_lod3/", PREFIX + "squr_mvt_lod2/")


class RangeFile(io.RawIOBase):
    def __init__(self):
        super().__init__()
        with urlopen(
            Request(URL, headers={"Range": "bytes=-65557"}), timeout=60
        ) as response:
            if response.status != 206:
                raise ValueError("Fixture server must support byte ranges")
            self.size = int(response.headers["Content-Range"].split("/")[-1])
            self.cache = response.read()
        self.start = self.size - len(self.cache)
        self.position = 0

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (
            self.position if whence == 1 else self.size if whence == 2 else 0
        )
        return self.position

    def read(self, size=-1):
        size = (
            self.size - self.position
            if size < 0
            else min(size, self.size - self.position)
        )
        if size <= 0:
            return b""
        if not self.start <= self.position or self.position + size > self.start + len(
            self.cache
        ):
            end = min(self.size - 1, self.position + max(size, 2 * 1024 * 1024) - 1)
            with urlopen(
                Request(URL, headers={"Range": f"bytes={self.position}-{end}"}),
                timeout=60,
            ) as response:
                if response.status != 206 or not response.headers.get(
                    "Content-Range", ""
                ).startswith(f"bytes {self.position}-"):
                    raise ValueError("Unexpected fixture byte range")
                self.cache = response.read(end - self.position + 2)
            self.start = self.position
        offset = self.position - self.start
        data = self.cache[offset : offset + size]
        self.position += len(data)
        return data


def archive_bytes(local_path=None):
    source = local_path if local_path else RangeFile()
    output = io.BytesIO()
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as selected,
    ):
        for info in original.infolist():
            if info.filename.startswith(MODELS):
                selected.writestr(info.filename, original.read(info))
    with zipfile.ZipFile(output) as check:
        assert any(re.search(r"/\d+/\d+/\d+\.mvt$", name) for name in check.namelist())
        assert any(name.endswith("tileset.json") for name in check.namelist())
    return output.getvalue()
