# Technical Specification

## Financial Asset Relationship Database - Technical Specification v2.0

### Document Information

| Field | Value |
|-------|-------|
| Project Name | Financial Asset Relationship Database |
| Version | 2.0 |
| Status | Active Development |
| Last Updated | January 2025 |

---

## 1. Executive Summary

The Financial Asset Relationship Database is a comprehensive visualization system for mapping and analyzing interconnected financial assets across multiple asset classes. The system provides both a Python-based Gradio interface and a modern Next.js web frontend, backed by a FastAPI REST API.

### 1.1 Purpose

- Visualize complex relationships between financial assets in 3D
- Enable cross-asset analysis across equities, bonds, commodities, and currencies
- Provide network metrics and relationship strength analysis
- Support regulatory event impact modeling

### 1.2 Scope

This specification covers:
- System architecture and component design
- Data models and relationship types
- API specifications
- Deployment configurations
- Integration requirements

---

## 2. System Architecture

### 2.1 High-Level Architecture


### 2.2 Component Overview

| Component | Technology | Port | Purpose |
|-----------|------------|------|---------|
| Gradio UI | Python/Gradio | 7860 | Interactive data science interface |
| Next.js Frontend | React/TypeScript | 3000 | Modern web application |
| FastAPI Backend | Python/FastAPI | 8000 | REST API services |
| Database | Supabase/PostgreSQL | - | Persistent data storage |

---

## 3. Data Models

### 3.1 Asset Classes

| Class | Description | Key Attributes |
|-------|-------------|----------------|
| Equity | Stock/share instruments | P/E ratio, dividend yield, EPS, sector |
| Bond | Fixed income securities | Yield, duration, credit rating, issuer |
| Commodity | Raw materials/futures | Contract specifications, spot price |
| Currency | Foreign exchange pairs | Exchange rate, base/quote currency |

### 3.2 Relationship Types

| Relationship | Direction | Description |
|--------------|-----------|-------------|
| `same_sector` | Bidirectional | Assets in same industry sector |
| `corporate_bond_to_equity` | Directional | Corporate bond issued by equity company |
| `commodity_exposure` | Directional | Equity company exposed to commodity price |
| `currency_risk` | Directional | Asset with FX exposure |
| `income_comparison` | Bidirectional | Dividend vs bond yield comparison |
| `event_impact` | Directional | Regulatory event affecting assets |

### 3.3 Relationship Strength

- **Scale**: 0.0 to 1.0 (normalized)
- **Calculation**: Based on correlation, sector alignment, and business relationships
- **Update Frequency**: On data refresh or event trigger

---

## 4. API Specification

### 4.1 REST Endpoints

#### Assets API

```
GET  /api/assets              - List all assets
GET  /api/assets/{id}         - Get asset by ID
POST /api/assets              - Create new asset
PUT  /api/assets/{id}         - Update asset
DELETE /api/assets/{id}       - Delete asset
```

#### Relationships API

```
GET  /api/relationships       - List all relationships
GET  /api/relationships/{id}  - Get relationship details
POST /api/relationships       - Create relationship
```

#### Visualization API

```
GET  /api/visualization       - Get 3D graph data
GET  /api/metrics             - Get network metrics
GET  /api/health              - Health check endpoint
```

### 4.2 Response Format

```json
{
  "status": "success",
  "data": { },
  "timestamp": "2025-01-12T00:00:00Z"
}
```

---

## 5. Technology Stack

### 5.1 Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Runtime environment |
| FastAPI | 0.109+ | REST API framework |
| Uvicorn | 0.27+ | ASGI server |
| Pydantic | v2 | Data validation |
| NumPy | 1.26+ | Numerical computing |
| Pandas | 2.1+ | Data analysis |

### 5.2 Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 14 | React framework |
| React | 18 | UI library |
| TypeScript | 5 | Type safety |
| Tailwind CSS | 3 | Styling |
| Plotly.js | Latest | 3D visualization |

### 5.3 Infrastructure

| Technology | Purpose |
|------------|---------|
| Vercel | Frontend hosting |
| Supabase | Database (PostgreSQL) |
| Docker | Containerization |
| GitHub Actions | CI/CD |

---

## 6. Security Requirements

### 6.1 Transport Security

- All communications over HTTPS/TLS
- Secure WebSocket for real-time features (future)

### 6.2 Application Security

- CORS configuration for API access control
- Input validation via Pydantic models
- Rate limiting for API endpoints (planned)

### 6.3 Data Security

- Environment variables for sensitive configuration
- No credentials in source code
- Row-level security in Supabase

---

## 7. Performance Requirements

### 7.1 Response Time Targets

| Operation | Target |
|-----------|--------|
| API response | < 200ms |
| 3D visualization load | < 2s |
| Graph computation | < 500ms |

### 7.2 Scalability

- Serverless deployment via Vercel
- Auto-scaling for API functions
- CDN for static assets

---

## 8. Deployment

### 8.1 Environments

| Environment | URL | Purpose |
|-------------|-----|---------|
| Development | localhost | Local development |
| Staging | staging.* | Pre-production testing |
| Production | *.vercel.app | Live deployment |

### 8.2 Configuration

Environment variables required:
- `SUPABASE_URL` - Database URL
- `SUPABASE_KEY` - Database API key
- `DATABASE_URL` - Direct PostgreSQL connection (optional)

---

## 9. Testing Strategy

### 9.1 Test Levels

| Level | Coverage Target | Tools |
|-------|-----------------|-------|
| Unit | 80% | pytest |
| Integration | Key flows | pytest |
| Frontend | Components | Jest |

### 9.2 Quality Gates

- All tests must pass before merge
- Linting with flake8/pylint
- Type checking with mypy
- Code formatting with Black

---

## 10. Maintenance

### 10.1 Monitoring

- Health check endpoints
- Error logging
- Performance metrics (planned)

### 10.2 Updates

- Dependency updates via Dependabot
- Security patches prioritized
- Feature releases via semantic versioning

---

## Appendix

### A. Related Documents

- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture diagrams
- [DEPLOYMENT.md](../DEPLOYMENT.md) - Deployment procedures
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guidelines
- [coding-guidelines.md](coding-guidelines.md) - Coding standards

### B. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | Jan 2025 | Added Next.js frontend, FastAPI backend |
| 1.0 | Initial | Original Gradio-only implementation |
