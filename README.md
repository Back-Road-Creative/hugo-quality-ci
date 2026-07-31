# hugo-quality-ci

Make a Hugo site's pull requests provable.

Most static-site setups check nothing until deploy: a broken link, an
accessibility regression, a front-matter date Hugo could not parse, a generated
release note that came out empty. All of those are cheap to catch on the pull
request and expensive to catch after merge, when the artifact already exists and
someone has to undo it.

This repository is the set of pieces that move those checks left:

| Piece | What it is |
|---|---|
| `workflows/pr-ci.yml` | One GitHub Actions workflow that gates every PR on a clean Hugo build, front matter, content accuracy, link checking, WCAG2AA accessibility and Lighthouse. |
| `python/hugo_quality/` | The Python validators: front-matter structure, content-accuracy rules, and an atomic front-matter rewriter. |
| `scripts/validate-generated-post.js` | A Node validator for machine-written pages (release notes, changelogs) that catches the ones that generated nothing. |
| `layouts/partials/` | Hugo partials emitting exactly one JSON-LD block per page, plus a head partial with canonical, Open Graph and Twitter meta. |
| `config/` | Ready-to-edit configs for pa11y-ci, Lighthouse CI and htmltest. |
| `examples/CONTENT_GUIDELINES.md` | A house style guide you can copy into your own site, written so each rule the CI enforces has a plain-English "instead of / write" example next to it. |

Take all of it or take one piece. Nothing here depends on anything else here,
except that the workflow runs the validators.

## Requirements

- **Hugo extended >= 0.139**
- **Node >= 18.19** — every script is stdlib-only, so adopting them does not
  change your site's dependency tree
- **Python >= 3.11** with `pyyaml` and `pytest`

## Install

Everything lands at fixed relative paths under your site root, and the workflow
expects them there.

```bash
git clone <this-repo-url> /tmp/hqci
cd /path/to/your-hugo-site

mkdir -p .github/workflows config scripts python layouts/partials
cp /tmp/hqci/workflows/pr-ci.yml   .github/workflows/
cp -r /tmp/hqci/config/.           config/
cp -r /tmp/hqci/scripts/.          scripts/
cp -r /tmp/hqci/python/.           python/
cp /tmp/hqci/.hugo-quality.json    .

# Optional: the structured-data and head partials.
# If your site uses a theme, put these under themes/<theme>/layouts/partials/.
cp /tmp/hqci/layouts/partials/*.html layouts/partials/

# Optional: the writer-facing explanation of the content rules, to adapt.
cp /tmp/hqci/examples/CONTENT_GUIDELINES.md docs/
```

Then do three things:

1. **Set your domain.** In `.github/workflows/pr-ci.yml`, change
   `SITE_DOMAIN: 'example.com'`. That value is what the link checker skips when
   it meets your own canonical URLs, which point at the live site and are stale
   by design until this change deploys.
2. **List your pages.** Edit the `urls` in `config/pa11yci.json` and
   `config/lighthouserc.json` — one page per distinct template is enough, since
   a template fixed once is fixed everywhere.
3. **Describe your content.** Edit `.hugo-quality.json` (see below). At minimum
   set `postSections` to the sections that hold your dated posts.

Finally, make the workflow a **required status check** under Settings →
Branches → branch protection. Without that it draws a red X that anyone can
merge straight past, which is a report, not a gate.

### Using the Python package on its own

```bash
pip install /path/to/this/repo     # not on PyPI yet; install from a checkout
```

That gives you `hugo-validate-frontmatter`, `hugo-update-frontmatter` and the
`hugo_quality` import path. The workflow deliberately does *not* install it —
it sets `PYTHONPATH=python` and imports the vendored copy, so a site pins the
validators by committing them rather than by resolving a version at CI time.

## Configuration

One file, `.hugo-quality.json` at your site root, read by both the Python and
Node validators. Every key is optional; the defaults describe a stock Hugo site
whose posts live in `content/blog/`.

```json
{
  "contentDir": "content",
  "postSections": ["blog"],
  "requiredFields": ["title"],
  "postRequiredFields": ["title", "date"],
  "skipFiles": ["_index.md"],

  "generatedPost": {
    "minWordCount": 100,
    "placeholderPhrases": ["General improvements", "See release notes"],
    "shaFreeFields": ["summary", "description"],
    "requireChangeList": true
  },

  "contentAccuracy": {
    "maxUndisclosedBullets": 3,
    "forbiddenPhrases": ["TBD", "FIXME", "lorem ipsum"]
  }
}
```

