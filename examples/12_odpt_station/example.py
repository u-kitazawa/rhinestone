"""Fetch ODPT station JSON with a lazily injected consumer key."""

import os

import requests

from rhinestone import Config, configure
from rhinestone.adapters import OdptAdapter
from rhinestone.execution_adapters import JsonServiceAdapter

app = configure(
    dependencies={"json-service": lambda: requests},
    source_adapters=(OdptAdapter(),),
    execution_adapters=(JsonServiceAdapter(OdptAdapter.prepare_request, "odpt"),),
    credentials={"odpt": lambda: os.environ["ODPT_CONSUMER_KEY"]},
)
records = app.open(
    Config(
        "odpt",
        {"dataset": "station", "credential": "odpt", "filters": {"dc:title": "東京"}},
    )
)
print("records:", len(records))
print("first identifier:", records[0]["owl:sameAs"] if records else "none")
