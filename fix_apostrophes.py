#!/usr/bin/env python3
import re

with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace common problematic patterns in docstrings
replacements = [
    ("job's", "job"),
    ("don't", "do not"),
    ("doesn't", "does not"),
    ("aren't", "are not"),
    ("isn't", "is not"),
    ("won't", "will not"),
    ("can't", "cannot"),
    ("shouldn't", "should not"),
    ("wouldn't", "would not"),
    ("haven't", "have not"),
    ("hasn't", "has not"),
    ("it's", "it is"),
    ("that's", "that is"),
    ("there's", "there is"),
    ("what's", "what is"),
    ("line's", "line"),
    ("file's", "file"),
    ("workflow's", "workflow"),
    ("step's", "step"),
]

for old, new in replacements:
    content = content.replace(old, new)

with open('tests/integration/test_github_workflows.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed apostrophes in docstrings")
