"""Authorize network destinations embedded in GDAL runtime locators."""

from typing import Tuple
from urllib.parse import parse_qs, urlsplit, urlunsplit

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
            return () if nested is None else _archive_destinations(nested)

    if locator.startswith(_LOCAL_PREFIXES):
        return ()

    raise _unsupported_locator()


def _archive_destinations(nested: str) -> Tuple[str, ...]:
    if DestinationRule.from_url(nested) is not None:
        return (_archive_url(nested),)
    for prefix in _NETWORK_PREFIXES:
        if nested.startswith(prefix):
            return (_archive_url(nested[len(prefix) :]),)
    if nested.startswith("/vsicurl?"):
        raise _unsupported_locator()
    return _network_destinations(nested)


def _archive_url(locator: str) -> str:
    parsed = urlsplit(locator)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise _unsupported_locator()
    archive_end = _archive_path_end(parsed.path)
    if archive_end is None:
        raise _unsupported_locator()
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path[:archive_end],
            parsed.query,
            parsed.fragment,
        )
    )


def _archive_path_end(path: str) -> int | None:
    lower_path = path.lower()
    extensions = (
        ".tar.gz",
        ".tar",
        ".tgz",
        ".zip",
        ".kmz",
        ".ods",
        ".xlsx",
        ".7z",
        ".rar",
        ".gz",
    )
    candidates = (
        (lower_path.find(extension), len(extension)) for extension in extensions
    )
    for index, length in sorted(
        (candidate for candidate in candidates if candidate[0] >= 0),
        key=lambda candidate: candidate[0],
    ):
        end = index + length
        if end == len(path) or path[end] == "/":
            return end
    return None


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
