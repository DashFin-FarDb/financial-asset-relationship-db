# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches the core development patterns, coding conventions, and common workflows used in the `financial-asset-relationship-db` repository. The project is primarily Python-based, with supporting frontend and CI/CD configuration files.
It emphasizes consistent code style, automated workflows for CI/CD, dependency management, and deployment configuration. This guide will help contributors quickly align with the project's standards and efficiently use the available automation.

## Coding Conventions

**File Naming**

- Use snake_case for Python files and modules.
  - Example: asset_graph.py, financial_models.py

**Import Style**

- Use relative imports within Python modules.
  - Example:
    ```python
    from .models import Asset
    from .utils import calculate_relationship
    ```

**Export Style**

- Use default exports (Python modules/classes/functions as the main export).
  - Example:
    ```python
    # In assetManager.py
    class AssetManager:
        ...
    ```

**Commit Message Patterns**

- Use prefixes like `style:`, `fix:`, `chore:` for clarity.
  - Example: `style: format code with Black`
  - Example: `fix: correct asset relationship calculation`

## Workflows

### CI Workflow Update and Fix

**Trigger:** When addressing CI/CD pipeline issues, updating workflow permissions, or responding to automated PR review findings.
**Command:** /ci-workflow-update-and-fix

1. Edit one or more files in `.github/workflows/` (e.g., `frontend-ci.yml`, `release-evidence-verify.yml`).
2. Make necessary changes to fix pipelines, update permissions, or resolve security findings.
3. Commit with a message referencing fixes, PR feedback, or security findings.
   - Example: `fix: update workflow permissions for code scanning`
4. Push changes and verify CI/CD passes.

**Files Involved:**

- `.github/workflows/frontend-ci.yml`
- `.github/workflows/release-evidence-verify.yml`
- `.github/workflows/staging-promotion.yml`
- `.github/workflows/production-container.yml`
- `.github/workflows/bandit.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/dependency-check.yml`
- `.github/workflows/semgrep.yml`
- `.github/workflows/trivy.yml`
- `.github/workflows/bearer.yml`
- `.github/workflows/snyk-container.yml`
- `.github/workflows/snyk-infrastructure.yml`
- `.github/workflows/snyk-security.yml`
- `.github/workflows/ci.yml`

---

### ESLint Config Update

**Trigger:** When changing ESLint rules, migrating config formats, or fixing lint-related CI failures.
**Command:** /eslint-config-update

1. Edit `frontend/eslint.config.mjs` (and possibly `.eslintrc.json`, `.eslintignore`).
2. Update `frontend/package.json` and/or `package-lock.json` if dependencies change.
3. Commit with a message referencing ESLint, config, or lint errors.
   - Example: `chore: update ESLint config for new rules`
4. Push changes and ensure frontend lint passes.

**Files Involved:**

- `frontend/eslint.config.mjs`
- `frontend/.eslintrc.json`
- `frontend/.eslintignore`
- `frontend/package.json`
- `frontend/package-lock.json`

---

### Code Formatting & Style Fix

**Trigger:** When enforcing code style or fixing formatting issues introduced by previous commits.
**Command:** /code-formatting-style-fix

1. Run code formatters on affected files (e.g., Black for Python, Prettier for JS).
   - Example:
     ```bash
     black .
     ```
2. Commit with a message starting with `style: format code with ...`.
   - Example: `style: format code with Black`
3. Push changes.

**Files Involved:**

- `frontend/eslint.config.mjs`
- `docs/ci-required-checks-policy.md`
- `docs/enterprise-readiness-index.md`
- `docs/roadmap/enterprise-readiness-pr-board.md`
- `docs/roadmap/enterprise-readiness-pr-plan.md`

---

### Docker and Deployment Config Update

**Trigger:** When adjusting deployment configuration, Docker images, or related scripts.
**Command:** `/deployment-config-update`

1. Edit deployment-related files (`Dockerfile.api`, `Dockerfile.frontend`, `docker-compose.production.yml`, or `scripts/verify_staging_promotion.py`).
2. Optionally update related documentation.
3. Commit with a message referencing deployment, Docker, or PR feedback.
   - Example: `chore: update Dockerfile for new Python version`
4. Push changes and verify deployment pipeline.

**Files Involved:**

- `Dockerfile.api`
- `Dockerfile.frontend`
- `docker-compose.production.yml`
- `scripts/verify_staging_promotion.py`
- `docs/ci-required-checks-policy.md`
- `docs/roadmap/enterprise-readiness-pr-board.md`

---

### Dependabot Config Update

**Trigger:** When changing how Dependabot operates (e.g., adding cooldown periods, fixing accidental deletions).
**Command:** `/dependabot-config`

1. Edit `.github/dependabot.yml` as needed.
2. Commit with a message referencing dependabot, cooldown, or security feedback.
   - Example: `chore: add cooldown period to dependabot config`
3. Push changes.

**Files Involved:**

- `.github/dependabot.yml`

---

### Frontend Package Update

**Trigger:** When upgrading frontend dependencies or fixing compatibility issues.
**Command:** `/frontend-deps-update`

1. Edit `frontend/package.json` and/or `frontend/package-lock.json` to update dependencies.
2. Commit with a message referencing update, upgrade, or fix.
   - Example: `fix: upgrade Next.js to v13`
3. Push changes and verify frontend builds and tests pass.

**Files Involved:**

- `frontend/package.json`
- `frontend/package-lock.json`

---

## Testing Patterns

- **Framework:** `pytest` (Python)
- **Test File Pattern:** `test_*.py` and `*_test.py`
- **Location:** `tests/` (configured in `pyproject.toml`)
- **Note:** `tests/benchmarks/` is excluded from default runs via `norecursedirs`.

## Commands

| Command                     | Purpose                                                        |
| --------------------------- | -------------------------------------------------------------- |
| /ci-workflow-update-and-fix | Update or fix CI/CD workflow YAML files                        |
| /eslint-config-update       | Update or fix ESLint configuration for the frontend            |
| /code-formatting-style-fix  | Apply code formatting and style fixes                          |
| /deployment-config-update   | Update Dockerfiles, deployment scripts, or related docs        |
| /dependabot-config          | Update the Dependabot configuration file                       |
| /frontend-deps-update       | Update frontend dependencies (package.json, package-lock.json) |

