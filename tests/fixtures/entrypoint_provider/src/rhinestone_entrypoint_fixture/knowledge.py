"""Knowledge export for the independent extension wheel."""

from rhinestone.adapters.knowledge import (
    KnowledgeAdapterContext,
    KnowledgeAdapterDefinition,
    TimeKind,
    TimeSemantic,
)

calls: list[str] = []


class InstalledTime:
    def resolve_time(self, value: str, *, kind: TimeKind | None = None) -> TimeSemantic:
        return TimeSemantic("calendar_year", year=2099, raw=value)


def factory(context: KnowledgeAdapterContext) -> InstalledTime:
    calls.append("factory")
    return InstalledTime()


definition = KnowledgeAdapterDefinition("installed-time", factory, "time")
