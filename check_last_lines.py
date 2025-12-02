#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f'Total lines: {len(lines)}')
print('\nLast 10 lines:')
for i in range(max(0, len(lines)-10), len(lines)):
    print(f'{i}: {lines[i].rstrip()[:100]}')
