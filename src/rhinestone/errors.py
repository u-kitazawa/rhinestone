"""Stable domain errors exposed by Rhinestone boundaries."""


class RhinestoneError(Exception):
    """Base class for expected Rhinestone failures."""


class ConfigValidationError(RhinestoneError):
    """A declarative config is structurally or semantically invalid."""


class UnsupportedSourceError(RhinestoneError):
    """No source adapter supports the requested source type."""


class UnsupportedSearchConditionError(RhinestoneError):
    """A source adapter cannot honor a supplied search condition."""


class ProviderMetadataError(RhinestoneError):
    """Provider metadata could not be retrieved."""


class ProviderResponseError(RhinestoneError):
    """A provider response violates its documented contract."""


class AmbiguousResourceError(RhinestoneError):
    """A resource cannot be selected uniquely."""


class UnsupportedAccessError(RhinestoneError):
    """A resource has no known access method."""


class ExecutionAdapterUnavailableError(RhinestoneError):
    """No requested or compatible execution adapter is available."""


class DependencyUnavailableError(RhinestoneError):
    """A user-owned runtime dependency is unavailable."""


class ResourceAccessError(RhinestoneError):
    """A selected resource could not be accessed."""


class IntegrityError(RhinestoneError):
    """Resource integrity verification failed."""


class AdapterRegistrationError(RhinestoneError):
    """An adapter registration is invalid or ambiguous."""


class ResourceNotFoundError(RhinestoneError):
    """No candidate matches the explicit resource selection."""


class CredentialUnavailableError(RhinestoneError):
    """A logical credential name has not been configured."""


class CredentialLoadError(RhinestoneError):
    """A credential factory failed or returned an invalid secret."""
