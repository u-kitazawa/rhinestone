import pytest

from rhinestone.errors import (
    AdapterRegistrationError,
    ConfigValidationError,
    ProviderMetadataError,
    UnsupportedSourceError,
)
from rhinestone.models import Metadata, Provenance, Reference, Resource
from rhinestone.pipeline import AccessPipeline
from rhinestone.registry import AdapterRegistry
from rhinestone.resolution import resource_from_delivery


class RecordingSourceAdapter:
    source_id = "fixture"

    def __init__(self, events: list[str]) -> None:
        self.events = events

    def load(self, reference: Reference) -> Resource:
        self.events.append("source-adapter")
        return resource_from_delivery(
            reference=reference,
            uri="https://example.jp/data.csv",
            format="csv",
            media_type="text/csv",
            metadata=Metadata(title="Dataset", raw={"original": True}),
            provenance=Provenance(provider="fixture", raw={"request": "known"}),
        )


def test_access_pipeline_delegates_unique_resource_selection_to_provider() -> None:
    events: list[str] = []
    pipeline = AccessPipeline(
        adapter_registry=AdapterRegistry((RecordingSourceAdapter(events),), ())
    )
    config = Reference(provider_id="fixture", parameters={"dataset": "data-1"})

    resource = pipeline.load(config)

    assert events == ["source-adapter"]
    assert resource.metadata.raw == {"original": True}
    assert resource.provenance.raw == {"request": "known"}
    assert resource.reference.provider_id == "fixture"


def test_unconfigured_pipeline_cannot_open_an_existing_resource() -> None:
    pipeline = AccessPipeline(
        adapter_registry=AdapterRegistry((RecordingSourceAdapter([]),), ())
    )
    resource = pipeline.load(Reference(provider_id="fixture", parameters={}))

    with pytest.raises(ProviderMetadataError, match="Execution pipeline"):
        pipeline.open_resource(resource, "gdal")


def test_unknown_provider_has_a_specific_failure() -> None:
    pipeline = AccessPipeline(adapter_registry=AdapterRegistry((), ()))

    with pytest.raises(UnsupportedSourceError, match="unknown"):
        pipeline.load(Reference("unknown"))


def test_provider_failure_is_wrapped_without_losing_its_cause() -> None:
    provider_error = OSError("connection closed")

    class BrokenAdapter:
        source_id = "broken"

        def load(self, reference: Reference) -> Resource:
            raise provider_error

    pipeline = AccessPipeline(adapter_registry=AdapterRegistry((BrokenAdapter(),), ()))

    with pytest.raises(ProviderMetadataError) as captured:
        pipeline.load(Reference("broken"))

    assert captured.value.__cause__ is provider_error


def test_pipeline_does_not_wrap_an_expected_domain_error() -> None:
    expected = ConfigValidationError("dataset is required")

    class RejectingAdapter:
        source_id = "rejecting"

        def load(self, reference: Reference) -> Resource:
            raise expected

    pipeline = AccessPipeline(
        adapter_registry=AdapterRegistry((RejectingAdapter(),), ())
    )

    with pytest.raises(ConfigValidationError) as captured:
        pipeline.load(Reference("rejecting"))

    assert captured.value is expected


def test_duplicate_source_adapters_are_rejected_by_pipeline() -> None:
    events: list[str] = []
    with pytest.raises(AdapterRegistrationError, match="fixture"):
        AccessPipeline(
            adapter_registry=AdapterRegistry(
                (RecordingSourceAdapter(events), RecordingSourceAdapter(events)), ()
            )
        )
