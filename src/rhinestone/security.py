"""Destination authorization derived from trusted Source definitions."""

from dataclasses import dataclass
from posixpath import normpath
from typing import Any, Iterable, Literal, Mapping, Optional, Tuple, cast
from urllib.parse import unquote, urlsplit

from .errors import ConfigValidationError, DestinationNotAllowedError
from .models import Provider

NetworkPolicyLevel = Literal["none", "credentialed"]


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
class CredentialDestinationRule:
    """A provider-scoped destination that may receive one credential."""

    provider: str
    service: str
    credential: Optional[str]
    destination: DestinationRule

    def matches(
        self,
        url: str,
        *,
        provider: Optional[str],
        service: Optional[str],
        credential: Optional[str],
    ) -> bool:
        if provider is not None and provider != self.provider:
            return False
        if service != self.service:
            return False
        if self.credential is not None and credential != self.credential:
            return False
        return self.destination.matches(url)


@dataclass(frozen=True)
class DestinationPolicy:
    """Authorize network destinations at the execution boundary."""

    level: NetworkPolicyLevel = "credentialed"
    rules: Tuple[DestinationRule, ...] = ()
    credential_rules: Optional[Tuple[CredentialDestinationRule, ...]] = None

    def __post_init__(self) -> None:
        if self.level not in {"none", "credentialed"}:
            raise ConfigValidationError(
                "network policy must be 'none' or 'credentialed'"
            )

    @classmethod
    def from_catalog(
        cls, catalog: Iterable[Provider], level: NetworkPolicyLevel = "credentialed"
    ) -> "DestinationPolicy":
        """Derive rules from the URL-bearing values in a trusted catalog."""
        rules: list[DestinationRule] = []
        seen: set[DestinationRule] = set()
        credential_rules: list[CredentialDestinationRule] = []
        seen_credential_rules: set[CredentialDestinationRule] = set()
        for provider in catalog:
            for url in _urls(provider.settings):
                rule = DestinationRule.from_url(url)
                if rule is not None and rule not in seen:
                    seen.add(rule)
                    rules.append(rule)
            for credential_rule in _credential_rules(provider):
                if credential_rule not in seen_credential_rules:
                    seen_credential_rules.add(credential_rule)
                    credential_rules.append(credential_rule)
        return cls(
            level=level,
            rules=tuple(rules),
            credential_rules=tuple(credential_rules),
        )

    @classmethod
    def unrestricted(cls) -> "DestinationPolicy":
        return cls(level="none")

    def authorize(
        self,
        url: str,
        *,
        credentialed: bool = False,
        provider: Optional[str] = None,
        service: Optional[str] = None,
        credential: Optional[str] = None,
    ) -> None:
        """Raise when ``url`` is outside this policy's authorized URL space."""
        if self.level == "none" or (self.level == "credentialed" and not credentialed):
            return
        try:
            scheme = urlsplit(url).scheme.lower()
        except ValueError:
            scheme = "__invalid__"
        if scheme in {"", "file"}:
            return
        if credentialed and self.credential_rules is not None:
            authorized = any(
                rule.matches(
                    url,
                    provider=provider,
                    service=service,
                    credential=credential,
                )
                for rule in self.credential_rules
            )
        else:
            authorized = any(rule.matches(url) for rule in self.rules)
        if not authorized:
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


def _credential_rules(provider: Provider) -> Tuple[CredentialDestinationRule, ...]:
    endpoint = provider.settings.get("endpoint")
    if not isinstance(endpoint, str):
        return ()
    endpoint = endpoint.rstrip("/")
    if provider.adapter_type == "odpt":
        resource_types = provider.settings.get("resource_types")
        if not isinstance(resource_types, Mapping):
            return ()
        urls = tuple(
            f"{endpoint}/{resource_type}"
            for resource_type in cast(Mapping[Any, Any], resource_types).values()
            if isinstance(resource_type, str) and resource_type
        )
        credential: Optional[str] = None
    elif provider.adapter_type not in {
        "direct",
        "static",
        "search-ckan-jp",
        "gsi-fundamental",
        "dcat",
    }:
        configured_credential = provider.settings.get("credential")
        if configured_credential is None:
            credential = None
        elif isinstance(configured_credential, str) and configured_credential:
            credential = configured_credential
        else:
            return ()
        urls = (endpoint,)
    else:
        return ()
    rules: list[CredentialDestinationRule] = []
    for url in urls:
        destination = DestinationRule.from_url(url)
        if destination is not None:
            rules.append(
                CredentialDestinationRule(
                    provider=provider.id,
                    service=provider.adapter_type,
                    credential=credential,
                    destination=destination,
                )
            )
    return tuple(rules)


__all__ = [
    "CredentialDestinationRule",
    "DestinationPolicy",
    "DestinationRule",
    "NetworkPolicyLevel",
]
