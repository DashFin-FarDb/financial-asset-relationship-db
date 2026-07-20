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
# Verification gate (required before issue lifecycle actions)
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git fetch origin main
DELTA_VS_MAIN="$(git rev-list --left-right --count origin/main...HEAD)"
PR1497_STATE="$(gh pr view 1497 --json state,mergedAt,mergeCommit,url)"
echo "branch=$CURRENT_BRANCH delta=$DELTA_VS_MAIN"
echo "$PR1497_STATE"

# Create new scoped issue A
ISSUE_A_URL="$(gh issue create \
  --title "ci: re-enable VALIDATE_YAML_PRETTIER in Super-Linter" \
  --body-file - \
  --label "ci-cd" \
  --label "[infra]" <<'EOF'
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
EOF
)"

# Create new scoped issue B
ISSUE_B_URL="$(gh issue create \
  --title "ci-security: harden Checkov waivers by removing global CKV2_GHA_1" \
  --body-file - \
  --label "ci-cd" \
  --label "[infra]" <<'EOF'
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
EOF
)"

ISSUE_A_ID="${ISSUE_A_URL##*/}"
ISSUE_B_ID="${ISSUE_B_URL##*/}"

# Close #1496 with completion note (include links to follow-ups)
gh issue comment 1496 --body-file - <<EOF
Closing as completed.

Delivered on \`main\`:
- \`VALIDATE_CHECKOV\` and \`VALIDATE_GITHUB_ACTIONS\` are re-enabled in \`.github/workflows/super-linter.yml\` (enabled by omission in Super-Linter v7).
- Checkov waivers are documented in \`.github/linters/.checkov.yaml\`.
- Representative \`Lint Code Base\` validation passed during implementation and follow-up hardening.

Follow-up tracks:
- #$ISSUE_A_ID ($ISSUE_A_URL)
- #$ISSUE_B_ID ($ISSUE_B_URL)
EOF
gh issue close 1496

# Close #1495 as superseded by scoped issues
gh issue comment 1495 --body-file - <<EOF
Closing in favor of narrower follow-up issues:
- #$ISSUE_A_ID ($ISSUE_A_URL)
- #$ISSUE_B_ID ($ISSUE_B_URL)

The original combined issue is superseded by these scoped tracks.
EOF
gh issue close 1495
```

> Note: this cloud environment provides `gh` read access only, so issue write actions
> above are intentionally documented rather than executed in-session.
