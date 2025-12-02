#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all lines with odd number of triple quotes
odd_lines = []
for i in range(len(lines)):
    count = lines[i].count('"""')
    if count % 2 == 1:
        odd_lines.append(i)

print(f'Total: {len(odd_lines)} lines (should be even)')
print()

# Try to pair them up and find unpaired ones
print('Analyzing potential pairs (assuming consecutive odds form pairs):')
for i in range(0, len(odd_lines), 2):
    if i+1 < len(odd_lines):
        line1 = odd_lines[i]
        line2 = odd_lines[i+1]
        gap = line2 - line1
        print(f'Pair {i//2}: lines {line1}-{line2} (gap={gap})')
        if gap > 20:  # Unusually large gap
            print(f'  ^^^ LARGE GAP - might indicate missing closing quote')
    else:
        print(f'UNPAIRED: line {odd_lines[i]}')
        print(f'  Content: {lines[odd_lines[i]].rstrip()}')
