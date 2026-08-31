# PR Copilot setup

PR Copilot runs as a mention-driven, exact-head, read-only status reporter.
The workflow file is `.github/workflows/pr-copilot.yml`.

## Repository settings

1. Enable GitHub Actions for the repository.
2. Set the default workflow permission to **Read repository contents**.
3. Leave **Allow GitHub Actions to create and approve pull requests** disabled.
4. Keep branch protection and required GitHub Actions checks authoritative.

The workflow declares no global token permissions. Its active status job grants
only the read permissions needed to inspect pull-request metadata and checks.
It has no comment, review, readiness, or merge authority.

## Verify the reporter

On an existing pull request, add one supported comment:

```text
@pr-copilot status update
```

`progress report` and `show status` are also supported, as are the same phrases
with the `@pr_copilot` alias. The completed run should contain:

- an exact-head status snapshot in the GitHub Actions job summary; and
- a status artifact retained for seven days.

It must not add or update a pull-request comment. Unrelated comments must not
start the status job.

Maintainers can also use manual workflow dispatch with a pull-request number.

## CI relationship

GitHub Actions is the canonical CI/CD pipeline and branch protection remains
the merge gate. CircleCI is a secondary, short-term parallel test lane intended
to reduce feedback time and provide additional test diagnostics. A CircleCI
result is supporting evidence only; it does not replace or override GitHub
Actions.

## Optional local helpers

`.github/pr-copilot-config.yml` configures only `analyze_pr.py` and
`suggest_fixes.py`. It does not configure workflow triggers, permissions, or
GitHub writes.

Validate the configuration with:

```bash
python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('.github/pr-copilot-config.yml').read_text(encoding='utf-8'))"
```

When troubleshooting, inspect the **PR Copilot Agent** workflow run and confirm
that the command is exact, the comment belongs to a pull request, and the run is
reporting the expected head commit.
