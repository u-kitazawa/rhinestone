"""Documentation link checks."""

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).parents[1]
MARKDOWN_FILES = tuple(
    path
    for path in ROOT.rglob("*.md")
    if not any(part in {".git", ".venv", "site"} for part in path.parts)
)
LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


def heading_anchor(text: str) -> str:
    """Create the anchor form used by MkDocs' default slugifier."""
    value = re.sub(r"[^\w-]+", "-", text.strip().lower(), flags=re.UNICODE)
    return re.sub(r"-+", "-", value).strip("-")


def anchors(path: Path) -> set[str]:
    return {
        heading_anchor(unquote(heading))
        for heading in HEADING_PATTERN.findall(path.read_text(encoding="utf-8"))
    }


def test_all_local_markdown_links_exist_and_anchors_resolve() -> None:
    failures: list[str] = []

    for source in MARKDOWN_FILES:
        for raw_target in LINK_PATTERN.findall(source.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue

            path_text, _, fragment = target.partition("#")
            destination = (source.parent / unquote(path_text)).resolve()
            if not destination.is_file():
                failures.append(f"{source}: missing {target}")
                continue
            if fragment and fragment not in anchors(destination):
                failures.append(f"{source}: missing anchor {target}")

    assert not failures, "\n".join(failures)


def test_example_index_lists_each_runnable_example() -> None:
    """The landing page must not silently omit runnable example directories."""
    index = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    targets = set(LINK_PATTERN.findall(index))
    expected = {
        f"{script.parent.name}/README.md"
        for script in (ROOT / "examples").glob("*/example.py")
    }
    assert expected <= targets


def test_adapter_guides_use_current_public_resource_contract() -> None:
    """These guides must not reintroduce the retired model or method names."""
    for name in ("static", "dcat", "geospatial-jp", "search-ckan-jp", "mlit-dpf"):
        guide = (ROOT / "docs" / "api" / "adapters" / f"{name}.md").read_text(
            encoding="utf-8"
        )
        for retired in ("`Source`", "`target`", "`resolve()`", " Config"):
            assert retired not in guide, (name, retired)


def test_runtime_and_extension_guides_use_current_contracts() -> None:
    """Runtime and extension instructions must use load and plan boundaries."""
    for name in ("runtimes", "dependency-policy", "custom-adapters"):
        guide = (ROOT / "docs" / f"{name}.md").read_text(encoding="utf-8")
        for retired in ("`resolve()`", "`resolve`", "`target`", "`Source`"):
            assert retired not in guide, (name, retired)

    custom = (ROOT / "docs" / "custom-adapters.md").read_text(encoding="utf-8")
    assert "destination_policy.authorize(plan.uri)" in custom
    assert "destination_policy.authorize(resource.uri)" not in custom
