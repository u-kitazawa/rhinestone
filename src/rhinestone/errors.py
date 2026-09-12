"""Stable, actionable errors raised at Rhinestone's public boundaries.

The exception type identifies the category of failure.  The message is intended
for a human operator and may contain safe context such as a field name, source
identifier, or candidate count.  Adapters must not include credentials,
credential values, or unbounded provider payloads in these messages.
"""


class RhinestoneError(Exception):
    """Base class for expected failures in the Rhinestone pipeline.

    Catch this class when an application needs one recovery boundary, or catch a
    specific subclass when the recovery action depends on the cause.
    """


class ConfigValidationError(RhinestoneError):
    """A configuration, query, or adapter definition is invalid.

    Correct the named field or value before retrying.  This error represents an
    input or composition problem, not a provider outage.
    """


class UnsupportedSourceError(RhinestoneError):
    """The requested source ID is not configured in this application.

    Check the ``Catalog`` or ``sources`` passed to :func:`rhinestone.configure`
    and ensure the requested source ID is present.
    """


class UnsupportedSearchConditionError(RhinestoneError):
    """A source adapter cannot apply a supplied search condition.

    Use the search diagnostics to identify the skipped condition, or restrict
    the query to conditions supported by that source.
    """


class ProviderMetadataError(RhinestoneError):
    """Provider metadata could not be retrieved.

    The request may have failed because of connectivity, authorization, or a
    provider-side availability problem.  Retry or inspect the configured
    endpoint and credential without exposing secret values in logs.
    """


class ProviderResponseError(RhinestoneError):
    """A provider response violates the adapter's documented contract.

    The provider responded, but its structure or semantics could not be
    interpreted safely.  Check the provider version or response contract before
    retrying; Rhinestone does not guess missing values.
    """


class AmbiguousResourceError(RhinestoneError):
    """More than one resource candidate matches the requested selection.

    Add an explicit selection such as a resource ID, asset key, or other
    provider-specific setting so that exactly one candidate remains.
    """


class UnsupportedAccessError(RhinestoneError):
    """A selected resource has no supported, explicit access plan.

    Supply a known format or an explicit access kind/options supported by an
    adapter.  Rhinestone does not infer a format from a URI suffix.
    """


class ExecutionAdapterUnavailableError(RhinestoneError):
    """No requested or compatible execution adapter is available.

    Install or inject the required runtime, choose a compatible library name,
    or omit the explicit library request when automatic selection is suitable.
    """


class DependencyUnavailableError(RhinestoneError):
    """A user-owned runtime dependency is missing or could not be loaded.

    Provide the named dependency through ``configure(dependencies=...)``.  A
    factory failure is retained as the exception cause for debugging.
    """


class ResourceAccessError(RhinestoneError):
    """The selected resource could not be opened by its execution adapter.

    Inspect the underlying cause, URI policy, runtime configuration, and access
    plan.  This error is raised after resource selection has succeeded.
    """


class DestinationNotAllowedError(ResourceAccessError):
    """A network destination is outside the configured execution policy.

    Add the intended endpoint to the trusted catalog or use an explicitly
    appropriate network policy.  Do not bypass the policy merely to hide an
    incorrect endpoint.
    """


class IntegrityError(RhinestoneError):
    """Resource integrity verification failed.

    Treat the retrieved bytes as untrusted and verify the checksum or source
    metadata before using the resource.
    """


class AdapterRegistrationError(RhinestoneError):
    """An adapter registration is invalid, duplicated, or inconsistent.

    Correct the adapter definition, its identity, or the factory's returned
    adapter before constructing the application.
    """


class KnowledgeAdapterUnavailableError(RhinestoneError):
    """A required shared-knowledge adapter is not configured.

    Register an adapter for the requested knowledge kind, such as ``time`` or
    ``identity``, before resolving provider-specific values that require it.
    """


class KnowledgeResolutionError(RhinestoneError):
    """A shared-knowledge adapter could not resolve or validate a value.

    Check the input's supported semantic form and the adapter's runtime or
    provider response.  The original exception is retained when loading fails.
    """


class KnowledgeValidationError(RhinestoneError):
    """A canonical shared-knowledge value is structurally invalid.

    Adapter implementations must return a complete ``MunicipalityIdentity`` or
    ``TimeSemantic`` value that satisfies the model's invariants.
    """


class ResourceNotFoundError(RhinestoneError):
    """No resource candidate matches the explicit selection.

    Check the provider-specific identifiers and selection settings, or inspect
    the source metadata to see which candidates were available.
    """


class CredentialUnavailableError(RhinestoneError):
    """A requested logical credential name has not been configured.

    Register a factory under the exact logical name in
    ``configure(credentials=...)``.  The secret itself is never stored in the
    Provider, Config, Result, or Resource.
    """


class CredentialLoadError(RhinestoneError):
    """A credential factory failed or returned an invalid secret.

    Fix the factory so it returns a non-empty string.  The secret and the
    factory's raw failure are intentionally not copied into the public message.
    """
