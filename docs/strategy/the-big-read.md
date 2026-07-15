# FarDB: the long way round to trustworthy relationships

## Why the hard part of graph software begins after the graph appears

**Document class:** STRATEGY manuscript

**Claim convention:** section-level CURRENT, NEXT, RESEARCH, ASPIRATION and EXCLUDED labels follow the
[claims and truth policy](claims-and-truth-policy.md)

**Evidence baseline:** repository main at
7b424b0012f0e4e56f7b3f5f5e4cd1533ca55990, merged PR 1477 head at
576cca12df449678ca9c146a0ff8fa2d2750fb60, and live platform observations made on 15 July 2026

**Audience:** users, contributors, domain experts, operators, partners, buyers, reviewers and investors

**Authority:** explanatory and strategic; subordinate to code, accepted ADRs, operating authorities and
release evidence

> FarDB began as a way to see relationships in financial data. It became a sustained attempt to answer a
> more difficult question: when a relationship matters, what must be true before a person or institution
> should rely on it?

## A note on how to read this manuscript

This is the long-form account that a collection of accurate but time-bound repository documents cannot provide
on its own. ADRs record decisions. Runbooks tell operators what to do. Tests establish bounded behaviour. Release
records preserve evidence for a particular artefact. Those documents should remain narrow. Their precision is
their value.

What they do not naturally provide is the continuous story: why a working visual prototype led to persistence;
why persistence led to recovery authority; why recovery led to fencing, evidence and release governance; why
those engineering lessons now suggest a wider product category; and why that category must carry ethical
constraints at its centre.

This manuscript joins that story without replacing its sources. Whenever it describes a present capability, the
statement is CURRENT and tied to the evidence baseline above. Whenever it describes intended work, it is marked
NEXT. Experiments are RESEARCH. Long-range possibilities are ASPIRATION. Uses that should not be pursued are
EXCLUDED.

The distinction matters. FarDB is ambitious. Ambition becomes more credible, not less, when it can say exactly
where the evidence ends.

---

## Part I — The picture that opened the problem

### 1. A graph is an invitation

> **Claim class:** CURRENT origin story

The original Financial Asset Relationship Database was a recognisable prototype: financial assets represented as
entities; relationships rendered as a network; a 2D and 3D experience capable of making bonds, equities,
commodities, currencies and regulatory events feel less like separate lists and more like parts of one system.
The repository began on 26 October 2025. Two days later, its history records the major 2D/3D visualisation and
formulaic-analysis enhancement. By the end of that first week, the project was already confronting CI, packaging,
deployment, API integration, security review and the division between a Python application and a modern web
frontend.

That pace is worth noticing, but commit volume is not the story and is certainly not a quality metric. The
important event was conceptual. Once the graph appeared, it changed the questions the software could ask.

A table is excellent at answering questions about a record. A graph makes it natural to ask what surrounds the
record, what depends on it, what connects two apparently separate events, which path carried an influence and
where a local change may have a non-local consequence. It offers a view from inside the framework of the data:
not simply the properties of an object, but the structure in which the object participates.

That is the familiar promise of graph theory and graph software. It is also where the dangerous simplification
begins.

An edge on a screen is not self-authenticating. It may represent a measured dependency, a legal assertion, a
market correlation, a model inference, a disputed allegation, a temporary exposure, a stale record or merely a
convenient visual grouping. The line can look equally solid in every case. The geometry does not disclose who
created it, what evidence supports it, which evidence opposes it, when it was valid, whether an authorised person
accepted it or what should happen when later information proves it wrong.

The prototype therefore succeeded in the most useful way a prototype can succeed: it made the next problem
impossible to ignore.

### 2. What the prototype proved

> **Claim class:** CURRENT historical interpretation

The prototype established several real things.

- Financial entities and events could be expressed through a shared relationship model.

- A visual network could reveal structure that ordinary record-by-record presentation obscured.

- Python-based graph logic, analytical calculations and an interactive interface could be assembled into a
  coherent working system.

- The same core could support more than one presentation path: first a direct Gradio experience, then a FastAPI
  application boundary and a Next.js product interface.

- A single founder-maintainer, working autodidactically and with extensive AI-assisted engineering and review,
  could take an idea far beyond a disposable demonstration.

That last point belongs to the human story of FarDB. The project was not born inside a conventional graph
database company or a platform team assembled to a familiar staffing plan. It was driven by a founder who holds
a UK MD from the University of Glasgow, was trained in surgery and brought medical-research experience to an
autodidactic software journey. The approach was to treat software as another field in which first principles,
persistent study and disciplined challenge can turn unfamiliar complexity into working knowledge. The repository
also records a large cast of automated contributors, reviewers, scanners and agents. FarDB is therefore neither
the work of a fictional army nor the output of an unattended machine. It is better described as a human-led,
AI-assisted engineering process with one unusually persistent centre of responsibility.

The prototype did not prove enterprise scale, clinical validity, a generic data platform, a defensible industry
standard or commercial product-market fit. It did not need to. A prototype earns its keep by reducing uncertainty
about the idea and exposing the work that lies between possibility and trust.

### 3. The first reversal

> **Claim class:** CURRENT architectural history

Many prototypes add features until they become products by accumulation. FarDB took a less direct route. It
began to remove ambiguity.

The decisive reversal was to stop treating every working interface as an equal production path. Gradio had done
valuable work. It allowed graph logic, data science and interaction to live close together. It remains well suited
to demonstrations, internal testing and rapid research. But the qualities that make a research interface fast to
change are not the same qualities that should define the governed boundary of a production platform.

Accepted ADR 0001 therefore declared FastAPI and Next.js as the production architecture in April 2026. Gradio
was retained and deliberately classified as non-production. This was not a verdict on the value of Gradio. It was
an exercise in architectural honesty: one production API, one primary product experience, one place to invest
security and contract discipline, and one unambiguous route for deployment.

The decision is central to the future vision. FarDB does not need to discard the freedom of research. It needs to
prevent research freedom from becoming production authority by accident.

---

## Part II — Hosting as an architecture teacher

### 4. The serverless lesson

> **Claim class:** CURRENT historical architecture

Hosting did not merely provide a URL. It exposed the difference between a process that is alive and a system that
remembers.

The early application could hold a graph in memory and use SQLite locally. That is entirely reasonable for a
prototype and remains useful for local development. It is not a durable production model on an ephemeral
serverless filesystem. A process can start successfully, answer a health check and display a graph while having
lost the state an operator believed it was protecting.

ADR 0002 records the resulting decision: retain SQLite as the low-friction local default, use PostgreSQL as the
hosted durable target and make persistence an explicit promotion concern. The chosen hosted path kept the
Next.js and FastAPI monorepo on Vercel and used managed PostgreSQL rather than pretending that a local file had
become durable because it was deployed.

The deployment history shows the learning in public. Earlier Vercel project records, created in November and
December 2025, include erroring deployment states and competing framework identities. The current project,
created in January 2026, identifies Next.js as the framework and serves a production deployment containing both
Node.js and Python functions. On 15 July 2026, the production alias resolved to a READY deployment of main at
2afe7721; Vercel reported no grouped runtime errors for the preceding seven days.

That is useful current evidence. It is not a lifetime availability guarantee, a load certificate or proof that
every backend path exercised the database. A green hosting state proves the deployment state Vercel observed. It
does not, on its own, prove durable graph truth.

### 5. The database lesson

> **Claim class:** CURRENT

The managed Supabase project was created on 19 October 2025, within the same formative period as the prototype.
By July 2026 it was ACTIVE_HEALTHY on PostgreSQL 17. Its public schema contained the small financial graph used
in the reviewed evidence: 19 assets and 73 asset relationships, alongside regulatory-event records and the
coordination tables used for rebuild jobs and distributed locks.

This is a modest dataset. Its importance lies in behaviour, not size. The graph survives process boundaries.
Startup can identify whether data was loaded from persistence. A release check can reject a deployment that is
live but has not loaded durable state. Rebuild and recovery coordination can be recorded in a database rather
than entrusted to one process's memory.

The distinction between a durable target and a hardened public data boundary must also be made explicit. A live
database access-control hardening item remains open. It is a release-blocking issue, not a theoretical footnote.
Remediation requires reviewed policy design, tests and staged rollout; it should not be performed as an
undocumented toggle. Exact live topology, role, policy and adviser details belong in restricted remediation
records until closure has been independently verified.

The current Vercel production deployment being READY does not cancel that database finding. Equally, the
database finding does not erase the persistence and recovery work already achieved. Mature engineering holds
both facts at once.

### 6. The quagmire is the product lesson

> **Claim class:** CURRENT interpretation

Once a graph becomes durable, questions multiply.

