```markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill provides a comprehensive guide to the development patterns, coding conventions, and recurring workflows used in the `financial-asset-relationship-db` TypeScript codebase. It covers file organization, code style, commit conventions, and step-by-step instructions for maintaining code quality and consistency, especially around linting and formatting.

## Coding Conventions

- **File Naming:**  
  Use kebab-case for all file names.  
  _Example:_  
  ```
  asset-relationship-manager.ts
  financial-entity-db.ts
  ```

- **Import Style:**  
  Use relative imports for referencing other modules.  
  _Example:_  
  ```typescript
  import { calculateRisk } from './risk-utils';
  ```

- **Export Style:**  
  Use named exports for all modules.  
  _Example:_  
  ```typescript
  export function calculateRisk(asset: Asset): number { ... }
  ```

- **Commit Message Prefixes:**  
  Use the following prefixes to categorize commits:  
    - `feat`: New features  
    - `fix`: Bug fixes  
    - `chore`: Maintenance tasks  
    - `test`: Test-related changes  
    - `style`: Formatting and style changes  
  _Example:_  
  ```
  feat: add support for multi-asset relationships
  fix: correct risk calculation for derivatives
  ```

## Workflows

### ESLint Config Update and Refactor
**Trigger:** When you need to change how ESLint is configured or upgrade its setup in the frontend.  
**Command:** `/eslint-config-update`

1. Edit or replace `frontend/.eslintrc.json` and/or `frontend/.eslintignore` as needed.
2. Add or modify `frontend/eslint.config.mjs` to reflect new configuration or migration.
3. Update `frontend/package.json` and `frontend/package-lock.json` to add, remove, or update ESLint dependencies.
4. Optionally, add or remove compatibility layers (such as FlatCompat) depending on the new setup.
5. Remove or update related test files, such as `frontend/__tests__/config/eslint-upgrade-validation.test.ts`, if necessary.
6. Commit your changes with a descriptive message, e.g.,  
   ```
   chore: migrate ESLint config to flat config format
   ```
7. Run the linter to ensure the new configuration works as expected.

### Code Formatting with Multi-Tool
**Trigger:** When you want to fix style issues or reformat code after major changes.  
**Command:** `/format-code`

1. Run all relevant code formatters (e.g., Prettier, StandardJS) on affected files to enforce style consistency.
2. For documentation and config files, ensure formatting tools are applied as appropriate.
3. Review the changes to confirm only style-related modifications are included.
4. Commit the changes with a message like:  
   ```
   style: reformat codebase with Prettier and StandardJS
   ```
5. Push your changes and verify that CI passes all style checks.

## Testing Patterns

- **Test File Naming:**  
  Test files follow the pattern `*.test.*`.  
  _Example:_  
  ```
  asset-relationship-manager.test.ts
  ```

- **Test Framework:**  
  The specific test framework is not detected, but standard TypeScript test patterns are followed.

- **Test Placement:**  
  Tests are typically placed alongside or within a `__tests__` directory.

- **Example Test Skeleton:**  
  ```typescript
  import { calculateRisk } from './risk-utils';

  describe('calculateRisk', () => {
    it('returns correct risk for basic asset', () => {
      // test implementation
    });
  });
  ```

## Commands

| Command                | Purpose                                                      |
|------------------------|--------------------------------------------------------------|
| /eslint-config-update  | Update or refactor ESLint configuration in the frontend      |
| /format-code           | Apply code formatting across the codebase using formatters   |
```
