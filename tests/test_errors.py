import pytest

from rhinestone.errors import (
    AmbiguousResourceError,
    ConfigValidationError,
    CredentialLoadError,
    DependencyUnavailableError,
    ExecutionAdapterUnavailableError,
    IntegrityError,
    ProviderMetadataError,
    ProviderResponseError,
    ResourceAccessError,
    RhinestoneError,
    UnsupportedAccessError,
    UnsupportedSearchConditionError,
    UnsupportedSourceError,
)
from rhinestone.models import Config, Provider, SearchQuery
from rhinestone.registry import CredentialRegistry


def test_expected_failure_causes_have_distinct_error_types() -> None:
    """Spec が列挙する失敗原因を RuntimeError 一種類へ潰さないために必要である。"""
    error_types = {
        ConfigValidationError,
        UnsupportedSourceError,
        UnsupportedSearchConditionError,
        ProviderMetadataError,
        ProviderResponseError,
        AmbiguousResourceError,
        UnsupportedAccessError,
        ExecutionAdapterUnavailableError,
        DependencyUnavailableError,
        ResourceAccessError,
        IntegrityError,
    }

    assert len(error_types) == 11
    assert all(issubclass(error_type, Exception) for error_type in error_types)


def test_public_errors_explain_recovery_without_exposing_secrets() -> None:
    """Public error messages should provide safe context for operators."""
    with pytest.raises(ConfigValidationError) as config_error:
        Provider("source", "")
    assert "adapter_type" in str(config_error.value)
    assert "registered source adapter type" in str(config_error.value)

    with pytest.raises(ConfigValidationError) as query_error:
        SearchQuery(text=42)  # type: ignore[arg-type]
    assert "text must be a string or None" in str(query_error.value)
    assert "int" in str(query_error.value)

    secret = "secret-in-underlying-error"

    def fail() -> str:
        raise RuntimeError(secret)

    with pytest.raises(CredentialLoadError) as credential_error:
        CredentialRegistry({"provider-token": fail}).get("provider-token")
    assert "provider-token" in str(credential_error.value)
    assert secret not in str(credential_error.value)
    assert credential_error.value.__cause__ is None


def test_public_models_and_operations_have_actionable_pydocs() -> None:
    """The public IDE-facing objects should document their contract."""
    assert "configured data provider" in (Provider.__doc__ or "")
    assert "configured source" in (Config.__doc__ or "")
    assert "pipeline" in (RhinestoneError.__doc__ or "").lower()
    assert "runtime" in (ResourceAccessError.__doc__ or "").lower()
