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

At the reviewed source commit, produce a deterministic credential inventory by following the checklist below and completing the credential-class table.

### Inventory checklist (deterministic)

1. **Trace reads to sources (per consumer):** For each consumer (launcher, workflow, application, and any deployed copies), trace every credential/identifier read at runtime back to its source store.
   - Include: aliases, reusable workflows, fallback order, and inherited bindings.
2. **Inspect deployed consumers outside the repo:** Inspect deployed binding metadata for consumers outside the repository (a provider’s deployed copy is a consumer).
3. **Record one row per consumer:** Record **one row per consumer** with:
   - environment
   - source store and binding name
   - effective runtime key
   - evidence (non-secret)
   - update owner
   - recovery owner
   - recovery method
4. **Mark uncertainty explicitly:** Mark opaque or unresolved mappings as **unconfirmed**.
5. **Treat Stage 1 routing as a candidate:** The Stage 1 auth route is a candidate consumer path and must be evaluated like any other path (confirmed or marked unconfirmed).
6. **Apply inclusion criteria for resets:** Include a binding in the reset **only if** its **effective role** is `fardb_login_auth`.
   - A candidate path or a matching variable name alone **cannot** establish the deployed role.
   - Inventory the separately approved `fardb_login_auth_prod` principal where deployed; record its effective bindings and exclusion evidence. Do not change its verifier under this `fardb_login_auth` plan.
7. **Retain exclusions with evidence:** Exclusions remain out of scope, but retain them in the inventory with their evidence.

### Credential classes to inventory (keys, consumers, evidence, inclusion)

| Credential class                        | Keys to check (in order)                                                       | Typical consumers to enumerate                                            | Confirmation evidence required (non-secret)                                                                                      | Inclusion / exclusion criteria                                                                               |
| --------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| App/auth connection                     | `DATABASE_URL` → `POSTGRES_URL`                                                | launcher; workflow job steps; application runtime; deployed provider copy | where the effective key is read; source store + binding name; deployed env binding metadata; runtime config reference (redacted) | Include in reset **only** if effective role is `fardb_login_auth`; otherwise exclude but keep row + evidence |
| Durable graph storage (durable staging) | `ASSET_GRAPH_DATABASE_URL` (must be explicitly configured for durable staging) | application runtime; deployed provider copy                               | deployed env binding metadata showing explicit durable staging config; source store + binding name                               | Include in reset **only** if effective role is `fardb_login_auth`; otherwise exclude but keep row + evidence |
| Rebuild coordination                    | `COORDINATION_DATABASE_URL` → `DATABASE_URL` → `POSTGRES_URL`                  | launcher; workflow job steps; application runtime; deployed provider copy | where fallback resolves; deployed env binding metadata; source store + binding name                                              | Include in reset **only** if effective role is `fardb_login_auth`; otherwise exclude but keep row + evidence |
| Stage 1 auth route (candidate path)     | N/A (treat as a candidate consumer path, not a single env var)                 | any route/path that can initiate or authorize a live collection attempt   | evidence of routing/config that would cause it to consume credentials or authorize execution (redacted)                          | Must be confirmed or marked unconfirmed; include in reset only if it resolves to role `fardb_login_auth`     |

## Review and execution order

1. Generate the non-secret inventory deterministically and serialize it in a **canonical format** before hashing so that different operators produce identical bytes and the SHA-256 is reproducible:
   - **File format:** CSV text file.
   - **Encoding:** UTF-8 (no BOM).
   - **Newlines:** LF (`\n`) only.
   - **Header row:** Required, exactly once, with the **exact column order** below.
   - **Column order (exact):** `consumer,environment,source_store,binding_name,effective_runtime_key,evidence,update_owner,recovery_owner,recovery_method,confirmation_status,notes`
   - **Sorting:** Sort rows bytewise by every field in header order (missing values sort as empty string); this also breaks ties between rows sharing the same consumer and binding.
   - **Whitespace normalization:** No trailing whitespace on any line. Field values must be trimmed of leading/trailing ASCII whitespace before serialization.
   - **CSV escaping:** Use RFC 4180-style CSV rules: comma-separated; fields containing comma, quote, or newline must be double-quoted; literal quotes are escaped as `""`. Do not add extra spaces after commas.
   - **Final newline and hashing:** End the header and every data row with exactly one LF, including the final row. Compute SHA-256 over those exact UTF-8 bytes.
   Bind the resulting SHA-256 digest to the approval. The custodian confirms completeness and the ratifier approves that digest, the change window and the partial-failure recovery plan.
   The ratifier's approval is conditional on every dependent consumer being confirmed or mitigated under the approved recovery plan before the custodian changes the PostgreSQL password verifier for `fardb_login_auth` in step 3.