What happens when two instances believe they may rebuild it? What happens when the authorised writer pauses,
loses network access and resumes after another writer has taken over? What distinguishes a slow worker from a
dead one? Can a stale process complete a mutation after its lease expires? What does startup do when a previous
job is marked running but no valid executor exists? Does the service fail open, invent a graph or block mutation
until the state can be reconciled? Which operator may override the block? What evidence must accompany that
decision?

These are not graph-layout questions. They are the software-engineering quagmire around the graph. They are also
where FarDB's most distinctive groundwork now sits.

The repository evolved a database-backed recovery control plane: lease and lock ownership, heartbeat and
freshness, fencing against stale writers, explicit rebuild-job lifecycle, failure detection, a RecoveryGate,
reconciliation planning and fail-closed mutation behaviour in ambiguous states. The governing state-machine
document defines operational authority, while runbooks and evidence packs bind release claims to observable
artefacts.

The theoretical insight and the engineering burden are therefore one idea viewed from opposite sides.
Relationships gain value when they reveal structure. They gain trust only when the system can preserve,
reconstruct, challenge and safely change the state from which that structure was derived.

There is a recurring genre of technology website on which the graph rotates beautifully, the word seamless
appears before the second scroll, and somewhere below the pricing accordion an operator is still trying to
discover which writer died halfway through rebuilding the truth. FarDB's strategic wager is that the last part
matters more than the adjective.

---

## Part III — What FarDB is now

### 7. A precise present tense

> **Claim class:** CURRENT

FarDB is now best described as a release-capable financial relationship platform with durable graph persistence,
controlled recovery, bounded FastAPI and Next.js product interfaces, and evidence-led delivery.

Every part of that sentence is deliberate.

**Financial** identifies the domain actually implemented. **Relationship platform** is more accurate than
general-purpose graph database: FarDB uses graph structures to deliver a product, but does not yet compete with
the scale, query languages or ecosystems of mature graph engines. **Release-capable** records that the
repository contains promotion criteria, evidence workflows, rollback and restore procedures, while avoiding the
claim that every current commit has completed those procedures in production. **Durable graph persistence**
describes the implemented storage boundary. **Controlled recovery** describes the authority and reconciliation
work. **Bounded interfaces** recognise that dense graphs require pagination, truncation and explicit contracts.
**Evidence-led delivery** describes a discipline, not a guarantee that every historical artefact is equally
proved.

The present platform can be summarised as follows.

<!-- markdownlint-disable MD013 -->

| Layer | Current role | Current qualification |
| --- | --- | --- |
| Next.js | Primary production user experience | Product-specific, bounded graph views; not a generic dashboard builder |
| FastAPI | Production application and API boundary | Validation, graph operations, health/readiness and recovery integration |
| PostgreSQL | Hosted durable target | Managed on Supabase; an access-control hardening item remains open |
| SQLite | Local development default | Deliberately simple; not the hosted durability claim |
| Graph repository | Persists assets and relationships | Small evidenced dataset; production-scale envelope unmeasured |
| Recovery control plane | Coordinates rebuild authority and failure handling | Database-backed locks, leases, heartbeat, fencing and reconciliation |
| Gradio | Demo, research and internal interface | Explicitly non-production and without canonical mutation authority |
| GitHub delivery system | Code, tests, ADRs, evidence and review history | Repository evidence complements but does not replace target-environment proof |
| Vercel | Current web and function hosting | Current production deployment READY; earlier project history records iteration |
| Supabase | Current managed PostgreSQL service | ACTIVE_HEALTHY; access-control policy requires remediation before broader exposure |

<!-- markdownlint-enable MD013 -->

### 8. What the June release candidate proved

> **Claim class:** CURRENT, artefact-qualified

The RC1 follow-up record dated 29 June 2026 is an important point in the journey. For its identified staging
candidate, it records persisted startup, 19 assets, 73 relationships, security-check review, operator sign-off and
a restore rehearsal. The record reports an observed 15-minute restoration time against a two-hour target for that
exercise.

This is meaningful evidence of behaviour. It is not a scale benchmark. It is not clinical or multi-domain
validation. It does not automatically certify main at 2afe7721 or any later release. The repository's own policy
is explicit: release evidence belongs to an immutable artefact and its environment. Later code must earn fresh
evidence.

That boundary may look cautious to a reader accustomed to cumulative marketing claims. It is actually an asset.
A platform that aims to govern disputed relationships should begin by governing its own assertions.

### 9. The architecture in one view

> **Claim class:** CURRENT

The current architecture has three distinct concerns even when one provider hosts more than one of them.

<!-- markdownlint-disable MD013 -->

| Concern | Question it answers | Current implementation |
| --- | --- | --- |
| Product plane | What may an authorised user see or request? | Next.js and FastAPI |
| Durable truth plane | Which assets and relationships survive process failure? | Repository abstractions backed by PostgreSQL hosted and SQLite local |
| Recovery control plane | Who may change or rebuild truth, and how is failure resolved? | Locks, leases, jobs, heartbeat, fencing, RecoveryGate and reconciliation |

<!-- markdownlint-enable MD013 -->

The separation is more important than the brand names. Vercel can change. The managed PostgreSQL supplier can
change. A specialist graph engine could one day be added for measured workloads. The stable architectural
principle is that product requests, durable domain state and recovery authority must not collapse into an
unexamined in-memory object.

This also explains why FarDB should not define itself by its current database vendor. PostgreSQL is the pragmatic
foundation. It provides familiar transactions, operational tooling and a managed path. FarDB's differentiating
value lies above and around storage: the lifecycle and governance of consequential relationships, and the
operational confidence that the projected state is the state the platform intended to serve.

### 10. Health, readiness and truth

> **Claim class:** CURRENT

FarDB distinguishes several statements that are often conflated:

- The process is alive.

- The application can answer ordinary requests.

- A database connection can be established.

- The durable graph loaded successfully.

- The startup source was persisted state rather than a sample or reconstruction.

- No unsafe rebuild or stale authority blocks mutation.

- The release artefact passed its required target-environment evidence.

Each statement is stronger than the one before it. None should be inferred merely from a green status badge.

This hierarchy is the operational version of FarDB's future semantic thesis. In the domain graph, too, a possible
relationship, a source observation, an actor's assertion, an authorised determination and the currently
projected relationship should not be treated as synonyms.

### 11. The work that remains

> **Claim class:** CURRENT limitations

FarDB is not production-scale certified. It has not demonstrated million-node or million-edge behaviour, an
approved dense-graph workload, sustained concurrency, measured p95 and p99 latency under production-shaped
pressure, a cost curve, or recovery objectives under representative fault injection.

It has not yet shown that two independent domains can use one canonical governed-relationship contract without
forking the core. It does not yet provide a mature domain-adapter SDK, multi-tenant isolation model, protected
identity vault, bitemporal assertion engine or federated evidence exchange.

The current database access posture also needs attention before the platform is exposed to broader or sensitive
use. An unresolved access-control finding affects the database boundary. The correct response is a designed
authorisation model, least-privilege database roles, verified server-side access patterns, appropriate
database-native controls, regression tests and staged evidence. Provider guidance is the starting reference, not
the completed design.

These limitations do not make the platform a prototype again. They define the next gates.

---

## Part IV — From a financial graph to a governed relationship platform

### 12. The product thesis

> **Claim class:** NEXT

FarDB's proposed category is a governed relationship intelligence platform for evidence-bound decisions in
high-stakes systems.

The phrase is intentionally narrower than connected data and broader than financial visualisation. It describes
systems in which a relationship:

- changes what a person or institution may decide;

- can be supported, opposed, corrected or retracted;

- is valid only in a period, jurisdiction, cohort or operational context;

- derives from evidence with a source, method and version;

- requires an identifiable authority before it becomes accepted;

- must be reconstructable after software failure or later challenge.

For such systems, the graph edge is a projection. Behind it sits a lifecycle.

The proposed lifecycle separates five layers:

1. **Proposition** — a relationship that may be true and is open to examination.
2. **Evidence** — material that supports, opposes or qualifies the proposition.
3. **Assertion** — a claim made by an identified actor, source, model or process.
4. **Determination** — an authorised decision about what is accepted for a defined purpose.
5. **Projection** — the relationship state exposed to a product, analysis or downstream system.

This model is not implemented in the current canonical core. It is the next semantic architecture decision to be
designed through an ADR, fixtures and migration policy.

### 13. Why the direction follows from the groundwork

> **Claim class:** NEXT rationale

The future thesis is not a random expansion into attractive industries. It follows a straight line from the
existing engineering.

Durable persistence established that graph state should survive the process displaying it. Recovery authority
established that not every process may change that state. Fencing established that a writer can lose authority
even if it continues to run. Reconciliation established that desired and observed states can differ and require a
deterministic plan. Release evidence established that trust belongs to an identified artefact, not to a vague
impression that the application worked recently.

