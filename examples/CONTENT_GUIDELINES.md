# Content guidelines (example)

> Copy this into your own site, adapt the voice, and delete this line. It is a
> starting point for telling writers what the automated rules enforce and why,
> not a document to adopt unchanged.

## Purpose

We publish factual observations. A reader should be able to tell, from the page
alone, which claims are confirmed and which are still expected. The rules below
are the ones a machine can check; the judgement behind them is yours.

Enforcement lives in `pytest --pyargs hugo_quality.content_check`, which runs on
every pull request. Thresholds and phrase lists come from `.hugo-quality.json`.

---

## 1. Do not enumerate what you were not told

**Rule.** Do not list specific tasks, features or implementation details under a
heading that reads as a disclosure, unless the source actually disclosed them —
or unless the page says it did not.

**Instead of:**

```markdown
## What changed

- file-system operations
- commit formatting
- status tracking
- error reporting
```

**Write:**

```markdown
## What changed

Routine administrative work moved into tooling.

The specific list was not disclosed. The stated scope was "the boring,
procedural admin tasks".
```

**Rule:** `check_undisclosed_enumeration`.
**Passes if** the page carries a disclaimer phrase, or reports the work in the
past tense ("shipped", "released"), or lists no more than
`maxUndisclosedBullets` items.

---

## 2. Unfinished work gets unfinished language

**Rule.** If the page says work is in progress, do not state its outcome as
settled.

**Instead of:**

```markdown
The rewrite is in progress.

Result: build time reduced by half.
```

**Write:**

```markdown
The rewrite is in progress.

Early results: build time reduced by half.
```

`Expected results:` and `Reported results:` work too — the second is the honest
choice when the number came from someone else.

**Rule:** `check_unhedged_results`.

---

## 3. Quotations name their source

**Rule.** A quotation gets a `## Source` section: who said it, where, when.

**Rule:** `check_quote_attribution`.

---

## 4. Code samples say whether they are real

**Rule.** A code block full of specific-looking function calls will be read as a
real API. Either use generic names, or mark the block.

**Instead of:**

````markdown
```python
build_index(path)
resolve_target(name)
write_manifest(data)
```
````

**Write:**

````markdown
The pattern, roughly:

```python
build_index(path)
resolve_target(name)
write_manifest(data)
```
````

Any of "example", "for instance", "pattern:", "approach:", "hypothetical" or
"illustrative" in the sentence above the block will do.

**Rule:** `check_unqualified_code_examples`.

---

## 5. Some phrases never ship

**Rule.** Drafting scaffolding — `TBD`, `FIXME`, `lorem ipsum` — must not reach
a reader. Add anything else you never want published to `forbiddenPhrases`: an
internal codename, an unreleased product name, a phrasing you only ever want
hedged.

**Rule:** `check_forbidden_phrases`.

---

## Style

- **Report, do not interpret.** State what happened.
- **Passive voice is fine** when the actor is genuinely uncertain.
- **Claims are verifiable** — dates, sources, quotes.
- **When in doubt, state less.**

## Generated pages

Release notes and changelogs are generated, not hand-written, and are checked by
`node scripts/validate-generated-post.js`. A generated page must have a real
change list, a description that is a sentence, a summary free of raw commit
hashes, and a body over the word floor. If the generator produced less than
that, fix the generator — do not hand-edit the output, because the next run
overwrites it.

## Adding a rule

1. Write the failing test in `tests/test_content_rules.py`.
2. Add the rule to `python/hugo_quality/content_rules.py` and to `RULES`.
3. Add its config keys and defaults to `python/hugo_quality/config.py`.
4. Document it here and in the README.

Test, then documentation, then implementation. All in one change.
