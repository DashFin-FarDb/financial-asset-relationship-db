# Dependency Policy

This document defines the dependency model for this repository.

## Core rule

`requirements.txt` is the source of truth for runtime and deployment dependencies.

If a dependency is required for the application to run, its authoritative version or range belongs in `requirements.txt`.

## File roles

### `requirements.txt`

Authoritative runtime / deployment dependency surface.

Use this file for:

- application runtime dependencies
- deployment dependencies
- intentional runtime security override pins
- the versions/ranges the project is actually expected to run against

### `pyproject.toml`

Packaging and editable-install surface.

Use this file for:

- package metadata
- build tool configuration
- a runtime dependency surface that mirrors `requirements.txt` closely enough for `pip install -e .`

Rule:

- `pyproject.toml` must not invent a different runtime policy from `requirements.txt`
- if the two differ, `requirements.txt` wins and `pyproject.toml` must be corrected

### `requirements-dev.txt`

Supplemental development, test, lint, and repository tooling.

Use this file for:

- pytest plugins and test-only helpers that are not required in production
- lint/format/type-check tooling
- optional contributor tooling not required for production runtime

Note:

- Some testing libraries may also appear in `requirements.txt` when they are part of the supported runtime or integration test matrix. In those cases, `requirements.txt` remains the authoritative source for the runtime version/range.

Rule:

- `requirements-dev.txt` is not the runtime source of truth
- when a package appears in both files, `requirements.txt` defines the canonical runtime constraint; `requirements-dev.txt` may mirror or narrow it for tooling, but must not introduce an incompatible version
- it may extend the toolchain, but it must not silently redefine runtime versions

### Tests, workflows, and documentation

These validate and describe the dependency model.
They do not define it.

Rule:

- if a validator or workflow disagrees with the dependency policy, fix the validator or workflow
- do not distort dependency files to satisfy a stale assumption

## CI bootstrap boundary

CI trusts the packaging tools supplied by its selected Python runtime. GitHub
Actions obtains that runtime through a commit-pinned `actions/setup-python`
invocation, directly or through the repository's pinned local composite action.
CircleCI obtains it from the configured, reviewed `cimg/python:3.12` executor
tag. That tag is not an immutable image digest and can be rebuilt upstream; the
current boundary explicitly trusts that provider-managed tag.

That provider-supplied `pip`, `setuptools`, and `wheel` surface is the narrow
trusted-bootstrap boundary. A job must not perform a floating network
self-upgrade of those tools before installing the repository's existing package
inputs. Every current bootstrap site must instead record the runtime identity
with this exact command:

```bash
python -m pip --version
```

The version record is build evidence; it is not a new dependency source of
truth. Changing the Python setup action, executor tag or digest, or bootstrap
model is a separate dependency decision and must be reviewed explicitly. If a
supported job cannot install its unchanged inputs with the supplied tooling,
stop and review that runtime boundary rather than adding an unpinned
self-upgrade.

This boundary does not change project dependencies, scanner roots, or the
separate PEP 517 build-isolation behavior declared by `pyproject.toml`.

## Dependency change order of operations

When changing dependencies, apply changes in this order:

1. Update `requirements.txt`
2. Align `pyproject.toml` to the intended runtime policy
3. Adjust `requirements-dev.txt` only if dev/test tooling is affected
4. Update validators, workflows, and docs to match
5. Run the validation commands below

## Allowed dependency PR types

A dependency PR should normally do exactly one of the following:

1. Runtime dependency alignment
2. Dev/test tooling alignment
3. Validator/workflow follow-up to an already-decided dependency model
4. Security or framework upgrade

Do not combine multiple dependency decisions into one PR unless there is a strong reason and the PR description explains why.

## Guardrails

### Do

- keep runtime dependency decisions anchored to `requirements.txt`
- explain why any exact pin exists
- split framework/security upgrades from validator cleanup where practical
- update docs when the supported install path changes
- state explicitly what is not in scope

### Do not

- let tests or workflow assumptions redefine the dependency model
- mix runtime dependency policy work with broad refactors
- broaden a PR from alignment into upgrade work without saying so
- claim files are "aligned" if `requirements.txt` and `pyproject.toml` still resolve materially different runtime surfaces

## Required validation commands

Run the relevant commands for the change you made.

### Runtime validation

```bash
pip install -r requirements.txt
pip check
```

### Editable install validation

```bash
pip install -r requirements.txt
pip install -e .
pip check
python -c "from app import FinancialAssetApp; assert callable(getattr(FinancialAssetApp, 'create_interface', None))"
python -c "from api.main import app"
```

### Full dev tooling validation

```bash
pip install -r requirements.txt -r requirements-dev.txt
pip check
```

### Core dev extra validation

```bash
pip install -e ".[dev]"
pip check
pytest --version
flake8 --version
pylint --version
mypy --version
black --version
isort --version
ruff --version
```

## Review checklist for dependency PRs

A dependency PR is not ready until all of the following are true:

- `requirements.txt` reflects the intended runtime decision
- `pyproject.toml` does not contradict that runtime decision
- `requirements-dev.txt` only adds dev/test/tooling intent
- validators and workflows reflect the dependency model rather than redefine it
- the PR description clearly states the scope and non-scope
- the listed validation commands have been run and reported