The governed assertion model applies the same discipline to domain meaning.

Not every source may define accepted truth. A model can lose authority when its version, cohort or purpose is no
longer valid. A later determination can supersede an earlier one without pretending the earlier decision never
happened. The state shown to a user can be reconstructed from evidence, assertions and review. Operational
authority and semantic authority become two parts of one architecture.

That alignment is FarDB's strongest plausible differentiation.

### 14. The three product planes

> **Claim class:** NEXT

The target platform contains three product planes with strict authority boundaries.

#### The governed product plane

Next.js and FastAPI remain the primary production experience. Users inspect accepted relationships, evidence,
conflicts, procedural state, explanations and operational confidence. Domain packs supply vocabulary, views and
workflows without bypassing canonical validation.

#### The research plane

Gradio gains strategic value here precisely because it is not the production authority. A Research Workbench can
support rapid cohort definition, model comparison, feature exploration, visual review and interactive
experimentation. Each run should be immutable and reproducible: dataset and cohort references, code and model
versions, configuration, metrics, outputs, limitations and reviewer state.

A research run may propose assertions. It may not silently promote them into accepted graph truth.

#### The Operational Assurance Profile

Some domains require event capture, freshness, expiry, geospatial context, offline operation, delayed
synchronisation and decisions made while records are incomplete. A future Operational Assurance Profile would
extend the common assertion lifecycle for crisis coordination, contact tracing, disaster displacement, field
triage and related work.

This is ASPIRATION until separately designed and certified. The current hosted web architecture must not be
marketed as offline-first, battlefield-ready, national-scale or safety-critical.

### 15. Build the envelope, not every domain

> **Claim class:** NEXT

FarDB should not attempt to replace the systems of record used by finance, medicine, patent offices, HR,
governments or humanitarian organisations. Nor should it invent one universal vocabulary for all of them.

The reusable product is the envelope around a consequential relationship:

- identity and provenance of the source;

- effective time and system time;

- supporting and opposing evidence;

- confidence and limitations;

- review authority and procedural state;

- permitted purpose and access conditions;

- correction, retraction and supersession;

- reproducible projection;

- operational readiness and recovery evidence.

Domain standards supply domain meaning. FarDB composes with them. FHIR, OMOP, CDISC and GA4GH remain important
in biomedical work. WIPO, EPO and USPTO representations remain important in patents. Existing HRIS, payroll,
customs, tax, benefits and identity systems remain systems of record. FarDB earns a place only where the
cross-system relationship, evidence and decision lifecycle is inadequately governed by those systems acting
alone.

---

## Part V — Values are part of the architecture

### 16. The moral asymmetry of relationship software

> **Claim class:** NEXT policy

Relationship analysis can produce enormous public and organisational value. It can also convert proximity into
suspicion, correlation into causation and administrative convenience into surveillance. The harm is asymmetric:
a false edge in a demo is untidy; a false edge used to deny treatment, employment, a benefit, movement or a vote
can alter a life.

FarDB's ethics therefore cannot be a policy page added after the product is complete. The product model itself
must preserve uncertainty, purpose, provenance, review and the right to correct.

The governing principle is:

> FarDB may help assemble evidence, expose uncertainty, test rules and preserve decision history. It must not
> turn association, allegation or model output into unreviewable authority.

This principle is not anti-automation. Automation can retrieve, compare, validate, detect contradiction, generate
bounded explanations, assemble an evidence bundle and block an unsafe transition. It can make skilled review
faster and more consistent. The boundary is authority: when a consequential adverse decision is made, the system
must make clear which rule, evidence and accountable actor gave it force.

### 17. Separations the platform must preserve

> **Claim class:** NEXT and EXCLUDED

FarDB must never silently collapse:

- contact into exposure, or exposure into transmission;

- anomaly into fraud;

- co-residence into partnership;

- association into ownership or control;

- allegation into finding;

- correlation into causation;

- a manager's opinion into a performance fact;

- a model output into clinical authority;

- a research result into accepted evidence;

- a legal argument into a judicial or administrative determination;

- a discrepancy in public records into an intention to deceive.

These are not merely wording rules. The canonical schema, API contracts, review screens and audit events must
make the distinctions difficult to erase.

### 18. Human authority that is actually human

> **Claim class:** NEXT policy

A human approval button does not create meaningful oversight by itself. A reviewer needs time, information,
authority and a practical ability to disagree.

For consequential decisions, FarDB should support:

- inspection of material supporting and opposing evidence;

- visibility of the rule, model and version used;

- explicit uncertainty and missing-information indicators;

- the ability to amend or reject a proposed outcome;

- recorded reasons and named decision authority;

- notice, correction and appeal where applicable;

- accessible non-digital routes for people who cannot use the product;

- independent challenge of the system's assumptions and effects.

If organisational targets punish reviewers for overturning the model, the review is ceremonial. FarDB cannot
solve every institutional incentive, but it should expose rather than conceal the difference.

### 19. Privacy, identity and purpose

> **Claim class:** NEXT architecture

The target architecture should separate four things that are too often placed in one convenient database view:

1. a protected identity vault;
2. a pseudonymous relationship and decision graph;
3. tamper-evident audit and provenance metadata;
4. aggregate analytical projections.

Access should depend on purpose, role, tenant, jurisdiction, sensitivity, mandate, consent or objection where
applicable, emergency context and retention state. Possession of an API credential is not a complete
authorisation model.

Auditability also does not justify permanent retention of personal content. A system may need to preserve that a
decision occurred, which policy version applied and which evidence categories were considered while deleting,
redacting or rendering inaccessible personal data that no longer has a lawful purpose.

This is why the current database access-control finding matters strategically. A platform cannot credibly
advocate purpose-bound relationship access while leaving the implemented data boundary under-specified. Fixing
it is not separate from the vision. It is the vision applied to the present.

### 20. Medicine as a source of discipline

> **Claim class:** RESEARCH direction

Medicine is a natural reference domain for FarDB, not because the current financial platform is a medical
product, but because biomedical research exposes the exact semantic pressures the target architecture must
handle.

A gene is associated with a phenotype under a study design. A treatment effect applies to a population defined
by inclusion and exclusion criteria. A sample belongs to a processing pipeline and versioned assay. An observed
signal may be statistically significant, clinically irrelevant, confounded or contradicted by later work. A
research model can generate a valuable hypothesis without acquiring the authority to diagnose or treat an
individual.

The founder's medical and research background is especially valuable here. Domain fluency can prevent a
software abstraction from flattening distinctions that matter to real research. It does not replace clinical
validation, biostatistics, information governance or independent review. It improves the quality of the
questions and makes biomedical research an unusually credible co-design environment.

The Gradio research plane also becomes more than a preserved prototype UI in this setting. It can be a fast,
interactive workbench for cohort construction, method comparison and on-the-fly input and output, provided every
run is reproducible and every route from experiment to accepted assertion is explicit.

Autonomous diagnosis, treatment recommendation or battlefield triage authority is EXCLUDED from the current and
near-term product.

---

## Part VI — Where FarDB may genuinely be advantageous

### 21. The domain admission test

> **Claim class:** NEXT strategy

A domain should not enter the roadmap merely because its data can be drawn as a graph. FarDB should have a clear
advantage only when most of the following conditions are present:

- relationships materially affect consequential decisions;

- sources disagree or change over time;

- evidence must be reconstructed across systems;

- the relationship can be contested, corrected or superseded;

- decision authority and procedural state matter;

- history must be preserved without presenting stale state as current;

- operational failure can corrupt or obscure the accepted state;

- manual review is expensive because investigators must traverse many records and systems;

- established systems of record do not already provide a satisfactory cross-system evidence lifecycle.

If an existing database, dashboard, workflow application or integration can solve the problem with ordinary
configuration, FarDB should integrate or step aside. The platform earns its complexity only where governed
relationship truth is itself the missing capability.

### 22. Financial relationship assurance

> **Claim class:** CURRENT foundation and NEXT product

Finance remains the origin and first product foundation. Ownership, exposure, instrument dependency, regulatory
events, collateral, jurisdiction and market relationships all benefit from graph representation. FarDB's future
advantage would not be another market-data terminal or portfolio dashboard. It would be the ability to reconstruct
why a relationship was accepted, which source and rule version supported it, how a regulatory event changed it,
who reviewed an exception and whether the served graph was operationally trustworthy.

Candidate workflows include complex ownership and control assertions, cross-instrument exposure,
regulatory-event impact, disputed entity resolution and source-qualified relationship changes. Market data,
trading, portfolio accounting and generic fraud case management remain better served by established products.

### 23. Biomedical and translational research

> **Claim class:** RESEARCH

Biomedical research is one of the strongest reference domains because it combines entity networks with
provenance, cohort context, versioned methods and contested evidence.

