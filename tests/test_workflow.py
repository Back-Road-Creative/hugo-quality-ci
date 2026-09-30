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


# --- Reproducible Python resolution in this repo's own CI ---------------------

CONSTRAINTS = REPO_ROOT / "constraints" / "ci.txt"
PYPROJECT = REPO_ROOT / "pyproject.toml"
EXACT_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\d+(?:\.\d+)*)$")


def _python_job_steps() -> list[dict]:
    return _load(OWN_CI)["jobs"]["python"]["steps"]


def _install_step() -> dict:
    return next(step for step in _python_job_steps() if step.get("name") == "Install")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _constraint_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = EXACT_PIN.match(line)
        assert match, f"constraints line is not an exact == pin: {line!r}"
        pins[_norm(match.group(1))] = match.group(2)
    return pins


def test_ci_install_step_does_not_float_pip() -> None:
    """`pip install --upgrade pip` resolves to whatever is newest that day."""
    run = _install_step()["run"]
    for command in run.splitlines():
        if "pip install" in command and re.search(r"(--upgrade|\s-U\b)", command):
            pytest.fail(f"install step upgrades without a pin: {command.strip()}")
    assert re.search(r"pip install [\"']?pip==\d", run), "pip itself must be pinned"


def test_ci_install_step_resolves_through_the_constraints_file() -> None:
    step = _install_step()
    run = step["run"]
    assert "constraints/ci.txt" in run or "constraints/ci.txt" in str(step.get("env", {}))
    assert CONSTRAINTS.exists()


def test_constraints_are_exact_pins_covering_every_declared_dependency() -> None:
    import tomllib

    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    declared = list(project["dependencies"])
    for extra in project["optional-dependencies"].values():
        declared.extend(extra)
    pins = _constraint_pins()
    for spec in declared:
        name = _norm(re.split(r"[<>=!~\[ ;]", spec, maxsplit=1)[0])
        assert name in pins, f"{name} is declared in pyproject.toml but not pinned"
    # pytest's own runtime dependencies float unless they are pinned too.
    for transitive in ("iniconfig", "packaging", "pluggy", "pygments"):
        assert transitive in pins, f"transitive dependency {transitive} is not pinned"


def test_test_steps_never_install_anything() -> None:
    """Preparation (Install) and validation (tests) stay separate steps."""
    for step in _python_job_steps():
        if "pytest" in step.get("run", ""):
            assert "pip install" not in step["run"], step.get("name")


def test_hugo_pin_is_exact_and_matches_the_drop_in_workflow() -> None:
    """The version CI tests against must be the version consumers are given."""
    ci_hugo = next(
        step["with"]["hugo-version"]
        for step in _python_job_steps()
        if str(step.get("uses", "")).startswith("peaceiris/actions-hugo@")
    )
    assert re.fullmatch(r"\d+\.\d+\.\d+", ci_hugo), f"hugo pin is not exact: {ci_hugo}"
    drop_in_hugo = _load(DROP_IN)["env"]["HUGO_VERSION"]
    assert ci_hugo == drop_in_hugo
