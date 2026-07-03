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

### 3. Security Scanners and Compliance Checks

To balance developer velocity with security rigor, we enforce distinct required-check policies based on the deployment path:

| Scanner Context | Standard PR (Blocking?) | Release Candidate (Blocking?) | Emergency Release (Blocking?) | Scheduled Audit (Blocking?) |
| --- | --- | --- | --- | --- |
| Snyk Code/Container | No | Yes | No | Yes |
| CodeQL / Semgrep | No | Yes | No | Yes |
| APIsec DAST / SOOS | No | Yes | No | Yes |
| Dependency Check | No | Yes | No | Yes |
| Trivy / Bandit | No | Yes | No | Yes |

- **Standard PR Path:** Scanners are advisory or deferred to the nightly schedule. They do not block merge.
- **Release Candidate Path:** All defined scanners MUST be run and MUST pass (or have findings explicitly approved) before a release candidate can be promoted to staging or production.
- **Emergency Release Path:** Scanners may be bypassed via an exception process, but the post-incident process requires a retroactive audit.
- **Scheduled Audit:** Scanners run automatically. Failures generate alerts that must be triaged within SLA.

## Platform Deduplication

- We use GitHub Actions as the primary CI.
- CircleCI Python and Frontend lint/test/build duplication has been minimized or shifted purely to GitHub Actions.

## Follow-up Actions for Maintainers

Update branch protection rules in GitHub settings to require:

- `Frontend CI / build`
- `Python CI / Test Python 3.10`, `Python CI / Test Python 3.11`, `Python CI / Test Python 3.12`
- `Production Container / build-and-smoke-test`
