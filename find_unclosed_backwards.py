#!/usr/bin/env python3
import ast

with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Work backwards from line 2400 to find where it becomes valid
for cutoff in range(2400, 0, -100):
    truncated = ''.join(lines[:cutoff])
    try:
        ast.parse(truncated)
        print(f'✓ Valid up to line {cutoff}')
        print(f'  The unclosed docstring is between lines {cutoff} and {cutoff+100}')
        
        # Now narrow it down
        for fine in range(cutoff, cutoff+100, 10):
            trunc2 = ''.join(lines[:fine])
            try:
                ast.parse(trunc2)
                print(f'  ✓ Valid up to line {fine}')
            except:
                print(f'  ✗ Invalid at line {fine}')
                print(f'    ERROR is between lines {fine-10} and {fine}')
                break
        break
    except SyntaxError:
        pass  # Keep searching

print('\nIf no valid point found, the error is very early in the file')
