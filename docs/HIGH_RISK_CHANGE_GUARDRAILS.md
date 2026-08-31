# High-Risk Change Guardrails

This document is the canonical source for low-autonomy implementation contracts and scanner scope in FarDb. It
consolidates requirements previously repeated across the AI agent and automation policies without changing their
authority or meaning.

## Governance and Compliance review boundary

Governance and Compliance (GNC) review never authorizes an agent to widen a task. Agents responding to GNC findings
must validate each claim against the current head and record one disposition: `resolved`, `deferred_out_of_scope`,
`rejected_speculative`, `duplicate_of`, `waived`, or `reopened_as_recurrence`. Out-of-scope findings require a
follow-up issue or explicit human decision; they are not silently implemented.

GNC policy, contract, evaluator, and skill changes cannot approve or waive themselves. A model-origin finding is
advisory unless it maps to a human-confirmed or deterministic blocking basis. Evidence satisfies a mandatory
requirement only when it was executed successfully for the exact head SHA and target. A skipped, canceled,
unavailable, `stale_sha`, or `wrong_target` check fails closed for that requirement.

Database, authentication, deployment, CI/CD, security scanner configuration, persistence, migration, and recovery
work require low-autonomy, file-bounded implementation contracts.

## Low-autonomy areas

The following areas have complex failure modes and require explicit, file-bounded implementation contracts before
implementation:

- database schema, connections, drivers, pooling
- authentication and authorization
- deployment, hosting, and containerization
- CI/CD pipelines and workflow configuration
- security scanner configuration (CodeQL, DeepSource, Snyk, Codacy, Trivy)
- persistence and storage backends
- environment-variable precedence and configuration loading
- migrations (schema, data, or auth)
- recovery and restore procedures
- connection pooling and async/sync driver selection

## Required implementation contract

The task must specify:

1. **Allowed files**: exact list of files that may be modified
2. **Forbidden files**: explicit list of files that must not be touched
3. **Exact targets**: specific functions, classes, or configuration keys to modify
4. **Exact non-targets**: functions, classes, or configuration keys that must not be modified
5. **Fixed decisions**: implementation choices already decided
6. **Tests to add/update**: specific test files or test cases required
7. **Validation commands**: commands to verify correctness
8. **Stop conditions**: when to stop and report instead of continuing

## Stop and report conditions

Stop implementation and report if the change appears to require:

- an architectural decision not already documented
- a new file outside the allowed-files list
- suppression of security scanner findings
- changes to dependencies (`requirements.txt`, `package.json`, or equivalent)
- touching a forbidden file
- choosing between technical alternatives such as drivers, pools, auth flows, or migration strategies

## Scanner configuration and finding rules

Security scanners may automatically:

1. Report vulnerabilities in production and non-production code.
2. Suggest version bumps for vulnerable dependencies.
3. Flag insecure code patterns.

Security scanners must not automatically:

1. Refactor large code sections to fix vulnerabilities without review.
2. Remove features to eliminate security surface without approval.
3. Change authentication or authorization models.
4. Modify API contracts to fix security issues.

Automated security and quality scanners must:

1. Focus primary analysis on the production FastAPI and Next.js architecture.
2. Clearly distinguish production findings from non-production findings.
3. Not auto-enable analysis for unused language ecosystems or package managers.
4. Not use broad auto-detection flags such as `--all-projects` without explicit documentation of intended scope.
5. Respect the documented dependency source-of-truth hierarchy.

Scanners must not:

1. Expand a PR from fixing one vulnerability to fixing all findings without approval.
2. Fail CI solely because of findings in non-production code paths.
3. Drive architecture or implementation decisions merely to satisfy scanner rules.
4. Override the documented dependency source of truth based on scanner assumptions.

Do not suppress scanner findings globally. Do not edit scanner configuration files (`.deepsource.toml`,
`.github/workflows/codeql.yml`, `.snyk`, `codacy-config.yml`, or equivalent) unless each exact file is listed in the
allowed-files list. Prefer fixing the specific code, test, or example causing the finding.

If a finding is believed to be a false positive:

1. Explain why it is a false positive.
2. Request a human decision before adding suppression.
3. If approved, add an inline suppression with a comment explaining the justification.

If a scanner identifies an issue in non-production code such as the Gradio UI, demo scripts, or test utilities,
report it with production context, prioritize production issues, and do not widen an existing PR or automatically
create a repair PR for the non-production finding.

Scanner noise (false positives, low-priority warnings, non-production findings) should not block PRs or drive scope
expansion.

## Artifact creation rules

Do not create root-level files unless explicitly requested:

- no `PR_DESCRIPTION.md`; PR summaries belong in the GitHub PR body
- no audit summaries, scratch scripts, or manual test scripts
- no new tracking documents or report files

## Scope control rules

When working in high-risk areas:

- No opportunistic cleanup of adjacent code.
- No refactoring unrelated to the stated objective.
- No dependency upgrades except explicitly named ones.
- No changes to graph logic, frontend, CI, or documentation unless each file is in the allowed-files list.

## Database, authentication, and deployment decisions

Do not choose between technical alternatives during implementation, including:

- SQLite vs PostgreSQL
- sync vs async database drivers
- migration tool selection (Alembic, sqlalchemy-migrate, custom scripts)
- connection pooling strategies
- environment-variable precedence order when multiple configuration sources exist

These decisions must be fixed before coding begins. If the task contract does not specify a required choice, stop and
ask for the decision.

## Origin and continuing application

PR #1096, which added PostgreSQL support for the API authentication database, demonstrated the risk of autonomous
implementation across database boundaries. It initially drifted into connection pooling, asynchronous driver
selection, and environment-variable precedence without explicit contracts. Future database, authentication,
deployment, CI, scanner, persistence, migration, and recovery work must therefore keep the file-bounded contract and
stop conditions above.
