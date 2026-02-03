# Quick Reference: DeepSource YAML Token Autofix Rules

## Summary

This PR fixes malformed YAML literal tokens and creates autofix rules for DeepSource to prevent future occurrences.

## What Was Fixed

### Test Files
- **`tests/integration/test_github_workflows_helpers.py`**: Fixed 11 malformed YAML tokens in test strings
- **`tests/integration/test_branch_integration.py`**: Fixed 2 malformed tokens in test comments

### Common Fixes Applied

| Before | After | Count |
|--------|-------|-------|
| `runs - on:` | `runs-on:` | 4 |
| `actions / checkout @ v4` | `actions/checkout@v4` | 4 |
| `python - version:` | `python-version:` | 4 |
| `fetch - depth:` | `fetch-depth:` | 2 |
| `actions / setup - python` | `actions/setup-python` | 2 |

## Rules Created

### Rule Configuration
- **Location**: `.github/deepsource-autofix-rules.yml`
- **Total Rules**: 12 autofix rules
- **Coverage**: All patterns mentioned in the issue

### Rule Categories

1. **Hyphenated Keys** (7 rules)
   - runs-on, fetch-depth, python-version
   - continue-on-error, timeout-minutes
   - retention-days, working-directory

2. **Action References** (3 rules)
   - actions/checkout
   - actions/upload-artifact
   - actions/cache

3. **Version Formatting** (2 rules)
   - Spaces around `@` signs
   - Spaces around `/` in uses statements

## Configuration Updates

### `.deepsource.toml`
Added custom transformer section:
```toml
[[transformers]]
name = "custom"

  [transformers.meta]
  config_file = ".github/deepsource-autofix-rules.yml"
```

## Documentation

- **Full Documentation**: `docs/DEEPSOURCE_YAML_RULES.md`
  - Detailed rule descriptions
  - Examples and usage guidelines
  - Maintenance instructions

## Validation

All fixed YAML tokens have been validated to parse correctly:
```python
import yaml
yaml.safe_load(fixed_yaml_content)  # ✓ Success
```

### Test Results
- ✓ runs-on token parses correctly
- ✓ actions/checkout@v4 parses correctly
- ✓ python-version parses correctly
- ✓ fetch-depth parses correctly
- ✓ All GitHub Actions syntax validated

## How to Use These Rules

### For DeepSource
DeepSource will automatically:
1. Load rules from `.github/deepsource-autofix-rules.yml`
2. Scan files matching specified patterns
3. Apply fixes to malformed tokens
4. Report changes for review

### For Manual Application
Use the patterns in the rules file to:
1. Search for malformed tokens: `grep -r "runs - on" .`
2. Replace with correct syntax: `runs-on`
3. Verify YAML parses: `python -c "import yaml; yaml.safe_load(...)"`

## Impact

### Benefits
- ✓ Prevents YAML parsing errors in tests
- ✓ Ensures consistent GitHub Actions syntax
- ✓ Automated detection and fixing via DeepSource
- ✓ Comprehensive documentation for maintainers

### Safety
- Only applies to YAML content and test strings
- Does not modify prose or general documentation
- Rules are scoped to prevent over-application

## Related Files

- `.github/deepsource-autofix-rules.yml` - Rule definitions
- `.deepsource.toml` - DeepSource configuration  
- `docs/DEEPSOURCE_YAML_RULES.md` - Complete documentation
- `tests/integration/test_github_workflows_helpers.py` - Fixed tests
- `tests/integration/test_branch_integration.py` - Fixed tests

## Next Steps

1. DeepSource will use these rules for future scans
2. New code will be automatically checked
3. Any similar issues will be auto-fixed
4. Rules can be extended by editing the YAML file

---

For detailed information, see `docs/DEEPSOURCE_YAML_RULES.md`
