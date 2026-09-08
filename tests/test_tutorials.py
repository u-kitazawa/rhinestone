import re
from pathlib import Path
from typing import Tuple

import pytest

TUTORIALS_ROOT = Path(__file__).parents[1] / "docs" / "tutorials"
TUTORIAL_NAMES: Tuple[str, ...] = (
    "estat-population.md",
    "stac-rasterio.md",
    "plateau-citygml.md",
)


@pytest.mark.parametrize("name", TUTORIAL_NAMES)
def test_tutorial_python_blocks_compile(name: str) -> None:
    """目的別チュートリアルの掲載コードがPythonとして構文検証できることを保証する。"""
    path = TUTORIALS_ROOT / name
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)

    assert blocks
    for index, block in enumerate(blocks):
        compile(block, f"{path} (block {index + 1})", "exec")
