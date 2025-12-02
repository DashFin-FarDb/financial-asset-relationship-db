#!/usr/bin/env python3
"""Fix all issues in test_github_workflows.py from PR #239"""

with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix the malformed docstring around line 448
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Fix the specific malformed docstring at line 448
    if i == 447 and 'def test_pr_agent_python_version' in line:
        fixed_lines.append(line)
        i += 1
        # Skip the malformed docstring lines and add a proper one
        if i < len(lines) and lines[i].strip() == '"""':
            # Skip all the malformed docstring content
            while i < len(lines) and not (lines[i].strip().startswith('trigger_job =') or 
                                          lines[i].strip().startswith('review_job =')):
                i += 1
            # Add a proper docstring
            fixed_lines.append('        """Ensure any actions/setup-python step specifies python-version 3.11."""\n')
        continue
    
    fixed_lines.append(line)
    i += 1

# Write back
with open('tests/integration/test_github_workflows.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

# Now fix all apostrophes
with open('tests/integration/test_github_workflows.py', 'r', encoding='utf-8') as f:
    content = f.read()

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
    # Fix f-strings with apostrophes - remove quotes around variable names
    ("job '{job_name}'", "job {job_name}"),
    ("step '{", "step {"),
    ("file '{", "file {"),
]

for old, new in replacements:
    content = content.replace(old, new)

with open('tests/integration/test_github_workflows.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed all issues")
