"""Pytest entry point that runs the content-accuracy rules over a real site.

This module is a *test file that ships inside the package*, so a site does not
have to vendor a copy. Point it at a site and run it::

    HUGO_SITE_ROOT=/path/to/site pytest --pyargs hugo_quality.content_check -v

It reads ``.hugo-quality.json`` from the site root (see
:mod:`hugo_quality.config`) and checks every page under the configured post
sections. With no posts on disk it reports a skip rather than a pass — a green
gate over zero files is worse than no gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .config import content_dir as resolve_content_dir
from .config import load_config, site_root
from .content_rules import check_text
from .frontmatter import iter_content_files, is_post


def _post_paths() -> list[Path]:
    cfg = load_config()
    root = resolve_content_dir(cfg)
    if not root.is_dir():
        return []
    sections = cfg.get("postSections", ())
    skip = cfg.get("skipFiles", ())
    return [
        path
        for path in iter_content_files(root, skip)
        if is_post(path.relative_to(root), sections)
    ]


def _ids(paths: list[Path]) -> list[str]:
    root = resolve_content_dir(load_config())
    return [path.relative_to(root).as_posix() for path in paths]


_PATHS = _post_paths()


@pytest.mark.skipif(not _PATHS, reason="no posts found under the configured post sections")
@pytest.mark.parametrize("post_path", _PATHS, ids=_ids(_PATHS) or None)
def test_post_meets_content_accuracy_rules(post_path: Path) -> None:
    cfg = load_config()
    violations = check_text(post_path.read_text(encoding="utf-8"), cfg["contentAccuracy"])
    if violations:
        rendered = "\n".join(f"  - {violation}" for violation in violations)
        pytest.fail(f"{post_path.name}:\n{rendered}", pytrace=False)


def test_site_root_is_configured() -> None:
    """Fail loudly when the gate is pointed at the wrong directory.

    Running this suite from the wrong working directory used to produce a
    confident green over an empty tree.
    """
    root = site_root()
    assert root.is_dir(), f"site root does not exist: {root}"