2. The custodian generates one replacement value and prepares all approved consumers. Obtain connection parameters from the project's Connect dialog. **Encoding rule (to prevent broken URLs during rotation):** (a) if the Connect dialog provides a complete connection URL, use that URL format as the source of truth and **do not percent-encode the full URL**; (b) if constructing a URL from discrete components, treat the password as **raw characters** and percent-encode **only the password subcomponent** for placement in the URL `userinfo` (RFC 3986), i.e., encode reserved delimiters such as `@`, `:`, `/`, `?`, `#`, `%` that would otherwise be interpreted as URL structure. **Verification step:** percent-decode the URL password subcomponent exactly once and compare it byte-for-byte with the generated raw credential in the protected environment; a literal `%` correctly encodes as `%25`. Do not print either value. While Actions is billing-locked, the custodian prepares protected local input for the step 3 updates to the scoped GitHub secret and approved consumers without activating the replacement. Local execution does not require reading an Actions secret back. Future automated distribution requires a reviewed synchronization step. When a host requires a stored runtime binding, update that copy through its deployment interface. A WSL or Supabase CLI invocation must have an explicitly identified credential source. No Supabase branch integration is required.
3. Immediately before the change, recompute the inventory SHA-256 from the exact bytes and require a match with the ratifier-approved digest. During the approved window the custodian changes the verifier and updates each confirmed consumer. Record per-consumer completion or failure with non-secret provider receipts. On partial failure, stop. The ratifier decides whether the custodian completes the approved change or restores a consistent prior state under the recovery plan. Record the role change and each consumer’s effective state, including any required redeployment. After rollback, keep Stage 1 on hold. Advance only when the ratifier accepts receipts showing the replacement is active for all dependent consumers or their approved mitigations are in effect.
4. Verify the collector, manifest, target and offline bindings. The ratifier issues a fresh one-use Stage 1 collection authorization using the complete strict schema and protected-storage requirements in the [CQ-03D procedure](database-migration-authority.md). It binds the reviewed commit and manifest digest, profile and lineage, target fingerprint, proposed marker and expected catalog digest, named operator and ratifier, approval time and expiry, initial unused state and read-only collection scope. Before issuing a replacement after an attempted run, check the prior authorization state in protected storage and revoke it under the CQ-03D procedure if it remains unused. Bind the approval to the machine-generated evidence record.
5. The authorized launcher validates the complete Stage 1 collection authorization under the CQ-03D procedure and atomically consumes it for the attempt before opening a connection. Run once and stop on failure. Submit a passing collection for catalog adjudication. Hosted preflight requires a separate preflight permit.

## Machine-generated evidence

Resolve the approved collector commit from the reviewed artifact or authenticated review record. Check it out by full commit ID. Obtain the actual ID with `git rev-parse --verify 'HEAD^{commit}'` in the collector checkout. Require an exact match before use and verify the tracked collector inputs are clean. For Actions, bind the reviewed workflow revision to the approval and verify the executing revision before releasing secrets to the job. A workflow run ID or a pull request merge ref alone cannot identify the reviewed collector.

Capture the collector CLI's complete stdout report only in protected operator storage: it contains the target fingerprint and catalog digests. Do not send it to workflow logs or a public artifact. Generate a separate allowlisted, redacted receipt from the launcher's verified values. Include only repository, collector commit, non-sensitive target label, inventory digest, non-sensitive approval reference, stage, outcome and the run identifiers below. Local runs add the launcher revision and a unique local attempt identifier and retain the receipt with the project evidence. Actions runs add the workflow revision, run ID and attempt and publish only the redacted receipt as a run artifact. Link only the redacted receipt from the issue. Keep the authorization, target binding, connection inputs and full collection report in protected operator storage. Never upload, log or link those records, raw provider output, the target fingerprint or catalog digests. Keep passwords, connection strings, verifier material and hashes of secret values out of receipts. Test mismatched commits, changed inventory, wrong target and consumed authorizations offline before enabling live execution.

## Merge verification during the billing lock

For this runbook PR, record the verified head, changed paths, substitute checks and results, and identify any required Actions check skipped specifically because of billing. Reference a dated project-owner approval outside this runbook before applying any exception, and identify the exact checks it covers in the PR. Review requirements, actual check failures and operational permits retain their usual effect. Revisit automated CI/CD after Actions billing is restored.
