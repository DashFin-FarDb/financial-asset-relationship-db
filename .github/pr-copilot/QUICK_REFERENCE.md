# PR Copilot Quick Reference

Fast reference guide for using PR Copilot in your pull requests.

## 🚀 Quick Start

Just open a PR or comment with `@pr-copilot` to get started!

## 💬 Commands

### Get Status Update
```
@pr-copilot status update
```
Shows detailed PR status including commits, reviews, checks, and merge readiness.

### Get Help
```
@pr-copilot help
```
Displays available commands and features.

### Conflict Resolution Help
```
@pr-copilot help conflicts
```
Shows guidance for resolving merge conflicts.

## 🤖 Automatic Features

PR Copilot automatically:

- ✅ **Welcomes** you on first interaction
- ✅ **Validates scope** when PR is opened (warns on long/multi-topic titles)
- ✅ **Acknowledges reviews** and tracks actionable feedback
- ✅ **Checks merge eligibility** when reviews/checks complete
- ✅ **Detects conflicts** when PR is synchronized
- ✅ **Updates status** on key events

## 📊 Status Report Includes

- **PR Info:** Title, author, branch, commits, files, lines changed
- **Reviews:** Approved, changes requested, commented
- **CI Checks:** Passed, failed, pending
- **Merge Status:** Mergeable, conflicts, blockers
- **Task Checklist:** What's done, what's needed

## ⚠️ Scope Warnings

PR Copilot warns if:
- Title is too long (>72 characters)
- Title suggests multiple changes ("and", "or", "&")
- Too many files changed
- Large changeset

## ✅ Merge Eligibility

PR is merge-ready when:
- ✅ Not a draft
- ✅ Has required approvals
- ✅ All checks passed
- ✅ No merge conflicts
- ✅ No pending change requests

## 🔔 Notifications

You'll get notified about:
- Welcome message (first interaction)
- Scope issues (PR opened)
- Review acknowledgment (review submitted)
- Merge eligibility (checks/reviews complete)
- Merge conflicts (PR synchronized)

## 🎯 Best Practices

1. **Tag early** - Mention `@pr-copilot` when you need help
2. **Check status** - Use `status update` to track progress
3. **Follow suggestions** - Agent provides actionable recommendations
4. **Keep PRs focused** - Avoid scope warnings by keeping changes small
5. **Resolve conflicts** - Follow provided guidance for conflicts

## 🛠️ Configuration

Maintainers can customize:
- Trigger events
- Title length threshold
- Auto-merge criteria
- Message templates
- Security settings

See [SETUP.md](SETUP.md) for configuration details.

## 📚 More Information

- **Full Guide:** [README.md](README.md)
- **Setup:** [SETUP.md](SETUP.md)
- **Testing:** [TESTING.md](TESTING.md)
- **Config:** [pr-copilot-config.yml](../pr-copilot-config.yml)

## 💡 Tips

- Mention `@pr-copilot` in comments, not in PR description
- Status updates are cached for 5 minutes
- Agent respects branch protection rules
- Works with all PR types (feature, bugfix, docs, etc.)

## 🐛 Troubleshooting

**Agent not responding?**
- Wait 1-2 minutes for workflow to run
- Check if GitHub Actions are enabled
- Verify you mentioned `@pr-copilot` correctly

**Status update not showing?**
- Ensure PR has commits and changes
- Check if checks are still running
- Try again after a few minutes

**Unexpected warnings?**
- Review scope validation rules in config
- Check if title matches warning criteria
- Warnings are suggestions, not blockers

## 🤝 Support

- Open an issue for bugs or feature requests
- Check workflow logs in Actions tab
- Consult documentation for detailed info
- Tag maintainers for urgent issues

---

**Quick Reference Version:** 1.0.0
**Last Updated:** 2026-01-02
