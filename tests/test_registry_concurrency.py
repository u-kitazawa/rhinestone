from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from rhinestone.adapters.knowledge import (
    KnowledgeAdapterContext,
    KnowledgeAdapterDefinition,
    KnowledgeAdapterRegistry,
    StandardTimeAdapter,
)
from rhinestone.models import RuntimeFactory
from rhinestone.registry import DependencyRegistry

from .test_knowledge import knowledge_context


def assert_created_once_under_concurrent_requests(
    configure_getters: Callable[
        [Callable[[], object]], tuple[Callable[[], object], ...]
    ],
) -> None:
    started = Event()
    release = Event()
    second_requested = Event()
    created: list[object] = []

    def factory() -> object:
        runtime = StandardTimeAdapter()
        created.append(runtime)
        started.set()
        assert release.wait(5), "test did not release factory"
        return runtime

    first_get, second_get = configure_getters(factory)

    def request_second() -> object:
        second_requested.set()
        return second_get()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(first_get)
        try:
            assert started.wait(5), "first factory never started"
            second = executor.submit(request_second)
            assert second_requested.wait(5), "second request never started"
        finally:
            release.set()
        assert first.result(timeout=5) is second.result(timeout=5)
    assert len(created) == 1


def test_scoped_dependencies_share_one_lazy_runtime_under_concurrency() -> None:
    def getters(factory: Callable[[], object]) -> tuple[Callable[[], object], ...]:
        registry = DependencyRegistry({"rdflib": RuntimeFactory(factory)})
        first = registry.scoped(("rdflib",))
        second = registry.scoped(("rdflib",))
        return lambda: first.get("rdflib"), lambda: second.get("rdflib")

    assert_created_once_under_concurrent_requests(getters)


def test_distinct_dependency_factories_initialize_concurrently() -> None:
    first_started = Event()
    second_started = Event()
    release = Event()

    def factory(started: Event, other_started: Event, name: str) -> object:
        started.set()
        assert other_started.wait(5), f"{name} factory blocked the other dependency"
        assert release.wait(5), "test did not release dependency factories"
        return object()

    registry = DependencyRegistry(
        {
            "first": RuntimeFactory(
                lambda: factory(first_started, second_started, "first")
            ),
            "second": RuntimeFactory(
                lambda: factory(second_started, first_started, "second")
            ),
        }
    )
    first = registry.scoped(("first",))
    second = registry.scoped(("second",))

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_result = executor.submit(first.get, "first")
        second_result = executor.submit(second.get, "second")
        try:
            assert first_started.wait(5), "first dependency factory never started"
            assert second_started.wait(5), "second dependency factory never started"
        finally:
            release.set()
        assert first_result.result(timeout=5) is first.get("first")
        assert second_result.result(timeout=5) is second.get("second")


def test_knowledge_factory_creates_one_shared_adapter_under_concurrency() -> None:
    def getters(factory: Callable[[], object]) -> tuple[Callable[[], object], ...]:
        def knowledge_factory(_context: KnowledgeAdapterContext) -> StandardTimeAdapter:
            adapter = factory()
            assert isinstance(adapter, StandardTimeAdapter)
            return adapter

        registry = KnowledgeAdapterRegistry(
            (KnowledgeAdapterDefinition("time", knowledge_factory, "time"),),
            knowledge_context(),
        )
        return registry.time, registry.time

    assert_created_once_under_concurrent_requests(getters)
