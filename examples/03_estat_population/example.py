"""Resolve e-Stat metadata as a service-query Resource."""

import os

from rhinestone import Config, configure, sources

app_id = (
    os.environ.get("RHINESTONE_ESTAT_APP_ID") or os.environ["RHINESTONE_ESTAT_API_KEY"]
)
stats_data_id = os.environ["RHINESTONE_ESTAT_STATS_DATA_ID"]
app = configure(
    sources=(sources.ESTAT,),
    credentials={"estat": lambda: app_id},
)
resource = app.resolve(
    Config(source_id="estat", settings={"stats_data_id": stats_data_id})
)

print("URI:", resource.uri)
print("metadata:", resource.metadata)
print("access plan:", resource.access_plan)
print("provenance:", resource.provenance)
