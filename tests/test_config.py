from __future__ import annotations

import json

import pytest

from hugo_quality import config


def test_defaults_apply_when_no_file_exists(tmp_path):
    cfg = config.load_config(root=tmp_path)
    assert cfg["contentDir"] == "content"
    assert cfg["postSections"] == ["blog"]
    assert cfg["generatedPost"]["minWordCount"] == 100


def test_file_overrides_merge_into_defaults(tmp_path):
    (tmp_path / config.CONFIG_FILENAME).write_text(
        json.dumps({"postSections": ["notes"], "generatedPost": {"minWordCount": 40}}),
        encoding="utf-8",
    )
    cfg = config.load_config(root=tmp_path)

    assert cfg["postSections"] == ["notes"]
    assert cfg["generatedPost"]["minWordCount"] == 40
    # Untouched sibling keys survive the merge.
    assert cfg["generatedPost"]["requireChangeList"] is True
    assert cfg["contentDir"] == "content"


def test_lists_replace_rather_than_extend(tmp_path):
    """Narrowing a list must mean *that* list, not the default plus one."""
    (tmp_path / config.CONFIG_FILENAME).write_text(
        json.dumps({"requiredFields": ["title", "summary"]}), encoding="utf-8"
    )
    cfg = config.load_config(root=tmp_path)
    assert cfg["requiredFields"] == ["title", "summary"]


def test_loading_the_defaults_does_not_mutate_them(tmp_path):
    (tmp_path / config.CONFIG_FILENAME).write_text(
        json.dumps({"generatedPost": {"minWordCount": 1}}), encoding="utf-8"
    )
    config.load_config(root=tmp_path)
    assert config.DEFAULTS["generatedPost"]["minWordCount"] == 100


def test_explicit_missing_config_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        config.load_config(config_path=tmp_path / "nope.json")


def test_non_object_config_raises(tmp_path):
    path = tmp_path / config.CONFIG_FILENAME
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        config.load_config(config_path=path)


def test_site_root_honours_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HUGO_SITE_ROOT", str(tmp_path))
    assert config.site_root() == tmp_path.resolve()


def test_content_dir_resolves_relative_to_the_site_root(tmp_path):
    cfg = config.load_config(root=tmp_path)
    assert config.content_dir(cfg, root=tmp_path) == tmp_path.resolve() / "content"


def test_absolute_content_dir_is_left_alone(tmp_path):
    cfg = config.load_config(root=tmp_path)
    cfg["contentDir"] = str(tmp_path / "elsewhere")
    assert config.content_dir(cfg, root=tmp_path) == tmp_path / "elsewhere"
