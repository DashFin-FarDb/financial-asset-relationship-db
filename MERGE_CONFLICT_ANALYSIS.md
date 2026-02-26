# Merge Conflict Analysis for PR #6

## Summary

PR #6 (`coderabbitai/utg/e47c649` → `main`) cannot be merged due to conflicts in 5 test-related files. These are "add/add" conflicts where both branches independently created the same files with different implementations.

## Conflicted Files

### 1. `tests/unit/test_api_main.py`

- **HEAD version (PR #6)**: 693 lines - Well-organized test classes by endpoint type
- **main version**: 608 lines - Organized by function and integration scenarios
- **Recommendation**: Use **main version** - Already validated and integrated

### 2. `frontend/app/lib/__tests__/api.test.ts`

- **HEAD version (PR #6)**: 551 lines - Comprehensive with extensive edge cases
- **main version**: 257 lines - Basic coverage of all endpoints
- **Recommendation**: Use **HEAD version** - More thorough test coverage

### 3. `frontend/jest.config.js`

- **Conflicts**: Module name mapper patterns and coverage settings
- **Resolution**: Merge both - Keep specific patterns from HEAD + generic pattern from main, merge exclusions, keep coverage thresholds from HEAD

### 4. `frontend/jest.setup.js`

- **Conflicts**: HEAD has more mocks (react-plotly.js, env vars, console suppression)
- **Resolution**: Keep all from HEAD - More comprehensive test environment setup

### 5. `frontend/package.json`

- **Conflicts**: Minor version differences in testing libraries
- **Resolution**: Use newer versions from main + keep @types/jest from HEAD

## Resolution Strategy

Since PR #35 is a sub-PR that depends on PR #6, the conflicts in PR #6 must be resolved first. Here's the recommended approach:

### Option 1: Merge main into PR #6's branch (Recommended)

```bash
git checkout coderabbitai/utg/e47c649
git merge main

# Resolve each file as documented above
git add <resolved-files>
git commit -m "Merge main and resolve test file conflicts"
git push origin coderabbitai/utg/e47c649
```

### Option 2: Rebase PR #6 onto main

```bash
git checkout coderabbitai/utg/e47c649
git rebase main

# Resolve conflicts during rebase
git push --force-with-lease origin coderabbitai/utg/e47c649
```

## Detailed Conflict Resolutions

### jest.config.js

```javascript
moduleNameMapper: {
    // Handle module aliases - specific patterns first (from HEAD)
    '^@/components/(.*)$': '<rootDir>/app/components/$1',
    '^@/lib/(.*)$': '<rootDir>/app/lib/$1',
    '^@/types/(.*)$': '<rootDir>/app/types/$1',
    '^@/app/(.*)$': '<rootDir>/app/$1',
    // Generic pattern last (from main)
    '^@/(.*)$': '<rootDir>/$1',
  },
  collectCoverageFrom: [
    'app/**/*.{js,jsx,ts,tsx}',
    '!app/**/*.d.ts',
    '!app/**/*.stories.{js,jsx,ts,tsx}',  // from HEAD
    '!app/**/index.{js,jsx,ts,tsx}',      // from HEAD
    '!app/**/_*.{js,jsx,ts,tsx}',         // from main
    '!**/node_modules/**',                // from main
  ],
  coverageThreshold: {  // from HEAD
    global: {
      branches: 70,
      functions: 70,
      lines: 70,
      statements: 70,
    },
  },
```

### jest.setup.js

Keep entire HEAD version including:

- React and plotly mocks
- Environment variable setup
- Console error suppression
- All window/IntersectionObserver mocks

### package.json

```json
"devDependencies": {
  "@testing-library/react": "^14.1.2",      // main (newer)
  "@testing-library/jest-dom": "^6.1.5",    // main (newer)
  "@testing-library/user-event": "^14.5.1", // main (newer)
  "jest": "^29.7.0",                        // both
  "jest-environment-jsdom": "^29.7.0",      // both
  "@types/jest": "^29.5.0"                  // HEAD (needed for TS)
}
```

## Additional Recommendations

### Coverage Files

The main branch includes coverage report files (`frontend/coverage/**`) which should not be committed. Add to `.gitignore`:

```gitignore
# Test coverage
coverage/
```

### After Resolution

1. Run tests to ensure both test suites work: `npm test` (frontend) and `pytest` (backend)
2. Verify no regressions were introduced
3. Update PR #35 if needed once PR #6 is mergeable

## Impact on PR #35

PR #35 will automatically become mergeable once PR #6's conflicts with main are resolved, as it only adds one commit on top of PR #6.
