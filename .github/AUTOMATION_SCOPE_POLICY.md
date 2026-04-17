# Automation Scope Policy

## Purpose

This document defines boundaries for automated tools, bots, AI agents, and scanners operating in this repository. Its purpose is to:

1. Prevent scope creep in automated changes
2. Maintain architectural consistency
3. Reduce review churn from over-broad automation
4. Preserve the repository's declared production architecture

## Authority

This policy is authoritative for all automated contributions to the repository, including but not limited to:

- AI coding agents (GitHub Copilot, Claude Code, etc.)
- Dependency bots (Dependabot, Renovate, etc.)
- Security scanners (Snyk, CodeQL, Trivy, etc.)
- Linters and formatters running in CI/CD
- Auto-merge bots and PR automation

## Core Principle

**Automated tools may review scope but may not redefine it.**

Automation should work within the repository's declared architecture and policy boundaries. If an automated tool identifies an issue that would require changing architectural direction or expanding beyond documented scope, it should:

1. Report the finding
2. Request human review
3. Wait for explicit permission before implementing changes that broaden scope

## Production Architecture Boundary

### Declared Production Architecture

**Production:** FastAPI backend + Next.js frontend

**Non-Production:** Gradio UI (`app.py`) for demos and internal testing

See [docs/adr/0001-production-architecture.md](docs/adr/0001-production-architecture.md) for the full architectural decision record.

### Rules for Automated Changes

1. **Production Priority**: Changes that improve the FastAPI + Next.js stack are preferred over Gradio improvements
2. **No Architecture Redefinition**: Automated tools must not promote Gradio to production status or demote FastAPI + Next.js
3. **Scope Respect**: Security, performance, and feature work should target the production architecture unless explicitly directed otherwise
4. **Documentation Alignment**: Automated documentation updates must maintain the production/non-production distinction

## PR Scope Boundaries

Automated tools creating or modifying pull requests must adhere to scope guardrails defined in [docs/PR_SCOPE_GUARDRAILS.md](docs/PR_SCOPE_GUARDRAILS.md).

### Required PR Sections

All automated PRs must include:

1. **Primary Objective**: The single main decision or change
2. **In Scope**: What this PR does
3. **Out of Scope**: What this PR explicitly does not do
4. **Files Expected to Change**: List of files and why they belong together
5. **Validation Commands**: Commands to verify the changes
6. **Merge Criteria**: Specific conditions for merge approval

### Prohibited Scope Expansion

Automated tools must not:

1. Mix unrelated concerns (e.g., dependency updates + feature additions)
2. Expand scope to "fix nearby issues" without explicit instruction
3. Change architectural boundaries to satisfy a failing validator
4. Rewrite tests or workflows to make changes pass if the changes conflict with documented policy

## Dependency Management

### Source of Truth

- **Runtime dependencies**: `requirements.txt` is authoritative
- **Development dependencies**: `requirements-dev.txt` is authoritative
- **Project metadata**: `pyproject.toml` mirrors the intent of the above files

See [docs/DEPENDENCY_POLICY.md](docs/DEPENDENCY_POLICY.md) for detailed dependency rules.

### Automated Dependency Updates

Dependency bots and automated updates must:

1. Create focused PRs addressing one dependency decision at a time
2. Not mix dependency updates with framework upgrades
3. Not change the dependency model itself without explicit approval
4. Include security scan results for any version changes
5. Respect the defined source-of-truth hierarchy

## Security Scanning

### Scope of Automated Fixes

Security scanners may automatically:

1. Report vulnerabilities in production and non-production code
2. Suggest version bumps for vulnerable dependencies
3. Flag insecure code patterns

Security scanners must not automatically:

1. Refactor large code sections to fix vulnerabilities without review
2. Remove features to eliminate security surface without approval
3. Change authentication or authorization models
4. Modify API contracts to fix security issues

### Prioritization

Security issues in the **production architecture** (FastAPI + Next.js) take priority over issues in the **non-production** Gradio UI.

## Testing and CI/CD

### Test Coverage Requirements

Automated test generation and modification must:

1. Prioritize production code paths (FastAPI + Next.js)
2. Maintain existing test coverage for non-production code (Gradio) but not expand it automatically
3. Not delete tests to make CI pass
4. Not modify test assertions to match new behavior without review

### CI/CD Changes

Automated tools must not:

1. Modify CI/CD pipelines to change deployment targets
2. Disable failing checks to make builds pass
3. Change the production deployment path from FastAPI + Next.js
4. Add new deployment targets without explicit approval

## Documentation Updates

### Automated Documentation Rules

Automated documentation updates must:

1. Maintain the production/non-production architecture distinction
2. Not contradict the declared production architecture
3. Prioritize production documentation completeness
4. Update cross-references when files are renamed or moved

### Prohibited Documentation Changes

Automated tools must not:

1. Change architectural decision records (ADRs) without review
2. Remove production architecture declarations
3. Promote non-production paths to equal status with production
4. Create new architectural documentation that conflicts with existing ADRs

## Code Quality and Linting

### Automated Formatting

Auto-formatters (Black, Prettier, etc.) may run automatically on:

- Code files (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`)
- Configuration files (`.json`, `.yaml`, `.toml`)
- Documentation (`.md`) for whitespace and basic formatting

### Linting and Style Enforcement

Automated linters must:

1. Enforce existing style rules consistently
2. Not introduce new rules that require large-scale refactoring without approval
3. Report style violations but allow human review before auto-fixing
4. Respect project-specific style overrides in `.flake8`, `.pylintrc`, etc.

## Review and Override

### Human Override Authority

Any human contributor with write access may override this policy for specific PRs by:

1. Explicitly stating the override in the PR description
2. Providing rationale for the exception
3. Obtaining approval from repository maintainers

### Policy Updates

This policy may be updated by:

1. Creating a PR that modifies this file
2. Including rationale for the change
3. Obtaining approval from repository maintainers

Changes to this policy do not require an ADR unless they alter fundamental architectural boundaries.

## Escalation Path

If an automated tool identifies an issue that:

1. Requires changing the production architecture
2. Conflicts with this policy
3. Needs architectural decision-making

The tool should:

1. Create an issue (not a PR) documenting the finding
2. Tag repository maintainers
3. Wait for explicit direction before proceeding

## Enforcement

Repository maintainers will:

1. Review automated PRs for scope compliance
2. Close or request changes for PRs that violate this policy
3. Update bot configurations to enforce these boundaries
4. Document repeated violations and adjust automation settings accordingly

## Related Documents

- [docs/adr/0001-production-architecture.md](docs/adr/0001-production-architecture.md): Production architecture decision
- [docs/PR_SCOPE_GUARDRAILS.md](docs/PR_SCOPE_GUARDRAILS.md): PR scope guidelines
- [docs/DEPENDENCY_POLICY.md](docs/DEPENDENCY_POLICY.md): Dependency management rules
- [CONTRIBUTING.md](../CONTRIBUTING.md): General contribution guidelines
- [README.md](../README.md): Project overview and architecture summary

## Version

- **Version**: 1.0
- **Effective Date**: 2026-04-17
- **Last Updated**: 2026-04-17
- **Next Review**: 2026-07-17 (3 months)
