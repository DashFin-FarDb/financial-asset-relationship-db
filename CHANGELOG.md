# Changelog

## [Unreleased]

### Fixed

- Removed inappropriate CI/CD workflow files that were causing build failures:
  - Deleted `.github/workflows/objective-c-xcode.yml` - Xcode/Objective-C workflow not applicable to Python/JavaScript project
  - Deleted `.github/workflows/go.yml` - Go workflow not applicable to Python/JavaScript project
  - Deleted `.github/workflows/dotnet-desktop.yml` - .NET Desktop workflow not applicable to Python/JavaScript project

### Improved

- Cleaned up CI/CD configuration to only include relevant workflows for the project's tech stack (Python, JavaScript/TypeScript, Next.js)
- Reduced CI/CD execution time and resource usage by removing unnecessary workflow runs
- Improved maintainability by removing duplicate and conflicting workflow configurations

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Comprehensive testing infrastructure with pytest
- Unit tests for financial models (test_financial_models.py)
- Unit tests for asset graph logic (test_asset_graph.py)
- Test fixtures in conftest.py for reusable test data
- Development dependencies in requirements-dev.txt
- Linting configuration (.flake8, pyproject.toml)
- Code formatting tools (black, isort)
- Type checking with mypy
- Pre-commit hooks configuration
- EditorConfig for consistent formatting
- Consolidated CI workflow (.github/workflows/ci.yml)
- Code coverage reporting with pytest-cov
- Makefile for common development tasks
- CONTRIBUTING.md guide for developers
- AUDIT_REPORT.md comprehensive code audit
- CHANGELOG.md (this file)

### Changed

- Consolidated redundant Python workflows into single ci.yml
- Updated .gitignore to include test artifacts and cache directories
- Improved CI/CD pipeline with dependency caching
- Enhanced workflow to include linting, type checking, and security scanning

### Removed

- 23 irrelevant workflow files (docker, .NET, Next.js, Node.js, etc.)
- python-app.yml (merged into ci.yml)
- python-package.yml (merged into ci.yml)
- pylint.yml (merged into ci.yml)
- super-linter.yml (replaced with specific linters)

## [1.0.0] - 2024-10-30

### Added

- Initial release
- Financial Asset Relationship Database with 3D visualization
- Support for multiple asset classes (Equity, Bond, Commodity, Currency, Derivative)
- Automatic relationship discovery between assets
- Regulatory event tracking and impact modeling
- Interactive Gradio web interface
- 3D network visualization with Plotly
- Metrics and analytics dashboard
- Schema and business rules reporting
- Asset explorer with detailed information
- Real-time data fetching with yfinance
- Sample data generation
- Comprehensive documentation (README.md, AI_RULES.md)

### Asset Classes

- Equities with P/E ratios, dividend yields, EPS
- Fixed Income with yield, duration, credit ratings
- Commodities with futures and spot prices
- Currencies with exchange rates
- Regulatory events with impact scoring

### Relationship Types

- Sector affinity (same_sector)
- Corporate links (corporate_bond_to_equity)
- Commodity exposure
- Currency risk
- Income comparison (dividend vs yield)
- Event impact

### Visualizations

- 3D network graph with deterministic positioning
- Asset class color coding
- Relationship strength visualization
- Metrics dashboard
- Schema documentation

---

## Version History

### Version Numbering

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

### Unreleased Changes

Changes in the `[Unreleased]` section are features and fixes that have been committed but not yet released.

### Release Process

1. Update CHANGELOG.md
2. Update version in pyproject.toml
3. Commit changes
4. Tag release: `git tag -a v1.0.0 -m "Release v1.0.0"`
5. Push tags: `git push --tags`

---

[Unreleased]: https://github.com/mohavro/financial-asset-relationship-db/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/mohavro/financial-asset-relationship-db/releases/tag/v1.0.0
