# Pull Request Template

## Architectural Alignment

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

This PR implements the Release and Deployment Automation layer (Objective 8) aligned with the production path.

## Primary Objective

Implement Objective 8 (Release and Deployment Automation Layer) including CI gates, release verification paths, production Docker containers, and CI deduplication, per the established enterprise readiness plan.

## Scope

### In Scope

- Added Objective 8 to `enterprise-readiness-pr-plan.md` and `enterprise-readiness-pr-board.md`.
- Created ADR 0006 recording the Release and Deployment automation strategy.
- Created `release-evidence-verify.yml` to produce manual release evidence output.
- Created `staging-promotion.yml` and a staging baseline verification script `verify_staging_promotion.py`.
- Configured frontend CI via `.github/workflows/frontend-ci.yml` and installed `jest-junit`.
- Added `Dockerfile.api`, `Dockerfile.frontend`, and `docker-compose.production.yml` for isolated production containers.
- Created `.github/workflows/production-container.yml` to build and smoke test the production container track.
- Deleted `.circleci/config.yml` entirely as part of CI platform deduplication (CircleCI is no longer in use; GitHub Actions is the canonical PR gate). Any legacy branch protection rules that still reference CircleCI must be updated to reference GitHub Actions required checks instead.
- Codified CI required checks policy in `docs/ci-required-checks-policy.md`.
- Implemented `dependabot.yml` for grouped dependency updates and enabled `fail-on-severity` for `dependency-review.yml`.

### Out of Scope

- New graph features.
- New persistence architectures.
- Major frontend redesign.
- Implementation of the operational drill scheduler.

### Files Expected to Change

- `docs/roadmap/enterprise-readiness-pr-plan.md`, `docs/roadmap/enterprise-readiness-pr-board.md`: Added Objective 8.
- `docs/adr/0006-release-and-deployment-automation.md`: Added ADR.
- `.github/workflows/release-evidence-verify.yml`, `.github/workflows/staging-promotion.yml`, `.github/workflows/frontend-ci.yml`, `.github/workflows/production-container.yml`: New GitHub Actions workflows.
- `scripts/verify_staging_promotion.py`: Staging baseline check.
- `Dockerfile.api`, `Dockerfile.frontend`, `docker-compose.production.yml`: Production Docker setups.
- `.github/dependabot.yml`, `.github/workflows/dependency-review.yml`: Dependabot configuration.
- `.circleci/config.yml`: Deleted entirely as part of CI platform deduplication (CircleCI is no longer in use; branch protection must rely on GitHub Actions required checks).
- `.github/workflows/*.yml`: Scanner configurations updated to schedule.

## Validation Commands

```bash
docker-compose -f docker-compose.production.yml build
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective
- [x] Validation commands pass locally or in CI
- [x] Changes align with production architecture (FastAPI + Next.js)

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only (see Primary Objective)
- [x] I have explicitly listed what is out of scope
- [x] If this is a docs/policy/architecture-only PR, I have not mixed those changes with unrelated code changes
- [x] If this is a docs/policy/architecture-only PR, no runtime behavior changes are included
- [x] I have verified the branch, base branch, and referenced PR/commit/ref context before concluding merge status or PR necessity
- [x] I have checked this PR against the production architecture (`FastAPI` backend + `Next.js` frontend)
- [x] I have checked this PR against `.github/AUTOMATION_SCOPE_POLICY.md`
- [x] If this PR changes governed rebuild/recovery/persistence behaviour, I updated `docs/governance/state-machine-and-operating-authority.md` or explicitly proved the canonical interpretation is unchanged

### Testing Best Practices

- [x] Tests verify observable behavior (events, state changes, return values) rather than coupling to implementation details
- [x] Tests avoid coupling to exact log message strings (verify log level instead of message text)
- [x] Tests use polling loops with `time.monotonic()` deadlines instead of fixed `time.sleep()` for timing-dependent assertions
- [x] Tests properly clean up resources (database connections, threads, temp files) in finally blocks

---

**Related Documentation**:

- [PR Scope Guardrails](docs/PR_SCOPE_GUARDRAILS.md)
- [Automation Scope Policy](.github/AUTOMATION_SCOPE_POLICY.md)
