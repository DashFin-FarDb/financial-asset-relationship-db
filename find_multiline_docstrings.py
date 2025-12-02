#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find potential multi-line docstrings (lines with only """ and whitespace)
multiline_starts = []
for i in range(2800, 2900):
    stripped = lines[i].strip()
    if stripped == '"""':
        multiline_starts.append(i)

print(f'Lines with standalone """ between 2800-2899:')
for i in multiline_starts:
    print(f'Line {i}: {lines[i].rstrip()}')
    # Show next few lines for context
    for j in range(i+1, min(i+5, len(lines))):
        print(f'  +{j-i}: {lines[j].rstrip()[:80]}')
    print()
