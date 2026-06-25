```markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill provides a comprehensive guide to the development patterns and workflows used in the `financial-asset-relationship-db` TypeScript codebase. It covers file and code conventions, documentation update workflows, and testing patterns to ensure consistency and maintainability across the project.

## Coding Conventions

### File Naming
- Use **kebab-case** for all file names.
  - Example:  
    ```
    financial-asset-model.ts
    asset-relationship-service.ts
    ```

### Import Style
- Use **relative imports** for modules within the repository.
  - Example:
    ```typescript
    import { AssetRelationship } from './models/asset-relationship';
    ```

### Export Style
- Use **named exports** for all modules.
  - Example:
    ```typescript
    // In models/asset-relationship.ts
    export interface AssetRelationship {
      assetId: string;
      relatedAssetId: string;
      relationshipType: string;
    }
    ```

### Commit Messages
- Mixed types, with some use of the `docs` prefix for documentation changes.
- Aim for concise descriptions (~45 characters).

## Workflows

### Update Release Candidate Evidence Template and Related Docs
**Trigger:** When someone needs to update release process documentation or evidence requirements.  
**Command:** `/update-release-docs`

1. Edit `.github/ISSUE_TEMPLATE/release_candidate_evidence.md` to reflect new requirements or clarifications.
2. Update related documentation files in `docs/` (such as staging deployment baselines or release checklists) to stay consistent with the template changes.
   - Files involved:
     - `docs/staging-deployment-operating-baseline.md`
     - `docs/release-checklist.md`
     - `docs/release-evidence-pack.md`
     - `docs/enterprise-deployment-operating-model.md`
3. Review changes for consistency and clarity.
4. Commit with a message prefixed by `docs:` (e.g., `docs: update release evidence template`).
5. Open a pull request for review.

**Example Command Usage:**
```shell
/update-release-docs
```

## Testing Patterns

- Test files use the `*.test.*` naming convention.
  - Example: `asset-relationship.test.ts`
- The specific testing framework is not detected, but standard TypeScript test patterns apply.
- Place test files alongside the modules they test or in a dedicated `tests/` directory.

**Example Test File:**
```typescript
// asset-relationship.test.ts
import { AssetRelationship } from './asset-relationship';

describe('AssetRelationship', () => {
  it('should create a valid relationship', () => {
    const rel: AssetRelationship = {
      assetId: 'A1',
      relatedAssetId: 'B1',
      relationshipType: 'ownership',
    };
    expect(rel.assetId).toBe('A1');
  });
});
```

## Commands

| Command                | Purpose                                                              |
|------------------------|----------------------------------------------------------------------|
| /update-release-docs   | Update release candidate evidence template and related documentation. |
```
