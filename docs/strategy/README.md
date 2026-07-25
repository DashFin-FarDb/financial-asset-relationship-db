# FarDB strategy documentation

**Status:** foundation in progress; GRAC v1 programme **NEXT**
**Evidence baseline:** `main` at `5e45753705c10c2c4f50e0e9bc4d07b823d752ab`
**Baseline verification (25 July 2026):** `origin/main` resolved to the baseline after PR #1529 (staging H-P0-04
Satisfied / ADR 0007 Accepted).
**Programme (25 July 2026):** Governed Relationship Assertion Contract v1 — ADR 0008 Accepted and contract text
frozen; runtime capability remains **NEXT** until exact-SHA staging proof (epic #1530 / #1540).
**Reviewed:** 25 July 2026

Re-run the manuscript's reviewer verification gate before treating volatile ref and PR observations as current.

## Continuity

- [FarDB Project Continuity Ledger](fardb-project-continuity.md) — durable decisions, commitments, milestones, and
  agent handoffs. Reconcile against current `main` / open PRs before treating its cutoff as current.
- Continuity entries **FARDB-GRAC-V1** (Agreed) and **FPC-2026-07-21-04** track the GRAC programme; do not read them
  as CURRENT product capability.

## Purpose

This section explains FarDB's product thesis, strategic direction and realistic long-range opportunity without
changing the repository's technical or operational authorities.

The organising thesis is:

> FarDB is intended to make consequential relationships explainable, evidence-bound, governed over time and
> operationally trustworthy.

**CURRENT — evidence date 25 July 2026:** The current implementation is a financial relationship platform with
durable persistence, rebuild control plane, and staging database-authorization closure.
**NEXT — evidence date 25 July 2026:** [Governed Relationship Assertion Contract v1](../governance/governed-relationship-assertion-contract-v1.md)
(ADR 0008 Accepted) is the ratified programme to make relationship edges explainable projections of append-only
assertions. Capability remains NEXT until staging proof.
**ASPIRATION — evidence date 15 July 2026:** That direction can be tested across carefully selected domains without
turning every domain into a fork.

## Truth boundary

Strategy material is subordinate to the repository's implementation and evidence sources. When statements
conflict, use this order:

1. Runtime behaviour and immutable evidence for an identified release artefact.
2. Merged code, tests, migrations and security controls.
3. Accepted ADRs, operational authorities and runbooks.
4. The enterprise-readiness index, current-state snapshots and roadmaps.
5. Research notes and domain profiles.
6. Board, brochure and marketing material.

The [enterprise-readiness index](../enterprise-readiness-index.md) remains the entry point for release status. The
[production architecture ADR](../adr/0001-production-architecture.md) remains authoritative for FastAPI, Next.js
and Gradio boundaries. The
[state-machine and operating authority](../governance/state-machine-and-operating-authority.md) remains
authoritative for rebuild, recovery and persistence behaviour. The
[governed relationship assertion contract v1](../governance/governed-relationship-assertion-contract-v1.md)
and [ADR 0008](../adr/0008-governed-relationship-assertion-contract.md) are authoritative for GRAC semantics once
landed; they do not authorize CURRENT capability claims before programme completion.

## Foundation documents

| Document                                              | Purpose                                                                           |
| ----------------------------------------------------- | --------------------------------------------------------------------------------- |
| [Claims and truth policy](claims-and-truth-policy.md) | Defines the five claim classes.                                                   |
| [Current-state snapshot](current-state.md)            | States what the reviewed baseline establishes and what it does not.               |
| [The big read](the-big-read.md)                       | Tells the accessible, evidence-qualified story from prototype to platform vision. |

## Programme documents (NEXT)

| Document | Purpose |
| --- | --- |
| [ADR 0008: Governed Relationship Assertion Contract](../adr/0008-governed-relationship-assertion-contract.md) | Accepted decision to adopt GRAC v1; claim discipline and control-plane disposition. |
| [Governed Relationship Assertion Contract v1](../governance/governed-relationship-assertion-contract-v1.md) | Frozen normative contract (lifecycle, evidence, bitemporal rules, projection, slice). |

## Planned corpus

The following documents should be introduced through separate, one-decision pull requests:

- Product thesis and principles;
- Long-range roadmap and evidence gates;
- Domain-fit and explicit exclusion doctrine;
- Operational Assurance Profile;
- Responsible use, governance and rights;
- Competitive positioning;
- Standardisation and ecosystem strategy;
- Repository documentation and delivery plan;
- Shared glossary and references.

The board roadmap, detailed next-phase roadmap and product brochure are dated strategy artefacts. They should be
regenerated from this corpus after the underlying documents are reviewed, rather than treated as technical sources
of truth.

## Publication rule

Every capability statement must carry a claim class and evidence date. Strategic material may simplify technical
sources, but it may not contradict them or silently promote a research direction into a current product capability.
GRAC v1 ratification (Accepted decision) MUST NOT be restated as CURRENT platform capability until exact-SHA
staging proof is recorded.
