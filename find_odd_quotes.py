#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find lines with odd number of triple quotes (1 or 3)
odd_quotes = []
for i, line in enumerate(lines):
    count = line.count('"""')
    if count % 2 == 1:  # Odd number
        odd_quotes.append((i, count, line.rstrip()[:100]))

print(f'Lines with ODD number of triple quotes: {len(odd_quotes)}')
print(f'Total should be EVEN for balanced quotes')
print()

if len(odd_quotes) > 0:
    print('All lines with odd triple quote counts:')
    for i, count, text in odd_quotes:
        print(f'Line {i}: count={count} | {text}')
