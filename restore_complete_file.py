#!/usr/bin/env python3
"""
Script to restore the complete test_github_workflows.py file from the PR.
The file was truncated during edits and needs to be restored.
"""

# The complete content was fetched earlier from the PR
# I need to write it to the file

import sys

# Read the original PR content that was successfully fetched
pr_file_content = open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8').read()

print(f"Current file length: {len(pr_file_content)} chars")
print(f"Current line count: {pr_file_content.count(chr(10)) + 1}")

# Count triple quotes
quote_count = pr_file_content.count('"""')
print(f"Triple quote count: {quote_count} ({'EVEN' if quote_count % 2 == 0 else 'ODD'})")

# The file is incomplete - it ends at line 2919 but should continue
# The issue is that line 2901 has an opening """ that never closes
# Let me add the missing closing """ and any remaining content

# Find where the file should continue
lines = pr_file_content.split('\n')
print(f"\nLast 5 lines:")
for i, line in enumerate(lines[-5:], start=len(lines)-4):
    print(f"{i}: {line[:80]}")
