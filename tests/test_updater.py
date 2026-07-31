from __future__ import annotations

from datetime import datetime

import pytest
import yaml

from hugo_quality import HugoFrontMatterUpdater, extract_youtube_id

BODY = """
Paragraph one, with trailing spaces preserved.

---

A horizontal rule above, which is not a front-matter delimiter.

    indented block
"""

DOC = '---\ntitle: "A Post"\ndate: 2026-01-15\ntags:\n  - one\n  - two\n---' + BODY


@pytest.fixture()
def post(tmp_path):
    path = tmp_path / "post.md"
    path.write_text(DOC, encoding="utf-8")
    return path


def _body_of(path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    closing = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    return text[len("\n".join(lines[: closing + 1])) :]


# -- reading ----------------------------------------------------------------


def test_read_returns_the_parsed_front_matter(post):
    frontmatter = HugoFrontMatterUpdater().read(post)
    assert frontmatter["title"] == "A Post"
    assert frontmatter["tags"] == ["one", "two"]


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        HugoFrontMatterUpdater().update(tmp_path / "nope.md", {"x": 1})


def test_document_without_front_matter_raises(tmp_path):
    path = tmp_path / "plain.md"
    path.write_text("Just prose.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not open"):
        HugoFrontMatterUpdater().read(path)


def test_unterminated_front_matter_raises(tmp_path):
    path = tmp_path / "open.md"
    path.write_text("---\ntitle: x\n\nbody\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No closing"):
        HugoFrontMatterUpdater().read(path)


def test_invalid_yaml_raises(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text("---\ntitle: [unclosed\n---\nbody\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        HugoFrontMatterUpdater().read(path)


# -- the core guarantee -----------------------------------------------------


def test_body_is_preserved_byte_for_byte(post):
    before = _body_of(post)
    HugoFrontMatterUpdater(create_backups=False).update(post, {"video_url": "https://x/y"})
    assert _body_of(post) == before == BODY


def test_a_horizontal_rule_in_the_body_is_not_mistaken_for_a_delimiter(post):
    """Splitting on the literal '---' truncates the body at the first rule."""
    HugoFrontMatterUpdater(create_backups=False).update(post, {"draft": False})
    assert "A horizontal rule above" in post.read_text(encoding="utf-8")


def test_a_triple_dash_inside_a_quoted_value_survives(tmp_path):
    path = tmp_path / "tricky.md"
    path.write_text('---\ntitle: "before --- after"\n---\nBody.\n', encoding="utf-8")
    HugoFrontMatterUpdater(create_backups=False).update(path, {"draft": True})
    assert HugoFrontMatterUpdater().read(path)["title"] == "before --- after"


# -- writing ----------------------------------------------------------------


def test_update_adds_and_overwrites_fields(post):
    HugoFrontMatterUpdater(create_backups=False).update(
        post, {"title": "Renamed", "video_url": "https://example.com/v"}
    )
    frontmatter = HugoFrontMatterUpdater().read(post)
    assert frontmatter["title"] == "Renamed"
    assert frontmatter["video_url"] == "https://example.com/v"
    assert frontmatter["tags"] == ["one", "two"]


def test_key_order_is_preserved(post):
    HugoFrontMatterUpdater(create_backups=False).update(post, {"video_url": "https://x/y"})
    text = post.read_text(encoding="utf-8")
    keys = list(yaml.safe_load(text.split("---")[1]).keys())
    assert keys == ["title", "date", "tags", "video_url"]


def test_remove_deletes_keys_and_ignores_absent_ones(post):
    HugoFrontMatterUpdater(create_backups=False).remove(post, ["tags", "not-there"])
    assert "tags" not in HugoFrontMatterUpdater().read(post)


def test_no_temp_file_is_left_behind(post, tmp_path):
    HugoFrontMatterUpdater(create_backups=False).update(post, {"x": 1})
    assert list(tmp_path.glob("*.tmp")) == []


def test_unicode_survives_the_round_trip(tmp_path):
    path = tmp_path / "unicode.md"
    path.write_text('---\ntitle: "Café — naïve"\n---\nBody\n', encoding="utf-8")
    HugoFrontMatterUpdater(create_backups=False).update(path, {"draft": False})
    assert HugoFrontMatterUpdater().read(path)["title"] == "Café — naïve"


# -- backups ----------------------------------------------------------------


def test_a_backup_is_written_by_default(post, tmp_path):
    original = post.read_text(encoding="utf-8")
    HugoFrontMatterUpdater().update(post, {"x": 1})
    backup = tmp_path / "post.md.bak"
    assert backup.is_file()
    assert backup.read_text(encoding="utf-8") == original


def test_a_second_backup_is_timestamped_not_clobbered(post, tmp_path):
    updater = HugoFrontMatterUpdater()
    updater.update(post, {"x": 1})
    updater.update(post, {"y": 2})
    backups = sorted(p.name for p in tmp_path.glob("post.md*.bak"))
    assert len(backups) == 2


def test_backups_can_be_suppressed_per_call(post, tmp_path):
    HugoFrontMatterUpdater().update(post, {"x": 1}, create_backup=False)
    assert list(tmp_path.glob("*.bak")) == []


# -- video helpers ----------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/watch?list=PL123&v=dQw4w9WgXcQ",
    ],
)
def test_youtube_id_is_extracted_from_every_url_form(url):
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


def test_an_unparseable_url_raises():
    with pytest.raises(ValueError, match="Could not extract"):
        extract_youtube_id("https://example.com/not-a-video")


def test_add_youtube_video_sets_the_expected_fields(post):
    HugoFrontMatterUpdater(create_backups=False).add_youtube_video(
        post,
        "https://youtu.be/dQw4w9WgXcQ",
        published_date=datetime(2026, 3, 4),
    )
    frontmatter = HugoFrontMatterUpdater().read(post)
    assert frontmatter["youtube_url"] == "https://youtu.be/dQw4w9WgXcQ"
    assert frontmatter["youtube_id"] == "dQw4w9WgXcQ"
    assert frontmatter["youtube_embed"] is True
    assert frontmatter["video_published_date"] == "2026-03-04"


def test_has_video_reflects_the_front_matter(post):
    updater = HugoFrontMatterUpdater(create_backups=False)
    assert not updater.has_video(post)
    updater.add_youtube_video(post, "https://youtu.be/dQw4w9WgXcQ")
    assert updater.has_video(post)


# -- CLI --------------------------------------------------------------------


def test_cli_sets_yaml_typed_values(post, capsys):
    from hugo_quality.updater import main

    assert main([str(post), "--set", "draft=false", "--set", "weight=3", "--no-backup"]) == 0
    frontmatter = HugoFrontMatterUpdater().read(post)
    assert frontmatter["draft"] is False
    assert frontmatter["weight"] == 3
    assert "Updated" in capsys.readouterr().out


def test_cli_unsets_fields(post):
    from hugo_quality.updater import main

    assert main([str(post), "--unset", "tags", "--no-backup"]) == 0
    assert "tags" not in HugoFrontMatterUpdater().read(post)


def test_cli_requires_something_to_do(post):
    from hugo_quality.updater import main

    with pytest.raises(SystemExit):
        main([str(post)])
