"""Resolve one explicitly selected G Spatial Information Center CKAN resource."""

import os
import sys
from pathlib import Path

from rhinestone import Config, configure, sources

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support.http_json import get_json  # noqa: E402

resource_id = os.environ["RHINESTONE_CKAN_RESOURCE_ID"]
app = configure(
    sources=(sources.GEOSPATIAL_JP,),
    dependencies={"http-json": lambda: get_json},
)
resource = app.resolve(
    Config(
        source_id="geospatial-jp",
        settings={"resource_id": resource_id},
    )
)

print("URI:", resource.uri)
print("format:", resource.format)
print("metadata:", resource.metadata)
print("access plan:", resource.access_plan)
print("provenance:", resource.provenance)
