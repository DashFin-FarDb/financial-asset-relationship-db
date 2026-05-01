# AI Agent Guardrails

This file exists to reduce agent drift in review-driven PRs.

## Repository rule

`requirements.txt` is the source of truth for runtime dependencies.

AI agents must treat all other dependency-related files as supporting files:

- `pyproject.toml` mirrors the runtime install surface
- `requirements-dev.txt` adds dev/test/tooling intent
- tests/workflows/docs validate or describe the model

They do not overrule `requirements.txt`.

## Mandatory reasoning order for dependency work

Before changing files, state internally:

1. what the runtime policy is
2. which file is authoritative
3. which files are mirrors
4. which files are validators

If that model is not clear, stop and narrow the task.

## Hard rules

- Do not let the latest review comment become the new architecture.
- Do not change dependency policy just to satisfy a failing validator.
- If a validator conflicts with the documented model, update the validator.
- Do not combine dependency alignment and framework upgrade work unless explicitly asked.
- Do not describe files as "aligned" if they still resolve materially different runtime surfaces.
- Do not broaden PR scope with unrelated cleanup.

## Preferred PR split

### Dependency alignment PR

Allowed files:

- `requirements.txt`
- `pyproject.toml`
- `requirements-dev.txt`
- dependency-related GitHub Actions workflows (for example, `.github/workflows/ci.yml`, `.github/workflows/dependency-review.yml`, or other dependency-focused workflow files present in this repository)
- dependency-related tests
- dependency policy docs

### Validator follow-up PR

Allowed files:

- tests
- workflows
- docs

Rule:

- if a follow-up only exists because validators lag the policy, keep dependency file edits out of that PR unless unavoidable

## Stop conditions

Open a follow-up PR instead of continuing when:

- a second architectural decision appears mid-task
- a security/framework upgrade becomes mixed with alignment work
- the PR now needs to justify why many unrelated files changed
- review comments are pulling the work in conflicting directions

## Validation expectations

For dependency-related changes, the PR should report the relevant commands that were actually run, not generic placeholders.

## Regex safety (Sonar S5852 / ReDoS)

**Hard rule: do not use `re.DOTALL` together with lazy or greedy quantifiers (`.*`, `.*?`, `.+`, `.+?`) in a single pattern that spans unbounded input.**

Such patterns are vulnerable to polynomial or exponential backtracking (ReDoS) and will be flagged by Sonar S5852 and Bandit.

### Preferred alternatives

| Instead of…                                                            | Use…                                                                                                                                                                                             |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `re.search(r"header.*?body", text, re.DOTALL)`                         | `str.find("header")` to locate the start, then slice, then match `[^\]]*` or similar on the bounded slice                                                                                        |
| `re.search(r"\[section\].*?\[key\]\s*=\s*\[(.*?)\]", text, re.DOTALL)` | Split on the section header with `str.find()`, trim to the next `[` header with a `re.search(r"^\[", …, re.MULTILINE)`, then run a simple character-class pattern (`[^\]]*`) on the bounded text |
| Any `.*` / `.*?` with `re.DOTALL` across a whole file                  | Use `splitlines()` + state-machine iteration, or a proper TOML/JSON/YAML parser                                                                                                                  |

### When `re.DOTALL` may be used

Only when **all three** conditions hold:

1. The input is provably short and bounded (e.g., a single line pulled from a known small config value, not a whole file).
2. There is no ambiguity in the terminator — the pattern cannot match the terminator character inside the content (use a negated character class instead of `.`).
3. The use is accompanied by an inline comment explaining why `re.DOTALL` is safe in that specific context.

### Origin of this rule

`re.DOTALL` + `.*?` spanning a whole file was used in `tests/integration/test_pyproject_dev_deps.py` (PR #1022, commit 6c94b98) and flagged as a ReDoS risk (Sonar S5852). It was replaced with a `str.find()` + bounded `[^\]]*` approach in commit b97073c. Do not reintroduce the broad-dotall pattern.

---

## High-risk change control

Database, authentication, deployment, CI/CD, security scanner configuration, persistence, and migration work require low-autonomy, file-bounded implementation contracts.

### Low-autonomy areas

The following areas have complex failure modes and require explicit boundaries before implementation:

- database schema, connections, drivers, pooling
- authentication and authorization
- deployment, hosting, and containerization
- CI/CD pipelines and workflow configuration
- security scanner configuration (CodeQL, DeepSource, Snyk, Codacy, Trivy)
- persistence and storage backends
- environment-variable precedence and configuration loading
- migrations (schema, data, or auth)
- connection pooling and async/sync driver selection

### Required prompt contract

When working in low-autonomy areas, the prompt must specify:

1. **Allowed files**: Exact list of files that may be modified
2. **Forbidden files**: Explicit list of files that must not be touched
3. **Exact targets**: Specific functions, classes, or config keys to modify
4. **Exact non-targets**: Functions, classes, or config keys that must not be modified
5. **Fixed decisions**: Implementation choices already decided (e.g., SQLite vs PostgreSQL, sync vs async, migration tool, env-var precedence order)
6. **Tests to add/update**: Specific test files or test cases required
7. **Validation commands**: Commands to verify correctness
8. **Stop conditions**: When to stop and report instead of continuing

### Stop and report conditions

Stop implementation and report (do not continue coding) if the change appears to require:

- an architectural decision not already documented
- a new file outside the allowed-files list
- suppression of security scanner findings
- changes to dependencies (requirements.txt, package.json, etc.)
- touching a forbidden file
- choosing between technical alternatives (drivers, pools, auth flows, migration strategies)

### Scanner finding rules

**Do not suppress scanner findings globally.**

Do not edit scanner configuration files (`.deepsource.toml`, `.github/workflows/codeql.yml`, `.snyk`, `codacy-config.yml`, etc.) unless that exact file is listed in the allowed-files list.

Prefer fixing the specific code, test, or example causing the finding.

If a finding is believed to be a false positive:

1. Explain why it is a false positive
2. Request human decision before adding suppression
3. If approved, add inline suppression with a comment explaining the justification

### Artifact creation rules

Do not create root-level files unless explicitly requested:

- No `PR_DESCRIPTION.md` (PR summaries belong in the GitHub PR body)
- No audit summaries, scratch scripts, or manual test scripts
- No new tracking documents or report files

### Scope control rules

When working in high-risk areas:

- No opportunistic cleanup of adjacent code
- No refactoring unrelated to the stated objective
- No dependency upgrades except explicitly named ones
- No changes to graph logic, frontend, CI, or docs unless listed in allowed files

### Database/auth/deployment-specific rules

Do not choose between technical alternatives during implementation:

- SQLite vs PostgreSQL
- sync vs async database drivers
- migration tool selection (Alembic, sqlalchemy-migrate, custom scripts)
- connection pooling strategies
- environment-variable precedence order when multiple config sources exist

These decisions must be made before coding begins.

If not specified in the prompt, stop and ask for the decision.

### Lesson from PR #1096

PR #1096 (PostgreSQL support for API auth database) demonstrated the risk of autonomous implementation across database boundaries. The PR added PostgreSQL support but initially drifted into broader scope (connection pooling, async driver selection, environment-variable precedence) without explicit contracts. This showed the need for file-bounded implementation contracts in high-risk areas. Future database/auth/deployment work should specify allowed files, fixed decisions, and stop conditions before coding begins.
