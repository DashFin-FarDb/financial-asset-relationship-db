#!/bin/bash
set -e

# Script to close unmergeable PRs with proper explanation
# Usage: ./close_unmergeable_prs_script.sh <pr_number>

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed." >&2
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "Error: GitHub CLI is not authenticated. Run 'gh auth login' first." >&2
    exit 1
fi

PR=$1

if [ -z "$PR" ]; then
    echo "Usage: $0 <pr_number>" >&2
    exit 1
fi

# Validate PR number is numeric
if ! [[ "$PR" =~ ^[0-9]+$ ]]; then
    echo "Error: PR number must be a positive integer." >&2
    exit 1
fi

COMMENT="This PR cannot be merged due to unrelated Git histories or merge conflicts that cannot be automatically resolved.

**Issue**: The branch has an incompatible Git history with main, likely caused by:
- Branch created from non-main base
- Automated tool generating branch without proper ancestry
- Targeting files that don't exist in main

**Resolution**: As documented in PR #427, we have:
- Successfully merged all truly mergeable PRs (#239, #254, #322)
- Identified systematic issues with bot-generated branches
- Proposed process improvements to prevent future issues

If this PR contains valuable changes, please:
1. Create a fresh branch from current main
2. Cherry-pick or manually apply the changes
3. Submit a new PR with proper Git history

Thank you for your contribution! This closure is part of a systematic cleanup of unmergeable PRs."

echo "Closing PR #$PR with comment..."
if ! gh pr close "$PR" --comment "$COMMENT"; then
    echo "Error: Failed to close PR #$PR. Please check the PR number and your permissions." >&2
    exit 1
fi

echo "Successfully closed PR #$PR."
