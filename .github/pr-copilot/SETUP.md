# PR Copilot Setup Guide

Administrator and maintainer guide for configuring and deploying the PR Copilot agent.

## 📋 Prerequisites

Before enabling PR Copilot, ensure:

- ✅ Repository has GitHub Actions enabled
- ✅ You have admin access to the repository
- ✅ Repository has PR workflow (PRs are used)
- ✅ Branch protection rules are configured (recommended)

## 🚀 Quick Setup

### Step 1: Enable GitHub Actions

1. Navigate to repository **Settings** → **Actions** → **General**
2. Under "Actions permissions", select:
   - ✅ **Allow all actions and reusable workflows** (or)
   - ✅ **Allow [organization] and select non-[organization] actions and reusable workflows**
3. Under "Workflow permissions", select:
   - ✅ **Read and write permissions**
4. Enable:
   - ✅ **Allow GitHub Actions to create and approve pull requests**

### Step 2: Verify Workflow File

The workflow file should exist at:
```
.github/workflows/pr-copilot.yml
```

Verify it's present:
```bash
ls -la .github/workflows/pr-copilot.yml
```

### Step 3: Verify Configuration File

The configuration file should exist at:
```
.github/pr-copilot-config.yml
```

Verify it's present and valid:
```bash
# Check existence
ls -la .github/pr-copilot-config.yml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('.github/pr-copilot-config.yml'))"
```

### Step 4: Test the Agent

Create a test PR or comment on an existing PR:
```
@pr-copilot help
```

The agent should respond within 1-2 minutes.

## 🔐 GitHub Token Permissions

PR Copilot uses the default `GITHUB_TOKEN` provided by GitHub Actions. Required permissions:

| Permission | Access Level | Purpose |
|------------|--------------|---------|
| `contents` | `read` | Read repository files and configuration |
| `pull-requests` | `write` | Post comments on PRs, update PR status |
| `issues` | `write` | Comment on issues (PRs are issues) |
| `checks` | `read` | Read check run status and results |
| `statuses` | `read` | Read commit status checks |

These permissions are configured in the workflow file:

```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
  checks: read
  statuses: read
```

### Verifying Token Permissions

If the agent fails with permission errors:

1. Check workflow permissions in repository settings
2. Ensure "Read and write permissions" is enabled
3. Verify no organization policies restrict permissions
4. Check Actions run logs for specific permission errors

## 🛡️ Branch Protection Rules

For best results with auto-merge features, configure branch protection:

### Recommended Settings for `main` branch:

1. Navigate to **Settings** → **Branches** → **Branch protection rules**
2. Add rule for `main` (or your default branch)
3. Enable:
   - ✅ **Require a pull request before merging**
     - ✅ Require approvals: **1** (or more)
     - ✅ Dismiss stale pull request approvals when new commits are pushed
   - ✅ **Require status checks to pass before merging**
     - ✅ Require branches to be up to date before merging
     - Select required checks (CI, tests, linting, etc.)
   - ✅ **Require conversation resolution before merging** (recommended)
   - ✅ **Do not allow bypassing the above settings**

These settings ensure the auto-merge check accurately reflects merge readiness.

## ⚙️ Configuration Options

Edit `.github/pr-copilot-config.yml` to customize behavior:

### Essential Settings

```yaml
agent:
  enabled: true  # Master enable/disable switch

triggers:
  help_wanted_label: true  # Respond to "help wanted" label
  mention: true            # Respond to @pr-copilot mentions

scope:
  warn_on_long_title: 72          # Character limit for title warning
  warn_on_multiple_changes: true  # Warn on "and", "or" in titles

auto_merge:
  enabled: true              # Enable auto-merge checking
  require_reviews: 1         # Minimum required approvals
  merge_method: "squash"     # Options: squash, merge, rebase
```

### Advanced Settings

