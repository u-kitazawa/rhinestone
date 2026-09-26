"""Bundled Japanese administrative-area snapshot.

Data is intentionally isolated from resolution logic so that a later snapshot
can be reviewed and replaced without changing adapter behavior.
"""

from .models import AdministrativeArea
from .space import BoundingBox

JAPAN_ADMINISTRATIVE_AREAS = (
    AdministrativeArea(
        canonical_name="神奈川県",
        code="14",
        aliases=("神奈川", "Kanagawa"),
        bbox=BoundingBox(138.915784, 35.128768, 139.798226, 35.675618),
        snapshot_date="2024-01-01",
        source_url="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html",
    ),
)

__all__ = ["JAPAN_ADMINISTRATIVE_AREAS"]
