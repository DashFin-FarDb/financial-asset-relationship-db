#!/usr/bin/env python3
"""Fix syntax errors in test_github_workflows.py"""

with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix specific line with apostrophe
content = content.replace(
    "Scans each job's steps and for any with keys containing token, password, key, or secret, ensures values start with",
    "Scans each job steps and for any with keys containing token, password, key, or secret, ensures values start with"
)

# Fix all common contractions and possessives
replacements = [
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
    ("job's", "job"),
    ("key's", "key"),
    ("'s ", "s "),  # Generic possessive removal
]

for old, new in replacements:
    content = content.replace(old, new)

with open('tests/integration/test_github_workflows.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed syntax errors")
