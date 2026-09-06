"""Fetch ODPT station JSON with a lazily injected consumer key."""

import os

from rhinestone import Config, configure, sources

app = configure(
    sources=(sources.ODPT,),
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
