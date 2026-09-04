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

Provider-specific fixtures are deliberately deferred: spec v0.4 names CKAN,
e-Stat, STAC, and OGC, but does not yet define request/response fixtures or
selection rules precise enough for deterministic golden tests. Guessing those
contracts would violate the spec's “fail rather than guess” principle.

