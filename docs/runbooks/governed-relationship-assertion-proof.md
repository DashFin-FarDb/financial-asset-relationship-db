# Governed Relationship Assertion Staging Proof Runbook

## Overview

This runbook describes the staging proof workflow for Governed Relationship Assertion Contract (GRAC) v1. The workflow validates that staged deployments meet all required invariants before promotion to production.

**Workflow:** `.github/workflows/relationship-assertion-staging-proof.yml`  
**Script:** `scripts/check_relationship_assertion_proof.py`  
**Environment:** `staging-manual-gate` (requires approval)

## Security Model

### Critical Constraints

- **No credential exposure:** Database URLs, JWTs, and secrets are never printed or uploaded
- **SHA pinning:** All GitHub Actions use SHA-pinned versions
- **Least privilege:** Workflow has `contents: read` only
- **Bounded artifacts:** All outputs are size-limited and redacted
- **Fail closed:** Missing required evidence causes validation failure
- **Manual approval:** Uses `staging-manual-gate` environment protection

### What Gets Redacted

- Database connection strings (only scheme://hostname shown)
- User credentials and passwords
- JWT tokens and API keys
- Internal IP addresses and network topology
- Unrestricted evidence references

## Two Operational Modes

### Mode 1: seed_and_publish

Validates initial evidence creation, proposal/determination flow, and publication binding.

**Checks:**
- Deployed SHA matches source
- Contract and registry digests are valid
- Database URL is properly configured
- Authorization evidence exists and is current
- Proposer and determiner are distinct actors
- Exactly one publication with correct owner
- Revision hash is well-formed

**When to use:**
- Initial staging deployment
- After contract or registry updates
- When validating proposal/determination flow
- Before first production promotion

### Mode 2: verify_after_restart

Validates persistence, restart behavior, historical reconstruction, and scope continuity.

**Checks:**
- Deployed SHA matches restarted instance
- Startup source is `persisted` (when required)
- Authorization evidence is current
- Scopes match before/after restart
- Historical entries are well-formed
- Empty-edge transitions preserve established scopes
- Legacy edges do not reappear

**When to use:**
- After staging restart/redeploy
- When validating persistence behavior
- Before production promotion
- During operational drills

## Prerequisites

### Required Secrets (staging-manual-gate environment)

```yaml
DATABASE_URL: postgres://...
ASSET_GRAPH_DATABASE_URL: postgres://...
COORDINATION_DATABASE_URL: postgres://...
```

### Optional Configuration

```yaml
FARDB_UNTRUSTED_DATABASE_ROLES: "anonymous,authenticator"
FARDB_EXPOSED_DATABASE_SCHEMAS: "public"
# ... per-database schema overrides
```

## Usage

### Running seed_and_publish Mode

1. Navigate to Actions → "Governed Relationship Assertion Staging Proof"
2. Click "Run workflow"
3. Fill in parameters:
   - **mode:** `seed_and_publish`
   - **deployed_sha:** Full 40-character commit SHA
   - **contract_digest:** (optional) GRAC v1 contract SHA-256
   - **registry_digest:** (optional) GRAC v1 registry SHA-256
   - **strict_mode:** `true` (recommended)
4. Approve in staging-manual-gate environment
5. Review workflow output and artifacts

**Example:**
```yaml
mode: seed_and_publish
deployed_sha: a1b2c3d4e5f6789012345678901234567890abcd
contract_digest: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
registry_digest: cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce
strict_mode: true
```

### Running verify_after_restart Mode

1. Navigate to Actions → "Governed Relationship Assertion Staging Proof"
2. Click "Run workflow"
3. Fill in parameters:
   - **mode:** `verify_after_restart`
   - **deployed_sha:** Full 40-character commit SHA (same as deployed)
   - **require_persistence:** `true` (default)
   - **strict_mode:** `true` (recommended)
4. Approve in staging-manual-gate environment
5. Review workflow output and artifacts

**Example:**
```yaml
mode: verify_after_restart
deployed_sha: a1b2c3d4e5f6789012345678901234567890abcd
require_persistence: true
strict_mode: true
```

## Required Failure Conditions

The workflow **MUST FAIL** when:

### SHA Mismatch
- Deployed SHA format is invalid (not 40-character hex)
- Deployed SHA differs from workflow input
- Authorization evidence SHA doesn't match deployed SHA

### Authorization Failures
- Authorization evidence is missing (in strict mode)
- Evidence status is not "passed"
- PostgreSQL authorization check was skipped
- Database URL is missing or malformed

### Actor Separation Violations
- Proposer and determiner are the same identity
- Executor matches proposer or determiner
- Actor IDs are missing (in strict mode)

### Publication Errors
- Publication count is not exactly 1
- Owner identity doesn't match expected value
- Revision hash is invalid or mismatched

### Restart/Persistence Failures
- Startup source is not "persisted" (when required)
- Scopes differ before/after restart
- Historical entries are missing or malformed
- Empty-edge causes scope loss
- Legacy edges reappear after transition

### Contract Violations
- Contract or registry digest is invalid
- Digest format is wrong (not 64-character SHA-256)
- Required evidence is missing in strict mode

## Interpreting Results

### Success Output

```json
{
  "status": "passed",
  "errors": [],
  "metadata": {
    "mode": "seed_and_publish",
    "sha": "a1b2c3d4...",
    "contract": "e3b0c442...",
    "registry": "cf83e135...",
    "proposer": "user-123...",
    "determiner": "user-456...",
    "publications": 1
  }
}
```

**Interpretation:** All checks passed, deployment is ready for promotion.

### Failure Output

```json
{
  "status": "failed",
  "errors": [
    "Proposer equals determiner: user-123...",
    "Publication count 2, expected 1",
    "Authz evidence: PostgreSQL not verified"
  ],
  "metadata": {
    "mode": "seed_and_publish",
    "sha": "a1b2c3d4...",
    "proposer": "user-123...",
    "determiner": "user-123..."
  }
}
```

**Interpretation:** Multiple violations detected, deployment cannot be promoted.

## Troubleshooting

### "Database URL not configured"

**Cause:** Required database secrets are missing from staging-manual-gate environment.

**Resolution:**
1. Verify `DATABASE_URL` secret exists in GitHub environment settings
2. Check that secret value is properly formatted: `postgresql://user:pass@host/db`
3. Re-run workflow after adding secret

### "Proposer equals determiner"

**Cause:** Same actor identity used for proposal and determination.

**Resolution:**
1. Ensure distinct user accounts for proposer and determiner roles
2. Verify actor IDs are captured correctly from application logs
3. Check that determination step uses different credentials

### "Authz evidence: PostgreSQL not verified"

**Cause:** Database authorization check was skipped or incomplete.

**Resolution:**
1. Ensure all database URLs are configured (app, asset-graph, coordination)
2. Verify `scripts/check_database_authorization.py` exists at deployed SHA
3. Check database connectivity from GitHub Actions runner
4. Review database authorization closure documentation

### "Startup source N/A (need persisted)"

**Cause:** Application started from fallback/sample data instead of persisted state.

**Resolution:**
1. Verify persistence configuration is enabled in deployment
2. Check database contains persisted graph data
3. Review application startup logs for persistence errors
4. Ensure `--require-persistence` flag is appropriate for deployment state

### "Scopes changed: X -> Y"

**Cause:** Scope continuity violated across restart.

**Resolution:**
1. Check for schema migrations between captures
2. Verify persistence layer is working correctly
3. Review application logs for scope reconciliation errors
4. Ensure restart used same SHA and configuration

## Artifacts

Each run produces two artifacts:

### staging-proof-result.json

Complete validation result with:
- Status (passed/failed)
- List of all errors
- Metadata about checks performed
- Run context (SHA, run ID, timestamp)

**Retention:** 90 days  
**Size limit:** 128 KB (enforced)

### authz-evidence.json

Database authorization evidence with:
- Status (passed/failed/skipped)
- Deployed SHA binding
- PostgreSQL verification flag
- Exit code (on failure)

**Retention:** 90 days  
**Size limit:** 128 KB (enforced)

## Integration with Production Promotion

Before promoting to production:

1. Run `verify_after_restart` mode on staging
2. Verify status is "passed" with no errors
3. Download and archive artifacts
4. Reference artifact URLs in promotion issue (e.g., #1540)
5. Include SHA binding in promotion checklist

**Critical:** A skipped proof is treated as a failure, not a pass.

## Related Documentation

- [GRAC v1 Contract](../governance/governed-relationship-assertion-contract-v1.md)
- [Database Authorization Closure](./database-authorization-closure.md)
- [Release Evidence Pack](../release-evidence-pack.md)
- [Staging Deployment Operating Baseline](../staging-deployment-operating-baseline.md)

## Support

For questions or issues:
- Review workflow logs in GitHub Actions
- Check `staging-proof-result.json` artifact for detailed errors
- Consult related documentation above
- Open issue with `staging-proof` label
