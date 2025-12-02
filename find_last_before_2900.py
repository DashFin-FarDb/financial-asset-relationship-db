#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all lines with """ before line 2900
found = []
for i in range(2870, 2900):
    if '"""' in lines[i]:
        found.append((i, lines[i].rstrip()[:100]))

print(f'Lines with """ between 2870-2899:')
for i, text in found:
    print(f'{i}: {text}')
