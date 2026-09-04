"""Minimal standard-library JSON transport for live examples."""

import json
from typing import Any, Mapping, Optional, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get_json(
    url: str,
    params: Mapping[str, Any],
    headers: Optional[Mapping[str, str]] = None,
) -> Mapping[str, Any]:
    query = urlencode(params)
    request_url = url + ("?" + query if query else "")
    request = Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "rhinestone-example",
            **dict(headers or {}),
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    return cast(Mapping[str, Any], payload)
