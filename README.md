# Financial Asset Relationship Database

A comprehensive 3D visualization system for interconnected financial assets across all major classes: **Equities, Bonds, Commodities, Currencies, and Regulatory Events**.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for Next.js frontend)
- Virtual environment (recommended)

### Option 1: Gradio UI (Original)

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd financial-asset-relationship-db
   ```

2. **Set up Python environment**

   ```bash
   python -m venv .venv
   ```

3. **Activate virtual environment**
   - **Windows (PowerShell):**
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   - **Windows (Command Prompt):**
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - **macOS/Linux:**
     ```bash
     source .venv/bin/activate
     ```

4. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

The application will launch in your browser automatically at `http://localhost:7860`.

### Option 2: Next.js Frontend + FastAPI Backend (New)

For the modern web frontend with REST API:

**Quick Start (Both Servers):**

```bash
# Linux/Mac
./run-dev.sh

# Windows
run-dev.bat
```

This will start both the FastAPI backend (port 8000) and Next.js frontend (port 3000).

**Manual Setup:**

1. **Start the FastAPI backend:**

   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   python -m uvicorn api.main:app --reload --port 8000
   ```

2. **Start the Next.js frontend (in a new terminal):**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Access the application:**
   - Frontend: `http://localhost:3000`
   - Backend API: `http://localhost:8000`
   - API Documentation: `http://localhost:8000/docs`

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions and Vercel integration.

### 🐳 Docker Installation (Alternative)

For containerized deployment:

1. **Using Docker Compose (recommended)**

   ```bash
   docker-compose up --build
   ```

2. **Using Docker directly**

   ```bash
   docker build -t financial-asset-db .
   docker run -p 7860:7860 financial-asset-db
   ```

3. **Using Makefile**
   ```bash
   make docker-compose-up
   ```

See [DOCKER.md](DOCKER.md) for detailed Docker deployment guide.

## 📊 Features

### Core Functionality

- **3D Network Visualization**: Interactive 3D graph of asset relationships
- **Cross-Asset Analysis**: Automatic relationship discovery between asset classes
- **Regulatory Integration**: Corporate events and SEC filings impact modeling
- **Real-time Metrics**: Network statistics and relationship strength analysis

### Asset Classes Supported

- **Equities**: Stocks with P/E ratios, dividend yields, EPS
- **Fixed Income**: Bonds with yield, duration, credit ratings
- **Commodities**: Futures and spot prices with contract specifications
- **Currencies**: FX pairs with exchange rates and monetary policy links
- **Regulatory Events**: Earnings, SEC filings, M&A activities

### Relationship Types

- **Sector Affinity**: Assets in same industry sector
- **Corporate Links**: Bonds issued by stock companies
- **Commodity Exposure**: Equity companies exposed to commodity prices
- **Currency Risk**: FX exposure for non-USD assets
- **Income Comparison**: Dividends vs bond yields
- **Event Impact**: Regulatory events affecting multiple assets

## 🏗️ Architecture

### Key Components

- **`app.py`**: Gradio web interface and event handlers
- **`src/logic/asset_graph.py`**: Core graph algorithms and relationship engine
- **`src/models/financial_models.py`**: Domain model dataclasses and enums
- **`src/data/sample_data.py`**: Sample dataset creation
- **`src/visualizations/`**: Plotly-based charts and 3D graphs
- **`src/reports/`**: Schema and business rules reporting

### Data Model

```
Assets -> Relationships -> Regulatory Events
    ↓           ↓              ↓
  Attributes  Strength    Impact Score
```

- **Relationship Strength**: Normalized 0.0-1.0 scale
- **Regulatory Impact**: -1 to +1 scale (negative to positive)
- **3D Positions**: Deterministic layout with seed=42 for consistency

## 🧪 Development

### Project Structure

```
.
├── app.py                          # Main application entry point
├── requirements.txt                # Python dependencies
├── .github/copilot-instructions.md # AI agent guidance
├── src/
│   ├── data/
│   │   └── sample_data.py         # Sample database creation
│   ├── logic/
│   │   └── asset_graph.py         # Core relationship engine
│   ├── models/
│   │   └── financial_models.py    # Domain model classes
│   ├── reports/
│   │   └── schema_report.py       # Schema documentation
│   └── visualizations/
│       ├── graph_visuals.py       # 3D network visualization
│       └── metric_visuals.py      # Analytics charts
```