The full default is in [`.hugo-quality.json`](.hugo-quality.json) and, with
comments explaining each key, in
[`python/hugo_quality/config.py`](python/hugo_quality/config.py).

## What each check does

### Front matter (`python -m hugo_quality.frontmatter`)

Catches the ways front matter fails *without* failing the build:

- the file is wrapped in a code fence, so Hugo reads the front matter as body
  text and every field silently defaults;
- the front matter does not start on line 1, which Hugo ignores entirely;
- the YAML block is unterminated or malformed;
- a required field is missing or null;
- the date is `0001-01-01`, Hugo's tell that it could not parse what it was
  given.

```bash
python -m hugo_quality.frontmatter --content content
```

Exit 0 clean, 1 on violations, 2 when the content directory does not exist —
so pointing it at the wrong place fails loudly instead of passing over nothing.

### Content accuracy (`pytest --pyargs hugo_quality.content_check`)

Five editorial rules, each a pure function you can call directly from
[`content_rules.py`](python/hugo_quality/content_rules.py):

| Rule | Fails when |
|---|---|
| `check_undisclosed_enumeration` | A heading like "What changed" is followed by more than N precise bullets, with nothing on the page saying the list was confirmed. |
| `check_unhedged_results` | A page says the work is unfinished and also states an outcome as settled ("Result: latency reduced by half"). |
| `check_quote_attribution` | The page quotes someone and has no source section. |
| `check_unqualified_code_examples` | A code block calls several specific-looking functions and nothing above it marks the block as an example. |
| `check_forbidden_phrases` | Any phrase you have decided never to publish appears — `TBD`, `FIXME`, an internal codename. |

Every rule is driven by `contentAccuracy` config, and every rule is a no-op
when its config is empty, so you can adopt them one at a time.

```bash
HUGO_SITE_ROOT=/path/to/site pytest --pyargs hugo_quality.content_check -v
```

A gate nobody explained is a gate writers route around, so
[`examples/CONTENT_GUIDELINES.md`](examples/CONTENT_GUIDELINES.md) states each
rule in prose with an "instead of / write" pair. Copy it into your own site,
adapt the voice, and delete the parts you do not enforce.

With no posts under the configured sections it **skips** rather than passing.
A green gate over zero files is worse than no gate.

### Generated posts (`node scripts/validate-generated-post.js`)

Release-note generators fail quietly: the script runs, exits 0, and writes a
page that is structurally perfect and editorially empty. This catches
placeholder rows left by an empty change list, a description that trails off
mid-sentence, raw commit SHAs dumped into a summary field, a body under the
word floor, and a post with no change list at all.

```bash
node scripts/validate-generated-post.js content/releases/*.md
```

It accepts a change list as either grouped bullets or a legacy markdown table,
because an archive outlives a format change and rejecting the old shape would
turn every historical page red.

### Links (htmltest)

Internal *and* external, so a moved upstream docs page fails before merge
rather than sitting live. The binary is fetched with a pinned SHA-256 and
extracted to a user-writable directory — no `sudo`, and an unexpected artifact
at the release URL fails the job instead of running.

The ignore list in [`config/htmltest.yml`](config/htmltest.yml) is short on
purpose. Each entry is a URL that *cannot be checked correctly* — your own
domain, whose canonical links point at the not-yet-deployed live site; social
platforms that answer CI runners with 403 and 429 because they think you are a
robot, which they are right about.

### Accessibility (pa11y-ci, WCAG2AA)

Runs against the locally built site, served on a port the kernel picks: the
workflow binds port 0 and reads back what it got. Hardcoding a port means two
concurrent jobs on one machine collide, and the failure looks like an
accessibility regression rather than a busy socket.

### Lighthouse CI

Performance and best-practices as warnings, accessibility and SEO as errors.
Adjust the thresholds in [`config/lighthouserc.json`](config/lighthouserc.json)
to whatever you can actually hold.

## Structured data

[`layouts/partials/jsonld.html`](layouts/partials/jsonld.html) emits **at most
one** `<script type="application/ld+json">` block per page. Two blocks on one
page is the most common way a site's structured data gets ignored: a consumer
picks one and drops the rest, and which one is not yours to choose.

