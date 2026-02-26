---
name: Branch Cleanup
about: Report stale or unnecessary branches that need cleanup
title: '[BRANCH CLEANUP] '
labels: 'maintenance, branch-cleanup'
assignees: ''
---

## Branch Information

**Branch Name**:
**Last Activity Date**:
**Associated PR**: #

## Branch Status

- [ ] Branch is merged into main
- [ ] Branch has no unique commits
- [ ] Associated PR is closed
- [ ] No active work depends on this branch
- [ ] Branch is older than 90 days

## Reason for Cleanup

<!-- Explain why this branch should be cleaned up -->

## Verification Steps Completed

- [ ] Checked commit history: `git log main..branch-name`
- [ ] Verified merge status: `git branch --merged main`
- [ ] Reviewed associated PR
- [ ] Confirmed no dependencies

## Recommended Action

- [ ] Delete branch (safe - fully merged)
- [ ] Archive branch (has historical value)
- [ ] Merge remaining commits first
- [ ] Close associated PR
- [ ] Other (specify below)

## Additional Context

<!-- Add any other context about the branch cleanup here -->

## Checklist Before Deletion

- [ ] Branch is fully merged to main
- [ ] No unique commits will be lost
- [ ] Associated PR is closed
- [ ] No active work depends on it
- [ ] CI/CD pipelines don't reference it

---

**Automated Detection**: This issue may have been created by the automated branch cleanup workflow.

**Related Documentation**:
- [Branch Cleanup Analysis](../../BRANCH_CLEANUP_ANALYSIS.md)
- [Branch Cleanup Quick Reference](../../BRANCH_CLEANUP_QUICK_REFERENCE.md)
- [Contributing Guidelines](../../CONTRIBUTING.md)