### Key Patterns

- **Bidirectional Relationships**: Some relationships are symmetric (e.g., `same_sector`)
- **Directional Relationships**: Others flow one way (e.g., `corporate_bond_to_equity`)
- **Deterministic Positions**: 3D layout uses fixed random seed for consistency
- **Relationship Discovery**: Automatic relationship detection via `_find_relationships()`

## 📈 Usage Examples

### Adding New Asset Types

```python
from src.models.financial_models import Asset, AssetClass

# Extend Asset for new types
@dataclass
class Derivative(Asset):
    underlying_asset: str
    expiration_date: str
    strike_price: Optional[float] = None
```

### Custom Relationship Rules

```python
# Add to _find_relationships() in AssetRelationshipGraph
if isinstance(asset1, Derivative) and isinstance(asset2, Equity):
    if asset1.underlying_asset == asset2.symbol:
        relationships.append(("derivative_underlying", 0.95, False))
```

## 🛠️ API Reference

### Core Methods

- `AssetRelationshipGraph.add_asset(asset)` - Add asset to graph
- `AssetRelationshipGraph.add_relationship(source, target, type, strength)` - Create relationship
- `AssetRelationshipGraph.build_relationships()` - Auto-discover relationships
- `AssetRelationshipGraph.calculate_metrics()` - Generate network statistics
- `AssetRelationshipGraph.get_3d_visualization_data()` - Export for visualization

## 🧪 Testing

The project includes comprehensive test coverage:

### Backend (Python)

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Or use Makefile
make test
```

### Frontend (Next.js/React)

```bash
# Run tests
cd frontend
npm test

# Run tests with coverage
npm test -- --coverage
```

**Note:** Coverage reports are generated locally in `frontend/coverage/` and are excluded from version control. These files are auto-generated by Jest/Istanbul and should not be committed.

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed testing guidelines.

## 🔧 Development Tools

- **Testing:** pytest with coverage reporting
- **Linting:** flake8, pylint
- **Formatting:** black, isort
- **Type Checking:** mypy
- **Pre-commit Hooks:** Automatic quality checks

Install development dependencies:

```bash
pip install -r requirements-dev.txt
pre-commit install
```

Or use the Makefile:

```bash
make install-dev
make pre-commit
```

## 📝 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

Quick start:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run `make check` to verify quality
5. Submit a pull request

For AI agents: see `.github/copilot-instructions.md` for development guidelines.

## 📚 Additional Documentation

### Getting Started (NEW)

- [QUICK_START.md](QUICK_START.md) - **Get started in under 5 minutes**
- [UI_COMPARISON.md](UI_COMPARISON.md) - **Compare Gradio vs Next.js interfaces**

### Deployment & Integration (NEW)

- [DEPLOYMENT.md](DEPLOYMENT.md) - **Vercel Next.js deployment guide**
- [VERCEL_DEPLOYMENT_CHECKLIST.md](VERCEL_DEPLOYMENT_CHECKLIST.md) - **Step-by-step deployment checklist**
- [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md) - **Technical integration details**
- [ARCHITECTURE.md](ARCHITECTURE.md) - **System architecture diagrams**

### Original Documentation

- [AUDIT_REPORT.md](AUDIT_REPORT.md) - Comprehensive code audit and improvements
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines
- [AI_RULES.md](AI_RULES.md) - Tech stack and coding conventions
- [DOCKER.md](DOCKER.md) - Docker deployment guide
- [IMPROVEMENTS.md](IMPROVEMENTS.md) - Code quality recommendations
- [SECURITY.md](SECURITY.md) - Security best practices
- [BRANCH_CLEANUP_ANALYSIS.md](BRANCH_CLEANUP_ANALYSIS.md) - Branch management and cleanup guide

## [![Repography logo](https://images.repography.com/logo.svg)](https://repography.com) / Structure

[![Structure](https://images.repography.com/101385307/DashFin/financial-asset-relationship-db/structure/arjWaynlR5rCs456RmPMMMqHEGw9SkWddam5SrE3whs/T4MviKoggvFTqpIOb8tlmjs-DCZZlG84-xtfxwZ4i5w_table.svg)](https://github.com/DashFin/financial-asset-relationship-db)
