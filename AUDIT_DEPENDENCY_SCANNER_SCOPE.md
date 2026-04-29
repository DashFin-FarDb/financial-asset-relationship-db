# Dependency and Scanner Scope Audit

**Date**: 2026-04-29
**Branch**: claude/dependency-scanner-scope-audit
**Issue**: #1028 Phase 5
**Auditor**: Claude Code (automated)

---

## Executive Summary

This audit examines dependency source-of-truth and scanner scope controls to ensure:

1. Dependency sources are explicit and enforceable
2. Scanner configurations do not introduce noise or widen PR scope
3. Policy documentation is clear and consistently applied

**Result**: Dependency source-of-truth is **CLEAR and WELL-DOCUMENTED**. Scanner configurations have **MINOR SCOPE ISSUES** that should be narrowed to prevent noise.

---

## Audit Findings

### 1. Dependency Source of Truth

**Area**: Python dependency management
**Current state**:
- `requirements.txt` - 41 lines, runtime/deployment dependencies with security pins
- `requirements-dev.txt` - 27 lines, dev/test/lint tooling
- `pyproject.toml` - Mirrors runtime deps in `dependencies` array, includes `[project.optional-dependencies]` for dev tools
- **No** `uv.lock` file present (uv package manager not in use)

**Issue**: None identified
**Decision**: **KEEP** - Current structure is correct per DEPENDENCY_POLICY.md

**Evidence**:
- DEPENDENCY_POLICY.md (lines 7-9): "`requirements.txt` is the source of truth for runtime and deployment dependencies"
- AUTOMATION_SCOPE_POLICY.md (lines 99-105): Clearly states runtime/dev dependency hierarchy
- All CI workflows correctly install from requirements.txt + requirements-dev.txt
- pyproject.toml dependencies align with requirements.txt (spot-checked: gradio, fastapi, pydantic versions match)

**Validation**:
```bash
# Dependencies are consistent
grep "fastapi" requirements.txt pyproject.toml
# requirements.txt:15:fastapi==0.127.0
# pyproject.toml:37:    "fastapi==0.127.0",

grep "pydantic" requirements.txt pyproject.toml
# requirements.txt:17:pydantic==2.12.5
# pyproject.toml:39:    "pydantic==2.12.5",
```

---

### 2. Codacy Scanner Configuration

**Area**: .codacy/codacy.yaml scanner scope
**Current state**:
```yaml
runtimes:
    - node@22.2.0
    - python@3.11.11
tools:
    - eslint@8.57.0
    - lizard@1.17.31
    - pylint@3.3.6
    - semgrep@1.78.0
    - trivy@0.66.0
```

**Issue**: Node.js runtime and ESLint are configured but NOT used in Python backend
**Decision**: **NARROW** - Remove node runtime; keep eslint only if needed for frontend scanning

**Rationale**:
- Production architecture is FastAPI (Python) backend + Next.js (JavaScript) frontend
- Node.js analysis is relevant for `frontend/` directory ONLY
- Codacy should NOT analyze root-level `package.json` (which is Gradio-only, non-production)
- Backend scanning should focus on Python tools: pylint, semgrep, trivy
- Frontend scanning (if needed) should be scoped to `frontend/` directory

**Scanner noise risk**: Medium
- ESLint may scan irrelevant root-level JS/JSON files
- Node.js runtime may trigger false positives on non-production code

**Proposed change**:
```yaml
runtimes:
    - python@3.11.11
tools:
    - eslint@8.57.0  # if needed for frontend/ only
    - lizard@1.17.31
    - pylint@3.3.6
    - semgrep@1.78.0
    - trivy@0.66.0
```

Or, if frontend scanning is handled separately:
```yaml
runtimes:
    - python@3.11.11
tools:
    - lizard@1.17.31
    - pylint@3.3.6
    - semgrep@1.78.0
    - trivy@0.66.0
```

**Defer decision**: Whether to keep eslint depends on whether Codacy is intended to scan frontend/. This audit recommends **removing node runtime** and **clarifying eslint scope** or removing it.

---

### 3. DeepSource Configuration

