```markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill covers the development patterns and conventions used in the `financial-asset-relationship-db` Python repository. It documents file naming, import/export styles, commit patterns, and testing approaches. Use this guide to contribute code that matches the project's established style and structure.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `asset_manager.py`, `relationship_db.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .models import Asset
    from .utils import calculate_relationship
    ```

### Export Style
- Use **named exports** (explicitly define what is exported).
  - Example:
    ```python
    __all__ = ['Asset', 'RelationshipDB']
    ```

### Commit Patterns
- Freeform commit messages, no strict prefix required.
- Average commit message length: ~34 characters.
  - Example: `Add relationship mapping logic`

## Workflows

### Add a New Financial Asset
**Trigger:** When introducing a new type of financial asset to the database
**Command:** `/add-asset`

1. Create a new model in a snake_case file (e.g., `bond.py`).
2. Use relative imports to reference shared utilities or base classes.
3. Add the new asset class to the `__all__` list in the module.
4. Write or update tests in a corresponding `*.test.*` file.

### Update Asset Relationships
**Trigger:** When modifying how assets relate to each other
**Command:** `/update-relationship`

1. Edit the relevant relationship logic in the appropriate module.
2. Use relative imports for any dependencies.
3. Update or add tests to cover the new relationship logic.
4. Commit changes with a descriptive message.

### Run Tests
**Trigger:** To verify code correctness after changes
**Command:** `/run-tests`

1. Identify all test files matching `*.test.*`.
2. Run the tests using your preferred Python test runner (e.g., `pytest` or `unittest`).
3. Review test output and fix any failures.

## Testing Patterns

- Test files follow the `*.test.*` naming pattern (e.g., `asset_manager.test.py`).
- The specific testing framework is not enforced; use Python's standard testing tools.
- Place test files alongside or near the code they test for clarity.
- Example test file:
  ```python
  # asset_manager.test.py
  from .asset_manager import AssetManager

  def test_add_asset():
      manager = AssetManager()
      assert manager.add('Stock') is True
  ```

## Commands
| Command            | Purpose                                      |
|--------------------|----------------------------------------------|
| /add-asset         | Add a new financial asset model              |
| /update-relationship | Update logic for asset relationships        |
| /run-tests         | Run all test files in the repository         |
```
