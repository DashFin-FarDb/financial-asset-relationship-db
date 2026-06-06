#!/bin/bash
set -e

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

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed. Please install jq to parse JSON." >&2
    exit 1
fi

# Get all open PRs with CONFLICTING status and display them
# Using a single API call to avoid N+1 pattern and rate limiting
echo "Fetching conflicting PRs..."

if ! result=$(gh pr list --state open --json number,title,mergeable,createdAt,headRefName --limit 100 | \
  jq -r '.[] | select(.mergeable == "CONFLICTING") | "PR #\(.number):\n  Title: \(.title)\n  Branch: \(.headRefName)\n  Created: \(.createdAt)\n"'); then
    echo "Error: Failed to fetch or parse conflicting PRs." >&2
    exit 1
fi

# Check if we found any conflicting PRs
if [ -z "$result" ]; then
    echo "No conflicting PRs found."
    exit 0
fi

# Count the number of PRs (count "PR #" occurrences)
pr_count=$(echo "$result" | grep -c "^PR #" || true)
echo "Found $pr_count conflicting PRs"
echo ""
echo "$result"
