# FarDB strategy documentation

**Status:** foundation in progress
**Evidence baseline:** `main` at `7b424b0012f0e4e56f7b3f5f5e4cd1533ca55990`
**Reviewed:** 15 July 2026

## Purpose

This section explains FarDB's product thesis, strategic direction and realistic long-range opportunity without
changing the repository's technical or operational authorities.

The organising thesis is:

> FarDB is intended to make consequential relationships explainable, evidence-bound, governed over time and
> operationally trustworthy.

**CURRENT — evidence date 14 July 2026:** The current implementation is a financial relationship platform.
**ASPIRATION — evidence date 14 July 2026:** The proposed direction is a governed
relationship-assertion and operational-assurance layer. That direction can be tested across carefully selected
domains without turning every domain into a fork.

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
authoritative for rebuild, recovery and persistence behaviour.

## Foundation documents

| Document | Purpose |
| --- | --- |
| [Claims and truth policy](claims-and-truth-policy.md) | Defines the five claim classes. |
| [Current-state snapshot](current-state.md) | States what the reviewed baseline establishes and what it does not. |
| [The big read](the-big-read.md) | Tells the accessible, evidence-qualified story from prototype to platform vision. |

## Planned corpus

The following documents should be introduced through separate, one-decision pull requests:

- Product thesis and principles;
- Governed relationship assertion proposal;
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
