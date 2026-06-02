````markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill provides a comprehensive guide to the development patterns, coding conventions, and workflows used in the `financial-asset-relationship-db` Python codebase. It covers best practices for file organization, code style, dependency management, CI/CD configuration, and testing. The goal is to help contributors quickly become productive and maintain consistency across the project.

## Coding Conventions

### File Naming

- Use **snake_case** for all Python files and modules.
  - Example: `asset_manager.py`, `relationship_db.py`

### Import Style

- Prefer **relative imports** within the package.
  - Example:
    ```python
    from .models import Asset
    from ..utils import parse_relationships
    ```

### Export Style

- Use **named exports** (i.e., explicitly define what is exported from a module).
  - Example:
    ```python
    __all__ = ['AssetManager', 'RelationshipDB']
    ```

### Commit Messages

- Mixed commit types, often using the `fix` prefix for bug fixes.
- Keep commit messages concise but descriptive (average ~62 characters).
  - Example: `fix: handle missing asset relationships in API response`

## Workflows

### python-test-file-edit-workflow

**Trigger:** When you need to fix, refactor, or improve a specific Python test file (e.g., for isolation, redundancy, or correctness).
**Command:** `/edit-test-file`

1. Edit a test file in `tests/unit/` (e.g., `test_api.py` or `test_api_main.py`).
2. Commit with a message referencing the fix, refactor, or improvement.
3. Optionally, repeat with further small edits (e.g., updating docstrings, fixtures, or pre-commit fixes).

**Example:**

```bash
# Edit tests/unit/test_api.py to fix a failing test
git add tests/unit/test_api.py
git commit -m "fix: correct asset linking logic in test_api"
```
````

---

### ci-workflow-configuration-update

**Trigger:** When you want to add, fix, or update CI/CD automation, security scanning, or labeling rules.
**Command:** `/update-ci-workflow`

1. Edit or add one or more YAML files under `.github/workflows/` or `.github/`.
2. Commit with a message referencing the workflow or config change.
3. Optionally, repeat to fix syntax, add conditions, or handle errors.

**Example:**

```bash
# Update Snyk security workflow
git add .github/workflows/snyk-security.yml
git commit -m "fix: update Snyk workflow for new scan rules"
```

---

### dependency-version-bump-or-fix

**Trigger:** When you need to fix dependency conflicts or update allowed versions for a package.
**Command:** `/bump-dependency-version`

1. Edit `pyproject.toml` and/or `requirements.txt` to change version specifiers.
2. Commit with a message referencing the dependency and reason for change.
3. Optionally, repeat to further restrict or loosen version bounds.

**Example:**

```bash
# Bump SQLAlchemy version in requirements.txt
git add requirements.txt
git commit -m "fix: bump SQLAlchemy to >=1.4,<2.0 for compatibility"
```

---

### merge-main-into-feature-branch

**Trigger:** When you want to bring the latest changes from main into your working branch before continuing work or opening a PR.
**Command:** `/merge-main`

1. Merge the `main` branch into your feature/fix branch.
2. Resolve any conflicts.
3. Commit the merge with a standard message.

**Example:**

```bash
git checkout feature/my-feature
git merge main
# Resolve conflicts if any
git commit -m "Merge branch 'main' into feature/my-feature"
```

## Testing Patterns

- **Framework:** Although the main codebase is Python, tests are written using **jest** (typically for TypeScript/JavaScript).
- **Test File Pattern:** Test files follow the `*.test.ts` naming convention.
  - Example: `relationship_api.test.ts`
- **Location:** Tests are usually placed in a `tests/unit/` directory for Python, and possibly in a separate directory for TypeScript tests.
- **Test Structure:** Tests are modular and focus on unit-level isolation, often edited iteratively for correctness and clarity.

**Example Jest Test:**

```typescript
// relationship_api.test.ts
import { getRelationship } from "../src/relationship_api";

test("returns correct relationship", () => {
  expect(getRelationship("A", "B")).toBe("parent");
});
```

## Commands

| Command                  | Purpose                                                          |
| ------------------------ | ---------------------------------------------------------------- |
| /edit-test-file          | Edit, refactor, or fix a specific Python test file               |
| /update-ci-workflow      | Update or fix CI/CD workflow YAML files                          |
| /bump-dependency-version | Adjust dependency versions in pyproject.toml or requirements.txt |
| /merge-main              | Merge the main branch into your feature or fix branch            |

```

```
