# PR Copilot

PR Copilot is an on-demand, exact-head status reporter for pull requests in
this repository. It is deliberately read-only and advisory.

## Supported commands

Use one of these exact phrases in a pull-request comment:

- `@pr-copilot status update`
- `@pr-copilot progress report`
- `@pr-copilot show status`

The `@pr_copilot` alias accepts the same three phrases. Other comments do not
start the workflow. A maintainer may also run the workflow manually with a pull
request number.

## Output and authority

The reporter inspects the pull request at its current head commit and writes a
GitHub Actions job summary plus a seven-day workflow artifact. It does not:

- post or update pull-request comments;
- submit, acknowledge, or resolve reviews;
- decide merge readiness;
- enable auto-merge or merge a pull request; or
- react automatically to commits, reviews, or completed checks.

The report is a snapshot, not merge authorization. GitHub Actions remains the
canonical CI/CD pipeline. CircleCI is a secondary, short-term parallel test
lane and cannot overrule GitHub Actions or branch protection.

## Optional local helpers

The scripts in [`scripts`](scripts) are not part of the active status workflow:

- `analyze_pr.py` analyses pull-request size, complexity, and scope.
- `suggest_fixes.py` classifies review text and produces local suggestions.

They read only the `scope` and `review_handling` sections of
`.github/pr-copilot-config.yml`. Running a helper does not grant it permission
to write to GitHub.

For repository setup and verification, see [SETUP.md](SETUP.md).
