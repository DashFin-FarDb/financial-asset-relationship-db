# PR #470 - Quick Reference Guide

## Critical Issues (Must Fix Before Merge) 🔴

### 1. **Duplicate Code in mcp_server.py**
- **Lines:** 123-206 (delete these lines)
- **Problem:** Entire codebase duplicated causing NameError and decorator issues
- **Fix:** Remove lines 123-206

### 2. **FastMCP Not Imported**
- **Line:** 124
- **Problem:** `NameError: name 'FastMCP' is not defined`
- **Fix:** Will be resolved by removing duplicate code

### 3. **CI/CD Failures**
- pre-commit.ci: Failed
- CircleCI python-lint: Failed
- DeepSource Python: Failed (5 issues)
- CircleCI frontend-build: Failed
- Vercel Deployment: Failed
- Semantic PR: Failed (title format)

### 4. **Qlty Blocking Issues**
- **Count:** 2 blocking
- **Issue:** Undefined name `FastMCP` (2 occurrences)
- **Fix:** Will be resolved by removing duplicate code

## High Priority Fixes 🟡

### 5. **Missing Dependencies**
- Add to `requirements.txt`:
  ```
  mcp>=1.0.0
  fastmcp>=0.1.0
  ```

### 6. **PR Title Format**
- **Current:** "Implement model context protocol (mcp) integration"
- **Change to:** "feat: implement model context protocol (mcp) integration"

## Quick Fix Checklist

```bash
# 1. Remove duplicate code
# Edit mcp_server.py and delete lines 123-206

# 2. Add dependencies
grep -qxF 'mcp>=1.0.0' requirements.txt || echo 'mcp>=1.0.0' >> requirements.txt
grep -qxF 'fastmcp>=0.1.0' requirements.txt || echo 'fastmcp>=0.1.0' >> requirements.txt

# 3. Run linters
pre-commit run --all-files
ruff check .
flake8 .

# 4. Update PR title via GitHub UI
# "feat: implement model context protocol (mcp) integration"

# 5. Commit and push
git add mcp_server.py requirements.txt
git commit -m "fix: remove duplicate code and add MCP dependencies"
git push
```

## Files Affected

- `mcp_server.py` - Remove lines 123-206
- `requirements.txt` - Add mcp and fastmcp
- `.github/workflows/mcp-check.yml` - Already correct

## Expected Outcome

After fixes:
- ✅ No NameError
- ✅ Qlty blocking issues resolved
- ✅ Linting passes
- ✅ Semantic PR check passes
- ✅ DeepSource issues reduced

## Full Details

See `PR470_OUTSTANDING_ISSUES.md` for complete analysis with:
- All 13 issues categorized
- Review comment summaries
- Detailed resolution steps
- Compliance failures
- Test status
- Workflow status

## Estimated Time

- **Critical fixes:** 30 minutes
- **High priority:** 1 hour
- **Testing & validation:** 30 minutes
- **Total:** ~2 hours to unblock

---

**Status:** Ready for immediate action
**Next Step:** Remove duplicate code in mcp_server.py (lines 123-206)
