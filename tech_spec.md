# Technical Specification

# 1. Introduction

This Technical Specification document provides a comprehensive reference for the **Financial Asset Relationship Database**, an enterprise-grade system designed to visualize and analyze complex interconnections between financial assets across multiple asset classes. This introduction establishes the project's purpose, scope, and context for all stakeholders involved in development, deployment, and utilization of the system.

## 1.1 Executive Summary

### 1.1.1 Project Overview

The Financial Asset Relationship Database is a sophisticated 3D visualization and analytics platform that enables users to explore interconnected financial assets spanning Equities, Fixed Income (Bonds), Commodities, Currencies, and Regulatory Events. The system features a dual-UI architecture that accommodates diverse user preferences and deployment scenarios:

| UI Component | Technology | Port | Target Users |
|--------------|------------|------|--------------|
| Legacy Interface | Gradio (Python) | 7860 | Python developers, rapid prototyping |
| Modern Interface | Next.js + React | 3000 | Web developers, production deployments |
| REST API | FastAPI | 8000 | System integrations, external applications |

The platform delivers interactive network visualizations powered by Plotly, enabling intuitive exploration of asset relationships through rotation, zoom, and hover interactions. Both frontend experiences share a common backend logic layer (`src/logic/asset_graph.py`) ensuring consistent analytical capabilities regardless of the chosen interface.

### 1.1.2 Core Business Problem

Financial markets present significant challenges in understanding the complex web of relationships between different asset types. The Financial Asset Relationship Database addresses several critical pain points:

| Challenge | Solution Provided |
|-----------|-------------------|
| Cross-Asset Complexity | Automatic discovery of relationships across asset classes including sector affinity, corporate bond-to-equity links, commodity exposure, and currency risk |
| Regulatory Impact Analysis | Integration of regulatory events with scored impact modeling (-1 to +1 scale) affecting multiple assets |
| Relationship Visualization | Interactive 3D network graphs with deterministic layouts (seed=42) for reproducible analysis |
| Portfolio Risk Assessment | Network metrics calculation including relationship density, average degree, and asset class distributions |

The system transforms raw financial data into actionable intelligence by surfacing hidden connections that traditional asset-by-asset analysis would miss.

### 1.1.3 Key Stakeholders and Users

The platform serves multiple user constituencies with varying technical backgrounds and analytical needs:

| Stakeholder Group | Primary Use Cases | Preferred Interface |
|-------------------|-------------------|---------------------|
| Financial Analysts | Cross-asset relationship insights, sector analysis | Next.js UI, Gradio UI |
| Portfolio Managers | Diversification analysis, risk exposure visualization | Next.js UI |
| Data Scientists | Network structure exploration, custom analytics | REST API, Gradio UI |
| Integration Developers | Programmatic data access, workflow automation | REST API |
| Compliance Officers | Regulatory event impact assessment | Next.js UI |

### 1.1.4 Value Proposition and Business Impact

The Financial Asset Relationship Database delivers measurable business value through:

**Analytical Capabilities:**
- Cross-asset analysis with automatic relationship discovery via `_find_relationships()` and `build_relationships()` methods
- Real-time network statistics with relationship strength normalization (0.0-1.0 scale)
- Deterministic 3D layouts ensuring reproducible visualizations across sessions
- Comprehensive schema and business rules documentation generation

**Technical Advantages:**
- Modern REST API architecture enabling integration with external systems
- Dual-UI strategy supporting both rapid prototyping (Gradio) and production deployments (Next.js)
- Thread-safe graph initialization with double-checked locking for concurrent access
- JWT-based authentication with configurable token expiration (30-minute default)

**Operational Benefits:**
- Multiple deployment options: local development, Docker containerization, and Vercel serverless
- Real market data integration via Yahoo Finance API (yfinance)
- Offline exploration capability using comprehensive sample dataset

## 1.2 System Overview

### 1.2.1 Project Context

#### Business Context and Market Positioning

The Financial Asset Relationship Database positions itself as a specialized analytical tool for financial professionals who require visibility into cross-asset relationships. Unlike traditional portfolio management systems that treat assets in isolation, this platform emphasizes the interconnected nature of financial markets.

The system operates within the broader financial technology landscape, providing:
- Network-based analysis complementing traditional fundamental and technical analysis
- Regulatory event integration bridging compliance and investment functions
- API-first architecture enabling ecosystem integration

#### Current System Architecture

The platform implements a layered architecture separating concerns across presentation, API, business logic, and data layers:

```mermaid
flowchart TB
    subgraph Presentation["Presentation Layer"]
        GradioUI["Gradio UI<br/>(app.py)"]
        NextJS["Next.js Frontend<br/>(frontend/)"]
    end

    subgraph APILayer["API Layer"]
        FastAPI["FastAPI Backend<br/>(api/main.py)"]
    end

    subgraph BusinessLogic["Business Logic Layer"]
        GraphLogic["Asset Graph<br/>(src/logic/)"]
        Models["Domain Models<br/>(src/models/)"]
        Visualization["Visualization<br/>(src/visualizations/)"]
    end

    subgraph DataLayer["Data Layer"]
        SampleData["Sample Data<br/>(src/data/sample_data.py)"]
        YahooFinance["Yahoo Finance<br/>(yfinance)"]
    end

    GradioUI --> GraphLogic
    NextJS --> FastAPI
    FastAPI --> GraphLogic
    GraphLogic --> Models
    GraphLogic --> Visualization
    GraphLogic --> SampleData
    GraphLogic --> YahooFinance
```

#### Integration with Enterprise Landscape

The system is designed for integration flexibility:

| Integration Point | Mechanism | Configuration |
|-------------------|-----------|---------------|
| External Data Sources | Yahoo Finance via yfinance library | `USE_REAL_DATA_FETCHER` environment variable |
| Authentication Systems | JWT token-based auth | Environment variables for secret key and algorithm |
| Frontend Applications | RESTful JSON API | CORS allowlist per environment |
| Container Orchestration | Docker Compose | `docker-compose.yml` configuration |
| Serverless Platforms | Vercel deployment | `vercel.json` configuration |

### 1.2.2 High-Level Description

#### Primary System Capabilities

| Capability | Description | Implementation |
|------------|-------------|----------------|
| 3D Network Visualization | Interactive Plotly-based graph rendering with rotation, zoom, and hover | `src/visualizations/` |
| Cross-Asset Analysis | Automatic relationship discovery between different asset classes | `src/logic/asset_graph.py` |
| Regulatory Integration | Corporate events and SEC filings with scored impact modeling | `src/models/financial_models.py` |
| Real-time Metrics | Network statistics, relationship density, distribution analysis | API `/api/metrics` endpoint |
| Asset Explorer | Filterable table with asset class and sector filters | Gradio and Next.js UIs |
| Schema Reporting | Auto-generated documentation of data models and business rules | `src/reports/schema_report.py` |

#### Major System Components

```mermaid
flowchart LR
    subgraph Frontend["Frontend Components"]
        A1["Gradio UI"]
        A2["Next.js App"]
    end

    subgraph Backend["Backend Services"]
        B1["FastAPI Server"]
        B2["JWT Auth"]
        B3["Rate Limiter"]
    end

    subgraph Core["Core Logic"]
        C1["Asset Graph Engine"]
        C2["Relationship Builder"]
        C3["Metrics Calculator"]
    end

    subgraph Data["Data Sources"]
        D1["Sample Database"]
        D2["Yahoo Finance"]
    end

    A1 --> C1
    A2 --> B1
    B1 --> B2
    B1 --> B3
    B1 --> C1
    C1 --> C2
    C1 --> C3
    C2 --> D1
    C2 --> D2
end
```

The component architecture follows these responsibilities:

| Component | Location | Responsibility |
|-----------|----------|----------------|
| Gradio UI | `app.py` | Legacy Python UI with tabbed interface for visualization, metrics, schema, and asset exploration |
| FastAPI Backend | `api/main.py` | REST API with JWT authentication, CORS configuration, and rate limiting |
| Next.js Frontend | `frontend/app/` | Modern React-based UI with TypeScript and Tailwind CSS |
| Core Logic | `src/logic/asset_graph.py` | Graph algorithms, relationship discovery, visualization data interface |
| Domain Models | `src/models/financial_models.py` | Asset dataclasses, enums, validation rules |
| Data Layer | `src/data/` | Sample data (19 assets, 4 regulatory events) and real Yahoo Finance fetcher |
| Visualization Layer | `src/visualizations/` | Plotly-based chart generation for 3D graphs, metrics, and 2D views |
| Reports | `src/reports/schema_report.py` | Schema documentation generator |

#### Asset Classes and Domain Model

The system supports five primary asset classes defined in the `AssetClass` enum:

| Asset Class | Key Attributes | Example Use |
|-------------|----------------|-------------|
| Equity | P/E ratio, dividend yield, EPS, book value | Stock analysis |
| Fixed Income | Yield to maturity, coupon rate, maturity date, credit rating, issuer_id | Bond analysis |
| Commodity | Contract size, delivery date, volatility | Commodity tracking |
| Currency | Exchange rate, country, central bank rate | FX exposure |
| Derivative | Extensible attributes | Future expansion |

#### Relationship Types

The relationship engine discovers and manages six primary relationship types:

| Relationship Type | Directionality | Description |
|-------------------|----------------|-------------|
| `same_sector` | Bidirectional | Assets operating in the same industry sector |
| `corporate_bond_to_equity` | Directional | Bonds issued by companies with traded stock |
| `commodity_exposure` | Directional | Equity companies exposed to commodity price movements |
| `currency_risk` | Directional | FX exposure for non-USD denominated assets |
| `income_comparison` | Bidirectional | Dividend yields compared to bond yields |
| `regulatory_impact` | Directional | Regulatory events affecting multiple assets |

### 1.2.3 Technology Stack

#### Backend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Runtime environment |
| FastAPI | 0.127.0 | REST API framework |
| Uvicorn | ≥0.24.0 | ASGI server |
| Pydantic | 2.12.5 | Data validation and serialization |
| NumPy | 2.2.6 | Numerical computing |
| Pandas | ≥1.5.0 | Data analysis and manipulation |
| yfinance | ≥0.2.51 | Yahoo Finance data acquisition |
| Plotly | ≥6.0.0 | Visualization generation |
| SQLAlchemy | ≥2.0.0 | Database ORM |
| Gradio | ≥4.0.0 | Legacy UI framework |

#### Frontend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.2.0 | UI component framework |
| Next.js | 14.2.x | React framework with App Router |
| TypeScript | Latest | Type safety |
| Tailwind CSS | Latest | Utility-first CSS framework |
| Plotly.js | Latest | Client-side 3D visualization |
| Axios | Latest | HTTP client for API communication |

#### Infrastructure Technologies

| Technology | Purpose | Configuration File |
|------------|---------|-------------------|
| Docker | Containerization | `Dockerfile` |
| Docker Compose | Multi-container orchestration | `docker-compose.yml` |
| Vercel | Serverless deployment | `vercel.json` |
| Jest | Frontend testing | `frontend/jest.config.js` |
| Pytest | Backend testing | `tests/` directory |

### 1.2.4 Success Criteria

#### Measurable Objectives

| Objective | Metric | Target |
|-----------|--------|--------|
| API Response Time | 95th percentile latency | < 500ms for standard queries |
| Visualization Rendering | Time to interactive | < 2 seconds for 3D graph |
| Relationship Discovery | Coverage | 100% of defined relationship types |
| Data Accuracy | Validation pass rate | 100% for all asset records |

#### Critical Success Factors

1. **Accurate Relationship Discovery**: The system must correctly identify and categorize all relationship types between assets based on the defined business rules in `src/logic/asset_graph.py`

2. **Reproducible Visualizations**: Deterministic 3D layouts using fixed seed (seed=42) must produce identical visual outputs across sessions

3. **API Reliability**: Thread-safe graph initialization with double-checked locking must prevent race conditions under concurrent load

4. **Security Compliance**: JWT authentication must enforce 30-minute token expiration with configurable rate limiting (5 requests/minute on `/token`)

#### Key Performance Indicators

| KPI | Description | Measurement Source |
|-----|-------------|-------------------|
| Network Density | Ratio of actual to possible relationships | `/api/metrics` endpoint |
| Average Degree | Mean number of connections per asset | `/api/metrics` endpoint |
| Max Degree | Highest connected asset | `/api/metrics` endpoint |
| Asset Class Distribution | Balance of asset types in network | `/api/metrics` endpoint |
| Relationship Strength Distribution | Distribution of normalized weights | Visualization layer |

## 1.3 Scope

### 1.3.1 In-Scope

#### Core Features and Functionalities

**Must-Have Capabilities:**

| Feature | Description | Status |
|---------|-------------|--------|
| 3D Network Visualization | Interactive Plotly-based graph with rotation, zoom, hover | Implemented |
| 2D Visualization | Alternative flat network view | Implemented |
| Multi-Asset Class Support | Equity, Fixed Income, Commodity, Currency, Derivative | Implemented |
| Automatic Relationship Discovery | Rule-based detection via `_find_relationships()` | Implemented |
| Network Metrics | Density, average/max degree, distributions | Implemented |
| Regulatory Event Modeling | Impact scores (-1 to +1 scale) | Implemented |
| Relationship Strength Normalization | Weights on 0.0-1.0 scale | Implemented |
| Schema Documentation | Auto-generated business rules reference | Implemented |

**Primary User Workflows:**

```mermaid
flowchart TD
    subgraph Workflow1["Visualization Workflow"]
        W1A["Access UI"] --> W1B["Select 3D/2D View"]
        W1B --> W1C["Interact with Graph"]
        W1C --> W1D["Hover for Details"]
    end

    subgraph Workflow2["Analytics Workflow"]
        W2A["View Metrics Dashboard"] --> W2B["Analyze Network Statistics"]
        W2B --> W2C["Review Distributions"]
    end

    subgraph Workflow3["Exploration Workflow"]
        W3A["Open Asset Explorer"] --> W3B["Apply Filters"]
        W3B --> W3C["Select Asset"]
        W3C --> W3D["View Relationships"]
    end

    subgraph Workflow4["Integration Workflow"]
        W4A["Authenticate via /token"] --> W4B["Call REST Endpoints"]
        W4B --> W4C["Process JSON Response"]
    end
end
```

**Essential Integrations:**

| Integration | Technology | Purpose |
|-------------|------------|---------|
| Market Data | Yahoo Finance (yfinance) | Real-time and historical asset data |
| Visualization | Plotly | Chart and graph rendering |
| Authentication | JWT | API security |
| Database | SQLite/PostgreSQL | Optional persistence |

**REST API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/assets` | GET | List assets with optional filters |
| `/api/assets/{id}` | GET | Retrieve single asset details |
| `/api/assets/{id}/relationships` | GET | Get relationships for specific asset |
| `/api/relationships` | GET | List all relationships |
| `/api/metrics` | GET | Network metrics and statistics |
| `/api/visualization` | GET | 3D visualization data payload |
| `/api/asset-classes` | GET | Enumerate available asset classes |
| `/api/sectors` | GET | List industry sectors |
| `/token` | POST | JWT authentication |

#### Implementation Boundaries

**System Boundaries:**

| Boundary | Scope |
|----------|-------|
| Deployment Model | Standalone application with optional external data sources |
| Data Persistence | In-memory graph with optional database backing |
| Authentication | Single-user JWT; multi-user requires extension |
| Network Protocol | HTTPS (production), HTTP (development) |

**User Groups Covered:**

| User Group | Access Level | Interface |
|------------|--------------|-----------|
| Analysts | Full read access | All UIs |
| Developers | API access with authentication | REST API |
| Administrators | Configuration management | Environment variables |

**Data Domains Included:**

| Domain | Coverage |
|--------|----------|
| Equities | US market securities |
| Fixed Income | Corporate and government bonds |
| Commodities | Major commodity contracts |
| Currencies | Major currency pairs |
| Regulatory Events | SEC filings and corporate actions |

**Sample Dataset:**
- 19 assets across 4 asset classes
- 4 regulatory events with impact scores
- Comprehensive relationship coverage for all defined types

### 1.3.2 Out-of-Scope

#### Explicitly Excluded Features

| Feature | Exclusion Reason | Future Consideration |
|---------|------------------|----------------------|
| Real-time Streaming Data | Architectural complexity | Phase 2 |
| WebSocket Live Updates | Infrastructure requirements | Phase 2 |
| Advanced Portfolio Optimization | Beyond core visualization scope | Not planned |
| Historical Backtesting | Requires time-series infrastructure | Not planned |
| Multi-User Role-Based Access | Basic JWT auth only | Phase 2 |
| Mobile Native Applications | Web-responsive only | Not planned |

#### Future Phase Considerations

The following enhancements are identified for future development phases:

**Phase 2 Enhancements (from INTEGRATION_SUMMARY.md):**

| Enhancement | Description |
|-------------|-------------|
| Enhanced Authentication | Role-based access control |
| Caching Layer | Redis integration for performance |
| Real-time Updates | WebSocket-based live data |
| Additional Visualizations | Extended chart types |
| Data Export | CSV, JSON, PDF export capabilities |
| CI/CD Pipeline | Automated testing and deployment |
| Monitoring & Analytics | Application performance monitoring |

**Feature Parity Roadmap (Next.js catching up to Gradio):**

| Feature | Gradio Status | Next.js Status |
|---------|---------------|----------------|
| Schema Report | ✓ Implemented | Pending |
| Documentation Tab | ✓ Implemented | Pending |
| 2D Visualization | ✓ Implemented | Pending |
| Formulaic Analysis | ✓ Implemented | Pending |
| Export Features | ✓ Implemented | Pending |

#### Integration Points Not Covered

| Integration | Status | Notes |
|-------------|--------|-------|
| Bloomberg Terminal | Out of scope | Proprietary API |
| Reuters Eikon | Out of scope | Licensing requirements |
| Alternative data providers | Out of scope | yfinance standardized |
| Third-party authentication (OAuth) | Out of scope | JWT only |

#### Unsupported Use Cases

| Use Case | Reason |
|----------|--------|
| High-Frequency Trading | Latency requirements exceed design parameters |
| Multi-Tenant SaaS | Single-user architecture |
| Offline Mobile | Web-only responsive design |
| Non-Financial Assets | Domain model specific to financial instruments |
| Real-time Market Making | No order execution capability |

## 1.4 References

### 1.4.1 Documentation Files

| File | Relevance |
|------|-----------|
| `README.md` | Project overview, features, quick start guide, architecture summary |
| `ARCHITECTURE.md` | Detailed system architecture, component diagrams, data flow |
| `QUICK_START.md` | User onboarding, development setup, usage examples |
| `INTEGRATION_SUMMARY.md` | Vercel integration, Next.js + FastAPI architecture, future roadmap |
| `DEPLOYMENT.md` | Deployment procedures, API endpoints, environment configuration |
| `UI_COMPARISON.md` | Gradio vs Next.js feature comparison |
| `SECURITY.md` | Security best practices, authentication patterns |

### 1.4.2 Source Code Files

| File | Relevance |
|------|-----------|
| `app.py` | Gradio UI implementation, tabs, visualization handlers |
| `api/main.py` | FastAPI implementation, all endpoints, CORS, rate limiting, JWT auth |
| `src/models/financial_models.py` | Domain models, asset classes, validation rules, enums |
| `src/logic/asset_graph.py` | Core graph logic, relationship discovery, visualization data interface |
| `src/data/sample_data.py` | Sample asset data with 19 assets, 4 regulatory events |
| `src/reports/schema_report.py` | Schema documentation generator |
| `requirements.txt` | Python dependencies and versions |

### 1.4.3 Configuration Files

| File | Relevance |
|------|-----------|
| `Dockerfile` | Container configuration |
| `docker-compose.yml` | Container orchestration |
| `vercel.json` | Serverless deployment configuration |
| `frontend/package.json` | Frontend dependencies |
| `frontend/jest.config.js` | Frontend test configuration |

### 1.4.4 Source Directories

| Directory | Relevance |
|-----------|-----------|
| `src/` | Core Python library packages |
| `src/models/` | Domain model definitions |
| `src/logic/` | Graph algorithm implementation |
| `src/data/` | Data sources and persistence |
| `src/visualizations/` | Plotly visualization helpers |
| `api/` | FastAPI backend package |
| `frontend/` | Next.js application |
| `frontend/app/` | React components, API client, types |
| `tests/` | Test harness structure |

# 2. Product Requirements

This section provides a comprehensive catalog of product requirements for the Financial Asset Relationship Database system. Each feature is documented with traceable requirements, acceptance criteria, and implementation considerations derived from the actual system implementation.

## 2.1 Feature Catalog

The feature catalog documents all discrete, testable features implemented in the Financial Asset Relationship Database. Features are categorized by functional domain and include complete metadata, descriptions, and dependency mappings.

### 2.1.1 Feature Overview

The system encompasses 17 primary features organized across five functional domains:

| Domain | Feature Count | Description |
|--------|---------------|-------------|
| Data Model | 2 | Asset types and regulatory events |
| Core Engine | 1 | Graph relationship processing |
| API Layer | 4 | REST endpoints, auth, security |
| Visualization | 3 | 3D/2D graphs, metrics display |
| User Interface | 4 | Gradio and Next.js frontends |

```mermaid
flowchart TD
    subgraph DataModel["Data Model Domain"]
        F001["F-001<br/>Multi-Asset Data Model"]
        F002["F-002<br/>Regulatory Events"]
    end

    subgraph CoreEngine["Core Engine Domain"]
        F003["F-003<br/>Graph Engine"]
    end

    subgraph APILayer["API Layer Domain"]
        F004["F-004<br/>REST API"]
        F005["F-005<br/>JWT Auth"]
        F006["F-006<br/>CORS Config"]
        F007["F-007<br/>Rate Limiting"]
    end

    subgraph Visualization["Visualization Domain"]
        F008["F-008<br/>3D Visualization"]
        F009["F-009<br/>2D Visualization"]
        F010["F-010<br/>Metrics Dashboard"]
    end

    subgraph UserInterface["User Interface Domain"]
        F011["F-011<br/>Asset Explorer"]
        F012["F-012<br/>Schema Report"]
        F016["F-016<br/>Gradio UI"]
        F017["F-017<br/>Next.js Frontend"]
    end

    F001 --> F003
    F002 --> F003
    F003 --> F004
    F003 --> F008
    F003 --> F009
    F003 --> F010
    F004 --> F017
    F005 --> F004
    F006 --> F004
    F007 --> F004
```

### 2.1.2 Data Model Features

#### F-001: Multi-Asset Class Data Model

| Attribute | Value |
|-----------|-------|
| Feature ID | F-001 |
| Feature Name | Multi-Asset Class Data Model |
| Category | Data Model |
| Priority | Critical |
| Status | Completed |

**Description:**

The Multi-Asset Class Data Model provides the foundational domain model supporting five distinct asset classes: Equity, Fixed Income (Bonds), Commodity, Currency, and Derivative. Each asset class extends a base `Asset` dataclass with specialized attributes relevant to that financial instrument type.

**Business Value:**

This feature enables comprehensive cross-asset analysis by providing a unified data structure that captures the unique characteristics of diverse financial instruments while maintaining a consistent interface for relationship discovery and visualization.

**User Benefits:**

- Analysts can explore relationships across heterogeneous asset types
- Portfolio managers can assess diversification across asset classes
- Data scientists can perform network analysis on a normalized dataset

**Technical Context:**

The domain model is implemented in `src/models/financial_models.py` using Python dataclasses. The `AssetClass` enum defines the five supported types, while specialized dataclasses (Equity, Bond, Commodity, Currency) extend the base `Asset` class with type-specific fields. Validation rules enforce data integrity constraints including non-empty identifiers, non-negative prices, and ISO currency code formatting.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | None |
| System Dependencies | Python 3.10+, dataclasses |
| External Dependencies | None |
| Integration Requirements | Compatible with SQLAlchemy ORM mapping |

---

#### F-002: Regulatory Event Integration

| Attribute | Value |
|-----------|-------|
| Feature ID | F-002 |
| Feature Name | Regulatory Event Integration |
| Category | Data Model |
| Priority | High |
| Status | Completed |

**Description:**

Regulatory Event Integration models corporate and regulatory activities that impact multiple financial assets. Events include earnings reports, SEC filings, dividend announcements, bond issuances, acquisitions, and bankruptcy proceedings. Each event carries a scored impact value enabling quantitative assessment of regulatory influence on asset relationships.

**Business Value:**

This feature bridges compliance and investment functions by surfacing regulatory events that affect asset valuations and inter-asset relationships, enabling proactive risk management.

**User Benefits:**

- Compliance officers can track regulatory event propagation
- Analysts can assess event impact across related assets
- Portfolio managers can evaluate regulatory risk exposure

**Technical Context:**

Implemented via the `RegulatoryEvent` dataclass and `RegulatoryActivity` enum in `src/models/financial_models.py`. The impact_score field uses a normalized scale from -1.0 (highly negative) to +1.0 (highly positive). Events link to affected assets via the `asset_id` field and optionally through `related_assets` for multi-asset impacts.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-001 (Multi-Asset Data Model) |
| System Dependencies | Python 3.10+, dataclasses |
| External Dependencies | None |
| Integration Requirements | Requires valid asset_id references |

---

### 2.1.3 Core Engine Features

#### F-003: Asset Relationship Graph Engine

| Attribute | Value |
|-----------|-------|
| Feature ID | F-003 |
| Feature Name | Asset Relationship Graph Engine |
| Category | Core Logic |
| Priority | Critical |
| Status | Completed |

**Description:**

The Asset Relationship Graph Engine is the central processing component that discovers, stores, and exposes relationships between financial assets. The engine implements rule-based relationship detection across eight relationship types, calculates network metrics, and provides visualization data interfaces.

**Business Value:**

This feature transforms raw financial data into actionable intelligence by surfacing hidden connections that traditional asset-by-asset analysis would miss, enabling superior risk assessment and portfolio construction.

**User Benefits:**

- Automatic discovery of non-obvious asset relationships
- Reproducible visualizations via deterministic layouts
- Network-based analysis complementing fundamental analysis

**Technical Context:**

Implemented in `src/logic/asset_graph.py`, the engine maintains a graph structure as `Dict[source_id, List[Tuple[target_id, rel_type, strength]]]`. Key methods include `add_asset()`, `add_regulatory_event()`, `build_relationships()`, `calculate_metrics()`, and `get_3d_visualization_data()`. The engine uses a fixed seed (42) for deterministic 3D layout generation.

**Supported Relationship Types:**

| Relationship Type | Directionality | Detection Rule |
|-------------------|----------------|----------------|
| same_sector | Bidirectional | Assets in identical sector |
| corporate_bond_to_equity | Directional | Bond issuer_id matches equity |
| commodity_exposure | Directional | Equity exposed to commodity |
| currency_risk | Directional | Non-USD currency exposure |
| income_comparison | Bidirectional | Dividend vs bond yield |
| regulatory_impact | Directional | Shared regulatory events |
| market_cap_similar | Bidirectional | Similar market capitalization |
| correlation | Bidirectional | Price correlation threshold |

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-001, F-002 |
| System Dependencies | NumPy 2.2.6, Pandas ≥1.5.0 |
| External Dependencies | None |
| Integration Requirements | Thread-safe initialization |

---

### 2.1.4 API Layer Features

#### F-004: REST API Endpoints

| Attribute | Value |
|-----------|-------|
| Feature ID | F-004 |
| Feature Name | REST API Endpoints |
| Category | API Layer |
| Priority | Critical |
| Status | Completed |

**Description:**

The REST API provides a comprehensive set of HTTP endpoints for programmatic access to asset data, relationships, network metrics, and visualization payloads. Built on FastAPI, the API implements OpenAPI specification compliance with automatic documentation generation.

**Business Value:**

Enables ecosystem integration, allowing external applications and automated workflows to consume financial relationship data programmatically.

**User Benefits:**

- Developers can integrate data into custom applications
- Automated workflows can consume relationship data
- Third-party tools can leverage visualization payloads

**Technical Context:**

Implemented in `api/main.py` using FastAPI 0.127.0. The API exposes 12 primary endpoints with Pydantic response models for type-safe serialization. Graph initialization occurs at startup via the lifespan context manager with thread-safe singleton access.

**API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API metadata and endpoint listing |
| `/api/health` | GET | System health check |
| `/token` | POST | JWT authentication |
| `/api/users/me` | GET | Current authenticated user |
| `/api/assets` | GET | List assets with filters |
| `/api/assets/{id}` | GET | Single asset details |
| `/api/assets/{id}/relationships` | GET | Asset-specific relationships |
| `/api/relationships` | GET | All relationships |
| `/api/metrics` | GET | Network metrics |
| `/api/visualization` | GET | 3D visualization payload |
| `/api/asset-classes` | GET | Available asset classes |
| `/api/sectors` | GET | Available sectors |

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-001, F-002, F-003 |
| System Dependencies | FastAPI 0.127.0, Pydantic 2.12.5 |
| External Dependencies | Uvicorn ≥0.24.0 |
| Integration Requirements | F-005 (Authentication), F-006 (CORS) |

---

#### F-005: JWT Authentication System

| Attribute | Value |
|-----------|-------|
| Feature ID | F-005 |
| Feature Name | JWT Authentication System |
| Category | API Layer |
| Priority | Critical |
| Status | Completed |

**Description:**

The JWT Authentication System provides token-based security for API endpoints. Users authenticate via username/password credentials to receive a time-limited access token. The system uses HS256 algorithm for token signing with configurable expiration.

**Business Value:**

Ensures secure access to sensitive financial data by authenticating API consumers and enforcing token-based session management.

**User Benefits:**

- Secure programmatic API access
- Stateless authentication enabling horizontal scaling
- Configurable session duration

**Technical Context:**

Implemented in `api/auth.py` using PyJWT ≥2.8.0 and passlib for password hashing. Tokens expire after 30 minutes (ACCESS_TOKEN_EXPIRE_MINUTES). The system requires SECRET_KEY, ADMIN_USERNAME, and ADMIN_PASSWORD environment variables. Failed authentication returns HTTP 401 with "WWW-Authenticate: Bearer" header.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | None |
| System Dependencies | PyJWT ≥2.8.0, passlib[bcrypt] ≥1.7.4 |
| External Dependencies | Environment variable configuration |
| Integration Requirements | F-004 (REST API) |

---

#### F-006: CORS Configuration

| Attribute | Value |
|-----------|-------|
| Feature ID | F-006 |
| Feature Name | CORS Configuration |
| Category | API Layer |
| Priority | High |
| Status | Completed |

**Description:**

CORS Configuration manages cross-origin resource sharing policies to enable secure frontend-backend communication across different origins. The configuration adapts between development and production modes with support for dynamic origin allowlists and Vercel preview deployments.

**Business Value:**

Enables secure browser-based API consumption while preventing unauthorized cross-origin requests.

**User Benefits:**

- Seamless frontend integration
- Secure cross-origin communication
- Support for preview deployments

**Technical Context:**

Implemented in `api/main.py` with environment-aware configuration. Development mode permits HTTP localhost:3000 and localhost:7860. Production mode restricts to HTTPS origins. Vercel preview domains are validated via regex pattern `^https://[a-zA-Z0-9\-\.]+\.vercel\.app$`. Custom origins are configurable via ALLOWED_ORIGINS environment variable.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | None |
| System Dependencies | FastAPI CORSMiddleware |
| External Dependencies | Environment configuration |
| Integration Requirements | F-004 (REST API) |

---

#### F-007: Rate Limiting

| Attribute | Value |
|-----------|-------|
| Feature ID | F-007 |
| Feature Name | Rate Limiting |
| Category | API Layer |
| Priority | Medium |
| Status | Completed |

**Description:**

Rate Limiting protects API endpoints from abuse by enforcing request frequency limits per client IP address. The feature uses the slowapi library integrated with FastAPI exception handlers.

**Business Value:**

Prevents denial-of-service attacks and ensures fair resource allocation among API consumers.

**User Benefits:**

- Consistent API availability
- Protection from credential stuffing attacks
- Fair usage enforcement

**Technical Context:**

Implemented using slowapi ≥0.1.4 with `get_remote_address` as the key function. Current rate limits include 5 requests per minute on `/token` and 10 requests per minute on `/api/users/me`.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | None |
| System Dependencies | slowapi ≥0.1.4 |
| External Dependencies | None |
| Integration Requirements | F-004 (REST API) |

---

### 2.1.5 Visualization Features

#### F-008: 3D Network Visualization

| Attribute | Value |
|-----------|-------|
| Feature ID | F-008 |
| Feature Name | 3D Network Visualization |
| Category | Visualization |
| Priority | Critical |
| Status | Completed |

**Description:**

3D Network Visualization renders the asset relationship graph as an interactive three-dimensional network using Plotly. Users can rotate, zoom, and hover over nodes and edges to explore asset relationships in an immersive spatial context.

**Business Value:**

Provides intuitive visual exploration of complex relationship networks that would be difficult to comprehend in tabular form, accelerating insight discovery.

**User Benefits:**

- Intuitive exploration of complex networks
- Reproducible layouts for consistent analysis
- Interactive hover details for deep dives

**Technical Context:**

Implemented in `src/visualizations/graph_visuals.py` with Plotly ≥6.0.0 (backend) and plotly.js ^2.27.0 (frontend). Nodes are color-coded by asset class: Blue (Equity), Green (Fixed Income), Orange (Commodity), Red (Currency), Purple (Derivative). Edge colors vary by relationship type. Deterministic layouts use seed=42. Frontend guardrails limit rendering to MAX_NODES (default 500) and MAX_EDGES (default 2000).

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-003 (Graph Engine) |
| System Dependencies | Plotly ≥6.0.0 |
| External Dependencies | None |
| Integration Requirements | Visualization data from F-003 |

---

#### F-009: 2D Network Visualization

| Attribute | Value |
|-----------|-------|
| Feature ID | F-009 |
| Feature Name | 2D Network Visualization |
| Category | Visualization |
| Priority | High |
| Status | Completed |

**Description:**

2D Network Visualization provides an alternative flat view of the asset relationship network with selectable layout algorithms. This view is optimized for static analysis and print output.

**Business Value:**

Offers an alternative visualization format suitable for reports, presentations, and users who prefer traditional 2D analysis.

**User Benefits:**

- Multiple layout options (spring, circular, grid)
- Print-friendly output
- Simplified interaction model

**Technical Context:**

Implemented in `src/visualizations/graph_2d_visuals.py`. Supports the same filtering and relationship visibility toggles as 3D visualization. Layout options include spring (force-directed), circular, and grid arrangements.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-003 (Graph Engine) |
| System Dependencies | Plotly ≥6.0.0 |
| External Dependencies | None |
| Integration Requirements | F-008 (shares visualization infrastructure) |

---

#### F-010: Metrics Dashboard

| Attribute | Value |
|-----------|-------|
| Feature ID | F-010 |
| Feature Name | Metrics Dashboard |
| Category | Visualization |
| Priority | High |
| Status | Completed |

**Description:**

The Metrics Dashboard displays network statistics and distribution analytics including total assets, total relationships, asset class distribution, average degree, maximum degree, network density, and relationship density.

**Business Value:**

Provides quantitative insight into network structure, enabling assessment of portfolio diversification and relationship concentration.

**User Benefits:**

- At-a-glance network health indicators
- Asset class distribution analysis
- Relationship concentration metrics

**Technical Context:**

Backend metrics calculation in F-003 exposes data via `/api/metrics` endpoint. The MetricsResponse model includes: total_assets, total_relationships, asset_classes (Dict[str, int]), avg_degree, max_degree, network_density, and relationship_density. Frontend rendering in `frontend/app/components/MetricsDashboard.tsx`.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-003 (Graph Engine) |
| System Dependencies | Plotly ≥6.0.0 |
| External Dependencies | None |
| Integration Requirements | F-004 (REST API) |

---

### 2.1.6 User Interface Features

#### F-011: Asset Explorer

| Attribute | Value |
|-----------|-------|
| Feature ID | F-011 |
| Feature Name | Asset Explorer |
| Category | User Interface |
| Priority | High |
| Status | Completed |

**Description:**

Asset Explorer provides a filterable, paginated table view of all assets in the system. Users can filter by asset class and sector, view asset details, and navigate to relationship views.

**Business Value:**

Enables structured data exploration for users who prefer tabular interfaces or need to locate specific assets efficiently.

**User Benefits:**

- Efficient asset lookup by class or sector
- Paginated navigation for large datasets
- Direct access to asset details

**Technical Context:**

Implemented in both Gradio (`app.py`) and Next.js (`frontend/app/components/AssetList.tsx`). API supports filtering via `asset_class` and `sector` query parameters. Pagination via `page` and `per_page` parameters. Display columns include symbol, name, asset class, sector, price, and market_cap.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-003 (Graph Engine) |
| System Dependencies | None |
| External Dependencies | None |
| Integration Requirements | F-004 (REST API) for Next.js |

---

#### F-012: Schema & Rules Report

| Attribute | Value |
|-----------|-------|
| Feature ID | F-012 |
| Feature Name | Schema & Rules Report |
| Category | User Interface |
| Priority | Medium |
| Status | Completed |

**Description:**

The Schema & Rules Report generates human-readable documentation of the data model, relationship types, business rules, and calculated metrics. Output is formatted in Markdown for easy consumption and publication.

**Business Value:**

Provides self-documenting system capabilities, reducing onboarding time for new users and enabling compliance documentation.

**User Benefits:**

- Auto-generated data dictionary
- Business rules reference
- Data quality score visibility

**Technical Context:**

Implemented in `src/reports/schema_report.py`. Output includes entity type descriptions, relationship type definitions, business rules documentation, calculated metrics explanations, and data quality scores. Accessible via the Gradio UI's Schema & Rules tab.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-003 (Graph Engine) |
| System Dependencies | None |
| External Dependencies | None |
| Integration Requirements | Gradio UI (F-016) |

---

#### F-013: Formulaic Analysis

| Attribute | Value |
|-----------|-------|
| Feature ID | F-013 |
| Feature Name | Formulaic Analysis |
| Category | Analytics |
| Priority | Medium |
| Status | Completed |

**Description:**

Formulaic Analysis provides a library of financial formulas with LaTeX rendering, variable definitions, example calculations, and R-squared values where applicable. Formula categories span fundamental analysis, correlation, valuation, risk/return, portfolio theory, and cross-asset relationships.

**Business Value:**

Educates users on the quantitative foundations underlying relationship analysis and enables validation of system calculations.

**User Benefits:**

- Formula library with mathematical notation
- Category-organized reference material
- Example calculations for verification

**Technical Context:**

Implemented in `src/analysis/formulaic_analysis.py`. The Formula dataclass includes: name, formula, latex, description, variables, example_calculation, category, and r_squared. The Gradio UI exposes this via the Formulaic Analysis tab with empirical relationship data including correlation matrices.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-001, F-003 |
| System Dependencies | None |
| External Dependencies | None |
| Integration Requirements | Gradio UI (F-016) |

---

#### F-014: Real Data Fetching

| Attribute | Value |
|-----------|-------|
| Feature ID | F-014 |
| Feature Name | Real Data Fetching |
| Category | Data Layer |
| Priority | Medium |
| Status | Completed |

**Description:**

Real Data Fetching integrates with Yahoo Finance to retrieve live market data for a predefined set of symbols. When enabled, the system fetches current prices and attributes for equities, bond ETFs, commodities, and currency pairs.

**Business Value:**

Enables analysis of real-world market relationships rather than static sample data, providing actionable insights for production use.

**User Benefits:**

- Live market data analysis
- Current price integration
- Production-ready data source

**Technical Context:**

Implemented in `src/data/real_data_fetcher.py` using yfinance ≥0.2.51. Supported symbols include: AAPL, MSFT, XOM, JPM (equities); TLT, LQD, HYG (bond ETFs); GC=F, CL=F, SI=F (commodities); EURUSD=X, GBPUSD=X, JPYUSD=X (currencies). Enabled via USE_REAL_DATA_FETCHER environment variable. Implements atomic JSON file caching via NamedTemporaryFile and os.replace.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-001 |
| System Dependencies | yfinance ≥0.2.51 |
| External Dependencies | Yahoo Finance API |
| Integration Requirements | Network connectivity |

---

#### F-015: Database Persistence

| Attribute | Value |
|-----------|-------|
| Feature ID | F-015 |
| Feature Name | Database Persistence |
| Category | Data Layer |
| Priority | Low |
| Status | Completed |

**Description:**

Database Persistence provides optional SQLAlchemy-based storage for assets, relationships, and regulatory events. The persistence layer supports both SQLite (development) and PostgreSQL (production) backends.

**Business Value:**

Enables data persistence across sessions and supports larger datasets than in-memory storage allows.

**User Benefits:**

- Data survives application restarts
- Scalable to larger datasets
- Standard SQL query access

**Technical Context:**

Implemented across `src/data/database.py`, `src/data/db_models.py`, and `src/data/repository.py`. Uses SQLAlchemy 2.x with Mapped/mapped_column syntax. Tables include: assets, asset_relationships, regulatory_events, and regulatory_event_assets (junction). Migrations defined in `migrations/001_initial.sql`.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-001, F-002 |
| System Dependencies | SQLAlchemy ≥2.0.0 |
| External Dependencies | SQLite or PostgreSQL |
| Integration Requirements | DATABASE_URL configuration |

---

#### F-016: Gradio UI (Legacy Interface)

| Attribute | Value |
|-----------|-------|
| Feature ID | F-016 |
| Feature Name | Gradio UI (Legacy Interface) |
| Category | User Interface |
| Priority | High |
| Status | Completed |

**Description:**

The Gradio UI provides a Python-native web interface with six tabbed sections covering 3D/2D visualization, metrics analytics, schema documentation, asset exploration, general documentation, and formulaic analysis. Designed for rapid prototyping and Python developer workflows.

**Business Value:**

Provides immediate visual access to system capabilities without frontend development, accelerating prototyping and Python-centric workflows.

**User Benefits:**

- Zero frontend setup required
- Full feature coverage
- Interactive controls for visualization

**Technical Context:**

Implemented in `app.py` using Gradio ≥4.0.0,<6.0.0. Exposes six tabs with interactive controls including view mode toggle (2D/3D), layout type selection, eight relationship visibility checkboxes, and direction arrows toggle. Runs on port 7860 by default.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-003, F-008, F-009, F-010, F-011, F-012, F-013 |
| System Dependencies | Gradio ≥4.0.0 |
| External Dependencies | None |
| Integration Requirements | Direct core library access |

---

#### F-017: Next.js Frontend (Modern Interface)

| Attribute | Value |
|-----------|-------|
| Feature ID | F-017 |
| Feature Name | Next.js Frontend (Modern Interface) |
| Category | User Interface |
| Priority | High |
| Status | In Development |

**Description:**

The Next.js Frontend provides a modern React-based interface with TypeScript type safety and Tailwind CSS styling. Currently implements visualization, metrics, and asset exploration tabs with additional features planned for parity with Gradio.

**Business Value:**

Provides production-ready web interface suitable for enterprise deployment with modern frontend tooling and performance optimization.

**User Benefits:**

- Modern, responsive user experience
- TypeScript type safety
- Production deployment readiness

**Technical Context:**

Implemented in `frontend/` using Next.js 14.2.x, React 18.2.0, TypeScript, and Tailwind CSS 3.3.0. API communication via Axios. 3D visualization with react-plotly.js ^2.6.0. Components in `frontend/app/components/` include NetworkVisualization, MetricsDashboard, and AssetList.

**Dependencies:**

| Dependency Type | Dependency |
|-----------------|------------|
| Prerequisite Features | F-004 (REST API) |
| System Dependencies | Node.js ≥18.0.0, Next.js 14.2.x |
| External Dependencies | None |
| Integration Requirements | F-004, F-006 (CORS) |

---

## 2.2 Functional Requirements Tables

This section provides detailed requirements for each feature with acceptance criteria, technical specifications, and validation rules.

### 2.2.1 Data Model Requirements

#### F-001 Requirements: Multi-Asset Class Data Model

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-001-RQ-001 | Support five asset classes via AssetClass enum | Must-Have |
| F-001-RQ-002 | Validate required fields (id, symbol, name) as non-empty | Must-Have |
| F-001-RQ-003 | Enforce non-negative price values | Must-Have |
| F-001-RQ-004 | Validate currency against ISO 4217 format | Must-Have |
| F-001-RQ-005 | Support optional market_cap with non-negative validation | Should-Have |

**F-001-RQ-001: Asset Class Enumeration**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-001-RQ-001 |
| Description | System shall support five asset classes: EQUITY, FIXED_INCOME, COMMODITY, CURRENCY, DERIVATIVE |
| Acceptance Criteria | AssetClass enum contains all five values; assets can be created with each type |
| Complexity | Low |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | asset_class: AssetClass enum value |
| Output/Response | Asset instance with valid asset_class |
| Performance Criteria | Instantiation < 1ms |
| Data Requirements | Valid enum member selection |

| Validation Rules | Specification |
|------------------|---------------|
| Business Rules | Only defined enum values accepted |
| Data Validation | Enum membership check |
| Security Requirements | None |
| Compliance Requirements | None |

**F-001-RQ-002: Required Field Validation**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-001-RQ-002 |
| Description | System shall validate id, symbol, and name fields as non-empty strings |
| Acceptance Criteria | Empty strings rejected with validation error; whitespace-only strings rejected |
| Complexity | Low |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | id: str, symbol: str, name: str |
| Output/Response | ValidationError on empty values |
| Performance Criteria | Validation < 1ms |
| Data Requirements | Non-empty string requirement |

**F-001-RQ-003: Price Validation**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-001-RQ-003 |
| Description | System shall enforce price values ≥ 0 |
| Acceptance Criteria | Negative prices rejected; zero and positive values accepted |
| Complexity | Low |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | price: float |
| Output/Response | ValidationError if price < 0 |
| Performance Criteria | Validation < 1ms |
| Data Requirements | Numeric type required |

**F-001-RQ-004: Currency Code Validation**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-001-RQ-004 |
| Description | System shall validate currency codes match pattern ^[A-Z]{3}$ |
| Acceptance Criteria | Three uppercase letters accepted; other formats rejected |
| Complexity | Low |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | currency: str (default "USD") |
| Output/Response | ValidationError on pattern mismatch |
| Performance Criteria | Regex validation < 1ms |
| Data Requirements | ISO 4217 format |

---

#### F-002 Requirements: Regulatory Event Integration

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-002-RQ-001 | Support six regulatory activity types | Must-Have |
| F-002-RQ-002 | Validate impact_score in range [-1, 1] | Must-Have |
| F-002-RQ-003 | Validate date format as ISO 8601 | Must-Have |
| F-002-RQ-004 | Support multi-asset event relationships | Should-Have |

**F-002-RQ-001: Regulatory Activity Types**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-002-RQ-001 |
| Description | System shall support: EARNINGS_REPORT, SEC_FILING, DIVIDEND_ANNOUNCEMENT, BOND_ISSUANCE, ACQUISITION, BANKRUPTCY |
| Acceptance Criteria | RegulatoryActivity enum contains all six values |
| Complexity | Low |

**F-002-RQ-002: Impact Score Validation**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-002-RQ-002 |
| Description | System shall validate impact_score as float in range [-1.0, 1.0] |
| Acceptance Criteria | Values outside range rejected; boundary values accepted |
| Complexity | Low |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | impact_score: float |
| Output/Response | ValidationError if outside [-1, 1] |
| Performance Criteria | Validation < 1ms |
| Data Requirements | Normalized impact scale |

**F-002-RQ-003: Date Format Validation**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-002-RQ-003 |
| Description | System shall validate dates match pattern ^\d{4}-\d{2}-\d{2} (YYYY-MM-DD) |
| Acceptance Criteria | ISO 8601 dates accepted; other formats rejected |
| Complexity | Low |

---

### 2.2.2 Core Engine Requirements

#### F-003 Requirements: Asset Relationship Graph Engine

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-003-RQ-001 | Discover relationships across 8 defined types | Must-Have |
| F-003-RQ-002 | Generate deterministic 3D layouts with seed=42 | Must-Have |
| F-003-RQ-003 | Provide thread-safe initialization | Must-Have |
| F-003-RQ-004 | Calculate network metrics accurately | Must-Have |
| F-003-RQ-005 | Normalize relationship strength to [0, 1] | Should-Have |

**F-003-RQ-001: Relationship Discovery**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-003-RQ-001 |
| Description | System shall discover relationships: same_sector, corporate_bond_to_equity, commodity_exposure, currency_risk, income_comparison, regulatory_impact, market_cap_similar, correlation |
| Acceptance Criteria | All relationship types detected per business rules |
| Complexity | High |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | Asset collection, RegulatoryEvent collection |
| Output/Response | Graph structure with typed edges |
| Performance Criteria | < 500ms for 100 assets |
| Data Requirements | Valid asset instances |

| Validation Rules | Specification |
|------------------|---------------|
| Business Rules | Bidirectional: same_sector, income_comparison, market_cap_similar, correlation; Directional: corporate_bond_to_equity, commodity_exposure, currency_risk, regulatory_impact |
| Data Validation | Valid asset and event IDs |
| Security Requirements | None |
| Compliance Requirements | None |

**F-003-RQ-002: Deterministic Layout**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-003-RQ-002 |
| Description | System shall generate identical 3D coordinates for same input data using seed=42 |
| Acceptance Criteria | Repeated calls produce identical node positions |
| Complexity | Medium |

**F-003-RQ-003: Thread-Safe Initialization**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-003-RQ-003 |
| Description | System shall use double-checked locking for graph singleton |
| Acceptance Criteria | Concurrent requests receive same instance; no race conditions |
| Complexity | Medium |

**F-003-RQ-004: Network Metrics Calculation**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-003-RQ-004 |
| Description | System shall calculate: total_assets, total_relationships, asset_classes distribution, avg_degree, max_degree, network_density, relationship_density |
| Acceptance Criteria | All metrics returned with correct values |
| Complexity | Medium |

---

### 2.2.3 API Layer Requirements

#### F-004 Requirements: REST API Endpoints

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-004-RQ-001 | Expose 12 primary endpoints | Must-Have |
| F-004-RQ-002 | Return valid JSON responses | Must-Have |
| F-004-RQ-003 | Support filtering on /api/assets | Must-Have |
| F-004-RQ-004 | Provide OpenAPI documentation | Should-Have |

**F-004-RQ-001: Endpoint Coverage**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-004-RQ-001 |
| Description | System shall expose all 12 documented endpoints with correct HTTP methods |
| Acceptance Criteria | Each endpoint responds with appropriate status codes |
| Complexity | Medium |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | Per-endpoint query/path parameters |
| Output/Response | JSON with Pydantic model serialization |
| Performance Criteria | 95th percentile < 500ms |
| Data Requirements | Valid request parameters |

**F-004-RQ-003: Asset Filtering**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-004-RQ-003 |
| Description | /api/assets shall support asset_class and sector query parameters |
| Acceptance Criteria | Filtered results match criteria; empty filters return all |
| Complexity | Low |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | asset_class: str (optional), sector: str (optional), page: int, per_page: int |
| Output/Response | Paginated asset list |
| Performance Criteria | < 100ms for typical queries |
| Data Requirements | Valid enum values for asset_class |

---

#### F-005 Requirements: JWT Authentication System

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-005-RQ-001 | Issue JWT tokens via /token endpoint | Must-Have |
| F-005-RQ-002 | Enforce 30-minute token expiration | Must-Have |
| F-005-RQ-003 | Use HS256 signing algorithm | Must-Have |
| F-005-RQ-004 | Return 401 with WWW-Authenticate on failure | Must-Have |

**F-005-RQ-001: Token Issuance**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-005-RQ-001 |
| Description | System shall issue JWT tokens upon valid username/password authentication |
| Acceptance Criteria | Valid credentials return access_token; invalid credentials return 401 |
| Complexity | Medium |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | username: str, password: str (form data) |
| Output/Response | {"access_token": "...", "token_type": "bearer"} |
| Performance Criteria | < 200ms including password hash verification |
| Data Requirements | Matching credentials in user store |

| Validation Rules | Specification |
|------------------|---------------|
| Business Rules | Passwords verified via pbkdf2_sha256 |
| Data Validation | Non-empty username and password |
| Security Requirements | Constant-time password comparison |
| Compliance Requirements | Token-based stateless auth |

---

#### F-006 Requirements: CORS Configuration

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-006-RQ-001 | Allow localhost:3000 and localhost:7860 in development | Must-Have |
| F-006-RQ-002 | Restrict to HTTPS origins in production | Must-Have |
| F-006-RQ-003 | Support Vercel preview domain pattern | Should-Have |

**F-006-RQ-001: Development Origins**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-006-RQ-001 |
| Description | Development mode shall allow HTTP origins: localhost:3000, localhost:7860 |
| Acceptance Criteria | Cross-origin requests from allowed origins succeed |
| Complexity | Low |

---

#### F-007 Requirements: Rate Limiting

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-007-RQ-001 | Limit /token to 5 requests per minute | Must-Have |
| F-007-RQ-002 | Limit /api/users/me to 10 requests per minute | Must-Have |
| F-007-RQ-003 | Return 429 when limit exceeded | Must-Have |

**F-007-RQ-001: Token Endpoint Rate Limit**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-007-RQ-001 |
| Description | /token endpoint shall reject requests exceeding 5 per minute per IP |
| Acceptance Criteria | 6th request within minute returns 429 |
| Complexity | Low |

---

### 2.2.4 Visualization Requirements

#### F-008 Requirements: 3D Network Visualization

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-008-RQ-001 | Render interactive 3D graph with Plotly | Must-Have |
| F-008-RQ-002 | Color-code nodes by asset class | Must-Have |
| F-008-RQ-003 | Support rotation, zoom, and hover | Must-Have |
| F-008-RQ-004 | Limit rendering to MAX_NODES/MAX_EDGES | Should-Have |

**F-008-RQ-001: 3D Graph Rendering**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-008-RQ-001 |
| Description | System shall render asset network as 3D scatter plot with edges |
| Acceptance Criteria | Graph displays with nodes positioned in 3D space |
| Complexity | High |

| Technical Specification | Value |
|-------------------------|-------|
| Input Parameters | Visualization data from graph engine |
| Output/Response | Plotly Figure object / JSON payload |
| Performance Criteria | Time to interactive < 2 seconds |
| Data Requirements | Valid node/edge data |

**F-008-RQ-002: Asset Class Color Coding**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-008-RQ-002 |
| Description | Nodes colored: Equity (Blue), Fixed Income (Green), Commodity (Orange), Currency (Red), Derivative (Purple) |
| Acceptance Criteria | Visual inspection confirms color mapping |
| Complexity | Low |

---

### 2.2.5 User Interface Requirements

#### F-011 Requirements: Asset Explorer

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| F-011-RQ-001 | Display asset table with key attributes | Must-Have |
| F-011-RQ-002 | Support filtering by asset_class and sector | Must-Have |
| F-011-RQ-003 | Implement pagination | Should-Have |

**F-011-RQ-001: Asset Table Display**

| Attribute | Specification |
|-----------|---------------|
| Requirement ID | F-011-RQ-001 |
| Description | Display columns: symbol, name, asset_class, sector, price, market_cap |
| Acceptance Criteria | All columns render with correct data |
| Complexity | Low |

---

## 2.3 Feature Relationships

This section documents the dependencies, integration points, and shared components between features.

### 2.3.1 Feature Dependency Map

The following diagram illustrates the dependency relationships between features:

```mermaid
flowchart TD
    subgraph Foundation["Foundation Layer"]
        F001["F-001: Multi-Asset<br/>Data Model"]
        F002["F-002: Regulatory<br/>Events"]
    end

    subgraph Core["Core Processing"]
        F003["F-003: Graph<br/>Engine"]
    end

    subgraph DataLayer["Data Layer"]
        F014["F-014: Real Data<br/>Fetching"]
        F015["F-015: Database<br/>Persistence"]
    end

    subgraph Security["Security Layer"]
        F005["F-005: JWT Auth"]
        F006["F-006: CORS"]
        F007["F-007: Rate Limiting"]
    end

    subgraph API["API Layer"]
        F004["F-004: REST API"]
    end

    subgraph Visualization["Visualization Layer"]
        F008["F-008: 3D Visualization"]
        F009["F-009: 2D Visualization"]
        F010["F-010: Metrics Dashboard"]
    end

    subgraph Analytics["Analytics Layer"]
        F012["F-012: Schema Report"]
        F013["F-013: Formulaic Analysis"]
    end

    subgraph Interface["Interface Layer"]
        F011["F-011: Asset Explorer"]
        F016["F-016: Gradio UI"]
        F017["F-017: Next.js Frontend"]
    end

    F001 --> F003
    F002 --> F003
    F014 --> F001
    F015 --> F001
    F015 --> F002
    F003 --> F004
    F005 --> F004
    F006 --> F004
    F007 --> F004
    F003 --> F008
    F003 --> F009
    F003 --> F010
    F003 --> F012
    F003 --> F013
    F001 --> F013
    F003 --> F011
    F004 --> F017
    F008 --> F016
    F009 --> F016
    F010 --> F016
    F011 --> F016
    F012 --> F016
    F013 --> F016
```

### 2.3.2 Dependency Matrix

| Feature | Depends On | Required By |
|---------|------------|-------------|
| F-001 | None | F-002, F-003, F-013, F-014, F-015 |
| F-002 | F-001 | F-003, F-015 |
| F-003 | F-001, F-002 | F-004, F-008, F-009, F-010, F-011, F-012, F-013 |
| F-004 | F-001, F-002, F-003, F-005, F-006, F-007 | F-017 |
| F-005 | None | F-004 |
| F-006 | None | F-004 |
| F-007 | None | F-004 |
| F-008 | F-003 | F-016 |
| F-009 | F-003 | F-016 |
| F-010 | F-003 | F-016, F-017 |
| F-011 | F-003 | F-016, F-017 |
| F-012 | F-003 | F-016 |
| F-013 | F-001, F-003 | F-016 |
| F-014 | F-001 | None |
| F-015 | F-001, F-002 | None |
| F-016 | F-008, F-009, F-010, F-011, F-012, F-013 | None |
| F-017 | F-004 | None |

### 2.3.3 Integration Points

| Integration Point | Features Involved | Mechanism |
|-------------------|-------------------|-----------|
| Graph Data Access | F-003 ↔ F-004 | Python method calls |
| Visualization Data | F-003 → F-008, F-009 | get_3d_visualization_data() |
| API Communication | F-004 ↔ F-017 | HTTP/JSON via Axios |
| Authentication Flow | F-005 → F-004 → F-017 | JWT Bearer token |
| Metrics Calculation | F-003 → F-010 | calculate_metrics() |
| Data Ingestion | F-014 → F-001 → F-003 | Asset instantiation |

### 2.3.4 Shared Components

| Component | Used By Features | Location |
|-----------|------------------|----------|
| AssetClass enum | F-001, F-003, F-004, F-008, F-011 | `src/models/financial_models.py` |
| Asset dataclasses | F-001, F-003, F-014, F-015 | `src/models/financial_models.py` |
| Plotly rendering | F-008, F-009, F-010 | `src/visualizations/` |
| Pydantic models | F-004, F-017 | `api/main.py`, `frontend/app/types/` |
| Graph singleton | F-003, F-004, F-016 | `api/main.py` initialization |

### 2.3.5 Common Services

| Service | Description | Consumer Features |
|---------|-------------|-------------------|
| Graph Initialization | Thread-safe singleton creation | F-003, F-004 |
| Relationship Discovery | Rule-based edge detection | F-003, F-008, F-009 |
| Validation | Data constraint enforcement | F-001, F-002 |
| JSON Serialization | Pydantic model conversion | F-004, F-017 |
| Password Hashing | pbkdf2_sha256 via passlib | F-005 |

---

## 2.4 Implementation Considerations

This section documents technical constraints, performance requirements, and operational considerations for each feature domain.

### 2.4.1 Data Model Implementation

**F-001, F-002: Domain Model Considerations**

| Consideration | Specification |
|---------------|---------------|
| Technical Constraints | Python 3.10+ required for dataclass features |
| Performance Requirements | Instantiation < 1ms; validation < 1ms |
| Scalability Considerations | Dataclass memory footprint scales linearly |
| Security Implications | Input validation prevents injection |
| Maintenance Requirements | Schema changes require migration |

### 2.4.2 Core Engine Implementation

**F-003: Graph Engine Considerations**

| Consideration | Specification |
|---------------|---------------|
| Technical Constraints | In-memory graph limits dataset size |
| Performance Requirements | Relationship discovery < 500ms for 100 assets |
| Scalability Considerations | O(n²) relationship detection; partition for scale |
| Security Implications | No sensitive data in graph structure |
| Maintenance Requirements | New relationship types require rule additions |

### 2.4.3 API Layer Implementation

**F-004, F-005, F-006, F-007: API Considerations**

| Consideration | Specification |
|---------------|---------------|
| Technical Constraints | Single-threaded graph access |
| Performance Requirements | 95th percentile response < 500ms |
| Scalability Considerations | Horizontal scaling requires shared state |
| Security Implications | JWT expiration enforced; CORS restricted |
| Maintenance Requirements | OpenAPI docs auto-generated |

### 2.4.4 Visualization Implementation

**F-008, F-009, F-010: Visualization Considerations**

| Consideration | Specification |
|---------------|---------------|
| Technical Constraints | Browser memory limits visualization size |
| Performance Requirements | Time to interactive < 2 seconds |
| Scalability Considerations | MAX_NODES=500, MAX_EDGES=2000 defaults |
| Security Implications | Client-side rendering; no server load |
| Maintenance Requirements | Plotly version compatibility |

### 2.4.5 User Interface Implementation

**F-016, F-017: UI Considerations**

| Consideration | Specification |
|---------------|---------------|
| Technical Constraints | Gradio: Python only; Next.js: Node.js required |
| Performance Requirements | Initial load < 3 seconds |
| Scalability Considerations | Static assets cacheable; API stateless |
| Security Implications | CORS enforcement; XSS prevention |
| Maintenance Requirements | Dependency updates; feature parity |

---

## 2.5 Traceability Matrix

This matrix links features to their implementing source files and test coverage.

### 2.5.1 Feature-to-Source Traceability

| Feature ID | Primary Source Files | Test Files |
|------------|---------------------|------------|
| F-001 | `src/models/financial_models.py` | `tests/unit/test_models.py` |
| F-002 | `src/models/financial_models.py` | `tests/unit/test_models.py` |
| F-003 | `src/logic/asset_graph.py` | `tests/unit/test_graph.py` |
| F-004 | `api/main.py` | `tests/unit/test_api.py` |
| F-005 | `api/auth.py` | `tests/unit/test_auth.py` |
| F-006 | `api/main.py` | `tests/unit/test_cors.py` |
| F-007 | `api/main.py` | `tests/unit/test_api.py` |
| F-008 | `src/visualizations/graph_visuals.py` | `tests/unit/test_visualizations.py` |
| F-009 | `src/visualizations/graph_2d_visuals.py` | `tests/unit/test_visualizations.py` |
| F-010 | `frontend/app/components/MetricsDashboard.tsx` | `frontend/__tests__/` |
| F-011 | `frontend/app/components/AssetList.tsx` | `frontend/__tests__/` |
| F-012 | `src/reports/schema_report.py` | `tests/unit/test_reports.py` |
| F-013 | `src/analysis/formulaic_analysis.py` | `tests/unit/test_analysis.py` |
| F-014 | `src/data/real_data_fetcher.py` | `tests/unit/test_data.py` |
| F-015 | `src/data/database.py`, `src/data/repository.py` | `tests/unit/test_database.py` |
| F-016 | `app.py` | Manual testing |
| F-017 | `frontend/app/page.tsx`, `frontend/app/components/` | `frontend/__tests__/` |

### 2.5.2 Requirement-to-Feature Traceability

| Requirement Category | Feature IDs | Count |
|---------------------|-------------|-------|
| Data Validation | F-001, F-002 | 9 |
| Graph Processing | F-003 | 5 |
| API Functionality | F-004, F-005, F-006, F-007 | 12 |
| Visualization | F-008, F-009, F-010 | 7 |
| User Interface | F-011, F-012, F-013, F-016, F-017 | 8 |

---

## 2.6 Assumptions and Constraints

### 2.6.1 Assumptions

| ID | Assumption | Impact |
|----|------------|--------|
| A-001 | Users have modern browser (Chrome, Firefox, Safari, Edge) | Visualization features may not work on legacy browsers |
| A-002 | Network connectivity available for real data fetching | System falls back to sample data when offline |
| A-003 | Single concurrent admin user sufficient | Multi-user requires authentication extension |
| A-004 | Dataset size < 500 nodes for optimal visualization | Larger datasets require pagination or filtering |

### 2.6.2 Constraints

| ID | Constraint | Mitigation |
|----|------------|------------|
| C-001 | In-memory graph limits scalability | Database persistence option (F-015) |
| C-002 | Single-user JWT authentication | Role-based access planned for Phase 2 |
| C-003 | Yahoo Finance API rate limits | Caching with atomic file writes |
| C-004 | Browser memory limits visualization | MAX_NODES/MAX_EDGES guardrails |

---

## 2.7 References

### 2.7.1 Source Files Examined

| File Path | Relevance |
|-----------|-----------|
| `src/models/financial_models.py` | Domain model definitions, validation rules, enums |
| `src/logic/asset_graph.py` | Core graph container, relationship discovery |
| `api/main.py` | FastAPI implementation, all REST endpoints |
| `api/auth.py` | JWT authentication, password hashing |
| `app.py` | Gradio UI implementation, tabbed interface |
| `src/data/sample_data.py` | Sample database with 19 assets, 4 events |
| `src/data/real_data_fetcher.py` | Yahoo Finance integration |
| `src/data/database.py` | SQLAlchemy database configuration |
| `src/data/repository.py` | Data access layer |
| `src/visualizations/graph_visuals.py` | 3D Plotly visualization |
| `src/visualizations/graph_2d_visuals.py` | 2D Plotly visualization |
| `src/reports/schema_report.py` | Schema documentation generator |
| `src/analysis/formulaic_analysis.py` | Financial formula library |
| `frontend/app/types/api.ts` | TypeScript API contracts |
| `frontend/app/components/NetworkVisualization.tsx` | 3D graph React component |
| `frontend/app/components/MetricsDashboard.tsx` | Metrics display component |
| `frontend/app/components/AssetList.tsx` | Asset table component |
| `requirements.txt` | Python dependencies |
| `frontend/package.json` | Node.js dependencies |
| `migrations/001_initial.sql` | Database schema |

### 2.7.2 Source Directories Examined

| Directory Path | Contents |
|----------------|----------|
| `src/` | Core Python library packages |
| `src/models/` | Domain model layer |
| `src/logic/` | Graph algorithm implementation |
| `src/data/` | Data persistence and ingestion |
| `src/visualizations/` | Plotly visualization layer |
| `src/analysis/` | Formulaic financial analysis |
| `src/reports/` | Schema documentation generation |
| `api/` | FastAPI backend package |
| `frontend/` | Next.js application root |
| `frontend/app/` | App Router source |
| `frontend/app/components/` | React UI components |
| `frontend/app/types/` | TypeScript API contracts |
| `tests/` | Test harness structure |

### 2.7.3 Technical Specification Cross-References

| Section | Relevance |
|---------|-----------|
| 1.1 Executive Summary | Business context, stakeholders, value proposition |
| 1.2 System Overview | Architecture, technology stack, success criteria |
| 1.3 Scope | In-scope/out-of-scope features, boundaries |
| 1.4 References | Documentation and source file inventory |

# 3. Technology Stack

This section documents the complete technology stack employed by the Financial Asset Relationship Database, including programming languages, frameworks, libraries, external services, data storage solutions, and development infrastructure. Each technology selection is justified based on system requirements, architectural constraints, and integration considerations.

## 3.1 Technology Stack Overview

### 3.1.1 Stack Architecture Summary

The Financial Asset Relationship Database employs a modern, polyglot architecture optimized for financial data visualization and API-driven consumption. The technology choices prioritize type safety, performance, and developer productivity while maintaining deployment flexibility.

```mermaid
flowchart TB
    subgraph Frontend["Frontend Layer"]
        NextJS["Next.js 14.2.35<br/>TypeScript ^5.3.0"]
        Gradio["Gradio ≥4.0.0<br/>Python UI"]
    end

    subgraph Backend["Backend Layer"]
        FastAPI["FastAPI 0.127.0<br/>Python 3.11"]
        Uvicorn["Uvicorn ≥0.24.0<br/>ASGI Server"]
    end

    subgraph Visualization["Visualization Layer"]
        PlotlyPy["Plotly ≥6.0.0<br/>Server-side"]
        PlotlyJS["plotly.js ^2.27.0<br/>Client-side"]
    end

    subgraph Data["Data Layer"]
        SQLAlchemy["SQLAlchemy ≥2.0.0<br/>ORM"]
        yfinance["yfinance ≥0.2.51<br/>Market Data"]
    end

    subgraph Infrastructure["Infrastructure"]
        Docker["Docker<br/>python:3.11-slim"]
        Vercel["Vercel<br/>Serverless"]
        GHACI["GitHub Actions<br/>CircleCI"]
    end

    NextJS --> FastAPI
    Gradio --> PlotlyPy
    FastAPI --> Uvicorn
    FastAPI --> SQLAlchemy
    FastAPI --> yfinance
    NextJS --> PlotlyJS
    FastAPI --> Docker
    NextJS --> Vercel
```

### 3.1.2 Technology Selection Criteria

| Criterion | Priority | Rationale |
|-----------|----------|-----------|
| **Type Safety** | Critical | Financial data requires strict validation to prevent calculation errors |
| **Performance** | High | Sub-500ms API response times for interactive visualizations |
| **Developer Productivity** | High | Rapid prototyping with Gradio; production-ready with Next.js |
| **Ecosystem Maturity** | High | Well-maintained libraries with active security patching |
| **Deployment Flexibility** | Medium | Support for containerized, serverless, and local development |
| **Integration Capability** | Medium | REST API and MCP protocol support for ecosystem integration |

### 3.1.3 Stack Deviations from Default Template

The following default template technologies are **not used** in this project:

| Default Technology | Actual Implementation | Rationale |
|--------------------|----------------------|-----------|
| Flask | FastAPI 0.127.0 | FastAPI provides automatic OpenAPI docs, native async support, and Pydantic integration |
| Auth0 | Custom JWT (PyJWT) | Simpler single-user authentication without external service dependency |
| MongoDB | SQLite/PostgreSQL (SQLAlchemy) | Relational model better suited for asset relationships and regulatory event linkages |
| LangChain | Not applicable | System is not an AI/LLM application |
| React-Native | Web-responsive only | Mobile native applications explicitly out of scope |
| Terraform | Docker Compose + Vercel | Simplified infrastructure for single-application deployment |

---

## 3.2 Programming Languages

### 3.2.1 Python (Backend & Core Logic)

| Attribute | Specification | Evidence |
|-----------|---------------|----------|
| **Minimum Version** | Python 3.10+ | `pyproject.toml`: `requires-python = ">=3.10"` |
| **Supported Versions** | 3.10, 3.11, 3.12 | `ci.yml` matrix configuration |
| **Production Version** | Python 3.11-slim | `Dockerfile` base image |
| **Package Manager** | pip with requirements files | `requirements.txt`, `requirements-dev.txt` |

#### Selection Justification

Python 3.10+ is required for the following technical reasons:

1. **Modern Dataclass Features**: The domain model in `src/models/financial_models.py` leverages enhanced dataclass functionality including `slots=True` for memory efficiency and `kw_only=True` for required parameter enforcement.

2. **Type Annotation Improvements**: Python 3.10 introduced `ParamSpec` and `TypeAlias` which improve type checking for the FastAPI dependency injection system.

3. **Performance Optimizations**: Python 3.11 provides approximately 25% faster execution through specialization improvements, benefiting compute-intensive relationship discovery operations.

4. **Ecosystem Compatibility**: The pinned versions of NumPy 2.2.6, Pandas ≥1.5.0, and Plotly ≥6.0.0 all require Python 3.10+ for full feature support.

#### Primary Use Cases

| Component | Location | Python Usage |
|-----------|----------|--------------|
| REST API Server | `api/main.py` | FastAPI application with async handlers |
| Core Graph Engine | `src/logic/asset_graph.py` | Relationship discovery and metrics calculation |
| Domain Models | `src/models/financial_models.py` | Dataclass definitions with validation |
| Visualization Generation | `src/visualizations/` | Plotly figure construction |
| Legacy UI | `app.py` | Gradio interface |
| Data Fetching | `src/data/real_data_fetcher.py` | Yahoo Finance integration |

### 3.2.2 TypeScript/JavaScript (Frontend)

| Attribute | Specification | Evidence |
|-----------|---------------|----------|
| **TypeScript Version** | ^5.3.0 | `frontend/package.json` |
| **Node.js Version** | >=18.0.0 | `frontend/package.json` engines |
| **npm Version** | >=8.0.0 | `frontend/package.json` engines |
| **Module System** | ES Modules | Next.js App Router conventions |
| **Strict Mode** | Enabled | `frontend/tsconfig.json`: `strict: true` |

#### Selection Justification

TypeScript is selected over plain JavaScript for the following reasons:

1. **API Contract Enforcement**: The frontend consumes strongly-typed API responses (e.g., `MetricsResponse`, `AssetResponse`). TypeScript ensures compile-time validation of response handling.

2. **Plotly Type Safety**: 3D visualization configuration requires precise coordinate arrays and layout objects. TypeScript prevents runtime errors from malformed visualization data.

3. **React Component Props**: Complex component interfaces for `NetworkVisualization`, `MetricsDashboard`, and `AssetList` benefit from explicit prop type definitions.

4. **IDE Productivity**: TypeScript provides enhanced code completion, refactoring support, and inline documentation in modern IDEs.

## Node.js Version Requirements

Node.js 18.0.0+ is required for:

- Next.js 14.x App Router architecture
- Native Fetch API support (no polyfill required)
- ES Module interoperability
- V8 engine optimizations for Plotly.js rendering

---

## 3.3 Frameworks & Libraries

### 3.3.1 Backend Frameworks

#### FastAPI (REST API Framework)

| Attribute | Specification |
|-----------|---------------|
| **Version** | 0.127.0 (pinned) |
| **Source** | `requirements.txt` |
| **Purpose** | REST API framework with automatic validation and documentation |

**Key Features Utilized:**

| Feature | Implementation | Location |
|---------|----------------|----------|
| Lifespan Context Manager | Thread-safe graph initialization at startup | `api/main.py` lines 159-165 |
| Dependency Injection | Authentication via `get_current_user` | `api/auth.py` |
| OAuth2PasswordBearer | JWT token extraction from Authorization header | `api/auth.py` |
| OpenAPI Generation | Auto-generated Swagger UI at `/docs` | FastAPI default |
| Pydantic Integration | Request/response validation | All API endpoints |

**Version Pinning Rationale:**

FastAPI 0.127.0 is explicitly pinned to ensure:
- Compatibility with Pydantic 2.12.5
- Stable behavior for lifespan event handling
- Consistent OpenAPI schema generation

```mermaid
flowchart LR
    subgraph FastAPIApp["FastAPI Application"]
        Lifespan["Lifespan<br/>Manager"]
        Router["API<br/>Router"]
        Middleware["Middleware<br/>Stack"]
    end

    subgraph MiddlewareChain["Middleware Chain"]
        CORS["CORS<br/>Middleware"]
        RateLimit["SlowAPI<br/>Rate Limiter"]
    end

    subgraph DependencySystem["Dependency Injection"]
        Auth["OAuth2<br/>Bearer"]
        UserDep["get_current_user"]
    end

    Lifespan --> Router
    Middleware --> MiddlewareChain
    CORS --> RateLimit
    Router --> DependencySystem
    Auth --> UserDep
```

#### Pydantic (Data Validation)

| Attribute | Specification |
|-----------|---------------|
| **Version** | 2.12.5 (pinned) |
| **Source** | `requirements.txt` |
| **Purpose** | API request/response validation and serialization |

**Version Pinning Rationale:**

Pydantic 2.12.5 is pinned for:
- FastAPI 0.127.0 compatibility
- Consistent JSON schema generation for OpenAPI
- Stable validation behavior across deployments

#### Uvicorn (ASGI Server)

| Attribute | Specification |
|-----------|---------------|
| **Version** | >=0.24.0 |
| **Package** | `uvicorn[standard]` (includes full async support) |
| **Default Port** | 8000 |

**Configuration:**

- Development: `uvicorn api.main:app --reload --port 8000`
- Production: Managed via Docker CMD or Vercel serverless functions

#### Gradio (Legacy UI Framework)

| Attribute | Specification |
|-----------|---------------|
| **Version** | >=4.0.0,<6.0.0 |
| **Source** | `requirements.txt` |
| **Default Port** | 7860 |
| **Purpose** | Python-native web interface for rapid prototyping |

**Selection Justification:**

Gradio provides immediate visual access to system capabilities without frontend development overhead. It serves as:
- A rapid prototyping environment for Python developers
- A reference implementation demonstrating all core features
- A standalone UI option for Python-centric workflows

### 3.3.2 Frontend Frameworks

## Next.js (React Meta-Framework)

| Attribute | Specification |
|-----------|---------------|
| **Version** | 14.2.35 |
| **Source** | `frontend/package.json` |
| **Architecture** | App Router (app/ directory) |
| **Configuration** | `reactStrictMode: true` |

**Selection Justification:**

Next.js 14.x is selected over Create React App for:

1. **App Router Architecture**: File-system based routing with React Server Components support
2. **Build Optimizations**: Automatic code splitting, tree shaking, and bundle analysis
3. **Vercel Integration**: First-class support for serverless deployment target
4. **TypeScript Native**: Zero-configuration TypeScript support

**Key Configuration:**

| Setting | Value | Purpose |
|---------|-------|---------|
| `reactStrictMode` | `true` | Enables additional development checks |
| `NEXT_PUBLIC_API_URL` | Environment variable | Backend API endpoint configuration |
| `NEXT_PUBLIC_MAX_NODES` | 500 | Visualization guardrail |
| `NEXT_PUBLIC_MAX_EDGES` | 2000 | Visualization guardrail |

#### React

| Attribute | Specification |
|-----------|---------------|
| **Version** | ^18.2.0 |
| **Source** | `frontend/package.json` |
| **Mode** | Client Components with `'use client'` directive |

#### Tailwind CSS

| Attribute | Specification |
|-----------|---------------|
| **Version** | ^3.3.0 |
| **Source** | `frontend/package.json` devDependencies |
| **Purpose** | Utility-first CSS framework |

**Selection Justification:**

Tailwind CSS provides:
- Consistent design system without custom CSS maintenance
- Responsive design utilities for visualization containers
- Integration with Next.js JIT compiler for optimal bundle size

### 3.3.3 Visualization Libraries

#### Plotly (Exclusive Visualization Library)

| Context | Package | Version |
|---------|---------|---------|
| **Backend (Python)** | plotly | >=6.0.0 |
| **Frontend (React)** | react-plotly.js | ^2.6.0 |
| **Frontend (Core)** | plotly.js | ^2.27.0 |

**Library Constraint:**

Per project coding standards, Plotly is the **only approved charting and visualization library**. Alternative visualization libraries (e.g., D3, Chart.js, Matplotlib) are explicitly prohibited to maintain consistency across both UI implementations.

**Visualization Capabilities:**

| Visualization Type | Implementation |
|--------------------|----------------|
| 3D Network Graph | `src/visualizations/graph_visuals.py` |
| 2D Network Graph | `src/visualizations/graph_2d_visuals.py` |
| Metrics Dashboard | `src/visualizations/metrics_visuals.py` |
| Formulaic Visuals | `src/visualizations/formulaic_visuals.py` |

**Deterministic Layout:**

All visualizations use `seed=42` for reproducible 3D node positioning, ensuring identical visual output across sessions.

---

## 3.4 Open Source Dependencies

### 3.4.1 Python Runtime Dependencies

**Source:** `requirements.txt`

#### Core Application Dependencies

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| **fastapi** | 0.127.0 (pinned) | REST API framework |
| **uvicorn[standard]** | >=0.24.0 | ASGI server with async support |
| **pydantic** | 2.12.5 (pinned) | Data validation and serialization |
| **gradio** | >=4.0.0,<6.0.0 | Legacy UI framework |

#### Data Processing Dependencies

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| **numpy** | 2.2.6 (pinned) | Numerical computing for graph coordinates |
| **pandas** | >=1.5.0 | Tabular data manipulation |
| **plotly** | >=6.0.0 | Visualization generation |
| **dataclasses-json** | >=0.5.7 | JSON serialization for domain models |

#### External Data Dependencies

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| **yfinance** | >=0.2.51 | Yahoo Finance API integration |
| **requests** | >=2.32.2 | HTTP client for external requests |

**Library Constraint:**

Per project coding standards, yfinance is the **only approved finance data API**. Alternative providers (e.g., Alpha Vantage, IEX Cloud) require explicit approval.

#### Security Dependencies

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| **PyJWT** | >=2.8.0 | JWT token signing and verification |
| **passlib[bcrypt]** | >=1.7.4 | Password hashing (pbkdf2_sha256) |
| **slowapi** | >=0.1.4 | Rate limiting middleware |

#### Database Dependencies

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| **sqlalchemy** | >=2.0.0 | ORM with 2.x Mapped/mapped_column syntax |
| **psycopg2-binary** | >=2.9.9 | PostgreSQL adapter for production |

#### Serverless/Protocol Dependencies

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| **mangum** | >=0.17.0 | AWS Lambda ASGI adapter |
| **mcp** | >=1.0.0 | Model Context Protocol |
| **fastmcp** | >=0.1.0 | FastMCP server implementation |

#### Compatibility Pins

| Package | Version Constraint | Reason |
|---------|-------------------|--------|
| **h11** | 0.16.0 (pinned) | HTTP/1.1 protocol compatibility with uvicorn/httpx |
| **httpx** | 0.28.1 (pinned) | Test HTTP client compatibility |
| **anyio** | 4.12.0 (pinned) | Async I/O compatibility with httpx |

#### Security-Mandated Pins (Snyk)

| Package | Version Constraint | Vulnerability Mitigation |
|---------|-------------------|-------------------------|
| **urllib3** | >=2.6.0 | Known vulnerability patch |
| **zipp** | >=3.19.1 | Known vulnerability patch |

### 3.4.2 Python Development Dependencies

**Source:** `requirements-dev.txt`

| Category | Package | Version | Purpose |
|----------|---------|---------|---------|
| **Testing** | pytest | >=7.0.0 | Test framework |
| **Testing** | pytest-cov | >=4.0.0 | Coverage reporting |
| **Testing** | pytest-asyncio | >=0.21.0 | Async test support |
| **Linting** | flake8 | >=6.0.0 | Style linting |
| **Linting** | pylint | >=2.17.0 | Static analysis |
| **Type Checking** | mypy | >=1.0.0 | Type checking |
| **Formatting** | black | >=23.0.0 | Code formatting |
| **Formatting** | isort | >=5.12.0 | Import sorting |
| **Git Hooks** | pre-commit | >=3.0.0 | Pre-commit hook management |
| **Configuration** | PyYAML | >=6.0 | YAML parsing |
| **Type Stubs** | types-PyYAML | - | Type annotations for PyYAML |

### 3.4.3 Frontend Runtime Dependencies

**Source:** `frontend/package.json`

| Package | Version | Purpose |
|---------|---------|---------|
| **next** | 14.2.35 | React framework with App Router |
| **react** | ^18.2.0 | UI component library |
| **react-dom** | ^18.2.0 | React DOM renderer |
| **axios** | ^1.13.2 | HTTP client for API communication |
| **plotly.js** | ^2.27.0 | 3D visualization engine |
| **react-plotly.js** | ^2.6.0 | React Plotly wrapper component |
| **recharts** | ^2.10.0 | Additional charting (secondary) |

### 3.4.4 Frontend Development Dependencies

**Source:** `frontend/package.json`

| Category | Package | Version | Purpose |
|----------|---------|---------|---------|
| **TypeScript** | typescript | ^5.3.0 | Type safety |
| **Styling** | tailwindcss | ^3.3.0 | CSS framework |
| **Styling** | postcss | ^8.4.31 | CSS processing |
| **Styling** | autoprefixer | ^10.4.16 | Vendor prefixing |
| **Testing** | jest | ^29.7.0 | Test framework |
| **Testing** | jest-environment-jsdom | ^29.7.0 | DOM testing environment |
| **Testing** | @testing-library/react | ^14.1.2 | React component testing |
| **Testing** | @testing-library/jest-dom | ^6.1.5 | DOM assertion matchers |
| **Testing** | @testing-library/user-event | ^14.5.1 | User interaction simulation |
| **Linting** | eslint | ^8.55.0 | Code linting |
| **Linting** | eslint-config-next | ^14.0.0 | Next.js ESLint rules |

### 3.4.5 Dependency Version Strategy

```mermaid
flowchart TD
    subgraph VersionStrategy["Version Constraint Strategy"]
        Pinned["Pinned Versions"]
        Minimum["Minimum Versions"]
        Range["Version Ranges"]
    end

    subgraph PinnedPackages["Pinned (Critical Compatibility)"]
        FastAPIPkg["fastapi 0.127.0"]
        PydanticPkg["pydantic 2.12.5"]
        NumpyPkg["numpy 2.2.6"]
        H11Pkg["h11 0.16.0"]
    end

    subgraph MinimumPackages["Minimum (Security + Features)"]
        SQLAlchemyPkg["sqlalchemy >=2.0.0"]
        PyJWTPkg["PyJWT >=2.8.0"]
        Urllib3Pkg["urllib3 >=2.6.0"]
    end

    subgraph RangePackages["Range (Compatibility)"]
        GradioPkg["gradio >=4.0.0,<6.0.0"]
        NextPkg["next ^14.2.35"]
    end

    Pinned --> PinnedPackages
    Minimum --> MinimumPackages
    Range --> RangePackages
```

---

## 3.5 Third-Party Services

### 3.5.1 External Data APIs

#### Yahoo Finance (via yfinance)

| Attribute | Specification |
|-----------|---------------|
| **Library** | yfinance >=0.2.51 |
| **Enable Flag** | `USE_REAL_DATA_FETCHER` environment variable |
| **Implementation** | `src/data/real_data_fetcher.py` |

**Supported Symbols:**

| Category | Symbols |
|----------|---------|
| **Equities** | AAPL, MSFT, XOM, JPM |
| **Bond ETFs** | TLT, LQD, HYG |
| **Commodities** | GC=F (Gold), CL=F (Crude Oil), SI=F (Silver) |
| **Currencies** | EURUSD=X, GBPUSD=X, JPYUSD=X |

**Rate Limit Mitigation:**

| Strategy | Implementation |
|----------|----------------|
| **File Caching** | JSON cache with atomic writes via `NamedTemporaryFile` + `os.replace` |
| **Cache Path** | Configurable via `REAL_DATA_CACHE_PATH` environment variable |
| **Fallback** | Sample data when network disabled or unavailable |

### 3.5.2 Authentication Services

The system implements **custom JWT authentication** rather than external identity providers:

| Component | Technology | Configuration |
|-----------|------------|---------------|
| **Token Signing** | PyJWT >=2.8.0 | HS256 algorithm |
| **Token Expiration** | 30 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| **Password Hashing** | passlib (pbkdf2_sha256) | `CryptContext` with pbkdf2_sha256 scheme |
| **Secret Management** | Environment variables | `SECRET_KEY` (required) |

**Authentication Flow:**

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant AuthModule
    participant Database

    Client->>FastAPI: POST /token (credentials)
    FastAPI->>AuthModule: Validate credentials
    AuthModule->>Database: Query user_credentials
    Database-->>AuthModule: User record
    AuthModule->>AuthModule: Verify password hash
    AuthModule->>AuthModule: Create JWT (HS256)
    AuthModule-->>FastAPI: Access token
    FastAPI-->>Client: JWT token (30 min expiry)

    Client->>FastAPI: GET /api/assets (Bearer token)
    FastAPI->>AuthModule: Validate JWT
    AuthModule->>AuthModule: Decode and verify
    AuthModule-->>FastAPI: User identity
    FastAPI-->>Client: Protected resource
```

### 3.5.3 CI/CD & Code Quality Services

| Service | Purpose | Integration |
|---------|---------|-------------|
| **GitHub Actions** | Primary CI pipeline | `.github/workflows/ci.yml` |
| **CircleCI** | Secondary CI pipeline | `.circleci/config.yml` |
| **Codecov** | Coverage reporting | Uploads `coverage.xml` |
| **GitHub Advanced Security** | Security analysis | SARIF uploads |
| **Codacy** | Code quality analysis | Automated reviews |
| **Snyk** | Dependency vulnerability scanning | Version pins |
| **Bandit** | Python security analysis | CI security job |
| **Safety** | Dependency security checks | CI security job |

### 3.5.4 Deployment Platforms

| Platform | Purpose | Configuration |
|----------|---------|---------------|
| **Vercel** | Production hosting | `vercel.json` |
| **Docker Hub** | Container registry | `Dockerfile`, `docker-compose.yml` |

---

## 3.6 Databases & Storage

### 3.6.1 Primary Storage: In-Memory Graph

| Attribute | Specification |
|-----------|---------------|
| **Data Structure** | `Dict[source_id, List[Tuple[target_id, rel_type, strength]]]` |
| **Implementation** | `src/logic/asset_graph.py` |
| **Thread Safety** | Double-checked locking singleton pattern |
| **Size Constraint** | Optimal performance for < 500 nodes |

**Justification:**

In-memory storage is selected for the primary graph due to:
- Sub-millisecond relationship traversal for visualization
- No external database dependency for deployment simplicity
- Sufficient capacity for the 19-asset sample dataset and moderate production workloads

**Thread-Safe Initialization:**

```mermaid
flowchart TD
    subgraph Initialization["Graph Initialization"]
        Request["API Request"]
        CheckGlobal{"Global<br/>graph exists?"}
        AcquireLock["Acquire<br/>Thread Lock"]
        DoubleCheck{"Double-check<br/>inside lock?"}
        CreateGraph["Create Graph<br/>Instance"]
        BuildRelationships["Build<br/>Relationships"]
        SetGlobal["Set Global<br/>Reference"]
        ReleaseLock["Release<br/>Lock"]
        ReturnGraph["Return<br/>Graph"]
    end

    Request --> CheckGlobal
    CheckGlobal -->|No| AcquireLock
    CheckGlobal -->|Yes| ReturnGraph
    AcquireLock --> DoubleCheck
    DoubleCheck -->|No| CreateGraph
    DoubleCheck -->|Yes| ReleaseLock
    CreateGraph --> BuildRelationships
    BuildRelationships --> SetGlobal
    SetGlobal --> ReleaseLock
    ReleaseLock --> ReturnGraph
```

### 3.6.2 SQLite (API Authentication)

| Attribute | Specification |
|-----------|---------------|
| **Purpose** | User credentials storage |
| **Implementation** | `api/database.py` |
| **Environment Variable** | `DATABASE_URL` (required for auth) |
| **Features** | Connection pooling, row factory, in-memory support |

**Schema:**

```
TABLE user_credentials (
    username TEXT PRIMARY KEY,
    email TEXT,
    full_name TEXT,
    hashed_password TEXT NOT NULL,
    disabled BOOLEAN DEFAULT FALSE
)
```

### 3.6.3 SQLAlchemy ORM (Optional Persistence)

| Attribute | Specification |
|-----------|---------------|
| **Version** | SQLAlchemy >=2.0.0 |
| **Syntax** | 2.x with `Mapped`/`mapped_column` |
| **Implementation** | `src/data/database.py`, `src/data/db_models.py` |
| **Environment Variable** | `ASSET_GRAPH_DATABASE_URL` |

**Supported Database Backends:**

| Backend | Use Case | Connection String |
|---------|----------|-------------------|
| **SQLite** | Development | `sqlite:///path/to/db.sqlite` |
| **SQLite In-Memory** | Testing | `sqlite:///:memory:` with `StaticPool` |
| **PostgreSQL** | Production | `postgresql://user:pass@host/db` |

**Database Schema (migrations/001_initial.sql):**

| Table | Purpose |
|-------|---------|
| **assets** | Primary entity table for financial instruments |
| **asset_relationships** | Directed edge table with unique constraint |
| **regulatory_events** | Event records with impact scoring |
| **regulatory_event_assets** | Many-to-many junction table |

### 3.6.4 Caching Strategy

| Cache Type | Implementation | Configuration |
|------------|----------------|---------------|
| **Real Data Cache** | JSON file with atomic writes | `REAL_DATA_CACHE_PATH` |
| **Graph Cache** | Optional JSON serialization | `GRAPH_CACHE_PATH` |

**Atomic Write Pattern:**

```
1. Write to NamedTemporaryFile in same directory
2. Flush and sync to disk
3. os.replace() atomic rename to target path
4. Guarantees no partial writes on failure
```

---

## 3.7 Development & Deployment

### 3.7.1 Development Tools

#### Makefile Commands

**Source:** `Makefile`

| Command | Purpose |
|---------|---------|
| `make install` | Install production dependencies |
| `make install-dev` | Install development dependencies |
| `make test` | Run pytest with coverage |
| `make lint` | Run flake8 + pylint |
| `make format` | Format with black + isort |
| `make type-check` | Run mypy type checking |
| `make check` | Full quality check pipeline |
| `make docker-compose-up` | Build and start containers |

#### Pre-commit Hooks

**Source:** `.pre-commit-config.yaml`

| Hook | Tool | Configuration |
|------|------|---------------|
| **Formatting** | black | `line-length: 120` |
| **Import Sorting** | isort | `profile: black` |
| **Linting** | flake8 | `.flake8` config file |

#### Code Quality Tools Configuration

| Tool | Config Source | Key Settings |
|------|---------------|--------------|
| **black** | `pyproject.toml` | `line-length = 120` |
| **isort** | `pyproject.toml` | `profile = "black"` |
| **mypy** | `pyproject.toml` | Strict type checking |
| **flake8** | `.flake8` | E501 max-line-length |
| **pylint** | `.pylintrc` | Customized rules |

### 3.7.2 Build System

#### Python Build Configuration

**Source:** `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"
```

#### Frontend Build Scripts

**Source:** `frontend/package.json`

| Script | Command | Purpose |
|--------|---------|---------|
| `npm run dev` | `next dev` | Development server with hot reload |
| `npm run build` | `next build` | Production build |
| `npm run start` | `next start` | Production server |
| `npm run lint` | `next lint` | ESLint analysis |
| `npm test` | `jest --silent` | Run test suite |
| `npm test -- --coverage` | `jest --coverage` | Coverage report |

### 3.7.3 Containerization

#### Docker Configuration

**Source:** `Dockerfile`

| Attribute | Specification |
|-----------|---------------|
| **Base Image** | `python:3.11-slim` |
| **Working Directory** | `/app` |
| **User** | Non-root `appuser` (UID 1000) |
| **Exposed Port** | 7860 (Gradio) |
| **Health Check** | HTTP probe every 30s |

**Security Considerations:**

| Practice | Implementation |
|----------|----------------|
| **Non-root User** | `useradd -m -u 1000 appuser` |
| **Minimal Base Image** | `python:3.11-slim` (no dev tools) |
| **Health Monitoring** | `HEALTHCHECK` instruction with curl |

#### Docker Compose Configuration

**Source:** `docker-compose.yml`

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "7860:7860"
    environment:
      - GRADIO_SERVER_NAME=0.0.0.0
      - GRADIO_SERVER_PORT=7860
    volumes:
      - ./src:/app/src
      - ./data:/app/data
    restart: unless-stopped
```

### 3.7.4 CI/CD Pipeline

#### GitHub Actions (Primary)

**Source:** `.github/workflows/ci.yml`

```mermaid
flowchart LR
    subgraph TestJob["Test Job"]
        Matrix["Python Matrix<br/>3.10, 3.11, 3.12"]
        Lint["Linting<br/>flake8, black, isort"]
        Pylint["Static Analysis<br/>pylint"]
        Tests["pytest<br/>+ coverage"]
    end

    subgraph SecurityJob["Security Job"]
        Safety["safety check"]
        Bandit["bandit scan"]
    end

    subgraph CoverageJob["Coverage Job"]
        Codecov["Upload to<br/>Codecov"]
    end

    Matrix --> Lint
    Lint --> Pylint
    Pylint --> Tests
    Tests --> SecurityJob
    Tests --> CoverageJob
```

**Job Configuration:**

| Job | Actions |
|-----|---------|
| **test** | Matrix Python 3.10/3.11/3.12, linting, pytest with coverage |
| **security** | safety check, bandit scan |
| **coverage** | Upload to Codecov (Python 3.11 only) |

#### CircleCI (Secondary)

**Source:** `.circleci/config.yml`

| Job | Actions |
|-----|---------|
| **python-lint** | flake8 with `.flake8` config |
| **python-test** | pytest with parallelism=4, JUnit XML output |
| **python-security** | safety + bandit |
| **frontend-lint** | npm run lint |
| **frontend-build** | npm run build |
| **docker-build** | Build container + smoke test |

#### Scheduled Security Scans

| Schedule | Workflow | Target |
|----------|----------|--------|
| Nightly (02:00 UTC) | Security workflow | main branch |

### 3.7.5 Deployment Options

#### Local Development

| Component | Command | Port |
|-----------|---------|------|
| **FastAPI Backend** | `uvicorn api.main:app --reload --port 8000` | 8000 |
| **Next.js Frontend** | `cd frontend && npm run dev` | 3000 |
| **Gradio Legacy UI** | `python app.py` | 7860 |

#### Vercel Serverless

**Source:** `vercel.json`

| Build | Configuration |
|-------|---------------|
| **Backend** | `@vercel/python`, maxLambdaSize: 50mb |
| **Frontend** | `@vercel/next` |

**Routes:**

| Pattern | Destination |
|---------|-------------|
| `/api/(.*)` | `api/main.py` |
| `/(.*)` | `frontend/$1` |

#### Docker Production

```bash
docker-compose up --build
# OR
make docker-compose-up
```

---

## 3.8 Security Considerations

### 3.8.1 Authentication Security

| Aspect | Implementation |
|--------|----------------|
| **Algorithm** | HS256 (HMAC-SHA256) |
| **Secret Key** | Environment variable (`SECRET_KEY`) |
| **Token Expiration** | 30 minutes default |
| **Password Hashing** | pbkdf2_sha256 via passlib |

### 3.8.2 API Security

| Protection | Implementation |
|------------|----------------|
| **Rate Limiting** | slowapi: 5 req/min on `/token`, 10 req/min on `/api/users/me` |
| **CORS** | Environment-specific allowlists; no wildcard `*` origins |
| **Input Validation** | Pydantic models with strict type enforcement |

### 3.8.3 Deployment Security

| Practice | Implementation |
|----------|----------------|
| **Container User** | Non-root `appuser` (UID 1000) |
| **Secrets Management** | Environment variables only; never committed |
| **Dependency Scanning** | Snyk, Safety, Bandit in CI pipeline |
| **HTTPS** | Required in production; Vercel provides TLS termination |

### 3.8.4 CORS Configuration

| Environment | Allowed Origins |
|-------------|-----------------|
| **Development** | `http://localhost:3000`, `http://localhost:7860` |
| **Production** | HTTPS origins only; Vercel preview domains via regex validation |
| **Custom** | `ALLOWED_ORIGINS` environment variable (comma-separated) |

---

## 3.9 Integration Requirements

### 3.9.1 Frontend-Backend Communication

| Aspect | Specification |
|--------|---------------|
| **Protocol** | REST over HTTPS (production) / HTTP (development) |
| **Data Format** | JSON |
| **Authentication** | Bearer token in `Authorization` header |
| **API Base URL** | `NEXT_PUBLIC_API_URL` environment variable |

### 3.9.2 Database Connectivity

| Backend | Connection Handling |
|---------|---------------------|
| **SQLite** | Single connection for in-memory; file-based for persistence |
| **PostgreSQL** | psycopg2-binary with connection pooling |
| **In-Memory Testing** | SQLAlchemy `StaticPool` for connection reuse |

### 3.9.3 External Data Source Integration

| Source | Integration Pattern |
|--------|---------------------|
| **Yahoo Finance** | Rate-limited with JSON file caching |
| **Fallback** | Sample data generator when network unavailable |
| **Enable Flag** | `USE_REAL_DATA_FETCHER` environment variable |

### 3.9.4 Component Version Compatibility Matrix

| Component A | Component B | Constraint |
|-------------|-------------|------------|
| FastAPI 0.127.0 | Pydantic 2.12.5 | Pinned together |
| NumPy 2.2.6 | Pandas >=1.5.0 | NumPy 2.x compatibility |
| Next.js 14.2.x | React 18.2.0 | React 18 required |
| Uvicorn >=0.24.0 | h11 0.16.0 | HTTP protocol compatibility |

---

## 3.10 References

### 3.10.1 Configuration Files Examined

| File | Purpose |
|------|---------|
| `requirements.txt` | Python runtime dependencies with pinned versions |
| `requirements-dev.txt` | Python development/testing dependencies |
| `pyproject.toml` | Python packaging, build config, tool configurations |
| `frontend/package.json` | Node.js/Next.js dependencies |
| `frontend/tsconfig.json` | TypeScript configuration |
| `Dockerfile` | Container configuration |
| `docker-compose.yml` | Multi-container orchestration |
| `vercel.json` | Serverless deployment configuration |
| `.github/workflows/ci.yml` | GitHub Actions CI pipeline |
| `.circleci/config.yml` | CircleCI CI pipeline |
| `Makefile` | Build automation commands |
| `.env.example` | Environment variable templates |
| `.pre-commit-config.yaml` | Pre-commit hook configuration |

### 3.10.2 Source Files Examined

| File | Purpose |
|------|---------|
| `api/main.py` | FastAPI application with CORS, auth, rate limiting |
| `api/auth.py` | JWT authentication implementation |
| `api/database.py` | SQLite database module for API auth |
| `src/data/database.py` | SQLAlchemy ORM configuration |
| `src/data/real_data_fetcher.py` | Yahoo Finance integration |
| `src/logic/asset_graph.py` | Core graph engine |
| `src/models/financial_models.py` | Domain model dataclasses |
| `app.py` | Gradio UI entry point |
| `mcp_server.py` | FastMCP server for Model Context Protocol |

### 3.10.3 Folders Explored

| Folder | Purpose |
|--------|---------|
| `api/` | FastAPI backend application |
| `src/` | Core Python packages |
| `src/data/` | Data layer and database |
| `src/visualizations/` | Plotly visualization generators |
| `frontend/` | Next.js application |
| `frontend/app/` | App Router pages and components |
| `.github/workflows/` | GitHub Actions configurations |
| `.circleci/` | CircleCI configurations |
| `migrations/` | Database migration scripts |

### 3.10.4 Technical Specification Cross-References

| Section | Reference Purpose |
|---------|-------------------|
| 1.2 System Overview | Architecture context and technology summary |
| 2.1 Feature Catalog | Feature technology dependencies |
| 2.4 Implementation Considerations | Technical constraints and requirements |
| 2.6 Assumptions and Constraints | Scalability and operational constraints |
| 1.3 Scope | System boundaries and excluded technologies |

# 4. Process Flowchart

This section documents the complete process workflows, state transitions, and integration patterns that govern the Financial Asset Relationship Database system. Each workflow is presented with detailed Mermaid.js diagrams illustrating decision points, error handling paths, system boundaries, and timing considerations.

## 4.1 High-Level System Workflow

### 4.1.1 End-to-End System Architecture Flow

The Financial Asset Relationship Database operates through a layered architecture where user interactions flow from presentation layers through API services to core business logic and data sources. The following diagram illustrates the complete end-to-end data flow across all system components.

```mermaid
flowchart TB
    subgraph UserLayer["User Layer"]
        User([User])
    end

    subgraph PresentationLayer["Presentation Layer"]
        GradioUI["Gradio UI<br/>(app.py:7860)"]
        NextJS["Next.js Frontend<br/>(frontend/:3000)"]
    end

    subgraph APILayer["API Layer"]
        FastAPI["FastAPI Backend<br/>(api/main.py:8000)"]
        Auth["JWT Authentication<br/>(api/auth.py)"]
        RateLimit["Rate Limiter<br/>(slowapi)"]
        CORS["CORS Middleware"]
    end

    subgraph BusinessLogic["Business Logic Layer"]
        GraphEngine["Asset Graph Engine<br/>(src/logic/asset_graph.py)"]
        RelBuilder["Relationship Builder<br/>(8 relationship types)"]
        MetricsCalc["Metrics Calculator"]
        VizData["Visualization Data<br/>Generator"]
    end

    subgraph DataLayer["Data Layer"]
        SampleData["Sample Data<br/>(src/data/sample_data.py)"]
        RealData["Real Data Fetcher<br/>(src/data/real_data_fetcher.py)"]
        YahooFinance["Yahoo Finance<br/>(yfinance)"]
        Cache["JSON File Cache"]
    end

    User --> GradioUI
    User --> NextJS
    GradioUI --> GraphEngine
    NextJS --> FastAPI
    FastAPI --> CORS
    CORS --> RateLimit
    RateLimit --> Auth
    Auth --> GraphEngine
    GraphEngine --> RelBuilder
    GraphEngine --> MetricsCalc
    GraphEngine --> VizData
    RelBuilder --> SampleData
    RelBuilder --> RealData
    RealData --> YahooFinance
    RealData --> Cache
```

### 4.1.2 Request Processing Pipeline

All API requests traverse a standardized pipeline that enforces security policies, rate limits, and proper error handling. The pipeline ensures consistent request processing regardless of the specific endpoint being accessed.

```mermaid
flowchart LR
    subgraph RequestPipeline["Request Processing Pipeline"]
        A[Incoming<br/>Request] --> B{CORS<br/>Valid?}
        B -->|Yes| C{Rate Limit<br/>OK?}
        B -->|No| D[403 Forbidden]
        C -->|Yes| E{Auth<br/>Required?}
        C -->|No| F[429 Too Many<br/>Requests]
        E -->|Yes| G{Token<br/>Valid?}
        E -->|No| H[Process<br/>Request]
        G -->|Yes| H
        G -->|No| I[401<br/>Unauthorized]
        H --> J{Success?}
        J -->|Yes| K[200 Response]
        J -->|No| L[Error Response<br/>4xx/5xx]
    end
```

### 4.1.3 System Startup Sequence

The system startup sequence orchestrates the initialization of all components in the correct order, ensuring dependencies are satisfied before dependent components activate.

```mermaid
sequenceDiagram
    participant Uvicorn as Uvicorn Server
    participant FastAPI as FastAPI App
    participant Lifespan as Lifespan Manager
    participant Graph as Graph Singleton
    participant Factory as Graph Factory
    participant Data as Data Source
    participant Cache as Cache Layer

    Uvicorn->>FastAPI: Start Application
    FastAPI->>Lifespan: Enter Lifespan Context
    Lifespan->>Graph: get_graph()
    Graph->>Graph: Acquire Thread Lock

    alt Graph Not Initialized
        Graph->>Factory: Check Custom Factory
        alt Custom Factory Set
            Factory-->>Graph: Create Test Graph
        else GRAPH_CACHE_PATH Set
            Graph->>Cache: Load Cached Graph
            Cache-->>Graph: Return Cached Data
        else USE_REAL_DATA_FETCHER
            Graph->>Data: RealDataFetcher.create_real_database()
            Data-->>Graph: Return Live Data
        else Default Mode
            Graph->>Data: SampleDatabase.create_sample_database()
            Data-->>Graph: Return Sample Data
        end
    end

    Graph->>Graph: Release Thread Lock
    Graph-->>Lifespan: Graph Ready
    Lifespan-->>FastAPI: Startup Complete
    FastAPI-->>Uvicorn: Accepting Requests
```

## 4.2 Core Business Process Flows

### 4.2.1 Authentication Workflow

The JWT-based authentication system implements a complete credential validation and token management workflow with security controls including rate limiting, constant-time password comparison, and token expiration enforcement.

```mermaid
flowchart TB
    subgraph AuthFlow["Authentication Flow"]
        Start([User Submits<br/>Credentials]) --> RateCheck{Rate Limit<br/>5/min OK?}
        RateCheck -->|No| RateError[429 Too Many<br/>Requests]
        RateCheck -->|Yes| ParseForm[Parse OAuth2<br/>Form Data]
        ParseForm --> LookupUser[Lookup User<br/>in Repository]
        LookupUser --> UserExists{User<br/>Found?}
        UserExists -->|No| AuthFail[401 Incorrect<br/>Username/Password]
        UserExists -->|Yes| VerifyPwd[Verify Password<br/>pbkdf2_sha256]
        VerifyPwd --> PwdValid{Password<br/>Valid?}
        PwdValid -->|No| AuthFail
        PwdValid -->|Yes| CheckActive{User<br/>Active?}
        CheckActive -->|No| InactiveError[400 Inactive<br/>User]
        CheckActive -->|Yes| CreateToken[Create JWT Token<br/>30min Expiry]
        CreateToken --> ReturnToken[Return<br/>access_token<br/>token_type: bearer]
        ReturnToken --> EndSuccess([Success])
    end
```

#### Token Validation Subprocess

Protected endpoints validate tokens through a standardized subprocess that checks token integrity, expiration, and user status.

```mermaid
flowchart TB
    subgraph TokenValidation["Token Validation Subprocess"]
        TokenStart([Protected<br/>Endpoint Called]) --> ExtractToken[Extract Bearer<br/>Token from Header]
        ExtractToken --> HasToken{Token<br/>Present?}
        HasToken -->|No| NoToken[401 Not<br/>Authenticated]
        HasToken -->|Yes| DecodeJWT[Decode JWT<br/>with SECRET_KEY]
        DecodeJWT --> DecodeOK{Decode<br/>Successful?}
        DecodeOK -->|No| InvalidToken[401 Could Not<br/>Validate Credentials]
        DecodeOK -->|Yes| CheckExpiry{Token<br/>Expired?}
        CheckExpiry -->|Yes| ExpiredToken[401 Token<br/>Has Expired]
        CheckExpiry -->|No| ExtractUsername[Extract Username<br/>from Payload]
        ExtractUsername --> LookupUser2[Lookup User<br/>in Repository]
        LookupUser2 --> UserFound{User<br/>Found?}
        UserFound -->|No| InvalidToken
        UserFound -->|Yes| CheckActive2{User<br/>Active?}
        CheckActive2 -->|No| InactiveUser[400 Inactive<br/>User]
        CheckActive2 -->|Yes| ReturnUser[Return<br/>Authenticated User]
        ReturnUser --> TokenEnd([Proceed to<br/>Endpoint Logic])
    end
```

### 4.2.2 Data Ingestion Workflow

The data ingestion workflow manages the creation and population of the asset graph from various data sources, implementing caching, fallback mechanisms, and atomic write operations for data integrity.

```mermaid
flowchart TB
    subgraph DataIngestion["Data Ingestion Workflow"]
        IngestStart([Start Data<br/>Ingestion]) --> CheckCache{Cache File<br/>Exists?}
        CheckCache -->|Yes| LoadCache[Load Cached<br/>Graph JSON]
        LoadCache --> CacheValid{Cache<br/>Valid?}
        CacheValid -->|Yes| UseCache[Use Cached<br/>Graph Data]
        CacheValid -->|No| FreshFetch[Proceed to<br/>Fresh Fetch]
        CheckCache -->|No| FreshFetch
        FreshFetch --> CheckNetwork{Network<br/>Enabled?}
        CheckNetwork -->|No| UseFallback[Use Fallback<br/>Sample Data]
        CheckNetwork -->|Yes| FetchEquities[Fetch Equities<br/>AAPL, MSFT, XOM, JPM]
        FetchEquities --> FetchBonds[Fetch Bond ETFs<br/>TLT, LQD, HYG]
        FetchBonds --> FetchCommodities[Fetch Commodities<br/>GC=F, CL=F, SI=F]
        FetchCommodities --> FetchCurrencies[Fetch Currencies<br/>EURUSD, GBPUSD, JPYUSD]
        FetchCurrencies --> CreateEvents[Create Regulatory<br/>Events]
        CreateEvents --> PopulateGraph[Populate Graph<br/>with Assets]
        PopulateGraph --> BuildRelations[Build<br/>Relationships]
        BuildRelations --> SaveCache[Save to Cache<br/>Atomic Write]
        UseCache --> IngestEnd([Graph<br/>Ready])
        UseFallback --> PopulateSample[Populate Sample<br/>Database]
        PopulateSample --> BuildRelations
        SaveCache --> IngestEnd
    end
```

#### Atomic Cache Write Subprocess

The atomic cache write operation ensures data integrity by using temporary files and atomic rename operations.

```mermaid
flowchart LR
    subgraph AtomicWrite["Atomic Cache Write"]
        WriteStart([Start<br/>Cache Write]) --> CreateTemp[Create<br/>NamedTemporaryFile]
        CreateTemp --> WriteJSON[Write JSON<br/>to Temp File]
        WriteJSON --> CloseTemp[Close<br/>Temp File]
        CloseTemp --> AtomicReplace[os.replace()<br/>Atomic Rename]
        AtomicReplace --> WriteEnd([Cache Write<br/>Complete])
    end
```

### 4.2.3 Relationship Discovery Workflow

The relationship discovery engine processes all assets to identify eight distinct relationship types using rule-based detection algorithms.

```mermaid
flowchart TB
    subgraph RelDiscovery["Relationship Discovery Workflow"]
        RelStart([Start Relationship<br/>Discovery]) --> GetAssets[Get All<br/>Assets]
        GetAssets --> InitRels[Initialize Empty<br/>Relationships Dict]
        InitRels --> SameSector[Detect<br/>same_sector<br/>Bidirectional]
        SameSector --> CorpBond[Detect<br/>corporate_bond_to_equity<br/>Directional]
        CorpBond --> CommodExp[Detect<br/>commodity_exposure<br/>Directional]
        CommodExp --> CurrRisk[Detect<br/>currency_risk<br/>Directional]
        CurrRisk --> IncomeComp[Detect<br/>income_comparison<br/>Bidirectional]
        IncomeComp --> RegImpact[Detect<br/>regulatory_impact<br/>Directional]
        RegImpact --> MarketCap[Detect<br/>market_cap_similar<br/>Bidirectional]
        MarketCap --> Correlation[Detect<br/>correlation<br/>Bidirectional]
        Correlation --> StoreRels[Store Relationships<br/>in Graph]
        StoreRels --> RelEnd([Relationships<br/>Built])
    end
```

#### Relationship Detection Rules

| Relationship Type | Detection Rule | Directionality | Strength Calculation |
|-------------------|----------------|----------------|----------------------|
| `same_sector` | Assets share identical sector value | Bidirectional | Fixed: 0.8 |
| `corporate_bond_to_equity` | Bond.issuer_id matches Equity.id | Directional | Based on credit rating |
| `commodity_exposure` | Equity sector linked to commodity type | Directional | Sector correlation coefficient |
| `currency_risk` | Asset currency ≠ USD | Directional | Exchange rate volatility |
| `income_comparison` | Dividend yield vs bond yield comparison | Bidirectional | Yield differential |
| `regulatory_impact` | Shared regulatory event with impact_score | Directional | Event impact_score |
| `market_cap_similar` | Market cap within 50% range | Bidirectional | Similarity ratio |
| `correlation` | Price correlation > threshold | Bidirectional | Correlation coefficient |

## 4.3 API Request Workflows

### 4.3.1 Asset Listing Flow

The asset listing endpoint (`GET /api/assets`) supports optional filtering by asset class and sector with efficient iteration over the in-memory graph.

```mermaid
flowchart TB
    subgraph AssetListing["GET /api/assets Workflow"]
        ListStart([GET /api/assets<br/>Request]) --> ParseParams[Parse Query<br/>Parameters]
        ParseParams --> GetGraph[get_graph()<br/>Thread-Safe]
        GetGraph --> InitResults[Initialize<br/>Results List]
        InitResults --> IterAssets[Iterate<br/>graph.assets]
        IterAssets --> NextAsset{More<br/>Assets?}
        NextAsset -->|Yes| CheckClassFilter{asset_class<br/>Filter Set?}
        CheckClassFilter -->|Yes| MatchClass{Asset Matches<br/>Class?}
        MatchClass -->|No| IterAssets
        MatchClass -->|Yes| CheckSectorFilter
        CheckClassFilter -->|No| CheckSectorFilter{sector<br/>Filter Set?}
        CheckSectorFilter -->|Yes| MatchSector{Asset Matches<br/>Sector?}
        MatchSector -->|No| IterAssets
        MatchSector -->|Yes| Serialize[serialize_asset()]
        CheckSectorFilter -->|No| Serialize
        Serialize --> AddResult[Add to<br/>Results]
        AddResult --> IterAssets
        NextAsset -->|No| ReturnList[Return<br/>List of Assets]
        ReturnList --> ListEnd([200 OK<br/>JSON Response])
    end
```

### 4.3.2 Visualization Data Flow

The visualization endpoint (`GET /api/visualization`) generates complete 3D graph data including node positions, colors, and edge connections.

```mermaid
flowchart TB
    subgraph VizFlow["GET /api/visualization Workflow"]
        VizStart([GET /api/visualization<br/>Request]) --> GetGraph2[get_graph()<br/>Thread-Safe]
        GetGraph2 --> CallViz[Call get_3d_visualization_data_enhanced()]
        CallViz --> GenPositions[Generate 3D<br/>Positions]
        GenPositions --> SetSeed[Set Random Seed=42<br/>Deterministic]
        SetSeed --> CalcPositions[Calculate Node<br/>Coordinates]
        CalcPositions --> GenColors[Generate Colors<br/>by Asset Class]
        GenColors --> GenHover[Generate<br/>Hover Text]
        GenHover --> BuildNodes[Build Nodes<br/>Array]
        BuildNodes --> BuildEdges[Build Edges<br/>from Relationships]
        BuildEdges --> SerializeViz[Serialize to<br/>VisualizationDataResponse]
        SerializeViz --> VizEnd([200 OK<br/>JSON Response])
    end
```

#### Color Mapping for Asset Classes

| Asset Class | Color Code | Visual |
|-------------|------------|--------|
| Equity | Blue (#1f77b4) | Standard equities |
| Fixed Income | Green (#2ca02c) | Bonds and bond ETFs |
| Commodity | Orange (#ff7f0e) | Commodity futures |
| Currency | Red (#d62728) | Currency pairs |
| Derivative | Purple (#9467bd) | Derivatives |

### 4.3.3 Metrics Calculation Flow

The metrics endpoint (`GET /api/metrics`) calculates and returns network statistics including density, degree distribution, and asset class breakdowns.

```mermaid
flowchart TB
    subgraph MetricsFlow["GET /api/metrics Workflow"]
        MetStart([GET /api/metrics<br/>Request]) --> GetGraph3[get_graph()<br/>Thread-Safe]
        GetGraph3 --> CallMetrics[Call calculate_metrics()]
        CallMetrics --> CountAssets[Count Total<br/>Assets]
        CountAssets --> CountRels[Count Total<br/>Relationships]
        CountRels --> CalcByClass[Calculate Assets<br/>by Class]
        CalcByClass --> CalcDegree[Calculate<br/>Avg/Max Degree]
        CalcDegree --> CalcDensity[Calculate Network<br/>Density]
        CalcDensity --> BuildResponse[Build<br/>MetricsResponse]
        BuildResponse --> MetEnd([200 OK<br/>JSON Response])
    end
```

#### Metrics Calculation Formulas

| Metric | Formula | Description |
|--------|---------|-------------|
| Total Assets | `len(graph.assets)` | Count of all asset nodes |
| Total Relationships | `sum(len(edges) for edges in graph.relationships.values())` | Count of all edges |
| Average Degree | `(2 × total_relationships) / total_assets` | Mean connections per node |
| Max Degree | `max(len(edges) for edges in graph.relationships.values())` | Highest connected node |
| Network Density | `total_relationships / (total_assets × (total_assets - 1) / 2)` | Ratio of actual to possible edges |

## 4.4 Frontend Workflows

### 4.4.1 Next.js Page Load Flow

The Next.js frontend implements a client-side data loading pattern with error handling and retry capabilities.

```mermaid
flowchart TB
    subgraph NextJSFlow["Next.js Page Load Workflow"]
        PageStart([Page Mount<br/>useEffect]) --> SetLoading[Set Loading<br/>State = true]
        SetLoading --> FetchData[Promise.all:<br/>getMetrics()<br/>getVisualizationData()]
        FetchData --> FetchResult{Fetch<br/>Successful?}
        FetchResult -->|Yes| StoreData[Store Data<br/>in State]
        StoreData --> ClearLoading[Clear Loading<br/>State]
        ClearLoading --> RenderUI[Render UI<br/>Components]
        RenderUI --> PageEnd([Page<br/>Ready])
        FetchResult -->|No| SetError[Set Error<br/>State]
        SetError --> ShowRetry[Show Retry<br/>Button]
        ShowRetry --> UserRetry{User Clicks<br/>Retry?}
        UserRetry -->|Yes| SetLoading
        UserRetry -->|No| WaitAction([Wait for<br/>User Action])
    end
```

### 4.4.2 Gradio UI Event Flow

The Gradio interface manages state and user interactions through an event-driven architecture with real-time visualization updates.

```mermaid
flowchart TB
    subgraph GradioFlow["Gradio UI Event Flow"]
        GradioStart([Gradio App<br/>Starts]) --> InitGraph[Initialize<br/>Graph State]
        InitGraph --> CreateInterface[Create Blocks<br/>Interface]
        CreateInterface --> SetupTabs[Setup 6<br/>Tabs]
        SetupTabs --> WireEvents[Wire Event<br/>Handlers]
        WireEvents --> LaunchServer[Launch Server<br/>Port 7860]
        LaunchServer --> WaitEvent([Wait for<br/>User Event])
        WaitEvent --> UserAction{User<br/>Action Type}
        UserAction -->|Refresh| RefreshAll[refresh_all_outputs()]
        UserAction -->|Filter Change| UpdateViz[refresh_visualization()]
        UserAction -->|Tab Change| LoadTab[Load Tab<br/>Content]
        UserAction -->|Asset Select| UpdateAsset[update_asset_info()]
        RefreshAll --> WaitEvent
        UpdateViz --> WaitEvent
        LoadTab --> WaitEvent
        UpdateAsset --> WaitEvent
    end
```

### 4.4.3 Tab Navigation State Machine

```mermaid
stateDiagram-v2
    [*] --> Visualization: Default Tab

    Visualization --> Metrics: Tab Click
    Visualization --> SchemaRules: Tab Click
    Visualization --> AssetExplorer: Tab Click
    Visualization --> Documentation: Tab Click
    Visualization --> FormulaicAnalysis: Tab Click

    Metrics --> Visualization: Tab Click
    Metrics --> SchemaRules: Tab Click
    Metrics --> AssetExplorer: Tab Click
    Metrics --> Documentation: Tab Click
    Metrics --> FormulaicAnalysis: Tab Click

    SchemaRules --> Visualization: Tab Click
    SchemaRules --> Metrics: Tab Click
    SchemaRules --> AssetExplorer: Tab Click
    SchemaRules --> Documentation: Tab Click
    SchemaRules --> FormulaicAnalysis: Tab Click

    AssetExplorer --> Visualization: Tab Click
    AssetExplorer --> Metrics: Tab Click
    AssetExplorer --> SchemaRules: Tab Click
    AssetExplorer --> Documentation: Tab Click
    AssetExplorer --> FormulaicAnalysis: Tab Click

    Documentation --> Visualization: Tab Click
    Documentation --> Metrics: Tab Click
    Documentation --> SchemaRules: Tab Click
    Documentation --> AssetExplorer: Tab Click
    Documentation --> FormulaicAnalysis: Tab Click

    FormulaicAnalysis --> Visualization: Tab Click
    FormulaicAnalysis --> Metrics: Tab Click
    FormulaicAnalysis --> SchemaRules: Tab Click
    FormulaicAnalysis --> AssetExplorer: Tab Click
    FormulaicAnalysis --> Documentation: Tab Click
```

## 4.5 Error Handling Workflows

### 4.5.1 API Error Handling Flow

The API implements comprehensive error handling with proper HTTP status codes and informative error messages.

```mermaid
flowchart TB
    subgraph APIErrors["API Error Handling Flow"]
        ErrStart([Error<br/>Occurs]) --> ErrType{Error<br/>Type?}

        ErrType -->|HTTPException| HTTPErr[Return HTTP<br/>Error Code]
        HTTPErr --> HTTP401{401?}
        HTTP401 -->|Yes| AddAuth[Add WWW-Authenticate<br/>Bearer Header]
        HTTP401 -->|No| HTTP404{404?}
        HTTP404 -->|Yes| NotFound[Return<br/>Not Found Detail]
        HTTP404 -->|No| HTTP400{400?}
        HTTP400 -->|Yes| BadRequest[Return<br/>Bad Request Detail]
        HTTP400 -->|No| OtherHTTP[Return<br/>Error Detail]

        ErrType -->|Rate Limit| RateErr[429 Too Many<br/>Requests]
        RateErr --> AddRetry[Add Retry-After<br/>Header]

        ErrType -->|Validation| ValErr[422 Validation<br/>Error]
        ValErr --> PydanticDetail[Return Pydantic<br/>Error Details]

        ErrType -->|Unexpected| UnexpErr[Log Exception]
        UnexpErr --> Return500[500 Internal<br/>Server Error]

        AddAuth --> ErrEnd([Error Response<br/>Sent])
        NotFound --> ErrEnd
        BadRequest --> ErrEnd
        OtherHTTP --> ErrEnd
        AddRetry --> ErrEnd
        PydanticDetail --> ErrEnd
        Return500 --> ErrEnd
    end
```

### 4.5.2 Authentication Error Scenarios

```mermaid
flowchart TB
    subgraph AuthErrors["Authentication Error Scenarios"]
        AuthErrStart([Auth Error<br/>Detected]) --> AuthErrType{Error<br/>Scenario}

        AuthErrType -->|Invalid Credentials| InvalidCred["401: Incorrect<br/>username or password"]
        AuthErrType -->|Expired Token| ExpiredTok["401: Token<br/>has expired"]
        AuthErrType -->|Malformed Token| MalformedTok["401: Could not<br/>validate credentials"]
        AuthErrType -->|Missing Token| MissingTok["401: Not<br/>authenticated"]
        AuthErrType -->|Disabled Account| DisabledAcc["400: Inactive<br/>user"]
        AuthErrType -->|Rate Limited| RateLimited["429: Too many<br/>requests"]

        InvalidCred --> RetryPrompt[Prompt User<br/>to Retry]
        ExpiredTok --> ReAuth[Redirect to<br/>Re-authenticate]
        MalformedTok --> ReAuth
        MissingTok --> LoginPrompt[Show Login<br/>Form]
        DisabledAcc --> ContactAdmin[Contact<br/>Administrator]
        RateLimited --> WaitRetry[Wait and<br/>Retry]

        RetryPrompt --> AuthErrEnd([Error<br/>Handled])
        ReAuth --> AuthErrEnd
        LoginPrompt --> AuthErrEnd
        ContactAdmin --> AuthErrEnd
        WaitRetry --> AuthErrEnd
    end
```

### 4.5.3 Graph Initialization Error Handling

```mermaid
flowchart TB
    subgraph GraphErrors["Graph Initialization Error Handling"]
        GraphErrStart([Graph Init<br/>Error]) --> ErrSource{Error<br/>Source}

        ErrSource -->|Cache Load Failed| CacheErr[Log Cache<br/>Error]
        CacheErr --> FallbackFetch[Proceed to<br/>Standard Fetch]

        ErrSource -->|Network Disabled| NetErr[Network<br/>Unavailable]
        NetErr --> UseSample[Use Sample<br/>Data Fallback]

        ErrSource -->|Yahoo Finance Error| YFErr[Log Yahoo<br/>Finance Error]
        YFErr --> CheckPartial{Partial Data<br/>Retrieved?}
        CheckPartial -->|Yes| UsePartial[Use Available<br/>Data]
        CheckPartial -->|No| UseSample

        ErrSource -->|Critical Failure| CritErr[Log Critical<br/>Error]
        CritErr --> AbortStartup[Abort<br/>Application Startup]

        FallbackFetch --> GraphReady([Graph<br/>Initialized])
        UseSample --> GraphReady
        UsePartial --> GraphReady
        AbortStartup --> StartupFailed([Startup<br/>Failed])
    end
```

### 4.5.4 Frontend Error Recovery Flow

```mermaid
flowchart TB
    subgraph FrontendErrors["Frontend Error Recovery"]
        FEStart([Frontend Error<br/>Detected]) --> ErrCategory{Error<br/>Category}

        ErrCategory -->|Network Error| NetError[Set Error:<br/>Network Unavailable]
        ErrCategory -->|API Error| APIError[Set Error:<br/>API Error Message]
        ErrCategory -->|Render Error| RenderError[Set Error:<br/>Display Error]

        NetError --> ShowRetryUI[Show Retry<br/>Button]
        APIError --> ShowRetryUI
        RenderError --> ShowRefresh[Show Refresh<br/>Page Option]

        ShowRetryUI --> UserRetries{User<br/>Retries?}
        UserRetries -->|Yes| ClearError[Clear Error<br/>State]
        ClearError --> ReloadData[Reload<br/>Data]
        ReloadData --> Success{Success?}
        Success -->|Yes| Normal([Normal<br/>Operation])
        Success -->|No| NetError
        UserRetries -->|No| WaitUser([Wait for<br/>User])

        ShowRefresh --> UserRefresh{User<br/>Refreshes?}
        UserRefresh -->|Yes| PageReload[Full Page<br/>Reload]
        PageReload --> Normal
        UserRefresh -->|No| WaitUser
    end
```

## 4.6 Integration Sequence Diagrams

### 4.6.1 Frontend-Backend API Integration

```mermaid
sequenceDiagram
    participant User as User Browser
    participant NextJS as Next.js Frontend
    participant Axios as Axios Client
    participant CORS as CORS Middleware
    participant FastAPI as FastAPI Backend
    participant Graph as Graph Engine

    User->>NextJS: Navigate to Page
    NextJS->>Axios: api.getMetrics()
    Axios->>CORS: GET /api/metrics
    CORS->>CORS: Validate Origin

    alt Origin Valid
        CORS->>FastAPI: Forward Request
        FastAPI->>Graph: get_graph()
        Graph-->>FastAPI: Graph Instance
        FastAPI->>Graph: calculate_metrics()
        Graph-->>FastAPI: Metrics Data
        FastAPI-->>CORS: MetricsResponse
        CORS-->>Axios: 200 OK + CORS Headers
        Axios-->>NextJS: Response Data
        NextJS-->>User: Render Metrics
    else Origin Invalid
        CORS-->>Axios: 403 Forbidden
        Axios-->>NextJS: Error
        NextJS-->>User: Show Error Message
    end
```

### 4.6.2 Authentication Token Flow

```mermaid
sequenceDiagram
    participant Client as API Client
    participant RateLimiter as Rate Limiter
    participant Auth as Auth Module
    participant UserRepo as User Repository
    participant JWT as JWT Library

    Client->>RateLimiter: POST /token
    RateLimiter->>RateLimiter: Check 5/min limit

    alt Rate Limit OK
        RateLimiter->>Auth: Process Login
        Auth->>UserRepo: get_user(username)
        UserRepo-->>Auth: User or None

        alt User Found
            Auth->>Auth: verify_password(plain, hashed)

            alt Password Valid
                Auth->>JWT: encode(payload, SECRET_KEY, HS256)
                JWT-->>Auth: Access Token
                Auth-->>Client: {"access_token": "...", "token_type": "bearer"}
            else Password Invalid
                Auth-->>Client: 401 Incorrect username or password
            end
        else User Not Found
            Auth-->>Client: 401 Incorrect username or password
        end
    else Rate Limit Exceeded
        RateLimiter-->>Client: 429 Too Many Requests
    end
```

### 4.6.3 Real Data Fetching Integration

```mermaid
sequenceDiagram
    participant App as Application
    participant Fetcher as RealDataFetcher
    participant Cache as File Cache
    participant YF as Yahoo Finance
    participant Graph as Graph Engine

    App->>Fetcher: create_real_database()
    Fetcher->>Cache: Check cache file

    alt Cache Exists
        Cache-->>Fetcher: Cached JSON
        Fetcher->>Graph: Load from cache
        Graph-->>App: Cached Graph
    else No Cache
        Fetcher->>YF: Download AAPL, MSFT, XOM, JPM
        YF-->>Fetcher: Equity Data
        Fetcher->>YF: Download TLT, LQD, HYG
        YF-->>Fetcher: Bond ETF Data
        Fetcher->>YF: Download GC=F, CL=F, SI=F
        YF-->>Fetcher: Commodity Data
        Fetcher->>YF: Download EURUSD=X, GBPUSD=X, JPYUSD=X
        YF-->>Fetcher: Currency Data

        Fetcher->>Graph: add_asset() × N
        Fetcher->>Graph: add_regulatory_event() × N
        Fetcher->>Graph: build_relationships()

        Fetcher->>Cache: Write temp file
        Cache->>Cache: Atomic rename
        Cache-->>Fetcher: Cache saved

        Graph-->>App: Fresh Graph
    end
```

### 4.6.4 Visualization Rendering Pipeline

```mermaid
sequenceDiagram
    participant User as User
    participant UI as UI Component
    participant API as API Layer
    participant Graph as Graph Engine
    participant Viz as Visualization Module
    participant Plotly as Plotly Renderer

    User->>UI: Request 3D Visualization
    UI->>API: GET /api/visualization
    API->>Graph: get_graph()
    Graph-->>API: Graph Instance
    API->>Viz: get_3d_visualization_data_enhanced()
    Viz->>Viz: Set seed(42)
    Viz->>Viz: Calculate 3D positions
    Viz->>Viz: Assign colors by asset class
    Viz->>Viz: Generate hover text
    Viz-->>API: (positions, ids, colors, hovers)
    API->>API: Build nodes array
    API->>API: Build edges array
    API-->>UI: VisualizationDataResponse
    UI->>Plotly: Render 3D scatter
    Plotly-->>User: Interactive 3D Graph
```

## 4.7 State Transition Diagrams

### 4.7.1 Graph Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Uninitialized: Application Start

    Uninitialized --> Initializing: get_graph() called
    Initializing --> Loading: Acquire Lock

    Loading --> LoadingFromCache: Cache path set
    Loading --> LoadingFromNetwork: Real data enabled
    Loading --> LoadingFromSample: Default mode

    LoadingFromCache --> Initialized: Cache loaded
    LoadingFromCache --> LoadingFromNetwork: Cache invalid

    LoadingFromNetwork --> Initialized: Data fetched
    LoadingFromNetwork --> LoadingFromSample: Network error

    LoadingFromSample --> Initialized: Sample created

    Initialized --> Ready: Release Lock
    Ready --> Ready: Serving requests

    Ready --> Resetting: reset_graph() called
    Resetting --> Uninitialized: Graph cleared

    Ready --> FactoryOverride: set_graph_factory()
    FactoryOverride --> Resetting: Factory set
```

### 4.7.2 Request State Machine

```mermaid
stateDiagram-v2
    [*] --> Received: HTTP Request

    Received --> ValidatingCORS: Check origin
    ValidatingCORS --> CORSRejected: Invalid origin
    ValidatingCORS --> CheckingRateLimit: Valid origin

    CORSRejected --> [*]: 403 Forbidden

    CheckingRateLimit --> RateLimited: Limit exceeded
    CheckingRateLimit --> CheckingAuth: Within limit

    RateLimited --> [*]: 429 Too Many Requests

    CheckingAuth --> Authenticated: Valid token
    CheckingAuth --> AuthRequired: Missing/invalid token
    CheckingAuth --> Processing: No auth required

    AuthRequired --> [*]: 401 Unauthorized

    Authenticated --> Processing: User validated

    Processing --> Completed: Success
    Processing --> Failed: Exception

    Completed --> [*]: 2xx Response
    Failed --> [*]: 4xx/5xx Response
```

### 4.7.3 User Session State Machine

```mermaid
stateDiagram-v2
    [*] --> Anonymous: Visit application

    Anonymous --> Authenticating: Submit credentials
    Authenticating --> Authenticated: Valid credentials
    Authenticating --> Anonymous: Invalid credentials

    Authenticated --> TokenExpired: 30 min elapsed
    TokenExpired --> Authenticating: Re-authenticate
    TokenExpired --> Anonymous: Session ended

    Authenticated --> Anonymous: Logout

    Authenticated --> Accessing: Request protected resource
    Accessing --> Authenticated: Request complete
```

## 4.8 Timing and SLA Considerations

### 4.8.1 Performance Targets by Operation

| Operation | Target SLA | Measurement Point |
|-----------|-----------|-------------------|
| API Response (95th percentile) | < 500ms | Request to response |
| Visualization Rendering | < 2 seconds | Data load to interactive |
| Relationship Discovery | < 500ms | For 100 assets |
| Token Generation | < 100ms | Credential submission to token |
| Graph Initialization | < 3 seconds | Application startup |
| Dataclass Instantiation | < 1ms | Per object |
| Validation | < 1ms | Per object |
| Initial Page Load | < 3 seconds | Navigation to interactive |

### 4.8.2 Timeout Configuration

```mermaid
flowchart LR
    subgraph Timeouts["Timeout Configuration"]
        JWT["JWT Token<br/>30 min expiry"]
        RateLimit["Rate Limit Window<br/>1 minute"]
        HTTPTimeout["HTTP Client<br/>30 sec default"]
        YahooFinance["Yahoo Finance<br/>Request timeout"]
    end
```

### 4.8.3 Rate Limiting Constraints

| Endpoint | Limit | Window | Key Function |
|----------|-------|--------|--------------|
| `POST /token` | 5 requests | 1 minute | Client IP |
| `GET /api/users/me` | 10 requests | 1 minute | Client IP |
| Other endpoints | Unlimited | N/A | N/A |

## 4.9 Validation Rules and Checkpoints

### 4.9.1 Business Rules Validation Flow

```mermaid
flowchart TB
    subgraph ValidationFlow["Validation Flow"]
        ValStart([Data<br/>Input]) --> DomainVal{Domain<br/>Validation}

        DomainVal -->|Asset| AssetRules["Asset Rules:<br/>• id non-empty<br/>• symbol non-empty<br/>• name non-empty<br/>• price ≥ 0<br/>• currency 3-letter ISO"]

        DomainVal -->|RegulatoryEvent| EventRules["Event Rules:<br/>• impact_score in [-1, 1]<br/>• date ISO 8601<br/>• id non-empty"]

        AssetRules --> ClassSpecific{Asset<br/>Class?}
        ClassSpecific -->|Equity| EquityRules["Equity Rules:<br/>• P/E ratio numeric<br/>• dividend_yield numeric"]
        ClassSpecific -->|FixedIncome| BondRules["Bond Rules:<br/>• maturity_date valid<br/>• coupon_rate numeric<br/>• credit_rating valid"]
        ClassSpecific -->|Commodity| CommodityRules["Commodity Rules:<br/>• contract_size positive<br/>• delivery_date valid"]
        ClassSpecific -->|Currency| CurrencyRules["Currency Rules:<br/>• exchange_rate positive<br/>• country non-empty"]

        EventRules --> ValEnd([Validation<br/>Complete])
        EquityRules --> ValEnd
        BondRules --> ValEnd
        CommodityRules --> ValEnd
        CurrencyRules --> ValEnd
    end
```

### 4.9.2 API Input Validation Checkpoints

| Checkpoint | Validation | Response on Failure |
|------------|------------|---------------------|
| Request Body | Pydantic model parsing | 422 Validation Error |
| Query Parameters | Type coercion and constraints | 422 Validation Error |
| Path Parameters | Type validation | 422 Validation Error |
| Authentication | Token format and signature | 401 Unauthorized |
| Authorization | User active status | 400 Inactive User |
| CORS Origin | Allowlist and pattern matching | 403 Forbidden |
| Rate Limit | Request count per window | 429 Too Many Requests |

### 4.9.3 Data Quality Validation

```mermaid
flowchart TB
    subgraph DataQuality["Data Quality Validation"]
        DQStart([Data<br/>Received]) --> Completeness["Completeness Check:<br/>Required fields present"]
        Completeness --> Consistency["Consistency Check:<br/>Cross-field logic"]
        Consistency --> Accuracy["Accuracy Check:<br/>Value ranges valid"]
        Accuracy --> Uniqueness["Uniqueness Check:<br/>ID uniqueness"]
        Uniqueness --> DQEnd([Quality<br/>Verified])
    end
```

## 4.10 Transaction Boundaries and Persistence

### 4.10.1 Data Persistence Points

| Component | Persistence Method | Durability |
|-----------|-------------------|------------|
| Graph State | In-memory singleton | Process lifetime |
| User Credentials | SQLite database | Persistent |
| Cache Files | JSON file system | Persistent |
| JWT Tokens | Stateless (client-held) | Token lifetime |
| Session State | React/Gradio state | Tab lifetime |

### 4.10.2 Transaction Flow for Cache Updates

```mermaid
flowchart TB
    subgraph CacheTransaction["Cache Update Transaction"]
        TxStart([Start Cache<br/>Update]) --> CreateTemp[Create<br/>Temp File]
        CreateTemp --> WriteData[Write JSON<br/>Data]
        WriteData --> FlushSync[Flush and<br/>Sync to Disk]
        FlushSync --> CloseFile[Close<br/>File Handle]
        CloseFile --> AtomicRename[os.replace()<br/>Atomic Rename]
        AtomicRename --> TxEnd([Transaction<br/>Complete])
    end
```

### 4.10.3 Thread Safety Boundaries

```mermaid
flowchart TB
    subgraph ThreadSafety["Thread Safety Boundaries"]
        Request1["Request 1"] --> Lock["graph_lock<br/>Threading Lock"]
        Request2["Request 2"] --> Lock
        Request3["Request 3"] --> Lock

        Lock --> GraphAccess["Graph Singleton<br/>Access"]
        GraphAccess --> ReadOps["Read Operations<br/>(Concurrent OK)"]
        GraphAccess --> WriteOps["Write Operations<br/>(Serialized)"]

        ReadOps --> Response1["Response 1"]
        ReadOps --> Response2["Response 2"]
        WriteOps --> Response3["Response 3"]
    end
```

## 4.11 References

#### Files Examined
- `api/main.py` - FastAPI backend with graph lifecycle, authentication flow, CORS, rate limiting, all REST endpoints, and error handling patterns
- `api/auth.py` - JWT authentication flow, password hashing, token creation/validation, and user repository
- `api/database.py` - SQLite database helpers and memory connection management
- `src/logic/asset_graph.py` - Core graph class with relationships data structure and 3D visualization data
- `src/data/sample_data.py` - Sample data creation workflow, asset/event registration, and relationship building
- `src/data/real_data_fetcher.py` - Yahoo Finance data fetching, caching mechanism, and fallback patterns
- `src/models/financial_models.py` - Domain models with validation rules
- `app.py` - Gradio UI controller with visualization workflows and event handlers
- `frontend/app/page.tsx` - Next.js home page with data loading, tab navigation, and error handling
- `frontend/app/lib/api.ts` - Frontend API client with all endpoint calls

#### Technical Specification Sections Referenced
- 1.2 System Overview - System architecture and component interactions
- 2.1 Feature Catalog - Feature definitions and dependencies
- 2.4 Implementation Considerations - Performance requirements and constraints
- 3.8 Security Considerations - Authentication and API security
- 3.9 Integration Requirements - Frontend-backend communication patterns

# 5. System Architecture

This section provides a comprehensive technical reference for the Financial Asset Relationship Database system architecture, documenting the architectural patterns, component interactions, technical decisions, and cross-cutting concerns that define the system's structure and behavior.

## 5.1 HIGH-LEVEL ARCHITECTURE

### 5.1.1 System Overview

#### Architectural Style and Rationale

The Financial Asset Relationship Database implements a **layered architecture** with clear separation of concerns, optimizing for deployment flexibility, maintainability, and appropriate scalability for financial analysis workloads. The system follows an **API-first design** philosophy, enabling multiple presentation layers to consume the same business logic through standardized interfaces.

| Architectural Characteristic | Design Decision | Rationale |
|------------------------------|-----------------|-----------|
| Layer Separation | Four distinct layers (Presentation, API, Business Logic, Data) | Enables independent evolution and testing of each concern |
| Monolithic Core | Single deployable Python process with modular packages | Simplifies deployment for current scale (<500 assets) while maintaining clear module boundaries |
| API-First Design | REST/JSON endpoints via FastAPI with automatic OpenAPI documentation | Universal client compatibility and self-documenting interfaces |
| Dual UI Strategy | Legacy Gradio + Modern Next.js frontends | Supports rapid prototyping and production-ready experiences |

#### Key Architectural Principles

The system adheres to the following architectural principles that guide all design decisions:

- **Thread-Safe Singleton Pattern**: The graph engine uses double-checked locking to ensure safe concurrent access during initialization, preventing race conditions under multi-threaded workloads
- **Deterministic Visualization**: Fixed random seed (seed=42) ensures reproducible 3D layouts across sessions, critical for consistent user experience and debugging
- **Type Safety**: Python dataclasses with validation and Pydantic models enforce strict type contracts throughout the stack
- **Graceful Degradation**: Fallback mechanisms ensure the system remains operational when external data sources are unavailable
- **Atomic Operations**: Cache writes use temporary files with atomic rename operations to prevent data corruption

#### System Boundaries and Interfaces

```mermaid
flowchart TB
    subgraph External[External Systems]
        YF[Yahoo Finance API]
        Users[End Users]
        Vercel[Vercel Platform]
    end

    subgraph SystemBoundary[Financial Asset Relationship Database]
        subgraph Presentation[Presentation Layer]
            NextJS[Next.js Frontend<br/>Port 3000]
            Gradio[Gradio UI<br/>Port 7860]
        end

        subgraph API[API Layer]
            FastAPI[FastAPI Backend<br/>Port 8000]
            Auth[JWT Auth Module]
            RateLimit[Rate Limiter]
            CORS[CORS Middleware]
        end

        subgraph Core[Business Logic Layer]
            Graph[Asset Graph Engine]
            Models[Domain Models]
            Viz[Visualization Module]
            Metrics[Metrics Calculator]
        end

        subgraph Data[Data Layer]
            Sample[Sample Data Generator]
            Fetcher[Real Data Fetcher]
            Cache[JSON File Cache]
            SQLite[SQLite Auth DB]
        end
    end

    Users --> NextJS
    Users --> Gradio
    NextJS --> FastAPI
    FastAPI --> CORS
    CORS --> RateLimit
    RateLimit --> Auth
    Auth --> Graph
    Gradio --> Graph
    Graph --> Models
    Graph --> Viz
    Graph --> Metrics
    Graph --> Sample
    Graph --> Fetcher
    Fetcher --> YF
    Fetcher --> Cache
    Auth --> SQLite
    FastAPI --> Vercel
    NextJS --> Vercel
```

### 5.1.2 Core Components

The system comprises eight major components, each with distinct responsibilities and well-defined integration boundaries.

| Component | Primary Responsibility | Key Dependencies | Integration Points |
|-----------|----------------------|------------------|-------------------|
| FastAPI Backend | REST API server, request routing, middleware orchestration | FastAPI 0.127.0, Uvicorn, slowapi, PyJWT | Frontend via HTTP/JSON, Graph via Python calls |
| Next.js Frontend | Modern React-based UI with TypeScript | Next.js 14.2.35, React 18.2.0, Axios, Plotly.js | FastAPI via REST, Users via browser |
| Gradio UI | Legacy Python-native dashboard | Gradio ≥4.0.0, Plotly ≥6.0.0 | Graph Engine via direct Python calls |
| Graph Engine | In-memory relationship storage, 3D layout calculation | NumPy 2.2.6 | All layers via singleton accessor |
| Domain Models | Asset/Event dataclasses, validation rules | Python standard library | All components via imports |
| Real Data Fetcher | Yahoo Finance integration, caching | yfinance ≥0.2.51 | Graph initialization pipeline |
| Visualization Module | Plotly chart generation, color mapping | Plotly ≥6.0.0 | API endpoints, Gradio UI |
| Auth Module | JWT token management, user authentication | PyJWT ≥2.8.0, passlib | FastAPI protected endpoints |

### 5.1.3 Data Flow Description

#### Primary Data Flow: API to Visualization

The primary data flow begins with user interaction and culminates in rendered visualizations:

1. **Request Initiation**: User navigates to a page in Next.js frontend or Gradio UI
2. **API Communication**: Next.js client sends HTTP request via Axios to FastAPI backend
3. **Security Pipeline**: Request traverses CORS validation → Rate limit check → JWT authentication (if protected)
4. **Graph Access**: API endpoint calls `get_graph()` to retrieve thread-safe singleton instance
5. **Data Processing**: Graph engine provides assets, relationships, and calculated positions
6. **Serialization**: Pydantic models serialize Python objects to JSON response
7. **Client Rendering**: Frontend receives data and renders Plotly.js 3D visualization

#### Data Ingestion Flow

The data ingestion flow populates the graph from external or internal sources:

1. **Cache Check**: On startup, `_initialize_graph()` checks for existing cache at `GRAPH_CACHE_PATH`
2. **Cache Loading**: If valid cache exists, JSON-serialized graph is loaded directly
3. **Fresh Fetch**: Otherwise, `RealDataFetcher` retrieves data from Yahoo Finance (if enabled)
4. **Fallback Mode**: If network unavailable, sample data generator creates representative dataset
5. **Graph Population**: Assets added via `graph.add_asset()`, events via `graph.add_regulatory_event()`
6. **Relationship Building**: `graph.build_relationships()` discovers all eight relationship types
7. **Cache Persistence**: Graph serialized to JSON using atomic write pattern

#### Relationship Discovery Data Flow

The relationship discovery engine processes assets through rule-based algorithms:

| Relationship Type | Detection Rule | Directionality | Data Source |
|-------------------|----------------|----------------|-------------|
| `same_sector` | Assets share identical sector | Bidirectional | Asset.sector field |
| `corporate_bond_to_equity` | Bond.issuer_id matches Equity.id | Directional | Cross-asset linkage |
| `commodity_exposure` | Equity sector linked to commodity | Directional | Sector-commodity mapping |
| `currency_risk` | Asset currency ≠ USD | Directional | Asset.currency field |
| `income_comparison` | Dividend yield vs bond yield | Bidirectional | Yield calculations |
| `regulatory_impact` | Shared regulatory event | Directional | Event.impact_score |
| `market_cap_similar` | Market cap within 50% range | Bidirectional | Asset.market_cap |
| `correlation` | Price correlation > threshold | Bidirectional | Historical prices |

### 5.1.4 External Integration Points

The system integrates with external services through well-defined interfaces:

| System Name | Integration Type | Data Exchange Pattern | Protocol/Format |
|-------------|-----------------|----------------------|-----------------|
| Yahoo Finance | External data source | HTTP pull with JSON caching | yfinance Python library |
| SQLite | Local authentication store | File-based SQL persistence | sqlite3 driver |
| PostgreSQL | Optional production persistence | Connection-pooled SQL | SQLAlchemy ORM |
| Vercel | Serverless hosting platform | HTTPS deployment | Vercel CLI/JSON config |

---

## 5.2 COMPONENT DETAILS

### 5.2.1 FastAPI Backend

#### Purpose and Responsibilities

The FastAPI backend serves as the primary API gateway, exposing graph data through RESTful endpoints while enforcing security policies, rate limiting, and data validation.

**Location**: `api/main.py`

| Responsibility | Implementation |
|---------------|----------------|
| REST API Routing | FastAPI router with typed endpoint definitions |
| Authentication | JWT token issuance and validation via `api/auth.py` |
| Rate Limiting | slowapi integration with per-endpoint limits |
| CORS Management | Environment-specific origin allowlists |
| Request Validation | Pydantic models for automatic validation |
| Graph Lifecycle | Thread-safe singleton management |

#### Technologies and Frameworks

| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.127.0 | REST framework with automatic OpenAPI |
| Uvicorn | ≥0.24.0 | ASGI server with async support |
| Pydantic | 2.12.5 | Request/response validation |
| slowapi | Latest | Rate limiting middleware |
| PyJWT | ≥2.8.0 | JWT token encoding/decoding |
| passlib | Latest | Password hashing (pbkdf2_sha256) |

#### Key Interfaces and APIs

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/token` | POST | JWT token issuance | No (rate limited: 5/min) |
| `/api/assets` | GET | List assets with optional filters | No |
| `/api/assets/{id}` | GET | Single asset details | No |
| `/api/assets/{id}/relationships` | GET | Asset relationships | No |
| `/api/relationships` | GET | All relationships | No |
| `/api/metrics` | GET | Network statistics | No |
| `/api/visualization` | GET | 3D visualization data | No |
| `/api/asset-classes` | GET | Available asset class enum | No |
| `/api/sectors` | GET | Available sectors | No |
| `/api/users/me` | GET | Current user info | Yes (rate limited: 10/min) |
| `/api/health` | GET | Health check | No |

#### Thread-Safe Graph Access Pattern

```mermaid
flowchart TB
    subgraph ThreadSafe[Thread-Safe Graph Initialization]
        Request([API Request]) --> CheckGlobal{Global graph<br/>exists?}
        CheckGlobal -->|Yes| ReturnGraph([Return Graph])
        CheckGlobal -->|No| AcquireLock[Acquire Thread Lock]
        AcquireLock --> DoubleCheck{Double-check<br/>inside lock?}
        DoubleCheck -->|Yes| ReleaseLock1[Release Lock]
        ReleaseLock1 --> ReturnGraph
        DoubleCheck -->|No| Initialize[Initialize Graph]
        Initialize --> SetGlobal[Set Global Reference]
        SetGlobal --> ReleaseLock2[Release Lock]
        ReleaseLock2 --> ReturnGraph
    end
```

#### Scaling Considerations

- **Node Limit**: Optimal performance for <500 nodes due to in-memory storage
- **Rate Limiting**: Protects against abuse and ensures fair resource allocation
- **Serverless Ready**: Mangum adapter enables Vercel Lambda deployment (50MB limit)
- **Stateless Requests**: Each request is independent; session state managed via JWT

### 5.2.2 Next.js Frontend

#### Purpose and Responsibilities

The Next.js frontend provides a modern, responsive user interface for exploring asset relationships and visualizing network data.

**Location**: `frontend/`

| Responsibility | Implementation |
|---------------|----------------|
| 3D Visualization | Plotly.js integration with SSR safety |
| Asset Exploration | Filterable tables with URL-synced state |
| Metrics Dashboard | Grid-based metrics display |
| API Communication | Axios HTTP client with error handling |
| Responsive Design | Tailwind CSS utility classes |

#### Technologies and Frameworks

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 14.2.35 | React meta-framework with App Router |
| React | 18.2.0 | UI component library |
| TypeScript | ^5.3.0 | Type safety |
| Tailwind CSS | Latest | Utility-first styling |
| Plotly.js | ^2.27.0 | Client-side 3D rendering |
| Axios | Latest | HTTP client |

#### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `NetworkVisualization` | `frontend/app/components/NetworkVisualization.tsx` | 3D Plotly graph with dynamic import for SSR |
| `MetricsDashboard` | `frontend/app/components/MetricsDashboard.tsx` | Metrics display grid |
| `AssetList` | `frontend/app/components/AssetList.tsx` | Filterable asset table with pagination |

#### Frontend Data Flow

```mermaid
sequenceDiagram
    participant User as User Browser
    participant Page as Next.js Page
    participant API as API Client
    participant Backend as FastAPI
    participant Plotly as Plotly.js

    User->>Page: Navigate to Page
    Page->>Page: useEffect on mount
    Page->>API: getMetrics()
    Page->>API: getVisualizationData()
    API->>Backend: GET /api/metrics
    API->>Backend: GET /api/visualization
    Backend-->>API: JSON Response
    API-->>Page: Data Objects
    Page->>Plotly: Render 3D Graph
    Plotly-->>User: Interactive Visualization
```

#### Scaling Considerations

- **MAX_NODES/MAX_EDGES**: Environment-configurable limits (`NEXT_PUBLIC_MAX_NODES`, `NEXT_PUBLIC_MAX_EDGES`)
- **Default Limits**: 500 nodes, 2000 edges for client-side performance
- **SSR Safety**: Dynamic imports prevent server-side Plotly rendering errors
- **Client Hydration**: Data fetched client-side to avoid SSR data mismatches

### 5.2.3 Gradio UI

#### Purpose and Responsibilities

The Gradio UI provides a legacy Python-native dashboard for rapid exploration and development, with direct integration to core Python modules.

**Location**: `app.py`

| Responsibility | Implementation |
|---------------|----------------|
| Tabbed Interface | Gradio Blocks with six tabs |
| Real-time Updates | Event handlers for refresh actions |
| Direct Python Access | No API intermediary for visualization |
| Development Tool | Rapid prototyping environment |

#### Technologies and Frameworks

| Technology | Version | Purpose |
|------------|---------|---------|
| Gradio | ≥4.0.0 | Python UI framework |
| Plotly | ≥6.0.0 | Server-side visualization |

#### Interface Structure

| Tab | Content | Data Source |
|-----|---------|-------------|
| 3D Visualization | Interactive network graph | `src/visualizations/graph_visuals.py` |
| Metrics | Network statistics | `src/visualizations/metric_visuals.py` |
| Schema & Rules | Data model documentation | `src/reports/schema_report.py` |
| Asset Explorer | Filterable asset table | Graph engine assets |
| Documentation | System documentation | Static content |
| Formulaic Analysis | Analysis dashboard | `src/visualizations/formulaic_visuals.py` |

### 5.2.4 Graph Engine

#### Purpose and Responsibilities

The Graph Engine serves as the central data structure, managing asset storage, relationship discovery, and 3D layout calculations.

**Location**: `src/logic/asset_graph.py`

| Responsibility | Implementation |
|---------------|----------------|
| Asset Storage | Dictionary-based in-memory storage |
| Relationship Management | Adjacency list with typed edges |
| 3D Layout Calculation | NumPy-based coordinate generation |
| Metrics Computation | Network statistics calculation |
| Singleton Access | Thread-safe global instance |

#### Data Structures

| Structure | Type | Purpose |
|-----------|------|---------|
| `assets` | `Dict[str, Asset]` | Asset ID to object mapping |
| `relationships` | `Dict[str, List[Tuple[str, str, float]]]` | Source ID to (target, type, strength) edges |
| `regulatory_events` | `Dict[str, RegulatoryEvent]` | Event ID to object mapping |

#### Key Methods

| Method | Parameters | Returns | Purpose |
|--------|------------|---------|---------|
| `add_asset()` | `Asset` | `None` | Register asset in graph |
| `add_regulatory_event()` | `RegulatoryEvent` | `None` | Register event |
| `build_relationships()` | `None` | `None` | Discover all relationship types |
| `get_relationships()` | `asset_id` | `List[Tuple]` | Get edges for asset |
| `calculate_metrics()` | `None` | `Dict` | Compute network statistics |
| `get_3d_visualization_data_enhanced()` | `filters` | `Tuple` | Generate visualization data |

### 5.2.5 Domain Models

#### Purpose and Responsibilities

Domain models define the type-safe data structures and validation rules that govern all financial entities in the system.

**Location**: `src/models/financial_models.py`

#### Asset Class Enumeration

| Value | Display Name | Description |
|-------|--------------|-------------|
| `EQUITY` | Equity | Stocks and equity instruments |
| `FIXED_INCOME` | Fixed Income | Bonds and debt instruments |
| `COMMODITY` | Commodity | Physical commodity futures |
| `CURRENCY` | Currency | Foreign exchange pairs |
| `DERIVATIVE` | Derivative | Derivative instruments |

#### Asset Type Hierarchy

```mermaid
classDiagram
    class Asset {
        +str id
        +str symbol
        +str name
        +AssetClass asset_class
        +str sector
        +float price
        +Optional[float] market_cap
        +str currency
        +__post_init__()
    }

    class Equity {
        +Optional[float] pe_ratio
        +Optional[float] dividend_yield
        +Optional[float] earnings_per_share
        +Optional[float] book_value
    }

    class Bond {
        +Optional[float] yield_to_maturity
        +Optional[float] coupon_rate
        +Optional[str] maturity_date
        +Optional[str] credit_rating
        +Optional[str] issuer_id
    }

    class Commodity {
        +Optional[float] contract_size
        +Optional[str] delivery_date
        +Optional[float] volatility
    }

    class Currency {
        +Optional[float] exchange_rate
        +Optional[str] country
        +Optional[float] central_bank_rate
    }

    Asset <|-- Equity
    Asset <|-- Bond
    Asset <|-- Commodity
    Asset <|-- Currency
```

#### Validation Rules

| Field | Rule | Error Handling |
|-------|------|----------------|
| `id`, `symbol`, `name` | Non-empty string | `ValueError` on empty |
| `price`, `market_cap` | Non-negative float | `ValueError` on negative |
| `currency` | 3-character ISO code | `ValueError` on invalid |
| `impact_score` (events) | Range [-1, 1] | `ValueError` on out of bounds |
| `date` (events) | ISO 8601 format | `ValueError` on invalid format |

### 5.2.6 Visualization Layer

#### Purpose and Responsibilities

The Visualization Layer generates Plotly-compatible chart specifications for both server-side (Gradio) and client-side (Next.js) rendering.

**Location**: `src/visualizations/`

| Module | Purpose |
|--------|---------|
| `graph_visuals.py` | 3D network visualization with filtering |
| `graph_2d_visuals.py` | 2D network layouts |
| `metric_visuals.py` | Metrics bar charts and dashboards |
| `formulaic_visuals.py` | Formulaic analysis dashboard |

#### Color Scheme Mapping

| Asset Class | Node Color | Relationship Type | Edge Color |
|-------------|------------|-------------------|------------|
| Equity | Blue (#1f77b4) | same_sector | Orange |
| Fixed Income | Green (#2ca02c) | corporate_bond_to_equity | Blue |
| Commodity | Orange (#ff7f0e) | commodity_exposure | Green |
| Currency | Red (#d62728) | regulatory_impact | Red |
| Derivative | Purple (#9467bd) | market_cap_similar | Gray |

### 5.2.7 Component Interaction Diagram

```mermaid
flowchart LR
    subgraph Frontend[Frontend Layer]
        NextJS[Next.js]
        Gradio[Gradio]
    end

    subgraph API[API Layer]
        FastAPI[FastAPI]
        Auth[Auth]
        Rate[Rate Limiter]
    end

    subgraph Business[Business Logic]
        Graph[Graph Engine]
        Viz[Visualization]
        Models[Domain Models]
    end

    subgraph Data[Data Layer]
        Sample[Sample Data]
        Yahoo[Yahoo Finance]
        Cache[Cache]
        SQLite[SQLite]
    end

    NextJS -->|HTTP/JSON| FastAPI
    Gradio -->|Direct Call| Graph
    FastAPI --> Rate
    Rate --> Auth
    Auth --> Graph
    Auth --> SQLite
    Graph --> Viz
    Graph --> Models
    Graph --> Sample
    Graph --> Yahoo
    Yahoo --> Cache
```

---

## 5.3 TECHNICAL DECISIONS

### 5.3.1 Architecture Style Decisions

#### Decision: Monolithic with API-First Design

| Aspect | Choice | Alternatives Considered |
|--------|--------|------------------------|
| Deployment Model | Monolithic | Microservices, Serverless-only |
| API Design | REST/JSON | GraphQL, gRPC |
| Data Storage | In-memory with optional persistence | Database-first, Event-sourced |

**Rationale**:

- **Simplified Deployment**: Single Python process reduces operational complexity for current scale
- **Module Boundaries**: Clear package structure (`src/logic/`, `src/data/`, `src/visualizations/`) enables future microservices migration
- **Adequate Scale**: <500 assets fits comfortably in memory with sub-millisecond access
- **Deployment Flexibility**: Same codebase deploys to Docker, Vercel, and local development

**Tradeoffs**:

| Benefit | Cost |
|---------|------|
| Simpler operations | Limited horizontal scaling of graph |
| Faster development | All components share runtime |
| Lower latency | Memory-bound capacity |

### 5.3.2 Communication Pattern Decisions

#### Decision: REST/JSON over HTTP

| Criterion | REST/JSON | GraphQL | gRPC |
|-----------|-----------|---------|------|
| Client Compatibility | Universal | Requires client | Limited browser support |
| Documentation | Auto-generated OpenAPI | Schema introspection | Protobuf definitions |
| Caching | HTTP caching natural | Complex caching | Not applicable |
| Complexity | Low | Medium | High |

**Rationale**:

- FastAPI provides automatic OpenAPI documentation generation
- JSON serialization handles complex types (dates as ISO strings)
- Pydantic models enforce type safety at API boundaries
- Stateless request handling simplifies scaling

### 5.3.3 Data Storage Decisions

#### Decision: In-Memory Graph with Optional Persistence

```mermaid
flowchart TB
    subgraph StorageOptions[Storage Decision Tree]
        Start([Storage<br/>Requirement]) --> Scale{Expected<br/>Scale?}
        Scale -->|"< 500 nodes"| InMemory[In-Memory Graph]
        Scale -->|"> 500 nodes"| Persistence{Persistence<br/>Required?}
        Persistence -->|No| InMemory
        Persistence -->|Yes| Database[SQLAlchemy + PostgreSQL]
        InMemory --> CacheNeeded{Cache<br/>Needed?}
        CacheNeeded -->|Yes| JSONCache[JSON File Cache]
        CacheNeeded -->|No| DirectUse[Direct Use]
    end
```

**Rationale**:

| Storage Option | Use Case | Trade-off |
|---------------|----------|-----------|
| In-Memory | Development, Small Datasets | Fast access, no persistence |
| JSON Cache | Startup optimization | Atomic writes, file I/O |
| SQLite | Authentication, Testing | Simple setup, single-writer |
| PostgreSQL | Production persistence | Scalable, connection pooling |

### 5.3.4 Caching Strategy Decisions

#### Decision: Atomic JSON File Cache

The caching strategy uses atomic write operations to prevent data corruption:

| Phase | Operation | Purpose |
|-------|-----------|---------|
| 1 | Write to `NamedTemporaryFile` | Isolate incomplete writes |
| 2 | Flush and sync to disk | Ensure durability |
| 3 | `os.replace()` atomic rename | Single atomic operation |
| 4 | Delete temp on failure | Clean up partial state |

**Configuration Variables**:

| Variable | Purpose | Default |
|----------|---------|---------|
| `REAL_DATA_CACHE_PATH` | Yahoo Finance data cache | None (disabled) |
| `GRAPH_CACHE_PATH` | Serialized graph cache | None (disabled) |

### 5.3.5 Security Mechanism Decisions

#### Decision: JWT with HS256 and pbkdf2_sha256

| Security Layer | Implementation | Rationale |
|---------------|----------------|-----------|
| Token Algorithm | HS256 (HMAC-SHA256) | Symmetric, fast, adequate for single-issuer |
| Password Hashing | pbkdf2_sha256 | OWASP recommended, passlib integration |
| Token Expiration | 30 minutes | Balance security and usability |
| Rate Limiting | slowapi per-endpoint | Prevent brute force attacks |

**Security Configuration**:

| Setting | Source | Default |
|---------|--------|---------|
| `SECRET_KEY` | Environment variable | Required |
| `ALGORITHM` | Environment variable | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Code constant | 30 |

---

## 5.4 CROSS-CUTTING CONCERNS

### 5.4.1 Monitoring and Observability

#### Logging Strategy

**Implementation**: Python standard logging with INFO level default

| Log Point | Level | Content |
|-----------|-------|---------|
| Graph initialization | INFO | Success/failure status |
| Application startup | INFO | Server binding, port |
| Cache operations | INFO | Load/save success |
| Request errors | ERROR | Exception details |
| Authentication failures | WARNING | Failed login attempts |

#### Metrics Endpoints

The system exposes operational metrics through the `/api/metrics` endpoint:

| Metric | Description | Source |
|--------|-------------|--------|
| `total_assets` | Count of nodes in graph | `len(graph.assets)` |
| `total_relationships` | Count of edges | Sum of adjacency lists |
| `average_degree` | Mean connections per node | Calculated statistic |
| `max_degree` | Highest connected node | Maximum adjacency count |
| `network_density` | Edge ratio | Actual/possible edges |

#### Health Check

| Endpoint | Response | Purpose |
|----------|----------|---------|
| `/api/health` | `{"status": "healthy"}` | Load balancer probe |
| Docker HEALTHCHECK | HTTP probe every 30s | Container orchestration |

### 5.4.2 Error Handling Patterns

#### API Error Categories

| Status Code | Scenario | Response Detail |
|-------------|----------|-----------------|
| 400 | Bad Request | Inactive user, invalid input |
| 401 | Unauthorized | Invalid/expired token, missing credentials |
| 404 | Not Found | Asset/resource not found |
| 422 | Validation Error | Pydantic validation failure |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Error | Unexpected exception |

#### Error Handling Flow

```mermaid
flowchart TB
    subgraph ErrorHandling[Error Handling Flow]
        Error([Error Occurs]) --> ErrorType{Error Type}

        ErrorType -->|HTTPException| HTTPHandle[Return HTTP Status]
        HTTPHandle --> Status401{401?}
        Status401 -->|Yes| AddWWW[Add WWW-Authenticate Header]
        Status401 -->|No| ReturnDetail[Return Error Detail]
        AddWWW --> ReturnDetail

        ErrorType -->|Rate Limit| RateHandle[429 + Retry-After]

        ErrorType -->|Validation| ValHandle[422 + Pydantic Details]

        ErrorType -->|Unexpected| UnexpHandle[Log Exception]
        UnexpHandle --> Return500[500 Internal Error]

        ReturnDetail --> Done([Response Sent])
        RateHandle --> Done
        ValHandle --> Done
        Return500 --> Done
    end
```

#### Graph Initialization Error Handling

| Error Source | Recovery Action | Fallback |
|--------------|-----------------|----------|
| Cache load failed | Proceed to fresh fetch | Standard initialization |
| Network disabled | Use sample data | Offline mode |
| Yahoo Finance error | Check partial data | Sample data fallback |
| Critical failure | Abort startup | Application exit |

#### Frontend Error Recovery

| Error Category | User Feedback | Recovery Option |
|---------------|---------------|-----------------|
| Network Error | "Unable to connect" | Retry button |
| API Error | Error message display | Retry button |
| Render Error | Display error state | Refresh page |

### 5.4.3 Authentication and Authorization Framework

#### Token Flow Sequence

```mermaid
sequenceDiagram
    participant Client as API Client
    participant Rate as Rate Limiter
    participant Auth as Auth Module
    participant Repo as User Repository
    participant JWT as JWT Library

    Client->>Rate: POST /token (credentials)
    Rate->>Rate: Check 5/min limit

    alt Within Limit
        Rate->>Auth: Process Login
        Auth->>Repo: get_user(username)
        Repo-->>Auth: User or None

        alt User Found
            Auth->>Auth: verify_password()

            alt Password Valid
                Auth->>Auth: Check user active
                Auth->>JWT: encode(payload, SECRET_KEY)
                JWT-->>Auth: Access Token
                Auth-->>Client: {access_token, token_type: bearer}
            else Invalid
                Auth-->>Client: 401 Unauthorized
            end
        else Not Found
            Auth-->>Client: 401 Unauthorized
        end
    else Exceeded
        Rate-->>Client: 429 Too Many Requests
    end
```

#### Protected Endpoint Validation

| Step | Action | Failure Response |
|------|--------|------------------|
| 1 | Extract Bearer token from header | 401 Not authenticated |
| 2 | Decode JWT with SECRET_KEY | 401 Could not validate |
| 3 | Check token expiration | 401 Token expired |
| 4 | Lookup user in repository | 401 Invalid credentials |
| 5 | Verify user is active | 400 Inactive user |

### 5.4.4 Performance Requirements and SLAs

#### Performance Targets

| Operation | Target SLA | Measurement |
|-----------|-----------|-------------|
| API Response (p95) | < 500ms | Request to response |
| Visualization Rendering | < 2 seconds | Data load to interactive |
| Token Generation | < 100ms | Credential to token |
| Graph Initialization | < 3 seconds | Application startup |
| Relationship Discovery | < 500ms | For 100 assets |
| Initial Page Load | < 3 seconds | Navigation to interactive |

#### Rate Limiting Configuration

| Endpoint | Limit | Window | Key Function |
|----------|-------|--------|--------------|
| `POST /token` | 5 requests | 1 minute | Client IP |
| `GET /api/users/me` | 10 requests | 1 minute | Client IP |
| Other endpoints | Unlimited | N/A | N/A |

#### Timeout Configuration

| Component | Timeout | Purpose |
|-----------|---------|---------|
| JWT Token | 30 minutes | Session expiration |
| Rate Limit Window | 1 minute | Request counting period |
| HTTP Client | 30 seconds | API request timeout |
| Health Check | 30 seconds | Container probe interval |

### 5.4.5 CORS Configuration

| Environment | Allowed Origins | Configuration |
|-------------|-----------------|---------------|
| Development | `http://localhost:3000`, `http://localhost:7860` | Hardcoded |
| Production | HTTPS origins only | Environment variable |
| Custom | Comma-separated list | `ALLOWED_ORIGINS` |

**Security Notes**:
- Wildcard (`*`) origins are prohibited when authentication headers are used
- Vercel preview domains validated via regex pattern matching
- CORS configuration should be reviewed when promoting to production

### 5.4.6 Disaster Recovery Procedures

#### Recovery Scenarios

| Scenario | Detection | Recovery Action |
|----------|-----------|-----------------|
| Graph corruption | Validation failure | Clear cache, reinitialize |
| Cache file corruption | JSON parse error | Delete cache, fresh fetch |
| Database unavailable | Connection timeout | Retry with exponential backoff |
| Yahoo Finance outage | Request timeout | Fall back to sample data |
| Authentication failure | JWT decode error | Re-authenticate user |

#### Data Recovery Priority

| Priority | Data | Recovery Source |
|----------|------|-----------------|
| 1 | User credentials | SQLite backup |
| 2 | Graph state | Cache file or Yahoo Finance |
| 3 | Session state | Stateless (no recovery needed) |

---

## 5.5 DEPLOYMENT ARCHITECTURE

### 5.5.1 Local Development

| Component | Command | Port | Purpose |
|-----------|---------|------|---------|
| FastAPI Backend | `uvicorn api.main:app --reload --port 8000` | 8000 | API development |
| Next.js Frontend | `cd frontend && npm run dev` | 3000 | UI development |
| Gradio UI | `python app.py` | 7860 | Legacy interface |

### 5.5.2 Docker Deployment

**Base Configuration** (from `Dockerfile`):

| Setting | Value | Purpose |
|---------|-------|---------|
| Base Image | `python:3.11-slim` | Minimal Python runtime |
| Working Directory | `/app` | Application root |
| User | `appuser` (UID 1000) | Non-root security |
| Exposed Port | 7860 | Gradio default |
| Health Check | HTTP probe every 30s | Container health |

**Docker Compose** (from `docker-compose.yml`):

| Service | Ports | Volumes | Restart Policy |
|---------|-------|---------|----------------|
| app | 7860:7860 | `./src:/app/src`, `./data:/app/data` | unless-stopped |

### 5.5.3 Vercel Serverless

**Build Configuration** (from `vercel.json`):

| Component | Builder | Configuration |
|-----------|---------|---------------|
| Backend | `@vercel/python` | maxLambdaSize: 50mb |
| Frontend | `@vercel/next` | Default Next.js settings |

**Route Configuration**:

| Pattern | Destination | Purpose |
|---------|-------------|---------|
| `/api/(.*)` | `api/main.py` | Backend API routes |
| `/(.*)` | `frontend/$1` | Frontend static/SSR |

### 5.5.4 Deployment Architecture Diagram

```mermaid
flowchart TB
    subgraph Local[Local Development]
        LocalFE[Next.js<br/>:3000]
        LocalAPI[FastAPI<br/>:8000]
        LocalGradio[Gradio<br/>:7860]
    end

    subgraph Docker[Docker Deployment]
        DockerApp[app container<br/>:7860]
        DockerVol[(Volumes)]
        DockerApp --> DockerVol
    end

    subgraph Vercel[Vercel Serverless]
        VercelEdge[Edge Network]
        VercelLambda[Python Lambda]
        VercelNext[Next.js SSR]
        VercelEdge --> VercelLambda
        VercelEdge --> VercelNext
    end

    Users([Users]) --> Local
    Users --> Docker
    Users --> Vercel
```

---

## 5.6 DATABASE SCHEMA

### 5.6.1 Schema Overview

The database schema (from `migrations/001_initial.sql`) defines four tables for optional persistence:

| Table | Purpose | Primary Key |
|-------|---------|-------------|
| `assets` | Financial instrument storage | `id` |
| `asset_relationships` | Relationship edges | `source_id, target_id, relationship_type` |
| `regulatory_events` | Event records | `id` |
| `regulatory_event_assets` | Event-asset junction | `event_id, asset_id` |

### 5.6.2 Entity Relationships

```mermaid
erDiagram
    assets {
        string id PK
        string symbol
        string name
        string asset_class
        string sector
        float price
        float market_cap
        string currency
    }

    asset_relationships {
        string source_id FK
        string target_id FK
        string relationship_type
        float strength
    }

    regulatory_events {
        string id PK
        string event_type
        date date
        string description
        float impact_score
    }

    regulatory_event_assets {
        string event_id FK
        string asset_id FK
    }

    assets ||--o{ asset_relationships : "source"
    assets ||--o{ asset_relationships : "target"
    assets ||--o{ regulatory_event_assets : "affected_by"
    regulatory_events ||--o{ regulatory_event_assets : "affects"
```

### 5.6.3 Cascade Behavior

| Parent Deletion | Cascade Target | Behavior |
|-----------------|----------------|----------|
| Asset | asset_relationships | Delete related edges |
| Asset | regulatory_event_assets | Remove junction entries |
| Regulatory Event | regulatory_event_assets | Remove junction entries |

---

## 5.7 References

#### Files Examined

- `api/main.py` - FastAPI application, routing, CORS, rate limiting, graph lifecycle
- `api/auth.py` - JWT authentication, password verification, user repository
- `api/database.py` - SQLite connection management for authentication
- `app.py` - Gradio UI entry point with tabbed interface
- `src/logic/asset_graph.py` - Core graph container class, relationship storage
- `src/models/financial_models.py` - Domain model dataclasses, enums, validation
- `src/data/sample_data.py` - Sample database generator
- `src/data/real_data_fetcher.py` - Yahoo Finance integration, caching
- `src/data/repository.py` - SQLAlchemy repository pattern
- `src/data/db_models.py` - ORM model definitions
- `src/visualizations/graph_visuals.py` - 3D Plotly visualization
- `src/visualizations/graph_2d_visuals.py` - 2D Plotly visualization
- `src/visualizations/metric_visuals.py` - Metrics dashboard charts
- `src/reports/schema_report.py` - Schema documentation generator
- `frontend/app/page.tsx` - Next.js home page component
- `frontend/app/lib/api.ts` - API client with Axios
- `frontend/app/components/NetworkVisualization.tsx` - 3D visualization component
- `frontend/app/components/MetricsDashboard.tsx` - Metrics display component
- `frontend/app/components/AssetList.tsx` - Asset table component
- `vercel.json` - Vercel deployment configuration
- `Dockerfile` - Container definition
- `docker-compose.yml` - Container orchestration
- `migrations/001_initial.sql` - Database schema definition
- `requirements.txt` - Python dependencies

#### Folders Explored

- `api/` - Backend API layer
- `src/logic/` - Core graph logic
- `src/models/` - Domain model definitions
- `src/data/` - Data layer components
- `src/visualizations/` - Visualization utilities
- `src/reports/` - Report generation
- `frontend/` - Next.js application
- `frontend/app/` - App Router source
- `frontend/app/components/` - React components
- `tests/` - Test harness

#### Technical Specification Sections Referenced

- 1.2 System Overview
- 3.1 Technology Stack Overview
- 3.6 Databases & Storage
- 3.7 Development & Deployment
- 3.8 Security Considerations
- 3.9 Integration Requirements
- 4.1 High-Level System Workflow
- 4.2 Core Business Process Flows
- 4.3 API Request Workflows
- 4.4 Frontend Workflows
- 4.5 Error Handling Workflows
- 4.6 Integration Sequence Diagrams
- 4.7 State Transition Diagrams
- 4.8 Timing and SLA Considerations

# 6. SYSTEM COMPONENTS DESIGN

## 6.1 Core Services Architecture

#### SERVICES ARCHITECTURE

## 6.1 Core Services Architecture

### 6.1.1 Architecture Classification Statement

#### Applicability Determination

**Core Services Architecture is not applicable for this system in the traditional microservices sense.** The Financial Asset Relationship Database is explicitly designed as a **monolithic layered architecture** with a single deployable Python process, not as a distributed microservices system.

This architectural decision is documented and intentional, based on the following rationale:

| Evaluation Criteria | System Characteristic | Microservices Applicability |
|--------------------|-----------------------|----------------------------|
| Deployment Model | Single Python process | Not Applicable |
| Service Decomposition | Modular packages within monolith | Not Applicable |
| Inter-Service Communication | Direct Python function calls | Not Applicable |
| Service Discovery | No distributed services to discover | Not Applicable |
| Data Management | Shared in-memory graph singleton | Not Applicable |

#### Explicit Architectural Decision

The technical specification documents this as a deliberate design choice:

| Aspect | Choice | Alternatives Considered |
|--------|--------|------------------------|
| Deployment Model | **Monolithic** | Microservices, Serverless-only |
| API Design | REST/JSON | GraphQL, gRPC |
| Data Storage | In-memory with optional persistence | Database-first, Event-sourced |

**Documented Rationale from Architecture Decision Records:**

- Single Python process reduces operational complexity for current scale
- Module boundaries enable future microservices migration if needed
- Dataset size (<500 assets) fits comfortably in memory with sub-millisecond access
- Same codebase deploys to Docker, Vercel, and local development environments

### 6.1.2 Monolithic Architecture Overview

#### Layered Architecture Design

Instead of service decomposition, the system implements a **four-layer architecture** with clear separation of concerns within a single process:

```mermaid
flowchart TB
    subgraph MonolithicArchitecture[Monolithic Layered Architecture]
        subgraph PresentationLayer[Presentation Layer]
            NextJS[Next.js Frontend<br/>Port 3000]
            GradioUI[Gradio UI<br/>Port 7860]
        end

        subgraph APILayer[API Layer]
            FastAPIApp[FastAPI Backend<br/>Port 8000]
            AuthModule[Auth Module]
            RateLimiter[Rate Limiter]
            CORSMiddleware[CORS Middleware]
        end

        subgraph BusinessLayer[Business Logic Layer]
            GraphEngine[Asset Graph Engine]
            DomainModels[Domain Models]
            VizModule[Visualization Module]
            MetricsCalc[Metrics Calculator]
        end

        subgraph DataLayer[Data Layer]
            SampleGen[Sample Data Generator]
            RealFetcher[Real Data Fetcher]
            JSONCache[JSON File Cache]
            SQLiteDB[SQLite Auth DB]
        end
    end

    NextJS --> FastAPIApp
    GradioUI --> GraphEngine
    FastAPIApp --> CORSMiddleware
    CORSMiddleware --> RateLimiter
    RateLimiter --> AuthModule
    AuthModule --> GraphEngine
    GraphEngine --> DomainModels
    GraphEngine --> VizModule
    GraphEngine --> MetricsCalc
    GraphEngine --> SampleGen
    GraphEngine --> RealFetcher
    RealFetcher --> JSONCache
    AuthModule --> SQLiteDB
```

#### Layer Responsibilities

| Layer | Components | Responsibility | Communication Pattern |
|-------|------------|----------------|----------------------|
| Presentation | Next.js, Gradio | User interface rendering | HTTP to API, Direct Python calls |
| API | FastAPI, Auth, Rate Limiter | Request routing, security enforcement | Direct Python imports |
| Business Logic | Graph Engine, Models, Visualization | Core domain logic, calculations | Direct Python function calls |
| Data | Fetcher, Cache, SQLite | Data persistence and retrieval | File I/O, SQL queries |

### 6.1.3 Modular Package Structure

#### Package Organization (Alternative to Services)

While the system does not use microservices, it maintains clean modular boundaries through Python packages that could theoretically be extracted into services in the future:

```mermaid
flowchart LR
    subgraph PackageStructure[Modular Package Organization]
        subgraph APIPackage[api/ Package]
            MainPy[main.py<br/>FastAPI App]
            AuthPy[auth.py<br/>JWT Handler]
            DatabasePy[database.py<br/>User Store]
        end

        subgraph SrcPackage[src/ Package]
            subgraph LogicPkg[logic/]
                AssetGraph[asset_graph.py]
            end

            subgraph ModelsPkg[models/]
                FinModels[financial_models.py]
            end

            subgraph DataPkg[data/]
                RealFetch[real_data_fetcher.py]
                SampleData[sample_database.py]
            end

            subgraph VizPkg[visualizations/]
                Graph3D[graph_visuals.py]
                Metrics[metric_visuals.py]
            end

            subgraph ReportsPkg[reports/]
                SchemaRpt[schema_report.py]
            end
        end

        subgraph FrontendPkg[frontend/ Package]
            NextApp[Next.js Application]
            Components[React Components]
            APIClient[Axios API Client]
        end
    end

    APIPackage --> SrcPackage
    FrontendPkg --> APIPackage
```

#### Module Boundary Definitions

| Module | Location | Future Service Potential | Dependencies |
|--------|----------|-------------------------|--------------|
| Graph Engine | `src/logic/asset_graph.py` | Graph Service | Domain Models only |
| Domain Models | `src/models/financial_models.py` | Shared Library | Python stdlib |
| Data Fetcher | `src/data/real_data_fetcher.py` | Data Ingestion Service | yfinance, cache |
| Visualization | `src/visualizations/` | Rendering Service | Plotly, Graph Engine |
| Auth Module | `api/auth.py` | Auth Service | PyJWT, passlib |
| API Gateway | `api/main.py` | API Gateway | All modules |

### 6.1.4 Communication Patterns Within Monolith

#### Internal Communication

Since all components run within a single Python process, communication uses direct function calls rather than network protocols:

| Source | Target | Pattern | Example |
|--------|--------|---------|---------|
| FastAPI → Graph | Direct import | `from src.logic.asset_graph import get_graph()` |
| Gradio → Graph | Direct import | `graph.get_assets()` |
| Graph → Models | Direct instantiation | `Asset(id=..., symbol=...)` |
| Graph → Fetcher | Direct call | `fetcher.fetch_real_data()` |
| API → Auth | Direct call | `authenticate_user(username, password)` |

#### External Communication

| Interface | Protocol | Purpose | Configuration |
|-----------|----------|---------|---------------|
| Frontend → API | REST/JSON over HTTP | Client-server communication | `NEXT_PUBLIC_API_URL` |
| API → Yahoo Finance | HTTP via yfinance | External data fetching | `USE_REAL_DATA_FETCHER` |
| API → SQLite | SQL via sqlite3 | Authentication persistence | `DATABASE_URL` |

### 6.1.5 Thread-Safe Singleton Pattern

#### Graph Instance Management

The system uses a thread-safe singleton pattern for the graph engine instead of distributed state management:

```mermaid
flowchart TB
    subgraph SingletonPattern[Thread-Safe Singleton Graph Access]
        APIRequest([API Request<br/>Arrives]) --> CheckGlobal{Global graph<br/>instance exists?}

        CheckGlobal -->|Yes| ReturnExisting[Return Existing<br/>Graph Instance]
        CheckGlobal -->|No| AcquireLock[Acquire<br/>threading.Lock]

        AcquireLock --> DoubleCheck{Double-check<br/>inside lock}
        DoubleCheck -->|Created by<br/>another thread| ReleaseReturn[Release Lock<br/>Return Graph]
        DoubleCheck -->|Still None| InitGraph[Initialize<br/>New Graph]

        InitGraph --> LoadCache{Cache<br/>available?}
        LoadCache -->|Yes| LoadFromCache[Load from<br/>JSON Cache]
        LoadCache -->|No| FetchData[Fetch from<br/>Data Source]

        FetchData --> BuildRelations[Build<br/>Relationships]
        LoadFromCache --> SetGlobal[Set Global<br/>Reference]
        BuildRelations --> SetGlobal

        SetGlobal --> ReleaseLock[Release Lock]
        ReleaseLock --> ReturnNew[Return New<br/>Graph Instance]

        ReturnExisting --> GraphReady([Graph Ready<br/>for Use])
        ReleaseReturn --> GraphReady
        ReturnNew --> GraphReady
    end
```

#### Implementation Details

| Aspect | Implementation | Purpose |
|--------|----------------|---------|
| Lock Type | `threading.Lock()` | Prevent race conditions |
| Pattern | Double-checked locking | Minimize lock contention |
| Scope | Module-level global | Single instance per process |
| Factory Override | `set_graph_factory()` | Test isolation support |

### 6.1.6 Resilience Patterns (Monolithic Context)

#### Graceful Degradation

Although not a distributed system, the monolith implements resilience patterns for external dependencies:

```mermaid
flowchart TB
    subgraph GracefulDegradation[Graceful Degradation Flow]
        StartInit([Initialize<br/>Graph]) --> TryCache{Try Load<br/>from Cache}

        TryCache -->|Success| CacheLoaded[Use Cached<br/>Graph Data]
        TryCache -->|Failure| LogCacheErr[Log Cache<br/>Error]

        LogCacheErr --> TryNetwork{Network<br/>Available?}
        TryNetwork -->|Yes| TryYahoo{Fetch from<br/>Yahoo Finance}
        TryNetwork -->|No| UseSample1[Fall Back to<br/>Sample Data]

        TryYahoo -->|Success| UseRealData[Use Real<br/>Market Data]
        TryYahoo -->|Partial| UsePartial[Use Available<br/>Partial Data]
        TryYahoo -->|Failure| UseSample2[Fall Back to<br/>Sample Data]

        CacheLoaded --> GraphReady([Graph<br/>Initialized])
        UseRealData --> SaveCache[Save to<br/>Cache]
        UsePartial --> SaveCache
        SaveCache --> GraphReady
        UseSample1 --> GraphReady
        UseSample2 --> GraphReady
    end
```

#### Resilience Pattern Summary

| Pattern | Implementation | Trigger Condition |
|---------|----------------|-------------------|
| Cache Fallback | JSON file cache | Cache load failure |
| Data Source Fallback | Sample data generator | Network unavailable |
| Partial Data Recovery | Use available data | Partial Yahoo Finance fetch |
| Atomic Cache Writes | `NamedTemporaryFile` + `os.replace()` | All cache operations |
| Rate Limiting | slowapi per-endpoint limits | Request threshold exceeded |
| Health Checks | `/api/health` endpoint | Container orchestration |

#### Atomic Cache Write Pattern

| Phase | Operation | Purpose |
|-------|-----------|---------|
| 1 | Write to `NamedTemporaryFile` | Isolate incomplete writes |
| 2 | Flush and sync to disk | Ensure durability |
| 3 | `os.replace()` atomic rename | Prevent corruption |
| 4 | Delete temp on failure | Clean up partial state |

### 6.1.7 Error Handling Architecture

#### Error Categories and Responses

| Error Type | HTTP Status | Recovery Action | User Feedback |
|------------|-------------|-----------------|---------------|
| Validation Error | 422 | Return Pydantic details | Field-level errors |
| Authentication Error | 401 | Prompt re-authentication | Login redirect |
| Rate Limit Exceeded | 429 | Add Retry-After header | Wait message |
| Resource Not Found | 404 | Return error detail | Item not found |
| Internal Error | 500 | Log exception | Generic error |

#### Graph Initialization Error Recovery

| Error Source | Detection | Recovery Action | Fallback |
|--------------|-----------|-----------------|----------|
| Cache load failed | JSON parse error | Proceed to fresh fetch | Standard initialization |
| Network disabled | Connection timeout | Use sample data | Offline mode |
| Yahoo Finance error | Request exception | Check partial data | Sample data fallback |
| Critical failure | Unrecoverable exception | Abort startup | Application exit |

### 6.1.8 Scalability Approach (Monolithic Context)

#### Current Scale Characteristics

| Metric | Current Capacity | Limiting Factor |
|--------|-----------------|-----------------|
| Node Count | <500 assets optimal | In-memory storage |
| Concurrent Users | Single-threaded graph | Python GIL |
| Response Time (p95) | <500ms | API processing |
| Visualization Nodes | 500 nodes, 2000 edges | Browser memory |

#### Scaling Tradeoffs

| Benefit of Monolithic | Associated Cost |
|----------------------|-----------------|
| Simpler operations | Limited horizontal scaling of graph |
| Faster development | All components share runtime |
| Lower latency | Memory-bound capacity |
| Single deployment | Single point of failure |

#### Future Scaling Path

If the system grows beyond current scale constraints, the modular package structure enables migration to microservices:

| Growth Trigger | Recommended Action | Module to Extract |
|---------------|-------------------|-------------------|
| >500 assets | Database persistence | Graph Engine → Graph Service |
| Multi-tenant requirements | Dedicated auth service | Auth Module → Auth Service |
| High visualization load | Separate rendering | Visualization → Render Service |
| Data ingestion volume | Async processing | Data Fetcher → Ingestion Service |

### 6.1.9 Performance Optimization

#### Performance Targets (SLAs)

| Operation | Target | Measurement |
|-----------|--------|-------------|
| API Response (p95) | <500ms | Request to response |
| Visualization Rendering | <2 seconds | Data load to interactive |
| Token Generation | <100ms | Credential to token |
| Graph Initialization | <3 seconds | Application startup |
| Relationship Discovery | <500ms | For 100 assets |
| Initial Page Load | <3 seconds | Navigation to interactive |

#### Optimization Techniques

| Technique | Implementation | Impact |
|-----------|----------------|--------|
| Deterministic Layout | Fixed seed (seed=42) | Reproducible 3D positions |
| Lazy Initialization | Double-checked locking | Fast startup |
| JSON Caching | Atomic file cache | Reduced API calls |
| Rate Limiting | Per-endpoint limits | Fair resource allocation |
| Client-Side Limits | MAX_NODES/MAX_EDGES | Browser stability |

### 6.1.10 Deployment Architecture Comparison

#### Deployment Options

```mermaid
flowchart TB
    subgraph DeploymentOptions[Deployment Architecture Options]
        subgraph LocalDev[Local Development]
            LocalFE[Next.js<br/>:3000]
            LocalAPI[FastAPI<br/>:8000]
            LocalGradio[Gradio<br/>:7860]
        end

        subgraph DockerDeploy[Docker Deployment]
            DockerContainer[Single Container<br/>:7860]
            DockerVolumes[(Mounted<br/>Volumes)]
            DockerContainer --> DockerVolumes
        end

        subgraph VercelDeploy[Vercel Serverless]
            VercelEdge[Edge<br/>Network]
            VercelLambda[Python<br/>Lambda]
            VercelSSR[Next.js<br/>SSR]
            VercelEdge --> VercelLambda
            VercelEdge --> VercelSSR
        end
    end

    Users([End Users]) --> LocalDev
    Users --> DockerDeploy
    Users --> VercelDeploy
```

#### Deployment Configuration Summary

| Environment | Components | Command | Notes |
|-------------|------------|---------|-------|
| Local Dev | FastAPI + Next.js + Gradio | Multiple processes | Full development environment |
| Docker | Single container | `docker-compose up` | Simplified deployment |
| Vercel | Lambda + SSR | `vercel deploy` | Serverless production |

### 6.1.11 Constraints and Limitations

#### Documented System Constraints

| ID | Constraint | Mitigation Strategy |
|----|------------|-------------------|
| C-001 | In-memory graph limits scalability | Database persistence option planned |
| C-002 | Single-user JWT authentication | Role-based access planned for Phase 2 |
| C-003 | Yahoo Finance API rate limits | Caching with atomic file writes |
| C-004 | Browser memory limits visualization | MAX_NODES/MAX_EDGES guardrails |

#### Architectural Assumptions

| ID | Assumption | Impact if Invalid |
|----|------------|------------------|
| A-001 | Modern browser support | Visualization features may fail |
| A-002 | Network connectivity available | Falls back to sample data |
| A-003 | Single concurrent admin sufficient | Multi-user requires extension |
| A-004 | Dataset size <500 nodes | Larger datasets need pagination |

### 6.1.12 Microservices Migration Readiness

#### Module Extraction Feasibility

| Module | Extraction Complexity | Dependencies to Resolve | Estimated Effort |
|--------|----------------------|------------------------|------------------|
| Auth Module | Low | JWT secret management | 1-2 weeks |
| Data Fetcher | Medium | Cache sharing strategy | 2-4 weeks |
| Visualization | Medium | Graph data access pattern | 2-4 weeks |
| Graph Engine | High | State management overhaul | 4-8 weeks |

#### Prerequisites for Migration

| Prerequisite | Current State | Required for Migration |
|--------------|--------------|----------------------|
| Database Persistence | Optional (F-015) | Required for shared state |
| Message Queue | Not implemented | Required for async communication |
| Service Mesh | Not applicable | Required for service discovery |
| Distributed Tracing | Not implemented | Required for observability |

### 6.1.13 References

#### Technical Specification Sections Referenced

- **5.1 HIGH-LEVEL ARCHITECTURE** - Layered architecture design and system boundaries
- **5.2 COMPONENT DETAILS** - Component responsibilities and interaction patterns
- **5.3 TECHNICAL DECISIONS** - Monolithic architecture choice rationale
- **5.4 CROSS-CUTTING CONCERNS** - Error handling, monitoring, authentication
- **5.5 DEPLOYMENT ARCHITECTURE** - Deployment options and configurations
- **2.4 Implementation Considerations** - Performance and scalability constraints
- **2.6 Assumptions and Constraints** - System limitations and mitigations
- **3.9 Integration Requirements** - Frontend-backend communication patterns
- **4.5 Error Handling Workflows** - Error recovery flows and patterns

#### Files and Folders Examined

| Path | Relevance |
|------|-----------|
| `api/main.py` | FastAPI application with thread-safe singleton graph pattern |
| `api/auth.py` | JWT authentication module implementation |
| `src/logic/asset_graph.py` | Graph engine with in-memory storage |
| `src/data/real_data_fetcher.py` | Fallback mechanism and atomic caching |
| `src/models/financial_models.py` | Domain model definitions |
| `src/visualizations/` | Plotly visualization modules |
| `app.py` | Gradio UI with direct Python function calls |
| `docker-compose.yml` | Single container deployment configuration |
| `vercel.json` | Serverless deployment configuration |
| `frontend/` | Next.js client application |

#### Architectural Decision Records

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ADR-001 | Monolithic over Microservices | Operational simplicity at current scale |
| ADR-002 | REST/JSON over GraphQL/gRPC | Universal client compatibility |
| ADR-003 | In-memory over Database-first | Sub-millisecond access for <500 assets |
| ADR-004 | Thread-safe Singleton | Prevent race conditions, enable testing |

## 6.2 Database Design

### 6.2.1 Database Architecture Overview

#### 6.2.1.1 Hybrid Storage Architecture

The Financial Asset Relationship Database employs a **hybrid data architecture** that combines multiple complementary storage mechanisms optimized for different use cases. This design prioritizes in-memory performance for real-time graph operations while providing optional persistence for durability and scalability.

| Storage Layer | Technology | Purpose | Durability |
|---------------|------------|---------|------------|
| Primary Runtime | In-Memory Graph | Relationship traversal | Process lifetime |
| Authentication | SQLite | User credentials | Persistent |
| Asset Persistence | SQLAlchemy ORM | Optional durable storage | Persistent |
| External Data Cache | JSON Files | Yahoo Finance data | Persistent |

#### 6.2.1.2 Storage Layer Architecture Diagram

```mermaid
flowchart TB
    subgraph StorageArchitecture[Hybrid Storage Architecture]
        subgraph RuntimeLayer[Runtime Layer]
            InMemoryGraph[In-Memory Graph<br/>Dict-based Adjacency Lists]
            GraphSingleton[Thread-Safe<br/>Singleton Pattern]
            InMemoryGraph --> GraphSingleton
        end

        subgraph PersistenceLayer[Persistence Layer]
            subgraph AuthDB[Authentication Database]
                SQLiteAuth[(SQLite<br/>user_credentials)]
            end

            subgraph AssetDB[Asset Persistence]
                SQLAORM[SQLAlchemy ORM]
                PostgreSQL[(PostgreSQL<br/>Production)]
                SQLiteDev[(SQLite<br/>Development)]
                SQLAORM --> PostgreSQL
                SQLAORM --> SQLiteDev
            end

            subgraph CacheLayer[Cache Layer]
                JSONCache[(JSON Files<br/>Atomic Writes)]
            end
        end
    end

    GraphSingleton --> SQLAORM
    GraphSingleton --> JSONCache
    AuthModule[Auth Module] --> SQLiteAuth
```

#### 6.2.1.3 Design Rationale

| Design Choice | Rationale | Trade-off |
|---------------|-----------|-----------|
| In-memory primary storage | Sub-millisecond relationship traversal | Memory-bound capacity |
| Optional database persistence | Flexibility for different deployment scales | Additional complexity |
| Wide table design | Single-table queries for asset retrieval | Nullable columns for type-specific fields |
| Cascade deletes on all FKs | Referential integrity without orphans | Potential for bulk deletes |

---

### 6.2.2 Schema Design

#### 6.2.2.1 Core Entity Model

The database schema is defined in `migrations/001_initial.sql` and implements a graph-oriented relational design supporting financial asset relationships.

#### Entity Tables Summary

| Table | Purpose | Primary Key | Record Count Expectation |
|-------|---------|-------------|--------------------------|
| `assets` | Financial instrument storage | `id` (TEXT) | <500 for optimal performance |
| `asset_relationships` | Directed relationship edges | `id` (INTEGER) | N × average_degree |
| `regulatory_events` | Regulatory event records | `id` (TEXT) | Events per asset |
| `regulatory_event_assets` | Many-to-many junction | `id` (INTEGER) | Events × affected assets |

#### 6.2.2.2 Assets Table Schema

The `assets` table uses a **wide table design** with nullable type-specific columns rather than separate tables per asset class, enabling simpler queries at the cost of schema sparsity.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | Unique asset identifier |
| `symbol` | TEXT | NOT NULL | Trading symbol |
| `name` | TEXT | NOT NULL | Display name |
| `asset_class` | TEXT | NOT NULL | Enum: equity, fixed_income, commodity, currency, derivative |
| `sector` | TEXT | NOT NULL | Industry sector classification |
| `price` | REAL | NOT NULL | Current market price |
| `market_cap` | REAL | NULLABLE | Market capitalization (equities) |
| `currency` | TEXT | NOT NULL | ISO 4217 currency code |

#### Equity-Specific Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `pe_ratio` | REAL | NULLABLE | Price-to-earnings ratio |
| `dividend_yield` | REAL | NULLABLE | Annual dividend yield |
| `earnings_per_share` | REAL | NULLABLE | EPS value |
| `book_value` | REAL | NULLABLE | Book value per share |

#### Fixed Income Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `yield_to_maturity` | REAL | NULLABLE | YTM percentage |
| `coupon_rate` | REAL | NULLABLE | Annual coupon rate |
| `maturity_date` | TEXT | NULLABLE | ISO 8601 date |
| `credit_rating` | TEXT | NULLABLE | Credit rating code |
| `issuer_id` | TEXT | NULLABLE | FK to issuing entity |

#### Commodity/Currency Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `contract_size` | REAL | NULLABLE | Commodity contract size |
| `delivery_date` | TEXT | NULLABLE | Commodity delivery date |
| `volatility` | REAL | NULLABLE | Price volatility |
| `exchange_rate` | REAL | NULLABLE | Currency exchange rate |
| `country` | TEXT | NULLABLE | Currency country |
| `central_bank_rate` | REAL | NULLABLE | Central bank interest rate |

#### 6.2.2.3 Asset Relationships Table Schema

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique edge identifier |
| `source_asset_id` | TEXT | NOT NULL, FK → assets(id) ON DELETE CASCADE | Origin node |
| `target_asset_id` | TEXT | NOT NULL, FK → assets(id) ON DELETE CASCADE | Destination node |
| `relationship_type` | TEXT | NOT NULL | Relationship classification |
| `strength` | REAL | NOT NULL | Edge weight [0.0, 1.0] |
| `bidirectional` | INTEGER | NOT NULL DEFAULT 0 | Boolean flag (0/1) |

**Unique Constraint**: `(source_asset_id, target_asset_id, relationship_type)` prevents duplicate edges.

#### 6.2.2.4 Regulatory Events Tables

#### Regulatory Events Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | Unique event identifier |
| `asset_id` | TEXT | NOT NULL, FK → assets(id) ON DELETE CASCADE | Primary affected asset |
| `event_type` | TEXT | NOT NULL | Event classification |
| `date` | TEXT | NOT NULL | ISO 8601 date |
| `description` | TEXT | NOT NULL | Event description |
| `impact_score` | REAL | NOT NULL | Impact range [-1.0, 1.0] |

#### Regulatory Event Assets Junction Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Junction record ID |
| `event_id` | TEXT | NOT NULL, FK → regulatory_events(id) ON DELETE CASCADE | Event reference |
| `asset_id` | TEXT | NOT NULL, FK → assets(id) ON DELETE CASCADE | Affected asset |

**Unique Constraint**: `(event_id, asset_id)` prevents duplicate associations.

#### 6.2.2.5 Authentication Schema

Defined in `api/database.py`, the authentication schema provides user credential storage separate from the asset database.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | User record ID |
| `username` | TEXT | UNIQUE NOT NULL | Login identifier |
| `email` | TEXT | NULLABLE | Email address |
| `full_name` | TEXT | NULLABLE | Display name |
| `hashed_password` | TEXT | NOT NULL | pbkdf2_sha256 hash |
| `disabled` | INTEGER | NOT NULL DEFAULT 0 | Active flag (0=active, 1=disabled) |

#### 6.2.2.6 Entity Relationship Diagram

```mermaid
erDiagram
    assets {
        TEXT id PK "Unique identifier"
        TEXT symbol "NOT NULL"
        TEXT name "NOT NULL"
        TEXT asset_class "NOT NULL"
        TEXT sector "NOT NULL"
        REAL price "NOT NULL"
        REAL market_cap "NULLABLE"
        TEXT currency "NOT NULL (3-char ISO)"
        REAL pe_ratio "NULLABLE - Equity"
        REAL dividend_yield "NULLABLE - Equity"
        REAL yield_to_maturity "NULLABLE - Bond"
        TEXT credit_rating "NULLABLE - Bond"
        TEXT issuer_id "NULLABLE - Bond FK"
    }

    asset_relationships {
        INTEGER id PK "AUTOINCREMENT"
        TEXT source_asset_id FK "NOT NULL"
        TEXT target_asset_id FK "NOT NULL"
        TEXT relationship_type "NOT NULL"
        REAL strength "NOT NULL [0-1]"
        INTEGER bidirectional "DEFAULT 0"
    }

    regulatory_events {
        TEXT id PK "Unique identifier"
        TEXT asset_id FK "Primary affected"
        TEXT event_type "NOT NULL"
        TEXT date "ISO 8601"
        TEXT description "NOT NULL"
        REAL impact_score "[-1, 1]"
    }

    regulatory_event_assets {
        INTEGER id PK "AUTOINCREMENT"
        TEXT event_id FK "NOT NULL"
        TEXT asset_id FK "NOT NULL"
    }

    user_credentials {
        INTEGER id PK "AUTOINCREMENT"
        TEXT username UK "NOT NULL"
        TEXT email "NULLABLE"
        TEXT full_name "NULLABLE"
        TEXT hashed_password "NOT NULL"
        INTEGER disabled "DEFAULT 0"
    }

    assets ||--o{ asset_relationships : "source_asset_id"
    assets ||--o{ asset_relationships : "target_asset_id"
    assets ||--o{ regulatory_events : "primary_asset"
    assets ||--o{ regulatory_event_assets : "affected_asset"
    regulatory_events ||--o{ regulatory_event_assets : "affects"
```

---

### 6.2.3 Indexing Strategy

#### 6.2.3.1 Primary Key Indexes

All primary keys are automatically indexed by the database engine:

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| `assets` | `id` | B-tree | Direct asset lookup |
| `asset_relationships` | `id` | B-tree | Edge identification |
| `regulatory_events` | `id` | B-tree | Event lookup |
| `regulatory_event_assets` | `id` | B-tree | Junction lookup |
| `user_credentials` | `id` | B-tree | User record access |

#### 6.2.3.2 Unique Constraint Indexes

| Table | Constraint | Columns | Purpose |
|-------|------------|---------|---------|
| `asset_relationships` | `uq_relationship` | `(source_asset_id, target_asset_id, relationship_type)` | Prevent duplicate edges |
| `regulatory_event_assets` | `uq_event_asset` | `(event_id, asset_id)` | Prevent duplicate associations |
| `user_credentials` | `username` | `username` | Unique login enforcement |

#### 6.2.3.3 Foreign Key Indexes

Foreign key columns are indexed to support cascade delete operations and join queries:

| Table | Column | References | Index Type |
|-------|--------|------------|------------|
| `asset_relationships` | `source_asset_id` | `assets(id)` | Implicit FK index |
| `asset_relationships` | `target_asset_id` | `assets(id)` | Implicit FK index |
| `regulatory_events` | `asset_id` | `assets(id)` | Implicit FK index |
| `regulatory_event_assets` | `event_id` | `regulatory_events(id)` | Implicit FK index |
| `regulatory_event_assets` | `asset_id` | `assets(id)` | Implicit FK index |

#### 6.2.3.4 Recommended Production Indexes

For PostgreSQL production deployments handling larger datasets:

| Table | Proposed Index | Columns | Rationale |
|-------|----------------|---------|-----------|
| `assets` | `idx_assets_sector` | `sector` | Sector-based filtering |
| `assets` | `idx_assets_class` | `asset_class` | Asset class filtering |
| `asset_relationships` | `idx_rel_type` | `relationship_type` | Relationship type queries |
| `regulatory_events` | `idx_events_date` | `date` | Date range queries |

---

### 6.2.4 Data Flow Architecture

#### 6.2.4.1 Data Flow Diagram

```mermaid
flowchart TB
    subgraph ExternalSources[External Data Sources]
        YahooFinance[Yahoo Finance API]
        SampleData[Sample Data Generator]
    end

    subgraph DataIngestion[Data Ingestion Layer]
        RealFetcher[RealDataFetcher<br/>src/data/real_data_fetcher.py]
        SampleGen[Sample Database<br/>src/data/sample_data.py]
    end

    subgraph CacheLayer[Cache Layer]
        JSONCache[(JSON File Cache<br/>Atomic Writes)]
    end

    subgraph GraphLayer[Graph Layer]
        InMemoryGraph[AssetRelationshipGraph<br/>src/logic/asset_graph.py]
        RelationshipBuilder[Relationship Builder<br/>Sector/Bond/Currency Links]
    end

    subgraph PersistenceLayer[Persistence Layer]
        Repository[AssetGraphRepository<br/>src/data/repository.py]
        SQLAlchemyDB[(SQLAlchemy ORM<br/>PostgreSQL/SQLite)]
        SQLiteAuth[(SQLite Auth<br/>user_credentials)]
    end

    subgraph APILayer[API Layer]
        FastAPI[FastAPI Endpoints<br/>api/main.py]
        AuthModule[Auth Module<br/>api/auth.py]
    end

    YahooFinance --> RealFetcher
    SampleData --> SampleGen
    RealFetcher --> JSONCache
    RealFetcher --> InMemoryGraph
    SampleGen --> InMemoryGraph
    JSONCache --> RealFetcher
    InMemoryGraph --> RelationshipBuilder
    RelationshipBuilder --> InMemoryGraph
    InMemoryGraph --> Repository
    Repository --> SQLAlchemyDB
    AuthModule --> SQLiteAuth
    FastAPI --> InMemoryGraph
    FastAPI --> AuthModule
```

#### 6.2.4.2 Data Flow Sequence

| Phase | Operation | Source | Destination |
|-------|-----------|--------|-------------|
| 1 | Data Fetch | Yahoo Finance / Sample Generator | Data Fetcher |
| 2 | Cache Check | JSON Cache | Data Fetcher |
| 3 | Graph Build | Asset Data | In-Memory Graph |
| 4 | Relationship Discovery | Graph Nodes | Edge Creation |
| 5 | Optional Persistence | In-Memory Graph | SQLAlchemy ORM |
| 6 | API Serving | In-Memory Graph | FastAPI Responses |

---

### 6.2.5 ORM Layer Design

#### 6.2.5.1 SQLAlchemy Configuration

Implemented in `src/data/database.py`, the ORM layer supports multiple database backends:

| Configuration | Value | Purpose |
|---------------|-------|---------|
| SQLAlchemy Version | >=2.0.0 | Modern ORM syntax |
| Syntax Style | 2.x with `Mapped`/`mapped_column` | Type-safe mappings |
| Environment Variable | `ASSET_GRAPH_DATABASE_URL` | Connection string |
| Default Backend | SQLite | Development simplicity |

#### 6.2.5.2 Connection Configuration by Backend

| Backend | Use Case | Configuration |
|---------|----------|---------------|
| SQLite (file) | Development | `sqlite:///path/to/db.sqlite` |
| SQLite (in-memory) | Testing | `sqlite:///:memory:` with `StaticPool` |
| PostgreSQL | Production | `postgresql://user:pass@host/db` |

#### 6.2.5.3 ORM Model Classes

Defined in `src/data/db_models.py`:

#### AssetORM Model

| Attribute | SQLAlchemy Type | Relationship |
|-----------|-----------------|--------------|
| `id` | `Mapped[str]` | Primary Key |
| `outgoing_relationships` | `Mapped[List["AssetRelationshipORM"]]` | One-to-Many (cascade: all, delete-orphan) |
| `incoming_relationships` | `Mapped[List["AssetRelationshipORM"]]` | One-to-Many (cascade: all, delete-orphan) |
| `regulatory_events` | `Mapped[List["RegulatoryEventORM"]]` | One-to-Many (cascade: all, delete-orphan) |

#### AssetRelationshipORM Model

| Attribute | SQLAlchemy Type | Relationship |
|-----------|-----------------|--------------|
| `id` | `Mapped[int]` | Primary Key (autoincrement) |
| `source_asset` | `Mapped["AssetORM"]` | Many-to-One |
| `target_asset` | `Mapped["AssetORM"]` | Many-to-One |

#### RegulatoryEventORM Model

| Attribute | SQLAlchemy Type | Relationship |
|-----------|-----------------|--------------|
| `id` | `Mapped[str]` | Primary Key |
| `asset` | `Mapped["AssetORM"]` | Many-to-One |
| `related_assets` | `Mapped[List["RegulatoryEventAssetORM"]]` | One-to-Many (cascade: all, delete-orphan) |

#### 6.2.5.4 Repository Pattern Implementation

The `AssetGraphRepository` class in `src/data/repository.py` provides the data access layer:

| Method | Operation | Transaction Scope |
|--------|-----------|-------------------|
| `upsert_asset()` | Insert or update asset | Caller manages |
| `list_assets()` | Retrieve all assets | Read-only |
| `get_assets_map()` | Dict by asset ID | Read-only |
| `delete_asset()` | Remove asset (cascades) | Caller manages |
| `add_or_update_relationship()` | Upsert edge | Caller manages |
| `list_relationships()` | Retrieve all edges | Read-only |
| `get_relationship()` | Single edge lookup | Read-only |
| `delete_relationship()` | Remove edge | Caller manages |
| `upsert_regulatory_event()` | Insert/update event | Caller manages |
| `list_regulatory_events()` | Retrieve all events | Read-only |
| `delete_regulatory_event()` | Remove event | Caller manages |

---

### 6.2.6 Caching Architecture

#### 6.2.6.1 JSON File Cache Design

Implemented in `src/data/real_data_fetcher.py`, the cache layer provides persistent storage for external API data:

| Configuration | Environment Variable | Purpose |
|---------------|---------------------|---------|
| Real Data Cache | `REAL_DATA_CACHE_PATH` | Yahoo Finance data |
| Graph Cache | `GRAPH_CACHE_PATH` | Serialized graph state |

#### 6.2.6.2 Atomic Write Pattern

The cache uses an atomic write pattern to prevent data corruption:

```mermaid
flowchart LR
    subgraph AtomicWrite[Atomic Write Sequence]
        Start([Start Write]) --> CreateTemp[Create NamedTemporaryFile<br/>in same directory]
        CreateTemp --> WriteJSON[Write JSON Data]
        WriteJSON --> FlushSync[Flush + Sync<br/>to Disk]
        FlushSync --> CloseHandle[Close File Handle]
        CloseHandle --> AtomicRename[os.replace()<br/>Atomic Rename]
        AtomicRename --> Complete([Write Complete])
    end

    subgraph FailurePath[Failure Recovery]
        WriteJSON -.->|Exception| CleanupTemp[Delete Temp File]
        FlushSync -.->|Exception| CleanupTemp
        CleanupTemp --> Failed([Write Failed<br/>Original Preserved])
    end
```

#### 6.2.6.3 Atomic Write Guarantees

| Phase | Operation | Failure Behavior |
|-------|-----------|------------------|
| 1 | Create temporary file | No change to target |
| 2 | Write JSON content | Temp file only |
| 3 | Flush and sync | Data on disk in temp |
| 4 | `os.replace()` | Atomic swap or rollback |

#### 6.2.6.4 Cache Content Structure

| Element | Serialization | Purpose |
|---------|---------------|---------|
| Assets | JSON with `__type__` discriminator | Type reconstruction |
| Regulatory Events | Enum values as strings | Serialization compatibility |
| Relationships | Adjacency list format | Graph reconstruction |
| Metadata | Timestamps, version info | Cache validation |

---

### 6.2.7 Replication and High Availability

#### 6.2.7.1 Current Architecture Limitations

As documented in the system constraints, the current architecture prioritizes simplicity over high availability:

| Constraint ID | Description | Impact |
|---------------|-------------|--------|
| C-001 | In-memory graph limits scalability | No built-in replication |
| A-003 | Single concurrent admin sufficient | Single-user authentication |
| A-004 | Dataset size <500 nodes | Memory-based storage viable |

#### 6.2.7.2 Replication Architecture Diagram

```mermaid
flowchart TB
    subgraph CurrentArchitecture[Current Single-Instance Architecture]
        SingleProcess[Python Process]
        InMemoryGraph[In-Memory Graph]
        SQLiteAuth[(SQLite Auth)]
        JSONCache[(JSON Cache)]

        SingleProcess --> InMemoryGraph
        SingleProcess --> SQLiteAuth
        SingleProcess --> JSONCache
    end

    subgraph FutureScaling[Future Scaling Path]
        LoadBalancer[Load Balancer]
        Instance1[Instance 1]
        Instance2[Instance 2]
        SharedDB[(PostgreSQL<br/>Shared Database)]
        DistCache[(Redis Cache)]

        LoadBalancer --> Instance1
        LoadBalancer --> Instance2
        Instance1 --> SharedDB
        Instance2 --> SharedDB
        Instance1 --> DistCache
        Instance2 --> DistCache
    end

    CurrentArchitecture -.->|Migration Path| FutureScaling
```

#### 6.2.7.3 Production Scaling Recommendations

| Growth Trigger | Recommended Action | Module Impact |
|----------------|-------------------|---------------|
| >500 assets | Enable PostgreSQL persistence | Graph Engine |
| Multi-user requirements | Implement connection pooling | Auth Module |
| High availability needs | Deploy multiple instances | All modules |
| Session management | Add Redis for shared state | API Layer |

---

### 6.2.8 Backup and Recovery Architecture

#### 6.2.8.1 Data Durability by Component

| Component | Durability Level | Backup Method |
|-----------|-----------------|---------------|
| In-Memory Graph | Process lifetime | JSON cache serialization |
| SQLite Auth | File-based persistence | File system backup |
| PostgreSQL (if used) | Database-level | pg_dump, WAL archiving |
| JSON Cache | File-based | File system backup |

#### 6.2.8.2 Recovery Scenarios

| Scenario | Detection Method | Recovery Action | Data Loss |
|----------|-----------------|-----------------|-----------|
| Graph corruption | Validation failure | Reload from cache or fetch | None (if cached) |
| Cache file corruption | JSON parse error | Fresh fetch from source | None |
| Auth database loss | Connection failure | Restore from backup | Potential |
| Process restart | N/A | Graph reinitialization | Session state |

#### 6.2.8.3 Disaster Recovery Flow

```mermaid
flowchart TB
    subgraph DisasterRecovery[Disaster Recovery Flow]
        Failure([System Failure]) --> DetectType{Failure Type}

        DetectType -->|Graph Corruption| ClearGraph[Clear In-Memory<br/>Graph]
        DetectType -->|Cache Corruption| DeleteCache[Delete Cache<br/>File]
        DetectType -->|Database Loss| RestoreBackup[Restore from<br/>Backup]
        DetectType -->|Full System| FullRestore[Full System<br/>Recovery]

        ClearGraph --> ReinitGraph[Reinitialize<br/>Graph]
        DeleteCache --> FreshFetch[Fresh Data<br/>Fetch]
        RestoreBackup --> VerifyData[Verify Data<br/>Integrity]
        FullRestore --> DeployNew[Deploy New<br/>Instance]

        ReinitGraph --> CheckCache{Cache<br/>Available?}
        CheckCache -->|Yes| LoadCache[Load from<br/>Cache]
        CheckCache -->|No| FreshFetch
        FreshFetch --> BuildGraph[Build Graph<br/>from Source]

        LoadCache --> Operational([System<br/>Operational])
        BuildGraph --> Operational
        VerifyData --> Operational
        DeployNew --> Operational
    end
```

#### 6.2.8.4 Data Recovery Priority

| Priority | Data Type | Recovery Source | Maximum Acceptable Loss |
|----------|-----------|-----------------|------------------------|
| 1 (Critical) | User credentials | SQLite backup | None |
| 2 (High) | Graph state | Cache or Yahoo Finance | Minutes of updates |
| 3 (Medium) | Cached data | Fresh external fetch | Cache refresh time |
| 4 (Low) | Session state | Stateless (no recovery) | Full session |

---

### 6.2.9 Compliance Considerations

#### 6.2.9.1 Data Retention Policies

| Data Type | Retention Period | Disposal Method |
|-----------|-----------------|-----------------|
| User credentials | Until explicitly deleted | Secure database deletion |
| Authentication logs | Application runtime | In-memory only |
| Cached market data | Configurable cache TTL | File overwrite |
| Graph state | Process lifetime | Memory deallocation |

#### 6.2.9.2 Access Control Matrix

| Role | Authentication | Asset Data | User Management |
|------|----------------|------------|-----------------|
| Anonymous | None | Read-only API access | None |
| Authenticated User | JWT token | Full API access | Self-profile only |
| Admin | JWT + admin flag | Full access | User CRUD |

#### 6.2.9.3 Privacy Controls

| Control | Implementation | Location |
|---------|----------------|----------|
| Password hashing | pbkdf2_sha256 | `api/auth.py` |
| Token expiration | 30-minute JWT lifetime | `api/auth.py` |
| Secure transport | HTTPS required in production | Deployment config |
| Secret management | Environment variables only | Never committed |

#### 6.2.9.4 Audit Mechanisms

| Audit Point | Log Level | Content |
|-------------|-----------|---------|
| Graph initialization | INFO | Success/failure status |
| Authentication attempts | WARNING | Failed login attempts |
| Request errors | ERROR | Exception details |
| Cache operations | INFO | Load/save success |

---

### 6.2.10 Performance Optimization

#### 6.2.10.1 Query Optimization Patterns

| Pattern | Implementation | Benefit |
|---------|----------------|---------|
| In-memory primary storage | `Dict[source_id, List[Tuple]]` | Sub-millisecond traversal |
| Thread-safe singleton | Double-checked locking | Minimal lock contention |
| Lazy initialization | On-demand graph creation | Fast application startup |
| Unique constraint indexes | Composite unique keys | O(1) duplicate detection |

#### 6.2.10.2 Performance Targets

| Operation | Target SLA | Measurement |
|-----------|------------|-------------|
| Relationship traversal | <1ms | In-memory graph access |
| Asset lookup | <10ms | Indexed primary key |
| Graph initialization | <3 seconds | Application startup |
| Relationship discovery | <500ms | For 100 assets |

#### 6.2.10.3 Connection Management

#### SQLite Authentication Database

| Configuration | Value | Purpose |
|---------------|-------|---------|
| `check_same_thread` | `False` | Multi-threaded access |
| Connection sharing | Locked shared connection | In-memory database support |
| Row factory | Dict-style access | Convenient result handling |

#### SQLAlchemy ORM Connection

| Backend | Pool Configuration | Purpose |
|---------|-------------------|---------|
| SQLite in-memory | `StaticPool` | Single shared connection |
| SQLite file | Default pool | Connection reuse |
| PostgreSQL | Default pool | Connection pooling |

#### 6.2.10.4 Batch Processing Approach

| Operation | Batch Strategy | Implementation |
|-----------|----------------|----------------|
| Graph initialization | Bulk asset loading | Single transaction |
| Relationship building | Iterate all assets once | O(n) complexity |
| Cache serialization | Single JSON write | Atomic file operation |
| Repository upserts | Caller-managed batching | Session scope pattern |

---

### 6.2.11 Transaction Management

#### 6.2.11.1 Transaction Boundaries

```mermaid
flowchart TB
    subgraph TransactionScope[Transaction Scope Management]
        StartOp([Start Operation]) --> AcquireSession[Acquire<br/>Session]
        AcquireSession --> BeginTx[Begin<br/>Transaction]
        BeginTx --> ExecuteOps[Execute<br/>Operations]

        ExecuteOps --> CheckSuccess{Success?}
        CheckSuccess -->|Yes| CommitTx[Commit<br/>Transaction]
        CheckSuccess -->|No| RollbackTx[Rollback<br/>Transaction]

        CommitTx --> CloseSession[Close<br/>Session]
        RollbackTx --> CloseSession
        CloseSession --> EndOp([End Operation])
    end
```

#### 6.2.11.2 Session Scope Context Manager

The `session_scope` context manager in `src/data/repository.py` provides transaction management:

| Phase | Action | On Exception |
|-------|--------|--------------|
| Entry | Create session from factory | N/A |
| Yield | Expose session for operations | N/A |
| Exit (success) | Commit transaction | N/A |
| Exit (error) | N/A | Rollback transaction |
| Finally | Close session | Close session |

#### 6.2.11.3 Cascade Delete Behavior

| Parent Entity | Child Entities | Cascade Type |
|---------------|----------------|--------------|
| Asset | asset_relationships (outgoing) | all, delete-orphan |
| Asset | asset_relationships (incoming) | all, delete-orphan |
| Asset | regulatory_events | all, delete-orphan |
| Regulatory Event | regulatory_event_assets | all, delete-orphan |

---

### 6.2.12 Domain Model Validation

#### 6.2.12.1 Validation Rules

Implemented in `src/models/financial_models.py`:

| Field | Validation Rule | Error Type |
|-------|-----------------|------------|
| `id`, `symbol`, `name` | Non-empty string | `ValueError` |
| `price`, `market_cap` | Non-negative float | `ValueError` |
| `currency` | 3-character ISO code | `ValueError` |
| `impact_score` | Range [-1.0, 1.0] | `ValueError` |
| `date` (events) | ISO 8601 format | `ValueError` |

#### 6.2.12.2 Validation Flow

```mermaid
flowchart LR
    subgraph ValidationFlow[Domain Model Validation]
        Input([Input Data]) --> TypeCheck{Type<br/>Valid?}
        TypeCheck -->|No| TypeError([TypeError])
        TypeCheck -->|Yes| RangeCheck{Range<br/>Valid?}
        RangeCheck -->|No| ValueError([ValueError])
        RangeCheck -->|Yes| FormatCheck{Format<br/>Valid?}
        FormatCheck -->|No| FormatError([ValueError])
        FormatCheck -->|Yes| CreateModel([Create<br/>Domain Object])
    end
```

---

### 6.2.13 Environment Configuration

#### 6.2.13.1 Database Environment Variables

| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `DATABASE_URL` | SQLite authentication database | `sqlite:///auth.db` |
| `ASSET_GRAPH_DATABASE_URL` | SQLAlchemy ORM connection | `postgresql://user:pass@host/db` |
| `GRAPH_CACHE_PATH` | Graph cache file location | `/data/graph_cache.json` |
| `REAL_DATA_CACHE_PATH` | Yahoo Finance cache location | `/data/real_data.json` |
| `USE_REAL_DATA_FETCHER` | Enable live data fetching | `true` or `false` |

#### 6.2.13.2 Security Environment Variables

| Variable | Purpose | Sensitivity |
|----------|---------|-------------|
| `SECRET_KEY` | JWT signing key | Critical - never commit |
| `ADMIN_USERNAME` | Default admin user | Sensitive |
| `ADMIN_PASSWORD` | Default admin password | Critical - never commit |
| `ADMIN_EMAIL` | Admin email address | Low |
| `ADMIN_FULL_NAME` | Admin display name | Low |
| `ADMIN_DISABLED` | Admin disabled flag | Low |

---

### 6.2.14 Future Database Enhancements

#### 6.2.14.1 Planned Improvements

| Enhancement | Priority | Complexity | Impact |
|-------------|----------|------------|--------|
| PostgreSQL full support | High | Medium | Production readiness |
| Connection pooling | Medium | Low | Improved concurrency |
| Read replicas | Low | High | Horizontal scaling |
| Partitioning by asset class | Low | Medium | Query performance |

#### 6.2.14.2 Migration Path to Microservices

| Current Component | Future Service | Database Change |
|-------------------|----------------|-----------------|
| In-memory graph | Graph Service | PostgreSQL + Redis cache |
| SQLite auth | Auth Service | Dedicated auth database |
| JSON cache | Cache Service | Redis/Memcached |
| Repository layer | Data Service | Dedicated asset database |

---

### 6.2.15 References

#### 6.2.15.1 Source Files

| Path | Description |
|------|-------------|
| `migrations/001_initial.sql` | DDL schema definitions |
| `api/database.py` | SQLite authentication helpers |
| `api/auth.py` | JWT authentication and user management |
| `api/main.py` | FastAPI application with graph lifecycle |
| `src/data/database.py` | SQLAlchemy engine configuration |
| `src/data/db_models.py` | ORM model definitions |
| `src/data/repository.py` | Repository pattern implementation |
| `src/data/real_data_fetcher.py` | Yahoo Finance caching with atomic writes |
| `src/data/sample_data.py` | Sample database creation |
| `src/logic/asset_graph.py` | In-memory graph structure |
| `src/models/financial_models.py` | Domain model validation |
| `requirements.txt` | Database dependency declarations |

#### 6.2.15.2 Technical Specification Sections

| Section | Relevance |
|---------|-----------|
| 5.6 DATABASE SCHEMA | Core schema definitions |
| 3.6 Databases & Storage | Technology stack details |
| 4.10 Transaction Boundaries and Persistence | Transaction patterns |
| 3.8 Security Considerations | Authentication security |
| 5.4 CROSS-CUTTING CONCERNS | Error handling and monitoring |
| 5.5 DEPLOYMENT ARCHITECTURE | Deployment configurations |
| 6.1 Core Services Architecture | Monolithic architecture context |
| 2.6 Assumptions and Constraints | System limitations |

#### 6.2.15.3 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| SQLAlchemy | >=2.0.0 | ORM framework |
| passlib | (bundled) | Password hashing |
| PyJWT | (bundled) | JWT token handling |
| sqlite3 | (stdlib) | Authentication database |

## 6.3 Integration Architecture

The Financial Asset Relationship Database implements a **REST/JSON API integration architecture** designed for seamless communication between frontend clients, backend services, and external data sources. While the system follows a monolithic layered design (as documented in Section 6.1), it exposes well-defined integration points that enable frontend applications, external data providers, and AI tool integrations to interact with the core graph engine.

### 6.3.1 API DESIGN

#### 6.3.1.1 Protocol Specifications

The system implements RESTful API communication using modern web standards and type-safe serialization patterns.

| Aspect | Specification | Implementation |
|--------|---------------|----------------|
| Protocol | REST over HTTP/HTTPS | HTTP for development, HTTPS for production |
| Data Format | JSON | Content-Type: application/json |
| API Framework | FastAPI 0.127.0 | Automatic OpenAPI documentation |
| ASGI Server | Uvicorn ≥0.24.0 | Async request handling |
| Serialization | Pydantic 2.12.5 | Strict type validation |

```mermaid
flowchart TB
    subgraph ProtocolStack[Protocol Stack Architecture]
        Client([API Client]) --> HTTPS[HTTPS/TLS Layer]
        HTTPS --> ASGI[Uvicorn ASGI Server]
        ASGI --> Middleware[FastAPI Middleware Stack]

        subgraph MiddlewareChain[Middleware Processing]
            CORS[CORS Middleware]
            RateLimit[Rate Limiter]
            Auth[Auth Middleware]
            CORS --> RateLimit
            RateLimit --> Auth
        end

        Middleware --> MiddlewareChain
        Auth --> Router[FastAPI Router]
        Router --> Pydantic[Pydantic Validation]
        Pydantic --> Handler[Endpoint Handler]
        Handler --> Graph[Graph Engine]
    end
```

#### API Endpoint Catalog

| Endpoint | Method | Description | Auth | Rate Limit |
|----------|--------|-------------|------|------------|
| `/` | GET | API metadata | No | None |
| `/token` | POST | JWT issuance | No | 5/min |
| `/api/health` | GET | Health check | No | None |
| `/api/assets` | GET | List assets | No | None |
| `/api/assets/{id}` | GET | Asset details | No | None |
| `/api/assets/{id}/relationships` | GET | Asset relationships | No | None |
| `/api/relationships` | GET | All relationships | No | None |
| `/api/metrics` | GET | Network stats | No | None |
| `/api/visualization` | GET | 3D visualization | No | None |
| `/api/asset-classes` | GET | Asset classes | No | None |
| `/api/sectors` | GET | Sectors | No | None |
| `/api/users/me` | GET | Current user | Yes | 10/min |

#### 6.3.1.2 Authentication Methods

The system implements JWT-based authentication with secure password hashing for credential validation.

| Component | Implementation | Configuration |
|-----------|----------------|---------------|
| Token Type | JWT (JSON Web Token) | OAuth2 Bearer scheme |
| Algorithm | HS256 (HMAC-SHA256) | PyJWT ≥2.8.0 |
| Token Expiration | 30 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Secret Key | Environment variable | `SECRET_KEY` (required) |
| Password Hashing | pbkdf2_sha256 | passlib CryptContext |
| Credential Storage | SQLite database | `user_credentials` table |

```mermaid
sequenceDiagram
    participant Client as API Client
    participant RateLimiter as Rate Limiter
    participant Auth as Auth Module
    participant UserRepo as User Repository
    participant JWT as JWT Library

    Client->>RateLimiter: POST /token (credentials)
    RateLimiter->>RateLimiter: Check 5/min limit

    alt Rate Limit OK
        RateLimiter->>Auth: Process Login
        Auth->>UserRepo: get_user(username)
        UserRepo-->>Auth: User or None

        alt User Found
            Auth->>Auth: verify_password(plain, hashed)

            alt Password Valid
                Auth->>JWT: encode(payload, SECRET_KEY, HS256)
                JWT-->>Auth: Access Token
                Auth-->>Client: {"access_token": "...", "token_type": "bearer"}
            else Password Invalid
                Auth-->>Client: 401 Incorrect username or password
            end
        else User Not Found
            Auth-->>Client: 401 Incorrect username or password
        end
    else Rate Limit Exceeded
        RateLimiter-->>Client: 429 Too Many Requests
    end
```

#### 6.3.1.3 Authorization Framework

Protected endpoint validation follows a five-step verification process ensuring token integrity and user status.

| Step | Action | Failure Response |
|------|--------|------------------|
| 1 | Extract Bearer token from header | 401 Not authenticated |
| 2 | Decode JWT with SECRET_KEY | 401 Could not validate |
| 3 | Check token expiration | 401 Token has expired |
| 4 | Lookup user in repository | 401 Invalid credentials |
| 5 | Verify user is active | 400 Inactive user |

```mermaid
flowchart TB
    subgraph Authorization[Authorization Validation Flow]
        Request([Protected Request]) --> ExtractToken{Bearer Token<br/>Present?}
        ExtractToken -->|No| Return401A[401 Not Authenticated]
        ExtractToken -->|Yes| DecodeJWT{Decode JWT<br/>Valid?}
        DecodeJWT -->|No| Return401B[401 Could Not Validate]
        DecodeJWT -->|Yes| CheckExpiry{Token<br/>Expired?}
        CheckExpiry -->|Yes| Return401C[401 Token Expired]
        CheckExpiry -->|No| LookupUser{User<br/>Exists?}
        LookupUser -->|No| Return401D[401 Invalid Credentials]
        LookupUser -->|Yes| CheckActive{User<br/>Active?}
        CheckActive -->|No| Return400[400 Inactive User]
        CheckActive -->|Yes| Authorized([Access Granted])
    end
```

#### 6.3.1.4 Rate Limiting Strategy

The system implements endpoint-specific rate limiting using slowapi with client IP-based tracking.

| Endpoint | Limit | Window | Key Function |
|----------|-------|--------|--------------|
| `POST /token` | 5 requests | 1 minute | Client IP |
| `GET /api/users/me` | 10 requests | 1 minute | Client IP |
| Other endpoints | Unlimited | N/A | N/A |

**Implementation Details:**
- **Library**: slowapi with `get_remote_address` key function
- **Exception Handling**: `RateLimitExceeded` → custom handler returning HTTP 429
- **Response Headers**: Includes `Retry-After` header indicating wait time

#### 6.3.1.5 CORS Configuration

Cross-Origin Resource Sharing is configured based on deployment environment with strict origin validation.

| Environment | Allowed Origins | Configuration |
|-------------|-----------------|---------------|
| Development | `http://localhost:3000`, `http://localhost:7860` | Hardcoded |
| Production | HTTPS origins only | Environment variable |
| Custom | Comma-separated list | `ALLOWED_ORIGINS` |

**CORS Validation Rules:**
- HTTP localhost allowed only in development mode
- HTTPS localhost allowed in any environment
- Vercel preview URLs validated via regex: `^https://[a-zA-Z0-9\-\.]+\.vercel\.app$`
- Wildcard (`*`) origins prohibited when authentication headers are used

#### 6.3.1.6 Versioning Approach

| Aspect | Current Implementation |
|--------|----------------------|
| API Version | 1.0.0 |
| Version Exposure | Root endpoint metadata |
| URL Versioning | Not implemented (single version) |
| Future Path | URL-based versioning (e.g., `/v2/`) when needed |

#### 6.3.1.7 Documentation Standards

The API implements comprehensive documentation through multiple mechanisms:

| Standard | Implementation |
|----------|----------------|
| OpenAPI/Swagger | Auto-generated by FastAPI from type annotations |
| Interactive Docs | Available at `/docs` (Swagger UI) and `/redoc` (ReDoc) |
| Docstrings | Comprehensive Python docstrings on all endpoints |
| Type Annotations | Pydantic models for request/response schemas |
| Response Examples | Included in OpenAPI specification |

---

### 6.3.2 MESSAGE PROCESSING

#### 6.3.2.1 Event Processing Patterns

The system implements lifecycle event handling through FastAPI's lifespan context manager pattern.

#### Application Lifecycle Events

```mermaid
flowchart TB
    subgraph LifecycleEvents[Application Lifecycle Events]
        Startup([Application Start]) --> InitGraph[Initialize Graph Engine]
        InitGraph --> LoadCache{Cache<br/>Available?}
        LoadCache -->|Yes| UseCache[Load from JSON Cache]
        LoadCache -->|No| FetchData[Fetch from Data Source]
        UseCache --> GraphReady[Graph Ready]
        FetchData --> BuildRelations[Build Relationships]
        BuildRelations --> GraphReady
        GraphReady --> LogStartup[Log Startup Complete]
        LogStartup --> Ready([Accept Requests])

        Ready --> Shutdown([Shutdown Signal])
        Shutdown --> LogShutdown[Log Shutdown]
        LogShutdown --> Exit([Application Exit])
    end
```

| Event | Trigger | Action | Purpose |
|-------|---------|--------|---------|
| Startup | Application launch | Initialize graph singleton | Pre-warm graph data |
| Request | HTTP request | Thread-safe graph access | Serve API requests |
| Shutdown | SIGTERM/SIGINT | Log shutdown event | Graceful termination |

#### 6.3.2.2 Batch Processing Flows

The real data fetching system implements batch processing for market data acquisition from Yahoo Finance.

```mermaid
sequenceDiagram
    participant App as Application
    participant Fetcher as RealDataFetcher
    participant Cache as File Cache
    participant YF as Yahoo Finance
    participant Graph as Graph Engine

    App->>Fetcher: create_real_database()
    Fetcher->>Cache: Check cache file

    alt Cache Exists
        Cache-->>Fetcher: Cached JSON
        Fetcher->>Graph: Load from cache
        Graph-->>App: Cached Graph
    else No Cache
        Fetcher->>YF: Download AAPL, MSFT, XOM, JPM
        YF-->>Fetcher: Equity Data
        Fetcher->>YF: Download TLT, LQD, HYG
        YF-->>Fetcher: Bond ETF Data
        Fetcher->>YF: Download GC=F, CL=F, SI=F
        YF-->>Fetcher: Commodity Data
        Fetcher->>YF: Download EURUSD=X, GBPUSD=X, JPYUSD=X
        YF-->>Fetcher: Currency Data

        Fetcher->>Graph: add_asset() × N
        Fetcher->>Graph: add_regulatory_event() × N
        Fetcher->>Graph: build_relationships()

        Fetcher->>Cache: Write temp file
        Cache->>Cache: Atomic rename
        Cache-->>Fetcher: Cache saved

        Graph-->>App: Fresh Graph
    end
```

#### Batch Processing Sequence

| Step | Operation | Fallback Behavior |
|------|-----------|-------------------|
| 1 | Check cache file | Proceed if missing |
| 2 | Fetch equities (AAPL, MSFT, XOM, JPM) | Skip on error |
| 3 | Fetch bond ETFs (TLT, LQD, HYG) | Skip on error |
| 4 | Fetch commodities (GC=F, CL=F, SI=F) | Skip on error |
| 5 | Fetch currencies (EURUSD=X, etc.) | Skip on error |
| 6 | Build relationships | Process available data |
| 7 | Atomic cache write | Log error, continue |

#### 6.3.2.3 Error Handling Strategy

The API implements comprehensive error categorization with appropriate HTTP status codes and recovery guidance.

#### API Error Categories

| Status Code | Scenario | Response Detail |
|-------------|----------|-----------------|
| 400 | Bad Request | Inactive user, invalid input |
| 401 | Unauthorized | Invalid/expired token, missing credentials |
| 404 | Not Found | Asset/resource not found |
| 422 | Validation Error | Pydantic validation failure with field details |
| 429 | Too Many Requests | Rate limit exceeded with Retry-After header |
| 500 | Internal Error | Unexpected exception (logged server-side) |

```mermaid
flowchart TB
    subgraph ErrorHandling[Error Handling Architecture]
        Error([Error Occurs]) --> ErrorType{Error Type}

        ErrorType -->|HTTPException| HTTPHandle[Return HTTP Status]
        HTTPHandle --> Status401{401?}
        Status401 -->|Yes| AddWWW[Add WWW-Authenticate Header]
        Status401 -->|No| ReturnDetail[Return Error Detail]
        AddWWW --> ReturnDetail

        ErrorType -->|Rate Limit| RateHandle[429 + Retry-After]

        ErrorType -->|Validation| ValHandle[422 + Pydantic Details]

        ErrorType -->|Unexpected| UnexpHandle[Log Exception]
        UnexpHandle --> Return500[500 Internal Error]

        ReturnDetail --> Done([Response Sent])
        RateHandle --> Done
        ValHandle --> Done
        Return500 --> Done
    end
```

#### Graph Initialization Error Recovery

| Error Source | Detection | Recovery Action | Fallback |
|--------------|-----------|-----------------|----------|
| Cache load failed | JSON parse error | Proceed to fresh fetch | Standard init |
| Network disabled | Configuration flag | Use sample data | Offline mode |
| Yahoo Finance error | Request exception | Check partial data | Sample fallback |
| Critical failure | Unrecoverable exception | Abort startup | Application exit |

---

### 6.3.3 EXTERNAL SYSTEMS

#### 6.3.3.1 Third-Party Integration Patterns

#### Yahoo Finance Integration

The system integrates with Yahoo Finance via the yfinance library for real-time market data.

| Attribute | Specification |
|-----------|---------------|
| Library | yfinance ≥0.2.51 |
| Enable Flag | `USE_REAL_DATA_FETCHER` environment variable |
| Implementation | `src/data/real_data_fetcher.py` |
| Data Source | Yahoo Finance API (via yfinance) |

**Supported Financial Instruments:**

| Category | Symbols |
|----------|---------|
| Equities | AAPL, MSFT, XOM, JPM |
| Bond ETFs | TLT, LQD, HYG |
| Commodities | GC=F (Gold), CL=F (Crude Oil), SI=F (Silver) |
| Currencies | EURUSD=X, GBPUSD=X, JPYUSD=X |

**Rate Limit Mitigation:**

| Strategy | Implementation |
|----------|----------------|
| File Caching | JSON cache with atomic writes via `NamedTemporaryFile` + `os.replace` |
| Cache Path | Configurable via `REAL_DATA_CACHE_PATH` environment variable |
| Fallback | Sample data when network disabled or unavailable |
| Atomic Writes | Prevents cache corruption on write failures |

```mermaid
flowchart TB
    subgraph YahooFinanceIntegration[Yahoo Finance Integration Pattern]
        Request([Data Request]) --> CheckEnabled{Real Data<br/>Enabled?}
        CheckEnabled -->|No| UseSample[Use Sample Data]
        CheckEnabled -->|Yes| CheckCache{Cache<br/>Valid?}
        CheckCache -->|Yes| LoadCache[Load from Cache]
        CheckCache -->|No| FetchAPI[Fetch from Yahoo Finance]

        FetchAPI --> HandleResponse{Response<br/>OK?}
        HandleResponse -->|Yes| ProcessData[Process Market Data]
        HandleResponse -->|Partial| PartialData[Use Available Data]
        HandleResponse -->|No| FallbackSample[Fallback to Sample]

        ProcessData --> WriteCache[Write to Cache]
        WriteCache --> AtomicRename[Atomic File Rename]

        LoadCache --> ReturnData([Return Data])
        AtomicRename --> ReturnData
        PartialData --> ReturnData
        FallbackSample --> ReturnData
        UseSample --> ReturnData
    end
```

#### 6.3.3.2 MCP (Model Context Protocol) Integration

The system includes support for the Model Context Protocol, enabling AI tool integrations.

| Component | Implementation |
|-----------|----------------|
| Framework | FastMCP (`mcp>=1.0.0`, `fastmcp>=0.1.0`) |
| Server Name | "DashFin-Relationship-Manager" |
| Thread Safety | `_ThreadSafeGraph` proxy with `threading.Lock` |
| Entry Point | `mcp_server.py` |

**Exposed MCP Tools/Resources:**

| Tool/Resource | Type | Description |
|---------------|------|-------------|
| `add_equity_node()` | Tool | Add equity asset to graph |
| `graph://data/3d-layout` | Resource | 3D visualization data resource |

#### 6.3.3.3 Frontend-Backend Integration

The Next.js frontend communicates with the FastAPI backend through a typed API client layer.

| Aspect | Implementation |
|--------|----------------|
| HTTP Client | Axios |
| Base URL | `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`) |
| Content-Type | `application/json` |
| Location | `frontend/app/lib/api.ts` |

**API Client Methods:**

| Method | Endpoint | Return Type |
|--------|----------|-------------|
| `healthCheck()` | GET /api/health | Health status |
| `getAssets(params?)` | GET /api/assets | Asset[] or paginated |
| `getAssetDetail(id)` | GET /api/assets/{id} | Asset |
| `getAssetRelationships(id)` | GET /api/assets/{id}/relationships | Relationship[] |
| `getAllRelationships()` | GET /api/relationships | Relationship[] |
| `getMetrics()` | GET /api/metrics | Metrics |
| `getVisualizationData()` | GET /api/visualization | VisualizationData |
| `getAssetClasses()` | GET /api/asset-classes | { asset_classes: string[] } |
| `getSectors()` | GET /api/sectors | { sectors: string[] } |

```mermaid
sequenceDiagram
    participant User as User Browser
    participant NextJS as Next.js Frontend
    participant Axios as Axios Client
    participant CORS as CORS Middleware
    participant FastAPI as FastAPI Backend
    participant Graph as Graph Engine

    User->>NextJS: Navigate to Page
    NextJS->>Axios: api.getMetrics()
    Axios->>CORS: GET /api/metrics
    CORS->>CORS: Validate Origin

    alt Origin Valid
        CORS->>FastAPI: Forward Request
        FastAPI->>Graph: get_graph()
        Graph-->>FastAPI: Graph Instance
        FastAPI->>Graph: calculate_metrics()
        Graph-->>FastAPI: Metrics Data
        FastAPI-->>CORS: MetricsResponse
        CORS-->>Axios: 200 OK + CORS Headers
        Axios-->>NextJS: Response Data
        NextJS-->>User: Render Metrics
    else Origin Invalid
        CORS-->>Axios: 403 Forbidden
        Axios-->>NextJS: Error
        NextJS-->>User: Show Error Message
    end
```

#### 6.3.3.4 Database Connectivity

The system supports multiple database backends for authentication credential storage.

| Backend | Connection Handling | Use Case |
|---------|---------------------|----------|
| SQLite | Single connection for in-memory; file-based for persistence | Development, testing |
| PostgreSQL | psycopg2-binary with connection pooling | Production |
| In-Memory Testing | SQLAlchemy `StaticPool` for connection reuse | Unit tests |

**Authentication Database Schema:**

| Table | Field | Type | Constraint |
|-------|-------|------|------------|
| `user_credentials` | `username` | VARCHAR | UNIQUE, NOT NULL |
| `user_credentials` | `email` | VARCHAR | NULL |
| `user_credentials` | `full_name` | VARCHAR | NULL |
| `user_credentials` | `hashed_password` | VARCHAR | NOT NULL |
| `user_credentials` | `disabled` | BOOLEAN | DEFAULT FALSE |

#### 6.3.3.5 Deployment Platform Integration

#### Vercel Serverless Deployment

| Component | Builder | Configuration |
|-----------|---------|---------------|
| Backend | `@vercel/python` | maxLambdaSize: 50mb |
| Frontend | `@vercel/next` | Default Next.js settings |

**Route Configuration:**

| Pattern | Destination | Purpose |
|---------|-------------|---------|
| `/api/(.*)` | `api/main.py` | Backend API routes |
| `/(.*)` | `frontend/$1` | Frontend static/SSR |

#### Docker Container Deployment

| Setting | Value | Purpose |
|---------|-------|---------|
| Base Image | `python:3.11-slim` | Minimal Python runtime |
| Container User | `appuser` (UID 1000) | Non-root security |
| Exposed Port | 7860 | Gradio default |
| Health Check | HTTP probe every 30s | Container health |
| Restart Policy | unless-stopped | Automatic recovery |

```mermaid
flowchart TB
    subgraph DeploymentArchitecture[Deployment Platform Integration]
        subgraph LocalDev[Local Development]
            LocalFE[Next.js<br/>:3000]
            LocalAPI[FastAPI<br/>:8000]
            LocalGradio[Gradio<br/>:7860]
        end

        subgraph DockerDeploy[Docker Deployment]
            DockerApp[Single Container<br/>:7860]
            DockerVol[(Mounted Volumes)]
            DockerApp --> DockerVol
        end

        subgraph VercelDeploy[Vercel Serverless]
            VercelEdge[Edge Network]
            VercelLambda[Python Lambda]
            VercelNext[Next.js SSR]
            VercelEdge --> VercelLambda
            VercelEdge --> VercelNext
        end
    end

    Users([End Users]) --> LocalDev
    Users --> DockerDeploy
    Users --> VercelDeploy
```

---

### 6.3.4 TYPE CONTRACTS

#### 6.3.4.1 Backend Response Models

The API uses Pydantic models for type-safe request/response serialization.

#### AssetResponse Model

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `id` | `str` | Yes | - |
| `symbol` | `str` | Yes | - |
| `name` | `str` | Yes | - |
| `asset_class` | `str` | Yes | - |
| `sector` | `str` | Yes | - |
| `price` | `float` | Yes | - |
| `market_cap` | `Optional[float]` | No | `None` |
| `currency` | `str` | No | `"USD"` |
| `additional_fields` | `Dict[str, Any]` | No | `{}` |

#### RelationshipResponse Model

| Field | Type | Required |
|-------|------|----------|
| `source_id` | `str` | Yes |
| `target_id` | `str` | Yes |
| `relationship_type` | `str` | Yes |
| `strength` | `float` | Yes |

#### MetricsResponse Model

| Field | Type | Required |
|-------|------|----------|
| `total_assets` | `int` | Yes |
| `total_relationships` | `int` | Yes |
| `asset_classes` | `Dict[str, int]` | Yes |
| `avg_degree` | `float` | Yes |
| `max_degree` | `int` | Yes |
| `network_density` | `float` | Yes |
| `relationship_density` | `float` | No (default: 0.0) |

#### 6.3.4.2 Frontend Type Definitions

TypeScript interfaces defined in `frontend/app/types/api.ts` provide compile-time type safety.

| Interface | Purpose |
|-----------|---------|
| `Asset` | Asset data structure |
| `Relationship` | Relationship data structure |
| `Metrics` | Network metrics |
| `VisualizationNode` | 3D visualization node |
| `VisualizationEdge` | 3D visualization edge |
| `VisualizationData` | Complete visualization payload |

---

### 6.3.5 INTEGRATION FLOW DIAGRAMS

#### 6.3.5.1 Complete API Request Lifecycle

```mermaid
flowchart TB
    subgraph IntegrationFlow[Complete API Request Lifecycle]
        Client([Client Request]) --> TLS[TLS Termination]
        TLS --> Load[Load Balancer]
        Load --> ASGI[Uvicorn ASGI]
        ASGI --> CORS[CORS Validation]

        CORS --> CORSCheck{Origin<br/>Valid?}
        CORSCheck -->|No| Reject403[403 Forbidden]
        CORSCheck -->|Yes| RateLimit[Rate Limit Check]

        RateLimit --> RateLimitCheck{Within<br/>Limit?}
        RateLimitCheck -->|No| Reject429[429 Too Many]
        RateLimitCheck -->|Yes| AuthCheck{Auth<br/>Required?}

        AuthCheck -->|Yes| ValidateJWT[Validate JWT]
        ValidateJWT --> JWTValid{Token<br/>Valid?}
        JWTValid -->|No| Reject401[401 Unauthorized]
        JWTValid -->|Yes| Process[Process Request]

        AuthCheck -->|No| Process

        Process --> Validate[Pydantic Validation]
        Validate --> ValidationOK{Valid<br/>Input?}
        ValidationOK -->|No| Reject422[422 Validation Error]
        ValidationOK -->|Yes| Handler[Endpoint Handler]

        Handler --> Graph[Graph Engine]
        Graph --> Serialize[Serialize Response]
        Serialize --> AddHeaders[Add Response Headers]
        AddHeaders --> Response([JSON Response])

        Reject403 --> ErrorResponse([Error Response])
        Reject429 --> ErrorResponse
        Reject401 --> ErrorResponse
        Reject422 --> ErrorResponse
    end
```

#### 6.3.5.2 Visualization Data Pipeline

```mermaid
sequenceDiagram
    participant User as User
    participant UI as UI Component
    participant API as API Layer
    participant Graph as Graph Engine
    participant Viz as Visualization Module
    participant Plotly as Plotly Renderer

    User->>UI: Request 3D Visualization
    UI->>API: GET /api/visualization
    API->>Graph: get_graph()
    Graph-->>API: Graph Instance
    API->>Viz: get_3d_visualization_data_enhanced()
    Viz->>Viz: Set seed(42)
    Viz->>Viz: Calculate 3D positions
    Viz->>Viz: Assign colors by asset class
    Viz->>Viz: Generate hover text
    Viz-->>API: (positions, ids, colors, hovers)
    API->>API: Build nodes array
    API->>API: Build edges array
    API-->>UI: VisualizationDataResponse
    UI->>Plotly: Render 3D scatter
    Plotly-->>User: Interactive 3D Graph
```

#### 6.3.5.3 Thread-Safe Singleton Pattern

```mermaid
flowchart TB
    subgraph SingletonAccess[Thread-Safe Graph Singleton Access]
        APIRequest([API Request]) --> CheckGlobal{Global graph<br/>exists?}
        CheckGlobal -->|Yes| ReturnGraph([Return Graph])
        CheckGlobal -->|No| AcquireLock[Acquire Thread Lock]
        AcquireLock --> DoubleCheck{Double-check<br/>inside lock}
        DoubleCheck -->|Created| Release1[Release Lock]
        Release1 --> ReturnGraph
        DoubleCheck -->|Still None| InitGraph[Initialize New Graph]
        InitGraph --> SetGlobal[Set Global Reference]
        SetGlobal --> Release2[Release Lock]
        Release2 --> ReturnNew[Return New Graph]
        ReturnNew --> ReturnGraph
    end
```

---

### 6.3.6 ENVIRONMENT CONFIGURATION

Integration behavior is controlled through environment variables that configure connectivity, security, and feature flags.

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | Frontend API base URL | `http://localhost:8000` |
| `ALLOWED_ORIGINS` | CORS allowed origins | (none - uses defaults) |
| `SECRET_KEY` | JWT signing key | **Required** |
| `DATABASE_URL` | SQLite connection string | **Required** |
| `USE_REAL_DATA_FETCHER` | Enable Yahoo Finance | `false` |
| `REAL_DATA_CACHE_PATH` | Cache file path | (none) |
| `GRAPH_CACHE_PATH` | Graph cache path | (none) |
| `ADMIN_USERNAME` | Admin user credential | (none) |
| `ADMIN_PASSWORD` | Admin user credential | (none) |
| `ENV` | Environment mode | `development` |

---

### 6.3.7 PERFORMANCE TARGETS

The integration architecture is designed to meet specific service level objectives.

| Operation | Target SLA | Measurement |
|-----------|-----------|-------------|
| API Response (p95) | < 500ms | Request to response |
| Visualization Rendering | < 2 seconds | Data load to interactive |
| Token Generation | < 100ms | Credential to token |
| Graph Initialization | < 3 seconds | Application startup |
| Relationship Discovery | < 500ms | For 100 assets |
| Initial Page Load | < 3 seconds | Navigation to interactive |

#### Timeout Configuration

| Component | Timeout | Purpose |
|-----------|---------|---------|
| JWT Token | 30 minutes | Session expiration |
| Rate Limit Window | 1 minute | Request counting period |
| HTTP Client | 30 seconds | API request timeout |
| Health Check | 30 seconds | Container probe interval |

---

### 6.3.8 EXTERNAL DEPENDENCIES

#### 6.3.8.1 Runtime Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.127.0 | REST framework |
| Uvicorn | ≥0.24.0 | ASGI server |
| Pydantic | 2.12.5 | Validation |
| PyJWT | ≥2.8.0 | Token handling |
| passlib | Latest | Password hashing |
| slowapi | Latest | Rate limiting |
| yfinance | ≥0.2.51 | Market data |
| SQLAlchemy | ≥2.0.0 | Database ORM |

#### 6.3.8.2 Frontend Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Next.js | 14.2.35 | React framework |
| React | 18.2.0 | UI library |
| TypeScript | ^5.3.0 | Type safety |
| Axios | Latest | HTTP client |
| Plotly.js | ^2.27.0 | Visualization |
| Tailwind CSS | Latest | Styling |

---

### 6.3.9 References

#### Files Examined

| Path | Relevance |
|------|-----------|
| `api/main.py` | FastAPI application, endpoints, CORS, rate limiting, graph lifecycle |
| `api/auth.py` | JWT authentication, password hashing, user repository |
| `api/database.py` | SQLite integration, connection management |
| `src/data/real_data_fetcher.py` | Yahoo Finance integration, caching strategy |
| `frontend/app/lib/api.ts` | Frontend HTTP client implementation |
| `frontend/app/types/api.ts` | TypeScript type definitions |
| `vercel.json` | Serverless deployment configuration |
| `docker-compose.yml` | Docker container orchestration |
| `Dockerfile` | Container build specification |
| `mcp_server.py` | Model Context Protocol server |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable templates |

#### Folders Explored

| Folder Path | Contents |
|-------------|----------|
| `api/` | FastAPI backend modules |
| `frontend/` | Next.js application |
| `frontend/app/lib/` | API client layer |
| `frontend/app/types/` | TypeScript contracts |
| `src/` | Python core packages |
| `src/data/` | Data layer modules |

#### Technical Specification Sections Referenced

| Section | Topic |
|---------|-------|
| 3.1 Technology Stack Overview | Stack architecture and technology choices |
| 3.5 Third-Party Services | External service integrations |
| 3.8 Security Considerations | Authentication and API security |
| 3.9 Integration Requirements | Frontend-backend communication |
| 4.3 API Request Workflows | API workflow diagrams |
| 4.5 Error Handling Workflows | Error recovery flows |
| 4.6 Integration Sequence Diagrams | Integration flow diagrams |
| 5.2 COMPONENT DETAILS | Component specifications |
| 5.4 CROSS-CUTTING CONCERNS | Cross-cutting concerns |
| 5.5 DEPLOYMENT ARCHITECTURE | Deployment options |
| 6.1 Core Services Architecture | Monolithic architecture overview |

## 6.4 Security Architecture

### 6.4.1 Security Architecture Overview

#### 6.4.1.1 Executive Security Summary

The Financial Asset Relationship Database implements a comprehensive, defense-in-depth security architecture designed to protect both user identities and financial asset data. The security model centers on JWT-based stateless authentication, environment-driven secrets management, multi-layered input validation, and proactive threat mitigation through rate limiting and CORS controls.

The architecture addresses security concerns across multiple domains:

| Security Domain | Implementation Approach | Primary Controls |
|-----------------|------------------------|------------------|
| Identity & Access | JWT with HS256 signing | Token-based authentication |
| Input Validation | Multi-layer validation | Pydantic models, domain validation |
| Transport Security | HTTPS enforcement | TLS termination at edge |
| Rate Protection | IP-based throttling | slowapi middleware |
| Origin Control | Allowlist validation | Environment-specific CORS |
| Container Security | Hardened runtime | Non-root execution |

#### 6.4.1.2 Security Zone Architecture

The system implements security zones with increasing trust levels from the external network to protected internal services:

```mermaid
flowchart TB
    subgraph ExternalZone[External Zone - Untrusted]
        Internet([Internet<br/>Clients])
        Vercel[Vercel Edge<br/>TLS Termination]
    end

    subgraph DMZ[DMZ - Semi-Trusted]
        LB[Load Balancer<br/>Rate Limiting]
        CORS[CORS<br/>Middleware]
    end

    subgraph ApplicationZone[Application Zone - Protected]
        Auth[Authentication<br/>Module]
        API[FastAPI<br/>Endpoints]
        RateLimit[Rate<br/>Limiter]
    end

    subgraph DataZone[Data Zone - Restricted]
        Graph[Graph<br/>Engine]
        SQLite[(SQLite<br/>Auth DB)]
        Cache[(JSON<br/>Cache)]
    end

    Internet --> Vercel
    Vercel --> LB
    LB --> CORS
    CORS --> RateLimit
    RateLimit --> Auth
    Auth --> API
    Auth --> SQLite
    API --> Graph
    Graph --> Cache
```

#### 6.4.1.3 Security Principles

| Principle | Implementation |
|-----------|----------------|
| Defense in Depth | Multiple validation layers (CORS → Rate Limit → Auth → Input Validation) |
| Least Privilege | Non-root container user, minimal API permissions |
| Fail Secure | Default-deny CORS policy, explicit token validation |
| Separation of Duties | Authentication separated from business logic |
| Audit Trail | Security event logging at multiple levels |

---

### 6.4.2 Authentication Framework

#### 6.4.2.1 Identity Management Architecture

The identity management system uses a SQLite-backed user repository with secure credential storage and JWT-based session management.

**Location**: `api/auth.py`, `api/database.py`

#### User Identity Model

| Field | Type | Purpose | Security Note |
|-------|------|---------|---------------|
| `username` | TEXT | Unique login identifier | Unique constraint enforced |
| `email` | TEXT | Contact information | Optional, nullable |
| `full_name` | TEXT | Display name | Optional, nullable |
| `hashed_password` | TEXT | pbkdf2_sha256 hash | Never stored in plaintext |
| `disabled` | INTEGER | Account status flag | Blocks authentication when true |

#### User Repository Pattern

The `UserRepository` class in `api/auth.py` provides secure user management:

| Method | Purpose | Security Control |
|--------|---------|------------------|
| `get_user(username)` | Retrieve user by username | Parameterized query protection |
| `has_users()` | Check for existing users | Used during admin seeding |
| `create_or_update_user()` | User CRUD operations | Password hashing enforced |

#### 6.4.2.2 Password Security

Password security is implemented using industry-standard cryptographic hashing with the `passlib` library.

| Aspect | Configuration | Source |
|--------|---------------|--------|
| Algorithm | `pbkdf2_sha256` | `passlib.context.CryptContext` |
| Hash Function | SHA-256 | NIST-approved |
| Salt | Automatic (per-hash) | Built-in to pbkdf2 |
| Iterations | passlib defaults | Configurable |

#### Password Handling Functions

| Function | Purpose | Security Behavior |
|----------|---------|-------------------|
| `get_password_hash(password)` | Hash plaintext password | Returns irreversible hash |
| `verify_password(plain, hashed)` | Validate credentials | Constant-time comparison |

#### 6.4.2.3 Token Handling (JWT)

The authentication system uses JSON Web Tokens (JWT) for stateless session management.

**JWT Configuration**:

| Setting | Value | Location |
|---------|-------|----------|
| Algorithm | HS256 (HMAC-SHA256) | `api/auth.py` line 23 |
| Expiration | 30 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Secret Key | Environment variable | `SECRET_KEY` (required) |

#### Token Lifecycle

```mermaid
sequenceDiagram
    participant Client as API Client
    participant Rate as Rate Limiter
    participant Auth as Auth Module
    participant Repo as User Repository
    participant JWT as JWT Library

    Client->>Rate: POST /token (credentials)
    Rate->>Rate: Check 5/min limit

    alt Within Rate Limit
        Rate->>Auth: Process Login Request
        Auth->>Repo: get_user(username)
        Repo-->>Auth: User Object or None

        alt User Found
            Auth->>Auth: verify_password()

            alt Password Valid
                Auth->>Auth: Check user.disabled

                alt User Active
                    Auth->>JWT: encode(payload, SECRET_KEY, HS256)
                    JWT-->>Auth: Access Token
                    Auth-->>Client: {"access_token": "...", "token_type": "bearer"}
                else User Disabled
                    Auth-->>Client: 400 Inactive user
                end
            else Password Invalid
                Auth-->>Client: 401 Incorrect username or password
            end
        else User Not Found
            Auth-->>Client: 401 Incorrect username or password
        end
    else Rate Limit Exceeded
        Rate-->>Client: 429 Too Many Requests
    end
```

#### Token Security Controls

| Control | Implementation | Mitigation |
|---------|----------------|------------|
| Algorithm Pinning | Explicit `algorithms=["HS256"]` in decode | Algorithm confusion attacks |
| Expiration Enforcement | `exp` claim validation | Session hijacking |
| Secret Key Requirement | `ValueError` if `SECRET_KEY` not set | Weak signing prevention |
| Bearer Token Standard | OAuth2PasswordBearer scheme | Standard compliance |

#### 6.4.2.4 Session Management

The system implements stateless session management through JWT tokens:

| Aspect | Implementation | Benefit |
|--------|----------------|---------|
| Session Storage | None (stateless) | No server-side session attacks |
| Token Transport | Bearer header | Standard OAuth2 pattern |
| Session Termination | Token expiration | Automatic timeout |
| Token Endpoint | `POST /token` | Form-based credentials |

#### 6.4.2.5 Admin Credential Seeding

Initial admin credentials are configured through environment variables for secure bootstrapping:

| Variable | Purpose | Required |
|----------|---------|----------|
| `ADMIN_USERNAME` | Initial admin login | Yes |
| `ADMIN_PASSWORD` | Initial admin password | Yes |
| `ADMIN_EMAIL` | Admin contact | No |
| `ADMIN_FULL_NAME` | Admin display name | No |
| `ADMIN_DISABLED` | Disable flag (default: false) | No |

**Security Enforcement**: The system raises a `ValueError` if no users exist after seeding, preventing operation without proper authentication configuration.

---

### 6.4.3 Authorization System

#### 6.4.3.1 Role-Based Access Control

The current implementation provides a simplified access control model with two user states:

| User State | Permissions | Enforcement |
|------------|-------------|-------------|
| Anonymous | Public API endpoints only | No token required |
| Authenticated Active | All API endpoints | Valid JWT + active flag |
| Authenticated Disabled | None | `400 Inactive user` returned |

#### 6.4.3.2 Protected Endpoint Validation Flow

The `get_current_user` dependency implements a multi-step validation pipeline:

```mermaid
flowchart TB
    subgraph ValidationPipeline[Protected Endpoint Validation]
        Request([Incoming<br/>Request]) --> ExtractToken{Extract Bearer<br/>Token from Header}

        ExtractToken -->|Missing| NoAuth[401: Not authenticated<br/>WWW-Authenticate: Bearer]
        ExtractToken -->|Present| DecodeJWT{Decode JWT with<br/>SECRET_KEY + HS256}

        DecodeJWT -->|Decode Error| InvalidToken[401: Could not<br/>validate credentials]
        DecodeJWT -->|Success| CheckExpiry{Check Token<br/>Expiration}

        CheckExpiry -->|Expired| ExpiredToken[401: Token<br/>has expired]
        CheckExpiry -->|Valid| ExtractSub{Extract username<br/>from 'sub' claim}

        ExtractSub -->|Missing| InvalidPayload[401: Could not<br/>validate credentials]
        ExtractSub -->|Present| LookupUser{Lookup User<br/>in Repository}

        LookupUser -->|Not Found| UserNotFound[401: Could not<br/>validate credentials]
        LookupUser -->|Found| CheckActive{User<br/>Active?}

        CheckActive -->|Disabled| InactiveUser[400: Inactive user]
        CheckActive -->|Active| Authorized([Request<br/>Authorized])

        NoAuth --> ErrorResponse([Error Response])
        InvalidToken --> ErrorResponse
        ExpiredToken --> ErrorResponse
        InvalidPayload --> ErrorResponse
        UserNotFound --> ErrorResponse
        InactiveUser --> ErrorResponse
    end
```

#### 6.4.3.3 Authorization Dependencies

| Dependency | Purpose | Returns |
|------------|---------|---------|
| `get_current_user` | Validates JWT and retrieves user | `UserInDB` object |
| `get_current_active_user` | Extends above with active check | Active `UserInDB` only |

#### 6.4.3.4 Endpoint Protection Matrix

| Endpoint | HTTP Method | Auth Required | Rate Limited | Description |
|----------|-------------|---------------|--------------|-------------|
| `/token` | POST | No | Yes (5/min) | JWT token issuance |
| `/api/users/me` | GET | Yes | Yes (10/min) | Current user info |
| `/api/assets` | GET | No | No | List assets |
| `/api/assets/{id}` | GET | No | No | Single asset details |
| `/api/metrics` | GET | No | No | Network statistics |
| `/api/visualization` | GET | No | No | 3D visualization data |
| `/api/health` | GET | No | No | Health check |

#### 6.4.3.5 Policy Enforcement Points

| Enforcement Point | Location | Control Type |
|-------------------|----------|--------------|
| Rate Limiting | `api/main.py` | Pre-authentication throttling |
| CORS Validation | `api/main.py` | Origin allowlist |
| Token Validation | `api/auth.py` | JWT signature verification |
| User State Check | `api/auth.py` | Active account enforcement |
| Input Validation | Pydantic models | Type/format enforcement |

---

### 6.4.4 Rate Limiting

#### 6.4.4.1 Rate Limiting Architecture

Rate limiting is implemented using the `slowapi` library with IP-based request tracking:

**Configuration Location**: `api/main.py` lines 156-169

| Component | Implementation |
|-----------|----------------|
| Library | `slowapi` |
| Key Function | `get_remote_address` |
| Exception Handler | `RateLimitExceeded` |

#### 6.4.4.2 Rate Limit Configuration

| Endpoint | Limit | Window | Rationale |
|----------|-------|--------|-----------|
| `POST /token` | 5 requests | 1 minute | Brute-force protection |
| `GET /api/users/me` | 10 requests | 1 minute | Authenticated endpoint protection |
| Other endpoints | Unlimited | N/A | Public data access |

#### 6.4.4.3 Rate Limit Response

When rate limits are exceeded:

| Response Element | Value |
|------------------|-------|
| HTTP Status | 429 Too Many Requests |
| Header | `Retry-After: <seconds>` |
| Body | Error message with limit details |

---

### 6.4.5 CORS Configuration

#### 6.4.5.1 CORS Security Model

Cross-Origin Resource Sharing (CORS) is implemented with environment-aware validation:

**Configuration Location**: `api/main.py` lines 226-302

#### 6.4.5.2 Origin Validation Rules

| Environment | HTTP localhost | HTTPS localhost | Vercel URLs | Custom HTTPS |
|-------------|----------------|-----------------|-------------|--------------|
| Development | ✅ Allowed | ✅ Allowed | ✅ Allowed | ✅ Allowed |
| Production | ❌ Rejected | ✅ Allowed | ✅ Allowed | ✅ Allowed |

#### 6.4.5.3 Vercel Preview Domain Validation

Preview deployments are validated using regex pattern matching:

| Pattern Component | Regex |
|-------------------|-------|
| Protocol | `^https://` |
| Subdomain | `[a-zA-Z0-9\-\.]+` |
| Domain | `\.vercel\.app$` |

#### 6.4.5.4 CORS Middleware Configuration

| Setting | Value | Security Note |
|---------|-------|---------------|
| `allow_origins` | Validated allowlist | No wildcard (`*`) |
| `allow_credentials` | `True` | Cookie support enabled |
| `allow_methods` | `["*"]` | All HTTP methods |
| `allow_headers` | `["*"]` | All headers allowed |

#### 6.4.5.5 Custom Origin Configuration

Custom origins can be added via the `ALLOWED_ORIGINS` environment variable:

| Format | Example |
|--------|---------|
| Comma-separated list | `https://app.example.com,https://staging.example.com` |

Origins are validated through `validate_origin()` before inclusion, with invalid origins logged as warnings and skipped.

---

### 6.4.6 Data Protection

#### 6.4.6.1 Database Security

**Location**: `api/database.py`

| Control | Implementation | Protection |
|---------|----------------|------------|
| Parameterized Queries | `WHERE username = ?` binding | SQL injection prevention |
| Thread-Safe Access | `threading.Lock` for shared connection | Race condition prevention |
| Connection Configuration | `check_same_thread=False` | Multi-threaded compatibility |

#### 6.4.6.2 Input Validation Layers

The system implements three layers of input validation:

```mermaid
flowchart TB
    subgraph ValidationLayers[Multi-Layer Input Validation]
        Input([External Input]) --> Layer1{Layer 1:<br/>API Validation}

        Layer1 -->|Pydantic Models| PydanticCheck[Type Enforcement<br/>Format Validation]
        PydanticCheck -->|Invalid| Reject422[422 Validation Error]
        PydanticCheck -->|Valid| Layer2{Layer 2:<br/>Domain Validation}

        Layer2 -->|Dataclass __post_init__| DomainCheck[Business Rule<br/>Validation]
        DomainCheck -->|Invalid| RejectValue[ValueError Exception]
        DomainCheck -->|Valid| Layer3{Layer 3:<br/>Database Constraints}

        Layer3 -->|SQLite/PostgreSQL| DBCheck[NOT NULL<br/>UNIQUE<br/>FOREIGN KEY]
        DBCheck -->|Invalid| RejectDB[Database Error]
        DBCheck -->|Valid| Success([Data Accepted])
    end
```

#### 6.4.6.3 Domain Model Validation Rules

| Field | Validation Rule | Error Type |
|-------|-----------------|------------|
| `id`, `symbol`, `name` | Non-empty string | `ValueError` |
| `price` | Non-negative float | `ValueError` |
| `market_cap` | Non-negative float (if present) | `ValueError` |
| `currency` | 3-character ISO code | `ValueError` |
| `impact_score` | Range [-1.0, 1.0] | `ValueError` |
| `date` | ISO 8601 format (YYYY-MM-DD) | `ValueError` |

#### 6.4.6.4 Encryption Standards

| Data Type | At Rest | In Transit |
|-----------|---------|------------|
| Passwords | pbkdf2_sha256 hash | HTTPS/TLS |
| JWT Tokens | N/A (ephemeral) | HTTPS/TLS |
| API Data | Unencrypted (SQLite) | HTTPS/TLS |
| Cache Files | Unencrypted (JSON) | N/A |

#### 6.4.6.5 Secure Communication

| Environment | Protocol | Implementation |
|-------------|----------|----------------|
| Development | HTTP allowed | Local testing |
| Production | HTTPS required | Vercel TLS termination |
| Container | HTTP internal | HTTPS at edge |

---

### 6.4.7 Secrets Management

#### 6.4.7.1 Required Environment Variables

| Variable | Purpose | Criticality |
|----------|---------|-------------|
| `SECRET_KEY` | JWT signing key | **Critical** - Application fails without |
| `DATABASE_URL` | SQLite connection string | **Critical** - Application fails without |
| `ADMIN_USERNAME` | Initial admin account | Required for user seeding |
| `ADMIN_PASSWORD` | Initial admin password | Required for user seeding |

#### 6.4.7.2 Optional Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ENV` | Environment mode | `development` |
| `ALLOWED_ORIGINS` | CORS allowlist | Empty (built-in defaults) |
| `ADMIN_EMAIL` | Admin email | None |
| `ADMIN_FULL_NAME` | Admin display name | None |
| `ADMIN_DISABLED` | Disable admin | `false` |

#### 6.4.7.3 Secrets Security Best Practices

| Practice | Implementation |
|----------|----------------|
| No committed secrets | `.env.example` provides template only |
| Runtime injection | Environment variables at deployment |
| Secret rotation | Manual SECRET_KEY rotation supported |
| Least privilege | Only required secrets loaded |

---

### 6.4.8 Container Security

#### 6.4.8.1 Docker Security Measures

**Location**: `Dockerfile`

| Security Measure | Implementation | Benefit |
|------------------|----------------|---------|
| Non-root User | `useradd -m -u 1000 appuser` | Privilege escalation prevention |
| Minimal Base Image | `python:3.11-slim` | Reduced attack surface |
| No Cache | `pip install --no-cache-dir` | No sensitive data in layers |
| Health Checks | `HEALTHCHECK` with 30s interval | Container orchestration support |
| No Bytecode | `PYTHONDONTWRITEBYTECODE=1` | Cleaner runtime |

#### 6.4.8.2 Container Security Flow

```mermaid
flowchart TB
    subgraph ContainerSecurity[Container Security Architecture]
        Build([Docker Build]) --> BaseImage[python:3.11-slim<br/>Minimal Base]
        BaseImage --> CreateUser[Create Non-Root User<br/>appuser UID 1000]
        CreateUser --> InstallDeps[Install Dependencies<br/>No Cache]
        InstallDeps --> CopyApp[Copy Application<br/>Code]
        CopyApp --> SetUser[Switch to<br/>appuser]
        SetUser --> HealthCheck[Configure<br/>Health Check]
        HealthCheck --> Runtime([Container Runtime])
    end
```

---

### 6.4.9 CI/CD Security Scanning

#### 6.4.9.1 Security Scanning Pipeline

The repository implements comprehensive security scanning through both CircleCI and GitHub Actions workflows:

#### CircleCI Security Pipeline

| Tool | Purpose | Stage |
|------|---------|-------|
| `safety check` | Python dependency vulnerabilities | Build |
| `bandit` | Python SAST analysis | Build |
| `pytest --cov` | Test coverage verification | Test |

#### GitHub Actions Security Workflows

| Workflow | Tool | Purpose |
|----------|------|---------|
| `bandit.yml` | Bandit | Python static security analysis |
| `codeql.yml` | CodeQL | Multi-language SAST |
| `semgrep.yml` | Semgrep | Pattern-based vulnerability detection |
| `trivy.yml` | Trivy | Container image scanning |
| `hadolint.yml` | Hadolint | Dockerfile best practices |
| `snyk-security.yml` | Snyk | Dependency vulnerability scanning |
| `snyk-container.yml` | Snyk | Container vulnerability scanning |
| `dependency-review.yml` | GitHub | PR dependency review |
| `scorecard.yml` | OSSF Scorecard | Supply chain security |
| `devskim.yml` | DevSkim | Security linting |

#### 6.4.9.2 SARIF Integration

Security scan results are integrated with GitHub Advanced Security:

| Configuration | Value |
|---------------|-------|
| Upload Action | `github/codeql-action/upload-sarif@v3` |
| Permission | `security-events: write` |
| Visibility | GitHub Security tab |

---

### 6.4.10 Error Handling Security

#### 6.4.10.1 Information Disclosure Controls

Error responses are designed to minimize information leakage:

| Status Code | Scenario | Information Disclosed |
|-------------|----------|----------------------|
| 400 | Bad Request | Generic "Inactive user" message |
| 401 | Unauthorized | Generic credential failure message |
| 404 | Not Found | Resource type and ID only |
| 422 | Validation Error | Pydantic field details |
| 429 | Rate Limited | Retry-After header only |
| 500 | Internal Error | Generic message (details logged internally) |

#### 6.4.10.2 Exception Handling Pattern

| Exception Type | Response Behavior | Internal Action |
|----------------|-------------------|-----------------|
| `HTTPException` | Re-raised directly | None |
| `RateLimitExceeded` | 429 with Retry-After | None |
| `ValidationError` | 422 with field details | None |
| Other exceptions | 500 generic message | `logger.exception()` |

---

### 6.4.11 Logging and Audit

#### 6.4.11.1 Logging Configuration

| Setting | Value |
|---------|-------|
| Level | `INFO` |
| Module | `logging.getLogger(__name__)` |
| Format | Python standard logging |

#### 6.4.11.2 Security Event Logging

| Event Category | Log Level | Content |
|----------------|-----------|---------|
| Graph initialization | INFO | Success/failure status |
| Application startup | INFO | Server binding, port |
| Authentication failures | WARNING | Failed login attempts |
| Invalid CORS origins | WARNING | Skipped origin value |
| Request errors | ERROR | Exception details |
| Cache operations | INFO | Load/save success |

---

### 6.4.12 Compliance Controls

#### 6.4.12.1 Security Control Matrix

| Control Category | Control | Status | Evidence |
|------------------|---------|--------|----------|
| **Access Control** | JWT Authentication | ✅ Implemented | `api/auth.py` |
| | Token Expiration | ✅ Implemented | 30-minute default |
| | Rate Limiting | ✅ Implemented | slowapi integration |
| **Data Protection** | Password Hashing | ✅ Implemented | pbkdf2_sha256 |
| | HTTPS Enforcement | ✅ Production | Vercel TLS |
| | Input Validation | ✅ Implemented | Multi-layer validation |
| **Audit** | Authentication Logging | ✅ Implemented | WARNING level |
| | Error Logging | ✅ Implemented | ERROR level |
| **Infrastructure** | Container Hardening | ✅ Implemented | Non-root user |
| | Dependency Scanning | ✅ Implemented | CI/CD pipelines |
| | Secret Management | ✅ Implemented | Environment variables |

#### 6.4.12.2 Security Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `PyJWT` | >=2.8.0 | JWT authentication |
| `passlib[bcrypt]` | >=1.7.4 | Password hashing |
| `slowapi` | >=0.1.4 | Rate limiting |
| `urllib3` | >=2.6.0 | Snyk security pin |
| `zipp` | >=3.19.1 | Snyk security pin |

#### 6.4.12.3 Compliance Recommendations

| Requirement | Current Status | Recommendation |
|-------------|----------------|----------------|
| Data Encryption at Rest | Not implemented | Consider SQLCipher for SQLite |
| Multi-Factor Authentication | Not implemented | Add TOTP support for admin |
| Audit Log Persistence | In-memory only | Add persistent audit logging |
| Session Revocation | Token-based expiry only | Implement token blacklist |
| Key Rotation | Manual only | Implement automated rotation |

---

### 6.4.13 Security Architecture Summary Diagram

```mermaid
flowchart TB
    subgraph SecurityArchitecture[Complete Security Architecture]
        subgraph ExternalLayer[External Security Layer]
            TLS[TLS/HTTPS<br/>Termination]
            EdgeCORS[CORS<br/>Validation]
        end

        subgraph ApplicationSecurity[Application Security Layer]
            RateLimit[Rate<br/>Limiting]
            JWTAuth[JWT<br/>Authentication]
            InputVal[Input<br/>Validation]
        end

        subgraph DataSecurity[Data Security Layer]
            PassHash[Password<br/>Hashing]
            ParamQuery[Parameterized<br/>Queries]
            SecretMgmt[Secrets<br/>Management]
        end

        subgraph InfrastructureSecurity[Infrastructure Security]
            Container[Container<br/>Hardening]
            CICD[CI/CD<br/>Scanning]
            AuditLog[Audit<br/>Logging]
        end
    end

    Client([Client]) --> TLS
    TLS --> EdgeCORS
    EdgeCORS --> RateLimit
    RateLimit --> JWTAuth
    JWTAuth --> InputVal
    InputVal --> PassHash
    PassHash --> ParamQuery
    ParamQuery --> SecretMgmt

    Container -.-> ApplicationSecurity
    CICD -.-> DataSecurity
    AuditLog -.-> ApplicationSecurity
```

---

### 6.4.14 References

#### 6.4.14.1 Source Files

| Path | Description |
|------|-------------|
| `api/auth.py` | Complete authentication module with JWT, password hashing, user repository |
| `api/database.py` | SQLite database helpers with parameterized queries |
| `api/main.py` | FastAPI application with CORS, rate limiting, authentication integration |
| `SECURITY.md` | Security best practices documentation |
| `Dockerfile` | Container security configuration |
| `docker-compose.yml` | Docker composition with health checks |
| `.env.example` | Environment variable template |
| `requirements.txt` | Security dependency specifications |
| `tests/unit/test_api_main.py` | CORS and API security tests |
| `tests/integration/test_api_integration.py` | Authentication flow integration tests |
| `src/models/financial_models.py` | Domain model validation rules |

#### 6.4.14.2 CI/CD Security Configuration

| Path | Description |
|------|-------------|
| `.circleci/config.yml` | CircleCI security pipeline |
| `.github/workflows/bandit.yml` | Bandit SAST workflow |
| `.github/workflows/codeql.yml` | CodeQL analysis workflow |
| `.github/workflows/semgrep.yml` | Semgrep pattern analysis |
| `.github/workflows/trivy.yml` | Container scanning workflow |
| `.github/workflows/snyk-security.yml` | Snyk dependency scanning |
| `.github/workflows/scorecard.yml` | OSSF supply chain security |

#### 6.4.14.3 Technical Specification Cross-References

| Section | Relevance |
|---------|-----------|
| 3.8 Security Considerations | Technology stack security overview |
| 5.2 COMPONENT DETAILS | FastAPI backend security integration |
| 5.4 CROSS-CUTTING CONCERNS | Authentication framework, error handling |
| 5.5 DEPLOYMENT ARCHITECTURE | Container and serverless security |
| 6.2 Database Design | Authentication schema, access control matrix |
| 4.3 API Request Workflows | Request validation flows |
| 4.5 Error Handling Workflows | Security error scenarios |

## 6.5 Monitoring and Observability

### 6.5.1 Monitoring Architecture Overview

#### 6.5.1.1 Current State Assessment

The Financial Asset Relationship Database implements **essential monitoring capabilities** through built-in health checks, application logging, and a metrics endpoint. The system follows a **monolithic layered architecture** that does not require complex distributed tracing infrastructure typically associated with microservices architectures.

The current monitoring implementation provides sufficient observability for the system's operational requirements while maintaining operational simplicity. The following table summarizes the monitoring architecture:

| Component | Implementation Status | Technology |
|-----------|----------------------|------------|
| Health Checks | ✅ Implemented | FastAPI endpoint, Docker HEALTHCHECK |
| Application Logging | ✅ Implemented | Python standard logging |
| Application Metrics | ✅ Implemented | Custom `/api/metrics` endpoint |
| Distributed Tracing | ⚠️ Not Required | Monolithic architecture |
| Log Aggregation | ⚠️ Not Implemented | Basic stdout logging |
| Alert Management | ⚠️ CI/CD Only | GitHub Actions, CircleCI |

#### 6.5.1.2 Monitoring Architecture Diagram

```mermaid
flowchart TB
    subgraph MonitoringArchitecture[Monitoring Architecture]
        subgraph ApplicationLayer[Application Layer]
            FastAPI[FastAPI Backend<br/>Port 8000]
            Gradio[Gradio UI<br/>Port 7860]
            NextJS[Next.js Frontend<br/>Port 3000]
        end

        subgraph MonitoringEndpoints[Monitoring Endpoints]
            HealthCheck["/api/health<br/>Health Check"]
            MetricsEndpoint["/api/metrics<br/>Graph Metrics"]
        end

        subgraph LoggingLayer[Logging Layer]
            PythonLogging[Python Standard<br/>Logging]
            ConsoleOutput[Console/Stdout<br/>Output]
        end

        subgraph ContainerMonitoring[Container Monitoring]
            DockerHealth[Docker HEALTHCHECK<br/>HTTP Probe]
            ComposeHealth[Docker Compose<br/>Health Config]
        end

        subgraph CICDMonitoring[CI/CD Monitoring]
            GitHubActions[GitHub Actions<br/>Security Scans]
            CircleCI[CircleCI<br/>Test Coverage]
            Codecov[Codecov<br/>Coverage Reports]
        end
    end

    FastAPI --> HealthCheck
    FastAPI --> MetricsEndpoint
    FastAPI --> PythonLogging
    PythonLogging --> ConsoleOutput

    DockerHealth --> HealthCheck
    ComposeHealth --> HealthCheck

    GitHubActions --> SecurityScan([Security<br/>Results])
    CircleCI --> CoverageRpt([Coverage<br/>Reports])
    CoverageRpt --> Codecov
```

---

### 6.5.2 Monitoring Infrastructure

#### 6.5.2.1 Health Check Implementation

The system implements comprehensive health checking at multiple levels to ensure operational reliability.

#### API Health Check Endpoint

**Location**: `api/main.py` (lines 428-431)

| Endpoint | Method | Response | Purpose |
|----------|--------|----------|---------|
| `/api/health` | GET | `{"status": "healthy", "graph_initialized": true}` | Load balancer probe |

The health check endpoint provides immediate visibility into application state and is used by container orchestration systems for readiness and liveness probes.

#### Docker Container Health Checks

**Location**: `Dockerfile` (lines 38-40), `docker-compose.yml` (lines 20-25)

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `interval` | 30 seconds | Probe frequency |
| `timeout` | 10 seconds | Maximum probe duration |
| `retries` | 3 | Failures before unhealthy |
| `start_period` | 5-40 seconds | Startup grace period |

#### Health Check Flow

```mermaid
flowchart TB
    subgraph HealthCheckFlow[Health Check Flow]
        Orchestrator([Container<br/>Orchestrator]) --> DockerProbe{Docker<br/>HEALTHCHECK}

        DockerProbe --> CurlRequest[HTTP GET<br/>localhost:7860/]
        CurlRequest --> CheckResponse{Response<br/>Status?}

        CheckResponse -->|200 OK| Healthy[Container<br/>Healthy]
        CheckResponse -->|Error/Timeout| RetryCount{Retry<br/>Count < 3?}

        RetryCount -->|Yes| WaitInterval[Wait 30s]
        WaitInterval --> CurlRequest
        RetryCount -->|No| Unhealthy[Container<br/>Unhealthy]

        Unhealthy --> RestartPolicy{Restart<br/>Policy?}
        RestartPolicy -->|unless-stopped| Restart[Restart<br/>Container]
        Restart --> StartPeriod[Start Period<br/>Grace 40s]
        StartPeriod --> CurlRequest
    end
```

#### Frontend Health Check Integration

**Location**: `frontend/app/lib/api.ts` (lines 14-18)

The Next.js frontend includes an API client method for health checking:

| Method | Endpoint | Response Handling |
|--------|----------|-------------------|
| `healthCheck()` | `GET /api/health` | Returns health status object |

#### 6.5.2.2 Logging Strategy

The system implements Python standard logging with structured output for operational visibility.

#### Logging Configuration

**Backend Logging** (`api/main.py` lines 26-28):

| Setting | Value | Purpose |
|---------|-------|---------|
| Level | `INFO` | Default verbosity |
| Logger | `logging.getLogger(__name__)` | Module-specific logger |
| Format | Python default | Standard log format |

**Gradio Logging** (`app.py` line 20):

| Setting | Value | Purpose |
|---------|-------|---------|
| Level | `INFO` | Default verbosity |
| Format | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` | Timestamped structured format |

#### Log Point Catalog

| Log Point | Level | Content | Location |
|-----------|-------|---------|----------|
| Graph initialization | INFO | Success/failure status | `api/main.py` |
| Application startup | INFO | Server binding, port | `api/main.py` |
| Application shutdown | INFO | Shutdown notification | `api/main.py` |
| Cache operations | INFO | Load/save success | `src/data/real_data_fetcher.py` |
| Data fetching | INFO | Yahoo Finance fetches | `src/data/real_data_fetcher.py` |
| Request errors | ERROR | Exception details | `api/main.py` |
| Authentication failures | WARNING | Failed login attempts | `api/auth.py` |
| Invalid CORS origins | WARNING | Skipped origin value | `api/main.py` |

#### 6.5.2.3 Metrics Collection

#### Application Metrics Endpoint

**Location**: `api/main.py` (lines 563-602)

The `/api/metrics` endpoint provides graph topology and network analysis metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `total_assets` | Counter | Count of nodes in graph |
| `total_relationships` | Counter | Count of edges in graph |
| `asset_classes` | Dictionary | Count per asset class |
| `avg_degree` | Gauge | Mean connections per node |
| `max_degree` | Gauge | Highest connected node |
| `network_density` | Gauge | Ratio of actual to possible edges |
| `relationship_density` | Gauge | Calculated relationship density |

#### Metrics Response Model

**Location**: `api/main.py` (lines 389-397)

```
MetricsResponse {
    total_assets: int
    total_relationships: int
    asset_classes: Dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float
}
```

---

### 6.5.3 Observability Patterns

#### 6.5.3.1 Performance Targets and SLAs

The system defines clear Service Level Agreements (SLAs) for critical operations:

#### Performance SLA Matrix

| Operation | Target SLA | Measurement Point |
|-----------|-----------|-------------------|
| API Response (p95) | < 500ms | Request to response |
| Visualization Rendering | < 2 seconds | Data load to interactive |
| Token Generation | < 100ms | Credential to token |
| Graph Initialization | < 3 seconds | Application startup |
| Relationship Discovery | < 500ms | For 100 assets |
| Initial Page Load | < 3 seconds | Navigation to interactive |
| Dataclass Instantiation | < 1ms | Per object |
| Validation | < 1ms | Per object |

#### Timeout Configuration

| Component | Timeout | Purpose |
|-----------|---------|---------|
| JWT Token | 30 minutes | Session expiration |
| Rate Limit Window | 1 minute | Request counting period |
| HTTP Client | 30 seconds | API request timeout |
| Health Check | 30 seconds | Container probe interval |

#### 6.5.3.2 Rate Limiting Observability

Rate limiting provides visibility into API usage patterns and abuse prevention.

**Location**: `api/main.py` (lines 156-169)

| Endpoint | Limit | Window | Key Function |
|----------|-------|--------|--------------|
| `POST /token` | 5 requests | 1 minute | Client IP |
| `GET /api/users/me` | 10 requests | 1 minute | Client IP |
| Other endpoints | Unlimited | N/A | N/A |

#### Rate Limit Response Indicators

| Indicator | Value | Purpose |
|-----------|-------|---------|
| HTTP Status | 429 | Too Many Requests |
| Header | `Retry-After: <seconds>` | Client retry guidance |
| Body | Error detail message | Limit information |

#### 6.5.3.3 Error Tracking Patterns

#### API Error Categories

| Status Code | Scenario | Monitoring Impact |
|-------------|----------|-------------------|
| 400 | Bad Request | User input validation |
| 401 | Unauthorized | Authentication failures |
| 404 | Not Found | Missing resource requests |
| 422 | Validation Error | Schema validation failures |
| 429 | Too Many Requests | Rate limiting activation |
| 500 | Internal Error | Application exceptions |

#### Error Handling Flow

```mermaid
flowchart TB
    subgraph ErrorObservability[Error Observability Flow]
        ErrorOccurs([Error<br/>Detected]) --> ErrorType{Error<br/>Category}

        ErrorType -->|HTTPException| HTTPLog[Log HTTP<br/>Error Details]
        ErrorType -->|Rate Limit| RateLog[Log Rate<br/>Limit Hit]
        ErrorType -->|Validation| ValLog[Log Validation<br/>Error]
        ErrorType -->|Unexpected| UnexpLog[Logger.exception<br/>Full Stack Trace]

        HTTPLog --> ReturnStatus[Return HTTP<br/>Status Code]
        RateLog --> Return429[Return 429<br/>+ Retry-After]
        ValLog --> Return422[Return 422<br/>+ Field Details]
        UnexpLog --> Return500[Return 500<br/>Generic Error]

        ReturnStatus --> ClientResponse([Client<br/>Response])
        Return429 --> ClientResponse
        Return422 --> ClientResponse
        Return500 --> ClientResponse
    end
```

#### 6.5.3.4 Frontend Error Recovery Patterns

**Location**: `frontend/app/page.tsx` (lines 109-119)

| Error Category | User Feedback | Recovery Option |
|----------------|---------------|-----------------|
| Network Error | "Unable to connect" | Retry button |
| API Error | Error message display | Retry button |
| Render Error | Display error state | Refresh page |

Client-side errors are logged via `console.error('Error loading data:', err)` for browser developer tools visibility.

---

### 6.5.4 CI/CD Monitoring and Quality Gates

#### 6.5.4.1 Test Coverage Monitoring

The system implements comprehensive test coverage monitoring through multiple platforms.

#### Codecov Integration

**Location**: `.github/workflows/codecov.yaml`

| Configuration | Value | Purpose |
|---------------|-------|---------|
| Coverage Format | XML/HTML | Report generation |
| Test Results | JUnit XML | Test outcome tracking |
| Upload Action | `codecov/codecov-action` | Results publication |

#### CircleCI Coverage Pipeline

**Location**: `.circleci/config.yml` (lines 68-75)

| Coverage Setting | Configuration |
|------------------|---------------|
| Source Directories | `src`, `tests` |
| Report Formats | XML, HTML |
| Upload Target | Codecov |
| Artifact Storage | Coverage reports |

#### Coverage Configuration

**Location**: `pyproject.toml` (lines 65-83)

| Setting | Value |
|---------|-------|
| Source | `["src"]` |
| Omit Patterns | `*/tests/*`, `*/__pycache__/*`, `*/site-packages/*` |
| Exclude Lines | `pragma: no cover`, abstract methods, type checking |

#### 6.5.4.2 Security Scanning Pipeline

The repository implements comprehensive security scanning through both CircleCI and GitHub Actions.

#### GitHub Actions Security Workflows

| Workflow | Tool | Trigger | Purpose |
|----------|------|---------|---------|
| `bandit.yml` | Bandit | Push/PR | Python SAST |
| `codeql.yml` | CodeQL | Push/PR/Schedule | Multi-language SAST |
| `semgrep.yml` | Semgrep | Push/PR | Pattern-based detection |
| `trivy.yml` | Trivy | Push/Schedule | Container scanning |
| `hadolint.yml` | Hadolint | Push/PR | Dockerfile analysis |
| `snyk-security.yml` | Snyk | Push/PR | Dependency scanning |
| `snyk-container.yml` | Snyk | Push/PR | Container vulnerabilities |
| `dependency-review.yml` | GitHub | PR | Dependency review |
| `scorecard.yml` | OSSF Scorecard | Push/Schedule | Supply chain security |
| `devskim.yml` | DevSkim | Push/PR | Security linting |

#### CircleCI Security Pipeline

**Location**: `.circleci/config.yml` (lines 77-100)

| Tool | Purpose | Stage |
|------|---------|-------|
| `safety check` | Python dependency vulnerabilities | Build |
| `bandit` | Python SAST analysis | Build |

#### Nightly Security Scan

**Location**: `.circleci/config.yml` (lines 206-216)

| Setting | Value |
|---------|-------|
| Schedule | `0 2 * * *` (2:00 AM UTC daily) |
| Branch | `main` |
| Jobs | `python-security` |

#### Security Scan Dashboard

```mermaid
flowchart TB
    subgraph SecurityScanPipeline[Security Scan Pipeline]
        subgraph GitHubSecurity[GitHub Actions Security]
            CodeQL[CodeQL<br/>SAST]
            Bandit[Bandit<br/>Python SAST]
            Semgrep[Semgrep<br/>Pattern Detection]
            Trivy[Trivy<br/>Container Scan]
            Snyk[Snyk<br/>Dependency Scan]
        end

        subgraph CircleCISecurity[CircleCI Security]
            Safety[Safety<br/>Dependency Check]
            BanditCI[Bandit<br/>SAST]
        end

        subgraph Results[Security Results]
            SARIF[SARIF Upload<br/>GitHub Security Tab]
            Artifacts[Scan<br/>Artifacts]
        end

        subgraph Schedule[Scheduled Scans]
            Nightly[Nightly Security<br/>2:00 AM UTC]
            Weekly[Weekly Trivy<br/>Saturday 14:30 UTC]
        end
    end

    CodeQL --> SARIF
    Bandit --> SARIF
    Semgrep --> SARIF
    Trivy --> SARIF
    Snyk --> SARIF

    Safety --> Artifacts
    BanditCI --> Artifacts

    Nightly --> CircleCISecurity
    Weekly --> Trivy
```

---

### 6.5.5 Incident Response

#### 6.5.5.1 Error Detection and Classification

#### Graph Initialization Error Handling

| Error Source | Detection Method | Recovery Action | Fallback |
|--------------|------------------|-----------------|----------|
| Cache load failed | JSON parse error | Proceed to fresh fetch | Standard initialization |
| Network disabled | Connection timeout | Use sample data | Offline mode |
| Yahoo Finance error | Request exception | Check partial data | Sample data fallback |
| Critical failure | Unrecoverable exception | Abort startup | Application exit |

#### Graph Initialization Recovery Flow

```mermaid
flowchart TB
    subgraph InitRecovery[Graph Initialization Recovery]
        StartInit([Initialize<br/>Graph]) --> TryCache{Load from<br/>Cache?}

        TryCache -->|Success| CacheLoaded[Use Cached<br/>Data]
        TryCache -->|JSON Error| LogCacheErr[Log Cache<br/>Error]

        LogCacheErr --> TryNetwork{Network<br/>Available?}
        TryNetwork -->|Yes| TryYahoo{Fetch Yahoo<br/>Finance?}
        TryNetwork -->|No| UseSample1[Use Sample<br/>Data]

        TryYahoo -->|Success| UseRealData[Use Real<br/>Market Data]
        TryYahoo -->|Partial| UsePartial[Use Partial<br/>Data]
        TryYahoo -->|Failure| UseSample2[Use Sample<br/>Data]

        CacheLoaded --> GraphReady([Graph<br/>Initialized])
        UseRealData --> SaveCache[Save to<br/>Cache]
        UsePartial --> SaveCache
        SaveCache --> GraphReady
        UseSample1 --> GraphReady
        UseSample2 --> GraphReady
    end
```

#### 6.5.5.2 Alert Routing Architecture

The current system relies on CI/CD platform notifications for alerting:

#### CI/CD Alert Flow

```mermaid
flowchart TB
    subgraph AlertRouting[Alert Routing Flow]
        subgraph Triggers[Alert Triggers]
            TestFail[Test<br/>Failure]
            SecurityFail[Security<br/>Scan Alert]
            BuildFail[Build<br/>Failure]
            CoverageDrop[Coverage<br/>Drop]
        end

        subgraph Platforms[CI/CD Platforms]
            GitHub[GitHub<br/>Actions]
            CircleCI[CircleCI]
        end

        subgraph Notifications[Notification Channels]
            GitHubUI[GitHub<br/>UI Alerts]
            Email[Email<br/>Notifications]
            SecurityTab[GitHub Security<br/>Tab]
        end

        TestFail --> GitHub
        TestFail --> CircleCI
        SecurityFail --> GitHub
        BuildFail --> GitHub
        BuildFail --> CircleCI
        CoverageDrop --> GitHub

        GitHub --> GitHubUI
        GitHub --> Email
        GitHub --> SecurityTab
        CircleCI --> Email
    end
```

#### 6.5.5.3 Escalation Procedures

| Severity | Detection | Initial Response | Escalation |
|----------|-----------|------------------|------------|
| Critical | Application crash | Restart container | Review logs, investigate root cause |
| High | Security scan failure | Review findings | Patch dependencies, update codebase |
| Medium | Test failure | Review failing tests | Fix code, update tests |
| Low | Coverage drop | Review changes | Improve test coverage |

#### 6.5.5.4 Recovery Scenarios

| Scenario | Detection | Recovery Action |
|----------|-----------|-----------------|
| Graph corruption | Validation failure | Clear cache, reinitialize |
| Cache file corruption | JSON parse error | Delete cache, fresh fetch |
| Database unavailable | Connection timeout | Retry with exponential backoff |
| Yahoo Finance outage | Request timeout | Fall back to sample data |
| Authentication failure | JWT decode error | Re-authenticate user |

---

### 6.5.6 Dashboard Design

#### 6.5.6.1 Metrics Dashboard Layout

The system provides operational metrics through the `/api/metrics` endpoint. A recommended dashboard layout for visualization:

```mermaid
flowchart TB
    subgraph MetricsDashboard[Metrics Dashboard Layout]
        subgraph TopRow[Overview Metrics]
            TotalAssets[Total Assets<br/>Counter]
            TotalRelationships[Total Relationships<br/>Counter]
            NetworkDensity[Network Density<br/>Gauge]
        end

        subgraph MiddleRow[Network Analysis]
            AvgDegree[Average Degree<br/>Gauge]
            MaxDegree[Maximum Degree<br/>Gauge]
            RelDensity[Relationship<br/>Density]
        end

        subgraph BottomRow[Asset Distribution]
            AssetClasses[Asset Classes<br/>Breakdown Chart]
        end
    end
```

#### 6.5.6.2 Alert Threshold Matrix

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|-------------------|-------------------|--------|
| API Response Time (p95) | > 400ms | > 500ms | Investigate slow endpoints |
| Error Rate | > 1% | > 5% | Review error logs |
| Health Check Failures | 1 retry | 3 retries | Container restart |
| Graph Initialization | > 2.5s | > 3s | Optimize data loading |
| Token Generation | > 80ms | > 100ms | Review auth performance |

#### 6.5.6.3 SLA Monitoring Dashboard Concept

| Panel | Metric | SLA Target | Visualization |
|-------|--------|------------|---------------|
| API Latency | Response time p95 | < 500ms | Time series graph |
| Availability | Health check status | > 99.9% | Status indicator |
| Error Rate | 5xx responses | < 0.1% | Percentage gauge |
| Throughput | Requests per second | Variable | Counter display |

---

### 6.5.7 Future Monitoring Recommendations

#### 6.5.7.1 Recommended Observability Stack

Based on industry best practices for FastAPI applications, the following enhancements are recommended for production deployments with increased scale requirements:

| Component | Recommended Tool | Purpose |
|-----------|------------------|---------|
| Metrics Collection | Prometheus + prometheus-fastapi-instrumentator | RED metrics (Rate, Error, Duration) |
| Distributed Tracing | OpenTelemetry | Request flow visualization |
| Log Aggregation | Loki or ELK Stack | Centralized log management |
| Visualization | Grafana | Unified dashboard |
| Error Tracking | Sentry | Exception monitoring |
| Alerting | Prometheus Alertmanager | Automated notifications |

#### 6.5.7.2 OpenTelemetry Integration Path

For future scalability, OpenTelemetry provides a vendor-neutral approach to observability:

| Integration Point | Library | Purpose |
|-------------------|---------|---------|
| Auto-instrumentation | `opentelemetry-instrumentation-fastapi` | Automatic request tracing |
| Metrics Export | `opentelemetry-exporter-prometheus` | Prometheus-compatible metrics |
| Trace Export | `opentelemetry-exporter-otlp` | Trace data export |

#### 6.5.7.3 Structured Logging Enhancement

Recommended logging format upgrade for improved observability:

| Enhancement | Current | Recommended |
|-------------|---------|-------------|
| Format | Plain text | JSON structured |
| Request ID | Not implemented | UUID per request |
| Correlation | None | Trace ID integration |
| Context | Basic | User, endpoint, duration |

#### 6.5.7.4 Monitoring Prerequisites for Microservices Migration

As documented in the Core Services Architecture (Section 6.1), the following monitoring capabilities would be required before migrating to a microservices architecture:

| Prerequisite | Current State | Required for Migration |
|--------------|--------------|----------------------|
| Database Persistence | Optional | Required for shared state |
| Message Queue | Not implemented | Required for async communication |
| Service Mesh | Not applicable | Required for service discovery |
| Distributed Tracing | Not implemented | Required for observability |

---

### 6.5.8 Security Event Monitoring

#### 6.5.8.1 Security Event Categories

| Event Category | Log Level | Content | Monitoring Action |
|----------------|-----------|---------|-------------------|
| Authentication failures | WARNING | Failed login attempts | Track frequency, detect brute force |
| Invalid CORS origins | WARNING | Skipped origin value | Review CORS configuration |
| Rate limit exceeded | INFO (429 response) | Client IP, endpoint | Identify abuse patterns |
| Request errors | ERROR | Exception details | Investigate root cause |
| Token expiration | INFO | Session timeout | Normal operation tracking |

#### 6.5.8.2 CI/CD Security Event Flow

```mermaid
flowchart TB
    subgraph SecurityEventFlow[Security Event Monitoring Flow]
        subgraph Sources[Event Sources]
            CodePush[Code<br/>Push]
            PRCreated[Pull Request<br/>Created]
            Schedule[Scheduled<br/>Trigger]
        end

        subgraph Scans[Security Scans]
            SAST[SAST<br/>Analysis]
            DependencyScan[Dependency<br/>Scan]
            ContainerScan[Container<br/>Scan]
        end

        subgraph Analysis[Results Analysis]
            FindingsReview[Findings<br/>Review]
            SeverityClass[Severity<br/>Classification]
        end

        subgraph Actions[Response Actions]
            BlockMerge[Block PR<br/>Merge]
            CreateIssue[Create<br/>Issue]
            AlertTeam[Alert<br/>Team]
        end
    end

    CodePush --> SAST
    CodePush --> DependencyScan
    PRCreated --> ContainerScan
    Schedule --> SAST
    Schedule --> DependencyScan
    Schedule --> ContainerScan

    SAST --> FindingsReview
    DependencyScan --> FindingsReview
    ContainerScan --> FindingsReview

    FindingsReview --> SeverityClass

    SeverityClass -->|Critical/High| BlockMerge
    SeverityClass -->|Critical/High| AlertTeam
    SeverityClass -->|Medium/Low| CreateIssue
```

---

### 6.5.9 Container and Deployment Monitoring

#### 6.5.9.1 Docker Container Monitoring

| Monitoring Aspect | Implementation | Configuration |
|-------------------|----------------|---------------|
| Health Probes | HTTP GET `/` | Every 30 seconds |
| Restart Policy | `unless-stopped` | Automatic recovery |
| Volume Mounts | `./src:/app/src`, `./data:/app/data` | Persistent storage |
| Port Exposure | 7860 | External access |

#### 6.5.9.2 Container Security Monitoring

**Trivy Vulnerability Scanner** (`.github/workflows/trivy.yml`)

| Configuration | Value |
|---------------|-------|
| Trigger | Dockerfile/docker-compose changes |
| Schedule | Weekly (Saturday 14:30 UTC) |
| Severity Filter | CRITICAL, HIGH |
| Results | SARIF upload to GitHub Security |

#### 6.5.9.3 Deployment Environment Comparison

| Environment | Monitoring Approach | Health Check |
|-------------|---------------------|--------------|
| Local Development | Console logging | Manual testing |
| Docker | Docker HEALTHCHECK | HTTP probe |
| Vercel Serverless | Platform monitoring | Edge health checks |

---

### 6.5.10 References

#### 6.5.10.1 Source Files Examined

| Path | Relevance |
|------|-----------|
| `api/main.py` | Health check endpoint, metrics endpoint, logging, rate limiting, error handling |
| `api/auth.py` | Authentication logging, security event handling |
| `api/database.py` | Database connection logging |
| `app.py` | Gradio application logging configuration |
| `src/data/real_data_fetcher.py` | Data fetch logging, cache operations |
| `frontend/app/page.tsx` | Frontend error handling, retry pattern |
| `frontend/app/lib/api.ts` | Frontend health check API client |
| `Dockerfile` | Docker health check configuration |
| `docker-compose.yml` | Container orchestration health checks |
| `pyproject.toml` | Test coverage configuration |

#### 6.5.10.2 CI/CD Configuration Files

| Path | Relevance |
|------|-----------|
| `.circleci/config.yml` | CircleCI monitoring, coverage, security scanning |
| `.github/workflows/ci.yml` | Main CI workflow with coverage |
| `.github/workflows/codecov.yaml` | Coverage upload workflow |
| `.github/workflows/trivy.yml` | Container security scanning |
| `.github/workflows/bandit.yml` | Python SAST workflow |
| `.github/workflows/codeql.yml` | CodeQL analysis workflow |
| `.github/workflows/semgrep.yml` | Semgrep pattern analysis |
| `.github/workflows/snyk-security.yml` | Snyk dependency scanning |
| `.github/workflows/scorecard.yml` | OSSF supply chain security |

#### 6.5.10.3 Technical Specification Cross-References

| Section | Relevance |
|---------|-----------|
| 5.4 CROSS-CUTTING CONCERNS | Monitoring, observability, error handling patterns |
| 6.4 Security Architecture | Security event logging, audit requirements |
| 5.5 DEPLOYMENT ARCHITECTURE | Container and serverless deployment monitoring |
| 4.5 Error Handling Workflows | Error detection and recovery flows |
| 4.8 Timing and SLA Considerations | Performance targets and timeout configuration |
| 6.1 Core Services Architecture | Monolithic architecture implications for monitoring |

#### 6.5.10.4 External References

| Resource | Context |
|----------|---------|
| FastAPI Observability Best Practices | Industry recommendations for monitoring |
| OpenTelemetry Documentation | Distributed tracing standards |
| Prometheus FastAPI Instrumentator | Metrics collection library |
| Grafana FastAPI Dashboard | Dashboard design patterns |

## 6.6 Testing Strategy

### 6.6.1 Testing Strategy Overview

#### 6.6.1.1 Executive Summary

The Financial Asset Relationship Database implements a comprehensive multi-tier testing strategy designed to ensure reliability, maintainability, and quality across both backend (Python/FastAPI) and frontend (Next.js/TypeScript) components. The testing approach emphasizes automated validation at multiple levels—from unit tests validating individual functions to integration tests verifying cross-component interactions.

The testing architecture aligns with industry best practices for monolithic layered applications, leveraging pytest for Python backend testing, Jest with React Testing Library for frontend validation, and a robust CI/CD pipeline for automated quality gates.

#### 6.6.1.2 Testing Philosophy

| Principle | Implementation | Rationale |
|-----------|---------------|-----------|
| Test Isolation | Separate test databases, fixture reset | Prevent test interference |
| Behavior-Driven | Test user interactions, not implementation | Resilient to refactoring |
| Coverage-First | 80%+ coverage targets | Catch regressions early |
| Fast Feedback | Parallel execution, CI integration | Developer productivity |

#### 6.6.1.3 Test Suite Statistics

| Component | Test Cases | Test Lines | Coverage Target |
|-----------|------------|------------|-----------------|
| Backend Python | 60+ | ~1,042 | >80% |
| Frontend TypeScript | 80+ | ~937 | >80% |
| **Total** | **140+** | **~2,000** | **>80%** |

---

### 6.6.2 Unit Testing

#### 6.6.2.1 Backend Unit Testing Framework

The Python backend utilizes pytest as the primary testing framework, providing powerful fixtures, parametrization, and extensibility.

#### Testing Framework Stack

| Tool | Version | Purpose |
|------|---------|---------|
| pytest | >= 7.0.0 | Test runner and framework |
| pytest-cov | >= 4.0.0 | Coverage reporting |
| httpx | >= 0.24.0 | Async HTTP client for TestClient |
| unittest.mock | stdlib | Mocking and patching |

#### Test Organization Structure

```
tests/
├── __init__.py                    # Test environment setup
├── conftest.py                    # Shared fixtures
├── unit/
│   ├── test_api.py               # FastAPI endpoint tests
│   ├── test_api_main.py          # Comprehensive API tests
│   ├── test_financial_models.py  # Domain model validation
│   ├── test_asset_graph.py       # Graph logic tests
│   ├── test_repository.py        # Data layer tests
│   ├── test_database.py          # SQLite/SQLAlchemy tests
│   ├── test_database_memory.py   # In-memory database tests
│   ├── test_graph_visuals.py     # Plotly visualization tests
│   ├── test_metric_visuals.py    # Metrics visualization tests
│   └── test_schema_report.py     # Report generation tests
└── integration/
    ├── conftest.py               # Integration fixtures
    ├── test_api_integration.py   # End-to-end API workflows
    └── test_repository.py        # Database integration tests
```

#### Pytest Configuration

**Location**: `pyproject.toml`

| Setting | Value | Purpose |
|---------|-------|---------|
| `testpaths` | `["tests"]` | Test discovery root |
| `python_files` | `["test_*.py", "*_test.py"]` | Test file patterns |
| `python_classes` | `["Test*"]` | Test class patterns |
| `python_functions` | `["test_*"]` | Test function patterns |

#### Test Markers

| Marker | Description | Usage |
|--------|-------------|-------|
| `@pytest.mark.unit` | Unit tests | `pytest -m unit` |
| `@pytest.mark.integration` | Integration tests | `pytest -m integration` |
| `@pytest.mark.slow` | Slow running tests | `pytest -m "not slow"` |

#### 6.6.2.2 Backend Mocking Strategy

The backend employs a multi-layered mocking approach to isolate components under test.

#### Graph Instance Mocking

| Pattern | Implementation | Use Case |
|---------|---------------|----------|
| Factory Override | `set_graph_factory()` | Test isolation for graph singleton |
| Fixture Reset | `_reset_graph` fixture | Clean state between tests |
| Mock Patch | `unittest.mock.patch` | API endpoint isolation |

#### Test Fixture Patterns

```mermaid
flowchart TB
    subgraph FixtureHierarchy[Backend Test Fixture Hierarchy]
        subgraph SessionScope[Session Scope]
            DBEngine[Database Engine<br/>SQLite in-memory]
        end

        subgraph ModuleScope[Module Scope]
            GraphFactory[Graph Factory<br/>Mock/Real Toggle]
        end

        subgraph FunctionScope[Function Scope]
            TestClient[FastAPI TestClient]
            MockGraph[Mock Graph Instance]
            SampleAssets[Sample Asset Data]
            DBSession[Database Session<br/>With Rollback]
        end
    end

    DBEngine --> DBSession
    GraphFactory --> MockGraph
    MockGraph --> TestClient
    SampleAssets --> TestClient
    DBSession --> TestClient
```

#### Shared Fixture Examples

**Location**: `tests/conftest.py`

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `mock_graph` | function | Isolated graph instance for testing |
| `sample_equity` | function | Pre-configured equity asset |
| `dividend_stock` | function | Asset with dividend data |
| `_reset_graph` | function | Graph state cleanup |

#### Conditional Test Execution

| Pattern | Implementation | Purpose |
|---------|---------------|---------|
| Import Skip | `pytest.importorskip("sqlalchemy")` | Skip if dependency missing |
| Environment Check | `pytest.mark.skipif(...)` | Environment-specific tests |
| Parametrization | `@pytest.mark.parametrize` | Multiple test scenarios |

#### 6.6.2.3 Frontend Unit Testing Framework

The Next.js frontend implements Jest with React Testing Library for comprehensive component and utility testing.

#### Testing Framework Stack

| Tool | Version | Purpose |
|------|---------|---------|
| Jest | ^29.7.0 | Test runner and framework |
| @testing-library/react | ^14.1.2 | React component testing |
| @testing-library/jest-dom | ^6.4.0 | DOM assertions |
| jest-environment-jsdom | ^29.7.0 | DOM simulation |

#### Frontend Test Organization

```
frontend/
├── __tests__/
│   ├── test-utils.ts               # Centralized mock data
│   ├── lib/
│   │   ├── api.test.ts            # API client tests
│   │   └── api-axios-compatibility.test.ts
│   ├── components/
│   │   ├── AssetList.test.tsx     # Asset list component
│   │   ├── MetricsDashboard.test.tsx
│   │   └── NetworkVisualization.test.tsx
│   └── app/
│       └── page.test.tsx          # Page-level tests
├── jest.config.js                  # Jest configuration
├── jest.setup.js                   # Environment setup
└── package.json                    # Test scripts
```

#### Jest Configuration

**Location**: `frontend/jest.config.js`

| Setting | Value | Purpose |
|---------|-------|---------|
| `testEnvironment` | `jest-environment-jsdom` | DOM simulation |
| `setupFilesAfterEnv` | `['./jest.setup.js']` | Test environment setup |
| `moduleNameMapper` | Path aliases | Module resolution |
| `testMatch` | `['**/__tests__/**/*.test.ts(x)?']` | Test file patterns |

#### Environment Setup

**Location**: `frontend/jest.setup.js`

| Configuration | Purpose |
|---------------|---------|
| `@testing-library/jest-dom` import | Extended DOM matchers |
| `window.matchMedia` mock | Media query simulation |
| `IntersectionObserver` mock | Viewport observation |

#### 6.6.2.4 Frontend Mocking Strategy

The frontend testing approach prioritizes testing user behavior over implementation details.

#### Mock Patterns

| Pattern | Implementation | Use Case |
|---------|---------------|----------|
| Module Mock | `jest.mock('axios')` | API client isolation |
| Component Mock | `jest.mock('../../app/lib/api')` | Component isolation |
| Module Reset | `jest.resetModules()` | Clean state between tests |
| Data-TestId | `data-testid` attributes | Element targeting |

#### Centralized Test Data

**Location**: `frontend/__tests__/test-utils.ts`

| Export | Type | Purpose |
|--------|------|---------|
| `mockAssets` | Asset[] | Sample asset collection |
| `mockMetrics` | Metrics | Network metrics data |
| `mockVisualization` | VisualizationData | 3D graph data |
| `mockRelationships` | Relationship[] | Sample relationships |

#### 6.6.2.5 Test Naming Conventions

| Component | Convention | Example |
|-----------|------------|---------|
| Backend Test Files | `test_<module>.py` | `test_api_main.py` |
| Frontend Test Files | `<Component>.test.tsx` | `AssetList.test.tsx` |
| Test Functions | `test_<behavior>` | `test_asset_creation_with_valid_data` |
| Test Classes | `Test<Feature>` | `TestCompleteAPIFlow` |

#### 6.6.2.6 Code Coverage Configuration

#### Backend Coverage

**Location**: `pyproject.toml`

| Setting | Value |
|---------|-------|
| Source Directories | `["src"]` |
| Omit Patterns | `*/tests/*`, `*/__pycache__/*`, `*/site-packages/*` |
| Exclude Lines | `pragma: no cover`, `def __repr__`, `raise NotImplementedError`, `if TYPE_CHECKING:` |

#### Frontend Coverage

| Command | Description |
|---------|-------------|
| `npm test -- --coverage` | Generate coverage report |
| `npm run test:ci` | CI-optimized coverage |

---

### 6.6.3 Integration Testing

#### 6.6.3.1 API Integration Testing

Integration tests validate end-to-end workflows across multiple system components.

**Location**: `tests/integration/test_api_integration.py`

#### Integration Test Categories

| Category | Test Class | Validation Focus |
|----------|------------|------------------|
| Complete API Flow | `TestCompleteAPIFlow` | health → assets → detail → relationships |
| Metrics Consistency | `TestMetricsConsistency` | Metrics match actual data |
| Visualization Data | `TestVisualizationData` | All nodes reference existing assets |
| Performance | `TestPerformance` | Response time SLAs |
| Authentication | `TestAuthentication` | JWT token flows |

#### Integration Test Flow

```mermaid
flowchart TB
    subgraph IntegrationTestFlow[Integration Test Execution Flow]
        Setup([Test Setup]) --> DBInit[Initialize Test<br/>Database]
        DBInit --> GraphInit[Initialize<br/>Graph Instance]
        GraphInit --> ClientCreate[Create FastAPI<br/>TestClient]

        ClientCreate --> TestExec{Execute Test<br/>Scenarios}

        TestExec --> HealthCheck[Health Check<br/>Endpoint]
        TestExec --> AssetFlow[Asset CRUD<br/>Operations]
        TestExec --> RelFlow[Relationship<br/>Queries]
        TestExec --> MetricsFlow[Metrics<br/>Validation]
        TestExec --> VizFlow[Visualization<br/>Data Check]

        HealthCheck --> Assert[Assert<br/>Expectations]
        AssetFlow --> Assert
        RelFlow --> Assert
        MetricsFlow --> Assert
        VizFlow --> Assert

        Assert --> Teardown([Test Teardown<br/>Reset State])
    end
```

#### Performance Integration Tests

| Test | Validation | Threshold |
|------|------------|-----------|
| `test_response_times` | API endpoint response | < 5 seconds |
| `test_concurrent_requests` | ThreadPoolExecutor with 5 workers | 10 requests success |
| `test_visualization_load` | Graph rendering data | < 2 seconds |

#### 6.6.3.2 Database Integration Testing

**Location**: `tests/integration/test_repository.py`

#### Database Test Strategy

| Approach | Implementation | Purpose |
|----------|---------------|---------|
| Isolated Database | `tmp_path` fixture | Test data isolation |
| Migration Testing | Apply `001_initial.sql` | Schema validation |
| CRUD Operations | SQLAlchemy sessions | Data layer verification |
| Transaction Rollback | Session rollback | Clean state |

#### Database Test Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Database URL | `sqlite:///{tmp_path}/test.db` | Isolated test database |
| Connection Args | `check_same_thread=False` | Multi-threaded compatibility |
| Pool Class | `StaticPool` | Connection reuse |

#### 6.6.3.3 External Service Mocking

#### Yahoo Finance Mocking

| Strategy | Implementation | Purpose |
|----------|---------------|---------|
| Environment Flag | `USE_REAL_DATA_FETCHER=false` | Disable real API calls |
| Sample Data Fallback | `sample_database.py` | Predictable test data |
| Cache Mocking | Mock JSON cache files | Cache behavior testing |

#### 6.6.3.4 Dependency and Workflow Testing

**Location**: `tests/integration/`

| Test File | Purpose |
|-----------|---------|
| `test_requirements.py` | Validate production dependencies |
| `test_requirements_dev.py` | Validate development dependencies |
| `test_github_workflows.py` | CI/CD workflow validation |
| `test_debricked_workflow.py` | Security workflow validation |

---

### 6.6.4 End-to-End Testing

#### 6.6.4.1 Current E2E Implementation

The system implements component-level E2E simulation through Jest and React Testing Library, providing comprehensive user interaction testing without requiring a full browser environment.

#### Frontend E2E Patterns

| Pattern | Implementation | Coverage |
|---------|---------------|----------|
| Page Rendering | `page.test.tsx` | Full page lifecycle |
| Component Interaction | `fireEvent`, `userEvent` | User actions |
| Loading States | `waitFor` assertions | Async behavior |
| Error Handling | Mock error responses | Recovery flows |
| Tab Navigation | State management tests | Navigation behavior |

#### Component Test Scenarios

| Component | Test Scenarios |
|-----------|----------------|
| `AssetList` | Render assets, filter by class, search functionality |
| `MetricsDashboard` | Display metrics, handle loading, show errors |
| `NetworkVisualization` | 3D graph rendering, node interaction |
| `page.tsx` | Tab switching, data loading, retry mechanisms |

#### 6.6.4.2 Planned E2E Enhancements

| Enhancement | Tool | Priority |
|-------------|------|----------|
| Browser E2E Tests | Playwright/Cypress | Medium |
| Visual Regression | Percy/Chromatic | Low |
| Load Testing | k6/Artillery | Medium |
| Accessibility Testing | axe-core | Medium |

#### 6.6.4.3 Test Data Management

#### Backend Test Data Setup

**Location**: `tests/__init__.py`

| Environment Variable | Test Value | Purpose |
|---------------------|------------|---------|
| `SECRET_KEY` | `test-secret-key` | JWT signing |
| `DATABASE_URL` | `sqlite:///{test_auth.db}` | Auth database |
| `ADMIN_USERNAME` | `admin` | Test admin user |
| `ADMIN_PASSWORD` | `changeme` | Test credentials |

#### Test Data Lifecycle

```mermaid
flowchart TB
    subgraph TestDataLifecycle[Test Data Lifecycle]
        subgraph Setup[Setup Phase]
            InitEnv[Initialize<br/>Environment]
            CreateDB[Create Test<br/>Database]
            LoadFixtures[Load Test<br/>Fixtures]
            SeedData[Seed Sample<br/>Data]
        end

        subgraph Execution[Execution Phase]
            RunTest[Execute Test<br/>Case]
            CaptureState[Capture<br/>State Changes]
            Validate[Validate<br/>Expectations]
        end

        subgraph Teardown[Teardown Phase]
            RollbackTx[Rollback<br/>Transactions]
            ResetState[Reset Graph<br/>State]
            CleanupFiles[Cleanup<br/>Temp Files]
        end
    end

    InitEnv --> CreateDB
    CreateDB --> LoadFixtures
    LoadFixtures --> SeedData
    SeedData --> RunTest
    RunTest --> CaptureState
    CaptureState --> Validate
    Validate --> RollbackTx
    RollbackTx --> ResetState
    ResetState --> CleanupFiles
```

---

### 6.6.5 Test Automation

#### 6.6.5.1 CI/CD Integration

The testing strategy integrates with both GitHub Actions and CircleCI for comprehensive automated validation.

#### GitHub Actions Primary CI

**Location**: `.github/workflows/ci.yml`

```mermaid
flowchart TB
    subgraph GitHubActionsCI[GitHub Actions CI Pipeline]
        Trigger([Push/PR to main]) --> Checkout[Checkout Code]

        Checkout --> Matrix{Python Version<br/>Matrix}
        Matrix --> Py310[Python 3.10]
        Matrix --> Py311[Python 3.11]
        Matrix --> Py312[Python 3.12]

        Py310 --> LintJobs
        Py311 --> LintJobs
        Py312 --> LintJobs

        subgraph LintJobs[Linting Jobs]
            Flake8[flake8<br/>Critical + Full]
            Black[black --check]
            Isort[isort --check-only]
            Pylint[pylint<br/>fail-under=7.0]
        end

        LintJobs --> TestJob[pytest<br/>--cov=src<br/>--cov-report=xml]

        TestJob --> CoverageCheck{Python 3.11<br/>Only?}
        CoverageCheck -->|Yes| Codecov[Upload to<br/>Codecov]
        CoverageCheck -->|No| Complete([Job Complete])
        Codecov --> Complete
    end
```

#### CI Job Configuration

| Job | Tools | Failure Behavior |
|-----|-------|------------------|
| test | pytest, flake8, black, isort, pylint | fail-fast: false |
| security | safety, bandit | continue-on-error: true |

#### CircleCI Secondary CI

**Location**: `.circleci/config.yml`

| Job | Parallelism | Output |
|-----|-------------|--------|
| python-lint | 1 | flake8 results |
| python-test | 4 | pytest with coverage |
| python-security | 1 | safety + bandit |
| frontend-lint | 1 | npm run lint |
| frontend-build | 1 | npm run build |
| docker-build | 1 | Smoke test |

#### 6.6.5.2 Frontend CI Pipeline

**Location**: `.github/workflows/node.js.yml`

| Configuration | Value |
|---------------|-------|
| Node Matrix | 18.x, 20.x, 22.x |
| Trigger Paths | `frontend/**` |
| Jobs | `npm ci`, `npm run build`, `npm test` |

#### 6.6.5.3 Automated Test Triggers

| Trigger | Event | Tests Executed |
|---------|-------|----------------|
| Push | `main` branch | Full suite |
| Pull Request | To `main` | Full suite |
| Schedule | Daily 02:00 UTC | Security scans |
| Manual | `workflow_dispatch` | Selected workflows |

#### 6.6.5.4 Parallel Test Execution

| Platform | Parallelism | Strategy |
|----------|-------------|----------|
| GitHub Actions | Python version matrix | 3.10, 3.11, 3.12 |
| CircleCI | `parallelism: 4` | Test file distribution |
| Jest | Default parallel | Worker pool |

#### 6.6.5.5 Test Reporting

| Report Type | Format | Destination |
|-------------|--------|-------------|
| Coverage | XML | Codecov upload |
| Test Results | JUnit XML | CircleCI artifacts |
| Coverage HTML | HTML | GitHub artifacts |
| Security | SARIF | GitHub Security tab |

#### 6.6.5.6 Failed Test Handling

| Strategy | Implementation | Purpose |
|----------|---------------|---------|
| Matrix Continue | `fail-fast: false` | Complete all versions |
| Security Continue | `continue-on-error: true` | Non-blocking scans |
| Artifact Preservation | Always upload | Debug information |
| Retry Mechanism | Manual re-run | Flaky test recovery |

---

### 6.6.6 Security Testing

#### 6.6.6.1 Static Application Security Testing (SAST)

| Tool | Workflow | Purpose |
|------|----------|---------|
| Bandit | `.github/workflows/bandit.yml` | Python security linting |
| CodeQL | `.github/workflows/codeql.yml` | Multi-language SAST |
| Semgrep | `.github/workflows/semgrep.yml` | Pattern-based scanning |
| DevSkim | `.github/workflows/devskim.yml` | Security linting |

#### Bandit Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| Skip Codes | `B101` | Allow asserts in tests |
| Output | SARIF | GitHub Security integration |
| Targets | `src/`, `api/` | Application code only |

#### 6.6.6.2 Software Composition Analysis (SCA)

| Tool | Workflow | Scope |
|------|----------|-------|
| Safety | CircleCI | Python dependencies |
| Snyk Open Source | `.github/workflows/snyk-security.yml` | All dependencies |
| Debricked | `.github/workflows/debricked_workflow.yml` | Dependency analysis |
| OSV Scanner | `.github/workflows/osv-scanner.yml` | Vulnerability database |

#### 6.6.6.3 Container Security

| Tool | Workflow | Purpose |
|------|----------|---------|
| Trivy | `.github/workflows/trivy.yml` | Container scanning |
| Hadolint | `.github/workflows/hadolint.yml` | Dockerfile linting |
| Snyk Container | `.github/workflows/snyk-container.yml` | Image vulnerabilities |

#### 6.6.6.4 Security Scanning Pipeline

```mermaid
flowchart TB
    subgraph SecurityPipeline[Security Scanning Pipeline]
        subgraph Triggers[Scan Triggers]
            Push([Code Push])
            PR([Pull Request])
            Schedule([Nightly/Weekly])
        end

        subgraph SAST[SAST Analysis]
            Bandit[Bandit<br/>Python SAST]
            CodeQL[CodeQL<br/>Multi-language]
            Semgrep[Semgrep<br/>Pattern Detection]
        end

        subgraph SCA[Dependency Scanning]
            Safety[Safety<br/>Python Deps]
            Snyk[Snyk<br/>All Deps]
            Debricked[Debricked<br/>Analysis]
        end

        subgraph Container[Container Security]
            Trivy[Trivy<br/>Image Scan]
            Hadolint[Hadolint<br/>Dockerfile]
        end

        subgraph Results[Results Processing]
            SARIF[SARIF Upload]
            SecurityTab[GitHub Security<br/>Tab]
            Artifacts[Scan Artifacts]
        end
    end

    Push --> SAST
    Push --> SCA
    PR --> SAST
    PR --> SCA
    PR --> Container
    Schedule --> SAST
    Schedule --> SCA
    Schedule --> Container

    SAST --> SARIF
    SCA --> SARIF
    Container --> SARIF

    SARIF --> SecurityTab
    SARIF --> Artifacts
```

#### 6.6.6.5 Authentication Testing

| Test Category | Validation | Location |
|---------------|------------|----------|
| JWT Token Flow | Token generation, expiration | `tests/integration/test_api_integration.py` |
| Password Hashing | pbkdf2_sha256 verification | `tests/unit/test_api_main.py` |
| Rate Limiting | 5/min on `/token` | Integration tests |
| CORS Validation | Origin allowlist | Unit tests |

---

### 6.6.7 Quality Metrics

#### 6.6.7.1 Code Coverage Targets

| Component | Current | Target | Critical Paths |
|-----------|---------|--------|----------------|
| Backend API | >90% | >80% | 100% |
| Frontend API Client | >95% | >80% | 100% |
| React Components | >80% | >80% | 100% |
| Domain Models | >85% | >80% | 100% |
| Visualization | >75% | >70% | 100% |

#### 6.6.7.2 Static Analysis Thresholds

| Tool | Metric | Threshold | Enforcement |
|------|--------|-----------|-------------|
| pylint | Score | >= 7.0 | CI blocking |
| black | Formatting | 100% | CI blocking |
| flake8 | Errors | 0 critical | CI blocking |
| isort | Import order | 100% | CI blocking |
| ESLint | Errors | 0 | CI blocking |

#### 6.6.7.3 Performance Test Thresholds

| Operation | Target SLA | Measurement |
|-----------|-----------|-------------|
| API Response (p95) | < 500ms | Request to response |
| Visualization Rendering | < 2 seconds | Data load to interactive |
| Token Generation | < 100ms | Credential to token |
| Graph Initialization | < 3 seconds | Application startup |
| Relationship Discovery | < 500ms | For 100 assets |
| Initial Page Load | < 3 seconds | Navigation to interactive |

#### 6.6.7.4 Quality Gates

```mermaid
flowchart TB
    subgraph QualityGates[Quality Gate Checkpoints]
        PRSubmit([PR Submitted]) --> Gate1{Code Coverage<br/>>= 80%?}

        Gate1 -->|No| Block1[Block Merge]
        Gate1 -->|Yes| Gate2{Linting<br/>Passed?}

        Gate2 -->|No| Block2[Block Merge]
        Gate2 -->|Yes| Gate3{Tests<br/>Passed?}

        Gate3 -->|No| Block3[Block Merge]
        Gate3 -->|Yes| Gate4{Security<br/>Scan Clean?}

        Gate4 -->|Critical| Block4[Block Merge]
        Gate4 -->|Warning/Clean| Gate5{Build<br/>Success?}

        Gate5 -->|No| Block5[Block Merge]
        Gate5 -->|Yes| Approve([Ready for Review])
    end
```

#### 6.6.7.5 Test Success Rate Requirements

| Environment | Required Pass Rate | Action on Failure |
|-------------|-------------------|-------------------|
| Unit Tests | 100% | Block merge |
| Integration Tests | 100% | Block merge |
| Security Scans | No critical | Block merge |
| Linting | 100% | Block merge |

---

### 6.6.8 Test Environment Architecture

#### 6.6.8.1 Environment Configuration

```mermaid
flowchart TB
    subgraph TestEnvironments[Test Environment Architecture]
        subgraph LocalDev[Local Development]
            LocalPytest[pytest<br/>Direct execution]
            LocalJest[Jest<br/>Watch mode]
            LocalDB[SQLite<br/>In-memory]
        end

        subgraph CI[CI Environment]
            GitHubRunner[GitHub Actions<br/>Ubuntu Latest]
            CircleCIRunner[CircleCI<br/>Python/Node Images]
            CIDatabase[Ephemeral<br/>SQLite]
        end

        subgraph Docker[Docker Testing]
            DockerBuild[Build Validation]
            SmokeTest[Container<br/>Smoke Test]
            HealthCheck[Health Check<br/>Probe]
        end
    end

    LocalDev -->|Push| CI
    CI -->|Build| Docker
```

#### 6.6.8.2 Backend Test Environment

| Component | Configuration |
|-----------|---------------|
| Python Version | 3.10, 3.11, 3.12 |
| Database | SQLite in-memory |
| Graph State | Reset per test |
| External APIs | Mocked/Sample data |

#### 6.6.8.3 Frontend Test Environment

| Component | Configuration |
|-----------|---------------|
| Node Version | 18.x, 20.x, 22.x |
| Test Environment | jest-environment-jsdom |
| API Mocking | jest.mock('axios') |
| Browser APIs | window.matchMedia, IntersectionObserver mocked |

#### 6.6.8.4 Docker Test Environment

**Location**: `.github/workflows/docker.yml`

| Test | Command | Validation |
|------|---------|------------|
| Build | `docker build` | Image creation |
| Smoke Test | HTTP probe | 10s health check |
| Config Validation | `docker-compose config` | YAML syntax |
| Security Scan | Trivy | Vulnerability check |

---

### 6.6.9 Test Execution Flow

#### 6.6.9.1 Complete Test Execution Pipeline

```mermaid
flowchart TB
    subgraph TestExecutionFlow[Test Execution Pipeline]
        Trigger([Trigger:<br/>Push/PR/Manual]) --> Checkout[Checkout<br/>Repository]

        Checkout --> ParallelStart{Start Parallel<br/>Execution}

        ParallelStart --> BackendTrack
        ParallelStart --> FrontendTrack
        ParallelStart --> SecurityTrack

        subgraph BackendTrack[Backend Track]
            PyMatrix[Python Matrix<br/>3.10, 3.11, 3.12]
            PyMatrix --> PyLint[Linting<br/>flake8, black, isort]
            PyLint --> PyTest[pytest<br/>--cov=src]
            PyTest --> PyCoverage[Coverage<br/>Upload]
        end

        subgraph FrontendTrack[Frontend Track]
            NodeMatrix[Node Matrix<br/>18.x, 20.x, 22.x]
            NodeMatrix --> NodeLint[npm run lint]
            NodeLint --> NodeBuild[npm run build]
            NodeBuild --> NodeTest[npm test]
        end

        subgraph SecurityTrack[Security Track]
            SASTScans[SAST Scans<br/>Bandit, CodeQL]
            SASTScans --> SCAScans[SCA Scans<br/>Safety, Snyk]
            SCAScans --> ContainerScans[Container Scans<br/>Trivy]
        end

        BackendTrack --> Aggregate{Aggregate<br/>Results}
        FrontendTrack --> Aggregate
        SecurityTrack --> Aggregate

        Aggregate --> QualityGate{Quality<br/>Gates Met?}
        QualityGate -->|Yes| Success([Pipeline<br/>Success])
        QualityGate -->|No| Failure([Pipeline<br/>Failure])
    end
```

#### 6.6.9.2 Test Execution Commands

#### Backend Commands

| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest -m unit` | Run unit tests only |
| `pytest -m integration` | Run integration tests only |
| `pytest --cov=src --cov-report=html` | Coverage with HTML report |
| `make test` | Makefile shortcut |

#### Frontend Commands

| Command | Description |
|---------|-------------|
| `npm test` | Run all tests |
| `npm test -- --coverage` | Tests with coverage |
| `npm test -- --watch` | Watch mode |
| `npm run test:ci` | CI-optimized execution |

---

### 6.6.10 References

#### 6.6.10.1 Source Files Examined

| Path | Relevance |
|------|-----------|
| `pyproject.toml` | Pytest configuration, coverage settings, tool configs |
| `conftest.py` (root) | Coverage plugin handling |
| `tests/conftest.py` | Shared backend fixtures |
| `tests/__init__.py` | Test environment setup |
| `tests/unit/test_api.py` | API unit tests |
| `tests/unit/test_api_main.py` | Comprehensive API tests |
| `tests/unit/test_financial_models.py` | Domain model validation |
| `tests/unit/test_repository.py` | Repository tests |
| `tests/unit/test_graph_visuals.py` | Visualization tests |
| `tests/integration/test_api_integration.py` | Integration tests |
| `tests/integration/test_repository.py` | Database integration |
| `tests/integration/conftest.py` | Integration fixtures |
| `frontend/jest.config.js` | Jest configuration |
| `frontend/jest.setup.js` | Jest environment setup |
| `frontend/package.json` | Frontend test scripts |
| `frontend/__tests__/test-utils.ts` | Mock data utilities |
| `frontend/__tests__/lib/api.test.ts` | API client tests |
| `.github/workflows/ci.yml` | Primary CI workflow |
| `.github/workflows/codecov.yaml` | Coverage reporting |
| `.github/workflows/node.js.yml` | Frontend CI |
| `.github/workflows/docker.yml` | Docker testing |
| `.github/workflows/bandit.yml` | Security scanning |
| `.github/workflows/snyk-security.yml` | Snyk scanning |
| `.circleci/config.yml` | Secondary CI |

#### 6.6.10.2 Testing Documentation Files

| Path | Relevance |
|------|-----------|
| `TESTING.md` | Testing guide overview |
| `TESTING_GUIDE.md` | Comprehensive testing documentation |
| `TEST_SUMMARY.md` | Test generation summary |
| `tests/README.md` | Test suite documentation |

#### 6.6.10.3 Technical Specification Cross-References

| Section | Relevance |
|---------|-----------|
| 3.1 Technology Stack Overview | Framework versions, tool choices |
| 5.4 CROSS-CUTTING CONCERNS | Performance SLAs, error handling |
| 5.5 DEPLOYMENT ARCHITECTURE | Test environment targets |
| 6.1 Core Services Architecture | Monolithic testing implications |
| 6.3 Integration Architecture | API testing patterns |
| 6.4 Security Architecture | Security testing requirements |
| 6.5 Monitoring and Observability | CI/CD quality gates |

#### 6.6.10.4 External Resources

| Resource | Context |
|----------|---------|
| FastAPI Testing Documentation | Official TestClient patterns |
| pytest Documentation | Test framework reference |
| Jest Documentation | Frontend testing reference |
| React Testing Library | Component testing best practices |
| Codecov | Coverage reporting integration |

# 7. User Interface Design

## 7.1 Overview

### 7.1.1 Executive Summary

The Financial Asset Relationship Database implements a **dual-UI architecture** providing two distinct user interface experiences: a legacy **Gradio UI** for Python-native rapid prototyping and a modern **Next.js Frontend** for production-ready web deployment. Both interfaces share a common visualization foundation built on **Plotly** and expose the same underlying graph engine capabilities through different integration patterns.

This architectural decision enables the system to serve multiple user personas—from data scientists who prefer Python-centric workflows to enterprise users requiring polished web applications—while maintaining consistency in data visualization and business logic.

### 7.1.2 UI Architecture Overview

| Aspect | Gradio UI | Next.js Frontend |
|--------|-----------|------------------|
| **Primary Use Case** | Rapid prototyping, Python development | Production deployment, enterprise users |
| **Technology Stack** | Python/Gradio/Plotly (server-side) | React/TypeScript/Tailwind/Plotly.js (client-side) |
| **Integration Pattern** | Direct Python function calls | REST API via FastAPI |
| **Default Port** | 7860 | 3000 (frontend) + 8000 (API) |
| **Deployment Target** | Local/Docker | Vercel Edge + FastAPI |
| **Responsive Design** | Limited | Full mobile support |

```mermaid
flowchart TB
    subgraph UserInterfaces[User Interface Layer]
        subgraph GradioUI[Gradio UI - Port 7860]
            GradioTabs[6 Tabbed Sections]
            GradioPlotly[Server-Side Plotly]
        end

        subgraph NextJSUI[Next.js Frontend - Port 3000]
            ReactComponents[React Components]
            ClientPlotly[Client-Side Plotly.js]
        end
    end

    subgraph Integration[Integration Layer]
        DirectCall[Direct Python Calls]
        RESTApi[REST API - Port 8000]
    end

    subgraph Backend[Backend Layer]
        GraphEngine[Graph Engine]
        Visualization[Visualization Module]
        Metrics[Metrics Calculator]
    end

    GradioUI --> DirectCall
    NextJSUI --> RESTApi
    DirectCall --> GraphEngine
    RESTApi --> GraphEngine
    GraphEngine --> Visualization
    GraphEngine --> Metrics
```

---

## 7.2 Core UI Technologies

### 7.2.1 Next.js Frontend Technology Stack

The modern frontend is built on an enterprise-grade React framework stack optimized for performance, type safety, and developer experience.

| Technology | Version | Purpose | Configuration Location |
|------------|---------|---------|----------------------|
| **Next.js** | 14.2.35 | React meta-framework with App Router | `frontend/package.json` |
| **React** | 18.2.0 | UI component library | `frontend/package.json` |
| **TypeScript** | ^5.3.0 | Static type checking | `frontend/tsconfig.json` |
| **Tailwind CSS** | 3.3.0 | Utility-first CSS framework | `frontend/tailwind.config.js` |
| **Plotly.js** | ^2.27.0 | 3D visualization rendering | `frontend/package.json` |
| **react-plotly.js** | ^2.6.0 | React Plotly wrapper | `frontend/package.json` |
| **Axios** | Latest | HTTP client for API communication | `frontend/package.json` |

#### Framework Selection Rationale

| Framework | Selection Criteria | Benefit |
|-----------|-------------------|---------|
| Next.js 14 | App Router, SSR capabilities, edge deployment | Modern React patterns with optimized bundling |
| TypeScript | Type safety across components and API contracts | Catch errors at compile time, improved IDE support |
| Tailwind CSS | Rapid UI development, consistent design system | Utility classes reduce CSS overhead |
| Plotly.js | Complex 3D visualization support | Interactive, zoom/rotate/hover capabilities |

### 7.2.2 Gradio UI Technology Stack

The legacy UI provides a Python-native interface optimized for data science workflows and rapid prototyping.

| Technology | Version | Purpose | Configuration Location |
|------------|---------|---------|----------------------|
| **Gradio** | ≥4.0.0,<6.0.0 | Python-native web interface | `requirements.txt` |
| **Plotly** | ≥6.0.0 | Server-side visualization | `requirements.txt` |

#### Gradio Selection Rationale

| Capability | Value Proposition |
|------------|-------------------|
| Zero Frontend Setup | Python developers can create UIs without JavaScript knowledge |
| Rapid Prototyping | Interactive UIs from Python functions in minutes |
| Direct Python Integration | No API serialization overhead for development |
| Component Library | Pre-built UI widgets for common visualization patterns |

### 7.2.3 Shared Visualization Foundation

Both UI implementations leverage Plotly for visualization rendering, ensuring visual consistency across platforms:

```mermaid
flowchart LR
    subgraph VisualizationLayer[Shared Visualization Layer]
        ColorScheme[Asset Color Mapping]
        EdgeColors[Relationship Colors]
        LayoutEngine[3D Layout Calculator]
    end

    subgraph ServerSide[Server-Side - Gradio]
        PlotlyPython[Plotly Python ≥6.0.0]
    end

    subgraph ClientSide[Client-Side - Next.js]
        PlotlyJS[Plotly.js ^2.27.0]
        ReactPlotly[react-plotly.js]
    end

    VisualizationLayer --> PlotlyPython
    VisualizationLayer --> PlotlyJS
    PlotlyJS --> ReactPlotly
```

---

## 7.3 UI Use Cases and Screens

### 7.3.1 Next.js Frontend Screens

The Next.js frontend implements three primary views accessible via tab navigation:

| Tab | Component | Location | Description |
|-----|-----------|----------|-------------|
| **3D Visualization** | `NetworkVisualization` | `frontend/app/components/NetworkVisualization.tsx` | Interactive 3D graph of asset relationships |
| **Metrics & Analytics** | `MetricsDashboard` | `frontend/app/components/MetricsDashboard.tsx` | Grid display of network statistics |
| **Asset Explorer** | `AssetList` | `frontend/app/components/AssetList.tsx` | Filterable, paginated asset table |

## Next.js Screen Structure

```mermaid
flowchart TB
    subgraph NextJSApp[Next.js Application Structure]
        RootLayout[Root Layout<br/>layout.tsx]

        subgraph HomePage[Home Page - page.tsx]
            TabNav[Tab Navigation]

            subgraph TabContent[Tab Content Area]
                VizTab[3D Visualization Tab]
                MetricsTab[Metrics Tab]
                AssetsTab[Asset Explorer Tab]
            end
        end

        RootLayout --> HomePage
        TabNav --> VizTab
        TabNav --> MetricsTab
        TabNav --> AssetsTab
    end

    subgraph Components[Component Library]
        NetworkViz[NetworkVisualization.tsx]
        MetricsDash[MetricsDashboard.tsx]
        AssetsList[AssetList.tsx]
    end

    VizTab --> NetworkViz
    MetricsTab --> MetricsDash
    AssetsTab --> AssetsList
```

### 7.3.2 Gradio UI Screens

The Gradio interface implements six tabbed sections providing comprehensive access to all system capabilities:

| Tab | Description | Primary Components |
|-----|-------------|-------------------|
| **🌐 Network Visualization (2D/3D)** | Interactive network graph with filtering | Plot, Radio buttons, Checkboxes |
| **Metrics & Analytics** | Distribution charts and statistics | Multiple Plot components |
| **Schema & Rules** | Auto-generated data model documentation | Markdown display |
| **Asset Explorer** | Asset detail viewer | Dropdown, JSON displays |
| **Documentation** | Static help documentation | Markdown display |
| **📊 Formulaic Analysis** | Mathematical formula dashboard | Plots, Dropdown, Textbox |

#### Gradio Tab Architecture

```mermaid
flowchart TB
    subgraph GradioApp[Gradio Application - app.py]
        Blocks[gr.Blocks Container]

        subgraph Tabs[Tab Navigation]
            Tab1[🌐 Network Visualization]
            Tab2[Metrics & Analytics]
            Tab3[Schema & Rules]
            Tab4[Asset Explorer]
            Tab5[Documentation]
            Tab6[📊 Formulaic Analysis]
        end

        Blocks --> Tabs
    end

    subgraph Tab1Content[Network Visualization Content]
        ViewMode[2D/3D Toggle]
        LayoutType[Layout Selector]
        RelFilters[8 Relationship Checkboxes]
        GraphPlot[Network Graph Plot]
    end

    subgraph Tab6Content[Formulaic Analysis Content]
        Dashboard[Dashboard Plot]
        CorrelationNet[Correlation Network]
        FormulaSelect[Formula Selector]
        FormulaDetails[Formula Details]
    end

    Tab1 --> Tab1Content
    Tab6 --> Tab6Content
```

### 7.3.3 Feature Parity Matrix

| Feature | Gradio UI | Next.js UI | Notes |
|---------|:---------:|:----------:|-------|
| 3D Network Visualization | ✅ | ✅ | Both use Plotly |
| 2D Network Visualization | ✅ | ❌ | Gradio-only |
| Metrics Dashboard | ✅ | ✅ | Different layouts |
| Asset Explorer | ✅ | ✅ | Next.js has better filtering |
| Asset Class Filtering | ✅ | ✅ | URL-synced in Next.js |
| Sector Filtering | ✅ | ✅ | URL-synced in Next.js |
| Pagination | ❌ | ✅ | Next.js only |
| Relationship Filtering | ✅ | ❌ | 8 checkboxes in Gradio |
| Schema Report | ✅ | ❌ | Gradio-only |
| Documentation Tab | ✅ | ❌ | Gradio-only |
| Formulaic Analysis | ✅ | ❌ | Advanced analytics |
| Mobile Responsive | ⚠️ Limited | ✅ | Full Tailwind support |
| Custom Branding | ⚠️ Limited | ✅ | Full CSS control |
| REST API Access | ❌ | ✅ | Frontend API client |

---

## 7.4 UI/Backend Interaction Boundaries

### 7.4.1 Next.js ↔ FastAPI Interaction

The Next.js frontend communicates with the FastAPI backend via HTTP/JSON through a typed API client layer.

```mermaid
sequenceDiagram
    participant User as User Browser
    participant Page as Next.js Page
    participant Client as API Client<br/>(api.ts)
    participant Axios as Axios HTTP
    participant Backend as FastAPI<br/>(Port 8000)
    participant Graph as Graph Engine

    User->>Page: Navigate to Page
    Page->>Page: useEffect Hook

    par Parallel Data Fetch
        Page->>Client: getMetrics()
        Client->>Axios: GET /api/metrics
        Axios->>Backend: HTTP Request
        Backend->>Graph: calculate_metrics()
        Graph-->>Backend: Metrics Data
        Backend-->>Axios: JSON Response
        Axios-->>Client: Response Object
        Client-->>Page: Metrics
    and
        Page->>Client: getVisualizationData()
        Client->>Axios: GET /api/visualization
        Axios->>Backend: HTTP Request
        Backend->>Graph: get_3d_visualization_data()
        Graph-->>Backend: Node/Edge Data
        Backend-->>Axios: JSON Response
        Axios-->>Client: Response Object
        Client-->>Page: Visualization Data
    end

    Page->>Page: setState(data)
    Page->>User: Render Components
```

#### API Client Configuration

**Location**: `frontend/app/lib/api.ts`

| Configuration | Value | Purpose |
|---------------|-------|---------|
| Base URL | `http://localhost:8000` | FastAPI server address |
| Timeout | Default (Axios) | Request timeout handling |
| Error Handling | Try/catch with console.error | Development debugging |

#### REST Endpoint Consumption

| Endpoint | Method | Frontend Usage | Component |
|----------|--------|----------------|-----------|
| `/api/health` | GET | Health check | Page load validation |
| `/api/assets` | GET | Asset list with filters | `AssetList.tsx` |
| `/api/assets/{id}` | GET | Single asset details | Asset detail view |
| `/api/assets/{id}/relationships` | GET | Asset relationships | Relationship display |
| `/api/relationships` | GET | All relationships | Visualization edges |
| `/api/metrics` | GET | Network statistics | `MetricsDashboard.tsx` |
| `/api/visualization` | GET | 3D graph data | `NetworkVisualization.tsx` |
| `/api/asset-classes` | GET | Filter dropdown options | `AssetList.tsx` |
| `/api/sectors` | GET | Filter dropdown options | `AssetList.tsx` |
| `/token` | POST | JWT authentication | Auth flows |
| `/api/users/me` | GET | Current user info | User profile |

#### Security Boundaries

| Security Control | Implementation | Location |
|-----------------|----------------|----------|
| CORS | Origin allowlist validation | `api/main.py` |
| Rate Limiting | IP-based throttling | `/token`: 5/min, `/api/users/me`: 10/min |
| JWT Authentication | Bearer token header | Protected endpoints |
| Input Validation | Pydantic models | All API endpoints |

### 7.4.2 Gradio ↔ Python Core Interaction

The Gradio UI bypasses the REST API, directly invoking Python functions from the core library.

```mermaid
flowchart LR
    subgraph GradioUI[Gradio UI Layer]
        EventHandler[Event Handlers]
        Components[UI Components]
    end

    subgraph CorePython[Python Core Layer]
        GraphVisuals[graph_visuals.py]
        MetricVisuals[metric_visuals.py]
        SchemaReport[schema_report.py]
        FormulaicVisuals[formulaic_visuals.py]
        AssetGraph[asset_graph.py]
    end

    EventHandler -->|Direct Import| GraphVisuals
    EventHandler -->|Direct Import| MetricVisuals
    EventHandler -->|Direct Import| SchemaReport
    EventHandler -->|Direct Import| FormulaicVisuals
    EventHandler -->|Direct Import| AssetGraph

    GraphVisuals --> Components
    MetricVisuals --> Components
```

#### Direct Integration Pattern

| UI Action | Python Function Call | Source Module |
|-----------|---------------------|---------------|
| Refresh Visualization | `generate_3d_network_graph()` | `src/visualizations/graph_visuals.py` |
| Update Metrics | `create_metric_visuals()` | `src/visualizations/metric_visuals.py` |
| Generate Schema | `SchemaReport.generate_report()` | `src/reports/schema_report.py` |
| Load Asset Details | `graph.get_asset()` | `src/logic/asset_graph.py` |
| Formulaic Dashboard | `create_formulaic_dashboard()` | `src/visualizations/formulaic_visuals.py` |

### 7.4.3 Visualization Data Guardrails

Both UIs implement performance guardrails to prevent browser/client overload with large datasets:

| Guardrail | Next.js Value | Environment Variable | Purpose |
|-----------|---------------|---------------------|---------|
| Maximum Nodes | 500 (default) | `NEXT_PUBLIC_MAX_NODES` | Client rendering limit |
| Maximum Edges | 2000 (default) | `NEXT_PUBLIC_MAX_EDGES` | Edge complexity limit |

**Implementation Location**: `frontend/app/components/NetworkVisualization.tsx`

---

## 7.5 UI Schemas and Type Definitions

### 7.5.1 TypeScript API Contracts

The Next.js frontend defines strict TypeScript interfaces for all API interactions, ensuring type safety across the frontend-backend boundary.

**Location**: `frontend/app/types/api.ts`

#### Core Entity Types

```mermaid
classDiagram
    class Asset {
        +string id
        +string symbol
        +string name
        +string asset_class
        +string sector
        +number price
        +number? market_cap
        +string currency
        +Record~string,any~ additional_fields
    }

    class Relationship {
        +string source_id
        +string target_id
        +string relationship_type
        +number strength
    }

    class Metrics {
        +number total_assets
        +number total_relationships
        +Record~string,number~ asset_classes
        +number avg_degree
        +number max_degree
        +number network_density
    }

    class VisualizationNode {
        +string id
        +string name
        +string symbol
        +string asset_class
        +number x
        +number y
        +number z
        +string color
        +number size
    }

    class VisualizationEdge {
        +string source
        +string target
        +string relationship_type
        +number strength
    }

    class VisualizationData {
        +VisualizationNode[] nodes
        +VisualizationEdge[] edges
    }

    VisualizationData *-- VisualizationNode
    VisualizationData *-- VisualizationEdge
```

### 7.5.2 Pydantic Response Models

The FastAPI backend defines Pydantic models that serialize Python objects to JSON responses consumed by the frontend.

**Location**: `api/main.py`

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `AssetResponse` | Single asset serialization | `id`, `symbol`, `name`, `asset_class`, `sector`, `price`, `market_cap`, `currency`, `additional_fields` |
| `RelationshipResponse` | Relationship edge data | `source_id`, `target_id`, `relationship_type`, `strength` |
| `MetricsResponse` | Network statistics | `total_assets`, `total_relationships`, `asset_classes`, `avg_degree`, `max_degree`, `network_density`, `relationship_density` |
| `VisualizationDataResponse` | 3D graph payload | `nodes: List[Dict]`, `edges: List[Dict]` |

### 7.5.3 Type Contract Alignment

The TypeScript and Pydantic models maintain structural alignment to ensure seamless serialization:

| TypeScript Type | Pydantic Model | Validation |
|-----------------|----------------|------------|
| `Asset` | `AssetResponse` | ✅ Aligned |
| `Relationship` | `RelationshipResponse` | ✅ Aligned |
| `Metrics` | `MetricsResponse` | ✅ Aligned |
| `VisualizationData` | `VisualizationDataResponse` | ✅ Aligned |

---

## 7.6 Screen Specifications

### 7.6.1 Next.js: 3D Visualization Screen

**Component**: `NetworkVisualization.tsx`

**Location**: `frontend/app/components/NetworkVisualization.tsx`

#### Screen States

| State | Condition | Display |
|-------|-----------|---------|
| `loading` | Data fetching in progress | Loading spinner |
| `ready` | Data loaded, within limits | Interactive 3D graph |
| `empty` | No nodes returned | "No data available" message |
| `tooLarge` | Nodes > MAX_NODES or Edges > MAX_EDGES | Size warning with counts |

#### Visual Elements

| Element | Implementation | Interaction |
|---------|---------------|-------------|
| 3D Node Graph | Plotly Scatter3d traces | Rotate, zoom, pan |
| Node Markers | Color-coded by asset class | Hover for tooltip |
| Edge Lines | Colored by relationship type | Visual connection |
| Hover Tooltip | Asset symbol, name, class | On node hover |

#### Dynamic Import Pattern

The Plotly component uses Next.js dynamic import with SSR disabled to prevent server-side rendering errors:

```mermaid
flowchart TB
    subgraph SSRSafety[SSR Safety Pattern]
        DynamicImport[dynamic import<br/>ssr: false]
        ClientOnly[Client-Only Rendering]
        PlotlyLoad[Plotly.js Load]
        GraphRender[3D Graph Render]
    end

    DynamicImport --> ClientOnly
    ClientOnly --> PlotlyLoad
    PlotlyLoad --> GraphRender
```

### 7.6.2 Next.js: Metrics Dashboard Screen

**Component**: `MetricsDashboard.tsx`

**Location**: `frontend/app/components/MetricsDashboard.tsx`

#### Metrics Display Grid

| Metric | Label | Format | Grid Position |
|--------|-------|--------|---------------|
| `total_assets` | Total Assets | Integer | Row 1, Col 1 |
| `total_relationships` | Total Relationships | Integer | Row 1, Col 2 |
| `avg_degree` | Average Degree | 2 decimal places | Row 1, Col 3 |
| `max_degree` | Maximum Degree | Integer | Row 2, Col 1 |
| `network_density` | Network Density | Percentage (×100) | Row 2, Col 2 |
| `relationship_density` | Relationship Density | Percentage (×100) | Row 2, Col 3 |

#### Asset Class Distribution

The component renders asset class counts from the `asset_classes` dictionary:

| Asset Class | Display Color | Source Key |
|-------------|---------------|------------|
| Equity | Blue | `asset_classes.Equity` |
| Fixed Income | Green | `asset_classes['Fixed Income']` |
| Commodity | Orange | `asset_classes.Commodity` |
| Currency | Red | `asset_classes.Currency` |
| Derivative | Purple | `asset_classes.Derivative` |

### 7.6.3 Next.js: Asset Explorer Screen

**Component**: `AssetList.tsx`

**Location**: `frontend/app/components/AssetList.tsx`

#### Filter Controls

| Control | Type | Options | State Management |
|---------|------|---------|------------------|
| Asset Class Filter | Dropdown Select | All asset classes + "All" | URL query param |
| Sector Filter | Dropdown Select | All sectors + "All" | URL query param |
| Page Size | Dropdown Select | 10, 20, 50, 100 | Component state |

#### URL State Synchronization

The Asset Explorer implements URL-synced state using Next.js navigation hooks:

```mermaid
flowchart LR
    subgraph URLState[URL State Management]
        URLParams[URL Search Params]
        ComponentState[React Component State]
        FilterControls[Filter Dropdowns]
    end

    URLParams -->|Read on mount| ComponentState
    FilterControls -->|onChange| URLParams
    URLParams -->|Browser history| Navigation
    ComponentState -->|Render| FilterControls
```

#### Table Columns

| Column | Field | Width | Sortable |
|--------|-------|-------|----------|
| Symbol | `symbol` | Auto | No |
| Name | `name` | Auto | No |
| Asset Class | `asset_class` | Auto | No |
| Sector | `sector` | Auto | No |
| Price | `price` | Auto | No |
| Market Cap | `market_cap` | Auto | No |

#### Pagination Controls

| Control | Behavior | Disabled Condition |
|---------|----------|-------------------|
| Previous Button | Decrement page | `page === 1` |
| Next Button | Increment page | `page >= totalPages` |
| Page Indicator | "Page X of Y" | N/A |

### 7.6.4 Gradio: Network Visualization Tab

**Location**: `app.py` (lines 386-450)

#### Control Panel

| Control | Type | Options | Default |
|---------|------|---------|---------|
| View Mode | Radio | "3D View", "2D View" | "3D View" |
| Layout Type | Dropdown | "spring", "circular", "grid" | "spring" |
| Show Direction Arrows | Checkbox | Boolean | `True` |

#### Relationship Visibility Checkboxes

| Checkbox | Relationship Type | Default |
|----------|-------------------|---------|
| Same Sector | `same_sector` | `True` |
| Market Cap Similar | `market_cap_similar` | `True` |
| Correlation | `correlation` | `True` |
| Corporate Bond → Equity | `corporate_bond_to_equity` | `True` |
| Commodity ↔ Currency | `commodity_currency` | `True` |
| Income Comparison | `income_comparison` | `True` |
| Regulatory Impact | `regulatory_impact` | `True` |
| Show All Relationships | All types | `False` |

#### Action Buttons

| Button | Function | Behavior |
|--------|----------|----------|
| Refresh | `refresh_all_outputs()` | Regenerate all visualizations |
| Reset View | `reset_visualization()` | Clear filters, restore defaults |

### 7.6.5 Gradio: Formulaic Analysis Tab

**Location**: `app.py` (lines 520-590)

#### Dashboard Components

| Component | Type | Content |
|-----------|------|---------|
| Formula Dashboard | Plot | Overview of all formula categories |
| Correlation Network | Plot | Asset correlation visualization |
| Metric Comparison | Plot | Formula metric comparisons |
| Formula Selector | Dropdown | Individual formula selection |
| Formula Details | Textbox | LaTeX formula, variables, example |
| Summary | Textbox | Analysis summary text |

---

## 7.7 User Interactions

### 7.7.1 Next.js Page Load Flow

The Next.js frontend implements a client-side data loading pattern with comprehensive error handling and retry capabilities.

```mermaid
flowchart TB
    subgraph NextJSPageLoad[Next.js Page Load Workflow]
        PageMount([Page Mount]) --> SetLoading[Set Loading<br/>State = true]
        SetLoading --> FetchData[Promise.all:<br/>getMetrics()<br/>getVisualizationData()]

        FetchData --> FetchResult{Fetch<br/>Successful?}

        FetchResult -->|Yes| StoreData[Store Data<br/>in State]
        StoreData --> ClearLoading[Clear Loading<br/>State]
        ClearLoading --> RenderUI[Render UI<br/>Components]
        RenderUI --> PageReady([Page Ready])

        FetchResult -->|No| SetError[Set Error<br/>State]
        SetError --> ShowRetry[Show Retry<br/>Button]
        ShowRetry --> UserRetry{User Clicks<br/>Retry?}
        UserRetry -->|Yes| SetLoading
        UserRetry -->|No| WaitAction([Wait for<br/>User Action])
    end
```

### 7.7.2 Tab Navigation State Machine

Both UIs implement tab-based navigation with distinct state transitions:

```mermaid
stateDiagram-v2
    [*] --> Visualization: Default Tab

    Visualization --> Metrics: Tab Click
    Visualization --> Assets: Tab Click

    Metrics --> Visualization: Tab Click
    Metrics --> Assets: Tab Click

    Assets --> Visualization: Tab Click
    Assets --> Metrics: Tab Click

    note right of Visualization: 3D Network Graph
    note right of Metrics: Statistics Dashboard
    note right of Assets: Filterable Table
```

### 7.7.3 Gradio Event Flow

The Gradio interface manages state through an event-driven architecture with real-time visualization updates:

```mermaid
flowchart TB
    subgraph GradioEventFlow[Gradio UI Event Flow]
        AppStart([Gradio App<br/>Starts]) --> InitGraph[Initialize<br/>Graph State]
        InitGraph --> CreateInterface[Create Blocks<br/>Interface]
        CreateInterface --> SetupTabs[Setup 6<br/>Tabs]
        SetupTabs --> WireEvents[Wire Event<br/>Handlers]
        WireEvents --> LaunchServer[Launch Server<br/>Port 7860]
        LaunchServer --> WaitEvent([Wait for<br/>User Event])

        WaitEvent --> UserAction{User<br/>Action Type}

        UserAction -->|Refresh| RefreshAll[refresh_all_outputs()]
        UserAction -->|Filter Change| UpdateViz[refresh_visualization()]
        UserAction -->|Tab Change| LoadTab[Load Tab<br/>Content]
        UserAction -->|Asset Select| UpdateAsset[update_asset_info()]

        RefreshAll --> WaitEvent
        UpdateViz --> WaitEvent
        LoadTab --> WaitEvent
        UpdateAsset --> WaitEvent
    end
```

### 7.7.4 3D Visualization Interactions

| Interaction | Action | Result |
|-------------|--------|--------|
| **Drag** | Click and drag on graph area | Rotate 3D view |
| **Scroll** | Mouse wheel | Zoom in/out |
| **Hover** | Mouse over node | Show tooltip with asset details |
| **Click** | Click on node | (Future: Asset detail view) |
| **Double-click** | Double-click on background | Reset view |

### 7.7.5 Asset Explorer Interactions

| Interaction | Action | Result |
|-------------|--------|--------|
| **Filter Change** | Select asset class/sector | Update table, modify URL params |
| **Page Size Change** | Select new page size | Reset to page 1, update display |
| **Previous Page** | Click Previous button | Load previous page |
| **Next Page** | Click Next button | Load next page |
| **Browser Back** | Browser back button | Restore previous filter state |

### 7.7.6 Error Recovery Flow

```mermaid
flowchart TB
    subgraph ErrorRecovery[Frontend Error Recovery]
        ErrorDetected([Error<br/>Detected]) --> ErrorCategory{Error<br/>Category}

        ErrorCategory -->|Network Error| NetError[Set Error:<br/>Network Unavailable]
        ErrorCategory -->|API Error| APIError[Set Error:<br/>API Error Message]
        ErrorCategory -->|Render Error| RenderError[Set Error:<br/>Display Error]

        NetError --> ShowRetryUI[Show Retry<br/>Button]
        APIError --> ShowRetryUI
        RenderError --> ShowRefresh[Show Refresh<br/>Page Option]

        ShowRetryUI --> UserRetries{User<br/>Retries?}
        UserRetries -->|Yes| ClearError[Clear Error<br/>State]
        ClearError --> ReloadData[Reload<br/>Data]
        ReloadData --> Success{Success?}
        Success -->|Yes| Normal([Normal<br/>Operation])
        Success -->|No| ErrorDetected
        UserRetries -->|No| WaitUser([Wait for<br/>User])

        ShowRefresh --> UserRefresh{User<br/>Refreshes?}
        UserRefresh -->|Yes| PageReload[Full Page<br/>Reload]
        PageReload --> Normal
    end
```

---

## 7.8 Visual Design Specifications

### 7.8.1 Asset Class Color Scheme

A consistent color palette maps asset classes to visual representations across both UIs:

| Asset Class | Node Color | Hex Code | Usage |
|-------------|------------|----------|-------|
| **Equity** | Blue | `#1f77b4` | Stocks and equity instruments |
| **Fixed Income** | Green | `#2ca02c` | Bonds and debt instruments |
| **Commodity** | Orange | `#ff7f0e` | Physical commodity futures |
| **Currency** | Red | `#d62728` | Foreign exchange pairs |
| **Derivative** | Purple | `#9467bd` | Derivative instruments |

**Source**: `src/visualizations/graph_visuals.py`

### 7.8.2 Relationship Edge Colors

Relationship types are distinguished by edge colors in the network visualization:

| Relationship Type | Edge Color | Hex Code |
|-------------------|------------|----------|
| `same_sector` | Red | `#FF6B6B` |
| `market_cap_similar` | Teal | `#4ECDC4` |
| `correlation` | Blue | `#45B7D1` |
| `corporate_bond_to_equity` | Green | `#96CEB4` |
| `commodity_currency` | Yellow | `#FFEAA7` |
| `income_comparison` | Plum | `#DDA0DD` |
| `regulatory_impact` | Light Salmon | `#FFA07A` |
| Default | Gray | `#888888` |

**Source**: `src/visualizations/graph_visuals.py` (lines 18-29)

### 7.8.3 CSS Design System (Next.js)

#### Tailwind CSS Configuration

**Location**: `frontend/tailwind.config.js`

| Configuration | Value | Purpose |
|---------------|-------|---------|
| Content Paths | `./pages/**`, `./components/**`, `./app/**` | Purge unused CSS |
| Theme | Extended defaults | Custom design tokens |
| Plugins | None | Minimal footprint |

#### Global CSS Variables

**Location**: `frontend/app/globals.css`

| CSS Variable | Light Mode Value | Purpose |
|--------------|------------------|---------|
| `--foreground-rgb` | `0, 0, 0` | Text color |
| `--background-start-rgb` | `214, 219, 220` | Gradient start |
| `--background-end-rgb` | `255, 255, 255` | Gradient end |

#### Background Gradient

The application uses a subtle vertical gradient:
- Start: `rgb(214, 219, 220)` (light gray)
- End: `rgb(255, 255, 255)` (white)
- Direction: Top to bottom

### 7.8.4 Responsive Design Patterns

The Next.js frontend implements mobile-first responsive design using Tailwind breakpoints:

| Breakpoint | Screen Size | Grid Columns (MetricsDashboard) |
|------------|-------------|--------------------------------|
| Default | < 768px | 1 column |
| `md:` | ≥ 768px | 2 columns |
| `lg:` | ≥ 1024px | 3 columns |

#### Component Responsive Classes

| Component | Responsive Pattern |
|-----------|-------------------|
| Container | `container mx-auto px-4` |
| Card | `bg-white rounded-lg shadow-md p-6` |
| Grid | `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4` |
| Button | `px-4 py-2 rounded-md` |

### 7.8.5 Application Metadata

## Next.js Metadata

**Location**: `frontend/app/layout.tsx`

| Property | Value |
|----------|-------|
| Title | "Financial Asset Relationship Network" |
| Description | "Interactive 3D visualization of interconnected financial assets" |

#### Gradio Application Title

**Location**: `app.py`

| Property | Value |
|----------|-------|
| Title | "Financial Asset Relationship Database Visualization" |
| Default Port | 7860 |

---

## 7.9 Testing Strategy

### 7.9.1 Frontend Testing Framework

The Next.js frontend implements comprehensive testing using Jest and React Testing Library:

| Tool | Version | Purpose |
|------|---------|---------|
| Jest | ^29.7.0 | Test runner and framework |
| @testing-library/react | ^14.1.2 | React component testing |
| @testing-library/jest-dom | ^6.4.0 | DOM assertions |
| jest-environment-jsdom | ^29.7.0 | DOM simulation |

**Configuration Location**: `frontend/jest.config.js`, `frontend/jest.setup.js`

### 7.9.2 Frontend Test Organization

```
frontend/__tests__/
├── test-utils.ts                    # Centralized mock data
├── lib/
│   ├── api.test.ts                 # API client tests
│   └── api-axios-compatibility.test.ts
├── components/
│   ├── AssetList.test.tsx          # Asset list component tests
│   ├── MetricsDashboard.test.tsx   # Metrics dashboard tests
│   └── NetworkVisualization.test.tsx # Visualization tests
└── app/
    └── page.test.tsx               # Page-level tests
```

### 7.9.3 Component Test Coverage

| Component | Test Scenarios | Coverage Focus |
|-----------|----------------|----------------|
| `AssetList` | Render assets, filter by class, pagination | User filtering flows |
| `MetricsDashboard` | Display metrics, handle loading, show errors | Data presentation |
| `NetworkVisualization` | 3D graph rendering, node interaction | Plotly integration |
| `page.tsx` | Tab switching, data loading, retry mechanisms | Page lifecycle |

### 7.9.4 Mock Data Utilities

**Location**: `frontend/__tests__/test-utils.ts`

| Export | Type | Purpose |
|--------|------|---------|
| `mockAssets` | `Asset[]` | Sample asset collection |
| `mockMetrics` | `Metrics` | Network metrics data |
| `mockVisualization` | `VisualizationData` | 3D graph data |
| `mockRelationships` | `Relationship[]` | Sample relationships |

### 7.9.5 Test Execution Commands

| Command | Description |
|---------|-------------|
| `npm test` | Run all frontend tests |
| `npm test -- --coverage` | Tests with coverage report |
| `npm test -- --watch` | Watch mode for development |
| `npm run test:ci` | CI-optimized execution |

---

## 7.10 Accessibility Considerations

### 7.10.1 Current Implementation

| Accessibility Feature | Status | Implementation |
|----------------------|--------|----------------|
| Semantic HTML | ✅ Implemented | Proper heading hierarchy |
| Color Contrast | ✅ Implemented | Tailwind default palette |
| Keyboard Navigation | ⚠️ Partial | Tab navigation works |
| Screen Reader Support | ⚠️ Limited | Labels on form controls |
| ARIA Attributes | ⚠️ Partial | Button roles |

### 7.10.2 Planned Enhancements

| Enhancement | Priority | Tool |
|-------------|----------|------|
| Full ARIA labeling | Medium | Manual implementation |
| Accessibility testing | Medium | axe-core integration |
| Keyboard shortcuts | Low | Custom implementation |
| High contrast mode | Low | Tailwind dark mode |

---

## 7.11 References

### 7.11.1 Source Files Examined

| Path | Relevance |
|------|-----------|
| `frontend/app/page.tsx` | Main Next.js page with tab navigation |
| `frontend/app/layout.tsx` | Root layout with metadata |
| `frontend/app/globals.css` | Global CSS styles |
| `frontend/tailwind.config.js` | Tailwind configuration |
| `frontend/app/components/NetworkVisualization.tsx` | 3D visualization component |
| `frontend/app/components/MetricsDashboard.tsx` | Metrics grid component |
| `frontend/app/components/AssetList.tsx` | Asset explorer component |
| `frontend/app/types/api.ts` | TypeScript API contracts |
| `frontend/app/lib/api.ts` | Axios API client |
| `frontend/package.json` | Frontend dependencies |
| `frontend/jest.config.js` | Jest configuration |
| `frontend/jest.setup.js` | Jest environment setup |
| `frontend/__tests__/test-utils.ts` | Mock data utilities |
| `app.py` | Gradio UI implementation |
| `api/main.py` | FastAPI endpoints and response models |
| `src/visualizations/graph_visuals.py` | Visualization color schemes |
| `requirements.txt` | Python dependencies |
| `UI_COMPARISON.md` | UI feature comparison |

### 7.11.2 Technical Specification Cross-References

| Section | Relevance |
|---------|-----------|
| 2.1 Feature Catalog | Feature requirements (F-016, F-017) |
| 3.3 Frameworks & Libraries | Technology stack details |
| 4.4 Frontend Workflows | Page load and event flows |
| 4.5 Error Handling Workflows | Error recovery patterns |
| 5.1 HIGH-LEVEL ARCHITECTURE | System architecture overview |
| 5.2 COMPONENT DETAILS | Component specifications |
| 6.4 Security Architecture | Authentication and CORS |
| 6.6 Testing Strategy | Frontend testing approach |

### 7.11.3 Frontend Component Locations

| Component | File Path |
|-----------|-----------|
| Root Layout | `frontend/app/layout.tsx` |
| Home Page | `frontend/app/page.tsx` |
| Network Visualization | `frontend/app/components/NetworkVisualization.tsx` |
| Metrics Dashboard | `frontend/app/components/MetricsDashboard.tsx` |
| Asset List | `frontend/app/components/AssetList.tsx` |
| API Client | `frontend/app/lib/api.ts` |
| Type Definitions | `frontend/app/types/api.ts` |
| Test Utilities | `frontend/__tests__/test-utils.ts` |

# 8. Infrastructure

## 8.1 Executive Overview

The Financial Asset Relationship Database implements a **hybrid deployment architecture** supporting multiple deployment targets to accommodate varying operational requirements. The infrastructure design prioritizes deployment flexibility, operational simplicity, and cost-effectiveness while maintaining security and reliability standards appropriate for financial data applications.

### 8.1.1 Infrastructure Philosophy

The system follows these core infrastructure principles:

| Principle | Implementation | Rationale |
|-----------|----------------|-----------|
| **Multi-Target Deployment** | Vercel, Docker, Local | Supports development through production workflows |
| **Serverless-First Production** | Vercel Edge Functions | Automatic scaling, global distribution, minimal ops |
| **Container-Based Portability** | Docker with Docker Compose | Consistent environments across all deployment stages |
| **Infrastructure as Code** | Configuration files, no imperative scripts | Reproducible, version-controlled infrastructure |
| **Security by Default** | Non-root containers, TLS enforcement | Defense in depth from build through production |

### 8.1.2 Infrastructure Architecture Diagram

```mermaid
flowchart TB
    subgraph ExternalUsers[External Access Layer]
        Users([End Users])
        Developers([Developers])
        CI([CI/CD Pipelines])
    end

    subgraph EdgeLayer[Edge & CDN Layer]
        VercelEdge[Vercel Edge Network<br/>Global CDN]
        TLS[TLS Termination<br/>HTTPS Enforcement]
    end

    subgraph ComputeLayer[Compute Layer]
        subgraph VercelCompute[Vercel Serverless]
            NextSSR[Next.js SSR<br/>@vercel/next]
            PythonLambda[Python Functions<br/>@vercel/python<br/>50MB max]
        end

        subgraph DockerCompute[Docker Deployment]
            AppContainer[app container<br/>python:3.11-slim<br/>Port 7860]
        end

        subgraph LocalDev[Local Development]
            FastAPILocal[FastAPI<br/>Port 8000]
            NextJSLocal[Next.js<br/>Port 3000]
            GradioLocal[Gradio<br/>Port 7860]
        end
    end

    subgraph DataLayer[Data Layer]
        InMemGraph[In-Memory Graph<br/>Dict-based Storage]
        SQLiteAuth[(SQLite<br/>Auth Database)]
        JSONCache[(JSON File Cache<br/>Atomic Writes)]
    end

    subgraph ExternalServices[External Services]
        YahooFinance[Yahoo Finance API<br/>via yfinance]
        GHCR[GitHub Container Registry<br/>ghcr.io]
        GitHubActions[GitHub Actions<br/>CI/CD]
    end

    Users --> VercelEdge
    Developers --> LocalDev
    CI --> GitHubActions

    VercelEdge --> TLS
    TLS --> VercelCompute

    VercelCompute --> InMemGraph
    DockerCompute --> InMemGraph
    LocalDev --> InMemGraph

    InMemGraph --> SQLiteAuth
    InMemGraph --> JSONCache
    InMemGraph --> YahooFinance

    GitHubActions --> GHCR
    GitHubActions --> VercelCompute
```

---

## 8.2 Deployment Environment

### 8.2.1 Target Environment Assessment

#### 8.2.1.1 Environment Type Classification

The Financial Asset Relationship Database operates in a **hybrid cloud/local** environment model:

| Environment Type | Primary Use | Technology | Scale |
|------------------|-------------|------------|-------|
| **Local Development** | Feature development, debugging | Native Python/Node.js | Single developer |
| **Docker Container** | Integration testing, self-hosted production | Docker, Docker Compose | Single to small cluster |
| **Vercel Serverless** | Production SaaS deployment | Vercel Edge Network | Auto-scaling global |
| **Google Cloud Run** | Alternative cloud deployment | GCR, Cloud Run | Auto-scaling regional |

#### 8.2.1.2 Geographic Distribution

| Deployment Target | Geographic Strategy | Implementation |
|-------------------|---------------------|----------------|
| Vercel | Global Edge Network | Automatic CDN distribution to nearest edge location |
| Docker | Single region | Deployer-determined; no built-in geo-distribution |
| Cloud Run | Regional with optional multi-region | Configurable via `REGION` environment variable |

#### 8.2.1.3 Resource Requirements

**Compute Requirements:**

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| **CPU** | 1 vCPU | 2 vCPU | Auto-scaling (Vercel) |
| **Memory** | 512 MB | 2 GB | 2-4 GB (Vercel Lambda) |
| **Disk** | 100 MB | 500 MB | N/A (ephemeral) |
| **Network** | Standard | Low latency | Edge-optimized |

**Application Constraints:**

| Constraint ID | Description | Impact | Mitigation |
|---------------|-------------|--------|------------|
| C-001 | In-memory graph limits scalability | < 500 nodes optimal | Database persistence option |
| C-002 | Single-user JWT authentication | Limited concurrent sessions | Session isolation per token |
| C-003 | Yahoo Finance API rate limits | Data freshness affected | JSON file caching with atomic writes |
| C-004 | Browser memory limits visualization | Large graph rendering issues | MAX_NODES/MAX_EDGES guardrails |
| C-005 | Vercel Lambda size limit | 50MB maximum | Dependency optimization required |

#### 8.2.1.4 Port Configuration Matrix

| Service | Port | Protocol | Exposure |
|---------|------|----------|----------|
| FastAPI Backend | 8000 | HTTP/HTTPS | API endpoints |
| Next.js Frontend | 3000 | HTTP/HTTPS | User interface |
| Gradio Legacy UI | 7860 | HTTP | Legacy interface |
| PostgreSQL (optional) | 5432 | TCP | Database (internal only) |

### 8.2.2 Environment Management

#### 8.2.2.1 Infrastructure as Code Components

| File | Purpose | Platform | Key Configuration |
|------|---------|----------|-------------------|
| `Dockerfile` | Container image definition | Docker | Base image, security, health check |
| `docker-compose.yml` | Multi-service orchestration | Docker Compose | Service definitions, volumes, networking |
| `vercel.json` | Serverless deployment config | Vercel | Builders, routes, lambda size |
| `Makefile` | Build and deployment automation | Cross-platform | Targets for common operations |
| `pyproject.toml` | Python project metadata | Python ecosystem | Build system, tool configs |
| `.env.example` | Environment variable template | All environments | Required and optional variables |

#### 8.2.2.2 Environment Variables Configuration

**Required Environment Variables:**

| Variable | Purpose | Default | Criticality |
|----------|---------|---------|-------------|
| `SECRET_KEY` | JWT signing key | None | **Critical** - App fails without |
| `DATABASE_URL` | SQLite connection string | None | **Critical** - App fails without |
| `ADMIN_USERNAME` | Initial admin account | None | Required for user seeding |
| `ADMIN_PASSWORD` | Initial admin password | None | Required for user seeding |

**Optional Environment Variables:**

| Variable | Purpose | Default |
|----------|---------|---------|
| `ENV` | Environment mode | `development` |
| `ALLOWED_ORIGINS` | CORS allowlist | Built-in defaults |
| `USE_REAL_DATA_FETCHER` | Yahoo Finance toggle | `false` |
| `REAL_DATA_CACHE_PATH` | Cache file location | Default path |
| `GRAPH_CACHE_PATH` | Graph serialization path | Default path |
| `NEXT_PUBLIC_API_URL` | Frontend API endpoint | `http://localhost:8000` |
| `GRADIO_SERVER_NAME` | Gradio binding address | `0.0.0.0` |
| `GRADIO_SERVER_PORT` | Gradio port | `7860` |

#### 8.2.2.3 Environment Promotion Strategy

```mermaid
flowchart LR
    subgraph Development[Development Stage]
        LocalDev[Local Development<br/>Feature Branches]
        DevTest[Developer Testing<br/>run-dev.sh]
    end

    subgraph Integration[Integration Stage]
        PR[Pull Request<br/>Preview Deploy]
        QualityGates[Quality Gates<br/>CI Pipeline]
    end

    subgraph Staging[Staging Stage]
        DockerValidate[Docker Build<br/>Validation]
        IntegrationTests[Integration<br/>Tests]
    end

    subgraph Production[Production Stage]
        VercelProd[Vercel Production<br/>Auto-Deploy]
        DockerProd[Docker Registry<br/>GHCR Publish]
    end

    LocalDev --> DevTest
    DevTest --> PR
    PR --> QualityGates
    QualityGates --> DockerValidate
    DockerValidate --> IntegrationTests
    IntegrationTests --> VercelProd
    IntegrationTests --> DockerProd
```

**Promotion Rules:**

| Stage Transition | Trigger | Gates |
|------------------|---------|-------|
| Development → Integration | Pull Request opened | Automated CI initiation |
| Integration → Staging | PR review approved | All quality gates passed |
| Staging → Production | Merge to `main` | Security scans, Docker build success |

#### 8.2.2.4 Backup and Disaster Recovery

| Component | Backup Strategy | Recovery Time Objective |
|-----------|-----------------|------------------------|
| **Application Code** | Git repository (GitHub) | Immediate (re-deploy) |
| **Docker Images** | GHCR versioned tags | < 5 minutes |
| **User Database (SQLite)** | Volume mount persistence | Container restart |
| **Graph Cache (JSON)** | Volume mount persistence | Cache rebuild < 30 seconds |
| **Configuration** | Git-tracked (except secrets) | Immediate (re-deploy) |

---

## 8.3 Cloud Services

### 8.3.1 Primary Platform: Vercel

Vercel serves as the primary production deployment platform, providing serverless hosting optimized for Next.js applications with Python serverless function support.

#### 8.3.1.1 Platform Selection Justification

| Criterion | Vercel Advantage | Alternative Consideration |
|-----------|------------------|---------------------------|
| **Next.js Integration** | Native framework support | Manual configuration on other platforms |
| **Python Functions** | Built-in `@vercel/python` builder | Requires container deployment elsewhere |
| **Global Edge Network** | Automatic CDN distribution | Manual CDN setup required |
| **Preview Deployments** | Automatic per-PR previews | Additional CI configuration needed |
| **Zero-Config Scaling** | Automatic scaling | Manual scaling configuration |

#### 8.3.1.2 Vercel Build Configuration

**Source:** `vercel.json`

```json
{
  "builds": [
    {
      "src": "api/main.py",
      "use": "@vercel/python",
      "config": { "maxLambdaSize": "50mb" }
    },
    {
      "src": "frontend/package.json",
      "use": "@vercel/next"
    }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "api/main.py" },
    { "src": "/(.*)", "dest": "frontend/$1" }
  ]
}
```

| Component | Builder | Configuration |
|-----------|---------|---------------|
| Backend API | `@vercel/python` | maxLambdaSize: 50MB |
| Frontend | `@vercel/next` | Default Next.js settings |

#### 8.3.1.3 Route Configuration

| Pattern | Destination | Purpose |
|---------|-------------|---------|
| `/api/(.*)` | `api/main.py` | Backend API routes |
| `/(.*)` | `frontend/$1` | Frontend static/SSR pages |

### 8.3.2 High Availability Design

#### 8.3.2.1 Vercel High Availability Architecture

```mermaid
flowchart TB
    subgraph GlobalHA[Vercel High Availability]
        subgraph EdgeNetwork[Global Edge Network]
            Edge1[Edge Location 1<br/>US-East]
            Edge2[Edge Location 2<br/>EU-West]
            Edge3[Edge Location 3<br/>APAC]
        end

        subgraph ComputeRegions[Compute Regions]
            Lambda1[Lambda Instance<br/>Primary]
            Lambda2[Lambda Instance<br/>Replica]
        end

        subgraph StaticAssets[Static Asset CDN]
            CDN[Global CDN<br/>Static Files]
        end
    end

    Users([Global Users]) --> Edge1
    Users --> Edge2
    Users --> Edge3

    Edge1 --> Lambda1
    Edge2 --> Lambda1
    Edge3 --> Lambda2

    Edge1 --> CDN
    Edge2 --> CDN
    Edge3 --> CDN
```

| HA Component | Implementation | Benefit |
|--------------|----------------|---------|
| Edge Distribution | Multiple global edge locations | Low latency worldwide |
| Function Replicas | Automatic instance scaling | Handle traffic spikes |
| Static CDN | Globally distributed cache | Fast asset delivery |
| Health Monitoring | Platform-level monitoring | Automatic unhealthy instance removal |

#### 8.3.2.2 Docker High Availability

| Strategy | Implementation | Configuration |
|----------|----------------|---------------|
| Health Checks | HTTP probe on container | 30s interval, 3 retries |
| Restart Policy | `unless-stopped` | Automatic recovery |
| Volume Persistence | Mounted data volumes | Data survives restarts |

### 8.3.3 Alternative Platform: Google Cloud Run

A deployment template is available for Google Cloud Run as an alternative cloud deployment option.

**Source:** `.github/workflows/google-cloudrun-docker.yml`

| Configuration | Purpose |
|---------------|---------|
| Workload Identity Federation | OIDC authentication for deployment |
| Artifact Registry | Container image storage |
| Cloud Run Service | Serverless container hosting |

**Required Google Cloud APIs:**
- Artifact Registry API
- Cloud Run Admin API
- IAM Credentials API

### 8.3.4 Cost Optimization Strategy

#### 8.3.4.1 Vercel Cost Considerations

| Resource | Hobby (Free) | Pro ($20/user/month) | Optimization Strategy |
|----------|--------------|---------------------|----------------------|
| **Bandwidth** | 100 GB/month | 1 TB/month | Enable compression, optimize assets |
| **Function Invocations** | 150K/month | 1M/month | Implement caching |
| **Active CPU Time** | Limited | 40 hours/month | Optimize function execution |
| **Edge Requests** | Included | 10M/month | Static asset CDN caching |

#### 8.3.4.2 Infrastructure Cost Estimates

| Deployment Model | Monthly Cost Estimate | Best For |
|------------------|----------------------|----------|
| **Local Development** | $0 | Development, testing |
| **Vercel Hobby** | $0 | Personal projects, demos |
| **Vercel Pro** | $20/user | Small teams, production |
| **Docker Self-Hosted** | Infrastructure cost only | Full control requirements |
| **Google Cloud Run** | ~$5-50 (usage-based) | GCP ecosystem integration |

---

## 8.4 Containerization

### 8.4.1 Container Platform: Docker

The system uses Docker for containerization, providing consistent runtime environments across development, testing, and production deployments.

#### 8.4.1.1 Base Image Strategy

**Source:** `Dockerfile`

| Attribute | Value | Rationale |
|-----------|-------|-----------|
| **Base Image** | `python:3.11-slim` | Minimal attack surface, small image size |
| **Python Version** | 3.11 | Stable, performance improvements |
| **Image Variant** | `slim` | No unnecessary development tools |

#### 8.4.1.2 Container Security Architecture

```mermaid
flowchart TB
    subgraph ContainerSecurity[Container Security Layers]
        subgraph BuildPhase[Build Phase Security]
            BaseImage[Minimal Base Image<br/>python:3.11-slim]
            NoCache[No Pip Cache<br/>--no-cache-dir]
            NoBytecode[No Bytecode<br/>PYTHONDONTWRITEBYTECODE=1]
        end

        subgraph RuntimeSecurity[Runtime Security]
            NonRoot[Non-Root User<br/>appuser UID 1000]
            ReadOnly[Minimal Permissions<br/>Application Directory Only]
            HealthCheck[Health Monitoring<br/>HTTP Probe]
        end

        subgraph NetworkSecurity[Network Security]
            SinglePort[Single Port Exposure<br/>7860]
            InternalOnly[Internal Services<br/>No External Access]
        end
    end

    BaseImage --> NoCache
    NoCache --> NoBytecode
    NoBytecode --> NonRoot
    NonRoot --> ReadOnly
    ReadOnly --> HealthCheck
    HealthCheck --> SinglePort
    SinglePort --> InternalOnly
```

**Security Measures Implementation:**

| Security Measure | Implementation | Protection |
|------------------|----------------|------------|
| Non-root User | `useradd -m -u 1000 appuser` | Privilege escalation prevention |
| Minimal Base Image | `python:3.11-slim` | Reduced attack surface |
| No Cache | `pip install --no-cache-dir` | No sensitive data in layers |
| Health Checks | `HEALTHCHECK` instruction | Container orchestration support |
| No Bytecode | `PYTHONDONTWRITEBYTECODE=1` | Cleaner runtime |
| Unbuffered Output | `PYTHONUNBUFFERED=1` | Real-time logging |

#### 8.4.1.3 Dockerfile Configuration

| Configuration | Value | Purpose |
|---------------|-------|---------|
| Working Directory | `/app` | Application root |
| User | `appuser` (UID 1000) | Non-root execution |
| Exposed Port | 7860 | Gradio interface |
| Health Check Interval | 30 seconds | Container health monitoring |
| Health Check Timeout | 10 seconds | Probe timeout |
| Health Check Retries | 3 | Failures before unhealthy |
| Health Check Start Period | 5 seconds | Startup grace period |

### 8.4.2 Docker Compose Configuration

**Source:** `docker-compose.yml`

#### 8.4.2.1 Service Definition

| Service | Image | Ports | Restart Policy |
|---------|-------|-------|----------------|
| `app` | `financial-asset-db:latest` | `7860:7860` | `unless-stopped` |
| `postgres` (optional) | `postgres:15-alpine` | `5432:5432` | `unless-stopped` |

#### 8.4.2.2 Volume Configuration

| Volume Mount | Purpose | Persistence |
|--------------|---------|-------------|
| `./src:/app/src` | Application source | Development hot-reload |
| `./data:/app/data` | Data persistence | Cache and database files |

#### 8.4.2.3 Health Check Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Test Command | `curl -f http://localhost:7860/` | HTTP health probe |
| Interval | 30 seconds | Check frequency |
| Timeout | 10 seconds | Maximum probe duration |
| Retries | 3 | Failures before unhealthy |
| Start Period | 40 seconds | Startup grace period |

### 8.4.3 Image Versioning Approach

| Version Pattern | Example | Use Case |
|-----------------|---------|----------|
| `latest` | `financial-asset-db:latest` | Development, CI |
| Semantic Version | `financial-asset-db:v1.2.3` | Production releases |
| Git SHA | `financial-asset-db:abc1234` | Traceability |
| Date-based | `financial-asset-db:2025-01-03` | Scheduled builds |

### 8.4.4 Build Optimization Techniques

| Technique | Implementation | Benefit |
|-----------|----------------|---------|
| Multi-stage builds | Separate build and runtime stages | Smaller final image |
| Layer caching | Order Dockerfile commands strategically | Faster rebuilds |
| `.dockerignore` | Exclude unnecessary files | Smaller build context |
| Dependency pinning | Exact versions in requirements.txt | Reproducible builds |

### 8.4.5 Security Scanning Requirements

| Tool | Workflow | Trigger | Severity |
|------|----------|---------|----------|
| Trivy | `.github/workflows/trivy.yml` | Push, PR, Weekly schedule | CRITICAL, HIGH |
| Hadolint | `.github/workflows/hadolint.yml` | Push, PR | All levels |
| Snyk Container | `.github/workflows/snyk-container.yml` | Push, PR | CRITICAL, HIGH |

**Scanning Schedule:**

| Scan Type | Frequency | Configuration |
|-----------|-----------|---------------|
| On-demand | Every push/PR | Immediate feedback |
| Scheduled | Weekly (Saturday 14:30 UTC) | Continuous vulnerability monitoring |
| Nightly | Daily (02:00 UTC) | Security regression detection |

---

## 8.5 Orchestration

### 8.5.1 Orchestration Platform Selection

The system uses **Docker Compose** for container orchestration rather than Kubernetes, optimized for the monolithic architecture design.

#### 8.5.1.1 Platform Justification

| Factor | Docker Compose | Kubernetes |
|--------|----------------|------------|
| **Complexity** | Low | High |
| **Scale Target** | < 500 assets | Enterprise-scale |
| **Operational Overhead** | Minimal | Significant |
| **Learning Curve** | Gentle | Steep |
| **Current Fit** | ✅ Optimal | ❌ Over-engineered |

**Rationale from Architecture:**
- Monolithic core architecture optimized for < 500 assets
- Single deployable Python process with modular packages
- Simplifies deployment for current scale
- Maintains clear module boundaries

### 8.5.2 Service Architecture

```mermaid
flowchart TB
    subgraph DockerCompose[Docker Compose Orchestration]
        subgraph AppService[Application Service]
            App[app container<br/>Port 7860<br/>Python 3.11-slim]
        end

        subgraph OptionalServices[Optional Services]
            Postgres[(PostgreSQL 15<br/>Port 5432<br/>Optional)]
        end

        subgraph Volumes[Persistent Volumes]
            SrcVol[Source Volume<br/>./src:/app/src]
            DataVol[Data Volume<br/>./data:/app/data]
            PgVol[(PostgreSQL Data<br/>Optional)]
        end

        subgraph Network[Docker Network]
            Bridge[Default Bridge<br/>Network]
        end
    end

    App --> SrcVol
    App --> DataVol
    App --> Bridge
    Postgres --> PgVol
    Postgres --> Bridge
    App -.-> Postgres
```

#### 8.5.2.1 Current Services

| Service | Purpose | Dependencies | Health Check |
|---------|---------|--------------|--------------|
| `app` | Primary application | None | HTTP probe |
| `postgres` (optional) | Database persistence | None | TCP probe |

### 8.5.3 Auto-Scaling Configuration

#### 8.5.3.1 Vercel Auto-Scaling

| Scaling Aspect | Configuration | Behavior |
|----------------|---------------|----------|
| Function Instances | Automatic | Scale to zero, scale up on demand |
| Cold Start | Expected | First request may have latency |
| Concurrent Requests | Platform-managed | Automatic instance distribution |
| Geographic Distribution | Automatic | Route to nearest edge |

#### 8.5.3.2 Docker Manual Scaling

```bash
# Scale application to multiple instances (load balancer required)
docker-compose up --scale app=3 -d
```

| Consideration | Current State | Production Recommendation |
|---------------|---------------|---------------------------|
| Load Balancing | Not configured | Add nginx/traefik for multi-instance |
| Session Affinity | N/A (stateless JWT) | Not required |
| Health-based Routing | Docker health checks | Configure orchestrator probes |

### 8.5.4 Future Kubernetes Support

A Kubernetes deployment template is documented in `DOCKER.md` for future enterprise deployments:

| Resource | Configuration |
|----------|---------------|
| Deployment | 3 replicas, rolling update strategy |
| Service | ClusterIP, port 7860 |
| ConfigMap | Environment variables |
| Secret | Sensitive credentials |

---

## 8.6 CI/CD Pipeline

### 8.6.1 Pipeline Architecture Overview

The system implements a comprehensive CI/CD pipeline using GitHub Actions as the primary platform with CircleCI as a secondary/redundant system.

```mermaid
flowchart TB
    subgraph Triggers[Pipeline Triggers]
        Push[Push to main]
        PR[Pull Request]
        Schedule[Scheduled Jobs]
        Tag[Version Tags]
    end

    subgraph QualityGates[Quality Gates]
        Lint[Linting<br/>flake8, black, isort]
        StaticAnalysis[Static Analysis<br/>pylint, mypy]
        Tests[Test Suite<br/>pytest + coverage]
        Security[Security Scans<br/>bandit, safety]
    end

    subgraph BuildPhase[Build Phase]
        DockerBuild[Docker Build]
        FrontendBuild[Frontend Build<br/>Next.js]
    end

    subgraph DeployPhase[Deployment Phase]
        VercelDeploy[Vercel<br/>Auto-Deploy]
        GHCRPublish[GHCR<br/>Image Publish]
        ImageSign[Image Signing<br/>cosign]
    end

    subgraph Reporting[Reporting]
        Codecov[Codecov<br/>Coverage]
        SARIF[GitHub Security<br/>SARIF Upload]
    end

    Push --> QualityGates
    PR --> QualityGates
    Schedule --> Security
    Tag --> BuildPhase

    QualityGates --> BuildPhase
    BuildPhase --> DeployPhase

    Tests --> Codecov
    Security --> SARIF
    DockerBuild --> GHCRPublish
    GHCRPublish --> ImageSign
```

### 8.6.2 Build Pipeline

#### 8.6.2.1 Source Control Triggers

| Trigger | Event | Branches | Actions |
|---------|-------|----------|---------|
| Push | Code push | `main` | Full CI pipeline |
| Pull Request | PR opened/updated | `main` | CI + preview deployment |
| Schedule | Cron | `main` | Security scans (nightly) |
| Tag | Version tag | `v*.*.*` | Release build + publish |
| Manual | `workflow_dispatch` | Selected | On-demand execution |

#### 8.6.2.2 Build Environment Requirements

**Python Environment Matrix:**

| Version | Status | Purpose |
|---------|--------|---------|
| Python 3.10 | ✅ Tested | Legacy support |
| Python 3.11 | ✅ Primary | Production runtime |
| Python 3.12 | ✅ Tested | Forward compatibility |

**Node.js Environment Matrix:**

| Version | Status | Purpose |
|---------|--------|---------|
| Node.js 18.x | ✅ Tested | LTS support |
| Node.js 20.x | ✅ Primary | Current LTS |
| Node.js 22.x | ✅ Tested | Forward compatibility |

#### 8.6.2.3 Dependency Management

**Python Dependencies (requirements.txt):**

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ==0.127.0 | API framework (pinned) |
| `pydantic` | ==2.12.5 | Data validation (pinned) |
| `numpy` | ==2.2.6 | Numerical computing (pinned) |
| `gradio` | >=4.0.0,<6.0.0 | Legacy UI |
| `plotly` | >=6.0.0 | Visualization |
| `yfinance` | >=0.2.51 | Financial data |
| `PyJWT` | >=2.8.0 | Authentication |
| `passlib[bcrypt]` | >=1.7.4 | Password hashing |
| `slowapi` | >=0.1.4 | Rate limiting |
| `urllib3` | >=2.6.0 | Security pin |
| `zipp` | >=3.19.1 | Security pin |

**Frontend Dependencies (package.json):**

| Package | Version | Purpose |
|---------|---------|---------|
| `next` | ^14.2.35 | React framework |
| `react` | ^18.2.0 | UI library |
| `axios` | ^1.6.0 | HTTP client |
| `plotly.js` | ^2.27.0 | Visualization |
| `jest` | ^29.7.0 | Test runner |
| `typescript` | ^5.3.0 | Type checking |

#### 8.6.2.4 Quality Gates

| Gate | Tool | Threshold | Blocking |
|------|------|-----------|----------|
| Critical Lint Errors | flake8 | 0 errors | Yes |
| Full Lint | flake8 + statistics | Pass | Yes |
| Formatting | black --check | 100% | Yes |
| Import Sorting | isort --check-only | 100% | Yes |
| Static Analysis | pylint | >= 7.0 score | Yes |
| Type Checking | mypy | Pass | Yes |
| Unit Tests | pytest | 100% pass | Yes |
| Coverage | Codecov | 80%+ target | Warning |

#### 8.6.2.5 Artifact Generation and Storage

| Artifact | Destination | Trigger | Retention |
|----------|-------------|---------|-----------|
| Coverage Reports (XML/HTML) | Codecov, GitHub Artifacts | Test completion | 90 days |
| Docker Images | GHCR (ghcr.io) | Push to main, tags | Permanent |
| Security Scan Results | SARIF → GitHub Security | Push/PR | 90 days |
| Build Outputs | CircleCI Artifacts | Build completion | 30 days |

### 8.6.3 GitHub Actions Primary Pipeline

**Source:** `.github/workflows/ci.yml`

#### 8.6.3.1 Workflow Configuration

```yaml
name: Python CI
on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

#### 8.6.3.2 Job Structure

| Job | Actions | Dependencies |
|-----|---------|--------------|
| `test` | Lint, format check, type check, pytest | None |
| `security` | safety, bandit | test |
| `coverage` | Codecov upload | test |

### 8.6.4 CircleCI Secondary Pipeline

**Source:** `.circleci/config.yml`

#### 8.6.4.1 Executor Configuration

| Executor | Image | Purpose |
|----------|-------|---------|
| `python-executor` | `cimg/python:3.11` | Python jobs |
| `node-executor` | `cimg/node:18.19` | Node.js jobs |

#### 8.6.4.2 Job Definitions

| Job | Actions | Parallelism |
|-----|---------|-------------|
| `python-lint` | flake8 (critical errors) | 1 |
| `python-test` | pytest with coverage | 4 |
| `python-security` | safety + bandit | 1 |
| `frontend-lint` | npm run lint | 1 |
| `frontend-build` | npm run build | 1 |
| `docker-build` | Build + smoke test | 1 |

#### 8.6.4.3 Workflow Definitions

```mermaid
flowchart LR
    subgraph BuildAndTest[build-and-test Workflow]
        PLint[python-lint] --> PTest[python-test]
        PTest --> PSec[python-security]

        FLint[frontend-lint] --> FBuild[frontend-build]

        PTest --> Docker[docker-build]
        FBuild --> Docker
    end

    subgraph NightlySecurity[nightly-security Workflow]
        Cron[Schedule<br/>02:00 UTC] --> NightSec[python-security]
    end
```

### 8.6.5 Deployment Pipeline

#### 8.6.5.1 Docker Image Publishing

**Source:** `.github/workflows/docker-publish.yml`

| Configuration | Value | Purpose |
|---------------|-------|---------|
| Registry | `ghcr.io` | GitHub Container Registry |
| Image Name | `${{ github.repository }}` | Repository-based naming |
| Signing | `sigstore/cosign` | Supply chain security |

**Triggers:**

| Trigger | Condition | Action |
|---------|-----------|--------|
| Schedule | Daily 15:27 UTC | Regular builds |
| Push | `main` branch, Docker paths | Auto-publish |
| Tag | `v*.*.*` pattern | Versioned release |

**Publishing Steps:**

1. Checkout repository
2. Install cosign (image signing)
3. Set up Docker Buildx
4. Login to GHCR
5. Extract metadata (tags, labels)
6. Build and push image
7. Sign image with cosign (except on PRs)

#### 8.6.5.2 Vercel Deployment

**GitHub Integration (Recommended):**

| Step | Action | Outcome |
|------|--------|---------|
| 1 | Push to GitHub | Triggers deployment |
| 2 | Vercel build | Frontend + API compiled |
| 3 | Preview URL | PR gets unique preview |
| 4 | Production deploy | Main branch auto-deploys |

**CLI Deployment:**

```bash
npm install -g vercel
vercel login
vercel          # Interactive deployment
vercel --prod   # Production deployment
```

#### 8.6.5.3 Deployment Strategy Comparison

| Environment | Strategy | Rollback | Downtime |
|-------------|----------|----------|----------|
| Vercel | Instant replacement | Promote previous | Zero |
| Docker | Build and restart | Previous image tag | Minimal |
| Cloud Run | Blue-green traffic split | Revert traffic | Zero |

### 8.6.6 Environment Promotion Workflow

```mermaid
flowchart TB
    subgraph PromotionFlow[Environment Promotion Flow]
        subgraph Dev[Development]
            FeatureBranch[Feature Branch<br/>Development]
            LocalTest[Local Testing<br/>run-dev.sh]
        end

        subgraph Preview[Preview]
            PROpen[Pull Request<br/>Opened]
            PreviewDeploy[Vercel Preview<br/>Deployment]
            CodeReview[Code Review<br/>+ Quality Gates]
        end

        subgraph Staging[Staging]
            DockerBuild[Docker Build<br/>Validation]
            SecurityScan[Security<br/>Scanning]
            IntegrationTest[Integration<br/>Tests]
        end

        subgraph Prod[Production]
            MergeMain[Merge to<br/>main]
            ProdDeploy[Production<br/>Deployment]
            Monitoring[Post-Deploy<br/>Monitoring]
        end
    end

    FeatureBranch --> LocalTest
    LocalTest --> PROpen
    PROpen --> PreviewDeploy
    PreviewDeploy --> CodeReview
    CodeReview --> DockerBuild
    DockerBuild --> SecurityScan
    SecurityScan --> IntegrationTest
    IntegrationTest --> MergeMain
    MergeMain --> ProdDeploy
    ProdDeploy --> Monitoring
```

### 8.6.7 Rollback Procedures

#### 8.6.7.1 Vercel Rollback

| Step | Action | Location |
|------|--------|----------|
| 1 | Navigate to Vercel Dashboard | vercel.com |
| 2 | Select Deployments tab | Project settings |
| 3 | Find previous working deployment | Deployment history |
| 4 | Click "Promote to Production" | Deployment actions |

#### 8.6.7.2 Docker Rollback

```bash
# Pull previous version
docker pull ghcr.io/<repo>:<previous-tag>

#### Stop current container
docker-compose down

#### Update image tag in docker-compose.yml or use:
docker run -d -p 7860:7860 ghcr.io/<repo>:<previous-tag>
```

### 8.6.8 Post-Deployment Validation

| Check | Endpoint | Expected Result | Timeout |
|-------|----------|-----------------|---------|
| Health Check | `/api/health` | `{"status": "healthy"}` | 5s |
| API Docs | `/docs` | OpenAPI documentation loads | 10s |
| Frontend Load | `/` | Page renders | 3s |
| 3D Visualization | Tab interaction | Renders smoothly | 5s |
| Authentication | `/token` | Returns JWT | 2s |

### 8.6.9 Reusable CI Components

**Source:** `.github/actions/ci-common/action.yml`

| Feature | Description |
|---------|-------------|
| Language Support | Python or Node.js |
| Caching | pip/npm cache integration |
| Configurable Commands | Install, build, test |
| Error Handling | `set -euo pipefail` strict mode |

---

## 8.7 Infrastructure Monitoring

### 8.7.1 Monitoring Architecture

```mermaid
flowchart TB
    subgraph MonitoringStack[Infrastructure Monitoring Stack]
        subgraph ApplicationMonitoring[Application Layer]
            HealthEndpoint[/api/health<br/>Health Check]
            MetricsEndpoint[/api/metrics<br/>Application Metrics]
            LoggingLayer[Python Logging<br/>INFO Level]
        end

        subgraph ContainerMonitoring[Container Layer]
            DockerHealth[Docker HEALTHCHECK<br/>HTTP Probe]
            ComposeHealth[Docker Compose<br/>Health Config]
        end

        subgraph CICDMonitoring[CI/CD Layer]
            GitHubSecurity[GitHub Actions<br/>Security Scans]
            CircleCITests[CircleCI<br/>Test Coverage]
            Codecov[Codecov<br/>Coverage Reports]
        end

        subgraph SecurityScanning[Security Monitoring]
            SAST[SAST Tools<br/>Bandit, CodeQL]
            Dependency[Dependency Scan<br/>Snyk, Safety]
            Container[Container Scan<br/>Trivy]
        end
    end

    HealthEndpoint --> DockerHealth
    DockerHealth --> ComposeHealth

    GitHubSecurity --> SAST
    GitHubSecurity --> Dependency
    GitHubSecurity --> Container

    CircleCITests --> Codecov
```

### 8.7.2 Resource Monitoring

#### 8.7.2.1 Health Check Implementation

| Level | Implementation | Configuration |
|-------|----------------|---------------|
| API Endpoint | `GET /api/health` | Returns status and graph state |
| Docker | `HEALTHCHECK` instruction | 30s interval, 10s timeout |
| Docker Compose | `healthcheck` service config | 40s start period |

**Health Response Schema:**

```json
{
  "status": "healthy",
  "graph_initialized": true
}
```

#### 8.7.2.2 Application Metrics Endpoint

**Endpoint:** `GET /api/metrics`

| Metric | Type | Description |
|--------|------|-------------|
| `total_assets` | Counter | Count of nodes in graph |
| `total_relationships` | Counter | Count of edges in graph |
| `asset_classes` | Dictionary | Count per asset class |
| `avg_degree` | Gauge | Mean connections per node |
| `max_degree` | Gauge | Highest connected node |
| `network_density` | Gauge | Edge ratio metric |
| `relationship_density` | Gauge | Calculated density |

### 8.7.3 Performance Metrics and SLAs

| Operation | Target SLA | Measurement Point |
|-----------|-----------|-------------------|
| API Response (p95) | < 500ms | Request to response |
| Visualization Rendering | < 2 seconds | Data load to interactive |
| Token Generation | < 100ms | Credential to token |
| Graph Initialization | < 3 seconds | Application startup |
| Relationship Discovery | < 500ms | For 100 assets |
| Initial Page Load | < 3 seconds | Navigation to interactive |

### 8.7.4 Logging Configuration

#### 8.7.4.1 Backend Logging

| Setting | Value | Location |
|---------|-------|----------|
| Level | `INFO` | `api/main.py` |
| Logger | `logging.getLogger(__name__)` | Module-specific |
| Format | Python default | Standard library |

#### 8.7.4.2 Log Point Catalog

| Log Point | Level | Content | Location |
|-----------|-------|---------|----------|
| Graph initialization | INFO | Success/failure | `api/main.py` |
| Application startup | INFO | Server binding, port | `api/main.py` |
| Application shutdown | INFO | Shutdown notification | `api/main.py` |
| Cache operations | INFO | Load/save success | `real_data_fetcher.py` |
| Authentication failures | WARNING | Failed login attempts | `api/auth.py` |
| Invalid CORS origins | WARNING | Skipped origin | `api/main.py` |
| Request errors | ERROR | Exception details | `api/main.py` |

### 8.7.5 Security Monitoring

#### 8.7.5.1 CI/CD Security Scanning Matrix

| Tool | Workflow | Purpose | Trigger |
|------|----------|---------|---------|
| Bandit | `bandit.yml` | Python SAST | Push/PR |
| CodeQL | `codeql.yml` | Multi-language SAST | Push/PR/Schedule |
| Semgrep | `semgrep.yml` | Pattern detection | Push/PR |
| Trivy | `trivy.yml` | Container scanning | Push/PR/Weekly |
| Hadolint | `hadolint.yml` | Dockerfile linting | Push/PR |
| Snyk | `snyk-security.yml` | Dependency scanning | Push/PR |
| OSSF Scorecard | `scorecard.yml` | Supply chain | Push/Schedule |
| DevSkim | `devskim.yml` | Security linting | Push/PR |
| Safety | CircleCI | Python vulnerabilities | Nightly |

#### 8.7.5.2 SARIF Integration

All security scans upload results to GitHub Advanced Security via SARIF format:

| Configuration | Value |
|---------------|-------|
| Upload Action | `github/codeql-action/upload-sarif@v3` |
| Permission | `security-events: write` |
| Visibility | GitHub Security tab |

### 8.7.6 Rate Limiting Monitoring

| Endpoint | Limit | Window | Response |
|----------|-------|--------|----------|
| `POST /token` | 5 requests | 1 minute | 429 + Retry-After |
| `GET /api/users/me` | 10 requests | 1 minute | 429 + Retry-After |

### 8.7.7 Cost Monitoring

#### 8.7.7.1 Vercel Cost Monitoring

| Method | Implementation |
|--------|----------------|
| Usage Dashboard | Vercel project settings |
| Spend Alerts | Email notifications at thresholds |
| Budget Limits | $200 default on-demand cap |
| Hard Limits | Optional auto-pause at 100% |

#### 8.7.7.2 Container Registry Cost

| Registry | Free Tier | Overage |
|----------|-----------|---------|
| GHCR (public) | Unlimited | N/A |
| GHCR (private) | 1 GB storage, 1 GB transfer | $0.25/GB storage |

### 8.7.8 Future Monitoring Recommendations

| Component | Recommended Tool | Purpose |
|-----------|------------------|---------|
| Metrics Collection | Prometheus + prometheus-fastapi-instrumentator | RED metrics |
| Distributed Tracing | OpenTelemetry | Request flow visualization |
| Log Aggregation | Loki or ELK Stack | Centralized management |
| Visualization | Grafana | Unified dashboard |
| Error Tracking | Sentry | Exception monitoring |
| Alerting | Prometheus Alertmanager | Automated notifications |

---

## 8.8 Database and Storage Infrastructure

### 8.8.1 Storage Architecture

```mermaid
flowchart TB
    subgraph StorageArchitecture[Data Storage Architecture]
        subgraph PrimaryStorage[Primary Storage]
            InMemGraph[In-Memory Graph<br/>Dict-based Structure<br/>< 500 nodes optimal]
        end

        subgraph AuthStorage[Authentication Storage]
            SQLiteAuth[(SQLite Database<br/>User Credentials<br/>DATABASE_URL)]
        end

        subgraph CacheStorage[Cache Storage]
            JSONCache[(JSON File Cache<br/>Atomic Writes<br/>REAL_DATA_CACHE_PATH)]
            GraphCache[(Graph Cache<br/>Optional Serialization<br/>GRAPH_CACHE_PATH)]
        end

        subgraph OptionalStorage[Optional Production Storage]
            PostgreSQL[(PostgreSQL 15<br/>Full Persistence<br/>ASSET_GRAPH_DATABASE_URL)]
        end
    end

    InMemGraph --> SQLiteAuth
    InMemGraph --> JSONCache
    InMemGraph --> GraphCache
    InMemGraph -.-> PostgreSQL
```

### 8.8.2 Primary Storage: In-Memory Graph

| Attribute | Specification |
|-----------|---------------|
| Data Structure | `Dict[source_id, List[Tuple[target_id, rel_type, strength]]]` |
| Implementation | `src/logic/asset_graph.py` |
| Thread Safety | Double-checked locking singleton pattern |
| Size Constraint | Optimal performance for < 500 nodes |

### 8.8.3 SQLite Authentication Database

| Attribute | Specification |
|-----------|---------------|
| Purpose | User credentials storage |
| Implementation | `api/database.py` |
| Environment Variable | `DATABASE_URL` |
| Schema | `user_credentials` table |

### 8.8.4 PostgreSQL (Optional Production)

| Attribute | Specification |
|-----------|---------------|
| Image | `postgres:15-alpine` |
| Database | `financial_assets` |
| User | `finuser` |
| Port | `5432` |
| ORM | SQLAlchemy >= 2.0.0 |

**Database Schema (migrations/001_initial.sql):**

| Table | Purpose |
|-------|---------|
| `assets` | Primary entity table |
| `asset_relationships` | Directed edge table |
| `regulatory_events` | Event records |
| `regulatory_event_assets` | Junction table |

### 8.8.5 Caching Strategy

| Cache Type | Implementation | Configuration |
|------------|----------------|---------------|
| Real Data Cache | JSON with atomic writes | `REAL_DATA_CACHE_PATH` |
| Graph Cache | JSON serialization | `GRAPH_CACHE_PATH` |

**Atomic Write Pattern:**
1. Write to NamedTemporaryFile
2. Flush and sync to disk
3. `os.replace()` atomic rename
4. Guarantees no partial writes

---

## 8.9 Development Workflow Infrastructure

### 8.9.1 Local Development Setup

**Script:** `run-dev.sh`

| Action | Command | Result |
|--------|---------|--------|
| Create venv | `python -m venv venv` | Virtual environment |
| Activate venv | `source venv/bin/activate` | Environment active |
| Install Python deps | `pip install -r requirements.txt` | Dependencies ready |
| Start FastAPI | `uvicorn api.main:app --reload` | Backend on 8000 |
| Install frontend deps | `npm install` | Node modules ready |
| Start Next.js | `npm run dev` | Frontend on 3000 |

**Access Points:**

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | User interface |
| Backend API | http://localhost:8000 | API endpoints |
| API Docs | http://localhost:8000/docs | OpenAPI documentation |

### 8.9.2 Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install production dependencies |
| `make install-dev` | Install development dependencies |
| `make test` | Run tests with coverage |
| `make lint` | Run flake8 + pylint |
| `make format` | Format with black + isort |
| `make type-check` | Run mypy type checking |
| `make check` | Full quality check pipeline |
| `make docker-build` | Build Docker image |
| `make docker-run` | Run Docker container |
| `make docker-compose-up` | Start with docker-compose |
| `make docker-shell` | Shell into container |

### 8.9.3 Pre-Commit Hooks

**Source:** `.pre-commit-config.yaml`

| Hook | Tool | Version | Configuration |
|------|------|---------|---------------|
| Formatting | black | v25.12.0 | Python 3 |
| Import Sorting | isort | v7.0.0 | profile: black |
| Linting | flake8 | v7.3.0 | + flake8-docstrings |
| Type Checking | mypy | v1.19.1 | --ignore-missing-imports |
| Standard Hooks | pre-commit | latest | trailing-whitespace, end-of-file-fixer |

---

## 8.10 Network Architecture

### 8.10.1 Network Topology

```mermaid
flowchart TB
    subgraph Internet[Public Internet]
        Users([End Users])
        Attackers([Potential Attackers])
    end

    subgraph EdgeSecurity[Edge Security Layer]
        VercelEdge[Vercel Edge<br/>TLS Termination<br/>DDoS Protection]
        CORS[CORS Middleware<br/>Origin Validation]
    end

    subgraph ApplicationNetwork[Application Network]
        subgraph RateLimiting[Rate Limiting]
            SlowAPI[SlowAPI<br/>IP-based Throttling]
        end

        subgraph Services[Application Services]
            FastAPI[FastAPI Backend<br/>Port 8000]
            NextJS[Next.js Frontend<br/>Port 3000]
            Gradio[Gradio UI<br/>Port 7860]
        end
    end

    subgraph DataNetwork[Data Network - Internal Only]
        Graph[Graph Engine]
        SQLite[(SQLite DB)]
        Cache[(File Cache)]
    end

    subgraph External[External APIs]
        YahooFinance[Yahoo Finance<br/>HTTPS]
    end

    Users --> VercelEdge
    Attackers --> VercelEdge
    VercelEdge --> CORS
    CORS --> SlowAPI
    SlowAPI --> Services

    FastAPI --> Graph
    Graph --> SQLite
    Graph --> Cache
    Graph --> YahooFinance
```

### 8.10.2 Port Exposure Matrix

| Port | Service | Protocol | External Access |
|------|---------|----------|-----------------|
| 3000 | Next.js Frontend | HTTP/HTTPS | Yes (via Vercel) |
| 7860 | Gradio UI | HTTP | Yes (Docker) |
| 8000 | FastAPI Backend | HTTP/HTTPS | Yes (via Vercel) |
| 5432 | PostgreSQL | TCP | No (internal only) |

### 8.10.3 CORS Configuration

| Environment | HTTP localhost | HTTPS localhost | Vercel URLs | Custom HTTPS |
|-------------|----------------|-----------------|-------------|--------------|
| Development | ✅ Allowed | ✅ Allowed | ✅ Allowed | ✅ Allowed |
| Production | ❌ Rejected | ✅ Allowed | ✅ Allowed | ✅ Allowed |

---

## 8.11 Infrastructure Cost Summary

### 8.11.1 Cost Comparison Matrix

| Deployment Model | Fixed Monthly | Variable Costs | Best For |
|------------------|---------------|----------------|----------|
| **Local Development** | $0 | $0 | Development |
| **Vercel Hobby** | $0 | Overages possible | Personal projects |
| **Vercel Pro** | $20/user | Bandwidth, CPU overage | Small teams |
| **Docker Self-Hosted** | Server cost | N/A | Full control |
| **Google Cloud Run** | $0 | Usage-based (~$5-50/month) | GCP integration |

### 8.11.2 Resource Sizing Guidelines

| Scale | Users | Assets | Recommended Deployment |
|-------|-------|--------|----------------------|
| Development | 1-5 | < 100 | Local, Vercel Hobby |
| Small | 5-50 | < 300 | Vercel Pro, Docker |
| Medium | 50-500 | < 500 | Vercel Pro + caching |
| Large | 500+ | 500+ | Requires architecture changes |

---

## 8.12 Maintenance Procedures

### 8.12.1 Routine Maintenance

| Task | Frequency | Procedure |
|------|-----------|-----------|
| Dependency Updates | Weekly | Review Dependabot PRs |
| Security Scans | Daily (automated) | Review SARIF alerts |
| Docker Image Refresh | Weekly | Rebuild with latest base |
| Cache Cleanup | As needed | Clear `GRAPH_CACHE_PATH` |
| Log Review | Weekly | Check for error patterns |

### 8.12.2 Emergency Procedures

| Scenario | Detection | Response |
|----------|-----------|----------|
| Security Vulnerability | SARIF alert, CVE notice | Patch dependencies, redeploy |
| Service Outage | Health check failures | Rollback to previous deployment |
| Data Corruption | Validation errors | Clear cache, reinitialize |
| Rate Limit Abuse | 429 response spike | Review IP patterns, adjust limits |

---

## 8.13 References

### 8.13.1 Configuration Files

| Path | Description |
|------|-------------|
| `Dockerfile` | Container image definition, security measures, health checks |
| `docker-compose.yml` | Service orchestration, volumes, environment |
| `vercel.json` | Serverless deployment configuration, routing |
| `Makefile` | Build automation commands |
| `.github/workflows/ci.yml` | Primary CI pipeline configuration |
| `.github/workflows/docker-publish.yml` | Container image publishing |
| `.github/workflows/trivy.yml` | Container security scanning |
| `.circleci/config.yml` | Secondary CI platform configuration |
| `.github/actions/ci-common/action.yml` | Reusable CI composite action |
| `.pre-commit-config.yaml` | Pre-commit hook configuration |
| `.env.example` | Environment variable template |
| `pyproject.toml` | Python project metadata and tooling |
| `requirements.txt` | Python dependencies |
| `run-dev.sh` | Development startup script |
| `frontend/package.json` | Frontend dependencies and scripts |
| `migrations/001_initial.sql` | Database schema definition |

### 8.13.2 Documentation Files

| Path | Description |
|------|-------------|
| `DEPLOYMENT.md` | Deployment guide |
| `DOCKER.md` | Docker deployment guide |
| `VERCEL_DEPLOYMENT_CHECKLIST.md` | Deployment checklist |
| `SECURITY.md` | Security best practices |

### 8.13.3 Technical Specification Cross-References

| Section | Relevance |
|---------|-----------|
| 5.5 DEPLOYMENT ARCHITECTURE | Deployment configurations |
| 6.5 Monitoring and Observability | Monitoring implementation |
| 6.4 Security Architecture | Security controls |
| 3.7 Development & Deployment | Development workflow |
| 2.6 Assumptions and Constraints | System constraints |
| 3.6 Databases & Storage | Storage architecture |
| 3.5 Third-Party Services | External dependencies |

### 8.13.4 External References

| Resource | Purpose |
|----------|---------|
| Vercel Documentation | Serverless deployment |
| Docker Documentation | Container configuration |
| GitHub Actions Documentation | CI/CD pipelines |
| CircleCI Documentation | Secondary CI platform |

# 9. Appendices

## 9.1 ADDITIONAL TECHNICAL INFORMATION

This appendix consolidates supplementary technical reference material that complements the main specification sections, providing quick-reference tables for configuration, operational parameters, and implementation constants.

### 9.1.1 Environment Variables Reference

The system requires specific environment variables for proper operation, categorized by criticality and purpose.

#### 9.1.1.1 Required Environment Variables

| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `SECRET_KEY` | JWT signing key for authentication | `your-secure-secret-key` |
| `DATABASE_URL` | SQLite authentication database connection | `sqlite:///auth.db` |
| `ADMIN_USERNAME` | Initial admin user login credential | `admin` |
| `ADMIN_PASSWORD` | Initial admin user password | `secure-password` |

#### 9.1.1.2 Optional Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENV` | `development` | Environment mode (development/production) |
| `ALLOWED_ORIGINS` | (built-in defaults) | Comma-separated CORS allowlist |
| `USE_REAL_DATA_FETCHER` | `false` | Enable Yahoo Finance integration |
| `REAL_DATA_CACHE_PATH` | None | Yahoo Finance cache file location |
| `GRAPH_CACHE_PATH` | None | Graph serialization cache location |
| `ASSET_GRAPH_DATABASE_URL` | None | SQLAlchemy ORM connection string |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend API base URL |
| `ADMIN_EMAIL` | None | Admin user email address |
| `ADMIN_FULL_NAME` | None | Admin user display name |
| `ADMIN_DISABLED` | `false` | Disable admin account flag |

### 9.1.2 Relationship Types Reference

The graph engine supports eight relationship types with specific detection rules and directionality configurations.

| Type | Directionality | Detection Rule |
|------|----------------|----------------|
| `same_sector` | Bidirectional | Assets share identical sector value |
| `corporate_bond_to_equity` | Directional | Bond `issuer_id` matches equity `id` |
| `commodity_exposure` | Directional | Equity sector linked to commodity type |
| `currency_risk` | Directional | Asset currency ≠ "USD" |
| `income_comparison` | Bidirectional | Dividend yield vs bond yield proximity |
| `regulatory_impact` | Directional | Shared regulatory event reference |
| `market_cap_similar` | Bidirectional | Market cap within 50% range |
| `correlation` | Bidirectional | Price correlation exceeds threshold |

### 9.1.3 HTTP Status Codes Reference

The API returns standardized HTTP status codes with consistent error message formatting.

| Code | Meaning | Usage Context |
|------|---------|---------------|
| 200 | OK | Successful GET/POST request |
| 400 | Bad Request | Invalid input, inactive user account |
| 401 | Unauthorized | Invalid/expired token, missing credentials |
| 403 | Forbidden | Invalid CORS origin |
| 404 | Not Found | Asset or resource not found |
| 422 | Validation Error | Pydantic validation failure |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected exception |

### 9.1.4 Default Port Assignments

| Component | Port | Purpose |
|-----------|------|---------|
| FastAPI Backend | 8000 | REST API development server |
| Next.js Frontend | 3000 | Modern UI development server |
| Gradio UI | 7860 | Legacy Python UI server |

### 9.1.5 Asset Class Color Scheme

The visualization layer uses a consistent color scheme for asset class identification.

| Asset Class | Hex Color | RGB Value |
|-------------|-----------|-----------|
| Equity | #1f77b4 | rgb(31, 119, 180) |
| Fixed Income | #2ca02c | rgb(44, 160, 44) |
| Commodity | #ff7f0e | rgb(255, 127, 14) |
| Currency | #d62728 | rgb(214, 39, 40) |
| Derivative | #9467bd | rgb(148, 103, 189) |

### 9.1.6 Visualization Guardrails

| Parameter | Default Value | Purpose |
|-----------|---------------|---------|
| MAX_NODES | 500 | Prevent browser memory exhaustion |
| MAX_EDGES | 2000 | Limit rendering complexity |
| Seed | 42 | Deterministic 3D layout reproduction |

### 9.1.7 Rate Limiting Configuration

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /token` | 5 requests | 1 minute |
| `GET /api/users/me` | 10 requests | 1 minute |
| Other endpoints | Unlimited | N/A |

### 9.1.8 Performance SLA Targets

| Operation | Target SLA |
|-----------|------------|
| API Response (p95) | < 500ms |
| Visualization Rendering | < 2 seconds |
| Token Generation | < 100ms |
| Graph Initialization | < 3 seconds |
| Relationship Discovery (100 assets) | < 500ms |
| Initial Page Load | < 3 seconds |

### 9.1.9 Timeout Configuration

| Component | Timeout | Purpose |
|-----------|---------|---------|
| JWT Token | 30 minutes | Session expiration |
| Rate Limit Window | 1 minute | Request counting period |
| HTTP Client | 30 seconds | API request timeout |
| Health Check | 30 seconds | Container probe interval |

### 9.1.10 Yahoo Finance Supported Symbols

| Category | Symbols |
|----------|---------|
| Equities | AAPL, MSFT, XOM, JPM |
| Bond ETFs | TLT, LQD, HYG |
| Commodities | GC=F (Gold), CL=F (Crude Oil), SI=F (Silver) |
| Currencies | EURUSD=X, GBPUSD=X, JPYUSD=X |

### 9.1.11 Sample Data Statistics

The sample database provides baseline testing and offline development data.

| Entity Type | Count |
|-------------|-------|
| Total Assets | 19 |
| Regulatory Events | 4 |
| Asset Classes | 5 (all supported) |

---

## 9.2 GLOSSARY

This glossary defines key terms used throughout the Technical Specification, organized by domain.

### 9.2.1 Financial Domain Terms

| Term | Definition |
|------|------------|
| **Asset** | A financial instrument with tradeable value. Base domain entity requiring id, symbol, name, asset_class, sector, and price fields. |
| **Asset Class** | Category classification for financial instruments. Supported values: Equity, Fixed Income, Commodity, Currency, Derivative. |
| **Asset Relationship Graph** | Core in-memory data structure storing assets as nodes and relationships as weighted edges in an adjacency list format. |
| **Average Degree** | Network metric representing the mean number of connections per node, calculated as (2 × total_relationships) / total_assets. |
| **Bidirectional Relationship** | A relationship type where the connection applies equally in both directions (e.g., same_sector, income_comparison). |
| **Bond** | Fixed income security with specialized attributes: yield_to_maturity, coupon_rate, maturity_date, credit_rating, and issuer_id. |
| **Commodity** | Asset class representing tradeable goods contracts with attributes: contract_size, delivery_date, and volatility. |
| **Commodity Exposure** | Directional relationship linking equity companies to commodity price movements based on sector exposure. |
| **Corporate Bond to Equity** | Directional relationship linking bonds to issuing companies via issuer_id matching equity id. |
| **Coupon Rate** | Annual interest rate paid on a bond's face value, expressed as a percentage. |
| **Credit Rating** | Assessment of bond issuer creditworthiness, typically represented as letter grades (e.g., AAA, BBB). |
| **Currency** | Asset class for foreign exchange pairs with attributes: exchange_rate, country, and central_bank_rate. |
| **Currency Risk** | Directional relationship for assets with non-USD currency exposure, indicating foreign exchange risk. |
| **Derivative** | Financial instrument whose value is derived from underlying assets. Reserved for future expansion. |
| **Directional Relationship** | A relationship type where the connection flows from source to target (e.g., corporate_bond_to_equity). |
| **Dividend Yield** | Annual dividend payment as percentage of stock price, applicable to equity assets. |
| **Earnings Per Share (EPS)** | Company profitability metric calculated as net income divided by outstanding shares. |
| **Equity** | Stock/share ownership in a company with attributes: pe_ratio, dividend_yield, earnings_per_share, and book_value. |
| **Fixed Income** | Asset class for bonds and debt securities generating regular income payments. |
| **Impact Score** | Numerical measure (-1.0 to +1.0) representing regulatory event impact. Negative indicates adverse impact, positive indicates favorable. |
| **Income Comparison** | Bidirectional relationship comparing dividend yields to bond yields for cross-asset income analysis. |
| **Market Cap** | Market Capitalization; total market value of a company's outstanding shares. |
| **Max Degree** | Network metric representing the highest-connected node in the graph by edge count. |
| **Network Density** | Ratio of actual relationships to maximum possible relationships, calculated as total_edges / (nodes × (nodes-1) / 2). |
| **P/E Ratio** | Price-to-Earnings ratio; stock price divided by earnings per share, indicating valuation. |
| **Regulatory Activity** | Enumerated type of corporate or regulatory event: earnings_report, sec_filing, dividend_announcement, bond_issuance, acquisition, bankruptcy. |
| **Regulatory Event** | Corporate or regulatory activity affecting one or more assets with dated occurrence, description, and scored impact. |
| **Relationship Strength** | Normalized weight (0.0-1.0) indicating connection intensity between assets in a relationship. |
| **Same Sector** | Bidirectional relationship linking assets operating in the same industry sector classification. |
| **Sector** | Industry classification for assets (e.g., Technology, Energy, Financial Services, Healthcare). |
| **Yield to Maturity (YTM)** | Total return anticipated on a bond if held until maturity, accounting for coupon payments and price difference. |

### 9.2.2 Technical Architecture Terms

| Term | Definition |
|------|------------|
| **Adjacency List** | Graph data structure where each node stores a list of connected nodes, implemented as Dict[str, List[Tuple[str, str, float]]]. |
| **App Router** | Next.js 14 routing paradigm using file-system-based routing in the app/ directory with React Server Components. |
| **Atomic Write** | File operation pattern using NamedTemporaryFile + os.replace() to prevent data corruption during writes. |
| **Bearer Token** | HTTP authorization scheme where the token is passed in the Authorization header as "Bearer {token}". |
| **Context Manager** | Python pattern using `with` statements for resource management, implemented as session_scope() for database transactions. |
| **Dataclass** | Python @dataclass decorator providing automatic __init__, __repr__, and field handling for domain models. |
| **Dependency Injection** | Design pattern where dependencies are passed to components rather than created internally, used in FastAPI route dependencies. |
| **Double-Checked Locking** | Thread-safe singleton pattern checking instance existence before and after acquiring lock to minimize contention. |
| **Enum** | Python enumeration type for type-safe constant values (e.g., AssetClass, RegulatoryActivity). |
| **Graph Engine** | Core component managing asset relationships, 3D layout calculation, and network metrics computation. |
| **Hybrid Storage** | Architecture combining multiple storage mechanisms: in-memory graph, SQLite auth, optional ORM, and JSON cache. |
| **Layered Architecture** | System design separating concerns into Presentation, API, Business Logic, and Data layers for maintainability. |
| **Lifespan Context Manager** | FastAPI pattern for managing application startup/shutdown events using asynccontextmanager decorator. |
| **Middleware** | Software layer intercepting requests/responses for cross-cutting concerns (CORS, rate limiting, authentication). |
| **Monolithic Architecture** | Single deployable unit containing all application components, as opposed to microservices. |
| **Post-Init Validation** | Dataclass validation in __post_init__ method executing after instance creation for business rule enforcement. |
| **Repository Pattern** | Data access abstraction providing collection-like interface over storage, implemented as AssetGraphRepository. |
| **Seed Value** | Random number generator initialization value (42) for deterministic/reproducible 3D layouts. |
| **Session Scope** | Database transaction boundary context manager committing on success, rolling back on error. |
| **Singleton Pattern** | Design pattern ensuring only one instance of a class exists, applied to the graph instance with thread-safety. |
| **Thread-Safe** | Code safe for concurrent execution by multiple threads without race conditions. |
| **Type Contract** | Formal interface defining expected data types through Pydantic models and TypeScript interfaces. |
| **Wide Table Design** | Database schema with nullable columns for type-specific attributes in a single table for simpler queries. |

### 9.2.3 UI/UX Terms

| Term | Definition |
|------|------------|
| **3D Network Visualization** | Interactive Plotly-based graph rendering with rotation, zoom, pan, and hover capabilities for spatial exploration. |
| **2D Network Visualization** | Flat network view with selectable layout algorithms (spring, circular, grid) for static analysis. |
| **Asset Explorer** | Filterable, paginated table view for browsing assets by class and sector with direct detail access. |
| **Color Mapping** | Visual encoding scheme mapping asset classes to distinct colors for identification in visualizations. |
| **Hover Text** | Tooltip content displayed when cursor hovers over visualization elements showing asset details. |
| **Metrics Dashboard** | UI component displaying network statistics including node/edge counts and distribution analytics. |
| **Schema Report** | Auto-generated Markdown documentation of data models, relationships, and business rules. |
| **Tabbed Interface** | UI organization with multiple content areas accessible via tab controls (Gradio implements 6 tabs). |

### 9.2.4 Infrastructure Terms

| Term | Definition |
|------|------------|
| **ASGI Server** | Asynchronous Server Gateway Interface server (Uvicorn) handling async HTTP requests for FastAPI. |
| **Container Hardening** | Security measures applied to Docker containers including non-root user execution and minimal base images. |
| **Edge Network** | Vercel's globally distributed CDN network for TLS termination and static asset delivery. |
| **Health Check** | HTTP endpoint probe (/api/health) returning system status for load balancer and orchestration verification. |
| **Lambda Function** | Serverless compute unit on Vercel handling individual API requests without persistent server. |
| **Static Pool** | SQLAlchemy connection pool configuration for in-memory SQLite maintaining single shared connection. |

---

## 9.3 ACRONYMS

This section provides expanded forms for all acronyms used throughout the Technical Specification.

### 9.3.1 Standard Technical Acronyms

| Acronym | Expansion |
|---------|-----------|
| API | Application Programming Interface |
| ASGI | Asynchronous Server Gateway Interface |
| CDN | Content Delivery Network |
| CI/CD | Continuous Integration/Continuous Deployment |
| CLI | Command Line Interface |
| CORS | Cross-Origin Resource Sharing |
| CPU | Central Processing Unit |
| CRUD | Create, Read, Update, Delete |
| CSS | Cascading Style Sheets |
| DAG | Directed Acyclic Graph |
| DDL | Data Definition Language |
| DNS | Domain Name System |
| DOM | Document Object Model |
| DRY | Don't Repeat Yourself |
| ERD | Entity Relationship Diagram |
| FK | Foreign Key |
| GUI | Graphical User Interface |
| HTML | HyperText Markup Language |
| HTTP | HyperText Transfer Protocol |
| HTTPS | HTTP Secure (over TLS) |
| IDE | Integrated Development Environment |
| IP | Internet Protocol |
| JSON | JavaScript Object Notation |
| KPI | Key Performance Indicator |
| LTS | Long-Term Support |
| ORM | Object-Relational Mapping |
| PK | Primary Key |
| PR | Pull Request |
| RAM | Random Access Memory |
| REST | Representational State Transfer |
| SDK | Software Development Kit |
| SLA | Service Level Agreement |
| SQL | Structured Query Language |
| SSR | Server-Side Rendering |
| TLS | Transport Layer Security |
| TTL | Time To Live |
| UID | User Identifier |
| UK | Unique Key |
| URI | Uniform Resource Identifier |
| URL | Uniform Resource Locator |
| UTC | Coordinated Universal Time |
| UUID | Universally Unique Identifier |
| WSGI | Web Server Gateway Interface |
| XML | eXtensible Markup Language |
| YAML | YAML Ain't Markup Language |

### 9.3.2 Security & Authentication Acronyms

| Acronym | Expansion |
|---------|-----------|
| HMAC | Hash-based Message Authentication Code |
| HS256 | HMAC-SHA256 (JWT signing algorithm) |
| JWT | JSON Web Token |
| NIST | National Institute of Standards and Technology |
| RBAC | Role-Based Access Control |
| SARIF | Static Analysis Results Interchange Format |
| SAST | Static Application Security Testing |
| SHA | Secure Hash Algorithm |
| TOTP | Time-based One-Time Password |
| WAL | Write-Ahead Logging |

### 9.3.3 Financial Domain Acronyms

| Acronym | Expansion |
|---------|-----------|
| EPS | Earnings Per Share |
| ETF | Exchange-Traded Fund |
| FX | Foreign Exchange |
| P/E | Price-to-Earnings (ratio) |
| SEC | Securities and Exchange Commission |
| YTM | Yield to Maturity |

### 9.3.4 Platform & Tool Acronyms

| Acronym | Expansion |
|---------|-----------|
| GHCR | GitHub Container Registry |
| MCP | Model Context Protocol |
| OSSF | Open Source Security Foundation |
| ISO | International Organization for Standardization |

### 9.3.5 Version-Specific Designations

| Designation | Meaning |
|-------------|---------|
| ISO 4217 | International standard for currency codes (e.g., USD, EUR) |
| ISO 8601 | International standard for date/time format (YYYY-MM-DD) |

---

## 9.4 QUICK REFERENCE CARDS

### 9.4.1 API Endpoint Quick Reference

```mermaid
flowchart LR
    subgraph PublicEndpoints[Public Endpoints]
        Health["/api/health"]
        Assets["/api/assets"]
        AssetDetail["/api/assets/{id}"]
        Relationships["/api/relationships"]
        Metrics["/api/metrics"]
        Visualization["/api/visualization"]
        Classes["/api/asset-classes"]
        Sectors["/api/sectors"]
    end

    subgraph ProtectedEndpoints[Protected Endpoints]
        Token["POST /token"]
        UserMe["/api/users/me"]
    end

    Client([Client]) --> PublicEndpoints
    Client --> ProtectedEndpoints
```

| Endpoint | Method | Authentication | Rate Limited |
|----------|--------|----------------|--------------|
| `/` | GET | No | No |
| `/api/health` | GET | No | No |
| `/token` | POST | No | Yes (5/min) |
| `/api/assets` | GET | No | No |
| `/api/assets/{id}` | GET | No | No |
| `/api/assets/{id}/relationships` | GET | No | No |
| `/api/relationships` | GET | No | No |
| `/api/metrics` | GET | No | No |
| `/api/visualization` | GET | No | No |
| `/api/asset-classes` | GET | No | No |
| `/api/sectors` | GET | No | No |
| `/api/users/me` | GET | Yes | Yes (10/min) |

### 9.4.2 Development Commands Quick Reference

| Task | Command |
|------|---------|
| Start FastAPI Backend | `uvicorn api.main:app --reload --port 8000` |
| Start Next.js Frontend | `cd frontend && npm run dev` |
| Start Gradio UI | `python app.py` |
| Run Python Tests | `pytest` |
| Run Tests with Coverage | `pytest --cov=api --cov=src --cov-report=html` |
| Run Frontend Tests | `cd frontend && npm test` |
| Docker Build | `docker-compose up --build` |
| Lint Python Code | `flake8 && black --check . && isort --check-only .` |

### 9.4.3 Domain Model Validation Rules

| Entity | Field | Rule |
|--------|-------|------|
| Asset | id, symbol, name | Non-empty string required |
| Asset | price | Non-negative float required |
| Asset | market_cap | Non-negative float (optional) |
| Asset | currency | 3-character ISO code |
| RegulatoryEvent | impact_score | Range [-1.0, 1.0] |
| RegulatoryEvent | date | ISO 8601 format (YYYY-MM-DD) |
| Relationship | strength | Normalized range [0.0, 1.0] |

---

## 9.5 DOCUMENT CROSS-REFERENCE INDEX

This index maps key topics to their primary documentation locations within this Technical Specification.

| Topic | Primary Section(s) |
|-------|-------------------|
| Asset Class Definitions | 1.2.2, 2.1.2, 6.2.2 |
| Authentication System | 5.4.3, 6.4.2, 6.4.3 |
| CI/CD Pipeline | 8.6 |
| CORS Configuration | 5.4.5, 6.3.1.5, 6.4.5 |
| Database Schema | 5.6, 6.2.2, 6.2.3 |
| Deployment Options | 5.5, 8.2-8.5 |
| Environment Variables | 6.2.13, 6.3.6, 6.4.7 |
| Error Handling | 4.5, 5.4.2, 6.3.2.3 |
| Feature Catalog | 2.1 |
| Graph Engine | 2.1.3, 5.1.2, 5.2 |
| Integration Architecture | 6.3 |
| Metrics & Analytics | 2.1.5 (F-010), 4.3, 5.4.1 |
| Rate Limiting | 2.1.4 (F-007), 5.4.4, 6.4.4 |
| Relationship Types | 1.2.2, 2.1.3, 6.2.2.3 |
| Security Architecture | 3.8, 6.4 |
| Technology Stack | 1.2.3, 3.1-3.4 |
| UI Technologies | 7.2 |
| Visualization Features | 2.1.5, 4.3.2, 7.3 |

---

## 9.6 REFERENCES

### 9.6.1 Source Files Examined

| Path | Description |
|------|-------------|
| `app.py` | Gradio UI implementation with tabbed interface |
| `api/main.py` | FastAPI application with endpoints, CORS, rate limiting |
| `api/auth.py` | JWT authentication and user management |
| `api/database.py` | SQLite database connection management |
| `src/models/financial_models.py` | Domain model definitions and validation |
| `src/logic/asset_graph.py` | Graph engine implementation |
| `src/data/real_data_fetcher.py` | Yahoo Finance integration with caching |
| `src/data/sample_data.py` | Sample database generation |
| `src/data/database.py` | SQLAlchemy ORM configuration |
| `src/data/db_models.py` | ORM model definitions |
| `src/data/repository.py` | Repository pattern implementation |
| `src/reports/schema_report.py` | Schema documentation generator |
| `src/visualizations/graph_visuals.py` | 3D visualization generation |
| `src/visualizations/graph_2d_visuals.py` | 2D visualization generation |
| `mcp_server.py` | Model Context Protocol server |
| `migrations/001_initial.sql` | Database DDL schema |
| `requirements.txt` | Python dependencies |
| `frontend/package.json` | Frontend dependencies |
| `Dockerfile` | Container configuration |
| `docker-compose.yml` | Container orchestration |
| `vercel.json` | Serverless deployment configuration |
| `.circleci/config.yml` | CircleCI pipeline configuration |
| `.github/workflows/` | GitHub Actions workflow definitions |

### 9.6.2 Technical Specification Sections Referenced

| Section | Topic |
|---------|-------|
| 1.1 Executive Summary | System overview and business context |
| 1.2 System Overview | Architecture and technology stack |
| 2.1 Feature Catalog | Complete feature descriptions |
| 2.6 Assumptions and Constraints | System limitations |
| 3.4 Open Source Dependencies | Dependency specifications |
| 3.5 Third-Party Services | External integrations |
| 5.1 High-Level Architecture | Architectural patterns |
| 5.4 Cross-Cutting Concerns | Logging, error handling, authentication |
| 5.5 Deployment Architecture | Deployment options |
| 6.2 Database Design | Schema and indexing |
| 6.3 Integration Architecture | API design and protocols |
| 6.4 Security Architecture | Security framework |
| 7.2 Core UI Technologies | Frontend specifications |
| 8.6 CI/CD Pipeline | Build and deployment automation |

### 9.6.3 External Standards Referenced

| Standard | Usage |
|----------|-------|
| ISO 4217 | Currency code validation (3-character format) |
| ISO 8601 | Date format validation (YYYY-MM-DD) |
| OpenAPI 3.x | API documentation specification |
| OAuth2 | Bearer token authentication scheme |
| RFC 7519 | JSON Web Token standard |
