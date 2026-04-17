# Repository Control Plane

This document defines the authoritative sources of truth for how the repository is structured, operated, and evolved.

The goal is to keep development direction singular and prevent drift across contributors, agents, and automation.

## Authoritative documents

The following documents form the control plane:

- `README.md` — repository identity and production path
- `docs/adr/0001-production-architecture.md` — production architecture decision
- `docs/RUNTIME_MODES.md` — runtime data mode and fallback policy
- `docs/DEPENDENCY_POLICY.md` — dependency source of truth and rules
- `docs/PR_SCOPE_GUARDRAILS.md` — pull request scope discipline
- `.github/AUTOMATION_SCOPE_POLICY.md` — automation and agent behavior
- `.github/PULL_REQUEST_TEMPLATE/*.md` — enforced PR structure

These documents take precedence over implicit assumptions in code, tooling, or external scanners.

## Design principle

The repository must have:

- one production architecture
- one runtime contract
- one dependency policy
- one PR execution model

Multiple competing interpretations of any of these introduce technical debt.

## How to use this control plane

When making changes:

1. Identify which control document applies
2. Follow that document's rules
3. If the change alters the rule, update the document in the same PR

When reviewing changes:

1. Validate that the change aligns with the control documents
2. Reject changes that silently contradict them

## Automation and agents

Automation must:

- respect PR scope
- follow the automation scope policy
- avoid redefining architectural or runtime decisions

If automation output conflicts with a control document, the control document is authoritative unless a maintainer explicitly changes it.

## Drift prevention

Drift typically occurs when:

- multiple architectural paths are treated as equal
- runtime behavior is implicit
- dependency sources are duplicated
- PR scope expands during review

This control plane exists to prevent those conditions.

## Updating the control plane

Changes to control-plane documents should:

- be made in focused PRs
- clearly state the new rule
- include rationale
- avoid mixing with unrelated code changes

The control plane is small by design. Do not expand it unnecessarily.
