#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f'Total lines: {len(lines)}')
print(f'Last 5 lines:')
for i in range(max(0, len(lines)-5), len(lines)):
    print(f'{i}: {lines[i][:80]}')
