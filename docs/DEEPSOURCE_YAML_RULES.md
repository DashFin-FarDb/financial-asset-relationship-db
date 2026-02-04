# DeepSource YAML Literal Token Autofix Rules

## Overview

This document describes the autofix rules created to fix malformed YAML literal tokens in GitHub Actions workflows and test files. These rules ensure that YAML syntax is correct and prevents parsing errors.

## Problem Statement

During testing and development, YAML tokens in GitHub Actions workflows were sometimes written with incorrect spacing, such as:

- `runs - on` instead of `runs-on`
- `actions / checkout @ v4` instead of `actions/checkout@v4`
- `python - version` instead of `python-version`

These malformed tokens cause YAML parsing errors and test assertion failures.

## Rules Created

The following autofix rules have been implemented in `.github/deepsource-autofix-rules.yml`:

### 1. Hyphenated Property Keys

These rules fix GitHub Actions workflow properties that should be hyphenated without spaces:

| Rule ID                            | Pattern                  | Replacement          | Description                  |
| ---------------------------------- | ------------------------ | -------------------- | ---------------------------- |
| `fix-yaml-runs-on-token`           | `runs - on:`             | `runs-on:`           | Job runner specification     |
| `fix-yaml-fetch-depth-token`       | `fetch - depth:`         | `fetch-depth:`       | Git checkout depth           |
| `fix-yaml-python-version-token`    | `python - version:`      | `python-version:`    | Python version specification |
| `fix-yaml-continue-on-error-token` | `continue - on - error:` | `continue-on-error:` | Error handling flag          |
| `fix-yaml-timeout-minutes-token`   | `timeout - minutes:`     | `timeout-minutes:`   | Job timeout setting          |
| `fix-yaml-retention-days-token`    | `retention - days:`      | `retention-days:`    | Artifact retention period    |
| `fix-yaml-working-directory-token` | `working - directory:`   | `working-directory:` | Working directory path       |

### 2. Action References

These rules fix GitHub Actions action references that should have no spaces:

| Rule ID                                  | Pattern                     | Replacement               | Description               |
| ---------------------------------------- | --------------------------- | ------------------------- | ------------------------- |
| `fix-yaml-actions-checkout-token`        | `actions / checkout`        | `actions/checkout`        | Checkout action reference |
| `fix-yaml-actions-upload-artifact-token` | `actions / upload-artifact` | `actions/upload-artifact` | Upload artifact action    |
| `fix-yaml-actions-cache-token`           | `actions / cache`           | `actions/cache`           | Cache action reference    |

### 3. Version References

These rules fix action version specifications:

| Rule ID                           | Description                                                       |
| --------------------------------- | ----------------------------------------------------------------- |
| `fix-yaml-action-version-at-sign` | Removes spaces around `@` in version specs (e.g., `@ v4` → `@v4`) |
| `fix-yaml-action-slash-spacing`   | Removes spaces around `/` in `uses:` statements                   |

## Scope and Application

### Files Affected

- `*.yml` - GitHub Actions workflow files
- `*.yaml` - YAML configuration files
- `*.py` - Python test files containing YAML strings
- `*.md` - Documentation with YAML examples (limited to action references)

### Scope Limitation

Rules are designed to apply only to:

- Actual YAML content in workflow files
- YAML strings embedded in test code
- Code blocks in documentation

Rules **should NOT** apply to:

- Regular prose or narrative text
- General comments or docstrings (unless containing test YAML)
- User-facing documentation text

## Implementation

### Configuration Files

1. **`.github/deepsource-autofix-rules.yml`**
   - Contains all rule definitions
   - Specifies patterns and replacements
   - Documents scope and purpose

2. **`.deepsource.toml`**
   - Updated to reference the custom rules file
   - Integrates rules with DeepSource analysis

### Usage with DeepSource

When DeepSource analyzes the repository:

1. It loads the custom rules from `.github/deepsource-autofix-rules.yml`
2. Scans files matching the specified patterns
3. Applies transformations to fix malformed tokens
4. Reports changes for review

## Examples

### Before and After

#### Example 1: Workflow Job Configuration

```yaml
# Before
jobs:
  test:
    runs - on: ubuntu - latest
    steps:
      - uses: actions / checkout @ v4

# After
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
```

#### Example 2: Python Version Matrix

```yaml
# Before
strategy:
  matrix:
    python - version: ['3.9', '3.10', '3.11']

# After
strategy:
  matrix:
    python-version: ['3.9', '3.10', '3.11']
```

#### Example 3: Checkout with Fetch Depth

```yaml
# Before
- uses: actions / checkout @ v4
  with:
    fetch - depth: 0

# After
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
```

## Testing

The rules have been validated by:

1. **Manual Testing**: Applied fixes to test files in `tests/integration/`
   - `test_github_workflows_helpers.py`
   - `test_branch_integration.py`

2. **YAML Validation**: Verified that fixed YAML parses correctly:

   ```python
   import yaml
   yaml.safe_load(fixed_yaml_content)  # Success
   ```

3. **Pattern Coverage**: Ensured all patterns from the issue are addressed

## Maintenance

To update or extend these rules:

1. Edit `.github/deepsource-autofix-rules.yml`
2. Add new rule entries following the existing pattern:
   ```yaml
   - id: fix-yaml-new-token
     name: Human-readable name
     description: Detailed description
     pattern: "regex pattern"
     replacement: "replacement text"
     file_types:
       - "*.yml"
   ```
3. Test the new rule with sample files
4. Update this documentation

## Related Files

- `.github/deepsource-autofix-rules.yml` - Rule definitions
- `.deepsource.toml` - DeepSource configuration
- `tests/integration/test_github_workflows_helpers.py` - Fixed test file
- `tests/integration/test_branch_integration.py` - Fixed test file

## References

- [DeepSource Documentation](https://deepsource.io/docs/)
- [GitHub Actions Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- Original Issue: "Ruleset for fixing literal tokens in YAML and non YAML files"