A FarDB Translational Evidence Graph could connect genes, variants, proteins, pathways, phenotypes, cohorts,
interventions, outcomes, publications, samples and research runs. The value would lie in questions such as:

- Which versioned evidence supports this translational hypothesis?

- In which cohort and experimental context did the relationship hold?

- Which later result contradicted or narrowed it?

- Which research run generated the proposed assertion?

- What must a reviewer accept before the relationship appears in a governed product view?

FarDB should compose with FHIR, OMOP, CDISC, GA4GH, research object and provenance standards. It should not try
to become an EHR, laboratory information system, clinical trial management system or autonomous clinical
decision-maker.

### 24. Patent argument and evidence graphs

> **Claim class:** RESEARCH

Patent work has an unusually strong fit because relationships are legal, temporal, evidential and frequently
disputed. A claim depends on other claims. A prior-art reference supports an anticipation or obviousness
argument. Patent families, priority chains, ownership changes, prosecution events and tribunal determinations
alter the context in which a relationship matters.

The product opportunity is not generic patent search or landscaping. Those are established categories. A FarDB
Patent Argument Graph would reconstruct how a proposition about novelty, validity, infringement or ownership was
formed; which passages and claim elements support or oppose it; which procedural authority accepted or rejected
it; and how later events superseded the view.

This is attractive as a bounded reference domain. Public patent sources exist, the procedural lifecycle is rich,
and the separation between argument, evidence and determination is impossible to ignore. Legal expertise and
professional review would still be required. FarDB should not present machine-generated legal conclusions as
authoritative advice.

### 25. Workforce decision integrity

> **Claim class:** RESEARCH

Large, multi-site and multinational employers struggle with evidence scattered across HRIS, payroll, project,
compliance and local management processes. FarDB may add value above those systems when an organisation must
reconstruct a contested relationship or complete a regulated workflow across them.

Candidate uses include:

- pay-grade and pay-dispute evidence, including effective dates and policy versions;

- completion and exception evidence for binding reviews;

- reconstructable performance-assessment inputs and reviewer decisions;

- visibility of workload distribution and cross-team dependency;

- organisational-impact analysis grounded in documented contributions rather than a single opaque score;

- emergency coordination of skills, teams and sites across a large geography.

The available expert support in multinational HR and innovation gives this domain a realistic co-design
advantage. That support includes a PhD-qualified HR scholar and practitioner with experience spanning the World
Bank, Islamic Development Bank, Gulf Investment Corporation, executive search and large-organisation innovation.
It also increases the obligation to reject poor uses. FarDB should not become an employee-surveillance product,
emotion-recognition system, productivity panopticon or automatic engine for dismissal, promotion or discipline.
Its role is evidence integrity and accountable review above existing systems, not the invention of an all-purpose
employee value score.

### 26. Public entitlement, tax and credential evidence

> **Claim class:** RESEARCH with high-governance threshold

Tax, social security, means-tested benefits, passports and driving-licence renewals often require people and
officials to reproduce evidence already held elsewhere. Discrepancies trigger manual review; delays create both
financial waste and harm to eligible people.

FarDB's potential advantage is a purpose-bound evidence and exception layer that can show which verified
relationship or document satisfies a requirement, which rule version applied, what is missing, who made an
exception and how a person can correct or appeal. The goal must include reducing underpayment, delay and
unfulfilled eligibility, not simply stopping payments.

FarDB should not replace tax calculation, benefits administration, identity issuance or ordinary renewal portals.
Nor should a network anomaly be labelled fraud. Public-sector use requires statutory authority, privacy and
equality assessment, security proof, accessible non-digital routes, independent challenge and transparent
appeal.

### 27. Customs, borders and population movement

> **Claim class:** RESEARCH and ASPIRATION

Customs work combines entities, declarations, licences, tariffs, ownership, routes, inspections and regulatory
decisions across jurisdictions. A governed relationship layer could help reconstruct why an exception was
raised, which source established beneficial ownership, which licence covered a movement and how a regulatory
change affected the decision. It should compose with the WCO Data Model and existing Single Window systems
rather than attempting to replace them.

Disaster displacement and humanitarian coordination create a different problem: rapid, incomplete and sensitive
information across organisations that do not have the luxury of exhaustive record review. A future Operational
Assurance Profile might support signed field events, freshness, expiry, consent and purpose restrictions, offline
capture and federated verification.

The same data could expose vulnerable people to serious harm. Migrant credibility scoring, offending prediction,
autonomous detention or removal, and silent transfer from humanitarian purpose to enforcement are EXCLUDED.
National or crisis deployment is ASPIRATION until governance, field safety, federation and offline recovery are
independently proved.

### 28. Contact tracing, emergency coordination and triage

> **Claim class:** ASPIRATION

Contact tracing is a textbook example of why semantic separation matters: contact is not exposure, exposure is
not transmission and transmission risk is not a diagnosis. Time, location, confidence, consent, public-health
purpose and expiry all affect the meaning of a relationship.

Large employers and public bodies also need to coordinate staff, skills, facilities and events during
emergencies across wide geographies. A governed operational graph could provide a current projection while
preserving the event history used to construct it, including stale-data warnings and handover decisions.

Triage models in medicine and other resource-constrained settings could be represented as versioned,
purpose-bound proposals with uncertainty and human authority. They must not be marketed as autonomous or
battlefield-ready on the strength of the present platform. Safety-critical operation requires formal hazard
analysis, human-factors work, validated models, resilient offline design, clinical or operational governance and
certification appropriate to the context.

### 29. Election integrity

> **Claim class:** RESEARCH only under strict constraints; several uses EXCLUDED

Election administration contains legitimate relationship questions: duplicate administrative records,
chain-of-custody events, equipment certification, poll-worker assignments, ballot-material logistics, incident
handling and completion of statutory procedures. A governed evidence graph could help authorised officials
reconstruct a process exception and its resolution.

Individual voter-fraud inference from network patterns is not an acceptable product direction. FarDB must not
connect voter identity to secret ballot content, support partisan targeting, create voter-suppression workflows
or autonomously declare an election valid or invalid. Anomaly detection may identify a record requiring lawful
review; it is not a finding of wrongdoing.

Because democratic legitimacy depends as much on public confidence and procedural fairness as technical
correctness, any election work would require non-partisan governance, public documentation, privacy safeguards,
independent scrutiny and a design that supports correction without disenfranchisement.

### 30. Other domains and the discipline to decline them

> **Claim class:** RESEARCH

FarDB may have useful applications in AI assurance, software and supply-chain evidence, insurance causation,
public inquiries, merger due diligence and critical-infrastructure dependency analysis. In each case the same
test applies: is the unmet problem the governed lifecycle of a consequential relationship, or merely the need to
store, search or display connected data?

FarDB should decline generic graph visualisation, enterprise search, GraphRAG, CRM, recommendation engines,
ordinary project management, generic master-data management, generic lineage, network-topology management,
logistics tracking, SBOM generation, carbon-accounting dashboards and general-purpose digital twins as drivers of
the canonical core. Mature tools already serve those categories. The ability to implement a feature is not the
same as having a reason to build a product around it.

---

## Part VII — Competition without costume

### 31. The graph market is several markets

> **Claim class:** CURRENT market framing

