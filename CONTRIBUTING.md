# Contributing to Financial Asset Relationship Database

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Submitting Changes](#submitting-changes)
- [Project Structure](#project-structure)

## Code of Conduct

This project adheres to a code of conduct that fosters an open and welcoming environment. Please be respectful and professional in all interactions.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Virtual environment tool (venv, virtualenv, or conda)

### Installation

1. Fork the repository on GitHub
2. Clone your fork locally:

   ```bash
   git clone https://github.com/YOUR_USERNAME/financial-asset-relationship-db.git
   cd financial-asset-relationship-db
   ```

3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/mohavro/financial-asset-relationship-db.git
   ```

## Development Setup

### 1. Create a Virtual Environment

```bash
python -m venv .venv
```

### 2. Activate the Virtual Environment

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

```cmd
.venv\Scripts\activate.bat
```

**macOS/Linux:**

```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

Or use the Makefile:

```bash
make install-dev
```

### 4. Install Pre-commit Hooks

```bash
pre-commit install
```

Or use the Makefile:

```bash
make pre-commit
```

## Development Workflow

### 1. Create a Branch

Always create a new branch for your work:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-number
```

Branch naming conventions:

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions/improvements

### 2. Make Your Changes

- Follow the coding standards (see below)
- Write or update tests for your changes
- Update documentation as needed
- Keep commits small and focused

### 3. Run Checks Locally

Before committing, run all checks:

```bash
# Format code
make format

# Run linters
make lint

# Run type checker
make type-check

# Run tests
make test

# Or run all checks at once
make check
```

### 4. Commit Your Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "Add feature: brief description

More detailed explanation of what changed and why.
Reference any related issues: #123"
```

Commit message guidelines:

- Use present tense ("Add feature" not "Added feature")
- First line should be concise (50 chars or less)
- Separate subject from body with blank line
- Body should explain what and why, not how

### 5. Push and Create Pull Request

```bash
git push origin your-branch-name
```

Then create a pull request on GitHub with:

- Clear description of changes
- Reference to related issues
- Screenshots (if UI changes)
- Test results

## Coding Standards

### Python Style

We follow PEP 8 with some modifications:

- **Line length:** 120 characters (not 79)
- **Formatting:** Use Black for automatic formatting
- **Import sorting:** Use isort
- **Type hints:** Add type hints to all functions
- **Docstrings:** Use Google or NumPy style

### Code Organization

```python
# Standard library imports
import os
from typing import Dict, List

# Third-party imports
import numpy as np
import plotly.graph_objects as go

# Local imports
from src.models.financial_models import Asset
from src.logic.asset_graph import AssetRelationshipGraph
```

### Naming Conventions

- **Variables/Functions:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_CASE`
- **Private methods:** `_leading_underscore`

### Documentation

Every public class and function should have a docstring:

```python
def calculate_metrics(self) -> Dict[str, Any]:
    """Calculate relationship strength metrics.

    Returns:
        Dict containing metrics including total_assets, total_relationships,
        average_relationship_strength, and more.

    Raises:
        ValueError: If graph is empty or invalid.
    """
    pass
```

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests
│   ├── test_models.py
│   └── test_graph.py
└── integration/         # Integration tests
    └── test_workflows.py
```

### Writing Tests

1. **Use descriptive test names:**

   ```python
   def test_asset_creation_with_valid_data():
       """Test that a valid asset can be created."""
   ```

2. **Use fixtures from conftest.py:**

   ```python
   def test_add_asset(empty_graph, sample_equity):
       empty_graph.add_asset(sample_equity)
       assert len(empty_graph.assets) == 1
   ```

3. **Test edge cases:**
   - Empty inputs
   - Null/None values
   - Boundary conditions
   - Invalid data

4. **Use pytest markers:**

   ```python
   @pytest.mark.unit
   def test_something():
       pass

   @pytest.mark.slow
   def test_something_slow():
       pass
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_models.py

# Run with coverage
pytest --cov=src

# Run only unit tests
pytest -m unit

# Run with verbose output
pytest -v
```

Or use the Makefile:

```bash
make test        # With coverage
make test-fast   # Without coverage
```

### Test Coverage Goals

- **Target:** 80% or higher
- **New features:** Must have tests
- **Bug fixes:** Add test that would have caught the bug

## Submitting Changes

### Pull Request Process

1. **Update documentation:**
   - Update README.md if needed
   - Update docstrings
   - Add comments for complex logic

2. **Ensure all checks pass:**
   - All tests pass
   - Linters show no errors
   - Type checking passes
   - Code is formatted

3. **Update CHANGELOG.md** (if exists) with:
   - Type of change (Added, Changed, Fixed, etc.)
   - Brief description
   - Issue reference if applicable

4. **Create Pull Request:**
   - Use descriptive title
   - Fill out PR template
   - Request review from maintainers
   - Link related issues

### PR Review Process

- Maintainers will review your PR
- Address any feedback or requested changes
- Keep discussion focused and professional
- Be patient - reviews take time

### After PR is Merged

- Delete your feature branch (both locally and on GitHub)
- Pull the latest changes from upstream:
  ```bash
  git checkout main
  git pull upstream main
  ```

### Branch Cleanup Best Practices

To keep the repository clean and organized:

1. **Delete merged branches:**
   - GitHub can automatically delete branches after PR merge
   - Manually delete local branches: `git branch -d branch-name`
   - Delete remote branches: `git push origin --delete branch-name`

2. **Avoid long-lived feature branches:**
   - Keep branches short-lived (ideally < 2 weeks)
   - Break large features into smaller PRs
   - Regularly sync with main to avoid conflicts

3. **Stale branch policy:**
   - Branches inactive for 90+ days may be automatically deleted
   - You'll receive a warning before deletion
   - Important branches should be documented in issues

4. **Branch naming:**
   - Use descriptive names that indicate purpose
   - Follow the naming conventions listed above
   - Avoid generic names like "test" or "temp"

See [BRANCH_CLEANUP_ANALYSIS.md](BRANCH_CLEANUP_ANALYSIS.md) for detailed branch management guidelines.

## Project Structure

```
financial-asset-relationship-db/
├── .github/
│   ├── workflows/           # CI/CD workflows
│   └── copilot-instructions.md
├── src/
│   ├── analysis/           # Analysis algorithms
│   ├── data/               # Data management
│   ├── logic/              # Core business logic
│   ├── models/             # Data models
│   ├── reports/            # Report generation
│   └── visualizations/     # Visualization code
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── app.py                  # Main application
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies
├── pyproject.toml          # Project configuration
├── Makefile                # Development commands
└── README.md               # Project documentation
```

### Key Files

- **app.py:** Main Gradio application entry point
- **src/logic/asset_graph.py:** Core graph algorithms
- **src/models/financial_models.py:** Domain models
- **src/data/sample_data.py:** Sample data generation
- **pyproject.toml:** Tool configurations

## Need Help?

- Check existing issues and pull requests
- Read the documentation in README.md
- Review AI_RULES.md for tech stack guidelines
- Ask questions in issue comments
- Contact maintainers

## Recognition

Contributors will be recognized in:

- GitHub contributors list
- Release notes
- Project documentation (if significant contribution)

Thank you for contributing! 🎉
