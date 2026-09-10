"""Authorize network destinations embedded in GDAL runtime locators."""

from typing import Tuple
from urllib.parse import parse_qs

from ...errors import DestinationNotAllowedError
from ...security import DestinationPolicy, DestinationRule

_ARCHIVE_PREFIXES = (
    "/vsizip/",
    "/vsitar/",
    "/vsigzip/",
    "/vsi7z/",
    "/vsirar/",
)
_NETWORK_PREFIXES = ("/vsicurl/", "/vsicurl_streaming/")
_LOCAL_PREFIXES = ("/vsimem/",)


def authorize_runtime_locator(
    locator: str, destination_policy: DestinationPolicy
) -> None:
    """Authorize HTTP(S) destinations represented by a GDAL runtime locator."""
    if destination_policy.level != "strict" or not locator.startswith("/vsi"):
        destination_policy.authorize(locator)
        return

    for destination in _network_destinations(locator):
        destination_policy.authorize(destination)


def _network_destinations(locator: str) -> Tuple[str, ...]:
    direct = DestinationRule.from_url(locator)
    if direct is not None:
        return (locator,)

    for prefix in _NETWORK_PREFIXES:
        if locator.startswith(prefix):
            destination = locator[len(prefix) :]
            if DestinationRule.from_url(destination) is None:
                raise _unsupported_locator()
            return (destination,)

    if locator.startswith("/vsicurl?"):
        try:
            values = parse_qs(
                locator.removeprefix("/vsicurl?"),
                keep_blank_values=True,
                max_num_fields=64,
            ).get("url", [])
        except ValueError as error:
            raise _unsupported_locator() from error
        if len(values) != 1 or DestinationRule.from_url(values[0]) is None:
            raise _unsupported_locator()
        return (values[0],)

    for prefix in _ARCHIVE_PREFIXES:
        if locator.startswith(prefix):
            nested = _nested_archive_locator(locator[len(prefix) :])
            return () if nested is None else _network_destinations(nested)

    if locator.startswith(_LOCAL_PREFIXES):
        return ()

    raise _unsupported_locator()


def _nested_archive_locator(payload: str) -> str | None:
    if payload.startswith("{"):
        depth = 0
        for index, character in enumerate(payload):
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return payload[1:index]
        raise _unsupported_locator()
    if payload.startswith("/vsi"):
        return payload
    if payload.startswith("vsi"):
        return "/" + payload
    if DestinationRule.from_url(payload) is not None:
        return payload
    return None


def _unsupported_locator() -> DestinationNotAllowedError:
    return DestinationNotAllowedError(
        "GDAL runtime locator is not an authorized HTTP(S) destination"
    )


__all__ = ["authorize_runtime_locator"]
