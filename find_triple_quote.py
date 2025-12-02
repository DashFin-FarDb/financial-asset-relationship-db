#!/usr/bin/env python3
"""Find unterminated triple quotes in a file."""

with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print("\nSearching for triple quotes around line 2900...")

for i in range(2850, min(len(lines), 2920)):
    line = lines[i]
    if '"""' in line:
        print(f"Line {i+1}: {line.rstrip()}")
