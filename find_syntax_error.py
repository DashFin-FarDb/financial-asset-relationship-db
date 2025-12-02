#!/usr/bin/env python3
import ast
import sys

try:
    with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
        code = f.read()
    
    ast.parse(code)
    print("No syntax errors found!")
    
except SyntaxError as e:
    print(f"Syntax Error found!")
    print(f"  File: {e.filename}")
    print(f"  Line: {e.lineno}")
    print(f"  Offset: {e.offset}")
    print(f"  Message: {e.msg}")
    print(f"  Text: {e.text}")
    
    # Show context around the error
    with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if e.lineno:
        start = max(0, e.lineno - 5)
        end = min(len(lines), e.lineno + 3)
        print(f"\nContext (lines {start}-{end}):")
        for i in range(start, end):
            marker = ">>>" if i == e.lineno - 1 else "   "
            print(f"{marker} {i}: {lines[i].rstrip()}")
