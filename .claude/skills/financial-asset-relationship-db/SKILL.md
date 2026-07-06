```markdown
# financial-asset-relationship-db Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill covers the development conventions and workflows for the `financial-asset-relationship-db` repository, a TypeScript project for managing and analyzing financial asset relationships. It outlines file organization, code style, testing patterns, and deployment configuration workflows to ensure consistency and efficiency in collaborative development.

## Coding Conventions

### File Naming
- Use **PascalCase** for file names.
  - Example: `AssetManager.ts`, `RelationshipGraph.ts`

### Import Style
- Use **relative imports** for modules within the project.
  - Example:
    ```typescript
    import { Asset } from './Asset';
    ```

### Export Style
- Use **named exports** for all exported functions, classes, or constants.
  - Example:
    ```typescript
    // AssetManager.ts
    export class AssetManager { ... }

    // RelationshipGraph.ts
    export function buildGraph() { ... }
    ```

### Commit Message Patterns
- Mostly freeform, with occasional use of the `fix` prefix.
- Keep commit messages concise (average ~40 characters).
  - Example: `fix: correct asset relationship mapping`

## Workflows

### Update Deployment Configuration
**Trigger:** When deployment-related settings need to be changed, such as updating Dockerfiles or docker-compose files for build, environment, or runtime adjustments.  
**Command:** `/update-deployment-config`

1. Identify the deployment configuration file(s) to update:
    - `Dockerfile.api`
    - `Dockerfile.frontend`
    - `docker-compose.production.yml`
2. Edit the necessary file(s) to reflect the required changes (e.g., environment variables, base images, service definitions).
3. Commit your changes with a clear message referencing the file and nature of the update.
    - Example: `fix: update Dockerfile.api to use Node 18`
4. (Optional) Reference co-authors or cherry-picks in the commit message if collaborating.
5. Push your changes and open a pull request for review.

#### Example: Updating the API Dockerfile
```dockerfile
# Dockerfile.api
FROM node:18-alpine
WORKDIR /app
COPY . .
RUN npm install
CMD ["npm", "start"]
```

## Testing Patterns

- **Test File Naming:** Test files use the `*.test.*` pattern.
  - Example: `AssetManager.test.ts`
- **Testing Framework:** Not explicitly detected; check test files for framework usage (e.g., Jest, Mocha).
- **Test Location:** Typically alongside or near the code they test.

#### Example Test File
```typescript
// AssetManager.test.ts
import { AssetManager } from './AssetManager';

describe('AssetManager', () => {
  it('should add a new asset', () => {
    const manager = new AssetManager();
    manager.addAsset({ id: 1, name: 'Stock A' });
    expect(manager.assets.length).toBe(1);
  });
});
```

## Commands

| Command                   | Purpose                                                        |
|---------------------------|----------------------------------------------------------------|
| /update-deployment-config | Update deployment configuration files (Dockerfile, Compose, etc.) |

```