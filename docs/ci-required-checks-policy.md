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

## Platform Deduplication

- We use GitHub Actions as the primary CI.
- CircleCI Python and Frontend lint/test/build duplication has been minimized or shifted purely to GitHub Actions.

## Follow-up Actions for Maintainers

Update branch protection rules in GitHub settings to require:

- `Frontend CI / build`
- `CI / test`
- `Production Container / build-and-smoke-test`
