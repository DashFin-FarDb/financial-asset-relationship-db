#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all lines with odd number of triple quotes
odd_lines = []
for i in range(len(lines)):
    count = lines[i].count('"""')
    if count % 2 == 1:
        odd_lines.append(i)

print(f'Total lines with odd """ count: {len(odd_lines)}')
print(f'This should be EVEN for balanced quotes, but we have {len(odd_lines)} (ODD!)')
print()

# Show the last 20 odd lines
print('Last 20 lines with odd """ counts:')
for i in odd_lines[-20:]:
    print(f'Line {i}: {lines[i].rstrip()[:80]}')
