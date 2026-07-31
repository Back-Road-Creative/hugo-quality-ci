"""Rewrite Hugo YAML front matter without touching the body.

The use case is metadata that only becomes known after a page is published --
a video URL, a canonical ID, a review date. Editing the file by hand risks the
body; editing it with a naive round-trip risks reflowing every paragraph.

Guarantees:

- **The body is preserved byte for byte.** It is sliced out of the original
  text and concatenated back unchanged; it is never parsed or re-rendered.
- **Writes are atomic.** Content goes to a sibling temp file which is then
  renamed over the original, so an interrupted run leaves the original intact.
- **A backup is taken by default**, timestamped when one already exists.

Only the front matter is re-serialised, so YAML comments and key order inside
the front-matter block are not preserved (``sort_keys=False`` keeps the order
of keys that survive the parse, and new keys append).

Usage::

    from hugo_quality import HugoFrontMatterUpdater

    updater = HugoFrontMatterUpdater()
    updater.update(Path("content/blog/post.md"), {"video_url": url})
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import yaml

logger = logging.getLogger(__name__)

_YOUTUBE_ID_PATTERNS = (
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)"
    r"([a-zA-Z0-9_-]{11})",
    r"[?&]v=([a-zA-Z0-9_-]{11})",
)


def extract_youtube_id(url: str) -> str:
    """Return the 11-character video ID from a YouTube URL.

    Handles ``watch?v=``, ``youtu.be/``, ``/embed/`` and ``/shorts/`` forms.

    Raises:
        ValueError: No ID could be found.
    """
    for pattern in _YOUTUBE_ID_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract a YouTube video ID from: {url}")


class HugoFrontMatterUpdater:
    """Update YAML front matter in place, preserving the body exactly."""

    def __init__(self, create_backups: bool = True, backup_suffix: str = ".bak") -> None:
        """
        Args:
            create_backups: Take a backup before each write.
            backup_suffix: Suffix appended to the backup filename.
        """
        self.create_backups = create_backups
        self.backup_suffix = backup_suffix

    # -- public API ---------------------------------------------------------

    def read(self, md_file: str | Path) -> dict[str, Any]:
        """Return the front matter of ``md_file`` as a dict."""
        frontmatter, _ = self._parse(Path(md_file))
        return frontmatter

    def update(
        self,
        md_file: str | Path,
        updates: dict[str, Any],
        create_backup: bool | None = None,
    ) -> Path:
        """Merge ``updates`` into the front matter of ``md_file``.

        Args:
            md_file: Path to the markdown file.
            updates: Fields to set or add. Existing keys are overwritten.
            create_backup: Override the instance backup setting.

        Returns:
            The path that was updated.

        Raises:
            FileNotFoundError: The file does not exist.
            ValueError: The file is not a Hugo markdown document.
        """
        path = Path(md_file)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {path}")

        frontmatter, body = self._parse(path)
        frontmatter.update(updates)

        should_backup = self.create_backups if create_backup is None else create_backup
        if should_backup:
            backup_path = self._backup(path)
            logger.info("Created backup: %s", backup_path)

        self._write(path, frontmatter, body)
        logger.info("Updated front matter in %s (%s)", path.name, ", ".join(sorted(updates)))
        return path

    def remove(
        self,
        md_file: str | Path,
        keys: Sequence[str],
        create_backup: bool | None = None,
    ) -> Path:
        """Delete ``keys`` from the front matter. Missing keys are ignored."""
        path = Path(md_file)
        frontmatter, body = self._parse(path)
        for key in keys:
            frontmatter.pop(key, None)

        should_backup = self.create_backups if create_backup is None else create_backup
        if should_backup:
            self._backup(path)

        self._write(path, frontmatter, body)
        return path

    def add_youtube_video(
        self,
        md_file: str | Path,
        youtube_url: str,
        youtube_id: str | None = None,
        enable_embed: bool = True,
        published_date: datetime | None = None,
    ) -> Path:
        """Attach a YouTube video to a page after it has been published.

        Sets ``youtube_url``, ``youtube_id``, ``youtube_embed`` and optionally
        ``video_published_date`` (``YYYY-MM-DD``).
        """
        updates: dict[str, Any] = {
            "youtube_url": youtube_url,
            "youtube_id": youtube_id or extract_youtube_id(youtube_url),
            "youtube_embed": enable_embed,
        }
        if published_date is not None:
            updates["video_published_date"] = published_date.strftime("%Y-%m-%d")
        return self.update(md_file, updates)

    def has_video(self, md_file: str | Path) -> bool:
        """True when the page already carries a video URL or ID."""
        frontmatter = self.read(md_file)
        return bool(frontmatter.get("youtube_url") or frontmatter.get("youtube_id"))

    # -- internals ----------------------------------------------------------

    def _parse(self, path: Path) -> tuple[dict[str, Any], str]:
        """Split a document into (front matter dict, verbatim body).

        The closing delimiter is located by scanning for a line that is exactly
        ``---``. Splitting on the literal string instead would truncate at the
        first ``---`` inside a quoted value or a horizontal rule in the body.
        """
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        if not lines or lines[0].strip() != "---":
            raise ValueError(f"File does not open with a '---' front-matter delimiter: {path}")

        closing = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                closing = index
                break
        if closing is None:
            raise ValueError(f"No closing '---' front-matter delimiter: {path}")

        try:
            parsed = yaml.safe_load("\n".join(lines[1:closing]))
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML front matter in {path}: {exc}") from exc

        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise ValueError(f"Front matter is not a mapping in {path}")

        # Everything after the closing delimiter line, byte for byte.
        consumed = len("\n".join(lines[: closing + 1]))
        return parsed, content[consumed:]

    def _write(self, path: Path, frontmatter: dict[str, Any], body: str) -> None:
        rendered = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )
        updated = f"---\n{rendered}---{body}"

        temp_file = path.with_name(path.name + ".tmp")
        try:
            temp_file.write_text(updated, encoding="utf-8")
            temp_file.replace(path)
        except Exception:
            temp_file.unlink(missing_ok=True)
            raise

    def _backup(self, path: Path) -> Path:
        backup_path = path.with_name(path.name + self.backup_suffix)
        if backup_path.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = path.with_name(f"{path.name}.{stamp}{self.backup_suffix}")
        shutil.copy2(path, backup_path)
        return backup_path


def _parse_assignment(raw: str) -> tuple[str, Any]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"expected key=value, got {raw!r}")
    key, _, value = raw.partition("=")
    # YAML-parse the value so --set draft=false stores a boolean, not a string.
    return key.strip(), yaml.safe_load(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hugo-update-frontmatter",
        description="Set or remove Hugo front-matter fields without touching the body.",
    )
    parser.add_argument("file", help="Markdown file to update.")
    parser.add_argument(
        "--set",
        dest="assignments",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Field to set. Values are parsed as YAML. Repeatable.",
    )
    parser.add_argument(
        "--unset",
        dest="removals",
        action="append",
        default=[],
        metavar="KEY",
        help="Field to remove. Repeatable.",
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not write a .bak file.")
    args = parser.parse_args(argv)

    if not args.assignments and not args.removals:
        parser.error("nothing to do: pass at least one --set or --unset")

    updater = HugoFrontMatterUpdater(create_backups=not args.no_backup)
    if args.assignments:
        updates = dict(_parse_assignment(item) for item in args.assignments)
        updater.update(args.file, updates)
    if args.removals:
        updater.remove(args.file, args.removals)
    print(f"Updated {args.file}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    raise SystemExit(main())
