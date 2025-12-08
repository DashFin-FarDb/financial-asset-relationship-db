#!/bin/bash

# Get all open PRs with CONFLICTING status
echo "Fetching conflicting PRs..."
gh pr list --state open --json number,title,mergeable,createdAt --limit 100 | \
  jq -r '.[] | select(.mergeable == "CONFLICTING") | "\(.number)"' > /tmp/conflicting_prs.txt

echo "Found $(wc -l < /tmp/conflicting_prs.txt) conflicting PRs"

# For now, let's just list them - we won't auto-close without manual review
while read pr_number; do
    echo "PR #$pr_number:"
    gh pr view $pr_number --json title,headRefName,createdAt | \
      jq -r '"  Title: \(.title)\n  Branch: \(.headRefName)\n  Created: \(.createdAt)"'
    echo ""
done < /tmp/conflicting_prs.txt
