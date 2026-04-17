# ADR 0001: Production Architecture - FastAPI Backend + Next.js Frontend

## Status

Accepted

## Date

2026-04-17

## Context

The Financial Asset Relationship Database project currently supports two runtime modes:

1. **Gradio UI** (`app.py`): The original interface providing direct Python-to-UI integration
2. **FastAPI + Next.js**: A newer architecture with a REST API backend and React frontend

This ambiguity creates several problems:

### Problems with Dual Runtime Identity

1. **Deployment Confusion**: Contributors and deployment tools don't have a clear target architecture
2. **Testing Scope**: Unclear which path should receive primary test coverage and CI/CD investment
3. **Documentation Drift**: Maintaining parallel documentation for two equally-weighted paths is costly
4. **Agent/Scanner Scope Creep**: Automated tools may attempt to maintain both paths equally, widening PR scope unnecessarily
5. **Security Surface**: Two complete UI stacks means double the attack surface and maintenance burden
6. **Performance Investment**: Optimization efforts lack a clear priority target

### Technical Context

- **Gradio** provides rapid prototyping and is excellent for demos and internal tools
- **FastAPI + Next.js** provides:
  - Clear API contracts via OpenAPI/Swagger
  - Scalable deployment on modern platforms (Vercel, AWS, etc.)
  - Professional authentication and authorization patterns
  - Type-safe client-server communication
  - Better separation of concerns
  - Industry-standard frontend tooling (React, TypeScript, Tailwind)

## Decision

**We declare FastAPI backend + Next.js frontend as the production architecture.**

The Gradio UI (`app.py`) is **demoted to non-production status** and will be maintained for:

- Internal demos
- Rapid prototyping
- Developer testing
- Educational purposes

### Implications

1. **Primary Development Target**: All production features, security hardening, and scalability work targets FastAPI + Next.js
2. **Documentation Priority**: Production documentation focuses on FastAPI + Next.js; Gradio gets secondary coverage
3. **CI/CD Focus**: Deployment pipelines, security scans, and production tests target the FastAPI + Next.js stack
4. **Breaking Changes**: The Gradio UI may lag behind or diverge from the production API as needed
5. **Code Organization**: Production code paths are clearly separated from demo/testing paths

## Consequences

### Positive

1. **Clear North Star**: Contributors, agents, and tools have one authoritative deployment target
2. **Reduced Maintenance**: Gradio becomes a convenience tool, not a production obligation
3. **Better Security**: Focused security investment on one production stack
4. **Easier Onboarding**: New contributors learn one primary architecture
5. **Controlled Scope**: Automated tools and PR reviewers can enforce the production boundary
6. **Better Documentation**: Single production path gets comprehensive docs instead of split coverage

### Negative

1. **Gradio Users**: Existing Gradio deployments (if any) must migrate or accept non-production status
2. **Two Codebases**: We still maintain both, but with different priorities
3. **Initial Friction**: Requires updating all documentation, templates, and automation policies

### Neutral

1. **No Code Deletion**: Gradio code remains in the repository for demos and testing
2. **No Runtime Changes**: This ADR is a documentation and policy change, not a code refactor

## Alternatives Considered

### Alternative 1: Keep Both as Equal Production Paths

**Rejected because:**

- Doubles maintenance burden
- Creates deployment ambiguity
- Splits security investment
- Increases documentation overhead
- Enables scope creep in PRs and automated tools

### Alternative 2: Delete Gradio Entirely

**Rejected because:**

- Gradio is still valuable for demos, testing, and rapid iteration
- Complete removal would discard working code with legitimate use cases
- Non-production status achieves the goal without code deletion

### Alternative 3: Make Gradio the Production Path

**Rejected because:**

- Gradio lacks enterprise-grade authentication patterns
- Less suitable for cloud-native deployment
- Doesn't provide API contract clarity (OpenAPI/Swagger)
- Smaller ecosystem for professional frontend tooling

## Implementation Plan

This ADR is implemented via documentation and policy updates only. No runtime code changes are required.

### Immediate Actions (This PR)

1. Update `README.md` to declare FastAPI + Next.js as production
2. Update `ARCHITECTURE.md` to mark production vs non-production paths
3. Update `DEPLOYMENT.md` to focus on production deployment
4. Add `.github/AUTOMATION_SCOPE_POLICY.md` to guide automated tools
5. Update PR templates to require scope declarations

### Deferred Follow-Up Work

The following are **explicitly out of scope** for this ADR and may be addressed in future work:

1. Centralized runtime configuration (environment variables, config files)
2. Explicit runtime data modes (sample data vs real data fetchers)
3. API/router/service decomposition for better modularity
4. Canonical staging and production deployment paths
5. Enhanced authentication and authorization
6. API rate limiting and caching strategies

## References

- [ARCHITECTURE.md](../../ARCHITECTURE.md): System architecture diagrams
- [DEPLOYMENT.md](../../DEPLOYMENT.md): Deployment procedures
- [README.md](../../README.md): Project overview and quick start
- [docs/PR_SCOPE_GUARDRAILS.md](../PR_SCOPE_GUARDRAILS.md): PR scope policy

## Authors

- Claude (AI Agent)
- DashFin-FarDb Organization

## Review and Approval

This ADR was created as part of PR #[TBD] to establish clear architectural direction for the repository.
