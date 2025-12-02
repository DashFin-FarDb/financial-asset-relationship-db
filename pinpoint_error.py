#!/usr/bin/env python3
import ast

with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Binary search between 900 and 910
for cutoff in range(901, 911):
    truncated = ''.join(lines[:cutoff])
    try:
        ast.parse(truncated)
        print(f'✓ Valid up to line {cutoff}')
    except SyntaxError as e:
        print(f'✗ Invalid at line {cutoff}: {e.msg} (reported at line {e.lineno})')
        print(f'  Line {cutoff-1}: {lines[cutoff-1].rstrip()[:80]}')
        if cutoff > 1:
            print(f'  Line {cutoff-2}: {lines[cutoff-2].rstrip()[:80]}')
