"""Content-accuracy rules for published prose.

These are editorial rules, not spelling rules. Each one catches a way a draft
can read as more certain than its sources are:

1. an enumerated list of specifics where nothing says the specifics were
   confirmed;
2. a definitive outcome claim on a page that also says the work is unfinished;
3. a quotation with no source section;
4. a code sample full of specific-looking API calls with nothing marking it as
   illustrative;
5. a phrase the site has decided never to publish.

Every rule is a pure function of ``(body, cfg)`` returning
:class:`Violation` objects, so they are testable without a site on disk and
usable from a linter, a pytest run, or an editor plugin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

__all__ = [
    "Violation",
    "RULES",
    "check_text",
    "split_document",
    "check_undisclosed_enumeration",
    "check_unhedged_results",
    "check_quote_attribution",
    "check_unqualified_code_examples",
    "check_forbidden_phrases",
]

_FRONTMATTER = re.compile(r"^---\n(?P<yaml>.*?)\n---\n?(?P<body>.*)$", re.DOTALL)


@dataclass(frozen=True)
class Violation:
    """One rule failure. ``rule`` is the function name, for stable filtering."""

    rule: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.rule}] {self.message}"


def split_document(text: str) -> tuple[str, str]:
    """Return ``(frontmatter_source, body)``. Both are ``""`` when absent."""
    match = _FRONTMATTER.match(text)
    if not match:
        return "", text
    return match.group("yaml"), match.group("body")


def _contains_any(haystack: str, needles: list[str]) -> bool:
    lowered = haystack.lower()
    return any(needle.lower() in lowered for needle in needles)


def check_undisclosed_enumeration(body: str, cfg: dict[str, Any]) -> list[Violation]:
    """Flag a long list of specifics under an enumerating heading.

    A heading such as "What changed" followed by a dozen precise bullets reads
    as a disclosure even when the underlying source said something vague. The
    rule passes if the page either carries a disclaimer or reports the work in
    the past tense, which is the shape of something already confirmed.
    """
    headings = cfg.get("enumerationHeadings", [])
    limit = int(cfg.get("maxUndisclosedBullets", 3))
    disclaimers = cfg.get("disclaimerPhrases", [])
    verbs = cfg.get("confirmationVerbs", [])

    if not headings:
        return []

    has_disclaimer = _contains_any(body, disclaimers)
    is_confirmed = bool(verbs) and re.search(
        r"\b(?:%s)\b" % "|".join(re.escape(v) for v in verbs), body, re.IGNORECASE
    )
    if has_disclaimer or is_confirmed:
        return []

    violations: list[Violation] = []
    # `\n+` between heading and bullets: markdown convention puts a blank line
    # there, and requiring the bullets on the very next line made the rule
    # silently match nothing.
    for heading, bullets in re.findall(r"^(#{2,6} .*)\n+((?:[-*] .*\n)+)", body, re.MULTILINE):
        if not _contains_any(heading, headings):
            continue
        count = len([line for line in bullets.splitlines() if line.strip()])
        if count > limit:
            violations.append(
                Violation(
                    "check_undisclosed_enumeration",
                    f"{heading.strip()!r} lists {count} specific items with no "
                    f"disclosure note and no past-tense confirmation "
                    f"(limit {limit})",
                )
            )
    return violations


def check_unhedged_results(body: str, cfg: dict[str, Any]) -> list[Violation]:
    """Flag a definitive outcome claim on a page that says work is unfinished."""
    indicators = cfg.get("pendingIndicators", [])
    pattern = cfg.get("resultClaimPattern")
    hedges = cfg.get("hedgePrefixes", [])
    if not indicators or not pattern:
        return []

    if not _contains_any(body, indicators):
        return []

    claims = re.findall(pattern, body, re.IGNORECASE)
    if not claims:
        return []
    if _contains_any(body, hedges):
        return []

    hedge_hint = ", ".join(hedges) if hedges else "a hedged form"
    return [
        Violation(
            "check_unhedged_results",
            f"page describes unfinished work but states {claims[0]!r} as settled; "
            f"use one of: {hedge_hint}",
        )
    ]


def check_quote_attribution(body: str, cfg: dict[str, Any]) -> list[Violation]:
    """Flag a quotation with no source section."""
    marker = cfg.get("quoteMarker")
    heading = cfg.get("sourceHeading")
    if not marker or not heading:
        return []
    if marker.lower() not in body.lower():
        return []
    if heading.lower() in body.lower():
        return []
    return [
        Violation(
            "check_quote_attribution",
            f"contains {marker!r} but no {heading!r} section",
        )
    ]


def check_unqualified_code_examples(body: str, cfg: dict[str, Any]) -> list[Violation]:
    """Flag a code block of specific-looking calls with no illustrative marker.

    A fenced block full of ``snake_case(`` calls reads as a real API. If the
    prose immediately above it does not mark the block as an example, a reader
    will try to call those functions.
    """
    pattern = cfg.get("codeCallPattern")
    limit = int(cfg.get("maxUnqualifiedCalls", 2))
    qualifiers = cfg.get("exampleQualifiers", [])
    if not pattern:
        return []

    violations: list[Violation] = []
    for match in re.finditer(r"```[^\n]*\n(.*?)```", body, re.DOTALL):
        code = match.group(1)
        calls = re.findall(pattern, code)
        if len(calls) <= limit:
            continue
        context = body[max(0, match.start() - 200) : match.start()]
        if _contains_any(context, qualifiers):
            continue
        violations.append(
            Violation(
                "check_unqualified_code_examples",
                f"code block calls {len(calls)} specific functions "
                f"({', '.join(sorted(set(calls))[:3])}) with no example/pattern "
                f"qualifier in the preceding text",
            )
        )
    return violations


def check_forbidden_phrases(body: str, cfg: dict[str, Any]) -> list[Violation]:
    """Flag any phrase the site has decided never to publish.

    Defaults cover drafting scaffolding (``TBD``, ``FIXME``, ``lorem ipsum``).
    Extend it with anything else that must never reach a reader — an internal
    codename, or a present-tense phrasing you only ever want hedged.
    """
    phrases = cfg.get("forbiddenPhrases", [])
    violations: list[Violation] = []
    for phrase in phrases:
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", body, re.IGNORECASE):
            violations.append(
                Violation("check_forbidden_phrases", f"contains forbidden phrase {phrase!r}")
            )
    return violations


#: Every rule, in report order.
RULES: tuple[Callable[[str, dict[str, Any]], list[Violation]], ...] = (
    check_undisclosed_enumeration,
    check_unhedged_results,
    check_quote_attribution,
    check_unqualified_code_examples,
    check_forbidden_phrases,
)


def check_text(text: str, cfg: dict[str, Any]) -> list[Violation]:
    """Run every rule over a markdown document (front matter included or not).

    ``cfg`` is the ``contentAccuracy`` sub-mapping, not the whole config.
    """
    _, body = split_document(text)
    violations: list[Violation] = []
    for rule in RULES:
        violations.extend(rule(body, cfg))
    return violations
