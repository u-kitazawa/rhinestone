from rhinestone.errors import (
    AmbiguousResourceError,
    ConfigValidationError,
    DependencyUnavailableError,
    ExecutionAdapterUnavailableError,
    IntegrityError,
    ProviderMetadataError,
    ProviderResponseError,
    ResourceAccessError,
    UnsupportedAccessError,
    UnsupportedSearchConditionError,
    UnsupportedSourceError,
)


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
