#!/bin/bash

# Branch Cleanup Script
# This script helps identify and clean up stale branches

set -e

echo "=== Branch Cleanup Analysis ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fetch latest from remote
echo "Fetching latest changes from remote..."
git fetch --all --prune

echo ""
echo "=== Local Branches ==="
git branch -vv

echo ""
echo "=== Remote Branches ==="
git branch -r

echo ""
echo "=== Merged Branches (can be safely deleted) ==="
# Find branches that have been merged into main
MERGED_BRANCHES=$(git branch --merged main | grep -v "^\*" | grep -v "main" | grep -v "develop" || true)

if [ -z "$MERGED_BRANCHES" ]; then
    echo -e "${GREEN}No merged branches found${NC}"
else
    echo -e "${YELLOW}The following branches have been merged into main:${NC}"
    echo "$MERGED_BRANCHES"
    echo ""
    read -p "Do you want to delete these local branches? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$MERGED_BRANCHES" | xargs -r git branch -d
        echo -e "${GREEN}Merged branches deleted${NC}"
    fi
fi

echo ""
echo "=== Stale Branches (no activity in 90+ days) ==="
# Find branches with no commits in the last 90 days
for branch in $(git for-each-ref --format='%(refname:short)' refs/heads/); do
    if [ "$branch" != "main" ] && [ "$branch" != "develop" ]; then
        LAST_COMMIT_DATE=$(git log -1 --format=%ci "$branch" 2>/dev/null || echo "")
        if [ -n "$LAST_COMMIT_DATE" ]; then
            DAYS_OLD=$(( ($(date +%s) - $(date -d "$LAST_COMMIT_DATE" +%s)) / 86400 ))
            if [ $DAYS_OLD -gt 90 ]; then
                echo -e "${YELLOW}$branch${NC} - Last commit: $DAYS_OLD days ago"
            fi
        fi
    fi
done

echo ""
echo "=== Remote Branches Not in Local ==="
# Find remote branches that don't have local counterparts
for remote_branch in $(git branch -r | grep -v "HEAD" | grep 'origin/' | sed 's/origin\///'); do
    if ! git show-ref --verify --quiet "refs/heads/$remote_branch"; then
        echo -e "${YELLOW}origin/$remote_branch${NC} - Not tracked locally"
    fi
done

echo ""
echo "=== Cleanup Recommendations ==="
echo "1. Review the BRANCH_CLEANUP_ANALYSIS.md file for detailed analysis"
echo "2. Delete merged branches that are no longer needed"
echo "3. Archive or delete stale branches (90+ days old)"
echo "4. Ensure all important commits are merged to main"
echo ""
echo "To delete a local branch: git branch -d <branch-name>"
echo "To delete a remote branch: git push origin --delete <branch-name>"
echo "To force delete a branch: git branch -D <branch-name>"
