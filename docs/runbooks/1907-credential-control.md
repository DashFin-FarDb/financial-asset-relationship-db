# FarDb staging and hosting credential control

Proposed for review under [#1907](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1907) (canonical tracking issue for review/approvals and links to redacted execution receipts). Adoption requires review and verification. This document records a procedure and grants no live permit.

## Definitions

- **Custodian**: The operator responsible for preparing and executing credential rotations/updates, producing the inventory and non-secret evidence, and stopping execution on partial failure to follow the approved recovery method.
- **Ratifier**: The reviewer/approver responsible for verifying the inventory digest and change plan, authorizing the change window, and issuing the Stage 1 collection authorization and the later hosted preflight permit.
- **Authorized launcher**: The operator permitted to initiate a live connection/collection run using a Stage 1 collection authorization, after checking it matches the exact checkout/commit and target.
- **Stage 1 collection authorization**: The protected, one-use [CQ-03D collection authorization](database-migration-authority.md) described in step 4. Each retry requires fresh authorization.

## Authority and inventory

Use the following checklist when deciding where credentials and identifiers live and how they are resolved at runtime:

1. **Distribution point:** GitHub Actions holds workflow inputs. The hosted backend reads private variables from its target Vercel environment. Each rotation affecting Vercel requires a reviewed update to that environment and a redeployment of the affected service.
2. **Classification (secret vs variable):**
   - Place sensitive inputs in Actions secrets.
   - Place public target identifiers in Actions variables.
3. **Scoping:** Scope secrets/variables to the target environment where available.
4. **Precedence/resolve collisions:** If the same binding name exists at repository, environment, and organization scope, inventory all same-named bindings and establish which one the job receives.
5. **Downstream consumers:** A provider's deployed copy is a downstream consumer.
6. **Exclusions:** Personal variable collections are outside the deployment path.

At the reviewed source commit, trace every credential read from launcher, workflow and application to its source. Include aliases, reusable workflows, fallback order and inherited bindings. Inspect deployed binding metadata for consumers outside the repository. Record one row per consumer with environment, source store and binding name, effective runtime key, evidence, update owner, recovery owner and recovery method. Mark opaque or unresolved mappings as unconfirmed. The Stage 1 auth route is a candidate. Inventory app/auth (`DATABASE_URL`, then `POSTGRES_URL`), durable graph storage (`ASSET_GRAPH_DATABASE_URL`, explicitly configured for durable staging), and rebuild coordination (`COORDINATION_DATABASE_URL`, then `DATABASE_URL`, then `POSTGRES_URL`). Include a binding in the reset only if its effective role is `fardb_login_auth`. A candidate or a matching variable name alone cannot establish the deployed role. Retain exclusions with their evidence.

## Review and execution order

1. Generate the non-secret inventory deterministically in consumer/environment order. Bind its exact bytes to a SHA-256 digest. The custodian confirms completeness and the ratifier approves that digest, the change window and the partial-failure recovery plan.
   The ratifier's approval is conditional on every dependent consumer being confirmed or mitigated under the approved recovery plan before the custodian changes the PostgreSQL password verifier for `fardb_login_auth` in step 3.
2. The custodian generates one replacement value and prepares all approved consumers. Obtain connection parameters from the project's Connect dialog and encode the password component once when constructing a URL. While Actions is billing-locked, the custodian prepares protected local input for the step 3 updates to the scoped GitHub secret and approved consumers without activating the replacement. Local execution does not require reading an Actions secret back. Future automated distribution requires a reviewed synchronization step. When a host requires a stored runtime binding, update that copy through its deployment interface. A WSL or Supabase CLI invocation must have an explicitly identified credential source. No Supabase branch integration is required.
3. During the approved window the custodian changes the verifier and updates each confirmed consumer. Record per-consumer completion or failure with non-secret provider receipts. On partial failure, stop. The ratifier decides whether the custodian completes the approved change or restores a consistent prior state under the recovery plan. Record the role change and each consumer’s effective state, including any required redeployment. After rollback, keep Stage 1 on hold. Advance only when the ratifier accepts receipts showing the replacement is active for all dependent consumers or their approved mitigations are in effect.
4. Verify the collector, manifest, target and offline bindings. The ratifier issues a fresh one-use Stage 1 collection authorization using the complete strict schema and protected-storage requirements in the [CQ-03D procedure](database-migration-authority.md). It binds the reviewed commit and manifest digest, profile and lineage, target fingerprint, proposed marker and expected catalog digest, named operator and ratifier, approval time and expiry, initial unused state and read-only collection scope. The previous attempt's authorization is consumed. Bind the approval to the machine-generated evidence record.
5. The authorized launcher validates the complete Stage 1 collection authorization under the CQ-03D procedure and atomically consumes it for the attempt before opening a connection. Run once and stop on failure. Submit a passing collection for catalog adjudication. Hosted preflight requires a separate preflight permit.

## Machine-generated evidence

Resolve the approved collector commit from the reviewed artifact or authenticated review record. Check it out by full commit ID. Obtain the actual ID with `git rev-parse --verify 'HEAD^{commit}'` in the collector checkout. Require an exact match before use and verify the tracked collector inputs are clean. For Actions, bind the reviewed workflow revision to the approval and verify the executing revision before releasing secrets to the job. A workflow run ID or a pull request merge ref alone cannot identify the reviewed collector.

Generate a separate redacted receipt from the launcher’s verified values. Include only repository, collector commit, non-sensitive target label, inventory digest, non-sensitive approval reference, stage, outcome and the run identifiers below. Local runs add the launcher revision and a unique local attempt identifier and retain the receipt with the project evidence. Actions runs add the workflow revision, run ID and attempt and publish the receipt as a run artifact. Link only the redacted receipt from the issue. Keep the authorization, target binding, connection inputs and full collection report in protected operator storage. Never upload, log or link those records, raw provider output, the target fingerprint or catalog digests. Keep passwords, connection strings, verifier material and hashes of secret values out of receipts. Test mismatched commits, changed inventory, wrong target and consumed authorizations offline before enabling live execution.

## Merge verification during the billing lock

For this runbook PR, record the verified head, changed paths, substitute checks and results, and identify any required Actions check skipped specifically because of billing. Reference a dated project-owner approval outside this runbook before applying any exception, and identify the exact checks it covers in the PR. Review requirements, actual check failures and operational permits retain their usual effect. Revisit automated CI/CD after Actions billing is restored.
