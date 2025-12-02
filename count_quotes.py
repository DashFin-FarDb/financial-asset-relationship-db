#!/usr/bin/env python3
"""Count triple quotes to find mismatch."""

with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Count all triple quote occurrences
count = content.count('"""')
print(f"Total triple quote markers: {count}")
print(f"Should be even (pairs), is {'EVEN' if count % 2 == 0 else 'ODD'}")

# Find all positions
import re
positions = [(m.start(), m.end()) for m in re.finditer(r'"""', content)]

print(f"\nFound {len(positions)} triple quote markers")
print("Checking last 20:")
for i, (start, end) in enumerate(positions[-20:], start=len(positions)-19):
    # Get line number
    line_num = content[:start].count('\n') + 1
    # Get context
    context_start = max(0, start - 30)
    context_end = min(len(content), end + 30)
    context = content[context_start:context_end].replace('\n', '\\n')
    print(f"{i}: Line {line_num}, pos {start}: ...{context}...")
