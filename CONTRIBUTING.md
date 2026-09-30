# Contributing

Thanks for taking an interest. This is a small repository and the bar is
straightforward: changes come with tests, and docs land in the same change.

## Reporting

- **Bugs and features:** open an issue. For a bug, include the Hugo, Node and
  Python versions, and the smallest content file that reproduces it.
- **Security vulnerabilities:** do **not** open a public issue. Follow
  [SECURITY.md](SECURITY.md).

## Development setup

```bash
git clone <this-repo-url>
cd hugo-quality-ci

pip install -e ".[test]"
```

Node needs no install step — every script here is stdlib-only and the test
runner is Node's own.

Hugo (extended, >= 0.139) on your PATH is optional but recommended: without it
the partial tests skip, and those are the only tests that check what the
templates actually render.

### Reproducible CI dependencies

CI installs Python packages with `pip install -c constraints/ci.txt`, and pins
pip itself, so a run resolves the same versions until that file changes. Local
setup above is deliberately unconstrained. To update CI's versions, change
`constraints/ci.txt` in its own commit and say why in the message. The Hugo
version is pinned in `.github/workflows/ci.yml` and must match `HUGO_VERSION` in
`workflows/pr-ci.yml`; `tests/test_workflow.py` fails if they drift.

## The gates

Run both before you push. CI runs the same thing across Node 18/20/22 and
Python 3.11/3.12/3.13.

```bash
pytest -q                       # Python validators, workflow guards, partials
npm test                        # Node validator
```

If `pytest` reports skips in `tests/test_partials.py`, Hugo is not installed.
Install it, or accept that you have not tested the partials — CI will, with
`HUGO_QUALITY_REQUIRE_HUGO=1` turning that skip into a failure.

## What a good change looks like

- **Tests first for a bug fix.** Add a test that fails before your change and
  passes after. Never weaken or delete a test to make the suite pass.
- **A new rule is configurable and defaults to off-or-obvious.** Every
  content-accuracy rule reads its thresholds from `.hugo-quality.json` and does
  nothing when its config is empty. A rule nobody can tune gets deleted from
  their site instead of tuned.
- **A new config key is documented in three places, in the same commit:**
  `python/hugo_quality/config.py` (the default and its comment), the
  `.hugo-quality.json` at the root, and the README.
- **New workflow steps pin their actions to a commit SHA**, never a moving tag.
  `tests/test_workflow.py` enforces this.
- **New scripts stay dependency-free.** Node scripts use the standard library
  only; the Python package depends on PyYAML and nothing else. The point is that
  adopting a script does not change the adopting site's dependency tree.

## Commits and pull requests

- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- One logical change per pull request, with the gate output in the description.
- Update the README and `CHANGELOG.md` in the same change as the code. Docs are
  not a follow-up task.

## Conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