```yaml
review_handling:
  auto_acknowledge: true      # Auto-respond to review feedback
  track_actionable: true      # Track actionable review comments
  actionable_keywords:        # Keywords indicating actionable feedback
    - "please"
    - "fix"
    - "change"

status:
  include_commits: true       # Include commit count in status
  include_files_changed: true # Include file count in status
  include_reviews: true       # Include review status
  include_checks: true        # Include CI check status

notifications:
  github_comments: true       # Post as GitHub comments
  use_reactions: true         # Use emoji reactions

security:
  allowed_users: []           # Empty = all users, or list specific users
  require_write_access: false # Require contributor write access
```

## 🔧 Customizing Messages

Message templates are in the configuration file. Customize:

### Welcome Message

```yaml
welcome:
  message: |
    👋 **Welcome to PR Copilot!**

    I'm here to help manage this PR.

    [Your custom message here]
```

### Scope Warning

```yaml
scope:
  warning_message: |
    ⚠️ **PR Scope Notice**

    [Your custom warning here]
```

### Auto-Merge Confirmation

```yaml
auto_merge:
  confirmation_message: |
    🚀 **Auto-Merge Eligible**

    [Your custom message here]
```

### Merge Conflict Notification

```yaml
merge_conflicts:
  notification_message: |
    ⚠️ **Merge Conflicts Detected**

    [Your custom message here]
```

## 📊 Monitoring and Maintenance

### Check Workflow Runs

1. Navigate to **Actions** tab
2. Select "PR Copilot Agent" workflow
3. Review recent runs for:
   - Success/failure status
   - Execution time
   - Triggered events
   - Error messages

### Common Issues and Solutions

#### Issue: Agent not responding

**Diagnosis:**
```bash
# Check if workflow file is valid
yamllint .github/workflows/pr-copilot.yml

# View recent workflow runs
gh run list --workflow=pr-copilot.yml --limit 5
```

**Solutions:**
- Verify GitHub Actions are enabled
- Check workflow permissions
- Review workflow run logs for errors
- Ensure triggers are configured correctly

#### Issue: Permission denied errors

**Diagnosis:**
Check workflow run logs for errors like:
```
Error: Resource not accessible by integration
```

**Solutions:**
- Enable "Read and write permissions" in repository settings
- Verify `permissions` block in workflow file
- Check organization-level restrictions

#### Issue: Agent posting duplicate comments

**Diagnosis:**
Multiple workflow instances may be running.

**Solutions:**
- Add `concurrency` group to workflow:
  ```yaml
  concurrency:
    group: pr-copilot-${{ github.event.pull_request.number }}
    cancel-in-progress: true
  ```

#### Issue: Status updates are slow

**Solutions:**
- Reduce scope of status checks
- Adjust GitHub API rate limits awareness
- Consider caching status data
- Increase workflow timeouts

## 🧪 Testing the Agent

### Test Checklist

Before deploying to production:

- [ ] Open a test PR and verify welcome message
- [ ] Add "help wanted" label and verify response
- [ ] Comment `@pr-copilot status update` and verify status report
- [ ] Submit a review with "please fix" and verify acknowledgment
- [ ] Create merge conflict and verify detection
- [ ] Get PR approved and verify merge eligibility check
- [ ] Test with long PR title (>72 chars) and verify scope warning
- [ ] Test with PR title containing "and" and verify scope warning

### Test PR Template

Create a test PR with:
- Title: "Test PR for PR Copilot Agent - Add feature and fix bug"
- Changes: 2-3 small files
- Description: "Testing @pr-copilot functionality"

Then test:
1. Scope warning should appear (title >72 chars + "and")
2. Comment: `@pr-copilot status update`
3. Submit review with: "Please fix the typo in line 10"
4. Verify all expected responses

## 🔄 Rollback Procedures

If issues occur, disable the agent:

### Method 1: Configuration File (Temporary)

Edit `.github/pr-copilot-config.yml`:
```yaml
agent:
  enabled: false
```

