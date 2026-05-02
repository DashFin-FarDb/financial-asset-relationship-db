```markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill covers the development patterns, coding conventions, and workflows used in the `financial-asset-relationship-db` Python codebase. The repository focuses on scripts for managing and analyzing financial asset relationships, with a strong emphasis on test coverage, code style consistency, and clear workflows for updating features, tests, and formatting code.

## Coding Conventions

- **File Naming:**  
  Use `snake_case` for all Python files and modules.  
  _Example:_
```

scripts/check_hosted_readiness.py
tests/unit/test_check_hosted_readiness.py

````

- **Import Style:**
Prefer **relative imports** within packages.
_Example:_
```python
from .utils import check_status
````

- **Export Style:**  
  Use **named exports** (explicit function and class definitions).  
  _Example:_

  ```python
  def check_hosted_readiness(...):
      ...
  ```

- **Commit Messages:**
  - Freeform, with occasional prefixes like `style`.
  - Average commit message length: ~52 characters.

- **Code Formatting:**
  - Automated formatting is encouraged (e.g., Black, Ruff).
  - Formatting passes are often applied to single files after changes.

## Workflows

### Script Feature Update and Test Sync

**Trigger:** When adding or updating a script feature and ensuring it is tested  
**Command:** `/update-script-and-tests`

1. Edit or add the feature in `scripts/check_hosted_readiness.py`.
2. Add or update tests in `tests/unit/test_check_hosted_readiness.py` to cover new or changed logic.
3. Commit both the script and test changes together.

_Example:_

```python
# scripts/check_hosted_readiness.py
def check_hosted_readiness(asset_id):
    # ...implementation...

# tests/unit/test_check_hosted_readiness.py
def test_check_hosted_readiness_valid():
    assert check_hosted_readiness("A123") is True
```

---

### Test File Extension and Refinement

**Trigger:** When improving or extending test coverage for an existing feature  
**Command:** `/extend-tests`

1. Edit `tests/unit/test_check_hosted_readiness.py` to add new test cases or clarify existing ones.
2. Commit only the test file changes.

_Example:_

```python
def test_check_hosted_readiness_invalid():
    assert not check_hosted_readiness("INVALID")
```

---

### Script Refactor or Bugfix

**Trigger:** When refactoring or fixing a bug in a script without immediate test changes  
**Command:** `/refactor-script`

1. Edit `scripts/check_hosted_readiness.py` to refactor code or fix a bug.
2. Commit only the script file.

_Example:_

```python
def check_hosted_readiness(asset_id):
    # Improved error handling
    if not asset_id:
        raise ValueError("asset_id required")
    # ...rest of logic...
```

---

### Code Formatting Pass (Single File)

**Trigger:** When applying automated code formatting to a single file  
**Command:** `/format-file`

1. Run a code formatter (e.g., Black, Ruff) on the changed file (`scripts/check_hosted_readiness.py` or `tests/unit/test_check_hosted_readiness.py`).
2. Commit the formatted file.

_Example:_

```bash
black scripts/check_hosted_readiness.py
git add scripts/check_hosted_readiness.py
git commit -m "style: format check_hosted_readiness.py"
```

## Testing Patterns

- **Test File Pattern:**  
  Test files are named with the pattern `*.test.*` or are located in `tests/unit/` with the prefix `test_`.
- **Test Structure:**
  - Tests are written as standalone functions.
  - Each test covers a specific aspect or edge case of the script logic.
  - Test framework is not explicitly specified, but patterns are compatible with `pytest`.

_Example:_

```python
# tests/unit/test_check_hosted_readiness.py
def test_check_hosted_readiness_valid():
    assert check_hosted_readiness("A123") is True
```

## Commands

| Command                  | Purpose                                                 |
| ------------------------ | ------------------------------------------------------- |
| /update-script-and-tests | Add/update a script feature and its corresponding tests |
| /extend-tests            | Add or refine tests for an existing script              |
| /refactor-script         | Refactor or fix a script without immediate test changes |
| /format-file             | Apply code formatting to a single file                  |

```

```
