"""End-to-end checks on the packaged pytest module.

These run the exact command the PR CI workflow runs, in a subprocess, against a
site built in a temp directory. Anything less would test the rules rather than
the gate, and the gate is where the interesting failures live -- a wrong
working directory used to make it pass over zero files.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = REPO_ROOT / "python"

CLEAN_POST = """---
title: "A Clean Post"
date: 2026-01-15
---

Prose with nothing to flag in it. It states what happened and no more.
"""

DIRTY_POST = """---
title: "A Dirty Post"
date: 2026-01-16
---

The rewrite is in progress.

Result: build time reduced by half.
"""


def _site(tmp_path: Path, posts: dict[str, str], config: dict | None = None) -> Path:
    content = tmp_path / "content" / "blog"
    content.mkdir(parents=True)
    for name, text in posts.items():
        (content / name).write_text(text, encoding="utf-8")
    if config is not None:
        (tmp_path / ".hugo-quality.json").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


def _run(site: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PYTHON_DIR)
    env.pop("HUGO_SITE_ROOT", None)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--pyargs",
            "hugo_quality.content_check",
            "-p",
            "no:cacheprovider",
            "-q",
        ],
        cwd=site,
        env=env,
        capture_output=True,
        text=True,
    )


def test_a_clean_site_passes(tmp_path):
    result = _run(_site(tmp_path, {"clean.md": CLEAN_POST}))
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_violation_fails_and_names_the_file(tmp_path):
    result = _run(_site(tmp_path, {"clean.md": CLEAN_POST, "dirty.md": DIRTY_POST}))
    assert result.returncode != 0
    assert "dirty.md" in result.stdout
    assert "check_unhedged_results" in result.stdout


def test_an_empty_site_skips_rather_than_passing_green(tmp_path):
    """A gate that finds nothing must say so, not report success."""
    result = _run(_site(tmp_path, {}))
    assert "skipped" in result.stdout


def test_the_post_section_is_configurable(tmp_path):
    """With posts in a section the config does not list, nothing is checked."""
    site = _site(tmp_path, {"dirty.md": DIRTY_POST}, config={"postSections": ["notes"]})
    result = _run(site)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("content_dir", ["content", "site/content"])
def test_the_content_dir_is_configurable(tmp_path, content_dir):
    posts = tmp_path / content_dir / "blog"
    posts.mkdir(parents=True)
    (posts / "dirty.md").write_text(DIRTY_POST, encoding="utf-8")
    (tmp_path / ".hugo-quality.json").write_text(
        json.dumps({"contentDir": content_dir}), encoding="utf-8"
    )
    assert _run(tmp_path).returncode != 0
