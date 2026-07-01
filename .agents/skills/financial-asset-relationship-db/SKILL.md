````markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches the core development patterns and workflows for the `financial-asset-relationship-db` repository, a TypeScript codebase for managing financial asset relationships. It covers coding conventions, code style, commit practices, and automated workflows for maintaining code quality and consistency.

## Coding Conventions

### File Naming

- Use **kebab-case** for all file names.
  - Example:
    ```
    asset-relationship-manager.ts
    financial-entity.test.ts
    ```

### Import Style

- Use **relative imports** for modules within the project.
  - Example:
    ```typescript
    import { calculateRisk } from "./risk-calculator";
    import { Asset } from "../models/asset";
    ```

### Export Style

- Use **named exports** for all exported functions, types, and constants.
  - Example:

    ```typescript
    // Good
    export function getAssetById(id: string): Asset { ... }

    // Bad
    export default function getAssetById(id: string): Asset { ... }
    ```

### Commit Message Patterns

- Use prefixes: `style`, `test`, `chore`, `fix`, `feat`
- Keep commit messages concise (~58 characters on average)
  - Example:
    ```
    feat: add relationship validation for new asset types
    fix: correct import path in asset-manager
    ```

## Workflows

### ESLint Configuration Update

**Trigger:** When updating, migrating, or refactoring ESLint configuration for the frontend  
**Command:** `/eslint-config-update`

1. Edit or replace ESLint configuration files (e.g., `.eslintrc.json`, `eslint.config.mjs`).
2. Update `package.json` and `package-lock.json` to reflect ESLint or related dependency changes.
3. Optionally, update `.eslintignore` or remove obsolete test files related to ESLint.
4. Commit changes with a message indicating ESLint config update or migration.

**Files Involved:**

- `frontend/.eslintrc.json`
- `frontend/eslint.config.mjs`
- `frontend/.eslintignore`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/__tests__/config/eslint-upgrade-validation.test.ts`

**Example Commit Message:**
````

chore: migrate ESLint config to new format and update dependencies

````

---

### Code Formatting Standardization
**Trigger:** When enforcing or fixing code style issues across the codebase, especially after major changes or before releases
**Command:** `/format-code`

1. Run code formatters (e.g., Prettier) on relevant files.
2. Commit formatted files with a message referencing the tools used and the related issue or PR.
3. Repeat as needed after significant code changes.

**Files Involved:**
- `frontend/eslint.config.mjs`

**Example Command:**
```bash
npx prettier --write .
````

**Example Commit Message:**

```
style: format codebase with Prettier for consistency
```

## Testing Patterns

- Test files follow the `*.test.*` naming convention.
  - Example: `asset-relationship.test.ts`
- Testing framework is not explicitly specified; check test files for framework clues.
- Place tests alongside implementation or in dedicated `__tests__` directories.

**Example Test File:**

```typescript
// asset-relationship.test.ts
import { getAssetById } from "./asset-relationship-manager";

describe("getAssetById", () => {
  it("returns the correct asset for a valid id", () => {
    // ...test implementation
  });
});
```

## Commands

| Command               | Purpose                                             |
| --------------------- | --------------------------------------------------- |
| /eslint-config-update | Update or migrate ESLint configuration              |
| /format-code          | Apply automated code formatting across the codebase |

```

```
