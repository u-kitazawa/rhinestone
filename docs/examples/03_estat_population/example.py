"""Resolve e-Stat metadata as a service-query Resource."""

import os
import sys
from pathlib import Path

from rhinestone import Config, configure
from rhinestone.adapters import EStatAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support.http_json import get_json  # noqa: E402

app_id = (
    os.environ.get("RHINESTONE_ESTAT_APP_ID") or os.environ["RHINESTONE_ESTAT_API_KEY"]
)
stats_data_id = os.environ["RHINESTONE_ESTAT_STATS_DATA_ID"]
app = configure(
    dependencies={},
    source_adapters=(EStatAdapter(api_key=app_id, get_json=get_json),),
    execution_adapters=(),
)
resource = app.resolve(
    Config(source_type="estat", settings={"stats_data_id": stats_data_id})
)

print("URI:", resource.uri)
print("metadata:", resource.metadata)
print("access plan:", resource.access_plan)
print("provenance:", resource.provenance)
