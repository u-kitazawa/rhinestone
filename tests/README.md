# Spec contract tests

These tests translate the provider-independent requirements in
`docs/spec_v4.md` into executable contracts before implementation.

## API assumptions

The specification defines model and component names, but intentionally does not
fix Python module paths or complete constructor signatures.  The tests use the
following minimal layout so implementation can start from an explicit design:

- domain values live in `rhinestone.models`;
- stable, cause-specific failures live in `rhinestone.errors`;
- registries, resolution, search, and execution selection are separate modules;
- adapters are accepted by behaviour (duck typing), so Core does not need to
  expose a premature third-party adapter API.

These are test-design assumptions rather than additional product requirements.
If implementation reveals a better public layout, update this note and the
imports without weakening the behavioural assertions.

Provider-specific tests use small, deterministic fixtures derived from the
official CKAN Action API, e-Stat API 3.0, STAC API 1.0.0, and OGC API Features
1.0 contracts. They specify only behaviour supported by those standards and
their fixtures; deployment-specific extensions remain out of scope.

`rhinestone.adapters.ProviderAdapter` is the formal public base class for Source
Adapters. Its `load(config)` method and injected `get_json(url, params)`
transport are public contracts. Provider-specific constructor arguments may
still evolve without weakening request, preservation, explicit-selection, and
failure behaviour.

The first execution vertical slice temporarily places execution adapters in
`rhinestone.adapters.execution` and connects them through `AccessPipeline.open`.
Those package and constructor shapes may evolve; the stable contracts are that
the selected Resource is translated without being re-selected, runtime
dependencies stay lazy and user-owned, and runtime failures retain their cause.

`rhinestone.adapters.ExecutionAdapter` is the formal public base class for
built-in Execution Adapters. It requires a stable name, priority, support
predicate, and runtime-opening operation; Selector composition remains
behaviour-based.

The following public-composition slice treats `rhinestone.configure()` as a
factory for an isolated application context rather than mutable process-global
configuration. A Resource resolved by that context is bound to its executor so
`resource.open(adapter=...)` can follow the documented interface. The binding
mechanism is not itself a permanent API; context isolation, lazy dependencies,
normal resolution, and explicit adapter selection are the guarantees.
