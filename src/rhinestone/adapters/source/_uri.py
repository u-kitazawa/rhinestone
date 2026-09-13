"""URI reference handling shared by provider response adapters."""

from urllib.parse import quote, urljoin, urlsplit, urlunsplit


def resolve_response_href(response_uri: str, href: str) -> str:
    """Resolve a provider href against the URI of its containing response."""
    return urljoin(response_uri, href)


def append_path_segment(uri: str, segment: str) -> str:
    """Append a path segment without moving it behind a query or fragment."""
    components = urlsplit(uri)
    encoded = (
        segment.replace(".", "%2E")
        if segment in {".", ".."}
        else quote(segment, safe="")
    )
    path = f"{components.path.rstrip('/')}/{encoded}"
    return urlunsplit(components._replace(path=path))


def has_embedded_credentials(uri: str) -> bool:
    """Return whether an HTTP(S) URI contains userinfo credentials."""
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return False
    return parsed.scheme.casefold() in {"http", "https"} and (
        parsed.username is not None or parsed.password is not None
    )
