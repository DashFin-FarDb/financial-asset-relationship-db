# Contributing to Financial Asset Relationship Database

Thank you for your interest in contributing. This document explains how to set up the project, follow the repository standards, and keep dependency management consistent.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Submitting Changes](#submitting-changes)
- [Project Structure](#project-structure)
- [Dependency Management](#dependency-management)

## Code of Conduct

This project expects professional, respectful collaboration in issues, pull requests, and review discussions.

## Getting Started

### Prerequisites

- Python 3.10 or higher (Python 3.12 recommended)
- Git
- A virtual environment tool such as `venv`, `virtualenv`, or `conda`

### Installation

1. Fork the repository on GitHub.
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

### 1. Create a virtual environment

```bash
python -m venv .venv
```

### 2. Activate the virtual environment

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

### 3. Install dependencies

Choose one of the supported setups below.

**Runtime only**

```bash
pip install -r requirements.txt
```

**Core development setup**

```bash
pip install -e ".[dev]"
```

**Full contributor tooling**

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 4. Install pre-commit hooks

```bash
pre-commit install
```

Or use the Makefile:

```bash
make pre-commit
```

## Development Workflow

### 1. Create a branch

Always create a new branch for your work:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-number
```

Branch naming conventions:

- `feature/description` - new features
- `bugfix/description` - bugfixes
- `docs/description` - documentation updates
- `refactor/description` - code refactoring
- `test/description` - test additions or improvements

### 2. Make your changes

- Follow the coding standards below.
- Write or update tests for your changes.
- Update documentation when behavior, setup, or policy changes.
- Keep commits small and focused.

### 3. Run checks locally

Before committing, run the relevant checks:

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

### 4. Commit your changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "Add feature: brief description

More detailed explanation of what changed and why.
Reference any related issues: #123"
```

Commit message guidelines:

- Use present tense ("Add feature", not "Added feature")
- Keep the first line concise
- Separate subject from body with a blank line
- Explain what changed and why

### 5. Push and create a pull request

```bash
git push origin your-branch-name
```

Then create a pull request on GitHub with:

- a clear description of the change
- references to related issues
- screenshots if the UI changed
- relevant test results

## Coding Standards

### Python style

This repository follows PEP 8 with the following project conventions:

- **Line length:** 120 characters
- **Formatting:** Black
- **Import sorting:** isort
- **Type hints:** expected on new or modified functions where practical
- **Docstrings:** Google style or NumPy style

### Code organization

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

### Naming conventions

- **Variables / functions:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_CASE`
- **Private methods:** `_leading_underscore`

### Documentation

Public classes and functions should generally have a docstring:

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

### Test structure

```text
tests/
├── conftest.py
├── unit/
│   ├── test_models.py
│   └── test_graph.py
└── integration/
    └── test_workflows.py
```

### Writing tests

1. Use descriptive test names:

   ```python
   def test_asset_creation_with_valid_data():
       """Test that a valid asset can be created."""
   ```

2. Use fixtures from `conftest.py`:

   ```python
   def test_add_asset(empty_graph, sample_equity):
       empty_graph.add_asset(sample_equity)
       assert len(empty_graph.assets) == 1
   ```

3. Test edge cases:
   - empty inputs
   - `None` values
   - boundary conditions
   - invalid data

4. Use pytest markers:

   ```python
   @pytest.mark.unit
   def test_something():
       pass

   @pytest.mark.slow
   def test_something_slow():
       pass
   ```

### Running tests

```bash
# Run all tests
pytest

# Run a specific test file
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
make test
make test-fast
```

### Test coverage goals

- **Target:** 80% or higher
- **New features:** should include tests
- **Bug fixes:** should include a regression test where practical

## Submitting Changes

### Pull request process

1. Update documentation where needed:
   - README changes if setup or usage changed
   - docstrings where behavior changed
   - comments for non-obvious logic

2. Ensure relevant checks pass:
   - tests
   - linters
   - type checking
   - formatting

3. Update `CHANGELOG.md` if the repository is maintaining one for the affected change type.

4. Create the pull request:
   - use a descriptive title
   - fill out the PR template
   - request review from maintainers
   - link related issues

### PR review process

- Maintainers will review the PR.
- Address feedback directly and keep follow-up commits focused.
- Keep the discussion technical and specific.

### After the PR is merged

- Delete the feature branch locally and on GitHub.
- Pull the latest changes from upstream:

  ```bash
  git checkout main
  git pull upstream main
  ```

### Branch cleanup best practices

1. Delete merged branches:
   - GitHub can automatically delete branches after merge.
   - Delete local branches with `git branch -d branch-name`.
   - Delete remote branches with `git push origin --delete branch-name`.

2. Avoid long-lived feature branches:
   - keep branches short-lived where possible
   - break large changes into smaller PRs
   - sync with `main` regularly

3. Stale branch policy:
   - branches inactive for long periods may be removed
   - important long-lived work should be tracked in issues

4. Branch naming:
   - use descriptive branch names
   - follow the naming conventions above
   - avoid generic names such as `test` or `temp`

See [BRANCH_CLEANUP_ANALYSIS.md](BRANCH_CLEANUP_ANALYSIS.md) for more branch-management detail.

## Project Structure

```text
financial-asset-relationship-db/
├── .github/
│   ├── workflows/           # CI/CD workflows
│   └── copilot-instructions.md
├── src/
│   ├── analysis/            # Analysis algorithms
│   ├── data/                # Data management
│   ├── logic/               # Core business logic
│   ├── models/              # Data models
│   ├── reports/             # Report generation
│   └── visualizations/      # Visualization code
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── app.py                   # Main application entry point
├── requirements.txt         # Runtime / deployment dependencies
├── requirements-dev.txt     # Supplemental development, test, and CI tooling
├── pyproject.toml           # Project metadata and editable-install configuration
├── Makefile                 # Development commands
└── README.md                # Project documentation
```

### Key files

- **app.py:** main application entry point
- **api/main.py:** API entry point
- **src/logic/asset_graph.py:** core graph algorithms
- **src/models/financial_models.py:** domain models
- **src/data/sample_data.py:** sample data generation
- **pyproject.toml:** project metadata and tool configuration

## Dependency Management

This repository uses three dependency surfaces. Each has a distinct role and should be edited accordingly.

### 1. `requirements.txt`

**Purpose:** runtime / deployment dependency surface.

Use this file for:

- production-style installs
- deployment environments
- runtime validation in CI

Policy:

- Keep runtime or deployment dependencies here, plus intentional **security override pins** for transitive packages (e.g., `urllib3`, `zipp`) where a vulnerability advisory requires a minimum version.
- Use exact pins for stability-critical packages where needed.
- Keep comments short and factual.
- When a runtime dependency is added or changed, update both `requirements.txt` and `[project.dependencies]` in `pyproject.toml`.

### 2. `requirements-dev.txt`

**Purpose:** supplemental development, test, and CI tooling installed on top of `requirements.txt`.

Use this file for:

- local contributor setup with the full toolchain
- test-only or CI-only libraries
- optional repository tools not required for editable install

Policy:

- This file is standalone.
- It must contain only standard parseable requirement specifiers.
- Do not use pip include directives such as `-r requirements.txt`.
- Install it with:

  ```bash
  pip install -r requirements.txt -r requirements-dev.txt
  ```

- Core dev tools should also appear in `[project.optional-dependencies].dev`.
- Optional or specialized tools may remain only in `requirements-dev.txt`.

### 3. `pyproject.toml`

**Purpose:** project metadata and editable-install surface.

Use this file for:

- package metadata
- build-system configuration
- the dependency surface needed for `pip install -e .`
- the optional core contributor extra `.[dev]`

Policy:

- `[project.dependencies]` must be sufficient for `pip install -e .` and import of the real repository entrypoints.
- `[project.optional-dependencies].dev` should define the minimal core contributor toolchain.
- The `dev` extra should remain a subset of `requirements-dev.txt`.
- Do not use `pyproject.toml` as a substitute lockfile.

### Supported install paths

**Runtime only**

```bash
pip install -r requirements.txt
```

**Core development setup**

```bash
pip install -e ".[dev]"
```

**Full contributor tooling**

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Updating dependencies

Use this checklist when changing dependencies:

1. Identify the change type:
   - **New runtime dependency:** add it to `requirements.txt` and `[project.dependencies]`
   - **New core dev tool:** add it to `requirements-dev.txt` and `[project.optional-dependencies].dev`
   - **New optional repository tool:** add it only to `requirements-dev.txt`
   - **Security or transitive override pin:** place it in the file for the environment that actually needs it and document why

2. Check compatibility:
   - verify Python 3.10+ support
   - run the relevant install commands
   - run `pip check`
   - validate entrypoint imports where applicable

3. Keep the files aligned:
   - remove avoidable version drift
   - keep comments accurate
   - update this document when dependency policy changes

## Need Help?

- Check existing issues and pull requests.
- Read the project documentation in `README.md`.
- Review repository-specific guidance such as `AI_RULES.md` if applicable.
- Ask focused questions in issue comments or pull request threads.
