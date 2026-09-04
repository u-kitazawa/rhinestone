from typing import FrozenSet, List, Tuple

import pytest

from rhinestone import configure
from rhinestone.errors import UnsupportedSearchConditionError
from rhinestone.models import (
    Config,
    Metadata,
    Provenance,
    ResourceCandidate,
    SearchQuery,
    SearchResult,
    Source,
)


class MemorySourceAdapter:
    source_type = "memory"
    search_conditions = frozenset({"text", "limit"})

    def __init__(self) -> None:
        self.loaded: List[Config] = []
        self.searched: List[SearchQuery] = []

    def load(self, config: Config) -> Source:
        self.loaded.append(config)
        name = str(config.settings["name"])
        candidate = ResourceCandidate(
            uri="memory://" + name,
            format="memory",
            media_type="application/x-memory",
        )
        return Source(
            metadata=Metadata(title=name, raw={"name": name}),
            candidates=(candidate,),
            capabilities=frozenset({"search"}),
            provenance=Provenance(provider="memory", raw={"name": name}),
            raw_metadata={"name": name},
        )

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        self.searched.append(query)
        return (
            SearchResult(
                title="result",
                description=None,
                source_type="memory",
                provider_settings={"name": "result"},
                metadata=Metadata(title="result", raw={}),
                provenance=Provenance(provider="memory", raw={}),
            ),
        )


class MemoryExecutionAdapter:
    name = "memory-runtime"
    priority = 10

    def supports(self, resource: object, dependencies: FrozenSet[str]) -> bool:
        return (
            getattr(resource, "format", None) == "memory" and self.name in dependencies
        )

    def open(self, resource: object, runtime: object) -> object:
        return getattr(runtime, "open")(getattr(resource, "uri"))


class MemoryRuntime:
    def __init__(self, label: str) -> None:
        self.label = label
        self.calls: List[str] = []

    def open(self, uri: str) -> str:
        self.calls.append(uri)
        return self.label + ":" + uri


def test_configure_returns_isolated_context_without_loading_dependencies() -> None:
    """利用者runtimeをグローバル共有せず、実際にopenする時までcallbackを呼ばないために必要である。"""
    callback_calls: List[str] = []
    runtime = MemoryRuntime("first")

    app = configure(
        dependencies={
            "memory-runtime": lambda: callback_calls.append("load") or runtime
        },
        source_adapters=(MemorySourceAdapter(),),
        execution_adapters=(MemoryExecutionAdapter(),),
    )

    assert callback_calls == []
    resource = app.resolve(Config("memory", {"name": "dataset"}))
    assert callback_calls == []
    assert resource.open() == "first:memory://dataset"
    assert callback_calls == ["load"]


def test_resource_open_honours_explicit_adapter_name() -> None:
    """公開Resource APIからの明示指定をExecution Adapter Selectorへ確実に渡すために必要である。"""
    selected: List[str] = []

    class LowerPriorityAdapter(MemoryExecutionAdapter):
        name = "explicit"
        priority = 1

        def open(self, resource: object, runtime: object) -> object:
            selected.append(self.name)
            return "explicit-data"

    app = configure(
        dependencies={
            "memory-runtime": lambda: MemoryRuntime("automatic"),
            "explicit": lambda: object(),
        },
        source_adapters=(MemorySourceAdapter(),),
        execution_adapters=(MemoryExecutionAdapter(), LowerPriorityAdapter()),
    )

    resource = app.resolve(Config("memory", {"name": "dataset"}))

    assert resource.open(adapter="explicit") == "explicit-data"
    assert selected == ["explicit"]


def test_application_search_keeps_results_grouped_by_provider() -> None:
    """公開検索でも比較不能なprovider scoreを混合せずCoordinatorのgroupingを保持するために必要である。"""
    source = MemorySourceAdapter()
    app = configure(
        dependencies={},
        source_adapters=(source,),
        execution_adapters=(),
    )
    query = SearchQuery(text="result", limit=1)

    grouped = app.search(query)

    assert tuple(grouped) == ("memory",)
    assert grouped["memory"][0].title == "result"
    assert source.searched == [query]


def test_search_result_config_uses_the_normal_resolution_path() -> None:
    """SearchResultから直接Resourceを作らず、Config検証とSource解釈を再利用するために必要である。"""
    source = MemorySourceAdapter()
    app = configure(
        dependencies={},
        source_adapters=(source,),
        execution_adapters=(),
    )
    result = app.search(SearchQuery(text="result"))["memory"][0]

    resource = app.resolve(result.to_config())

    assert resource.uri == "memory://result"
    assert source.loaded == [Config("memory", {"name": "result"})]


def test_public_search_exposes_unsupported_conditions_as_domain_error() -> None:
    """公開APIが未対応検索条件を削除せず、呼び出し側へ安定した型で通知するために必要である。"""
    app = configure(
        dependencies={},
        source_adapters=(MemorySourceAdapter(),),
        execution_adapters=(),
    )

    with pytest.raises(UnsupportedSearchConditionError, match="bbox"):
        app.search(SearchQuery(bbox=(139.0, 35.0, 140.0, 36.0)))


def test_configured_contexts_do_not_share_runtime_instances() -> None:
    """複数利用者設定間でruntime callback/cacheが漏れず、所有権境界を守るために必要である。"""
    first_runtime = MemoryRuntime("first")
    second_runtime = MemoryRuntime("second")
    source = MemorySourceAdapter()
    adapters = (MemoryExecutionAdapter(),)
    first = configure(
        dependencies={"memory-runtime": lambda: first_runtime},
        source_adapters=(source,),
        execution_adapters=adapters,
    )
    second = configure(
        dependencies={"memory-runtime": lambda: second_runtime},
        source_adapters=(source,),
        execution_adapters=adapters,
    )
    config = Config("memory", {"name": "dataset"})

    assert first.resolve(config).open() == "first:memory://dataset"
    assert second.resolve(config).open() == "second:memory://dataset"


def test_application_open_is_a_convenience_for_resolve_then_open() -> None:
    """ConfigからDataへの公開短縮経路も同じ選択・依存注入pipelineを通るために必要である。"""
    app = configure(
        dependencies={"memory-runtime": lambda: MemoryRuntime("app")},
        source_adapters=(MemorySourceAdapter(),),
        execution_adapters=(MemoryExecutionAdapter(),),
    )

    assert app.open(Config("memory", {"name": "dataset"})) == ("app:memory://dataset")
