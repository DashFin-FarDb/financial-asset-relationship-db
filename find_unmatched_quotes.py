#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Track triple quote positions
triple_quotes = []
for i, line in enumerate(lines):
    count = line.count('"""')
    if count > 0:
        triple_quotes.append((i, count, line.rstrip()[:80]))

print(f'Total lines with triple quotes: {len(triple_quotes)}')
print(f'Total triple quote occurrences: {sum(c for _, c, _ in triple_quotes)}')
print(f'Should be even: {sum(c for _, c, _ in triple_quotes) % 2 == 0}')

# Show the last 10
print('\nLast 10 occurrences:')
for i, count, text in triple_quotes[-10:]:
    print(f'Line {i}: count={count} | {text}')
