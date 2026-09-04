# Rhinestone Agent Guide

## Project shape

- Use the `src/` layout. Package code belongs under `src/rhinestone/`; keep tests in a separate `tests/` directory when they are added.
- The design specification is the source of truth for architecture and invariants: [docs/spec_v2.md](docs/spec_v2.md).
- The package currently has no runtime dependencies, test suite, lint configuration, type-check configuration, CI configuration, or lockfile.

## Development commands

- Build the distribution with `uv build`.
- Do not claim that tests, linting, or type checking passed until the corresponding tooling and configuration exist. When adding a feature, add focused tests and document the command here or in project documentation.
- Preserve compatibility with the `requires-python = ">=3.7"` declaration unless the project configuration is intentionally changed.

## Architecture rules

- Preserve the access pipeline: `Config -> DataReference -> SourceMetadata -> AccessPlan -> Execution -> Data`.
- Keep responsibilities separate: a Resolver reads metadata and selects an access plan; a Loader executes a chosen plan and does not select resources; `DataReference` identifies the target but does not contain loader details.
- Keep provider-specific behavior out of the Domain layer. Prefer existing standards and OSS libraries over reimplementing format or protocol handling.
- Avoid implicit format conversion, URL guessing, discovery in Core, and HTML scraping. If a decision cannot be made reliably, fail explicitly or require opt-in.
- Use distinct error types for distinct failure causes rather than collapsing failures into `RuntimeError`.
- Keep resolution deterministic and explainable: the same config, metadata, and capabilities should produce the same `AccessPlan`.

## Change discipline

- Follow specification by example, contract testing, and vertical slicing. For a new provider, add a representative fixture, expected access plan, and contract test.
- Keep Config immutable and do not discard source metadata without a documented reason.
- Avoid designing a public plugin API before repeated implementation patterns justify one; an internal registry is sufficient for v0.x.
- Keep changes minimal, preserve public APIs, and update the specification or documentation when behavior changes.