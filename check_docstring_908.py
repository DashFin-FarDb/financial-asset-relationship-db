#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(908, 914):
    print(f'Line {i}: {repr(lines[i])}')
