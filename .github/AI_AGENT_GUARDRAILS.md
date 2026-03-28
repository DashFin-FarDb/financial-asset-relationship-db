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
- `.github/workflows/dependency-check.yml`
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
