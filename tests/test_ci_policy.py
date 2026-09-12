from pathlib import Path

WORKFLOWS = Path(__file__).parents[1] / ".github" / "workflows"


def test_ci_does_not_modify_or_push_contributor_branches() -> None:
    """CI生成commitと検証対象SHAのずれを再発させないために必要である。"""
    assert not (WORKFLOWS / "ruff-autofix.yml").exists()

    workflows = (*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml"))
    workflow_text = "\n".join(workflow.read_text() for workflow in sorted(workflows))
    assert "ruff check --fix" not in workflow_text
    assert "ruff format ." not in workflow_text
    assert "git commit" not in workflow_text
    assert "git push" not in workflow_text


def test_normal_ci_runs_full_checks_for_pushes_and_pull_requests() -> None:
    """変更されない対象SHAへ通常のmerge gateを適用するために必要である。"""
    workflow = (WORKFLOWS / "test.yml").read_text()

    assert "  push:" in workflow
    assert "  pull_request:" in workflow
    assert "      UV_PYTHON: ${{ matrix.python-version }}" in workflow
    assert "run: bash scripts/check.sh" in workflow
