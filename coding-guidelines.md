# Coding Guidelines

This document outlines the coding standards and best practices for the Financial Asset Relationship Database project.

## Table of Contents

- [Python Style Guide](#python-style-guide)
- [Code Organization](#code-organization)
- [Naming Conventions](#naming-conventions)
- [Documentation Standards](#documentation-standards)
- [Error Handling](#error-handling)
- [Testing Standards](#testing-standards)
- [Security Considerations](#security-considerations)

## Python Style Guide

### General Rules

We follow [PEP 8](https://peps.python.org/pep-0008/) with the following modifications:

- **Line length:** 120 characters maximum (not 79)
- **Formatting:** Use [Black](https://black.readthedocs.io/) for automatic code formatting
- **Import sorting:** Use [isort](https://pycqa.github.io/isort/) for import organization
- **Type hints:** Required for all public functions and methods
- **Docstrings:** Use Google-style docstrings

### Formatting Tools

Run these tools before committing:

```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Or use the Makefile
make format
```

### Type Hints

All public functions must include type hints:

```python
def calculate_relationship_strength(
    asset_a: Asset,
    asset_b: Asset,
    weight: float = 1.0
) -> float:
    """Calculate the relationship strength between two assets."""
    ...
```

## Code Organization

### Import Order

Organize imports in three groups, separated by blank lines:

```python
# 1. Standard library imports
import os
import sys
from typing import Dict, List, Optional

# 2. Third-party imports
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# 3. Local application imports
from src.models.financial_models import Asset, Relationship
from src.logic.asset_graph import AssetRelationshipGraph
```

### Module Structure

Each module should follow this structure:

1. Module docstring
2. Imports
3. Constants
4. Classes
5. Functions
6. Main block (if applicable)

```python
"""Module for handling asset relationships.

This module provides functionality for creating and managing
relationships between financial assets.
"""

from typing import Dict, List

# Constants
DEFAULT_WEIGHT = 1.0
MAX_RELATIONSHIPS = 1000

# Classes
class RelationshipManager:
    ...

# Functions
def create_relationship(asset_a: Asset, asset_b: Asset) -> Relationship:
    ...

# Main block
if __name__ == "__main__":
    ...
```

## Naming Conventions

| Type              | Convention           | Example                                    |
| ----------------- | -------------------- | ------------------------------------------ |
| Variables         | snake_case           | `asset_count`, `total_value`               |
| Functions         | snake_case           | `calculate_metrics()`, `get_asset_by_id()` |
| Classes           | PascalCase           | `AssetRelationshipGraph`, `FinancialModel` |
| Constants         | UPPER_SNAKE_CASE     | `DEFAULT_TIMEOUT`, `MAX_RETRIES`           |
| Private members   | \_leading_underscore | `_internal_cache`, `_validate_input()`     |
| Protected members | \_single_underscore  | `_helper_method()`                         |

### Descriptive Names

Use clear, descriptive names that indicate purpose:

```python
# Good
def calculate_portfolio_risk(assets: List[Asset]) -> float:
    total_exposure = sum(asset.value for asset in assets)
    ...

# Avoid
def calc(a: List) -> float:
    t = sum(x.value for x in a)
    ...
```

## Documentation Standards

### Module Docstrings

Every module should have a docstring explaining its purpose:

```python
"""Asset graph management module.

This module provides the core AssetRelationshipGraph class for managing
financial asset relationships, including methods for:
- Adding and removing assets
- Creating and managing relationships
- Calculating graph metrics
- Exporting graph data
"""
```

### Function Docstrings

Use Google-style docstrings for all public functions:

```python
def add_relationship(
    self,
    source: Asset,
    target: Asset,
    relationship_type: str,
    weight: float = 1.0
) -> Relationship:
    """Add a relationship between two assets.

    Creates a new relationship edge in the asset graph connecting
    the source and target assets with the specified type and weight.

    Args:
        source: The source asset for the relationship.
        target: The target asset for the relationship.
        relationship_type: Type of relationship (e.g., "correlation", "ownership").
        weight: Relationship strength from 0.0 to 1.0. Defaults to 1.0.

    Returns:
        The created Relationship object.

    Raises:
        ValueError: If source or target asset is not in the graph.
        ValueError: If weight is not between 0.0 and 1.0.

    Example:
        >>> graph.add_relationship(stock_a, stock_b, "correlation", 0.85)
        Relationship(source='AAPL', target='MSFT', type='correlation')
    """
```

### Inline Comments

Use inline comments sparingly for complex logic:

```python
# Calculate weighted average, excluding zero-weight items
weighted_sum = sum(
    value * weight
    for value, weight in zip(values, weights)
    if weight > 0  # Skip zero weights to avoid division issues
)
```

## Error Handling

### Exception Guidelines

1. **Use specific exceptions** rather than generic ones:

```python
# Good
raise ValueError(f"Asset '{asset_id}' not found in graph")

# Avoid
raise Exception("Asset not found")
```

2. **Provide context** in exception messages:

```python
raise ValueError(
    f"Invalid relationship weight {weight}. "
    f"Weight must be between 0.0 and 1.0."
)
```

3. **Create custom exceptions** for domain-specific errors:

```python
class AssetNotFoundError(Exception):
    """Raised when an asset cannot be found in the graph."""
    pass

class InvalidRelationshipError(Exception):
    """Raised when a relationship cannot be created."""
    pass
```

### Try/Except Blocks

Keep try blocks focused and specific:

```python
# Good
try:
    asset = self._assets[asset_id]
except KeyError:
    raise AssetNotFoundError(f"Asset '{asset_id}' not found")

# Avoid catching all exceptions
try:
    asset = self._assets[asset_id]
except Exception:  # Too broad
    raise AssetNotFoundError(f"Asset '{asset_id}' not found")
```

## Testing Standards

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_models.py
│   ├── test_graph.py
│   └── test_analysis.py
└── integration/             # Integration tests
    ├── test_workflows.py
    └── test_api.py
```

### Test Naming

Use descriptive test names that explain what is being tested:

```python
# Good
def test_add_asset_with_valid_data_succeeds():
    ...

def test_add_asset_with_duplicate_id_raises_error():
    ...

# Avoid
def test_add():
    ...

def test_1():
    ...
```

### Test Coverage

- **Target:** 80% or higher code coverage
- **New features:** Must include tests
- **Bug fixes:** Must include a test that would have caught the bug

## Security Considerations

### Input Validation

Always validate external input:

```python
def process_user_input(asset_id: str) -> Asset:
    # Validate input format
    if not asset_id or not isinstance(asset_id, str):
        raise ValueError("Asset ID must be a non-empty string")

    # Sanitize input
    asset_id = asset_id.strip().upper()

    # Validate against allowed patterns
    if not re.match(r'^[A-Z0-9]{1,10}$', asset_id):
        raise ValueError("Asset ID must be 1-10 alphanumeric characters")

    return self.get_asset(asset_id)
```

### Sensitive Data

- Never log sensitive information (passwords, API keys, personal data)
- Use environment variables for configuration secrets
- Never commit sensitive data to version control

### Dependencies

- Keep dependencies up to date
- Review security advisories for dependencies
- Use `pip-audit` or similar tools to check for vulnerabilities

## Additional Resources

- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [AI_RULES.md](AI_RULES.md) - Tech stack and AI assistant guidelines
- [TESTING.md](TESTING.md) - Detailed testing documentation
- [PEP 8](https://peps.python.org/pep-0008/) - Python style guide
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