**Area**: .deepsource.toml analyzer scope
**Current state**:
```toml
[[analyzers]]
name = "sql"

[[analyzers]]
name = "test-coverage"

[[analyzers]]
name = "javascript"
  [analyzers.meta]
  plugins = ["react"]
  environment = ["nodejs"]

[[analyzers]]
name = "python"
  [analyzers.meta]
  runtime_version = "3.x.x"
```

**Issue**: SQL analyzer may not be relevant; JavaScript analyzer scope unclear
**Decision**: **DEFER** - Requires understanding of actual DeepSource usage

**Questions**:
1. Is SQL analysis targeting SQLAlchemy models or raw SQL? (May be legitimate)
2. Is JavaScript analyzer scoped to `frontend/` or analyzing root-level files?
3. Does test-coverage analyzer provide value or just noise?

**Scanner noise risk**: Low-Medium
- SQL analyzer may flag ORM patterns as issues
- JavaScript analyzer may scan non-production Gradio code
- Current formatters include both Python (black, autopep8, isort, ruff) and JS (standardjs, prettier) which suggests broad scanning intent

**Recommendation**: Monitor DeepSource output in PRs. If it consistently flags non-production code or creates noise, narrow analyzer scope to production paths only.

---

### 4. Snyk Configuration

**Area**: .github/workflows/snyk-security.yml
**Current state**:
```yaml
- name: Snyk Open Source monitor
  run: snyk monitor --all-projects
```

**Issue**: `--all-projects` flag may scan ALL ecosystems including unused ones
**Decision**: **CLARIFY** - Determine if Snyk should scan Python, Docker, or both

**Scanner noise risk**: Medium-High
- `--all-projects` will auto-detect and scan any ecosystem it finds
- May scan package.json (non-production Gradio) alongside requirements.txt (production)
- May generate dependency alerts for Gradio packages that aren't deployment-critical

**Current Snyk scope** (from workflow):
1. Snyk Code (SAST) - scans all code
2. Snyk Open Source - scans `--all-projects` (Python + Node + Docker)
3. Snyk IaC - scans infrastructure config
4. Snyk Container - scans Docker image

**Recommendation**:
- Explicitly scope Snyk to production dependencies: `snyk monitor --file=requirements.txt`
- OR document that `--all-projects` is intentional and includes non-production scanning
- Add comment explaining scope: "Scans all dependency ecosystems including non-production Gradio for comprehensive security coverage"

**Alternative** (narrower scope):
```yaml
- name: Snyk Open Source monitor
  run: |
    snyk monitor --file=requirements.txt --project-name=backend-production
    snyk monitor --file=frontend/package.json --project-name=frontend-production
```

---

### 5. CodeQL Configuration

**Area**: .github/workflows/codeql.yml
**Current state**:
```yaml
matrix:
  include:
  - language: actions
    build-mode: none
  - language: python
    build-mode: none
```

**Issue**: None identified
**Decision**: **KEEP** - Appropriate scope for this repository

**Rationale**:
- Analyzes Python (production backend)
- Analyzes GitHub Actions workflows (CI/CD security)
- Does NOT analyze JavaScript (frontend is not included, which is appropriate given Next.js is client-side)
- Uses custom config at `.github/codeql/codeql-config.yml` to exclude test file false positives

**Scanner noise risk**: Low
- Well-scoped to production code
- Custom config reduces noise

---

### 6. Trivy Configuration

**Area**: .github/workflows/trivy.yml
**Current state**:
- Scans Docker image only
- Triggered by Dockerfile changes
- Uploads SARIF results to GitHub Security

**Issue**: Limited scope - only runs on Docker changes
**Decision**: **KEEP** - Appropriate for current usage

**Rationale**:
- Trivy is Docker vulnerability scanner
- Dockerfile builds Gradio app (non-production)
- Workflow correctly scopes to Docker-related file changes
- SECURITY NOTE: Production deployment does NOT use Docker currently (per ADR 0001), so Trivy findings are informational only

**Scanner noise risk**: Low
- Well-scoped to Docker changes
- Does not run on every PR

---

### 7. CI/CD Dependency Installation Paths

**Area**: GitHub Actions CI, CircleCI
**Current state**:

**GitHub Actions** (.github/workflows/ci.yml):
```yaml
install: |
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
```

**CircleCI** (.circleci/config.yml):
```yaml
install-python-deps:
  command: |
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
    if [ -f requirements-dev.txt ]; then
      pip install -r requirements-dev.txt
    fi
```

