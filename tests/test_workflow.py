"""Guard the install story.

The drop-in workflow references files by path. Renaming one of those files
without updating the workflow produces a workflow that is valid YAML and fails
on the first pull request that runs it. These tests keep the two in step.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DROP_IN = REPO_ROOT / "workflows" / "pr-ci.yml"
OWN_CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"

SHA_PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps(workflow: dict) -> list[dict]:
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


@pytest.mark.parametrize("path", [DROP_IN, OWN_CI], ids=["drop-in", "own-ci"])
def test_workflow_is_valid_yaml_with_jobs_and_steps(path: Path) -> None:
    workflow = _load(path)
    assert workflow["jobs"], f"{path.name} defines no jobs"
    for job in workflow["jobs"].values():
        assert job["steps"], f"{path.name} has a job with no steps"


@pytest.mark.parametrize("path", [DROP_IN, OWN_CI], ids=["drop-in", "own-ci"])
def test_every_action_is_pinned_to_a_commit_sha(path: Path) -> None:
    """A moving tag is a supply-chain hole: the tag can be repointed."""
    unpinned = [
        step["uses"]
        for step in _steps(_load(path))
        if "uses" in step and not SHA_PINNED.match(step["uses"])
    ]
    assert unpinned == [], f"{path.name} uses unpinned actions: {unpinned}"


def test_drop_in_workflow_grants_only_read_permission() -> None:
    assert _load(DROP_IN)["permissions"] == {"contents": "read"}


@pytest.mark.parametrize(
    "relative",
    [
        "config/pa11yci.json",
        "config/lighthouserc.json",
        "config/htmltest.yml",
        "scripts/validate-generated-post.js",
    ],
)
def test_paths_the_drop_in_workflow_references_exist(relative: str) -> None:
    text = DROP_IN.read_text(encoding="utf-8")
    assert relative in text, f"{relative} is no longer referenced by the workflow"
    assert (REPO_ROOT / relative).exists(), f"{relative} is referenced but missing"


def test_htmltest_download_is_checksum_verified() -> None:
    text = DROP_IN.read_text(encoding="utf-8")
    assert "sha256sum -c -" in text
    assert re.search(r"HTMLTEST_SHA256: '[0-9a-f]{64}'", text)


def test_the_domain_placeholder_is_not_a_real_domain() -> None:
    """SITE_DOMAIN must ship as something the adopter has to replace."""
    assert re.search(r"SITE_DOMAIN: 'example\.com'", DROP_IN.read_text(encoding="utf-8"))
    assert "__SITE_DOMAIN__" in (REPO_ROOT / "config" / "htmltest.yml").read_text(
        encoding="utf-8"
    )


def test_the_accessibility_step_allocates_a_free_port() -> None:
    """A hardcoded port turns a busy machine into a phantom a11y failure."""
    text = DROP_IN.read_text(encoding="utf-8")
    assert "s.bind((\"\",0))" in text
    assert "$PORT" in text
