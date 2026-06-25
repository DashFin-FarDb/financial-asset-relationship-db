```markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions for the `financial-asset-relationship-db` repository. The codebase is written in TypeScript and is designed to model and manage relationships between financial assets. While no specific framework is enforced, the repository follows clear conventions for file naming, code organization, commit messages, and testing. This guide will help you contribute code that fits seamlessly with the existing style and workflows.

## Coding Conventions

### File Naming
- Use **kebab-case** for all file names.
  - Example:  
    ```
    asset-manager.ts
    relationship-utils.ts
    ```

### Import Style
- Use **relative imports** for modules within the repository.
  - Example:
    ```typescript
    import { getAssetById } from './asset-manager';
    ```

### Export Style
- Use **named exports** instead of default exports.
  - Example:
    ```typescript
    // In asset-manager.ts
    export function getAssetById(id: string) { ... }
    export function listAssets() { ... }
    ```

### Commit Messages
- Follow the **Conventional Commits** format.
- Use prefixes such as `docs:` for documentation changes.
- Keep commit messages concise (average: 36 characters).
  - Example:
    ```
    docs: update README with usage examples
    ```

## Workflows

### Documenting Code Changes
**Trigger:** When updating or adding documentation  
**Command:** `/docs-update`

1. Make your documentation changes in the relevant files.
2. Commit your changes using the `docs:` prefix.
   - Example:  
     ```
     docs: add API usage section
     ```
3. Push your branch and open a pull request.

### Adding or Updating Code
**Trigger:** When implementing new features or fixing bugs  
**Command:** `/code-update`

1. Write your code in TypeScript, following file naming and import/export conventions.
2. Add or update relevant tests (see Testing Patterns).
3. Commit changes with a descriptive, conventional commit message.
4. Push your branch and open a pull request.

## Testing Patterns

- Test files use the pattern `*.test.*` (e.g., `asset-manager.test.ts`).
- The specific testing framework is not detected; check existing test files for style.
- Place tests alongside or near the files they cover.
- Example test file name:
  ```
  relationship-utils.test.ts
  ```
- Example test structure (framework-agnostic):
  ```typescript
  // relationship-utils.test.ts
  import { calculateRelationship } from './relationship-utils';

  describe('calculateRelationship', () => {
    it('returns correct relationship for valid input', () => {
      // test implementation
    });
  });
  ```

## Commands
| Command       | Purpose                                   |
|---------------|-------------------------------------------|
| /docs-update  | Document or update documentation changes  |
| /code-update  | Add or update code and related tests      |
```