Selection is by page type:

- the home page, and any path in `params.jsonld.organization_paths` →
  `Organization`
- a regular page in `params.jsonld.post_section` → `BlogPosting`, with the
  Organization as its publisher
- the path at `params.jsonld.software.path` → `SoftwareApplication`
- everything else → nothing

The JSON is built with Hugo's `dict` and rendered with `jsonify`, never
assembled as a string. Hand-written JSON in a template breaks the first time a
title contains a quote or an ampersand, and the failure is invisible in the
rendered page.

Site params, all optional except `description`:

```toml
[params]
description = "One sentence about the site."
author = "Your Name"
tagline = "appended to the site title on the home page"
ogImage = "/images/og.png"
sameAs = ["https://github.com/you", "https://example.net/@you"]
twitter_handle = "@you"
color_scheme = "dark"
favicon = "/favicon.svg"
theme_color = "#101010"
stylesheets = ["/css/site.css"]
scripts = ["/js/site.js"]

[params.jsonld]
organization_paths = ["/about/"]
post_section = "blog"

# Omit this table entirely to skip the SoftwareApplication block.
[params.jsonld.software]
path = "/docs/"
name = "your-tool"
version = "1.4.0"
download_url = "https://example.com/download"
application_category = "DeveloperApplication"
operating_system = "Linux, macOS, Windows"
price = "0"
price_currency = "USD"
license = "https://opensource.org/license/mit"
```

[`head.html`](layouts/partials/head.html) covers title, description, canonical,
Open Graph, Twitter card, feed autodiscovery, `noindex` on taxonomy pages, and
calls the JSON-LD partial. It assumes no CSS framework and no JS bundle — list
your own in `params.stylesheets` and `params.scripts`.

## Editing front matter after publish

`HugoFrontMatterUpdater` exists for metadata that only becomes known after a
page is live: a video URL, a canonical ID, a review date.

```python
from pathlib import Path
from hugo_quality import HugoFrontMatterUpdater

updater = HugoFrontMatterUpdater()          # backups on by default
updater.update(Path("content/blog/post.md"), {"video_url": "https://youtu.be/dQw4w9WgXcQ"})
updater.add_youtube_video(Path("content/blog/post.md"), "https://youtu.be/dQw4w9WgXcQ")
```

or from a shell:

```bash
hugo-update-frontmatter content/blog/post.md --set draft=false --set weight=3
```

Guarantees:

- **The body is preserved byte for byte.** It is sliced out of the original
  text and concatenated back unchanged; it is never parsed or re-rendered. A
  horizontal rule in your prose is not mistaken for the closing delimiter, and
  neither is a `---` inside a quoted title.
- **Writes are atomic** — temp file, then rename — so an interrupted run leaves
  the original intact.
- **A backup is taken by default**, timestamped when one already exists.

## Honest limits

- **The workflow is not a drop-in for every site.** It assumes `public/` as the
  build output and a `content/` tree. Two steps (`scripts/test_data_contract.py`
  and `scripts/verify-facts.js`) are extension points that do nothing until you
  add those files — that is deliberate, and the shape is the useful part.
- **The content-accuracy rules are heuristics.** They read prose with regular
  expressions. They will occasionally flag something fine; tune the thresholds
  or narrow `postSections` rather than deleting the rule.
- **Nothing here validates rendered HTML semantics** beyond what pa11y and
  Lighthouse check. There is no HTML validator step.
- **External link checking is flaky by nature.** Upstream sites go down; a red
  link check is sometimes about them. The ignore list is where you record that,
  with the reason next to it.
- **The Python package is not on PyPI yet.** Install it from a checkout, or
  vendor `python/` as the workflow does.
- **`pa11y-ci` and Lighthouse need Chrome.** The workflow uses the one
  GitHub-hosted runners ship. Locally you will need your own.

## Development

```bash
pip install -e ".[test]"
pytest -q        # Python validators, workflow guards, and the Hugo partials
npm test         # Node validator (no install step: zero dependencies)
```

The partial tests build a fixture site with Hugo and assert on the rendered
output, so they need `hugo` on PATH; without it they skip. Set
`HUGO_QUALITY_REQUIRE_HUGO=1` — as CI does — to turn that skip into a failure.

## Licence

MIT. See [LICENSE](LICENSE).
