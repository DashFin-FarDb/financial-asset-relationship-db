```markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and workflows used in the `financial-asset-relationship-db` Python codebase. You'll learn the project's coding conventions, how to maintain and update unit tests, and how to use suggested commands to streamline your workflow. The repository focuses on managing relationships between financial assets, with an emphasis on maintainable Python code and robust testing practices.

## Coding Conventions

### File Naming
- Use **snake_case** for all file and module names.
  - **Example:** `asset_manager.py`, `test_api_main.py`

### Import Style
- Prefer **relative imports** within the package.
  - **Example:**
    ```python
    from .models import Asset
    from .utils import calculate_relationships
    ```

### Export Style
- Use **named exports** (explicitly declare what is exported from modules).
  - **Example:**
    ```python
    __all__ = ["AssetManager", "RelationshipCalculator"]
    ```

### Commit Message Patterns
- Commit messages are typically freeform, sometimes prefixed with `fix`.
- Keep commit messages concise (average ~48 characters).
  - **Example:**
    ```
    fix: correct asset relationship calculation bug
    ```

## Workflows

### Unit Test File Iteration
**Trigger:** When you need to fix, improve, or auto-format a unit test file after code changes or review feedback.
**Command:** `/update-unit-test`

1. **Edit** the target unit test file (e.g., `tests/unit/test_api.py`) to fix or improve tests based on code changes or review suggestions.
2. **Apply code review suggestions** from collaborators or automated bots.
3. **Run pre-commit hooks or CI auto-fixes** to enforce formatting and linting.
4. **Repeat** the above steps as needed until tests and formatting are satisfactory.

**Files Involved:**
- `tests/unit/test_api.py`
- `tests/unit/test_api_main.py`

**Frequency:** ~3-4 times per month

**Example:**
```python
# tests/unit/test_api.py

def test_relationship_creation():
    result = create_relationship(asset_a, asset_b)
    assert result is not None
```

## Testing Patterns

- **Framework:** pytest (standard for Python)
- **Test File Pattern:** `test_*.py`
- **Unit Tests:** Use Python test files in `tests/unit/`, named with `test_` prefix.
  - **Example:**
    ```python
    # tests/unit/test_api_main.py
    def test_main_endpoint():
        response = client.get("/api/main")
        assert response.status_code == 200
    ```
  - **Example:**
    ```python
    # tests/unit/test_api_main.py

    def test_main_endpoint():
        response = client.get("/api/main")
        assert response.status_code == 200
    ```

## Commands

| Command            | Purpose                                                        |
|--------------------|----------------------------------------------------------------|
| /update-unit-test  | Iteratively update, fix, and auto-format a unit test file      |

```
