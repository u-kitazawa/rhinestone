from pathlib import Path


def test_develop_promotion_checks_the_head_repository() -> None:
    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "branch-policy.yml"
    ).read_text()

    assert "HEAD_REPOSITORY:" in workflow
    assert "BASE_REPOSITORY: ${{ github.repository }}" in workflow
    assert 'HEAD_REF" == "develop"' in workflow
    assert 'HEAD_REPOSITORY" != "$BASE_REPOSITORY"' in workflow
