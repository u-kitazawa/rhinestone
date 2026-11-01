"""Shared URI authority validation."""

from urllib.parse import urlsplit


def is_valid_http_authority(uri: str) -> bool:
    """Return whether an HTTP(S) URI has a syntactically valid host authority."""
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except (TypeError, ValueError, UnicodeError):
        return False
    if parsed.scheme.casefold() not in {"http", "https"}:
        return True
    host = parsed.hostname
    if (
        not host
        or parsed.username is not None
        or parsed.password is not None
        or any(
            character.isspace() or ord(character) < 32 for character in parsed.netloc
        )
    ):
        return False
    if ":" in host:
        return True
    if "%" in host or (port is None and ":" in parsed.netloc):
        return False
    labels = host.rstrip(".").split(".")
    return bool(labels and all(_is_hostname_label(label) for label in labels))


def _is_hostname_label(label: str) -> bool:
    """Validate one DNS hostname label without accepting URI delimiters."""
    if not label or len(label) > 63 or label[0] == "-" or label[-1] == "-":
        return False
    return all(character.isalnum() or character == "-" for character in label)
