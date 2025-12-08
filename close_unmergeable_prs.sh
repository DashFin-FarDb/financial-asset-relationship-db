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

# Get all open PRs with CONFLICTING status
echo "Fetching conflicting PRs..."
if ! gh pr list --state open --json number,title,mergeable,createdAt --limit 100 | \
  jq -r '.[] | select(.mergeable == "CONFLICTING") | "\(.number)"' > /tmp/conflicting_prs.txt; then
    echo "Error: Failed to fetch or parse conflicting PRs." >&2
    exit 1
fi

# Check if file exists and is non-empty
if [ ! -s /tmp/conflicting_prs.txt ]; then
    echo "No conflicting PRs found."
    exit 0
fi

echo "Found $(wc -l < /tmp/conflicting_prs.txt) conflicting PRs"

# For now, let's just list them - we won't auto-close without manual review
while read pr_number; do
    echo "PR #$pr_number:"
    if ! gh pr view $pr_number --json title,headRefName,createdAt | \
      jq -r '"  Title: \(.title)\n  Branch: \(.headRefName)\n  Created: \(.createdAt)"'; then
        echo "  Error: Failed to fetch details for PR #$pr_number" >&2
    fi
    echo ""
done < /tmp/conflicting_prs.txt

# Cleanup
rm -f /tmp/conflicting_prs.txt
