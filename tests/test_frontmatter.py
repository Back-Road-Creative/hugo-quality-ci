from __future__ import annotations

import json

from hugo_quality import config, frontmatter

VALID = """---
title: "A Page"
date: 2026-01-15
---

Body text.
"""


def _write(root, relative: str, text: str):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# -- extract_frontmatter ----------------------------------------------------


def test_extracts_the_yaml_block():
    yaml_source, errors = frontmatter.extract_frontmatter(VALID)
    assert errors == []
    assert 'title: "A Page"' in yaml_source


def test_code_fence_wrapper_is_reported():
    _, errors = frontmatter.extract_frontmatter("```markdown\n---\ntitle: x\n---\n```")
    assert errors == ["file starts with a code fence — Hugo will not parse the front matter"]


def test_front_matter_must_start_on_line_one():
    _, errors = frontmatter.extract_frontmatter("\n---\ntitle: x\n---\n")
    assert "not found on line 1" in errors[0]


def test_unterminated_front_matter_is_reported():
    _, errors = frontmatter.extract_frontmatter("---\ntitle: x\n\nbody\n")
    assert "no closing" in errors[0]


# -- validate_text ----------------------------------------------------------


def test_valid_document_has_no_errors():
    assert frontmatter.validate_text(VALID, required_fields=["title", "date"]) == []


def test_missing_required_field():
    text = "---\ntitle: x\n---\n\nbody\n"
    assert frontmatter.validate_text(text, required_fields=["title", "date"]) == [
        "missing required field: date"
    ]


def test_null_field_counts_as_missing():
    text = "---\ntitle: x\ndate:\n---\n\nbody\n"
    assert "missing required field: date" in frontmatter.validate_text(
        text, required_fields=["title", "date"]
    )


def test_zero_value_date_is_reported():
    text = "---\ntitle: x\ndate: 0001-01-01T00:00:00Z\n---\n\nbody\n"
    errors = frontmatter.validate_text(text, required_fields=["title"])
    assert any("zero-value" in error for error in errors)


def test_empty_title_is_reported():
    text = '---\ntitle: "   "\n---\n\nbody\n'
    assert "title is empty" in frontmatter.validate_text(text, required_fields=["title"])


def test_invalid_yaml_is_reported():
    text = "---\ntitle: [unclosed\n---\n\nbody\n"
    errors = frontmatter.validate_text(text, required_fields=["title"])
    assert len(errors) == 1
    assert errors[0].startswith("invalid YAML")


def test_scalar_front_matter_is_not_a_mapping():
    text = "---\njust a string\n---\n\nbody\n"
    assert frontmatter.validate_text(text, required_fields=["title"]) == [
        "front matter did not parse as a YAML mapping"
    ]


def test_empty_front_matter_is_reported():
    assert frontmatter.validate_text("---\n---\n\nbody\n", required_fields=[]) == [
        "front matter is empty"
    ]


# -- tree walking -----------------------------------------------------------


def test_is_post_matches_configured_sections():
    assert frontmatter.is_post("blog/post.md", ["blog"])
    assert not frontmatter.is_post("about.md", ["blog"])
    assert not frontmatter.is_post("notes/post.md", ["blog"])


def test_skip_files_are_not_walked(tmp_path):
    _write(tmp_path, "blog/_index.md", "not even valid")
    _write(tmp_path, "blog/post.md", VALID)
    found = {path.name for path in frontmatter.iter_content_files(tmp_path, ["_index.md"])}
    assert found == {"post.md"}


def test_validate_tree_applies_the_stricter_post_rules(tmp_path):
    cfg = config.load_config(root=tmp_path)
    _write(tmp_path, "about.md", '---\ntitle: "About"\n---\n\nbody\n')
    _write(tmp_path, "blog/undated.md", '---\ntitle: "Undated"\n---\n\nbody\n')

    results = frontmatter.validate_tree(tmp_path, cfg)

    assert results["about.md"] == []
    assert results["blog/undated.md"] == ["missing required field: date"]


# -- CLI --------------------------------------------------------------------


def test_cli_returns_zero_on_a_clean_tree(tmp_path, capsys):
    _write(tmp_path, "content/blog/post.md", VALID)
    assert frontmatter.main(["--content", str(tmp_path / "content")]) == 0
    assert "PASSED" in capsys.readouterr().out


def test_cli_returns_one_and_names_the_file(tmp_path, capsys):
    _write(tmp_path, "content/blog/broken.md", '---\ntitle: "x"\n---\n\nbody\n')
    assert frontmatter.main(["--content", str(tmp_path / "content")]) == 1
    out = capsys.readouterr().out
    assert "FAIL: blog/broken.md — missing required field: date" in out


def test_cli_returns_two_when_the_content_dir_is_missing(tmp_path):
    assert frontmatter.main(["--content", str(tmp_path / "nowhere")]) == 2


def test_cli_reads_the_content_dir_from_the_config_file(tmp_path):
    (tmp_path / config.CONFIG_FILENAME).write_text(
        json.dumps({"contentDir": "site/content"}), encoding="utf-8"
    )
    _write(tmp_path, "site/content/blog/post.md", VALID)
    assert frontmatter.main(["--root", str(tmp_path)]) == 0
