# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0

First release.

### Added

- **`workflows/pr-ci.yml`** — a GitHub Actions workflow gating every pull
  request on a Hugo build, front-matter validation, content-accuracy rules,
  checksum-pinned sudo-free `htmltest` link checking (internal and external),
  `pa11y-ci` WCAG2AA against a locally served build on a dynamically allocated
  port, and Lighthouse CI. All actions pinned to commit SHAs. Two steps are
  documented extension points for site-specific checks and are no-ops until
  those files exist.
- **`hugo_quality.frontmatter`** — structural front-matter validation: code-fence
  wrappers, front matter not on line 1, unterminated or malformed YAML, missing
  required fields, and Hugo's `0001-01-01` zero-value date. Console script
  `hugo-validate-frontmatter`; exits 2 when pointed at a directory that does not
  exist.
- **`hugo_quality.content_rules`** — five content-accuracy rules as pure
  functions: undisclosed enumerations, unhedged outcome claims on unfinished
  work, unattributed quotations, unqualified code examples, and forbidden
  phrases. Every rule is a no-op under empty configuration.
- **`hugo_quality.content_check`** — a packaged pytest module that runs those
  rules over a real site (`pytest --pyargs hugo_quality.content_check`). Skips
  rather than passing when it finds no posts.
- **`hugo_quality.updater`** — `HugoFrontMatterUpdater`, an atomic,
  backup-creating YAML front-matter rewriter that preserves the body byte for
  byte. Console script `hugo-update-frontmatter`.
- **`hugo_quality.config`** — one `.hugo-quality.json` shared by the Python and
  Node validators, with documented defaults for a stock Hugo site.
- **`scripts/validate-generated-post.js`** — a Node (stdlib-only) validator for
  machine-written pages: placeholder rows, empty descriptions, raw commit SHAs
  in prose fields, a word-count floor, and a real change list in either bullet
  or legacy-table form.
- **`layouts/partials/jsonld.html`** — emits at most one JSON-LD block per page
  (Organization, BlogPosting with publisher, SoftwareApplication), built with
  Hugo `dict`/`jsonify` rather than string concatenation, driven entirely by
  site params.
- **`layouts/partials/head.html`** — title, description, canonical, Open Graph,
  Twitter card, feed autodiscovery and `noindex` on taxonomy pages, with no
  assumptions about CSS or JS tooling.
- **`config/`** — ready-to-edit `pa11yci.json`, `lighthouserc.json` and
  `htmltest.yml`.
- **`examples/CONTENT_GUIDELINES.md`** — a starting point for documenting the
  content-accuracy rules to writers.
- Test suites for all of the above, including a fixture Hugo site that is built
  and asserted on, and guards keeping the workflow's file references honest.
