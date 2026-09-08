"""Destination authorization derived from trusted Source definitions."""

from dataclasses import dataclass
from posixpath import normpath
from typing import Any, Iterable, Literal, Mapping, Optional, Tuple, cast
from urllib.parse import unquote, urlsplit

from .errors import ConfigValidationError, DestinationNotAllowedError
from .models import Provider

NetworkPolicyLevel = Literal["none", "credentialed", "strict"]


@dataclass(frozen=True)
class DestinationRule:
    """A URL origin and path boundary that may receive a request."""

    scheme: str
    host: str
    port: int
    path: str

    @classmethod
    def from_url(cls, url: str) -> Optional["DestinationRule"]:
        try:
            parsed = urlsplit(url)
            port = parsed.port
            hostname = parsed.hostname
        except ValueError:
            return None
        if parsed.scheme.lower() not in {"http", "https"}:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if not hostname:
            return None
        default_port = 443 if parsed.scheme.lower() == "https" else 80
        return cls(
            scheme=parsed.scheme.lower(),
            host=hostname.lower(),
            port=port if port is not None else default_port,
            path=_normalize_path(parsed.path),
        )

    def matches(self, url: str) -> bool:
        candidate = self.from_url(url)
        if candidate is None:
            return False
        if (
            candidate.scheme != self.scheme
            or candidate.host != self.host
            or candidate.port != self.port
        ):
            return False
        return (
            self.path == "/"
            or candidate.path == self.path
            or candidate.path.startswith(self.path + "/")
        )


@dataclass(frozen=True)
class DestinationPolicy:
    """Authorize network destinations at the execution boundary."""

    level: NetworkPolicyLevel = "credentialed"
    rules: Tuple[DestinationRule, ...] = ()

    def __post_init__(self) -> None:
        if self.level not in {"none", "credentialed", "strict"}:
            raise ConfigValidationError(
                "network policy must be 'none', 'credentialed', or 'strict'"
            )

    @classmethod
    def from_catalog(
        cls, catalog: Iterable[Provider], level: NetworkPolicyLevel = "credentialed"
    ) -> "DestinationPolicy":
        """Derive rules from the URL-bearing values in a trusted catalog."""
        rules: list[DestinationRule] = []
        seen: set[DestinationRule] = set()
        for provider in catalog:
            for url in _urls(provider.settings):
                rule = DestinationRule.from_url(url)
                if rule is not None and rule not in seen:
                    seen.add(rule)
                    rules.append(rule)
        return cls(level=level, rules=tuple(rules))

    @classmethod
    def unrestricted(cls) -> "DestinationPolicy":
        return cls(level="none")

    def authorize(self, url: str, *, credentialed: bool = False) -> None:
        """Raise when ``url`` is outside this policy's authorized URL space."""
        if self.level == "none" or (self.level == "credentialed" and not credentialed):
            return
        try:
            scheme = urlsplit(url).scheme.lower()
        except ValueError:
            scheme = "__invalid__"
        if scheme in {"", "file"}:
            return
        if not any(rule.matches(url) for rule in self.rules):
            raise DestinationNotAllowedError("Network destination is not authorized")


def _normalize_path(path: str) -> str:
    normalized = normpath("/" + unquote(path).lstrip("/"))
    return normalized or "/"


def _urls(value: Any) -> Tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, str):
        if DestinationRule.from_url(value) is not None:
            found.append(value)
    elif isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        for item in mapping.values():
            found.extend(_urls(item))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in cast(Iterable[Any], value):
            found.extend(_urls(item))
    return tuple(found)


__all__ = ["DestinationPolicy", "DestinationRule", "NetworkPolicyLevel"]
