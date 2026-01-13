# Branch Cleanup Quick Reference

Quick commands and procedures for maintaining a clean repository.

## 🚀 Quick Start

```bash
# Run the automated cleanup script
chmod +x cleanup-branches.sh
./cleanup-branches.sh
```

## 📋 Common Commands

### View Branches

```bash
# List all local branches
git branch -a

# List branches with last commit info
git branch -vv

# List remote branches
git branch -r

# Show merged branches
git branch --merged main

# Show unmerged branches
git branch --no-merged main
```

### Delete Branches

```bash
# Delete local branch (safe - only if merged)
git branch -d branch-name

# Force delete local branch (use with caution)
git branch -D branch-name

# Delete remote branch
git push origin --delete branch-name

# Delete multiple local branches
git branch --merged main | grep -v "^\*" | grep -v "main" | xargs -r git branch -d
```

### Cleanup Remote References

```bash
# Remove stale remote-tracking branches
git fetch --prune

# Or use the shorthand
git fetch -p

# Remove all remote-tracking branches that no longer exist
git remote prune origin
```

### Check Branch Status

```bash
# Show branches and their tracking status
git branch -vv

# Show last commit date for each branch
git for-each-ref --sort=-committerdate refs/heads/ --format='%(committerdate:short) %(refname:short)'

# Find branches older than 90 days
git for-each-ref --sort=-committerdate refs/heads/ --format='%(committerdate:short) %(refname:short)' | awk '$1 < "'$(date -d '90 days ago' +%Y-%m-%d)'"'
```

## 🔍 Branch Analysis

### Check if Branch is Merged

```bash
# Check if branch is merged into main
git branch --merged main | grep branch-name

# Check commits unique to branch
git log main..branch-name --oneline

# Check if branch has unique commits
git cherry -v main branch-name
```

### Find Stale Branches

```bash
# Branches with no commits in last 90 days
for branch in $(git branch | sed 's/^..//'); do
    if [ "$branch" != "main" ]; then
        last_commit=$(git log -1 --format=%ci "$branch")
        echo "$branch: $last_commit"
    fi
done
```

## ⚠️ Safety Checks

Before deleting any branch:

1. **Verify it's merged**:

   ```bash
   git branch --merged main | grep branch-name
   ```

2. **Check for unique commits**:

   ```bash
   git log main..branch-name
   ```

3. **Ensure no active work**:

   ```bash
   git log -1 branch-name
   ```

4. **Check PR status** on GitHub

## 🤖 Automated Workflow

The repository includes an automated workflow that runs weekly:

- **Location**: `.github/workflows/branch-cleanup.yml`
- **Schedule**: Every Monday at 9 AM UTC
- **Manual trigger**: Actions tab → "Branch Cleanup Report" → "Run workflow"

## 📝 Branch Naming Conventions

Use descriptive branch names:

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions/updates
- `chore/description` - Maintenance tasks

## 🎯 Best Practices

### For Contributors

1. ✅ Create branches from `main`
2. ✅ Keep branches short-lived (< 2 weeks)
3. ✅ Sync with main regularly
4. ✅ Delete after merge
5. ✅ Use descriptive names

### For Maintainers

1. ✅ Review PRs promptly
2. ✅ Merge or close stale PRs
3. ✅ Delete merged branches
4. ✅ Run cleanup script monthly
5. ✅ Monitor branch count

## 🔧 Troubleshooting

### Branch Won't Delete

```bash
# If branch has unmerged commits
git branch -D branch-name  # Force delete (careful!)

# If remote branch won't delete
git push origin --delete branch-name --force
```

### Restore Deleted Branch

```bash
# Find the commit SHA
git reflog

# Recreate branch
git branch branch-name <commit-sha>
```

### Sync Fork with Upstream

```bash
# Add upstream remote (if not already added)
git remote add upstream https://github.com/original/repo.git

# Fetch upstream changes
git fetch upstream

# Merge upstream main into your main
git checkout main
git merge upstream/main

# Push to your fork
git push origin main
```

## 📊 Repository Health Metrics

Target metrics for a healthy repository:

- **Total branches**: < 10
- **Stale branches** (90+ days): 0
- **Merged but not deleted**: 0
- **Open PRs**: < 5
- **Average branch age**: < 30 days

## 🔗 Related Documentation

- [BRANCH_CLEANUP_ANALYSIS.md](BRANCH_CLEANUP_ANALYSIS.md) - Detailed analysis
- [BRANCH_CLEANUP_SUMMARY.md](BRANCH_CLEANUP_SUMMARY.md) - Executive summary
- [CONTRIBUTING.md](CONTRIBUTING.md) - Full contributing guidelines

## 💡 Tips

- Use `git fetch --prune` regularly to clean up remote references
- Enable "Automatically delete head branches" in GitHub repository settings
- Set up branch protection rules for `main`
- Use the automated workflow to stay informed
- Review branches monthly, not just when they become a problem

---

**Quick Help**: Run `./cleanup-branches.sh` for an interactive cleanup session
