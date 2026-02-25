#!/bin/bash

# Systematic PR Mergeability Assessment Script
# Analyzes all codex/copilot branches for mergeability and valuable changes

echo "=== PR Mergeability Assessment ==="
echo "Date: $(date)"
echo ""

# Get list of branches
echo "Getting branch list..."
branches=$(git branch -r | grep -E "(origin/codex/|origin/copilot/)" | tr -d ' ')
echo "Found ${#branches[@]} branches to analyze"
echo ""

# Counters
mergeable_count=0
unrelated_count=0
valuable_count=0

# Analyze each branch
for branch in $branches; do
    echo "=== Analyzing: $branch ==="

    # Test mergeability
    if git merge-base main "$branch" >/dev/null 2>&1; then
        echo "✅ MERGEABLE: Related history found"
        ((mergeable_count++))

        # Check if it has meaningful changes
        files=$(git show --name-only "$branch" | grep -E "(\.py$|\.txt$|\.yml$|\.yaml$|\.md$)" | wc -l)
        if [ $files -gt 0 ]; then
            echo "  📁 Contains $files relevant files"
            ((valuable_count++))
        fi
    else
        echo "❌ UNRELATED: Cannot merge due to unrelated history"
        ((unrelated_count++))

        # Check if it has valuable changes we could extract
        files=$(git show --name-only "$branch" | grep -E "(\.py$|\.txt$|\.yml$|\.yaml$|\.md$)" | wc -l)
        if [ $files -gt 0 ]; then
            echo "  💎 Potential value: $files relevant files for extraction"
            ((valuable_count++))
        fi
    fi

    # Show key files being changed
    echo "  📄 Key files:"
    git show --name-only "$branch" | grep -E "(\.py$|\.txt$|\.yml$|\.yaml$|\.md$)" | head -5 | sed 's/^/    /'

    echo ""
done

echo "=== SUMMARY ==="
total=$((mergeable_count + unrelated_count))
echo "Total branches analyzed: $total"
echo "Mergeable: $mergeable_count"
echo "Unrelated history: $unrelated_count"
echo "Branches with potential value: $valuable_count"
