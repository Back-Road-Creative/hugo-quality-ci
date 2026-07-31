"""Structural validation of Hugo YAML front matter.

Catches the failure modes that make Hugo silently render the wrong thing rather
than fail the build:

- a file wrapped in a code fence (```markdown ... ```), so the front matter is
  body text and every field is lost;
- front matter that does not start on line 1, which Hugo ignores entirely;
- an unterminated or malformed YAML block;
- missing required fields;
- a zero-value date (``0001-01-01``), Hugo's tell that it could not parse the
  date it was given.

Run against a site::

    python -m hugo_quality.frontmatter --content content

or, after ``pip install``::

    hugo-validate-frontmatter --content content
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import yaml

from .config import content_dir as resolve_content_dir
from .config import load_config

ZERO_DATE_PREFIX = "0001-01-01"


def extract_frontmatter(text: str) -> tuple[str | None, list[str]]:
    """Split the YAML front-matter block out of a markdown document.

    Returns ``(yaml_source, errors)``. ``yaml_source`` is ``None`` when the
    block could not be located, in which case ``errors`` says why.
    """
    errors: list[str] = []
    lines = text.split("\n")

    if lines and lines[0].strip().startswith("```"):
        errors.append("file starts with a code fence — Hugo will not parse the front matter")
        return None, errors

    if not lines or lines[0].strip() != "---":
        errors.append("front matter delimiter '---' not found on line 1")
        return None, errors

    closing = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = index
            break

    if closing is None:
        errors.append("no closing '---' delimiter found for front matter")
        return None, errors

    return "\n".join(lines[1:closing]), errors


def validate_text(
    text: str,
    *,
    required_fields: Iterable[str],
) -> list[str]:
    """Validate one document's front matter. Returns a list of error strings."""
    yaml_source, errors = extract_frontmatter(text)
    if yaml_source is None:
        return errors

    try:
        parsed: Any = yaml.safe_load(yaml_source)
    except yaml.YAMLError as exc:
        return [f"invalid YAML in front matter: {exc}"]

    if parsed is None:
        return ["front matter is empty"]
    if not isinstance(parsed, dict):
        return ["front matter did not parse as a YAML mapping"]

    for field in sorted(required_fields):
        if field not in parsed or parsed[field] is None:
            errors.append(f"missing required field: {field}")

    date_value = parsed.get("date")
    if date_value is not None and str(date_value).startswith(ZERO_DATE_PREFIX):
        errors.append(f"date is zero-value ({ZERO_DATE_PREFIX}) — Hugo could not parse it")

    title = parsed.get("title")
    if title is not None and str(title).strip() == "":
        errors.append("title is empty")

    return errors


def is_post(relative_path: str | os.PathLike[str], post_sections: Sequence[str]) -> bool:
    """True when a content path sits inside one of the configured post sections."""
    parts = Path(relative_path).parts
    return bool(parts) and parts[0] in set(post_sections)


def iter_content_files(
    root: str | os.PathLike[str],
    skip_files: Iterable[str] = (),
) -> Iterator[Path]:
    """Yield every ``.md`` file under ``root``, sorted, minus the skip list."""
    skip = set(skip_files)
    for directory, _subdirs, filenames in os.walk(root):
        for name in sorted(filenames):
            if name.endswith(".md") and name not in skip:
                yield Path(directory) / name


def validate_file(path: str | os.PathLike[str], cfg: dict[str, Any], *, post: bool) -> list[str]:
    """Validate a single content file against ``cfg``."""
    required = cfg["postRequiredFields"] if post else cfg["requiredFields"]
    text = Path(path).read_text(encoding="utf-8")
    return validate_text(text, required_fields=required)


def validate_tree(
    root: str | os.PathLike[str],
    cfg: dict[str, Any],
) -> dict[str, list[str]]:
    """Validate every content file under ``root``.

    Returns a mapping of *relative* path to its errors. A file with no errors is
    still present in the mapping with an empty list, so callers can report the
    number of files checked without walking the tree twice.
    """
    root_path = Path(root)
    results: dict[str, list[str]] = {}
    for path in iter_content_files(root_path, cfg.get("skipFiles", ())):
        relative = path.relative_to(root_path).as_posix()
        post = is_post(relative, cfg.get("postSections", ()))
        results[relative] = validate_file(path, cfg, post=post)
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hugo-validate-frontmatter",
        description="Validate Hugo front matter across a content tree.",
    )
    parser.add_argument(
        "--content",
        help="Content directory. Overrides contentDir from the config file.",
    )
    parser.add_argument(
        "--root",
        help="Site root. Defaults to $HUGO_SITE_ROOT, then the current directory.",
    )
    parser.add_argument(
        "--config",
        help="Path to a config file. Defaults to .hugo-quality.json under the site root.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Print failures only.",
    )
    args = parser.parse_args(argv)

    cfg = load_config(root=args.root, config_path=args.config)
    target = Path(args.content).resolve() if args.content else resolve_content_dir(cfg, args.root)

    if not target.is_dir():
        print(f"Content directory not found: {target}", file=sys.stderr)
        return 2

    results = validate_tree(target, cfg)

    total_errors = 0
    for relative, errors in sorted(results.items()):
        if errors:
            total_errors += len(errors)
            for error in errors:
                print(f"FAIL: {relative} — {error}")
        elif not args.quiet:
            print(f"  OK: {relative}")

    print()
    print(f"Checked {len(results)} file(s), {total_errors} error(s)")
    if total_errors:
        print("FAILED: front matter validation failed")
        return 1
    print("PASSED: all front matter valid")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    raise SystemExit(main())
