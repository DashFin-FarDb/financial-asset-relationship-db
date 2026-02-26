# PR Copilot Agent

An automated PR management, maintenance, and completion agent for the DashFin/financial-asset-relationship-db repository.

## 🎯 Purpose

PR Copilot automates common PR management tasks, provides status visibility, tracks review feedback, and helps maintain high-quality pull requests throughout their lifecycle.

## ✨ Features

### 1. **Welcome & Introduction**
- Automatically greets contributors on first interaction
- Explains available features and commands
- Activates when:
  - PR is opened
  - `help wanted` label is added
  - First `@pr-copilot` mention

### 2. **PR Scope Validation**
- Warns when PR titles suggest multiple changes
- Detects long titles (>72 characters)
- Identifies keywords like "and", "or", commas that indicate scope creep
- Helps maintain focused, reviewable PRs

### 3. **Status Updates**
- Comprehensive PR status on demand
- Includes:
  - PR metadata (author, commits, files changed)
  - Review status (approvals, changes requested)
  - CI/check status (passed, failed, pending)
  - Open discussion threads count
  - Task checklist (completed/pending)
- Updates automatically or on request

### 4. **Review Comment Handling**
- Automatically detects actionable feedback
- Tracks comments with keywords like:
  - "please", "should", "could you"
  - "nit", "typo", "fix"
  - "refactor", "change", "update"
- Acknowledges review feedback
- Helps ensure no feedback is missed

### 5. **Auto-Merge Eligibility**
- Evaluates when PRs are ready to merge
- Checks:
  - All CI checks pass
  - Has required approvals
  - No merge conflicts
  - Not a draft
  - Branch up to date
- Notifies when ready or lists blockers

### 6. **Merge Conflict Detection**
- Automatically detects merge conflicts
- Provides resolution guidance
- Shows affected files
- Offers step-by-step fix instructions

## 🚀 Usage

### Basic Commands

Trigger the agent by mentioning it in PR comments:

```
@pr-copilot status update
```

Get detailed status of the current PR.

```
@pr-copilot help
```

Show available commands and features.

```
@pr-copilot help conflicts
```

Get guidance on resolving merge conflicts.

### Automatic Triggers

The agent activates automatically on:

- **PR opened** - Posts welcome, checks scope
- **Label added** - `help wanted` triggers welcome
- **PR synchronized** - Checks for conflicts and merge eligibility
- **Review submitted** - Tracks actionable feedback, checks merge status
- **Review comment created** - Identifies and acknowledges actionable items
- **Status check completed** - Evaluates merge readiness
- **@pr-copilot mention** - Responds to direct mentions

## 📋 Command Reference

| Command | Description | Example |
|---------|-------------|---------|
| `@pr-copilot status update` | Get comprehensive PR status | `@pr-copilot status update` |
| `@pr-copilot help` | Show available commands | `@pr-copilot help` |
| `@pr-copilot help conflicts` | Merge conflict resolution help | `@pr-copilot help conflicts` |

**Aliases:**
- Status: `status update`, `progress report`, `show status`, `pr status`
- Help: `help`, `commands`, `usage`

## 🎭 Example Workflows

### Workflow 1: Opening a New PR

1. **You open a PR**
2. **PR Copilot responds with:**
   - Welcome message explaining features
   - Scope check (warns if title suggests multiple changes)
3. **You continue development**

### Workflow 2: Receiving Review Feedback

1. **Reviewer submits review with changes requested**
2. **PR Copilot responds with:**
   - Acknowledgment of feedback
   - List of actionable items identified
   - Tracking confirmation
3. **You address feedback**
4. **PR Copilot checks merge eligibility**

### Workflow 3: Checking PR Status

1. **You comment:** `@pr-copilot status update`
2. **PR Copilot responds with:**
   - PR information (commits, files, lines changed)
   - Review status (approvals, changes requested)
   - CI/check status (passed, failed, pending)
   - Open threads count
   - Task checklist showing what's completed and pending
   - Merge readiness assessment

### Workflow 4: Preparing to Merge

1. **All checks pass and review approved**
2. **PR Copilot automatically posts:**
   - "Auto-Merge Eligible" message
   - Confirmation all criteria met
   - Ready-to-merge indicator
3. **Maintainer merges when ready**

## ⚙️ Configuration

The agent behavior is configured in `.github/pr-copilot-config.yml`. Key settings:

```yaml
agent:
  name: "pr-copilot"
  enabled: true

triggers:
  help_wanted_label: true
  mention: true
  status_keywords:
    - "status update"
    - "progress report"

scope:
  warn_on_long_title: 72
  warn_on_multiple_changes: true

auto_merge:
  enabled: true
  require_reviews: 1
  merge_method: "squash"

review_handling:
  auto_acknowledge: true
  track_actionable: true
```

See [configuration file](.github/pr-copilot-config.yml) for all options.

## 🔧 Advanced Features

