"""Load the shared quality-gate configuration.

One JSON file describes a site's content layout and rule thresholds, and both
the Python validators and the Node validator read it. That keeps "where do the
posts live" and "how long must a post be" from drifting between the two.

The file is optional: with no file at all every value below applies, which is
enough to validate a stock Hugo site whose posts live in ``content/blog/``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_FILENAME = ".hugo-quality.json"

#: Every setting, with the value used when the config file omits it.
DEFAULTS: dict[str, Any] = {
    # Where content lives, relative to the site root.
    "contentDir": "content",
    # Sections whose pages are dated posts (stricter front-matter rules and the
    # only pages the content-accuracy rules read).
    "postSections": ["blog"],
    # Filenames never validated -- Hugo branch bundles carry section metadata,
    # not page metadata.
    "skipFiles": ["_index.md"],
    # Front-matter fields required on every page...
    "requiredFields": ["title"],
    # ...and the stricter set required on a post.
    "postRequiredFields": ["title", "date"],
    "generatedPost": {
        "minWordCount": 100,
        "placeholderPhrases": [
            "General improvements",
            "See release notes",
            "Lorem ipsum",
        ],
        "emptyDescriptionPatterns": [
            r"^\s*$",
            r"\b(?:adds|includes|contains|covers)\s*\.?\s*$",
        ],
        "shaFreeFields": ["summary", "description"],
        "requireChangeList": True,
    },
    "contentAccuracy": {
        "enumerationHeadings": [
            "tasks",
            "components",
            "features",
            "what is included",
            "what changed",
        ],
        "maxUndisclosedBullets": 3,
        "disclaimerPhrases": ["not disclosed", "not confirmed", "unconfirmed"],
        "confirmationVerbs": [
            "deployed",
            "added",
            "implemented",
            "released",
            "shipped",
        ],
        "pendingIndicators": ["in progress", "expected", "pending", "upcoming"],
        "resultClaimPattern": (
            r"(Results?:[^.\n]*(?:reduced|improved|eliminated|dropped|increased)[^.\n]*\.)"
        ),
        "hedgePrefixes": [
            "Early results",
            "Initial results",
            "Reported results",
            "Expected results",
        ],
        "quoteMarker": "Quote:",
        "sourceHeading": "## Source",
        "codeCallPattern": r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\s*\(",
        "maxUnqualifiedCalls": 2,
        "exampleQualifiers": [
            "example",
            "hypothetical",
            "for instance",
            "pattern:",
            "approach:",
            "illustrative",
        ],
        "forbiddenPhrases": ["TBD", "FIXME", "lorem ipsum"],
    },
}


def site_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the Hugo site root.

    Precedence: the argument, then ``HUGO_SITE_ROOT``, then the process cwd.
    """
    if explicit is not None:
        return Path(explicit).resolve()
    env = os.environ.get("HUGO_SITE_ROOT")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge ``override`` onto ``base``, recursing into nested mappings.

    Lists replace wholesale rather than concatenating: a site that narrows
    ``postSections`` to one entry means *one*, not "one more than the default".
    """
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge(current, value)
        else:
            merged[key] = value
    return merged


def load_config(
    root: str | os.PathLike[str] | None = None,
    config_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Return the effective configuration for a site.

    Args:
        root: Site root. Ignored when ``config_path`` is given.
        config_path: Explicit path to a config file. Missing file raises.

    Raises:
        FileNotFoundError: ``config_path`` was given and does not exist.
        ValueError: The file exists but is not a JSON object.
    """
    if config_path is not None:
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")
    else:
        path = site_root(root) / CONFIG_FILENAME
        if not path.is_file():
            return _merge(DEFAULTS, {})

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: config must be a JSON object")
    return _merge(DEFAULTS, raw)


def content_dir(cfg: dict[str, Any], root: str | os.PathLike[str] | None = None) -> Path:
    """Absolute path of the content directory described by ``cfg``."""
    configured = Path(cfg.get("contentDir", DEFAULTS["contentDir"]))
    if configured.is_absolute():
        return configured
    return site_root(root) / configured