**Issue**: None identified
**Decision**: **KEEP** - Correctly follows declared source-of-truth

**Evidence**:
- Both CI systems use requirements.txt as primary source
- Both install requirements-dev.txt for testing/linting
- No CI system tries to install from pyproject.toml directly
- Frontend CI correctly uses `npm install` for Next.js (frontend/package.json)

---

### 8. Documentation and Policy Alignment

**Area**: DEPENDENCY_POLICY.md, AUTOMATION_SCOPE_POLICY.md, PR templates

**Current state**:
- DEPENDENCY_POLICY.md (159 lines): **EXCELLENT** - comprehensive, clear source-of-truth rules
- AUTOMATION_SCOPE_POLICY.md (254 lines): **EXCELLENT** - clear automation boundaries
- PR template: Includes scope guardrails and references policy docs

**Issue**: Scanner scope control not explicitly mentioned in AUTOMATION_SCOPE_POLICY.md
**Decision**: **CLARIFY** - Add scanner scope guardrail section

**Gap identified**:
- Policy covers dependency bots, security scanners (what they can fix), and CI/CD
- Policy does NOT explicitly state: "Scanners must not analyze unused ecosystems or non-production code paths"
- Policy does NOT state: "Scanner findings do not justify widening PR scope"

**Proposed addition** to AUTOMATION_SCOPE_POLICY.md:

```markdown
### Scanner Scope Control

Security and quality scanners must:

1. Focus analysis on production architecture (FastAPI + Next.js) first
2. Not expand PR scope to fix findings in non-production code without approval
3. Not analyze unused language ecosystems or package managers
4. Clearly distinguish production findings from non-production findings in reports

Scanners must not:

1. Auto-enable analysis for new ecosystems without review
2. Widen PR scope from "fix vulnerability X" to "fix all scanner findings"
3. Fail CI solely based on non-production code findings
4. Use broad auto-detection flags (e.g., --all-projects) without documenting scope
```

---

## Summary of Decisions

| Area | Current State | Issue | Decision | Priority |
|------|---------------|-------|----------|----------|
| requirements.txt | Authoritative source | None | **KEEP** | N/A |
| pyproject.toml | Mirrors runtime deps | None | **KEEP** | N/A |
| requirements-dev.txt | Dev/test tooling | None | **KEEP** | N/A |
| .codacy/codacy.yaml | Node.js + Python | Node.js not used in backend | **NARROW** | Medium |
| .deepsource.toml | SQL + JS + Python | Scope unclear | **DEFER** | Low |
| Snyk workflow | --all-projects flag | May scan non-production | **CLARIFY** | Medium |
| CodeQL workflow | Python + Actions | None | **KEEP** | N/A |
| Trivy workflow | Docker only | Limited scope (OK) | **KEEP** | N/A |
| CI dependency install | requirements.txt first | None | **KEEP** | N/A |
| AUTOMATION_SCOPE_POLICY.md | Comprehensive | Scanner scope not explicit | **CLARIFY** | High |

---

## Recommended Minimal Changes

### Change 1: Narrow .codacy/codacy.yaml

**File**: `.codacy/codacy.yaml`
**Action**: Remove `node@22.2.0` runtime (not used in Python backend)
**Justification**: Prevents ESLint from scanning non-production root-level files

**Before**:
```yaml
runtimes:
    - node@22.2.0
    - python@3.11.11
```

**After**:
```yaml
runtimes:
    - python@3.11.11
```

**Impact**: Low risk
- Codacy will focus on Python analysis only
- If frontend scanning is needed, it should be configured separately with explicit path scope
- Reduces noise from analyzing package.json (non-production Gradio)

---

### Change 2: Add Scanner Scope Guardrail to AUTOMATION_SCOPE_POLICY.md

**File**: `.github/AUTOMATION_SCOPE_POLICY.md`
**Action**: Add "Scanner Scope Control" subsection under "Security Scanning" section
**Justification**: Explicit policy prevents scanner noise from driving PR scope creep

**Location**: After line 137 (after "Prioritization" section)

