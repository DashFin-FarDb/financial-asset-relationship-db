# Coding Guidelines

## Financial Asset Relationship Database - Coding Standards

This document establishes the coding standards and best practices for all contributors to the Financial Asset Relationship Database project.

---

## Table of Contents

1. [General Principles](#general-principles)
2. [Python Guidelines](#python-guidelines)
3. [TypeScript/React Guidelines](#typescriptreact-guidelines)
4. [Code Organization](#code-organization)
5. [Naming Conventions](#naming-conventions)
6. [Documentation Standards](#documentation-standards)
7. [Testing Requirements](#testing-requirements)
8. [Version Control](#version-control)

---

## General Principles

### Core Values

1. **Readability**: Code should be self-documenting and easy to understand
2. **Maintainability**: Write code that others can easily modify
3. **Simplicity**: Prefer simple solutions over complex ones
4. **Consistency**: Follow established patterns throughout the codebase
5. **Completeness**: No partial implementations or placeholder code

### Design Philosophy

- **Modularity**: Create small, focused components (aim for < 100 lines)
- **Single Responsibility**: Each function/class should do one thing well
- **DRY (Don't Repeat Yourself)**: Extract common logic into reusable units
- **YAGNI (You Aren't Gonna Need It)**: Don't build features speculatively

---

## Python Guidelines

### Style Guide

We follow PEP 8 with these modifications:

| Rule | Standard | Our Modification |
|------|----------|-----------------|
| Line length | 79 chars | **120 chars** |
| Indentation | 4 spaces | 4 spaces |
| Quotes | Either | **Double quotes preferred** |

### Code Formatting

Use automated tools for consistency:

```bash
# Format code with Black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Or use Makefile
make format
```

### Import Organization

Organize imports in this order:

```python
# 1. Standard library imports
import os
import sys
from typing import Dict, List, Optional

# 2. Third-party imports
import numpy as np
import pandas as pd
from fastapi import FastAPI

# 3. Local application imports
from src.models.financial_models import Asset, Equity
from src.logic.asset_graph import AssetRelationshipGraph
```

### Type Hints

**Required** for all function signatures:

```python
# Good
def calculate_strength(asset1: Asset, asset2: Asset) -> float:
    """Calculate relationship strength between two assets."""
    pass

# Bad - missing type hints
def calculate_strength(asset1, asset2):
    pass
```

### Docstrings

Use Google-style docstrings for all public functions and classes:

```python
def add_relationship(
    self,
    source_id: str,
    target_id: str,
    relationship_type: str,
    strength: float
) -> bool:
    """Add a relationship between two assets.

    Args:
        source_id: The source asset identifier.
        target_id: The target asset identifier.
        relationship_type: Type of relationship (e.g., 'same_sector').
        strength: Relationship strength from 0.0 to 1.0.

    Returns:
        True if relationship was added successfully, False otherwise.

    Raises:
        ValueError: If strength is not between 0.0 and 1.0.
        KeyError: If source or target asset not found.

    Example:
        >>> graph.add_relationship('AAPL', 'MSFT', 'same_sector', 0.8)
        True
    """
    pass
```

### Error Handling

- **Do not** use broad try/except blocks for general error handling
- **Do** let exceptions propagate for easier debugging
- **Do** use specific exception types when catching is necessary

```python
# Bad - catches everything
try:
    result = process_data(data)
except Exception:
    return None

# Good - specific handling
try:
    result = process_data(data)
except ValueError as e:
    logger.error(f"Invalid data format: {e}")
    raise
```

### Data Classes

Use dataclasses for structured data:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Asset:
    """Base class for all financial assets."""

    id: str
    name: str
    asset_class: AssetClass
    value: float
    currency: str = "USD"
    metadata: Optional[dict] = None
```

### Enumerations

Use enums for fixed sets of values:

```python
from enum import Enum, auto

class AssetClass(Enum):
    """Classification of financial assets."""

    EQUITY = auto()
    BOND = auto()
    COMMODITY = auto()
    CURRENCY = auto()
```

---

## TypeScript/React Guidelines

### TypeScript Configuration

- **Strict mode**: Always enabled
- **No implicit any**: Avoid `any` type when possible

### Component Structure

```typescript
// 1. Imports
import React, { useState, useEffect } from 'react';
import { AssetData } from '@/types';

// 2. Type definitions
interface AssetCardProps {
  asset: AssetData;
  onClick?: (id: string) => void;
}

// 3. Component definition
export const AssetCard: React.FC<AssetCardProps> = ({ asset, onClick }) => {
  // State hooks
  const [isExpanded, setIsExpanded] = useState(false);

  // Effect hooks
  useEffect(() => {
    // Side effects
  }, [asset.id]);

  // Event handlers
  const handleClick = () => {
    onClick?.(asset.id);
  };

  // Render
  return (
    <div className="asset-card" onClick={handleClick}>
      {/* Component content */}
    </div>
  );
};
```

### Styling

- Use **Tailwind CSS** for styling
- Avoid inline styles except for dynamic values
- Use consistent spacing and color tokens

```tsx
// Good
<div className="p-4 bg-white rounded-lg shadow-md">

// Avoid
<div style={{ padding: '16px', backgroundColor: 'white' }}>
```

---

## Code Organization

### Directory Structure

```
src/
├── data/           # Data access and management
├── logic/          # Core business logic
├── models/         # Data models and types
├── reports/        # Report generation
├── visualizations/ # Chart components
└── utils/          # Shared utilities

frontend/
├── app/            # Next.js app router
├── components/     # React components
├── lib/            # Utility functions
├── hooks/          # Custom React hooks
└── types/          # TypeScript types
```

### File Organization

Within each file:

1. Imports
2. Constants
3. Type definitions
4. Helper functions (private)
5. Main class/component
6. Exports

---

## Naming Conventions

### Python

| Element | Convention | Example |
|---------|------------|---------|
| Variables | snake_case | `asset_count` |
| Functions | snake_case | `calculate_metrics()` |
| Classes | PascalCase | `AssetRelationshipGraph` |
| Constants | UPPER_SNAKE | `MAX_RELATIONSHIPS` |
| Private | _leading | `_internal_method()` |
| Modules | snake_case | `asset_graph.py` |

### TypeScript

| Element | Convention | Example |
|---------|------------|---------|
| Variables | camelCase | `assetCount` |
| Functions | camelCase | `calculateMetrics()` |
| Classes | PascalCase | `AssetService` |
| Interfaces | PascalCase | `AssetData` |
| Constants | UPPER_SNAKE | `MAX_RETRIES` |
| Components | PascalCase | `AssetCard.tsx` |

### Git Branches

| Type | Pattern | Example |
|------|---------|---------|
| Feature | feature/description | `feature/add-currency-support` |
| Bugfix | bugfix/description | `bugfix/fix-chart-render` |
| Docs | docs/description | `docs/update-api-guide` |
| Refactor | refactor/description | `refactor/simplify-graph` |

---

## Documentation Standards

### Code Comments

```python
# Good - explains WHY
# Use deterministic seed for consistent graph layout across sessions
np.random.seed(42)

# Bad - explains WHAT (obvious from code)
# Set seed to 42
np.random.seed(42)
```

### README Files

Each major directory should have a README explaining:

- Purpose of the directory
- Key files and their roles
- Usage examples

### API Documentation

- Document all public API endpoints
- Include request/response examples
- Specify error codes and meanings

---

## Testing Requirements

### Coverage Targets

| Category | Minimum |
|----------|---------|
| Unit tests | 80% |
| Integration | Key flows |
| Frontend | Component tests |

### Test Naming

```python
def test_add_asset_with_valid_data_succeeds():
    """Adding an asset with valid data should succeed."""
    pass

def test_add_asset_with_invalid_id_raises_error():
    """Adding an asset with invalid ID should raise ValueError."""
    pass
```

### Test Organization

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_graph.py
│   └── test_utils.py
├── integration/
│   ├── test_api.py
│   └── test_workflows.py
└── conftest.py  # Shared fixtures
```

### Required Test Cases

For each feature, include:

1. Happy path test
2. Edge cases
3. Error conditions
4. Boundary values

---

## Version Control

### Commit Messages

```
<type>: <short description>

<longer description if needed>

Refs: #<issue-number>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructure
- `test`: Test additions
- `chore`: Maintenance

### Pull Request Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No linting errors
- [ ] No type errors
- [ ] Reviewed own changes

---

## Tools and Automation

### Pre-commit Hooks

Install and use pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

### Makefile Commands

```bash
make format      # Format code
make lint        # Run linters
make type-check  # Run mypy
make test        # Run tests
make check       # All checks
```

### IDE Configuration

Recommended VS Code extensions:

- Python (Microsoft)
- Pylance
- ESLint
- Prettier
- Tailwind CSS IntelliSense

---

## Appendix: Quick Reference

### Python Checklist

- [ ] Type hints on all functions
- [ ] Docstrings on public functions
- [ ] Black formatted
- [ ] Imports sorted with isort
- [ ] No broad exception handling

### TypeScript Checklist

- [ ] Strict mode compliant
- [ ] Interfaces for props
- [ ] No `any` types
- [ ] Components have default exports
- [ ] Tailwind for styling

---

*Last Updated: January 2025*

See also:
- [AI_RULES.md](../AI_RULES.md) - Tech stack and library guidelines
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution process
- [tech_spec.md](tech_spec.md) - Technical specification
