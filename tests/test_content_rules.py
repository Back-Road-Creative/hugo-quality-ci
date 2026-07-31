from __future__ import annotations

import pytest

from hugo_quality import content_rules
from hugo_quality.config import DEFAULTS

CFG = DEFAULTS["contentAccuracy"]


def rules_fired(text: str, cfg=CFG) -> set[str]:
    return {violation.rule for violation in content_rules.check_text(text, cfg)}


# -- document splitting -----------------------------------------------------


def test_split_document_separates_front_matter_from_body():
    yaml_source, body = content_rules.split_document('---\ntitle: "x"\n---\nHello\n')
    assert yaml_source == 'title: "x"'
    assert body == "Hello\n"


def test_split_document_passes_through_a_bare_document():
    yaml_source, body = content_rules.split_document("Hello\n")
    assert yaml_source == ""
    assert body == "Hello\n"


def test_front_matter_is_not_scanned_for_violations():
    """A forbidden phrase inside a draft flag is metadata, not published prose."""
    assert rules_fired('---\nstatus: "TBD"\n---\nClean prose.\n') == set()


# -- rule 1: undisclosed enumeration ----------------------------------------

ENUMERATION = """
## What changed

- the first specific thing
- the second specific thing
- the third specific thing
- the fourth specific thing
"""


def test_long_enumeration_without_disclosure_fails():
    assert "check_undisclosed_enumeration" in rules_fired(ENUMERATION)


def test_short_enumeration_passes():
    short = "## What changed\n\n- one thing\n- another thing\n"
    assert "check_undisclosed_enumeration" not in rules_fired(short)


def test_a_disclaimer_clears_the_enumeration():
    text = ENUMERATION + "\nThe full list was not disclosed.\n"
    assert "check_undisclosed_enumeration" not in rules_fired(text)


def test_past_tense_confirmation_clears_the_enumeration():
    text = ENUMERATION + "\nAll four shipped in the last release.\n"
    assert "check_undisclosed_enumeration" not in rules_fired(text)


def test_enumeration_ignores_headings_outside_the_configured_list():
    text = ENUMERATION.replace("What changed", "Reading list")
    assert "check_undisclosed_enumeration" not in rules_fired(text)


# -- rule 2: unhedged results -----------------------------------------------


def test_definitive_result_on_unfinished_work_fails():
    text = "The migration is in progress.\n\nResult: latency reduced by half.\n"
    assert "check_unhedged_results" in rules_fired(text)


def test_hedged_result_passes():
    text = "The migration is in progress.\n\nEarly results: latency reduced by half.\n"
    assert "check_unhedged_results" not in rules_fired(text)


def test_result_claim_on_finished_work_passes():
    text = "The migration shipped last month.\n\nResult: latency reduced by half.\n"
    assert "check_unhedged_results" not in rules_fired(text)


# -- rule 3: quote attribution ----------------------------------------------


def test_quote_without_a_source_section_fails():
    assert "check_quote_attribution" in rules_fired('Quote: "it depends".\n')


def test_quote_with_a_source_section_passes():
    text = 'Quote: "it depends".\n\n## Source\n\nA public talk, 2026.\n'
    assert "check_quote_attribution" not in rules_fired(text)


# -- rule 4: unqualified code examples --------------------------------------

CODE = """
```python
build_index(path)
resolve_target(name)
write_manifest(data)
```
"""


def test_specific_looking_calls_without_a_qualifier_fail():
    assert "check_unqualified_code_examples" in rules_fired(CODE)


def test_a_qualifier_in_the_preceding_prose_clears_it():
    text = "The pattern: a three-step build.\n" + CODE
    assert "check_unqualified_code_examples" not in rules_fired(text)


def test_a_short_code_block_passes():
    text = "```python\nbuild_index(path)\n```\n"
    assert "check_unqualified_code_examples" not in rules_fired(text)


def test_a_qualifier_further_up_the_page_does_not_count():
    """The marker has to be near the block, or it is not marking that block."""
    text = "For instance, consider builds.\n\n" + ("filler paragraph. " * 40) + CODE
    assert "check_unqualified_code_examples" in rules_fired(text)


# -- rule 5: forbidden phrases ----------------------------------------------


@pytest.mark.parametrize("phrase", ["TBD", "FIXME", "lorem ipsum", "Lorem Ipsum"])
def test_forbidden_phrases_are_caught_case_insensitively(phrase):
    assert "check_forbidden_phrases" in rules_fired(f"Some prose {phrase} more prose.\n")


def test_forbidden_phrases_respect_word_boundaries():
    """'TBD' inside a longer token is not the drafting marker."""
    assert "check_forbidden_phrases" not in rules_fired("The NOTBDX identifier is fine.\n")


def test_forbidden_phrases_are_configurable():
    cfg = {**CFG, "forbiddenPhrases": ["codename-atlas"]}
    assert "check_forbidden_phrases" in rules_fired("Ship codename-atlas soon.\n", cfg)
    assert "check_forbidden_phrases" not in rules_fired("Ship it soon. TBD.\n", cfg)


# -- rules disable cleanly ---------------------------------------------------


def test_every_rule_is_a_no_op_under_an_empty_config():
    empty: dict = {}
    text = ENUMERATION + CODE + '\nQuote: "x". TBD. Result: latency improved.\n'
    assert content_rules.check_text(text, empty) == []


def test_violation_renders_with_its_rule_name():
    violation = content_rules.Violation("check_forbidden_phrases", "boom")
    assert str(violation) == "[check_forbidden_phrases] boom"


def test_rules_tuple_covers_every_public_check():
    exported = {
        name
        for name in content_rules.__all__
        if name.startswith("check_") and name != "check_text"
    }
    assert {rule.__name__ for rule in content_rules.RULES} == exported
