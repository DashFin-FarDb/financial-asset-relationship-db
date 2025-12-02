#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

odd_after = []
for i in range(2438, len(lines)):
    count = lines[i].count('"""')
    if count % 2 == 1:
        odd_after.append((i, lines[i].rstrip()[:80]))

print(f'Lines after 2438 with odd triple quotes: {len(odd_after)}')
if odd_after:
    for i, text in odd_after:
        print(f'Line {i}: {text}')
else:
    print('No odd triple quotes after line 2438!')
    print('\nThis means the unmatched quote must be BEFORE line 2438')
    print('Since we have 95 lines total with odd counts (which is odd),')
    print('one of the PAIRS must be broken')