**Addition**:
```markdown
### Scanner Scope Control

Automated security and quality scanners must:

1. Focus primary analysis on production architecture (FastAPI + Next.js)
2. Clearly distinguish production findings from non-production findings
3. Not auto-enable analysis for unused language ecosystems or package managers
4. Not use broad auto-detection flags (e.g., `--all-projects`) without explicit documentation of intended scope

Scanners must not:

1. Expand PR scope from "fix specific vulnerability" to "fix all scanner findings" without approval
2. Fail CI based solely on findings in non-production code paths
3. Drive implementation decisions (e.g., suggesting architecture changes to satisfy scanner rules)
4. Override documented dependency source-of-truth (requirements.txt) based on scanner assumptions

### Scanner Findings and PR Scope

If a scanner identifies issues in non-production code (Gradio UI, demo scripts, test utilities):

1. Report the finding with context (production vs. non-production)
2. Prioritize production issues first
3. Do not automatically create PRs to fix non-production issues
4. Do not widen an existing PR to include non-production fixes

Scanner noise (false positives, low-priority warnings, non-production findings) should not block PRs or drive scope expansion.
```

**Impact**: Low risk
- Codifies existing practice
- Provides clear guidance for automated tools
- Prevents future scope creep from scanner findings

---

### Change 3: Document Snyk Scope (Optional Clarification)

**File**: `.github/workflows/snyk-security.yml`
**Action**: Add comment explaining `--all-projects` scope
**Justification**: Makes intent explicit for future maintainers

**Location**: Line 61 (before `snyk monitor` command)

**Addition**:
```yaml
      # Scans all dependency ecosystems (Python, Node, Docker) including non-production code.
      # Production dependencies: requirements.txt (backend), frontend/package.json (frontend)
      # Non-production dependencies: package.json (root, Gradio demo)
      - name: Snyk Open Source monitor
        run: snyk monitor --all-projects
```

**Impact**: Documentation only, no functional change

---

## Out of Scope (Explicit)

This audit does NOT include:

1. **No dependency version changes** - No upgrades, no pins, no version bumps
2. **No scanner finding remediation** - Not fixing any issues reported by scanners
3. **No CI/CD restructuring** - Not changing workflow logic, just documentation
4. **No adding new scanners** - Not enabling new security tools
5. **No DeepSource changes** - Deferred pending usage analysis
6. **No Snyk command changes** - Only documentation clarification, no flag changes (yet)

---

## Validation Commands

### Validate dependency source-of-truth alignment

```bash
# Verify requirements.txt can be installed
pip install -r requirements.txt
pip check

# Verify pyproject.toml doesn't contradict requirements.txt
pip install -e .
pip check

# Verify dev dependencies install
pip install -r requirements.txt -r requirements-dev.txt
pip check
```

### Validate CI still works after changes

```bash
# Simulate CI dependency install (GitHub Actions path)
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run lint (will catch any config issues)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

### Validate frontend build unaffected

```bash
cd frontend
npm install
npm run lint
npm run build
```

---

## Merge Criteria

This PR is ready to merge when:

- [x] Audit document is complete and accurate
- [ ] .codacy/codacy.yaml narrowed to remove node runtime (if approved)
- [ ] AUTOMATION_SCOPE_POLICY.md updated with scanner scope guardrails (if approved)
- [ ] All validation commands pass
- [ ] No unrelated changes introduced
- [ ] Scope strictly limited to config/documentation clarity

---

## Related Issues

- Issue #1028 - Master Production Readiness Checklist (Phase 5)
- DEPENDENCY_POLICY.md - Source-of-truth documentation
- AUTOMATION_SCOPE_POLICY.md - Automation boundaries
- ADR 0001 - Production architecture declaration

---

## Conclusion

The repository has a **clear and well-documented dependency model** with requirements.txt as the authoritative source. Documentation (DEPENDENCY_POLICY.md, AUTOMATION_SCOPE_POLICY.md) is comprehensive and accurate.

**Recommended actions**:
1. Narrow .codacy/codacy.yaml to remove node runtime (prevents noise)
2. Add scanner scope guardrail to AUTOMATION_SCOPE_POLICY.md (prevents future scope creep)
3. Optionally document Snyk `--all-projects` intent (improves clarity)

All changes are **minimal, justified, and documentation-focused**. No dependency changes, no scanner remediation, no scope drift.