Commit and push. Agent will stop responding but workflow still runs.

### Method 2: Disable Workflow (Recommended for Issues)

1. Navigate to **Actions** tab
2. Select "PR Copilot Agent" workflow
3. Click **⋮** (three dots) → **Disable workflow**

This completely stops workflow execution.

### Method 3: Delete/Rename Workflow (Emergency)

```bash
# Rename workflow file
mv .github/workflows/pr-copilot.yml .github/workflows/pr-copilot.yml.disabled

# Commit and push
git add .github/workflows/pr-copilot.yml.disabled
git commit -m "Disable PR Copilot temporarily"
git push
```

### Re-enabling After Rollback

1. Fix the issue
2. Re-enable workflow or set `enabled: true` in config
3. Test with a single PR before full deployment
4. Monitor workflow runs closely

## 📈 Performance Tuning

### Optimize Workflow Execution

```yaml
# Add to workflow file
concurrency:
  group: pr-copilot-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  detect-trigger:
    timeout-minutes: 5  # Prevent runaway jobs
```

### Reduce API Calls

Configure status update frequency:
```yaml
limits:
  max_status_updates_per_hour: 10
  status_cache_ttl: 300  # 5 minutes
```

### Optimize Python Scripts

Install dependencies only once:
```yaml
- name: Cache Python dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('.github/pr-copilot/scripts/requirements.txt') }}
```

## 🔒 Security Considerations

### Best Practices

1. **Never commit secrets** - Use GitHub Secrets for sensitive data
2. **Validate inputs** - Scripts validate all environment variables
3. **Limit permissions** - Use minimum required permissions
4. **Review logs** - Regularly check workflow logs for anomalies
5. **Keep updated** - Update dependencies in `requirements.txt`

### Security Checklist

- [ ] Workflow uses `GITHUB_TOKEN` (not a personal access token)
- [ ] Permissions are read-only where possible
- [ ] No secrets in configuration file
- [ ] Python scripts validate inputs
- [ ] External API calls are minimal
- [ ] Error messages don't leak sensitive info

## 📞 Support and Troubleshooting

### Getting Help

1. **Check documentation** - Review README.md and this guide
2. **Search workflow logs** - Look for specific error messages
3. **Open an issue** - Report bugs or request features
4. **Review recent changes** - Check if recent commits broke functionality

### Debug Mode

Enable verbose logging:

```yaml
# In .github/pr-copilot-config.yml
debug:
  enabled: true
  verbose_logging: true
  log_api_calls: true
```

This adds detailed logging to workflow runs.

### Contact Information

For issues specific to this repository:
- Open a GitHub Issue
- Tag maintainers in PR comments
- Refer to repository CONTRIBUTING.md

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub API Documentation](https://docs.github.com/en/rest)
- [PyGithub Library](https://pygithub.readthedocs.io/)
- [YAML Syntax Reference](https://yaml.org/spec/)

## ✅ Setup Validation

After setup, verify:

```bash
# 1. Workflow file exists and is valid
ls -la .github/workflows/pr-copilot.yml
yamllint .github/workflows/pr-copilot.yml

# 2. Configuration file exists and is valid
ls -la .github/pr-copilot-config.yml
python -c "import yaml; print('Valid' if yaml.safe_load(open('.github/pr-copilot-config.yml')) else 'Invalid')"

# 3. Scripts are executable and dependencies installed
ls -la .github/pr-copilot/scripts/*.py
pip install -r .github/pr-copilot/scripts/requirements.txt

# 4. GitHub Actions are enabled
gh api repos/:owner/:repo/actions/permissions | jq .enabled

# 5. Workflow permissions are correct
gh api repos/:owner/:repo/actions/permissions/workflow | jq .default_workflow_permissions
```

All checks should pass before deploying to production.

---

**Setup complete?** Test with `@pr-copilot help` in any PR!
