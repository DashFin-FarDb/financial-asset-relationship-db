# FarDb staging and hosting credential control

Proposed for review under [#1907](/issues/1907) (canonical tracking issue for review/approvals and links to execution evidence). Adoption requires review and verification. This document records a procedure and grants no live permit.

## Definitions

- **Custodian**: The operator responsible for preparing and executing credential rotations/updates, producing the inventory and non-secret evidence, and stopping execution on partial failure to follow the approved recovery method.
- **Ratifier**: The reviewer/approver responsible for verifying the inventory digest and change plan, authorizing the change window, and issuing the one-use permit(s) described below.
- **Authorized launcher**: The operator permitted to initiate a live connection/collection run using an issued permit, after checking the permit matches the exact checkout/commit and target.
- **Permit (Stage 1 permit)**: A one-use approval token issued by the ratifier for a specific collector commit and target. It is consumed by a single live attempt; a new permit is required for retries or for hosted preflight as noted below.

## Authority and inventory

Use GitHub Actions as the default distribution point for staging and hosted deployments until an explicitly reviewed change supersedes this procedure. Place sensitive inputs in Actions secrets and public target identifiers in Actions variables. Scope them to the target environment where available. Inventory same-named repository, environment and organization bindings and establish which one the job receives. A provider's deployed copy is a downstream consumer. Personal variable collections are outside the deployment path.

At the reviewed source commit, trace every credential read from launcher, workflow and application to its source. Include aliases, reusable workflows, fallback order and inherited bindings. Inspect deployed binding metadata for consumers outside the repository. Record one row per consumer with environment, source store and binding name, effective runtime key, evidence, update owner, recovery owner and recovery method. Mark opaque or unresolved mappings as unconfirmed. The Stage 1 auth route is a candidate. The hosted API accepts DATABASE_URL or POSTGRES_URL. A candidate or a matching variable name alone cannot establish the deployed role. Retain exclusions with their evidence.

## Review and execution order

1. Generate the non-secret inventory deterministically in consumer/environment order. Bind its exact bytes to a SHA-256 digest. The custodian confirms completeness and the ratifier approves that digest, the change window and the partial-failure recovery plan.
2. The custodian generates one replacement value and prepares all approved consumers. Obtain connection parameters from the project's Connect dialog and encode the password component once when constructing a URL. While Actions is billing-locked, the custodian supplies the same newly generated value to the scoped GitHub secret and approved consumers during the change window using protected local input. Local execution does not require reading an Actions secret back. After service resumes, a reviewed protected job can distribute the GitHub binding. When a host requires a stored runtime binding, update that copy through its deployment interface. A WSL or Supabase CLI invocation must have an explicitly identified credential source. No Supabase branch integration is required.
3. During the approved window the custodian changes the verifier and updates each confirmed consumer. Record per-consumer completion or failure with non-secret provider receipts. On a partial update, stop and invoke the approved recovery method. Record the resulting state before proceeding.
4. Verify the collector, manifest, target and offline bindings. The ratifier issues a fresh one-use Stage 1 permit for the exact collector commit and target. The previous attempt's permit is consumed. Bind the approval to the machine-generated evidence record.
5. The authorized launcher checks the permit against the checkout and target before opening a connection. Run once and stop on failure. Submit a passing collection for catalog adjudication. Hosted preflight requires a separate permit.

## Machine-generated evidence

Resolve the approved collector commit from the reviewed artifact or authenticated review record. Check it out by full commit ID. Obtain the actual ID with `git rev-parse --verify 'HEAD^{commit}'` in the collector checkout. Require an exact match before use and verify the tracked collector inputs are clean. Record the workflow revision separately if the workflow and collector come from different commits. A workflow run ID or a pull request merge ref alone cannot identify the reviewed collector.

Generate the receipt once from the executing launcher’s verified values. For local runs, record the launcher revision and local attempt identifier in place of workflow metadata and retain the receipt with the project evidence. For Actions runs, use the workflow fields below. Include repository, collector commit, workflow revision, target, inventory digest, approval reference, run ID and attempt, stage and outcome. For an Actions run, publish the same receipt as a run artifact and link to it from the issue. Keep passwords, connection strings, verifier material and hashes of secret values out of receipts. Test mismatched commits, changed inventory, wrong target and consumed permits offline before enabling live execution.

## Merge verification during the billing lock

For this runbook PR, record the verified head, changed paths, substitute checks and results, and identify any required Actions check skipped specifically because of billing. The project owner authorizes bypass of those billing-blocked checks once the PR is otherwise ready. Review requirements, actual check failures and operational permits retain their usual effect. Revisit automated CI/CD after Actions billing is restored.
