"""
Comprehensive validation tests for documentation markdown files added in current branch.

Tests ensure that:
- All markdown files are valid and parseable
- Links within markdown files are correctly formatted
- Code blocks have proper language identifiers
- Tables are properly formatted
- Headings follow a logical hierarchy
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

import pytest


class TestDocumentationFilesValidation:


```), fail if 50 % or more of those blocks lack a language specifier(for example,
