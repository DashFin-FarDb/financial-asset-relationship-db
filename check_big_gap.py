#!/usr/bin/env python3
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check the big gap between 1479 and 2430
triple_quotes = []
for i in range(1479, 2430):
    if '"""' in lines[i]:
        triple_quotes.append((i, lines[i].rstrip()[:80]))

print(f'Lines with triple quotes between 1479-2430: {len(triple_quotes)}')
if len(triple_quotes) == 0:
    print('NO TRIPLE QUOTES IN THIS RANGE!')
    print('This means line 1479 closed a docstring, and the next one opens at line 2430.')
    print('But our pairing analysis says line 1479 should pair with line 2430.')
    print('This creates a 951-line "docstring" that includes everything between them!')
else:
    print('Found triple quotes:')
    for i, text in triple_quotes:
        print(f'  {i}: {text}')
