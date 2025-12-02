#!/usr/bin/env python3
import ast

with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Work backwards from line 2900 to find the unclosed docstring
# Try truncating the file at different points and see where it becomes valid
for cutoff in range(2900, 2400, -50):
    truncated = ''.join(lines[:cutoff])
    try:
        ast.parse(truncated)
        print(f'✓ Valid up to line {cutoff}')
        print(f'  ERROR must be between lines {cutoff} and {cutoff+50}')
        break
    except SyntaxError as e:
        print(f'✗ Invalid at line {cutoff}: {e.msg}')