The graph ecosystem is often described as though every product competes for one job. It does not. Neo4j's
[2025 graph-visualisation survey](https://neo4j.com/blog/graph-visualization/neo4j-graph-visualization-tools/)
usefully divides tools into four purposes: development, exploration, dashboarding and embedding. Its examples
include Neo4j Browser, Bloom, NVL, NeoDash, react-force-graph, Cytoscape, Cosmograph, Linkurious, Hume, SemSpect,
Graphileon, KeyLines and yFiles.

Below those product experiences sit graph databases and analytics engines. Beside them sit investigation
products, knowledge-graph platforms, ontology tools, BI systems and domain applications. They overlap, but a
buyer choosing a JavaScript rendering library is not making the same decision as a buyer choosing an enterprise
investigation environment or a durable database.

FarDB should not flatten this landscape in order to make a larger competitor list. It should identify the layer
at which it genuinely creates value.

### 32. How current FarDB stacks up

> **Claim class:** CURRENT

Current FarDB is not a credible substitute for Neo4j as a general graph database, Bloom or Linkurious as mature
exploration products, NeoDash or Graphileon as dashboard builders, or Cytoscape, Cosmograph, KeyLines and yFiles
as specialist visualisation technology.

<!-- markdownlint-disable MD013 -->

| Buyer need | Stronger current default | Current FarDB position |
| --- | --- | --- |
| Store and traverse a very large general graph | Mature graph database and analytics engine | Capacity not certified; PostgreSQL-backed product architecture |
| Develop and optimise graph queries | Neo4j Browser and established query tooling | Product-specific APIs; no equivalent general graph language or ecosystem |
| Let analysts explore arbitrary networks | Bloom, Linkurious, Hume, SemSpect | Bounded financial product views |
| Build configurable graph dashboards | NeoDash, Graphileon and BI tools | Not a dashboard-construction product |
| Embed high-performance network rendering | NVL, Cytoscape, Cosmograph, KeyLines, yFiles and similar libraries | Working 2D/3D product visualisation, without specialist breadth or scale proof |
| Receive enterprise support and training | Established vendors | Early platform and small human-led organisation |
| Reconstruct how a disputed relationship became accepted | Usually a custom application workflow | FarDB's target differentiation; semantic model not yet implemented |
| Separate research proposals from accepted production truth | Usually custom governance | FarDB's target Research Workbench; current Gradio boundary provides groundwork |
| Align relationship governance with recovery and release evidence | Usually assembled across several layers | FarDB has relevant operational groundwork; full product alignment is NEXT |

<!-- markdownlint-enable MD013 -->

The honest conclusion is not that FarDB loses. It is that several rows describe games FarDB should not spend
years trying to win.

### 33. The fully formed FarDB position

> **Claim class:** ASPIRATION with an achievable architecture path

A fully formed FarDB can be stronger by becoming a good customer of mature technology.

It can retain PostgreSQL while it meets measured requirements, add a specialist graph engine only when a tested
workload justifies the operational cost, and integrate a leading embedded visualisation library rather than
attempting to out-layout the companies devoted to that problem. It can expose bounded exploration inside domain
workflows and integrate with existing BI where ordinary reporting is enough.

FarDB should own the layers that express its thesis:

- proposition, evidence, assertion, determination and projection;

- bitemporal relationship history;

- review, correction, retraction, supersession and appeal;

- reproducible research-run promotion;

- purpose-bound evidence bundles and explanation;

- operational readiness, recovery authority and release evidence;

- versioned domain adapters and conformance tests.

The mature target comparison therefore looks different from a feature checklist.

<!-- markdownlint-disable MD013 -->

| Layer | Fully formed FarDB strategy | Competitors that remain stronger in their speciality |
| --- | --- | --- |
| Storage and traversal | Pluggable, workload-measured persistence; PostgreSQL baseline | Neo4j and other graph engines for raw graph scale, algorithms and query ecosystem |
| Rendering | Integrate the best licensed/open component for each product profile | Specialist libraries for layout breadth and browser-scale rendering |
| Exploration | Purpose-built evidence and decision workflows | Bloom, Linkurious, Hume and similar tools for generic analyst exploration |
| Dashboards | Curated operational and decision views; integrate BI | NeoDash, Graphileon and general BI for no-code dashboards |
| Domain records | Preserve source-system authority through adapters | EHR, HRIS, patent, tax, customs, case-management and other systems of record |
| Relationship semantics | Governed assertion lifecycle with time, provenance and contestability | Usually custom modelling in general graph platforms |
| Research boundary | Immutable runs propose; authorised workflows determine | Usually assembled from notebooks, MLOps and workflow tools |
| Operational trust | Recovery authority, readiness and artefact-bound evidence | Infrastructure vendors provide components; FarDB makes the alignment product-visible |
| Rights and governance | Purpose, correction, explanation, review and prohibited uses in the product contract | Varies widely by application and implementation |

<!-- markdownlint-enable MD013 -->

In this position, FarDB does not need to defeat Neo4j. A mature deployment could use Neo4j. It does not need to
defeat Cytoscape. A biomedical domain pack could embed it. FarDB competes with the expensive custom glue,
semantic ambiguity and procedural fragmentation that remain after those capable components have been selected.

### 34. What would make the position defensible

> **Claim class:** NEXT

Architecture alone does not create a market category. FarDB needs proof across five dimensions.

<!-- markdownlint-disable MD013 -->

| Dimension | Proof required |
| --- | --- |
| Semantic | Two independent domains use the same assertion lifecycle without core forks |
| Operational | Published workload, latency, failure, recovery and cost envelopes are repeatable |
| Human | Users can understand, contest and correct consequential relationship decisions |
| Ecosystem | Standards adapters and an external implementation exchange data through conformance tests |
| Market | Design partners select FarDB for the governed relationship workflow and measure an improvement |

<!-- markdownlint-enable MD013 -->

Useful commercial measures include time to reconstruct an evidence chain, reviewer effort, exception-cycle time,
percentage of decisions with complete provenance, rate of corrected unsupported assertions, restoration
performance and integration cost. Beautiful graphs may help adoption. They are not the proof of value.

### 35. The platform brochure promise

> **Claim class:** NEXT positioning

The strongest accurate promise is:

> FarDB helps an organisation know which relationships it currently accepts, why it accepts them, who authorised
> them, what evidence could change them and whether the underlying operational state can be trusted.

This demonstrates competence without pretending that every element is already implemented. Marketing should show
the working financial platform and its persistence, recovery and delivery foundations as CURRENT; present the
governed assertion core and first domain packs as NEXT or RESEARCH; and reserve words such as industry standard,
clinical, national-scale and autonomous for evidence that does not yet exist.

The platform does not need inflated claims. Its unusual quality is that the proposed destination can be traced
back through decisions already taken in the codebase.

---

## Part VIII — The tortoise strategy

### 36. Old-fashioned work in a fashionable field

> **Claim class:** NEXT strategy

In the spirit of Warren Buffett and the late Charlie Munger—this is a paraphrase of an investing disposition, not
a claimed verbatim quotation—FarDB's posture is the tortoise that keeps doing the important, unfashionable work
while fashion changes its vocabulary.

In software, the unfashionable work includes:

- defining who owns a decision;

- maintaining dependencies and applying security patches;

- documenting migration and compatibility rules;

- testing persistence across restarts;

- rehearsing restore rather than admiring the backup setting;

- failing closed when authority is ambiguous;

- measuring capacity before promising scale;

- recording evidence for the artefact actually deployed;

- making correction and appeal work after the demonstration ends.

This is not a rejection of innovation. FarDB uses graph theory, modern web architecture, managed cloud services,
AI-assisted engineering and a research interface designed for rapid ML experimentation. The strategic claim is
that innovation compounds when it is attached to durable operating discipline. Hype can accelerate attention. It
cannot substitute for state recovery.

### 37. Values and business are co-dependent

> **Claim class:** NEXT strategy

The business opportunity is not to sell virtue as decoration. It is to serve buyers for whom trustworthy process
has economic value.

Regulated organisations, research teams and public institutions pay for work caused by ambiguity: manual
evidence collection, repeated reconciliation, disputed decisions, inconsistent policy versions, audit
preparation, incident reconstruction and the inability to prove which state was served. A platform that reduces
that burden while supporting correction can create value and protect rights through the same mechanism.

That co-dependence is important. If ethical controls make the product impossible to buy or operate, they will be
bypassed. If commercial pressure turns uncertainty into unjustified certainty, the product destroys the trust on
which its differentiation depends. FarDB should therefore design review, evidence and purpose controls as usable
product capabilities with measurable operational benefit.

### 38. Authentic growth

> **Claim class:** ASPIRATION

FarDB's most plausible route is not to claim a universal platform before a second domain exists. It is to earn a
small number of demanding users who recognise the problem.

The early buyer may be the person who has spent years moving between a system of record, a spreadsheet, an email
thread, a policy document and a case tool to reconstruct one consequential relationship. The early technical
reviewer may be the person who routinely searches past the polished screenshots for patch governance, data
durability, persistence semantics, restore procedures and evidence of what happens when the writer fails.

For those people, the repository's journey is not an embarrassing prelude to be hidden. It is part of product
credibility. It shows which problems appeared only after the prototype worked and how the architecture changed in
response.

Authentic growth means converting that credibility into repeatable delivery:

1. one proved release process;
2. one measured workload;
3. one implemented assertion lifecycle;
4. one reference domain beyond finance;
5. one design partner with an outcome;
6. one external conformance exchange.

Each step is valuable by itself. Together they create the possibility of a category.

### 39. The team story without mythology

> **Claim class:** CURRENT and NEXT

FarDB's origin demonstrates unusual individual range and persistence. It should neither hide that fact nor turn it
into a theory that expertise is unnecessary.

The founder's role is product thesis, architectural continuity, medical and research perspective, and the
willingness to stay with the unglamorous problem. AI-assisted engineering and automated review have expanded the
amount of work one person can coordinate. External domain expertise, particularly in HR, further improves the
quality of discovery without imposing an immediate financial burden.

As adoption and risk grow, named capability must grow with them. Security, data protection, site reliability,
frontend product design, performance engineering, domain safety, legal interpretation and customer integration
are responsibilities that need competent owners. Those owners may arrive through focused contracting,
partnerships, outsourced product work, design partners, advisors or employees. The roadmap should define the work
and evidence first, then acquire the capacity appropriate to each gate.

This is not a concession that the current journey should have required a conventional team. It is how the
project protects what one determined mind has already made possible.

---

## Part IX — The next phase

### 40. Roadmap principle

> **Claim class:** NEXT

FarDB should progress by evidence gates, not by the number of features completed or the passage of calendar time.
Discovery can run ahead. Production claims cannot.

The highest-value sequence is:

1. close the current access-control finding and stabilise the truth baseline;
2. make release and recovery repeatable for one immutable artefact;
3. measure the workload and failure envelope;
4. implement the governed assertion core;
5. prove the core in two domains;
6. add research and operational profiles without weakening canonical authority;
7. test interoperability before proposing a standard.

### 41. Immediate priority — database access hardening

> **Claim class:** NEXT, release-blocking

The 15 July access-control finding changes the order of work. Before broader exposure, the platform needs a
deliberate database authorisation boundary. Exact live configuration and adviser evidence remain restricted
until remediation is verified.

#### Immediate hardening work

- Map every route to the database, including application, provider-managed API, administrative, migration and
  recovery paths.

- Identify which tables belong in an API-exposed schema and which should move to a private schema.

- Define application, migration, recovery, read-only and administrative roles with least privilege.

- Review existing access policies and remove duplicate or contradictory rules before enforcement.

- Enforce tested row-level or equivalent authorisation on every API-exposed data path, or revoke exposure where
  the product does not need it.

- Review privileged function execution and restrict it to intended roles.

- Add integration tests for untrusted, ordinary application, recovery and administrative principals.

- Run migrations and policy changes in a branch or staging project, capture before/after adviser results and
  rehearse rollback.

- Review secrets and keys after the exposure analysis, rotating any credential whose risk cannot be bounded.

#### Immediate hardening exit evidence

- No unresolved high-severity database access-control finding, or a named and time-bounded exception approved
  before release.

- No public role can read or mutate coordination, credential or internal graph tables without an explicit
  product requirement and tested policy.

- Hosted application, recovery and restore paths still pass after the policy change.

- The database topology and migration authority are documented without publishing secrets.

#### Immediate hardening expected outcome

A credible least-privilege boundary and a release baseline that can support sensitive-domain design without
contradicting FarDB's own purpose-bound-access principle.

### 42. Gate 1 — repeatable production release

> **Claim class:** NEXT

**Indicative horizon:** the first six weeks after immediate hardening, subject to evidence.

#### Gate 1 work

- Create a release manifest binding commit SHA, build artefacts, image or function identities, dependency locks,
  migrations, configuration class and evidence bundle.

- Promote the same immutable artefact through staging and production rather than rebuilding an equivalent
  candidate.

- Define migration ownership, forward/backward compatibility and rollback rules.

- Validate PostgreSQL connection pooling and total connection budget under the Vercel function topology.

- Exercise failed persisted-load, lock loss, stale writer, interrupted rebuild and ambiguous startup paths.

- Rehearse application rollback, configuration rollback and database restore.

- Separate deploy, promotion, rollback and restore authority even if one person currently holds more than one
  role.

- Capture fresh security, readiness and persistence evidence for the exact release identity.

#### Gate 1 exit evidence

- Two consecutive release cycles use the same procedure and immutable artefact identity.

- Persisted startup is proven after deploy, rollback and restoration.

- No unresolved critical security or data-integrity finding remains.

- Recovery and operator sign-off evidence are complete and redacted appropriately.

#### Gate 1 expected outcome

FarDB becomes repeatably releasable, not merely release-capable. This is the foundation for reliable demos,
design-partner access and investment diligence.

### 43. Gate 2 — capacity and resilience certification

> **Claim class:** NEXT

**Indicative horizon:** weeks 6–12 after Gate 1, with tuning iterations.

#### Gate 2 work

- Define named workloads rather than one vague scale target: sparse portfolio networks, dense ownership or
  exposure subgraphs, regulatory-event fan-out, paginated browsing, concurrent reads, controlled mutation,
  rebuild and restart.

- Create deterministic dataset manifests and generators with known node, edge, density and attribute
  distributions.

- Measure end-to-end p50, p95 and p99 latency, throughput, memory, database connections, query cost, cold start,
  rebuild duration and UI rendering limits.

- Test pressure tiers that increase by order of magnitude until an approved workload passes or an architectural
  boundary is reached.

- Inject writer loss, database interruption, lease expiry, partial recovery and stale process resumption.

- Validate pagination, truncation and aggregation so the UI fails boundedly when a graph is too dense to render
  meaningfully.

- Publish an infrastructure and operating-cost curve for each approved tier.

- Decide from measurements—not fashion—whether PostgreSQL remains sufficient, requires indexed/projection
  changes or should be complemented by a specialist graph engine.

#### Gate 2 exit evidence

- A versioned workload envelope names what the platform supports and under which topology.

- Performance and failure limits are published with the test harness.

- Recovery objectives hold under representative pressure.

- Product interfaces remain responsive and semantically honest at their density limits.

#### Gate 2 expected outcome

The phrase production scale acquires a number, a workload and a cost. Architecture choices become investable
decisions rather than intuitions.

### 44. Gate 3 — the governed assertion core

> **Claim class:** NEXT

**Indicative horizon:** one to two quarters after capacity baselining, with ADR work beginning earlier.

#### Architectural decisions

- Canonical identity and versioning for proposition, evidence, assertion, determination and projection.

- Bitemporal representation: effective time in the domain and system time in FarDB.

- Evidence-reference policy: what FarDB stores, what remains with the source custodian and how integrity is
  verified.

- Lifecycle state machine for proposal, review, acceptance, rejection, retraction and supersession.

- Deterministic projection rules and explanation bundles.

- Extension mechanism for domain vocabularies.

- Migration, compatibility and event-version authority.

#### Implementation work

- Publish the ADR and a versioned schema with valid, invalid and adversarial fixtures.

- Implement persistence and repository boundaries without coupling the core to the current financial classes.

- Add mutation APIs that enforce authority and idempotency.

- Build reviewer views for evidence, opposition, procedural state and projected output.

- Preserve the current financial graph through an adapter and a rehearsed migration.

- Add projection-reproducibility and lifecycle-transition tests.

#### Gate 3 exit evidence

- The financial domain uses the new core without losing current behaviour or provenance.

- The same input lifecycle deterministically produces the same authorised projection.

- Invalid authority, time and supersession transitions fail closed.

- Migration and rollback are proven on a representative copy.

#### Gate 3 expected outcome

FarDB crosses from a robust financial graph platform into the first implemented form of its proposed category.

### 45. Gate 4 — research workbench and reference-domain proof

> **Claim class:** RESEARCH moving to NEXT only after gate approval

**Indicative horizon:** two to four quarters, overlapping with Gate 3 discovery.

#### Biomedical reference

- Choose one bounded translational-research workflow with public, licensed or synthetic data.

- Map established identifiers and provenance rather than inventing a medical ontology.

- Implement immutable ResearchRun records for cohort, data, code, model, parameters, outputs, metrics and
  limitations.

- Let Gradio create and compare runs and propose assertions.

- Require governed review before any assertion reaches the accepted projection.

- Evaluate reproducibility, evidence-reconstruction time and expert usability.

#### Second-domain proof

- Implement either a patent argument graph or a workforce evidence workflow using the same canonical core.

- Permit domain-specific extensions, but record every pressure to change canonical fields.

- Demonstrate that the second domain can be delivered without a core fork.

#### Gate 4 exit evidence

- Two domains share the proposition-to-projection lifecycle.

- Research outputs cannot bypass review.

- Domain experts approve the semantic distinctions and identify limitations.

- A measurable workflow outcome improves against the current manual process.

#### Gate 4 expected outcome

The general-platform claim becomes evidence-based. Biomedical expertise becomes a genuine design advantage, and
the second domain proves that the core is not merely finance renamed.

### 46. Gate 5 — operational assurance

> **Claim class:** ASPIRATION until Gate 4 evidence

#### Gate 5 work

- Specify signed event identity, freshness, expiry, correction and chain of custody.

- Design offline capture, deterministic conflict resolution and delayed synchronisation.

- Define geospatial privacy and purpose limitations.

- Separate current operational projection from the immutable event record.

- Add incident modes, degraded operation, resource state and handover.

- Conduct field-oriented safety, usability and recovery exercises in synthetic or shadow mode.

#### Gate 5 exit evidence

- Offline and reconnect behaviour is deterministic and recoverable.

- Stale or conflicting data is visible rather than silently merged.

- A domain safety case and misuse assessment have independent review.

- No safety-critical claim exceeds the tested context.

#### Gate 5 expected outcome

FarDB can explore crisis and field coordination as a separately certified product profile without contaminating
the simpler hosted core.

### 47. Gate 6 — conformance and ecosystem

> **Claim class:** ASPIRATION

#### Gate 6 work

- Publish a narrow assertion-envelope specification only after cross-domain proof.

- Provide schemas, lifecycle rules, normative examples, invalid fixtures and migration tests.

- Map provenance and domain standards without claiming to replace them.

- Exchange an evidence-qualified assertion with an independently configured implementation.

- Establish version, security, privacy and change governance.

- Invite external implementers and domain reviewers before approaching a standards body or consortium.

#### Gate 6 exit evidence

- At least one implementation outside the core repository passes conformance tests.

- A real exchange exposes and resolves semantic gaps.

- Governance includes credible participation beyond one vendor.

#### Gate 6 expected outcome

FarDB may contribute an interoperable method for governing relationship assertions. Industry-standard language
becomes appropriate only after adoption, not at schema publication.

### 48. Roadmap summary

<!-- markdownlint-disable MD013 -->

| Gate | Highest-value result | Board-level evidence |
| --- | --- | --- |
| Immediate | Secure data boundary | Adviser errors resolved, policy tests and staged rollback proof |
| 1 | Repeatable release | Two immutable-artefact promotions with recovery evidence |
| 2 | Known scale and cost | Approved workload envelope and fault-tested limits |
| 3 | Differentiating semantic core | Governed lifecycle running the financial domain |
| 4 | Platform generality | Two domains, one core, measurable expert workflow outcome |
| 5 | Operational profile | Independently reviewed offline and field-safety evidence |
| 6 | Ecosystem potential | External conformance implementation and exchange |

<!-- markdownlint-enable MD013 -->

---

## Part X — Architectural decisions that will determine the company

### 49. Decisions to keep stable

> **Claim class:** CURRENT

Several decisions should remain stable unless new evidence justifies an ADR:

- FastAPI and Next.js are the production architecture.

- Gradio is a non-production research and demonstration path.

- SQLite is the local default; hosted state requires durable persistence.

- Product, durable truth and recovery authority are logically distinct.

- Ambiguous mutation and recovery state fails closed.

- Release evidence is tied to an identified artefact and environment.

- Repository checks and hosted proof are complementary.

### 50. Decisions to make next

> **Claim class:** NEXT

<!-- markdownlint-disable MD013 -->

| Decision | Why it matters | Preferred direction to test |
| --- | --- | --- |
| Database authorisation | Open access-control finding and future sensitive data | Private-by-default schemas, least-privilege roles and tested purpose-bound access |
| Connection management | Serverless concurrency can exhaust PostgreSQL | Bounded pooling and measured connection budget |
| Assertion contract | Defines FarDB's product category | Five-layer lifecycle with explicit actor, evidence, time, authority and status |
| Bitemporality | Corrections must not erase historical decisions | Effective and system time as first-class fields |
| Evidence custody | Centralisation creates cost and privacy risk | Integrity-verified references by default; store content only with a defined purpose |
| Identity separation | Multi-domain sensitive work requires minimisation | Protected vault, pseudonymous graph and aggregate views |
| Domain extensions | Prevents a universal-schema trap | Versioned namespaces and conformance fixtures |
| Research promotion | Protects canonical truth | Immutable runs propose; governed services accept |
| Graph engine threshold | Avoids both premature rewrite and late bottleneck | Add a specialist engine only after a measured workload crosses a defined boundary |
| Multi-tenancy | Determines security and commercial topology | Isolation model selected before sensitive design-partner data |
| Federation | Cross-organisation work should not require one data lake | Verify necessary assertions while evidence remains with lawful custodians |
| Operational profile | Offline and crisis work changes the safety case | Separate optional profile and certification envelope |

<!-- markdownlint-enable MD013 -->

### 51. A reversible architecture

> **Claim class:** NEXT principle

FarDB should prefer interfaces, adapters and measured substitution points over sweeping rewrites. The current
PostgreSQL foundation can remain canonical while a projection is exported to a specialist engine for a proven
query or rendering need. A domain pack can add vocabulary without changing the assertion lifecycle. A research
tool can evolve quickly without acquiring production write authority.

Reversibility is especially important for a small organisation. It preserves the ability to learn without
turning every experiment into migration debt.

---

## Part XI — Outcomes, risks and measures

### 52. Expected outcomes

> **Claim class:** NEXT

If the roadmap is executed in order, the expected outcomes are:

- **For users:** less time reconstructing why a relationship exists, clearer uncertainty and a practical route to
  correction.

- **For operators:** explicit recovery authority, known release identity and repeatable restore evidence.

- **For organisations:** reduced manual evidence gathering, more consistent cross-system review and stronger
  auditability.

- **For researchers:** rapid experimentation with reproducible runs and no accidental path from model output to
  accepted truth.

- **For partners:** a narrow integration contract that preserves source-system authority.

- **For investors:** a sequence of de-risking proofs—security, release, scale, semantic differentiation,
  cross-domain reuse and market outcome—rather than one all-or-nothing platform bet.

### 53. Principal risks

> **Claim class:** CURRENT and NEXT

<!-- markdownlint-disable MD013 -->

| Risk | Present signal | Response |
| --- | --- | --- |
| Access-control gap | Unresolved database access-control finding | Treat as immediate release-blocking hardening |
| Scope dilution | Many plausible domains | Apply the domain admission test and explicit exclusions |
| Semantic overreach | Universal graph models erase domain distinctions | Own the governance envelope; preserve domain standards |
| Scale uncertainty | Small 19/73 evidence dataset | Gate claims through representative benchmark and fault harnesses |
| Vendor/topology drift | Several historical Vercel project identities | Maintain topology manifest and immutable release mapping |
| Documentation inflation | Strategy can outrun implementation | Use PR1 taxonomy and evidence dates for every publication |
| Founder concentration | Architectural context and authority are concentrated | Decision records, runbooks, conformance tests and named backup capability |
| AI-assisted change volume | Automated contributors can widen scope or add noise | One PR equals one decision, explicit production boundary and human approval |
| High-stakes misuse | Attractive domains include people, rights and safety | Prohibited uses, purpose controls, independent review and staged shadow mode |
| Premature standardisation | A schema without adopters creates ceremony | Cross-domain and external implementation before standards claims |

<!-- markdownlint-enable MD013 -->

### 54. Measures that matter

> **Claim class:** NEXT

FarDB should maintain a balanced scorecard.

#### Reliability

- successful immutable-artefact promotion rate;
- persisted-startup success;
- restoration and rollback time;
- stale-writer prevention and recovery drill results;
- security adviser and dependency status.

#### Performance

- p50, p95 and p99 API latency by workload;
- dense-view time and bounded truncation behaviour;
- rebuild duration;
- database connections, memory and cost per workload tier.

#### Semantic quality

- percentage of accepted relationships with complete provenance;
- reproducible-projection rate;
- unsupported assertion and correction rate;
- supersession and bitemporal consistency;
- cross-domain core-change pressure.

#### Human and product outcomes

- evidence-reconstruction time;
- reviewer effort and exception-cycle time;
- appeal/correction completion;
- user comprehension and accessibility;
- false certainty or stale-state incidents.

#### Market learning

- design partners reaching a defined outcome;
- integration time;
- renewal or expansion based on governed relationship value;
- external conformance implementations;
- requests declined because another product was the better fit.

The last measure is not facetious. The ability to decline work that would dilute the platform is a sign that the
category has a boundary.

---

## Part XII — The invitation

### 55. What FarDB asks of a user

> **Claim class:** NEXT strategy

FarDB is not asking a user to admire a graph. It is asking them to identify a relationship decision that is
currently expensive, fragmented, difficult to explain or unsafe to reconstruct.

The right first engagement is narrow:

- name the relationship and the decision it changes;

- identify the systems and evidence that currently support it;

- describe who may assert, challenge and determine it;

- define the time, purpose and jurisdiction in which it is valid;

- measure the present reconstruction and review burden;

- build a shadow workflow before making it authoritative;

- agree in advance what evidence would count as success or failure.

This creates a design partnership rather than a theatrical pilot.

### 56. What FarDB asks of a contributor

> **Claim class:** CURRENT practice

Contributors are asked to respect the distinction between working code and authorised architecture. The
repository's one-PR-one-decision discipline is not bureaucracy for its own sake. It is how a small, highly
automated project preserves reviewability.

A valuable contribution may be a new capability. It may also be a smaller contract, a clearer invariant, a
deleted ambiguity, a reproduced failure, a migration fixture, a restore record or a statement that an attractive
idea does not belong in the core.

### 57. What FarDB asks of a partner or investor

> **Claim class:** NEXT strategy

The useful question is not whether FarDB can list enough industries to sound large. It is whether the proposed
governed relationship category is real, whether the existing architecture reduces the cost of reaching it and
whether each funding or partnership step can retire a defined risk.

Near-term resources should buy evidence:

- access-control closure;

- repeatable release;

- capacity measurement;

- semantic-core implementation;

- expert-led reference-domain proof;

- product usability and integration;

- independent security, privacy and domain challenge.

Presentation quality matters, and specialist UI work can be commissioned when it accelerates adoption. It should
show the product's competence rather than disguise missing operational proof.

### 58. What FarDB promises in return

> **Claim class:** NEXT strategy

FarDB should promise intellectual honesty, serious engineering, visible limitations and the willingness to
change an architecture when evidence requires it.

It should promise that a research model will not be called a determination, that a deployment badge will not be
called durable truth, that a small restore exercise will not be called national resilience and that a graph
association will not be called guilt.

It should also promise not to confuse modest language with modest intent.

---

## Epilogue — From the line to the trust

The first FarDB made relationships visible.

The engineering journey since then has asked what it takes to keep the picture from lying after the process
restarts, the filesystem disappears, two workers compete, a writer loses authority, a release changes, a source
is corrected or a reviewer disagrees.

Those are not secondary concerns orbiting the original idea. They reveal the larger idea.

A consequential relationship is not just two entities and an edge. It is a proposition made in context,
supported and opposed by evidence, asserted by an actor, accepted or rejected by authority, projected for a
purpose, changed over time and served by an operational system that must itself be trustworthy.

FarDB has not completed that platform. It has built enough of the difficult foundations to make the direction
logical. It has also built enough to know that the remaining work cannot be skipped by a larger animation, a
longer feature list or a fashionable model.

The tortoise is not slow because it lacks imagination. It is steady because it intends to arrive with the truth
still attached.

---

## Appendix A — Milestone chronology

> **Claim class:** CURRENT historical record

<!-- markdownlint-disable MD013 -->

| Date or period | Milestone | Meaning |
| --- | --- | --- |
| 19 October 2025 | Current Supabase project created | Managed PostgreSQL entered the platform story during the prototype period |
| 26 October 2025 | Initial repository commit | Financial Asset Relationship Database became a versioned engineering project |
| 28 October 2025 | Major 2D/3D and formulaic-analysis enhancement | The visual graph proposition became tangible |
| 31 October 2025 | Vercel Next.js and FastAPI integration work | Hosting began to force frontend/backend and serverless decisions |
| November–December 2025 | High-volume CI, test, security, deployment and review iteration | Prototype breadth met the realities of maintainability and hosting |
| 17 April 2026 | ADR 0001 accepted | FastAPI and Next.js declared production; Gradio classified non-production |
| 30 April 2026 | ADR 0002 adopted | PostgreSQL chosen for hosted durability; SQLite retained locally |
| PRs 1096–1119 | PostgreSQL URL handling, health, persistence and repository round-trip | Hosted graph truth moved out of process memory |
| PRs 1141–1193 | Audit logging, operator authority, job persistence, observability, failure detection, RecoveryGate and reconciliation | The recovery control plane became explicit |
| PRs 1287–1301 | Enterprise-readiness remediation sequence | Persistence, promotion, contracts, recovery, hosting, security, DR and evidence were reconciled |
| 29 June 2026 | RC1 follow-up evidence | Small persisted graph, restore rehearsal and operator evidence captured for the identified candidate |
| 13 July 2026 | Main at 2afe7721 | Baseline used by the current-state strategy snapshot |
| 14 July 2026 | PR 1477 opened | CURRENT/NEXT/RESEARCH/ASPIRATION/EXCLUDED taxonomy proposed as documentation policy |
| 15 July 2026 | PR 1477 merged | Claim taxonomy accepted into main through merge commit 7b424b00 |
| 15 July 2026 | Live Vercel and Supabase observation | Current production deployment READY; PostgreSQL ACTIVE_HEALTHY; access-control finding surfaced |

<!-- markdownlint-enable MD013 -->

## Appendix B — Live observation record

> **Claim class:** CURRENT at 15 July 2026; volatile evidence

These observations were made through the connected platform APIs while preparing this manuscript. They are not
a substitute for a redacted release evidence pack and should be recaptured for promotion.

### GitHub

- Repository: DashFin-FarDb/financial-asset-relationship-db.

- Main baseline: 7b424b0012f0e4e56f7b3f5f5e4cd1533ca55990.

- PR 1477: merged from head
  576cca12df449678ca9c146a0ff8fa2d2750fb60 through merge commit
  7b424b0012f0e4e56f7b3f5f5e4cd1533ca55990.

- PR 1477 is documentation-only; its merged taxonomy does not make the target assertion model current.

### Vercel

- Current project framework: Next.js.

- Production alias resolved to a READY deployment of main at 2afe7721.

- Deployment metadata reported one Node.js and one Python function runtime, consistent with the declared
  Next.js/FastAPI monorepo path.

- No grouped runtime error was reported for the selected preceding seven-day window.

- Two earlier project records remain visible, with older latest deployments in ERROR state. They are historical
  evidence of deployment iteration, not the current production identity.

### Supabase

- Project state: ACTIVE_HEALTHY.

- Database: PostgreSQL 17 on the general-availability channel.

- Current graph rows: 19 assets and 73 asset relationships.

- Current coordination tables include rebuild jobs and distributed locks.

- A database access-control hardening item was observed and remains open.

- Exact live schema, role, policy and adviser output is intentionally omitted from this public manuscript. It
  should remain in restricted remediation records until closure is independently verified.

- Performance-adviser findings also require triage; exact live configuration details are omitted here.

No database mutation was made while preparing this manuscript. Authorisation changes require reviewed policies,
staged testing and rollback evidence because incorrect controls can block legitimate access.

## Appendix C — Claim glossary

<!-- markdownlint-disable MD013 -->

| Class | Meaning in this manuscript |
| --- | --- |
| CURRENT | Implemented or observed at the named baseline, with stated limitations |
| NEXT | Approved or recommended next work, not yet a current capability |
| RESEARCH | Hypothesis, experiment or reference-domain investigation |
| ASPIRATION | Long-range possibility dependent on prior proofs |
| EXCLUDED | Capability or use that should not be claimed or pursued under the stated platform direction |

<!-- markdownlint-enable MD013 -->

## Appendix D — Reading paths

### Ten-minute strategic path

Read sections 1, 6, 7, 12, 16, 31–38, 40 and the epilogue.

### Technical and architecture path

Read sections 3–15, 31–34, 40–51 and Appendices A–B.

### Domain and ethics path

Read sections 16–30, 44–47 and 52–54.

### Board and investment path

Read sections 7–11, 31–39, 41–48, 52–58 and the epilogue.

## Appendix E — Repository source map

This manuscript should be reviewed against the following authorities:

- [Production architecture ADR](../adr/0001-production-architecture.md).

- [Hosted deployment and persistence ADR](../adr/0002-hosted-deployment-and-persistence.md).

- [Distributed lock refresh and heartbeat ADR](../adr/0003-distributed-lock-refresh-and-heartbeat-strategy.md).

- [Distributed hosting semantics ADR](../adr/0004-distributed-hosting-semantics.md).

- [Backup, restore and disaster-recovery ADR](../adr/0005-backup-restore-dr-strategy.md).

- [Release and deployment automation ADR](../adr/0006-release-and-deployment-automation.md).

- [State machine and operating authority](../governance/state-machine-and-operating-authority.md).

- [Enterprise-readiness index](../enterprise-readiness-index.md).

- [Enterprise-readiness audit](../audits/enterprise-readiness-audit.md).

- [Release evidence pack](../release-evidence-pack.md).

- [RC1 follow-up evidence](../evidence-records/rc1-objective-2-follow-up.md).

- [Operational evidence capture framework](../operations/operational-evidence-capture-framework.md).

- [Failure-mode and scale validation](../testing/failure-mode-and-scale-validation.md).

- [Claims and truth policy](claims-and-truth-policy.md).

- [Current-state strategy snapshot](current-state.md).

## Appendix F — Review and maintenance rule

This manuscript is intentionally comprehensive, but it must not become a frozen monument.

- Review live-state statements before every external publication.

- Update the evidence baseline when a new immutable release becomes authoritative.

- Change an accepted architecture statement only through the corresponding ADR or operating authority.

- Add domain claims only after the domain admission test and appropriate expert review.

- Record a new limitation when evidence exposes it; do not wait for a marketing revision.

- Preserve the narrative history even when the architecture changes. The reason for a change is part of the
  platform's institutional memory.

The manuscript should remain one coherent read. Detailed specifications, runbooks, schemas, benchmarks and
domain profiles should stay in their own source-of-truth documents and be linked from here.
