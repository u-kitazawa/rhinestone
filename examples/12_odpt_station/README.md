# ODPT Station

## Setup

Register with ODPT, install Rhinestone, and set `ODPT_CONSUMER_KEY`. HTTP communication uses Rhinestone's built-in transport. Run `python examples/12_odpt_station/example.py`.

The consumer key is resolved only when the request is opened. It is never put
in Config, Source metadata, or Provenance.
