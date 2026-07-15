# Claims and truth policy

**Status:** proposed governance baseline
**Applies to:** repository documentation, ADRs, issues, pull requests, board materials, brochures, demos, proposals
and public statements
**Reviewed:** 14 July 2026

## Purpose

FarDB's credibility depends on preserving the difference between implementation, evidence, plan, experiment and
ambition. This policy makes that distinction explicit.

It is not designed to suppress ambition. It allows FarDB to state a large ambition confidently because the boundary
around current capability remains clear.

## Five claim classes

### CURRENT

Use only where the claimed behaviour is tied to identifiable evidence.

Examples from the reviewed repository baseline (`main` at `2afe77212fba06b6556d38696a5323e55f04a35a`,
evidence date 14 July 2026):

- **CURRENT — evidence date 14 July 2026; source:** [ADR 0001](../adr/0001-production-architecture.md) declares
  FastAPI and Next.js as the production application path, while Gradio remains non-production and some deployment
  artefacts still require follow-up alignment.
- **CURRENT — evidence date 14 July 2026; source:**
  [ADR 0002](../adr/0002-hosted-deployment-and-persistence.md) identifies PostgreSQL as the hosted durable target and
  preserves SQLite compatibility for local development and tests.
- **CURRENT — evidence date 14 July 2026; source:**
  [state-machine and operating authority](../governance/state-machine-and-operating-authority.md) records persisted
  startup, database-backed recovery authority, lease/lock ownership, heartbeat, fencing-token semantics, RecoveryGate
  and reconciliation invariants.
- **CURRENT — evidence date 14 July 2026; source:** The
  [enterprise-readiness index](../enterprise-readiness-index.md) tracks release-evidence, disaster-recovery and
  operator-sign-off mechanisms.

"Implemented" does not automatically mean "production-scale certified," "generally available" or "independently
assured." Historical evidence for one release candidate does not prove the state of a later commit.

### NEXT

Use for work with a named decision, bounded scope and exit gate.

Examples:

- Repeat a production-shaped release using the identical artefact and fresh evidence.
- Certify a defined capacity and fault envelope.
- Adopt a domain-neutral assertion contract through an ADR before broad vertical work.

NEXT statements must identify what evidence changes the status to CURRENT.

### RESEARCH

Use for hypotheses and experiments that may fail without invalidating the platform.

Examples:

- A Gradio Research Workbench that creates immutable `ResearchRun` records and proposed assertions.
- Synthetic mass-casualty triage simulations.
- A patent claim/evidence reference graph.
- A shadow-mode means-tested entitlement evidence bundle.

Research output should record dataset, code/model version, configuration, limitations and review status. Research
output must not write directly to accepted graph truth.

### ASPIRATION

Use for long-range position and intended category leadership.

Examples:

- A generally reusable governed relationship-assertion standard.
- An industry-leading platform for evidence-bound relationship decisions.
- A federated operational-assurance platform used across regulated and humanitarian settings.

An aspiration must be linked to intermediate proof points, not an unsupported calendar promise.

### EXCLUDED

Use where technical possibility would create strategic drift or unacceptable risk.

Examples:

- Generic graph database replacement.
- Generic visualisation toolkit.
- Direct research-model writes into canonical graph truth.
- Autonomous diagnosis, treatment, battlefield triage or employment dismissal.
- Individual voter, migrant, employee or benefit-claimant risk scoring from associations alone.
- Silent reuse of humanitarian data for enforcement.

## Constructing a capability claim

A defensible capability statement contains:

1. **Subject:** the component, release or product profile.
2. **Behaviour:** what it does, not what it resembles.
3. **Scope:** environment, data shape and user group.
4. **Evidence:** test, artefact, run or authority.
5. **Limitation:** what remains unproven.
6. **Date/version:** when the claim was true.

Example:

> **CURRENT — RC1 evidence captured 29 June 2026:** The identified staging release candidate loaded durable graph
> state and reported 19 assets and 73 relationships. This evidence does not certify a million-node or million-edge
> workload and does not prove a later commit.

## Prohibited unqualified language

Avoid these phrases unless the required evidence exists:

- "enterprise-grade" without a defined workload, availability and support envelope;
- "at scale" without measured scale;
- "real time" without a latency percentile, freshness definition and load;
- "AI-powered" when the value comes from deterministic rules or ordinary automation;
- "prevents fraud" when the system identifies inconsistencies or supports investigation;
- "fair" or "unbiased" as an absolute property;
- "industry standard" before interoperable implementations and external adoption;
- "compliant" where FarDB only supplies controls or evidence that assist compliance;
- "single source of truth" where authority remains federated across lawful custodians.

## Comparative claims

Competitive comparisons must distinguish among:

- a graph database;
- a visualisation or exploration tool;
- a domain application;
- a workflow or case-management system;
- an evidence and decision-governance layer.

FarDB should not be described as outperforming graph databases, visualisation products or domain incumbents at their
primary purpose without reproducible evidence. Its intended differentiation is category and workflow, not universal
technical superiority.

## Evidence expiry

Re-check a current-state statement when:

- the source commit or release artefact changes materially;
- the deployment environment changes;
- a migration alters persistence or recovery;
- a security boundary changes;
- a domain moves from synthetic to real data;
- a model or automated rule affects a consequential decision;
- a public statement is reused after six months.

## Publication review

Before publication, verify:

- every CURRENT claim has identifiable evidence;
- target capabilities are visibly separated;
- numbers are tied to a dataset, artefact and date;
- excluded uses are stated where misuse is foreseeable;
- consequential decisions retain meaningful human authority;
- overpayment, error, allegation and fraud are not conflated;
- proposition, assertion and determination are not conflated;
- a reasonable reader cannot mistake a research prototype for a deployed product.

If any test fails, the material is not ready to publish.
