# Automation Scope Policy

This repository uses automated review tools, code scanners, and coding agents. They are useful only when they stay inside clearly declared intent.

## Core rule

Automation may review scope, but it may not redefine scope.

An active pull request is a bounded unit of intent. Automated tooling must not widen that intent without an explicit human decision.

## Allowed behavior

Automation may:

- comment on pull requests
- add inline review suggestions
- annotate files or lines
- open a separate, narrow follow-up pull request
- open an issue for out-of-scope findings
- apply labels when configured to do so

## Prohibited behavior on active pull requests

Automation must not:

- add unrelated files to an active pull request
- modify files outside the pull request's declared scope
- regenerate lockfiles unless the pull request is explicitly a dependency pull request
- modify workflow files unless the pull request is explicitly a workflow or CI pull request
- reformat unrelated files for consistency
- broaden docs, runtime code, dependency files, tests, and workflows together in response to isolated findings
- redefine dependency policy, production architecture, or runtime policy from scanner output alone

## Required behavior for out-of-scope findings

If automation discovers something outside the active pull request's scope, it must do one of the following:

1. leave a comment on the current pull request
2. open a separate, narrow follow-up pull request
3. open an issue

It must not silently widen the active pull request.

## Scope declarations are authoritative

Every pull request should define:

- primary objective
- in scope
- out of scope
- files expected to change
- validation commands
- merge criteria

Automation should treat those declarations as the operational boundary for the pull request.

## Dependency and workflow changes

Dependency changes and workflow changes are high-risk scope expanders.

- Dependency files should change only in dependency-focused pull requests.
- Workflow files should change only in workflow or CI-focused pull requests.
- Lockfiles should not be regenerated in unrelated pull requests.
- Validator or scanner findings that require dependency or workflow updates should be handled in a separate pull request unless that work is the explicit purpose of the current pull request.

## Documentation as control plane

Automation must treat the repository control documents as architectural guidance, not optional prose. If those documents disagree with a scanner assumption, the scanner assumption does not automatically win.

The authoritative control documents are listed in `docs/REPOSITORY_CONTROL_PLANE.md`.

## Human override

A maintainer may explicitly authorize a broader automated change. When that happens, the pull request description should state that broader scope directly.

Absent that explicit instruction, narrow scope is the default.