### PR Analysis Tool

Analyze PR complexity and scope:

```bash
python .github/pr-copilot/scripts/analyze_pr.py
```

**Provides:**
- Complexity score (0-100)
- Risk level assessment
- File type breakdown
- Large file detection
- Scope issue identification

### Status Generator

Generate detailed status reports:

```bash
python .github/pr-copilot/scripts/generate_status.py
```

**Includes:**
- Complete PR metadata
- Review aggregation
- Check status summary
- Task checklist
- Timeline information

### Fix Suggestion Parser

Parse and categorize review feedback:

```bash
python .github/pr-copilot/scripts/suggest_fixes.py
```

**Extracts:**
- Actionable items from reviews
- Code suggestions
- Priority categorization
- Fix proposals

*Note: These scripts are used internally by the workflow but can be run manually.*

## 📊 Status Report Format

Status updates include:

**PR Information:**
- Author, title, number
- Branch information
- Commit count
- Files changed
- Lines added/deleted
- Labels

**Review Status:**
- Approvals
- Changes requested
- Comments
- Total reviews

**CI/Check Status:**
- Passed checks
- Failed checks
- Pending checks
- Individual check details

**Merge Status:**
- Mergeable state
- Draft status
- Conflict detection

**Task Checklist:**
- Ready for review
- Has approval
- Checks passing
- No conflicts
- Changes addressed
- Threads resolved

## 🔐 Permissions

The agent requires these GitHub permissions:

- `contents: read` - Read repository content
- `pull-requests: write` - Comment on PRs
- `issues: write` - Comment on issues
- `checks: read` - Read check status
- `statuses: read` - Read commit statuses

These are configured in the workflow file and use the default `GITHUB_TOKEN`.

## 🛡️ Security & Privacy

- Agent only responds to public PR activity
- Does not access or store sensitive information
- All operations use GitHub's official API
- Comments are public and visible to all contributors
- No external services or data transmission

## 🐛 Troubleshooting

### Agent Not Responding

**Check:**
1. Is the workflow enabled in repository settings?
2. Are GitHub Actions enabled for this repo?
3. Is the PR in a fork? (Agent may have limited permissions)
4. Check workflow runs in Actions tab for errors

### Incorrect Status Information

**Try:**
1. Wait a few seconds and request status again
2. Check if GitHub API is experiencing issues
3. Verify PR has loaded all data (checks, reviews)

### Missing Notifications

**Verify:**
1. Configuration file is valid YAML
2. Trigger keywords are correct
3. Notifications are enabled in config
4. User has repository access

### Scope Warnings Incorrect

**Adjust:**
- Edit `.github/pr-copilot-config.yml`
- Modify `scope.warn_on_long_title` value
- Adjust `scope.multiple_change_keywords` list
- Disable with `scope.enabled: false`

## 📝 Best Practices

### For PR Authors

1. **Keep PRs focused** - Address scope warnings
2. **Link to issues** - Reference related issues in description
3. **Request status updates** - Use `@pr-copilot status update` to track progress
4. **Address feedback promptly** - Agent tracks actionable items

### For Reviewers

1. **Use clear language** - Agent detects keywords like "please fix"
2. **Provide code suggestions** - Use GitHub's suggestion feature
3. **Be specific** - Clear feedback helps agent categorize items
4. **Approve when ready** - Triggers merge eligibility check

### For Maintainers

1. **Monitor auto-merge notifications** - Agent identifies ready PRs
2. **Configure appropriately** - Adjust settings to match workflow
3. **Review blocked PRs** - Agent lists specific blockers
4. **Use labels effectively** - `help wanted` activates agent

## 🔄 Integration with Existing Workflows

PR Copilot works alongside:

- **PR Agent** (`.github/workflows/pr-agent.yml`) - Complementary automation
- **CI/CD pipelines** - Monitors and reports check status
- **Branch protection** - Respects required checks and reviews
- **Code review process** - Enhances with tracking and notifications

## 📚 Additional Resources

- [Setup Guide](SETUP.md) - Administrator configuration instructions
- [Configuration Reference](.github/pr-copilot-config.yml) - All available settings
- [Workflow File](.github/workflows/pr-copilot.yml) - Implementation details

## 💡 Tips

- **Mention early** - Tag `@pr-copilot` as soon as you need help
- **Check status often** - Regular status updates help track progress
- **Follow recommendations** - Agent provides actionable suggestions
- **Read welcome message** - Contains important usage information
- **Keep config updated** - Adjust settings as team needs evolve

## 🤝 Contributing

To improve PR Copilot:

1. Report issues or suggest features via GitHub Issues
2. Submit PRs with enhancements
3. Share usage feedback and best practices
4. Help improve documentation

## 📄 License

Part of the financial-asset-relationship-db repository. See main repository LICENSE file.

---

**Questions or issues?** Open an issue or mention `@pr-copilot help` in any PR!
