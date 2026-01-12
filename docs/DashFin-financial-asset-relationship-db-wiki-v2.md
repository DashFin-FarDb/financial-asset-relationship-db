# DashFin Financial Asset Relationship Database Wiki v2

## Welcome to the DashFin Wiki

This wiki provides comprehensive documentation for the Financial Asset Relationship Database project, a system designed to visualize and analyze interconnections between financial assets.

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Core Concepts](#core-concepts)
4. [User Guide](#user-guide)
5. [Architecture](#architecture)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Overview

### What is DashFin?

DashFin (Financial Asset Relationship Database) is a comprehensive visualization platform that maps relationships between financial instruments across multiple asset classes:

- **Equities** - Stocks and shares
- **Fixed Income** - Bonds and debt instruments
- **Commodities** - Raw materials and futures
- **Currencies** - Foreign exchange pairs
- **Regulatory Events** - Corporate actions and SEC filings

### Key Features

| Feature | Description |
|---------|-------------|
| 3D Network Visualization | Interactive graph showing asset interconnections |
| Cross-Asset Analysis | Automatic relationship discovery |
| Real-time Metrics | Network statistics and strength analysis |
| Dual Interface | Gradio UI + Modern Next.js frontend |
| REST API | Programmatic access to all features |

### Version History

| Version | Release | Highlights |
|---------|---------|------------|
| v2.0 | Jan 2025 | Next.js frontend, FastAPI backend, Supabase integration |
| v1.5 | 2024 | Enhanced visualizations, regulatory events |
| v1.0 | 2024 | Initial Gradio implementation |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ (for Next.js frontend)
- Git

### Quick Installation

#### Option 1: Gradio UI (Python Only)

```bash
# Clone repository
git clone <repository-url>
cd financial-asset-relationship-db

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

Access at: `http://localhost:7860`

#### Option 2: Full Stack (Recommended)

```bash
# Start both servers
./run-dev.sh  # Windows: run-dev.bat
```

Access:
- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

---

## Core Concepts

### Asset Classes

#### Equities

Equity assets represent ownership in companies. Key attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| symbol | string | Trading symbol (e.g., AAPL) |
| sector | string | Industry sector |
| pe_ratio | float | Price-to-earnings ratio |
| dividend_yield | float | Annual dividend yield |
| eps | float | Earnings per share |

#### Bonds

Fixed income instruments with defined terms:

| Attribute | Type | Description |
|-----------|------|-------------|
| symbol | string | Bond identifier |
| issuer | string | Issuing entity |
| yield_rate | float | Annual yield |
| duration | float | Interest rate sensitivity |
| credit_rating | string | Credit quality rating |

#### Commodities

Physical goods and their derivatives:

| Attribute | Type | Description |
|-----------|------|-------------|
| symbol | string | Commodity code |
| commodity_type | string | Category (precious metals, energy, etc.) |
| contract_unit | string | Trading unit specification |

#### Currencies

Foreign exchange pairs:

| Attribute | Type | Description |
|-----------|------|-------------|
| symbol | string | Currency pair (e.g., EUR/USD) |
| base_currency | string | Base currency |
| quote_currency | string | Quote currency |
| exchange_rate | float | Current rate |

### Relationship Types

The system automatically discovers and categorizes relationships:

#### Same Sector
- **Type**: Bidirectional
- **Strength**: Based on sector alignment
- **Example**: AAPL ↔ MSFT (both Technology)

#### Corporate Bond to Equity
- **Type**: Directional
- **Strength**: Based on issuer match
- **Example**: AAPL Bond → AAPL Stock

#### Commodity Exposure
- **Type**: Directional
- **Strength**: Based on business exposure
- **Example**: Gold → Mining Company

#### Currency Risk
- **Type**: Directional
- **Strength**: Based on revenue geography
- **Example**: EUR/USD → European Company

#### Income Comparison
- **Type**: Bidirectional
- **Strength**: Based on yield similarity
- **Example**: High-yield Bond ↔ Dividend Stock

### Relationship Strength

Strength values range from 0.0 to 1.0:

| Range | Interpretation |
|-------|----------------|
| 0.8 - 1.0 | Strong relationship |
| 0.5 - 0.8 | Moderate relationship |
| 0.2 - 0.5 | Weak relationship |
| 0.0 - 0.2 | Minimal relationship |

---

## User Guide

### Using the Gradio Interface

1. **Launch Application**: Run `python app.py`
2. **Navigate Tabs**: Use tabs for different views
3. **Interact with 3D Graph**:
   - Click and drag to rotate
   - Scroll to zoom
   - Hover for details
4. **View Metrics**: Check network statistics panel
5. **Explore Assets**: Use asset explorer to filter

### Using the Next.js Frontend

1. **Dashboard**: Overview of all assets and relationships
2. **3D Visualization**: Full-screen interactive graph
3. **Asset Details**: Click nodes for detailed view
4. **Search**: Filter assets by type, sector, or symbol

### API Usage

```python
import requests

# Get all assets
response = requests.get("http://localhost:8000/api/assets")
assets = response.json()

# Get visualization data
response = requests.get("http://localhost:8000/api/visualization")
graph_data = response.json()
```

---

## Architecture

### System Components

```
┌─────────────────────────────────────────┐
│           Presentation Layer            │
│  ┌─────────────┐  ┌─────────────┐      │
│  │   Gradio    │  │   Next.js   │      │
│  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────┘
              │                │
              ▼                ▼
┌─────────────────────────────────────────┐
│             Service Layer               │
│  ┌───────────────────────────────┐     │
│  │        FastAPI Backend        │     │
│  └───────────────────────────────┘     │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│            Business Logic               │
│  ┌─────────────────────────────────┐   │
│  │   AssetRelationshipGraph        │   │
│  │   - add_asset()                 │   │
│  │   - build_relationships()       │   │
│  │   - calculate_metrics()         │   │
│  │   - get_3d_visualization_data() │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│             Data Layer                  │
│  ┌─────────────┐  ┌─────────────┐      │
│  │ Sample Data │  │  Supabase   │      │
│  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────┘
```

### Directory Structure

```
financial-asset-relationship-db/
├── api/                    # FastAPI backend
│   └── main.py
├── src/
│   ├── data/              # Data management
│   │   ├── database.py    # Database connection
│   │   └── sample_data.py # Sample data generation
│   ├── logic/             # Business logic
│   │   └── asset_graph.py # Core graph engine
│   ├── models/            # Data models
│   │   └── financial_models.py
│   ├── reports/           # Report generation
│   └── visualizations/    # Chart components
├── frontend/              # Next.js application
│   ├── app/              # App router pages
│   ├── components/       # React components
│   └── lib/              # Utilities
├── tests/                 # Test suite
├── docs/                  # Documentation
├── app.py                 # Gradio entry point
└── requirements.txt       # Python dependencies
```

---

## API Reference

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/assets` | List all assets |
| GET | `/api/assets/{id}` | Get asset by ID |
| GET | `/api/relationships` | List relationships |
| GET | `/api/visualization` | Get graph data |
| GET | `/api/metrics` | Get network metrics |

### Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request |
| 404 | Not found |
| 500 | Server error |

---

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Find process using port
lsof -i :7860  # macOS/Linux
netstat -ano | findstr :7860  # Windows

# Kill process or use different port
python app.py --server-port 7861
```

#### Module Not Found

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### Database Connection Failed

1. Check `.env` file exists with correct credentials
2. Verify Supabase project is active
3. Check network connectivity

#### Visualization Not Loading

1. Clear browser cache
2. Check browser console for errors
3. Verify API is running at port 8000

---

## FAQ

### General Questions

**Q: What data sources does DashFin use?**

A: DashFin uses Yahoo Finance (yfinance) for real-time market data and supports custom data via the Supabase database.

**Q: Can I add custom asset types?**

A: Yes, extend the `Asset` base class in `financial_models.py` and update the relationship discovery logic in `asset_graph.py`.

**Q: Is the 3D visualization deterministic?**

A: Yes, the graph layout uses a fixed random seed (42) for consistent positioning across sessions.

### Technical Questions

**Q: Which database is supported?**

A: The primary database is Supabase (PostgreSQL). Direct PostgreSQL connections are also supported.

**Q: Can I deploy without Docker?**

A: Yes, see the Quick Installation section for direct Python/Node.js deployment.

**Q: How do I add new relationship types?**

A: Add relationship logic to the `_find_relationships()` method in `AssetRelationshipGraph`.

---

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.

## Support

- Create an issue on GitHub for bugs
- Check existing issues before reporting
- Include reproduction steps in bug reports

---

*Last Updated: January 2025*
