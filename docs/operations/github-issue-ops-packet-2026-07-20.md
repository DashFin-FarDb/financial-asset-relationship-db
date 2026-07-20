# GitHub issue operations packet (2026-07-20)

This packet documents the recommended issue lifecycle actions after merged PR work
for Super-Linter validator re-enablement.

## Merged context

- PR #1497 (merged): Re-enable Super-Linter Checkov and GitHub Actions validators
 - Merge commit: `dd19b5b0d5be009f665ff962bc57885a6262cd13`

## 1) Close no-longer-needed issues

### Close issue #1496

Reason: acceptance criteria are satisfied by merged work.

Suggested close comment:

```md
Closing as completed.

Delivered on `main`:
- `VALIDATE_CHECKOV` and `VALIDATE_GITHUB_ACTIONS` are re-enabled in `.github/workflows/super-linter.yml` (enabled by omission in Super-Linter v7).
- Checkov waivers are documented in `.github/linters/.checkov.yaml`.
- Representative `Lint Code Base` validation passed during implementation and follow-up hardening.

This issue's acceptance criteria are satisfied; remaining validator debt is tracked in follow-up issues.
```

### Close issue #1495

Reason: original scope bundled multiple follow-ups; replaced by narrower, independently trackable issues below.

Suggested close comment:

```md
Closing in favor of narrower follow-up issues for remaining debt:
- YAML_PRETTIER re-enable cleanup
- Checkov waiver hardening (global waiver removal path)

The original combined issue is now superseded by these scoped tracks.
```

## 2) Create scoped follow-up issues

### New issue A

Title:

```md
ci: re-enable VALIDATE_YAML_PRETTIER in Super-Linter
```

Body:

```md
## Summary

`VALIDATE_YAML_PRETTIER` remains disabled in `.github/workflows/super-linter.yml`.
This issue tracks the dedicated cleanup required to re-enable it safely.

## Objective

Re-enable `VALIDATE_YAML_PRETTIER` on `main` without introducing unrelated CI scope.

## In Scope

- Identify and fix workflow YAML formatting debt that currently fails YAML_PRETTIER.
- Re-enable `VALIDATE_YAML_PRETTIER` in `.github/workflows/super-linter.yml`.
- Validate `Lint Code Base` passes on a representative PR.

## Out of Scope

- Checkov policy hardening
- Workflow permission refactors unrelated to formatting
- Application/runtime code changes

## Acceptance Criteria

- [ ] `VALIDATE_YAML_PRETTIER` enabled on `main`
- [ ] `Lint Code Base` passes with YAML_PRETTIER active
- [ ] Changes remain narrowly scoped to formatting + validator toggle

## Related

- PR #1497 (merged re-enable baseline for Checkov + GitHub Actions)
```

### New issue B

Title:

```md
ci-security: harden Checkov waivers by removing global CKV2_GHA_1
```

Body:

```md
## Summary

Current Checkov config (`.github/linters/.checkov.yaml`) still includes a global
`CKV2_GHA_1` waiver. This can hide future workflow permission regressions.

## Objective

Remove global `CKV2_GHA_1` waiver by remediating workflow permissions to least privilege.

## In Scope

- Audit workflows currently relying on global `CKV2_GHA_1` waiver.
- Apply least-privilege top-level `permissions` where required.
- Remove global `CKV2_GHA_1` from `.github/linters/.checkov.yaml`.
- Validate `Lint Code Base` passes after hardening.

## Out of Scope

- YAML_PRETTIER formatting work
- New broad waivers
- Non-CI application/runtime behavior changes

## Acceptance Criteria

- [ ] Global `CKV2_GHA_1` waiver removed
- [ ] Workflow permissions hardened and documented
- [ ] `Lint Code Base` passes on representative PR(s)

## Related

- PR #1497 (merged)
- Follow-up commits on re-enable branch that narrowed Checkov waivers
```

## 3) Ready-to-run commands (execute in a write-enabled environment)

```bash
# Close #1496 with completion note
gh issue comment 1496 --body-file /tmp/issue1496-close.md
gh issue close 1496

# Close #1495 as superseded by scoped issues
gh issue comment 1495 --body-file /tmp/issue1495-close.md
gh issue close 1495

# Create new scoped issue A
gh issue create \
  --title "ci: re-enable VALIDATE_YAML_PRETTIER in Super-Linter" \
  --body-file /tmp/issue-yaml-prettier.md \
  --label "ci-cd" \
  --label "[infra]"

# Create new scoped issue B
gh issue create \
  --title "ci-security: harden Checkov waivers by removing global CKV2_GHA_1" \
  --body-file /tmp/issue-checkov-hardening.md \
  --label "ci-cd" \
  --label "[infra]"
```

> Note: this cloud environment provides `gh` read access only, so issue write actions
> above are intentionally documented rather than executed in-session.
