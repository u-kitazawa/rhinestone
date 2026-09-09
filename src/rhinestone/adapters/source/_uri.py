"""URI reference handling shared by provider response adapters."""

from urllib.parse import urljoin, urlsplit, urlunsplit


def resolve_response_href(response_uri: str, href: str) -> str:
    """Resolve a provider href against the URI of its containing response."""
    return urljoin(response_uri, href)


def append_path_segment(uri: str, segment: str) -> str:
    """Append a path segment without moving it behind a query or fragment."""
    components = urlsplit(uri)
    path = f"{components.path.rstrip('/')}/{segment}"
    return urlunsplit(components._replace(path=path))
