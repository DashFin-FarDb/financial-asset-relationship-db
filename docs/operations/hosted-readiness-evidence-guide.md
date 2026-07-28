# Hosted Readiness Evidence Guide

**Status:** Active
**Scope:** Hosted readiness evidence capture for release-candidate and staging/production promotion decisions.

## Purpose

This guide is the single entrypoint for hosted readiness evidence. It consolidates the capture, classification,
redaction, and linking rules that are otherwise distributed across the release evidence pack, the staging baseline,
and the operational evidence-capture framework.

The guide does not replace those authoritative documents. It points to them so operators can follow one path without
duplicating the full rule set.

## What Hosted Readiness Proves

Hosted readiness can prove that:

- a named hosted target responded to the readiness checks;
- durable persistence was required during the check;
- nested graph fields reported persisted startup;
- bounded asset smoke succeeded, or approved sentinel evidence exists.

## What Hosted Readiness Does Not Prove

Hosted readiness does not prove that:

- another environment is safe;
- CI success equals hosted proof;
- database reachability equals graph persistence proof;
- documentation existence equals operator evidence;
- preview evidence is valid for staging/production unless it is labelled durable and explicitly approved.

## Required Evidence Inputs

Before attaching hosted readiness evidence, collect:

- the target label or deployment label;
- the durability label for the environment;
- the command output for the readiness check and the bounded endpoints;
- the nested fields observed in `/api/health/detailed`;
- the redaction confirmation for any issue or PR attachment.

## Required Commands

Use the canonical readiness commands below:

```bash
python scripts/check_hosted_readiness.py <base_url> --require-persistence
curl -fsS "<base_url>/api/health/detailed"
curl -fsS "<base_url>/api/assets?per_page=1"
```

Use `--timeout 30` (or higher) when the target is a Vercel Python deployment that may cold-start.
The script default is 30 seconds; promotion workflows also pass `--timeout 30` explicitly.

If JSON output is available and preferred for release evidence capture, use:

```bash
python scripts/check_hosted_readiness.py <base_url> --require-persistence --json --base-url-label <operator-safe-label>
```

## Post-Rollback / Post-Restore Re-Smoke (H-P1-03)

After a staging or production rollback, or after a restore rehearsal, do **not** rely on the thin
`hosted-readiness.yml` skip path. Dispatch `.github/workflows/post-recovery-readiness.yml` with:

- `recovery_context`: `post-rollback` or `post-restore`
- `target_environment`: `staging` or `production`
- `base_url`: scratch/restored target when it differs from the Environment secret

The workflow always runs `--json --require-persistence` (assets-smoke via H-P1-01), asserts durable
graph fields, and uploads a context-named artifact:

- `post-rollback-readiness`
- `post-restore-readiness`

Each artifact includes `readiness-output.json` and `recovery-metadata.json` (`hardening_id: H-P1-03`).
Attach the workflow run and artifact to the incident or restore evidence record before closing.

## Required Field Paths

When `/api/health/detailed` returns JSON, capture the exact nested graph persistence fields:

- `graph_persistence_configured == true`
- `graph.persistence_enabled == true`
- `graph.persistence_loaded == true`
- `graph.startup_source == "persisted"`

## Durable Graph Proof Rule

All four required fields together constitute durable graph proof. No single field is sufficient on its own.

Refer to the [Operational Evidence Capture Framework](operational-evidence-capture-framework.md) for the canonical
evidence object grammar and false-positive controls.

Refer to [ADR 0002: Hosted Deployment and Persistence](../adr/0002-hosted-deployment-and-persistence.md) and
[ADR 0004: Distributed Hosting Semantics](../adr/0004-distributed-hosting-semantics.md) for the hosted and
distributed-persistence assumptions that make durable proof meaningful.

## Staging Boundary Evidence

Record the staging provider and boundary labels explicitly:

- `DATABASE_URL`
- `ASSET_GRAPH_DATABASE_URL`
- `COORDINATION_DATABASE_URL`

