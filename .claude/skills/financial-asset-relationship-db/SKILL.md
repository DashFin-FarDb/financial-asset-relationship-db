````markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you the core development patterns, coding conventions, and automated workflows used in the `financial-asset-relationship-db` Python codebase. You'll learn how to maintain code style, implement features, manage database migrations, and update documentation in a way that aligns with the project's established practices. The repository emphasizes consistent formatting, clear commit messages, and a robust approach to testing and documentation.

## Coding Conventions

- **Language:** Python (no framework detected)
- **File Naming:** Use `snake_case` for all Python files.
  - Example: `graph_lifecycle_providers.py`
- **Import Style:** Prefer relative imports within packages.
  - Example:
    ```python
    from .repository import AssetRepository
    ```
- **Export Style:** Use named exports; avoid wildcard imports.
  - Example:
    ```python
    __all__ = ["AssetRepository", "fetch_assets"]
    ```
- **Commit Messages:** Use clear prefixes such as `style`, `fix`, `docs`, `test`, `refactor`.
  - Example: `fix: handle edge case in lock refresh logic`
- **Formatting:** Code is auto-formatted using tools like Black, isort, Autopep8, and Ruff Formatter. Formatting fixes are often committed separately after main changes.

## Workflows

### Code Formatting Auto-Fix

**Trigger:** When code is committed that does not meet style guidelines, or after a batch of changes is merged.
**Command:** `/format-code`

1. Run code formatting tools (Autopep8, Black, isort, Prettier, Ruff Formatter, StandardJS).
2. Apply formatting fixes to affected files.
3. Commit the changes with a standardized commit message.

_Example:_

```bash
black src/
isort src/
git commit -am "style: auto-format codebase"
```
````

---

### Pre-commit CI Auto-Fix

**Trigger:** When pre-commit CI detects issues after a push or PR merge.
**Command:** `/pre-commit-fix`

1. Run pre-commit hooks on affected files.
2. Apply auto-fixes as recommended by the hooks.
3. Commit the changes with a standardized `[pre-commit.ci] auto fixes` message.

_Example:_

```bash
pre-commit run --all-files
git commit -am "[pre-commit.ci] auto fixes"
```

---

### Feature or Bugfix with Follow-up Formatting

**Trigger:** When implementing a feature or bugfix, followed by formatting/style fixes.
**Command:** `/feature-with-format`

1. Implement the feature or bugfix (update main code and possibly tests).
2. Commit the change.
3. Run formatting tools (manually or via CI).
4. Commit formatting fixes.

_Example:_

```bash
# Implement feature
git add src/data/repository.py
git commit -m "feat: add asset relationship endpoint"

# Format code
black src/
git commit -am "style: format after feature implementation"
```

---

### Feature Development with Tests and Migrations

**Trigger:** When a new feature or major bugfix requires schema changes and test coverage.
**Command:** `/feature-with-migration`

1. Modify or add core logic files (e.g., in `src/data`, `src/logic`, `api/`).
2. Add or update migration SQL scripts in `migrations/`.
3. Update or add tests in `tests/unit` or `tests/integration`.
4. Update documentation if needed.

_Example:_

```bash
# Update models and migrations
vim src/data/db_models.py
vim migrations/003_add_new_field.sql

# Add tests
vim tests/unit/test_repository_cancellation.py

# Commit all changes
git add .
git commit -m "feat: support new asset type with migration and tests"
```

---

### Docs or PR Description Update

**Trigger:** When a new feature or process requires documentation or PR description updates.
**Command:** `/update-docs`

1. Add or update markdown documentation file(s) (e.g., `PR_*.md`, `ISSUE_*.md`, `AGENTS.md`).
2. Commit the changes.
3. Optionally, follow up with a formatting commit.

_Example:_

```bash
vim PR_5C_3C_DESCRIPTION.md
git add PR_5C_3C_DESCRIPTION.md
git commit -m "docs: update PR description for cancellation feature"
```

## Testing Patterns

- **Test Files:** Located in `tests/unit/` and `tests/integration/`.
- **Naming Convention:** Test files use `snake_case` and start with `test_`.
  - Example: `test_lock_refresh_flow.py`
- **Test Framework:** Not explicitly detected, but likely uses `pytest` or similar.
- **Test Patterns:** Each test module targets a specific feature or flow, often reflecting recent changes or bugfixes.

_Example test:_

```python
def test_lock_refresh_flow():
    # Arrange
    repo = AssetRepository()
    # Act
    result = repo.refresh_lock()
    # Assert
    assert result is True
```

## Commands

| Command                 | Purpose                                                      |
| ----------------------- | ------------------------------------------------------------ |
| /format-code            | Auto-format the codebase to meet style guidelines            |
| /pre-commit-fix         | Apply pre-commit CI auto-fixes for linting/formatting issues |
| /feature-with-format    | Implement a feature or bugfix, then apply formatting fixes   |
| /feature-with-migration | Implement a feature/bugfix with migrations and tests         |
| /update-docs            | Add or update documentation or PR description files          |

```

```
