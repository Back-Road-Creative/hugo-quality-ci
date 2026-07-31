"""Quality gates for Hugo sites: front matter, content accuracy, front-matter edits.

The public surface is small on purpose::

    from hugo_quality import (
        load_config,          # read .hugo-quality.json (or the defaults)
        validate_tree,        # structural front-matter check over a content dir
        check_text,           # content-accuracy rules over one document
        HugoFrontMatterUpdater,
    )
"""

from __future__ import annotations

from .config import CONFIG_FILENAME, DEFAULTS, content_dir, load_config, site_root
from .content_rules import RULES, Violation, check_text, split_document
from .frontmatter import (
    extract_frontmatter,
    is_post,
    iter_content_files,
    validate_file,
    validate_text,
    validate_tree,
)
from .updater import HugoFrontMatterUpdater, extract_youtube_id

__version__ = "0.1.0"

__all__ = [
    "CONFIG_FILENAME",
    "DEFAULTS",
    "HugoFrontMatterUpdater",
    "RULES",
    "Violation",
    "__version__",
    "check_text",
    "content_dir",
    "extract_frontmatter",
    "extract_youtube_id",
    "is_post",
    "iter_content_files",
    "load_config",
    "site_root",
    "split_document",
    "validate_file",
    "validate_text",
    "validate_tree",
]
