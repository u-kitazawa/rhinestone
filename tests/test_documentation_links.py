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
