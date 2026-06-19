# Project Engineering Mandates

This document defines the foundational engineering standards and workflows for this repository. All contributors (human and agentic) must adhere to these rules.

## 1. PR Triage & Description Standards

Every PR description MUST include the following triage data. Vague statements (e.g., "Updated imports", "Refactored code") are blocking errors; such PRs will be closed immediately for rewriting.

- **Upstream Source:** What called this method, and what assumptions does that caller make about execution speed and state.
- **Downstream Impact:** Where does this return value or state change propagate, and can it cause downstream starvation, resource leaks, or OOM panics.
- **Failure Mode:** What happens when this specific change fails (e.g., if a file stream is interrupted or a database connection drops, how is the system left in a clean state).

## 2. PR Review Lifecycle

- **The 48-Hour TTL:** PRs must progress within 48 hours. Stalled PRs are automatically flagged for an immediate architectural sync.
- **Commit Tag Halts:** CI must parse tags like `[manual-stop]` or `[star]` to pause automated pipelines and force manual sign-off in an ephemeral preview environment.

## 3. Architectural & Invariant Constraints

- **Concurrency Enforcement:**
  - Lock context managers must have a non-configurable TTL max bound of 300 seconds.
  - Acquisition must use deterministic back-off with a 30s max wait ceiling before throwing `LockAcquisitionTimeout`.
- **Resource Safety:** All connection pools, sessions, and file handles must be explicitly managed via context managers with absolute disposal pathways.
- **Idempotency:** All operations must be idempotent and safe against partial failure (network drop/process termination).

## 4. Issue Management (The Gatekeeper)

The Issue Manager ensures abstract roadmap objectives are translated into immutable, bounded engineering contracts.

- **Single Invariant Principle:** One issue = one logical slice of the system. Cross-layer changes must be shredded into isolated issues.
- **No Implied Context:** If a technical dependency or constraint isn't in the issue text, it doesn't exist.
- **Immutable Boundaries:** Once assigned, scope is locked. Edge cases or peripheral optimizations require new issues.

## 5. Enterprise Readiness & Production Gates

All work must adhere to the Enterprise Readiness Roadmap and Release Checklist (`docs/enterprise-readiness-index.md`).

- **Durable Persistence is the Gating Dependency:** Durable graph persistence is required for restart, promotion, and disaster recovery. When implementing persistence, **SQLite compatibility MUST be preserved** for local development.
- **Promotion Requirements:** Bounded health checks are insufficient for promotion. Promotion to staging/production requires explicit durable graph-persistence smoke procedures.
- **API Contracts:** Any changes to API contracts must eliminate ambiguity: density semantics must be normalized end-to-end, visualization payloads must be explicitly modeled, and pagination must be consistently applied.
- **Distributed Hosting & Recovery:** Stale owners must never mutate state after a restart or lock loss. Rebuild cancellation, lock-loss, and multi-instance behavior must be deterministic.
- **PR Scope Strictness:** Work mapped to the Enterprise Readiness PR Plan must contain **one primary decision per PR** and rigorously enforce stated out-of-scope boundaries.
