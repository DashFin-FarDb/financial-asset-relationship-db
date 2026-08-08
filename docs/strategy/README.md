# FarDB strategy documentation

**Status:** foundation in progress; GRAC v1 staged financial vertical slice **CURRENT**
**Evidence baseline:** `main` candidate `16d0a69c5d6f9bae94b9251991466bacbf15d3f0`
**Baseline verification (7 August 2026):** exact-SHA staging seed/publish, same-SHA restart, restart verification,
strict P0 release evidence, database authorization, and named human sign-off are recorded in #1540 / PR #1598.
**Historical programme gate:** GRAC v1 programme **NEXT** until #1540; that gate is satisfied for the exact evidenced
staging financial vertical slice only.
**Reviewed:** 7 August 2026

Re-run the manuscript's reviewer verification gate before treating volatile ref and PR observations as current.

## Continuity

- [FarDB Project Continuity Ledger](fardb-project-continuity.md) — durable decisions, commitments, milestones, and
  agent handoffs. Reconcile against current `main` / open PRs before treating its older cutoff as current.
- The ledger entries **FARDB-GRAC-V1** and **FPC-2026-07-21-04** preserve programme history. Their earlier `NEXT`
  wording is superseded for the bounded staging claim by the exact-SHA sign-off record below; broader production,
  capacity, and multi-domain claims remain unproved.

## Purpose

This section explains FarDB's product thesis, strategic direction and realistic long-range opportunity without
changing the repository's technical or operational authorities.

The organising thesis is:

> FarDB is intended to make consequential relationships explainable, evidence-bound, governed over time and
> operationally trustworthy.

**CURRENT — evidence date 7 August 2026:** FarDB has an exact-SHA proved GRAC v1 financial vertical slice for
`financial.bond.issuer_reference@1` in the evidenced staging scope, with append-only lifecycle history, distinct
proposal/determination authority, deterministic publication, supersession, empty-edge governed-scope continuity,
restart reconstruction, and explanation evidence. The binding record is
[GRAC v1 exact-SHA staging evidence and sign-off](../governance/grac-v1-exact-sha-evidence-signoff.md).

**CURRENT — evidence date 7 August 2026 — broader platform foundation:** The implementation remains a financial
relationship platform with durable persistence, rebuild control plane, bounded FastAPI/Next.js interfaces,
database-authorization controls, and evidence-led release mechanisms.

**NEXT — evidence date 7 August 2026:** Production certification for the GRAC capability, measured
capacity/resilience, repeated immutable promotion, and a second-domain proof remain separate future gates.

**ASPIRATION — evidence date 15 July 2026:** The governed relationship direction can be tested across carefully
selected domains without turning every domain into a fork.

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
and [ADR 0008](../adr/0008-governed-relationship-assertion-contract.md) remain authoritative for GRAC semantics;
the exact-SHA sign-off record is authoritative for the bounded post-#1540 capability claim.

## Foundation documents

| Document                                              | Purpose                                                                           |
| ----------------------------------------------------- | --------------------------------------------------------------------------------- |
| [Claims and truth policy](claims-and-truth-policy.md) | Defines the five claim classes.                                                   |
| [Historical current-state snapshot](current-state.md) | Preserves what the 14 July 2026 baseline established and did not establish.        |
| [The big read](the-big-read.md)                       | Tells the accessible, evidence-qualified story from prototype to platform vision. |

## Programme documents (NEXT) — historical programme classification

The heading retains the programme's pre-#1540 classification for traceability. The frozen contract/ADR describe the
rules that had to be satisfied before promotion; the exact-SHA sign-off record records that the bounded staging gate
has now been satisfied.

| Document                                                                                                      | Purpose                                                                               |
| ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| [ADR 0008: Governed Relationship Assertion Contract](../adr/0008-governed-relationship-assertion-contract.md) | Accepted decision to adopt GRAC v1; claim discipline and control-plane disposition.   |
| [Governed Relationship Assertion Contract v1](../governance/governed-relationship-assertion-contract-v1.md)   | Frozen normative contract (lifecycle, evidence, bitemporal rules, projection, slice). |
| [Exact-SHA GRAC v1 staging sign-off](../governance/grac-v1-exact-sha-evidence-signoff.md)                     | Current bounded staging evidence, final marker, redaction disposition, and sign-off.  |

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
Before #1540, GRAC v1 ratification (Accepted decision) MUST NOT be restated as CURRENT platform capability without
exact-SHA staging proof. That bounded proof and named human sign-off are now recorded for the staged
`financial.bond.issuer_reference@1` vertical slice at
`16d0a69c5d6f9bae94b9251991466bacbf15d3f0`. No broader `CURRENT` claim follows from that evidence.
