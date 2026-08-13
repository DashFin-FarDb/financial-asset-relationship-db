# Governed Relationship Assertion v1 Evidence Template

**Purpose:** Record staging proof evidence for GRAC v1 deployments
**Workflow:** `.github/workflows/relationship-assertion-staging-proof.yml`
**Created:** [YYYY-MM-DD]
**Deployment SHA:** `[40-character Git SHA]`
**Evidence ID:** `[grac-v1-YYYYMMDD-NNNN]`

---

## Executive Summary

| Attribute         | Value                                   |
| ----------------- | --------------------------------------- |
| **Status**        | ✓ PASS / ✗ FAIL                         |
| **Mode**          | seed_and_publish / verify_after_restart |
| **Deployed SHA**  | `[SHA]`                                 |
| **Run ID**        | [GitHub Actions run ID]                 |
| **Run Number**    | [GitHub Actions run number]             |
| **Evidence Date** | [YYYY-MM-DD HH:MM UTC]                  |
| **Operator**      | [@github-username]                      |

---

## Deployment Context

### Source Verification

- **Git commit SHA:** `[full 40-character SHA]`
- **Branch:** [branch name, e.g., `main`]
- **Merge ancestor:** ✓ Verified / ⚠ Warning / ✗ Failed
- **Workflow SHA:** `[SHA of workflow source]`

### Contract Binding

- **GRAC v1 contract digest:** `[SHA-256, if validated]`
- **Registry digest:** `[SHA-256, if validated]`
- **Contract version:** v1
- **Transitions frozen:** [Yes/No]

### Database Configuration

- **Database configured:** ✓ Yes / ✗ No
- **Database URL (redacted):** `postgresql://[hostname]/***`
- **Asset graph DB configured:** ✓ Yes / ✗ No
- **Coordination DB configured:** ✓ Yes / ✗ No

---

## Authorization Evidence

### Database Authorization Check

| Check                      | Status                | Details                     |
| -------------------------- | --------------------- | --------------------------- |
| **Schema authorization**   | PASS / FAIL / SKIPPED | [Details]                   |
| **PostgreSQL verified**    | ✓ Yes / ✗ No          | Required for proof validity |
| **Public schema locked**   | ✓ Yes / ✗ No / N/A    | ADR-0007 compliance         |
| **Untrusted roles denied** | ✓ Yes / ✗ No / N/A    | Function execute revoked    |
| **Evidence SHA binding**   | `[SHA]`               | Must match deployed SHA     |

**Authz evidence artifact:** `authz-evidence.json`
**Authz workflow:** [Link to check_database_authorization.py run]

---

## Mode-Specific Evidence

### For seed_and_publish Mode

#### Actor Separation

| Role                      | Identity (redacted)         | Status              |
| ------------------------- | --------------------------- | ------------------- |
| **Proposer**              | `[ID first 8 chars]...`     | [Status]            |
| **Determiner**            | `[ID first 8 chars]...`     | [Status]            |
| **Executor**              | `[ID first 8 chars]...`     | [Status if present] |
| **Distinctness verified** | ✓ All distinct / ✗ Conflict | Required            |

#### Publication Binding

| Attribute                | Value                      | Status    |
| ------------------------ | -------------------------- | --------- |
| **Publication count**    | [number]                   | Must be 1 |
| **Owner identity**       | `[ID first 8 chars]...`    | [Status]  |
| **Expected owner match** | ✓ Match / ✗ Mismatch / N/A | [Details] |
| **Revision hash**        | `[SHA-256 first 8]...`     | [Status]  |

#### Evidence Artifacts

- Proposal evidence: `[artifact reference]`
- Determination evidence: `[artifact reference]`
- Publication metadata: `[artifact reference]`
- Redacted outputs captured: ✓ Yes / ✗ No

### For verify_after_restart Mode

#### Persistence Proof

| Check                   | Value                         | Status                |
| ----------------------- | ----------------------------- | --------------------- |
| **Startup source**      | persisted / fallback / sample | [Required: persisted] |
| **Persistence enabled** | ✓ Yes / ✗ No                  | [Status]              |
| **Persistence loaded**  | ✓ Yes / ✗ No                  | [Status]              |
| **Graph initialized**   | ✓ Yes / ✗ No                  | [Status]              |

#### Scope Continuity

| Transition       | Before     | After      | Status                  |
| ---------------- | ---------- | ---------- | ----------------------- |
| **Restart**      | [N scopes] | [N scopes] | ✓ Match / ✗ Changed     |
| **Empty-edge**   | [N scopes] | [N scopes] | ✓ Preserved / ✗ Lost    |
| **Legacy edges** | N/A        | [Status]   | ✓ Absent / ✗ Reappeared |

**Scope details:** [Redacted scope identifiers if available]

#### Historical Reconstruction

| Attribute                 | Value                     | Status     |
| ------------------------- | ------------------------- | ---------- |
| **History entries**       | [count]                   | Minimum: 1 |
| **Known_at present**      | ✓ All / ✗ Missing         | [Details]  |
| **State transitions**     | [count]                   | [Status]   |
| **Actor provenance**      | ✓ Complete / ✗ Incomplete | [Details]  |
| **Predecessor/successor** | [Status]                  | [Details]  |

---

## Validation Results

### All Checks

| Check             | Result                | Errors        |
| ----------------- | --------------------- | ------------- |
| SHA format        | ✓ PASS / ✗ FAIL       | [List if any] |
| Contract/registry | ✓ PASS / ✗ FAIL       | [List if any] |
| Database config   | ✓ PASS / ✗ FAIL       | [List if any] |
| Authorization     | ✓ PASS / ✗ FAIL       | [List if any] |
| Actor separation  | ✓ PASS / ✗ FAIL / N/A | [List if any] |
| Publication       | ✓ PASS / ✗ FAIL / N/A | [List if any] |
| Persistence       | ✓ PASS / ✗ FAIL / N/A | [List if any] |
| Scope continuity  | ✓ PASS / ✗ FAIL / N/A | [List if any] |
| Historical        | ✓ PASS / ✗ FAIL / N/A | [List if any] |

### Summary

**Total errors:** [count]
**Critical failures:** [count]
**Warnings:** [count]
**Overall status:** ✓ PASS / ✗ FAIL

---

## Artifacts

| Artifact           | Location                    | Size    | SHA-256    |
| ------------------ | --------------------------- | ------- | ---------- |
| **Proof result**   | `staging-proof-result.json` | [bytes] | `[digest]` |
| **Authz evidence** | `authz-evidence.json`       | [bytes] | `[digest]` |
| **Workflow logs**  | [GitHub Actions link]       | [size]  | N/A        |

**Artifact retention:** 90 days from run date
**Download instructions:** See workflow artifacts tab

---

## Promotion Readiness

- [ ] All required checks passed
- [ ] No critical errors present
- [ ] Authorization evidence current
- [ ] SHA binding verified
- [ ] Artifacts archived
- [ ] Evidence reviewed by: [@reviewer-username]

**Promotion decision:** READY / BLOCKED
**Blocking issues:** [List if any, or "None"]

---

**Template version:** 1.0
**Last updated:** 2024-01-XX
