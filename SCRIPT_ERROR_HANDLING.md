# Script Error Handling Documentation

## Overview
Both PR cleanup scripts now include comprehensive error handling to address code review feedback.

## Error Checks Implemented

### close_unmergeable_prs.sh

#### Prerequisites Validation
- ✅ **GitHub CLI (`gh`) installation check**
  - Verifies `gh` command is available
  - Exits with clear error message if missing

- ✅ **GitHub authentication check**
  - Validates user is logged in via `gh auth status`
  - Prevents API call failures

- ✅ **jq installation check**
  - Ensures JSON parsing tool is available
  - Required for processing PR data

#### Operation Error Handling
- ✅ **API call failures**
  - Catches errors from `gh pr list`
  - Handles JSON parsing errors from `jq`
  - Exits with descriptive error messages

- ✅ **Empty results handling**
  - Checks if conflicting_prs.txt is empty or missing
  - Provides clear "No conflicting PRs found" message
  - Prevents confusion from silent failures

- ✅ **Per-PR error handling**
  - Individual PR view failures don't stop the script
  - Errors logged to stderr for problematic PRs
  - Script continues processing remaining PRs

- ✅ **Cleanup**
  - Removes temporary file `/tmp/conflicting_prs.txt`
  - Prevents stale data from affecting subsequent runs

### close_unmergeable_prs_script.sh

#### Prerequisites Validation
- ✅ **GitHub CLI (`gh`) installation check**
- ✅ **GitHub authentication check**

#### Input Validation
- ✅ **Missing PR number check**
  - Validates PR argument is provided
  - Shows usage message if missing

- ✅ **PR number format validation**
  - Ensures PR number is numeric (positive integer)
  - Prevents invalid API calls

#### Operation Error Handling
- ✅ **PR close operation failure**
  - Catches `gh pr close` command failures
  - Handles invalid PR numbers
  - Handles permission errors
  - Provides clear error messages

- ✅ **Success confirmation**
  - Displays "Successfully closed PR #XXX" on success
  - Clear feedback for successful operations

## Error Message Standards

### stderr Usage
All error messages are directed to stderr (`>&2`) following best practices:
```bash
echo "Error: message" >&2
```

### Exit Codes
- `0` - Success or no PRs found
- `1` - Error (missing tool, auth failure, operation failure)

### Error Message Format
```
Error: [Clear description of what went wrong]
```

## Testing

Run the included test script to verify error handling:
```bash
bash test_scripts.sh
```

Expected output:
```
✅ gh CLI detected successfully
✅ Correctly requires PR number
✅ Correctly validates numeric PR number
All error handling tests passed! ✅
```

## Usage Examples

### Safe execution of close_unmergeable_prs.sh
```bash
# Script will:
# 1. Check for gh CLI and jq
# 2. Verify authentication
# 3. Safely handle empty results
# 4. Continue on individual PR errors
# 5. Clean up temporary files

bash close_unmergeable_prs.sh
```

### Safe execution of close_unmergeable_prs_script.sh
```bash
# Valid usage
bash close_unmergeable_prs_script.sh 123

# Invalid usage (caught by validation)
bash close_unmergeable_prs_script.sh abc  # Error: must be numeric
bash close_unmergeable_prs_script.sh      # Error: missing PR number
```

## Code Review Feedback Addressed

| Review Comment | Implementation | Status |
|----------------|----------------|--------|
| Check gh pr list errors | Added error check + exit on failure | ✅ |
| Check jq command errors | Added error check + exit on failure | ✅ |
| Verify file exists/non-empty | Added check before loop | ✅ |
| Check gh CLI installation | Added at script start | ✅ |
| Verify gh authentication | Added at script start | ✅ |
| Handle gh pr close errors | Added error check + feedback | ✅ |
| Validate PR number | Added numeric validation | ✅ |

## Benefits

1. **No silent failures** - All errors reported clearly
2. **Early detection** - Prerequisites checked before operations
3. **Clear feedback** - Users know exactly what went wrong
4. **Graceful degradation** - Per-PR errors don't stop batch processing
5. **Clean execution** - Temporary files cleaned up automatically
6. **Better UX** - Success/failure clearly communicated

---

Generated with [Continue](https://continue.dev)
Co-authored by: mohavro & Continue
