# Security Policy

## Supported versions

Only the latest released tag receives security fixes. Pin a released `v*` tag;
`main` is unstable.

## Reporting a vulnerability

Please report suspected vulnerabilities privately. Do **not** open a public
issue for a security report.

- Preferred: open a private advisory via GitHub's **Security → Report a
  vulnerability** tab on this repository.
- Fallback, if that tab is unavailable to you: email **backroadcreativeco@gmail.com** with
  `hugo-quality-ci security` in the subject.

Please include the affected version or commit, a description of the issue and
its impact, reproduction steps, and any suggested remediation.

## What to expect

- Acknowledgement within 5 business days.
- An initial assessment and severity triage within 10 business days.
- Coordinated disclosure: we agree a timeline with you before any public
  write-up, and credit reporters who want it.

## Scope

**In scope**

- The workflow in `workflows/` — in particular the pinned `htmltest` download
  and checksum verification, and the `permissions:` block.
- The Node script under `scripts/` and the Python package under `python/`,
  including anything that reads a file path or a config value from a repository
  under test.
- The Hugo partials under `layouts/partials/`, including how site params reach
  rendered output.

**Out of scope**

- Findings about a *site you point these tools at*. This project reports on your
  content; it is not the vulnerable surface there.
- Issues in the third-party tools the workflow invokes — `htmltest`, `pa11y-ci`,
  Lighthouse CI, and the GitHub Actions it uses. Report those upstream. If the
  problem is that *this* project invokes one of them unsafely, that is in scope.

## Notes for adopters

- The workflow runs on `pull_request` and grants `contents: read` only. Keep it
  on a GitHub-hosted runner. A `pull_request`-triggered workflow on a
  self-hosted runner lets a fork PR queue arbitrary jobs onto that machine.
- The `htmltest` download is pinned by SHA-256. If you bump the version, bump
  the checksum in the same change — an unverified download runs whatever the
  release URL serves.
- Every action is pinned to a commit SHA rather than a tag, because a tag can be
  repointed.
