# CI Required Checks Policy

**Status:** Active
**Scope:** Defines the required, advisory, scheduled, and release-only CI checks for the repository.
**Hardening:** H-P1-04 — check-run names reconciled across this policy, Mergify auto-merge, and
maintainer branch-protection guidance.

## Principle

GitHub Actions is the canonical PR gate. We shift heavyweight scanners off the per-PR path to keep the feedback loop fast.

GitHub reports **check run names** as each job's `name:` field, or the job ID when `name:` is omitted.
They are **not** `Workflow / job` strings (for example, `Frontend CI / build` is not a real check name).

## Categories

### 1. Required for Merge

#### Always required (every PR targeting `main`)

These workflows have no path filters on `pull_request` and must pass before merge. Use these exact
check-run names in branch protection and Mergify `check-success` conditions:

| Check run name         | Workflow                                          | Job ID                 |
| ---------------------- | ------------------------------------------------- | ---------------------- |
| `Test Python 3.10`     | Python CI (`.github/workflows/ci.yml`)            | `test` (matrix 3.10)   |
| `Test Python 3.11`     | Python CI (`.github/workflows/ci.yml`)            | `test` (matrix 3.11)   |
| `Test Python 3.12`     | Python CI (`.github/workflows/ci.yml`)            | `test` (matrix 3.12)   |
| `Security checks`      | Python CI (`.github/workflows/ci.yml`)            | `security`             |
| `build-and-smoke-test` | Production Container (`production-container.yml`) | `build-and-smoke-test` |

#### Path-filtered (pass when the workflow runs; not a hard branch-protection requirement)

| Check run name | Workflow                                          | Notes                                                                    |
| -------------- | ------------------------------------------------- | ------------------------------------------------------------------------ |
| `frontend-ci`  | Frontend CI (`.github/workflows/frontend-ci.yml`) | Runs only when frontend-related paths change. Do not hard-require in BP. |

### 2. Advisory

These checks run on PRs but are not strictly required for merge (e.g., they might fail due to strictness, but give useful feedback).

- Dependabot PRs (though patch/minor updates can auto-merge if required checks pass).
- `Run eslint scanning` (ESLint workflow) — useful signal; not a merge gate.

### 3. Scheduled / Release-Only

These are heavyweight or scanner jobs that run on a daily/weekly schedule or during a release-candidate cut to reduce PR noise. Some scanners may still run on PRs when their workflow `on:` includes `pull_request`/`push`.

- Scheduled / release-only: Snyk Security/Container/Infrastructure (`snyk-*.yml`), Bearer (`bearer.yml`)
- Scheduled + push-to-main: Trivy (`trivy.yml`), Bandit (`bandit.yml`), CodeQL (`codeql.yml`), Dependency Check (`dependency-check.yml`)
- Scheduled + PR/push: Semgrep (`semgrep.yml`)

### 4. Release-only / dispatch (not PR merge gates)

These workflows prove hosted durability, staging/production promotion, and hardening backlog items. They are
**not** required branch-protection checks for ordinary PR merge. RC cuts must run them explicitly.

| Workflow                      | Purpose                                                   | Hardening notes                                                                                                                                                                                   |
| ----------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `release-evidence-verify.yml` | Pytest gate bundles + hosted readiness + gate summary     | Input allows only `none` / `P0`. Default `P0` forces strict hosted readiness (fail on SKIPPED). Use `none` only for soft rehearsal. P1–P3 are backlog IDs until tier-specific checks exist.       |
| `staging-promotion.yml`       | Evidence-file checklist + live `--require-persistence`    | Verifier requires P0 hardening markers (`hardening_ids`, topology, `db_authz`). Live DB authorization fails closed when secrets are missing.                                                      |
| `production-promotion.yml`    | Production twin of staging promotion (H-P1-02)            | Same gates as staging, plus main-only dispatch, readiness bound to `HOSTED_READINESS_BASE_URL`, and `production` / `production-manual-gate` Environments with `production-readiness` artifacts.   |
| `post-recovery-readiness.yml` | Mandatory post-rollback / post-restore re-smoke (H-P1-03) | Fail-closed `--require-persistence` (assets-smoke via H-P1-01); uploads `post-rollback-readiness` or `post-restore-readiness` with `recovery-metadata.json`. Does not replace promotion/RC gates. |
| `hosted-readiness.yml`        | Thin hosted smoke                                         | Does not replace release-evidence, staging-promotion, production-promotion, or post-recovery-readiness.                                                                                           |

Hardening backlog IDs: [Release Evidence Pack](release-evidence-pack.md#hardening-backlog-p0p3).

## Platform Deduplication

- We use GitHub Actions as the primary CI.
- CircleCI Python and Frontend lint/test/build duplication has been minimized or shifted purely to GitHub Actions.

## Follow-up Actions for Maintainers

Update GitHub **Settings → Branches → Branch protection** required status checks to exactly these
names (no slash forms):

- `Test Python 3.10`
- `Test Python 3.11`
- `Test Python 3.12`
- `Security checks`
- `build-and-smoke-test`

Do **not** add `frontend-ci` as a hard required check: path filters mean the check is absent on
many PRs and would block merge incorrectly.

Do **not** use obsolete names such as `Frontend CI / build`, `CI / test`, or
`Production Container / build-and-smoke-test`.

Mergify auto-merge (`.mergify.yml`) must require the same always-required check-success set.
Live branch-protection edits are outside the repository and must be applied by a maintainer.

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
  - Run `pytest tests/unit/test_ci_required_checks_policy.py -v` to verify policy ↔ workflow ↔ Mergify alignment.
