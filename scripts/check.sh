#!/usr/bin/env bash
set -euo pipefail

# Keep the local preflight and the PR CI checks in one place.
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict
uv build
