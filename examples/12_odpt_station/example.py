"""Fetch ODPT station JSON with a lazily injected consumer key."""

import os

from rhinestone import Reference, configure
from rhinestone.catalogs import BUILTIN, Catalog

app = configure(
    catalog=Catalog(provider for provider in BUILTIN if provider.id == "odpt"),
    credentials={"odpt": lambda: os.environ["ODPT_CONSUMER_KEY"]},
)
records = app.open(
    Reference(
        "odpt",
        parameters={
            "dataset": "station",
            "credential": "odpt",
            "filters": {"dc:title": "東京"},
        },
    )
)
print("records:", len(records))
print("first identifier:", records[0]["owl:sameAs"] if records else "none")