Use the [Staging Deployment Operating Baseline](../staging-deployment-operating-baseline.md) for the full boundary
table, Vercel mapping, and promotion checklist.

## Preview Durability Labels

Preview evidence must be labelled as either `durable` or `non-durable`.

- `durable`: preview evidence that uses authoritative durable boundaries and is approved for the claim being made.
- `non-durable`: preview evidence that may prove shape or smoke behavior, but not staging or production durable graph
  truth.

Non-durable preview evidence cannot satisfy staging or production promotion proof.

## Asset Smoke Evidence

The bounded asset smoke is the operator-safe `/api/assets?per_page=1` check. It should be attached alongside the
durable readiness evidence so the record shows that the target is not only healthy, but also returning bounded graph
evidence.

If an approved sentinel baseline is used instead of a live asset row, record that explicitly.

## Restart / Redeploy Evidence

Hosted readiness should make the graph startup source explicit so operators can distinguish persistence from cache or
sample-state startup.

Use the [Enterprise Release Checklist](../release-checklist.md) and the distributed hosting ADRs to classify restart
and redeploy evidence correctly.

## Redaction Rules

Do not include:

- raw URLs;
- credentials;
- bearer tokens;
- private keys;
- full graph dumps;
- raw exception traces.

Preserve:

- field names;
- booleans;
- counts;
- status labels;
- timestamps;
- environment labels;
- boundary labels.

Use `--base-url-label` when you need an operator-safe label for JSON output.

Refer to the [Operational Evidence Capture Framework](operational-evidence-capture-framework.md) for the full redaction
policy and false-positive controls.

## Evidence Attachment Checklist

Use this structure when attaching evidence to an RC record or issue:

- Evidence ID
- Release candidate / commit SHA
- Environment
- Target URL or deployment label
- Durability label
- Database boundary labels
- Command
- Expected result
- Actual result
- Observed fields
- Assets smoke result
- Redaction performed
- Result
- Follow-up issue
- Reviewer

## How to Link Evidence into RC Issues

Attach or link the hosted evidence inside the release-candidate evidence issue created from
[`.github/ISSUE_TEMPLATE/release_candidate_evidence.md`](../../.github/ISSUE_TEMPLATE/release_candidate_evidence.md).

Use the release-candidate issue for the operator-facing evidence record, and keep this guide as the shared reference
for what should be captured and how it should be classified.

If the RC also maintains a committed companion record, cross-link that file from both the release-candidate issue and
the release evidence pack so reviewers can move between the live ledger and the durable archive without re-deriving
the evidence structure.

## Failure Classification

- `Passed`: the evidence object includes the required fields and the check meets the durable proof rule.
- `Failed`: the check or attached smoke evidence shows the target did not meet the claim.
- `Blocked`: the operator cannot obtain the required evidence from the target or cannot prove the claim safely.
- `Follow-up required`: partial evidence exists, but a linked issue or missing artifact must be resolved before the
  claim is release-grade.

## Related Documents

- [Release Evidence Pack](../release-evidence-pack.md)
- [Staging Deployment Operating Baseline](../staging-deployment-operating-baseline.md)
- [Operational Evidence Capture Framework](operational-evidence-capture-framework.md)
- [Enterprise Release Checklist](../release-checklist.md)
- [Backup, Restore, and DR Runbook](../runbooks/backup-restore-dr.md)
- [Release candidate evidence capture template](../../.github/ISSUE_TEMPLATE/release_candidate_evidence.md)
- [RC1 / Objective 2 follow-up evidence record](../evidence-records/rc1-objective-2-follow-up.md)
- [ADR 0002: Hosted Deployment and Persistence](../adr/0002-hosted-deployment-and-persistence.md)
- [ADR 0003: Distributed Lock Refresh and Heartbeat Strategy](../adr/0003-distributed-lock-refresh-and-heartbeat-strategy.md)
- [ADR 0004: Distributed Hosting Semantics](../adr/0004-distributed-hosting-semantics.md)
- [ADR 0005: Backup, Restore, and Disaster Recovery Strategy](../adr/0005-backup-restore-dr-strategy.md)
