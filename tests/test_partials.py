"""Build a fixture Hugo site and assert what the partials actually emit.

Reading a template does not tell you what it renders, so this suite runs Hugo.
Where Hugo is not on PATH the whole module skips -- the Python validators do
not need it, and a missing binary should not read as a failure on a laptop.

On CI that leniency is the wrong default: a skip there means the partials
stopped being tested and the run still went green. Set
``HUGO_QUALITY_REQUIRE_HUGO=1`` and a missing Hugo becomes a hard error.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "hugo-site"
PARTIALS = REPO_ROOT / "layouts" / "partials"

LD_BLOCK = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.DOTALL)

_HUGO_MISSING = shutil.which("hugo") is None
_REQUIRE_HUGO = os.environ.get("HUGO_QUALITY_REQUIRE_HUGO") == "1"

pytestmark = pytest.mark.skipif(
    _HUGO_MISSING and not _REQUIRE_HUGO,
    reason="hugo is not installed (set HUGO_QUALITY_REQUIRE_HUGO=1 to make this a failure)",
)


@pytest.fixture(scope="module")
def built_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copy the fixture site, drop the partials in, build it, return public/."""
    site = tmp_path_factory.mktemp("site")
    shutil.copytree(FIXTURE, site, dirs_exist_ok=True)
    target = site / "layouts" / "partials"
    target.mkdir(parents=True, exist_ok=True)
    for partial in PARTIALS.glob("*.html"):
        shutil.copy2(partial, target / partial.name)

    result = subprocess.run(
        ["hugo", "--destination", str(site / "public"), "--logLevel", "error"],
        cwd=site,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"hugo build failed:\n{result.stdout}\n{result.stderr}"
    return site / "public"


def _ld_blocks(html: str) -> list[dict]:
    return [json.loads(block) for block in LD_BLOCK.findall(html)]


def _page(public: Path, relative: str) -> str:
    path = public / relative
    assert path.is_file(), f"Hugo did not render {relative}"
    return path.read_text(encoding="utf-8")


# -- JSON-LD ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("relative", "expected_type"),
    [
        ("index.html", "Organization"),
        ("about/index.html", "Organization"),
        ("blog/first-post/index.html", "BlogPosting"),
        ("docs/index.html", "SoftwareApplication"),
    ],
)
def test_exactly_one_jsonld_block_of_the_right_type(
    built_site: Path, relative: str, expected_type: str
) -> None:
    blocks = _ld_blocks(_page(built_site, relative))
    assert len(blocks) == 1, f"{relative} emitted {len(blocks)} JSON-LD blocks, expected 1"
    assert blocks[0]["@type"] == expected_type
    assert blocks[0]["@context"] == "https://schema.org"


def test_section_list_pages_emit_no_jsonld(built_site: Path) -> None:
    assert _ld_blocks(_page(built_site, "blog/index.html")) == []


def test_blogposting_carries_an_organization_publisher(built_site: Path) -> None:
    block = _ld_blocks(_page(built_site, "blog/first-post/index.html"))[0]
    publisher = block["publisher"]
    assert publisher["@type"] == "Organization"
    assert publisher["name"] == "Example Site"
    assert publisher["sameAs"] == [
        "https://github.com/example",
        "https://example.net/profile",
    ]


def test_blogposting_dates_and_keywords(built_site: Path) -> None:
    block = _ld_blocks(_page(built_site, "blog/first-post/index.html"))[0]
    assert block["datePublished"] == "2026-01-15"
    # `updated` in front matter wins over Hugo's own Lastmod.
    assert block["dateModified"] == "2026-02-01"
    assert block["keywords"] == "structured-data, testing"
    assert block["author"] == {"@type": "Person", "name": "Example Author"}


def test_titles_with_markup_characters_survive_as_data(built_site: Path) -> None:
    """The reason the block is built with dict/jsonify and not string concat."""
    block = _ld_blocks(_page(built_site, "blog/first-post/index.html"))[0]
    assert block["headline"] == "A Post With Quotes & Ampersands"


def test_software_application_is_driven_by_params(built_site: Path) -> None:
    block = _ld_blocks(_page(built_site, "docs/index.html"))[0]
    assert block["name"] == "example-tool"
    assert block["softwareVersion"] == "1.4.0"
    assert block["downloadUrl"] == "https://example.com/download"
    assert block["offers"] == {"@type": "Offer", "price": "0", "priceCurrency": "USD"}


def test_no_hardcoded_urls_in_the_partials() -> None:
    """The partials must carry no site-specific URLs -- everything is a param."""
    for partial in PARTIALS.glob("*.html"):
        text = partial.read_text(encoding="utf-8")
        # schema.org and the opensource.org licence URL in the docs comment are
        # vocabulary, not site identity; nothing else may be an absolute URL.
        found = re.findall(r"https?://[^\s\"'}]+", text)
        unexpected = [
            url
            for url in found
            if not url.startswith(("https://schema.org", "http://schema.org"))
        ]
        assert unexpected == [], f"{partial.name} hardcodes {unexpected}"


# -- head meta --------------------------------------------------------------


def test_canonical_and_open_graph(built_site: Path) -> None:
    html = _page(built_site, "blog/first-post/index.html")
    assert '<link rel="canonical" href="https://example.com/blog/first-post/">' in html
    assert '<meta property="og:type" content="article">' in html
    assert '<meta property="og:site_name" content="Example Site">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert '<meta name="twitter:site" content="@example">' in html


def test_home_title_uses_the_tagline(built_site: Path) -> None:
    assert "<title>Example Site — structured data, checked</title>" in _page(
        built_site, "index.html"
    )


def test_inner_page_title_is_page_then_site(built_site: Path) -> None:
    assert "<title>About | Example Site</title>" in _page(built_site, "about/index.html")


def test_feed_autodiscovery_points_at_a_real_feed(built_site: Path) -> None:
    html = _page(built_site, "index.html")
    assert 'rel="alternate" type="application/rss+xml"' in html
    assert (built_site / "index.xml").is_file()
