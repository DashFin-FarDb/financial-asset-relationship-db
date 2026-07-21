# CI Required Checks Policy

**Status:** Active
**Scope:** Defines the required, advisory, scheduled, and release-only CI checks for the repository.

## Principle

GitHub Actions is the canonical PR gate. We shift heavyweight scanners off the per-PR path to keep the feedback loop fast.

## Categories

### 1. Required for Merge

These checks run on every PR and push to `main`. They must pass before a PR can be merged.

- **Frontend CI (`frontend-ci.yml`)**: Lint, test, and build for the Next.js frontend.
- **Backend CI (`ci.yml`)**: Python lint, format, type-check, and unit/integration tests.
- **Production Container Smoke (`production-container.yml`)**: Verifies that the FastAPI and Next.js Docker images build and start cleanly.

### 2. Advisory

These checks run on PRs but are not strictly required for merge (e.g., they might fail due to strictness, but give useful feedback).

- Dependabot PRs (though patch/minor updates can auto-merge if tests pass).

### 3. Scheduled / Release-Only

These are heavyweight or scanner jobs that run on a daily/weekly schedule or during a release-candidate cut to reduce PR noise. Some scanners may still run on PRs when their workflow `on:` includes `pull_request`/`push`.

- Scheduled / release-only: Snyk Security/Container/Infrastructure (`snyk-*.yml`), Bearer (`bearer.yml`)
- Scheduled + push-to-main: Trivy (`trivy.yml`), Bandit (`bandit.yml`), CodeQL (`codeql.yml`), Dependency Check (`dependency-check.yml`)
- Scheduled + PR/push: Semgrep (`semgrep.yml`)

### 4. Release-only / dispatch (not PR merge gates)

These workflows prove hosted durability, staging/production promotion, and hardening backlog items. They are
**not** required branch-protection checks for ordinary PR merge. RC cuts must run them explicitly.

| Workflow                      | Purpose                                                | Hardening notes                                                                                                                                                                             |
| ----------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `release-evidence-verify.yml` | Pytest gate bundles + hosted readiness + gate summary  | Input allows only `none` / `P0`. Default `P0` forces strict hosted readiness (fail on SKIPPED). Use `none` only for soft rehearsal. P1–P3 are backlog IDs until tier-specific checks exist. |
| `staging-promotion.yml`       | Evidence-file checklist + live `--require-persistence` | Verifier requires P0 hardening markers (`hardening_ids`, topology, `db_authz`). Live DB authorization fails closed when secrets are missing.                                                 |
| `production-promotion.yml`    | Production twin of staging promotion (H-P1-02)         | Same gates as staging, plus main-only dispatch, readiness bound to `HOSTED_READINESS_BASE_URL`, and `production` / `production-manual-gate` Environments with `production-readiness` artifacts. |
| `hosted-readiness.yml`        | Thin hosted smoke                                      | Does not replace release-evidence, staging-promotion, or production-promotion.                                                                                                              |

Hardening backlog IDs: [Release Evidence Pack](release-evidence-pack.md#hardening-backlog-p0p3).

## Platform Deduplication

- We use GitHub Actions as the primary CI.
- CircleCI Python and Frontend lint/test/build duplication has been minimized or shifted purely to GitHub Actions.

## Follow-up Actions for Maintainers

Update branch protection rules in GitHub settings to require:

- `Frontend CI / build`
- `CI / test`
- `Production Container / build-and-smoke-test`

## Local composite action guardrail (`ci-common`)

Jobs that use the local composite action `./.github/actions/ci-common` must run
`actions/checkout` first. Without checkout, the workflow fails before the job
can execute because local actions are resolved from the checked-out workspace.

Enforcement:

- `tests/unit/test_ci_common_checkout.py::test_ci_common_callers_checkout_first`

When editing workflow YAML that references `ci-common`, validate with:

```bash
pytest tests/unit/test_ci_common_checkout.py -v
```

## Workflow maintenance troubleshooting

- CI fails with "uses ci-common without a preceding actions/checkout":
  - Add an `actions/checkout@...` step before the `uses: ./.github/actions/ci-common` step in the affected job.
- Security/code scanning signal missing from Pyre workflow:
  - Ensure `.github/workflows/pyre.yml` still includes SARIF output and upload (`github/codeql-action/upload-sarif@...`).
- Required check names changed after workflow refactors:
  - Reconcile GitHub branch protection required-check names with this document and the active workflow job names.
